import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from django.db import transaction

from apps.bookings.models import (
    ActivitySchedule,
    ActivityScheduleSlot,
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
    warn_if_capacity_overbooked,
)
from apps.core.privacy import mask_contact_text
from apps.ingestion.parsers import detect_provider, get_parser
from apps.ingestion.parsers.common import (
    EVENT_CANCELLATION,
    STATUS_CANCELLED,
    STATUS_MANUAL_REVIEW,
    extract_forwarded_headers,
)
from apps.ingestion.providers import provider_display_name

from .models import RawEmail

LOW_CONFIDENCE_THRESHOLD = 0.8
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
        if _should_ignore_non_booking_email(raw_email):
            raw_email.parse_status = RawEmail.ParseStatus.IGNORED
            raw_email.parse_error = "Ignored non-booking email."
            raw_email.save(update_fields=["parse_status", "parse_error", "updated_at"])
            return None
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

    if _should_ignore_non_booking_email(raw_email):
        raw_email.parse_status = RawEmail.ParseStatus.IGNORED
        raw_email.parse_error = "Ignored non-booking email."
        raw_email.save(update_fields=["parse_status", "parse_error", "updated_at"])
        return None

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
            details=_warnings_review_details(parsed_booking.warnings),
        )
    else:
        raw_email.parse_status = RawEmail.ParseStatus.PARSED

    if parsed_booking.event_type == EVENT_CANCELLATION and booking:
        _create_cancellation_without_booking_review_if_needed(
            raw_email=raw_email,
            booking=booking,
            was_created=booking.events.filter(raw_email=raw_email).count() == 1,
        )

    has_missing_data = _create_completeness_review_items(
        raw_email=raw_email,
        booking=booking,
    )

    product_mismatch = not alias_match.alias and bool(parsed_booking.raw_product_name)
    if product_mismatch:
        _create_review_item(
            raw_email=raw_email,
            booking=booking,
            issue_type=ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
            title="Unmapped provider product",
            details=_provider_alias_review_details(parsed_booking, alias_match),
        )
        _create_review_item(
            raw_email=raw_email,
            booking=booking,
            issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
            title="Product title is not mapped",
            details=_provider_alias_review_details(parsed_booking, alias_match),
        )

    if has_missing_data or product_mismatch:
        raw_email.parse_status = RawEmail.ParseStatus.NEEDS_REVIEW

    if warn_if_capacity_overbooked(booking=booking, raw_email=raw_email):
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
    return booking


def _create_completeness_review_items(
    *,
    raw_email: RawEmail,
    booking: Booking,
) -> bool:
    checks = [
        (
            not booking.activity_id,
            ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
            "Product match missing",
            "No approved provider alias maps this raw product to a Tour/Activity.",
        ),
        (
            booking.active_travel_date is None,
            ReviewQueueItem.IssueType.DATE_MISSING,
            "Booking date missing",
            "Parser did not find an operational booking date.",
        ),
        (
            _booking_time_missing(booking),
            ReviewQueueItem.IssueType.TIME_MISSING,
            "Booking time missing",
            "Parser did not find a start time or full-day/half-day slot.",
        ),
        (
            booking.active_traveler_count is None,
            ReviewQueueItem.IssueType.TRAVELER_COUNT_MISSING,
            "Traveler count missing",
            "Parser did not find a traveler count.",
        ),
        (
            not booking.lead_traveler_name,
            ReviewQueueItem.IssueType.LEAD_TRAVELER_MISSING,
            "Lead traveler missing",
            "Parser did not find a lead traveler name.",
        ),
    ]
    created = False
    for failed, issue_type, title, details in checks:
        if not failed:
            continue
        _create_review_item(
            raw_email=raw_email,
            booking=booking,
            issue_type=issue_type,
            title=title,
            details=details,
        )
        created = True
    return created


def _booking_time_missing(booking: Booking) -> bool:
    if booking.active_start_time:
        return False
    return booking.active_slot_type not in {
        "full_day",
        "half_day",
    }


def match_product_alias(parsed_booking) -> ProviderAliasMatch:
    provider = _get_or_create_provider(parsed_booking.provider_code)
    queryset = ProviderAlias.objects.filter(provider=provider)
    approved = queryset.filter(approved=True)

    if parsed_booking.provider_product_code:
        alias = approved.filter(
            provider_product_code=parsed_booking.provider_product_code,
            provider_option_code=parsed_booking.provider_option_code or "",
        ).first()
        if alias:
            return ProviderAliasMatch(alias=alias)

    if parsed_booking.raw_product_name:
        exact = _normalized_alias_match(
            approved,
            product_name=parsed_booking.raw_product_name,
            option_name=parsed_booking.raw_option_name,
            include_option=True,
        )
        if not exact and parsed_booking.raw_option_name:
            exact = _normalized_alias_match(
                approved,
                product_name=parsed_booking.raw_product_name,
                option_name="",
                include_option=False,
            )
        if exact:
            return ProviderAliasMatch(alias=exact)

        exact_suggestions = _normalized_alias_suggestions(
            queryset,
            product_name=parsed_booking.raw_product_name,
            option_name=parsed_booking.raw_option_name,
        )
        if exact_suggestions:
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
        matched_slot = _slot_for_parsed_time(alias_match.alias, parsed)
        values["schedule_slot"] = matched_slot
        _apply_alias_slot_values(active_values, alias_match.alias, slot=matched_slot)
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference=parsed.provider_booking_reference,
        source_thread_id=raw_email.gmail_thread_id,
        last_email_received_at=raw_email.received_at,
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
        if _skip_empty_provider_update(
            field_name=field_name,
            old_value=diff["old"],
            new_value=diff["new"],
        ):
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

    alias_values = _alias_values(alias_match, parsed)
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

    if raw_email.received_at:
        booking.last_email_received_at = raw_email.received_at
    if raw_email.gmail_thread_id:
        booking.source_thread_id = raw_email.gmail_thread_id
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


