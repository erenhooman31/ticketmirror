from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from django.db import transaction

from apps.bookings.models import (
    Booking,
    BookingEvent,
    Provider,
    ProviderAlias,
    ReviewQueueItem,
)
from apps.bookings.services import (
    active_updates_from_provider_values,
    diff_field_values,
    is_manually_overridden,
    provider_update_conflicts,
)
from apps.core.privacy import mask_contact_text
from apps.ingestion.parsers import detect_provider, get_parser
from apps.ingestion.parsers.common import (
    EVENT_CANCELLATION,
    STATUS_CANCELLED,
    STATUS_MANUAL_REVIEW,
    extract_forwarded_headers,
)

from .models import RawEmail

LOW_CONFIDENCE_THRESHOLD = 1.0
PARSER_VERSION = "deterministic-v1"


@dataclass(frozen=True)
class ProviderAliasMatch:
    alias: ProviderAlias | None = None
    suggestions: list[dict[str, Any]] = field(default_factory=list)


@transaction.atomic
def store_raw_email(payload: dict) -> RawEmail:
    forwarded = extract_forwarded_headers(payload.get("body_text", ""))
    raw_email, created = RawEmail.objects.update_or_create(
        gmail_message_id=payload["gmail_message_id"],
        defaults={
            "gmail_thread_id": payload.get("gmail_thread_id"),
            "gmail_history_id": payload.get("gmail_history_id"),
            "gmail_outer_sender": payload.get("gmail_outer_sender", ""),
            "original_forwarded_sender": payload.get("original_forwarded_sender")
            or forwarded.sender,
            "subject": payload.get("subject", ""),
            "received_at": payload["received_at"],
            "body_text": payload.get("body_text", ""),
            "body_html": payload.get("body_html"),
        },
    )
    raw_email._was_created = created
    return raw_email


@transaction.atomic
def process_gmail_message(message_data: dict) -> RawEmail:
    raw_email = store_raw_email(message_data)
    if not getattr(raw_email, "_was_created", False) and raw_email.parse_status != (
        RawEmail.ParseStatus.PENDING
    ):
        return raw_email
    process_raw_email(raw_email.id)
    raw_email.refresh_from_db()
    return raw_email


@transaction.atomic
def process_raw_email(raw_email_id: int) -> Booking | None:
    raw_email = RawEmail.objects.select_for_update().get(id=raw_email_id)
    provider_code, _confidence = detect_provider(
        raw_email.subject,
        raw_email.gmail_outer_sender,
        raw_email.body_text,
    )
    if not provider_code:
        raw_email.parse_status = RawEmail.ParseStatus.NEEDS_REVIEW
        raw_email.parse_error = "Provider could not be detected."
        raw_email.save(update_fields=["parse_status", "parse_error", "updated_at"])
        _create_review_item(
            raw_email=raw_email,
            booking=None,
            issue_type=ReviewQueueItem.IssueType.PROVIDER_NOT_DETECTED,
            title="Provider not detected",
            details="No deterministic provider pattern matched this email.",
        )
        return None

    provider = _get_or_create_provider(provider_code)
    raw_email.provider_detected = provider
    raw_email.parser_version = PARSER_VERSION
    raw_email.save(update_fields=["provider_detected", "parser_version", "updated_at"])

    parser = get_parser(provider.parser_key or provider.code)
    if parser is None:
        raw_email.parse_status = RawEmail.ParseStatus.FAILED
        raw_email.parse_error = f"No parser registered for {provider.code}."
        raw_email.save(update_fields=["parse_status", "parse_error", "updated_at"])
        _create_review_item(
            raw_email=raw_email,
            booking=None,
            issue_type=ReviewQueueItem.IssueType.PARSER_ERROR,
            title="Parser not registered",
            details=raw_email.parse_error,
        )
        return None

    try:
        parsed = parser.parse(raw_email)
    except Exception as exc:
        raw_email.parse_status = RawEmail.ParseStatus.FAILED
        raw_email.parse_error = mask_contact_text(str(exc), limit=500)
        raw_email.save(update_fields=["parse_status", "parse_error", "updated_at"])
        _create_review_item(
            raw_email=raw_email,
            booking=None,
            issue_type=ReviewQueueItem.IssueType.PARSER_ERROR,
            title="Parser error",
            details=raw_email.parse_error,
        )
        return None

    return upsert_booking_from_parsed(raw_email, parsed)


@transaction.atomic
def upsert_booking_from_parsed(raw_email: RawEmail, parsed_booking) -> Booking | None:
    provider = _get_or_create_provider(parsed_booking.provider_code)
    raw_email.provider_detected = provider
    raw_email.parser_version = PARSER_VERSION
    raw_email.parse_error = None

    if not parsed_booking.provider_booking_reference:
        raw_email.parse_status = RawEmail.ParseStatus.NEEDS_REVIEW
        raw_email.save(
            update_fields=[
                "provider_detected",
                "parser_version",
                "parse_status",
                "parse_error",
                "updated_at",
            ]
        )
        _create_review_item(
            raw_email=raw_email,
            booking=None,
            issue_type=ReviewQueueItem.IssueType.REFERENCE_MISSING,
            title="Booking reference missing",
            details="Parser could not find a stable provider booking reference.",
        )
        return None

    alias_match = match_product_alias(parsed_booking)
    provider_values = _provider_values_from_parsed(parsed_booking)
    if parsed_booking.confidence < LOW_CONFIDENCE_THRESHOLD:
        provider_values["status"] = STATUS_MANUAL_REVIEW
    if parsed_booking.event_type == EVENT_CANCELLATION:
        provider_values["status"] = STATUS_CANCELLED

    booking = (
        Booking.objects.select_for_update()
        .filter(
            provider=provider,
            provider_booking_reference=parsed_booking.provider_booking_reference,
        )
        .first()
    )
    if booking is None:
        booking = _create_booking(
            provider=provider,
            raw_email=raw_email,
            parsed=parsed_booking,
            provider_values=provider_values,
            alias_match=alias_match,
        )
    else:
        booking = _update_booking(
            booking=booking,
            raw_email=raw_email,
            parsed=parsed_booking,
            provider_values=provider_values,
            alias_match=alias_match,
        )

    if parsed_booking.confidence < LOW_CONFIDENCE_THRESHOLD:
        raw_email.parse_status = RawEmail.ParseStatus.NEEDS_REVIEW
        _create_review_item(
            raw_email=raw_email,
            booking=booking,
            issue_type=ReviewQueueItem.IssueType.LOW_CONFIDENCE_PARSE,
            title="Low confidence parse",
            details=", ".join(parsed_booking.warnings),
        )
    else:
        raw_email.parse_status = RawEmail.ParseStatus.PARSED

    if parsed_booking.event_type == EVENT_CANCELLATION and booking:
        _create_cancellation_without_booking_review_if_needed(
            raw_email=raw_email,
            booking=booking,
            was_created=booking.events.filter(raw_email=raw_email).count() == 1,
        )

    if not alias_match.alias and parsed_booking.raw_product_name:
        _create_review_item(
            raw_email=raw_email,
            booking=booking,
            issue_type=ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
            title="Unmapped provider product",
            details=_provider_alias_review_details(parsed_booking, alias_match),
        )

    raw_email.save(
        update_fields=[
            "provider_detected",
            "parser_version",
            "parse_status",
            "parse_error",
            "updated_at",
        ]
    )
    return booking


def match_product_alias(parsed_booking) -> ProviderAliasMatch:
    provider = _get_or_create_provider(parsed_booking.provider_code)
    queryset = ProviderAlias.objects.filter(provider=provider)
    approved = queryset.filter(approved=True)

    if parsed_booking.provider_product_code:
        alias = approved.filter(
            provider_product_code=parsed_booking.provider_product_code,
            provider_option_code=parsed_booking.provider_option_code,
        ).first()
        if alias:
            return ProviderAliasMatch(alias=alias)

    if parsed_booking.raw_product_name:
        exact = approved.filter(
            raw_product_name__iexact=parsed_booking.raw_product_name,
            raw_option_name__iexact=parsed_booking.raw_option_name or "",
        ).first()
        if exact:
            return ProviderAliasMatch(alias=exact)

        exact_suggestions = queryset.filter(
            raw_product_name__iexact=parsed_booking.raw_product_name,
            raw_option_name__iexact=parsed_booking.raw_option_name or "",
        )
        if exact_suggestions.exists():
            return ProviderAliasMatch(
                suggestions=[
                    _alias_suggestion(alias, 1.0) for alias in exact_suggestions[:3]
                ]
            )

    return ProviderAliasMatch(
        suggestions=_fuzzy_alias_suggestions(queryset, parsed_booking)
    )