def _should_ignore_non_booking_email(raw_email: RawEmail) -> bool:
    subject = raw_email.subject or ""
    body_text = raw_email.body_text or ""
    haystack = f"{subject}\n{body_text}".lower()
    if _has_booking_intent(haystack):
        return False
    return bool(
        re.search(
            r"\b(newsletter|guest\s*list|guestlist|report|reminder|"
            r"question about activity|inquiry|enquiry|digest|promotion|"
            r"marketing|survey|payout|invoice)\b",
            haystack,
            re.IGNORECASE,
        )
    )


def _has_booking_intent(haystack: str) -> bool:
    return bool(
        re.search(
            r"\b(new booking|booking details|booking reference|booking ref|"
            r"booking number|booking request|booking canceled|booking cancelled|"
            r"booking changed|order id|order number|reference id|confirmed booking|"
            r"cancellation)\b",
            haystack,
            re.IGNORECASE,
        )
    )


def _skip_empty_provider_update(
    *,
    field_name: str,
    old_value: Any,
    new_value: Any,
) -> bool:
    if field_name == "status":
        return False
    if old_value in (None, "", [], {}):
        return False
    return new_value in (None, "", [], {})


def _get_or_create_provider(provider_code: str) -> Provider:
    provider, _created = Provider.objects.get_or_create(
        code=provider_code,
        defaults={
            "name": provider_display_name(provider_code),
            "parser_key": provider_code,
        },
    )
    canonical_name = provider_display_name(provider_code)
    if provider.name != canonical_name:
        provider.name = canonical_name
        provider.save(update_fields=["name", "updated_at"])
    return provider


def _alias_values(alias_match: ProviderAliasMatch, parsed) -> dict[str, Any]:
    if not alias_match.alias:
        return {}
    matched_slot = _slot_for_parsed_time(alias_match.alias, parsed)
    values = {
        "activity": alias_match.alias.linked_activity,
        "schedule_slot": matched_slot,
    }
    _apply_alias_slot_values(values, alias_match.alias, slot=matched_slot)
    return values


def _apply_alias_slot_values(
    values: dict[str, Any],
    alias: ProviderAlias,
    *,
    slot=None,
) -> None:
    slot = slot if slot is not None else alias.linked_slot
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
        details=_manual_conflict_details(conflicts),
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
    details = [f"Raw product: {parsed.raw_product_name or 'Missing tour/activity'}"]
    if parsed.raw_option_name:
        details.append(f"Raw option: {parsed.raw_option_name}")
    if alias_match.suggestions:
        details.append("Suggested mappings:")
        for suggestion in alias_match.suggestions:
            option = (
                f" / {suggestion['raw_option_name']}"
                if suggestion.get("raw_option_name")
                else ""
            )
            details.append(
                "- "
                f"{suggestion['linked_activity']} from "
                f"{suggestion['raw_product_name']}{option} "
                f"({int(suggestion['score'] * 100)}% match)"
            )
    return "\n".join(details)


def _warnings_review_details(warnings: list[str]) -> str:
    if not warnings:
        return "Parser confidence was below the automatic approval threshold."
    labels = {
        "provider_missing": "provider",
        "reference_missing": "booking reference",
        "travel_date_missing": "travel date",
        "product_name_missing": "tour/activity",
        "traveler_count_missing": "participant count",
        "forwarded_email": "forwarded email",
        "needs_review": "manual review",
    }
    readable = [labels.get(warning, warning.replace("_", " ")) for warning in warnings]
    return "Check " + ", ".join(readable) + "."


def _manual_conflict_details(conflicts: dict[str, dict[str, Any]]) -> str:
    if not conflicts:
        return "Provider update conflicts with a manual override."
    lines = []
    for field_name, values in conflicts.items():
        lines.append(
            f"{field_name.replace('_', ' ').title()} was kept from manual edit; "
            f"provider sent {values.get('provider_value') or 'blank'}."
        )
    return "\n".join(lines)


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
        _normalize_alias_text(part) for part in [product_name, option_name] if part
    )


def _normalize_alias_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def _normalized_alias_match(
    queryset,
    *,
    product_name: str,
    option_name: str | None,
    include_option: bool,
) -> ProviderAlias | None:
    target_product = _normalize_alias_text(product_name)
    target_option = _normalize_alias_text(option_name)
    for alias in queryset:
        if _normalize_alias_text(alias.raw_product_name) != target_product:
            continue
        if (
            include_option
            and _normalize_alias_text(alias.raw_option_name) != target_option
        ):
            continue
        return alias
    return None


def _normalized_alias_suggestions(
    queryset,
    *,
    product_name: str,
    option_name: str | None,
) -> list[ProviderAlias]:
    matches = []
    target_product = _normalize_alias_text(product_name)
    target_option = _normalize_alias_text(option_name)
    for alias in queryset:
        if _normalize_alias_text(alias.raw_product_name) != target_product:
            continue
        if _normalize_alias_text(alias.raw_option_name) not in {"", target_option}:
            continue
        matches.append(alias)
    return matches


def _slot_for_parsed_time(
    alias: ProviderAlias,
    parsed,
) -> ActivityScheduleSlot | None:
    if not parsed.start_time:
        return alias.linked_slot
    return (
        ActivityScheduleSlot.objects.filter(
            schedule__activity=alias.linked_activity,
            schedule__schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
            start_time=parsed.start_time,
            active=True,
        )
        .order_by("id")
        .first()
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