def _create_booking(
    *,
    provider: Provider,
    raw_email: RawEmail,
    parsed,
    provider_values: dict[str, Any],
    alias_match: ProviderAliasMatch,
) -> Booking:
    values = provider_values.copy()
    active_values = {
        "active_travel_date": values["provider_travel_date"],
        "active_start_time": values["provider_start_time"],
        "active_end_time": values["provider_end_time"],
        "active_slot_type": values["provider_slot_type"],
        "active_traveler_count": values["provider_traveler_count"],
    }
    if alias_match.alias:
        values["activity"] = alias_match.alias.linked_activity
        values["schedule_slot"] = alias_match.alias.linked_slot
        _apply_alias_slot_values(active_values, alias_match.alias)
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference=parsed.provider_booking_reference,
        **values,
        **active_values,
    )
    _create_booking_event(
        booking=booking,
        raw_email=raw_email,
        event_type=parsed.event_type,
        old_values={},
        new_values={**parsed.payload, "provider_values": _json_safe(provider_values)},
    )
    return booking


def _update_booking(
    *,
    booking: Booking,
    raw_email: RawEmail,
    parsed,
    provider_values: dict[str, Any],
    alias_match: ProviderAliasMatch,
) -> Booking:
    old_values = {}
    new_values = {}
    provider_diffs = diff_field_values(booking, provider_values)
    for field_name, diff in provider_diffs.items():
        if field_name == "status" and is_manually_overridden(booking, "status"):
            continue
        old_values[field_name] = diff["old"]
        new_values[field_name] = diff["new"]
        setattr(booking, field_name, diff["new"])

    active_values = active_updates_from_provider_values(
        booking=booking,
        provider_values=provider_values,
    )
    active_diffs = diff_field_values(booking, active_values)
    for field_name, diff in active_diffs.items():
        old_values[field_name] = diff["old"]
        new_values[field_name] = diff["new"]
        setattr(booking, field_name, diff["new"])

    alias_values = _alias_values(alias_match)
    alias_diffs = diff_field_values(booking, alias_values)
    for field_name, diff in alias_diffs.items():
        if field_name.startswith("active_") and is_manually_overridden(
            booking,
            field_name,
        ):
            continue
        old_values[field_name] = diff["old"]
        new_values[field_name] = diff["new"]
        setattr(booking, field_name, diff["new"])

    booking.save()
    conflicts = provider_update_conflicts(
        booking=booking,
        provider_values=provider_values,
    )
    if conflicts:
        _create_manual_conflict_review(
            raw_email=raw_email,
            booking=booking,
            conflicts=conflicts,
        )
        _create_booking_event(
            booking=booking,
            raw_email=raw_email,
            event_type=BookingEvent.EventType.CONFLICT_DETECTED,
            old_values={},
            new_values={"manual_override_conflicts": _json_safe(conflicts)},
        )

    event_type = (
        BookingEvent.EventType.EMAIL_CANCELLATION
        if parsed.event_type == EVENT_CANCELLATION
        else BookingEvent.EventType.EMAIL_UPDATE
    )
    _create_booking_event(
        booking=booking,
        raw_email=raw_email,
        event_type=event_type,
        old_values=_json_safe(old_values),
        new_values={**parsed.payload, "changed_values": _json_safe(new_values)},
    )
    return booking


def _provider_values_from_parsed(parsed) -> dict[str, Any]:
    return {
        "provider_order_reference": parsed.provider_order_reference,
        "status": parsed.status,
        "raw_product_name": parsed.raw_product_name,
        "raw_option_name": parsed.raw_option_name,
        "provider_product_code": parsed.provider_product_code,
        "provider_option_code": parsed.provider_option_code,
        "provider_travel_date": parsed.travel_date,
        "provider_start_time": parsed.start_time,
        "provider_end_time": parsed.end_time,
        "provider_slot_type": parsed.slot_type,
        "provider_traveler_count": parsed.traveler_count,
        "lead_traveler_name": parsed.lead_traveler_name,
        "lead_traveler_email": parsed.lead_traveler_email,
        "lead_traveler_phone": parsed.lead_traveler_phone,
        "traveler_names": parsed.traveler_names,
        "ticket_breakdown": parsed.ticket_breakdown,
        "language": parsed.language,
        "pickup_location": parsed.pickup_location,
        "meeting_point": parsed.meeting_point,
        "special_requirements": parsed.special_requirements,
        "customer_message": parsed.customer_message,
        "price": parsed.price,
        "payment_status": parsed.payment_status,
    }


def _get_or_create_provider(provider_code: str) -> Provider:
    provider, _created = Provider.objects.get_or_create(
        code=provider_code,
        defaults={
            "name": provider_code.replace("-", " ").title(),
            "parser_key": provider_code,
        },
    )
    return provider


def _alias_values(alias_match: ProviderAliasMatch) -> dict[str, Any]:
    if not alias_match.alias:
        return {}
    values = {
        "activity": alias_match.alias.linked_activity,
        "schedule_slot": alias_match.alias.linked_slot,
    }
    _apply_alias_slot_values(values, alias_match.alias)
    return values


def _apply_alias_slot_values(values: dict[str, Any], alias: ProviderAlias) -> None:
    slot = alias.linked_slot
    if not slot:
        return
    values.setdefault("active_start_time", slot.start_time)
    values.setdefault("active_end_time", slot.end_time)
    values.setdefault("active_slot_type", slot.slot_type)
    if not values.get("active_start_time"):
        values["active_start_time"] = slot.start_time
    if not values.get("active_end_time"):
        values["active_end_time"] = slot.end_time
    if not values.get("active_slot_type"):
        values["active_slot_type"] = slot.slot_type


def _create_booking_event(
    *,
    booking: Booking,
    raw_email: RawEmail,
    event_type: str,
    old_values: dict,
    new_values: dict,
) -> BookingEvent:
    return BookingEvent.objects.create(
        booking=booking,
        event_type=event_type,
        source=(
            BookingEvent.Source.EMAIL
            if event_type.startswith("email_")
            else BookingEvent.Source.SYSTEM
        ),
        old_values=old_values,
        new_values=new_values,
        raw_email=raw_email,
    )


def _create_review_item(
    *,
    raw_email: RawEmail,
    booking: Booking | None,
    issue_type: str,
    title: str,
    details: str,
) -> ReviewQueueItem:
    review, _created = ReviewQueueItem.objects.update_or_create(
        raw_email=raw_email,
        booking=booking,
        issue_type=issue_type,
        status=ReviewQueueItem.Status.OPEN,
        defaults={"title": title, "details": details},
    )
    return review


def _create_manual_conflict_review(
    *,
    raw_email: RawEmail,
    booking: Booking,
    conflicts: dict[str, dict[str, Any]],
) -> None:
    _create_review_item(
        raw_email=raw_email,
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.MANUAL_OVERRIDE_CONFLICT,
        title="Provider update conflicts with manual override",
        details=str(_json_safe(conflicts)),
    )


def _create_cancellation_without_booking_review_if_needed(
    *,
    raw_email: RawEmail,
    booking: Booking,
    was_created: bool,
) -> None:
    if not was_created:
        return
    _create_review_item(
        raw_email=raw_email,
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.CANCELLATION_WITHOUT_BOOKING,
        title="Cancellation received before known booking",
        details="A cancellation email created this booking record.",
    )


def _provider_alias_review_details(parsed, alias_match: ProviderAliasMatch) -> str:
    details = [f"Raw product: {parsed.raw_product_name}"]
    if parsed.raw_option_name:
        details.append(f"Raw option: {parsed.raw_option_name}")
    if alias_match.suggestions:
        details.append(f"Suggestions: {alias_match.suggestions}")
    return "\n".join(details)


def _fuzzy_alias_suggestions(queryset, parsed) -> list[dict[str, Any]]:
    target = _alias_key(parsed.raw_product_name, parsed.raw_option_name)
    if not target:
        return []
    scored = []
    for alias in queryset:
        score = SequenceMatcher(
            None,
            target,
            _alias_key(alias.raw_product_name, alias.raw_option_name),
        ).ratio()
        if score >= 0.65:
            scored.append(_alias_suggestion(alias, round(score, 2)))
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:3]


def _alias_suggestion(alias: ProviderAlias, score: float) -> dict[str, Any]:
    return {
        "id": alias.id,
        "raw_product_name": alias.raw_product_name,
        "raw_option_name": alias.raw_option_name,
        "linked_activity": alias.linked_activity.name,
        "approved": alias.approved,
        "score": score,
    }


def _alias_key(product_name: str | None, option_name: str | None) -> str:
    return " ".join(
        part.lower().strip() for part in [product_name, option_name] if part
    )


def _json_safe(values: dict[str, Any]) -> dict[str, Any]:
    safe = {}
    for key, value in values.items():
        if hasattr(value, "isoformat"):
            safe[key] = value.isoformat()
        elif isinstance(value, dict):
            safe[key] = _json_safe(value)
        elif isinstance(value, (list, tuple)):
            safe[key] = [
                (
                    _json_safe({"value": item})["value"]
                    if isinstance(item, dict) or hasattr(item, "isoformat")
                    else str(item) if hasattr(item, "pk") else item
                )
                for item in value
            ]
        elif hasattr(value, "pk"):
            safe[key] = str(value)
        else:
            safe[key] = value
    return safe
