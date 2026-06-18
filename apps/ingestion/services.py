import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.bookings.models import (
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
    resolve_schedule_slot_details,
    review_issue_is_obsolete_for_context,
    warn_if_capacity_overbooked,
)
from apps.core.privacy import mask_contact_text
from apps.ingestion.parsers import detect_provider, get_parser
from apps.ingestion.parsers.common import (
    EVENT_CANCELLATION,
    STATUS_CANCELLED,
    decode_body_text,
    effective_message,
    extract_forwarded_headers,
)
from apps.ingestion.providers import provider_display_name
from apps.ingestion.translate import to_english

from .models import RawEmail

LOW_CONFIDENCE_THRESHOLD = 0.8
PARSER_VERSION = "deterministic-v1"


class TranslatedRawEmailView:
    def __init__(
        self,
        raw_email: RawEmail,
        *,
        subject: str,
        body_text: str,
    ) -> None:
        self._raw_email = raw_email
        self._original_subject = raw_email.subject
        self._original_body = raw_email.body_text
        self._translated_subject = subject
        self._translated_body = body_text
        self._translation_applied = (
            subject != raw_email.subject or body_text != raw_email.body_text
        )
        self.subject = subject
        self.body_text = body_text

    def __getattr__(self, name: str):
        return getattr(self._raw_email, name)


def translated_raw_email_view(raw_email: RawEmail):
    translated_subject = to_english(raw_email.subject)
    translated_body = to_english(raw_email.body_text)
    if (
        translated_subject == raw_email.subject
        and translated_body == raw_email.body_text
    ):
        return raw_email
    return TranslatedRawEmailView(
        raw_email,
        subject=translated_subject,
        body_text=translated_body,
    )


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
    parser_email = translated_raw_email_view(raw_email)
    ignore_reason = non_booking_ignore_reason(parser_email)
    if ignore_reason:
        _mark_raw_email_ignored(raw_email, ignore_reason)
        return None

    provider_code, _confidence = detect_provider(
        parser_email.subject,
        parser_email.gmail_outer_sender,
        parser_email.body_text,
    )
    if not provider_code:
        ignore_reason = non_booking_ignore_reason(parser_email)
        if ignore_reason:
            _mark_raw_email_ignored(raw_email, ignore_reason)
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

    ignore_reason = non_booking_ignore_reason(parser_email)
    if ignore_reason:
        _mark_raw_email_ignored(raw_email, ignore_reason)
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
        parsed = parser.parse(parser_email)
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
    if parsed_booking.event_type == EVENT_CANCELLATION:
        provider_values["status"] = STATUS_CANCELLED

    booking = _find_booking_for_parsed(
        provider=provider,
        parsed=parsed_booking,
        provider_values=provider_values,
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
        _promote_booking_identity_if_needed(
            booking=booking,
            provider=provider,
            parsed=parsed_booking,
            raw_email=raw_email,
        )
        booking = _update_booking(
            booking=booking,
            raw_email=raw_email,
            parsed=parsed_booking,
            provider_values=provider_values,
            alias_match=alias_match,
        )

    is_cancellation = _is_cancellation(parsed_booking, booking)

    if parsed_booking.confidence < LOW_CONFIDENCE_THRESHOLD and not is_cancellation:
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

    has_missing_data = False
    product_mismatch = False
    if not is_cancellation:
        has_missing_data = _create_completeness_review_items(
            raw_email=raw_email,
            booking=booking,
        )
        product_mismatch = not alias_match.alias and bool(
            parsed_booking.raw_product_name
        )

    has_slot_review = _create_schedule_slot_review_if_needed(
        raw_email=raw_email,
        booking=booking,
        parsed=parsed_booking,
        alias_match=alias_match,
    )

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

    if has_missing_data or product_mismatch or has_slot_review:
        raw_email.parse_status = RawEmail.ParseStatus.NEEDS_REVIEW

    if warn_if_capacity_overbooked(booking=booking, raw_email=raw_email):
        raw_email.parse_status = RawEmail.ParseStatus.NEEDS_REVIEW

    _resolve_obsolete_review_items(raw_email=raw_email, booking=booking)
    _resolve_obsolete_booking_review_items(booking=booking)

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


def _resolve_obsolete_review_items(*, raw_email: RawEmail, booking: Booking) -> int:
    base_queryset = ReviewQueueItem.objects.select_related("booking").filter(
        raw_email=raw_email,
        status=ReviewQueueItem.Status.OPEN,
    )
    resolved_at = timezone.now()
    resolved = 0

    for review in base_queryset:
        if not review_issue_is_obsolete_for_context(
            issue_type=review.issue_type,
            title=review.title,
            raw_email=raw_email,
            review_booking=review.booking,
            current_booking=booking,
        ):
            continue
        resolved += ReviewQueueItem.objects.filter(id=review.id).update(
            status=ReviewQueueItem.Status.RESOLVED,
            resolved_at=resolved_at,
        )

    return resolved


def _resolve_obsolete_booking_review_items(*, booking: Booking) -> int:
    queryset = ReviewQueueItem.objects.select_related(
        "raw_email",
        "raw_email__provider_detected",
        "booking",
    ).filter(
        booking=booking,
        status=ReviewQueueItem.Status.OPEN,
    )
    resolved_at = timezone.now()
    resolved = 0

    for review in queryset:
        if not review_issue_is_obsolete_for_context(
            issue_type=review.issue_type,
            title=review.title,
            raw_email=review.raw_email,
            review_booking=review.booking,
            current_booking=booking,
        ):
            continue
        resolved += ReviewQueueItem.objects.filter(id=review.id).update(
            status=ReviewQueueItem.Status.RESOLVED,
            resolved_at=resolved_at,
        )

    return resolved


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
        if _provider_omits_field(raw_email, issue_type):
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


def _provider_omits_field(raw_email: RawEmail, issue_type: str) -> bool:
    provider_code = getattr(raw_email.provider_detected, "code", "")
    return (
        provider_code in {"tripster", "sputnik8"}
        and issue_type == ReviewQueueItem.IssueType.LEAD_TRAVELER_MISSING
    )


def _booking_time_missing(booking: Booking) -> bool:
    if booking.active_start_time:
        return False
    return booking.active_slot_type not in {
        "full_day",
        "half_day",
    }


def _is_cancellation(parsed, booking: Booking | None = None) -> bool:
    if parsed.event_type == EVENT_CANCELLATION:
        return True
    if parsed.status == STATUS_CANCELLED:
        return True
    return bool(booking and booking.status == Booking.Status.CANCELLED)


def _preserve_cancelled_status(
    booking: Booking,
    *,
    field_name: str,
    new_value,
) -> bool:
    return (
        field_name == "status"
        and booking.status == Booking.Status.CANCELLED
        and new_value != Booking.Status.CANCELLED
    )


def _create_schedule_slot_review_if_needed(
    *,
    raw_email: RawEmail,
    booking: Booking,
    parsed,
    alias_match: ProviderAliasMatch,
) -> bool:
    if _is_cancellation(parsed, booking):
        return False
    if not alias_match.alias or not parsed.start_time:
        return False
    if is_manually_overridden(booking, "schedule_slot"):
        return False
    resolution = resolve_schedule_slot_details(
        activity=alias_match.alias.linked_activity,
        travel_date=parsed.travel_date,
        start_time=parsed.start_time,
        slot_type=parsed.slot_type,
        fallback_slot=alias_match.alias.linked_slot,
    )
    if not resolution.no_match_for_time:
        return False
    _create_review_item(
        raw_email=raw_email,
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.TIME_MISSING,
        title="Schedule slot needs confirmation",
        details=(
            f"Parsed start time {parsed.start_time:%H:%M} did not match an "
            "active schedule slot for this activity/date. The alias fallback "
            "slot was kept for now."
        ),
    )
    return True


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
        if _preserve_cancelled_status(
            booking,
            field_name=field_name,
            new_value=diff["new"],
        ):
            continue
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
        if _preserve_cancelled_status(
            booking,
            field_name=field_name,
            new_value=diff["new"],
        ):
            continue
        old_values[field_name] = diff["old"]
        new_values[field_name] = diff["new"]
        setattr(booking, field_name, diff["new"])

    alias_values = _alias_values(alias_match, parsed)
    alias_diffs = diff_field_values(booking, alias_values)
    for field_name, diff in alias_diffs.items():
        if field_name == "schedule_slot" and is_manually_overridden(
            booking,
            field_name,
        ):
            continue
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


def _mark_raw_email_ignored(raw_email: RawEmail, reason: str) -> None:
    mark_raw_email_ignored(raw_email, reason)


def mark_raw_email_ignored(raw_email: RawEmail, reason: str) -> None:
    raw_email.parse_status = RawEmail.ParseStatus.IGNORED
    raw_email.parse_error = f"Ignored - not a booking: {reason}."
    raw_email.save(update_fields=["parse_status", "parse_error", "updated_at"])
    _resolve_reviews_for_ignored_raw_email(raw_email)
    _cancel_false_bookings_for_ignored_raw_email(raw_email, reason)


def _resolve_reviews_for_ignored_raw_email(raw_email: RawEmail) -> int:
    return ReviewQueueItem.objects.filter(
        raw_email=raw_email,
        status=ReviewQueueItem.Status.OPEN,
    ).update(status=ReviewQueueItem.Status.RESOLVED, resolved_at=timezone.now())


def _cancel_false_bookings_for_ignored_raw_email(
    raw_email: RawEmail,
    reason: str,
) -> int:
    cancelled = 0
    booking_ids = (
        BookingEvent.objects.filter(raw_email=raw_email, booking__isnull=False)
        .values_list("booking_id", flat=True)
        .distinct()
    )
    for booking in Booking.objects.select_for_update().filter(id__in=booking_ids):
        if not _safe_to_cancel_ignored_raw_email_booking(booking, raw_email):
            continue
        old_status = booking.status
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])
        _create_booking_event(
            booking=booking,
            raw_email=raw_email,
            event_type=BookingEvent.EventType.CONFLICT_DETECTED,
            old_values={"status": old_status},
            new_values={
                "status": Booking.Status.CANCELLED,
                "non_booking_reclassified": True,
                "reason": reason,
            },
        )
        cancelled += 1
    return cancelled


def _safe_to_cancel_ignored_raw_email_booking(
    booking: Booking,
    raw_email: RawEmail,
) -> bool:
    if booking.status in {
        Booking.Status.CANCELLED,
        Booking.Status.REJECTED,
        Booking.Status.DUPLICATE_IGNORED,
    }:
        return False
    if booking.events.exclude(raw_email=raw_email).exists():
        return False
    if (
        raw_email.gmail_thread_id
        and booking.source_thread_id
        and booking.source_thread_id != raw_email.gmail_thread_id
    ):
        return False
    return True


def _should_ignore_non_booking_email(raw_email: RawEmail) -> bool:
    return bool(non_booking_ignore_reason(raw_email))


def non_booking_ignore_reason(raw_email: RawEmail) -> str:
    subject = raw_email.subject or ""
    sender = raw_email.gmail_outer_sender or ""
    body_text = decode_body_text(raw_email.body_text or "")
    original_subject = getattr(raw_email, "_original_subject", subject) or ""
    original_body = getattr(raw_email, "_original_body", body_text) or ""
    effective_subject, effective_sender, _forwarded = effective_message(
        subject=subject,
        sender=sender,
        body_text=body_text,
    )
    subject_lower = effective_subject.casefold()
    haystack = (
        f"{subject}\n{original_subject}\n{effective_subject}\n"
        f"{effective_sender}\n{body_text}\n{original_body}".casefold()
    )
    sender_lower = effective_sender.casefold()
    if "news@sup.getyourguide.com" in sender_lower:
        return "GetYourGuide newsletter sender"
    if "message@reply.getyourguide.com" in sender_lower:
        return "GetYourGuide reply/message sender"
    if "@messages.sputnik8.com" in sender_lower:
        return "Sputnik8 message/interest sender"
    if re.search(
        r"you have a new review|new review(?:\s+of|\s+on)?|новый отзыв|"
        r"question about the activity|ticket received|ticket id",
        haystack,
        re.IGNORECASE,
    ) or subject_lower.startswith("reminder:"):
        return "GetYourGuide service notification"
    if _contains_any(
        haystack,
        [
            "\N{SPEECH BALLOON} \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435",
            (
                "\u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 "
                "\u043a \u0437\u0430\u043a\u0430\u0437\u0443"
            ),
            (
                "\u0432\u0430\u043c \u043f\u0440\u0438\u0448\u043b\u043e "
                "\u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435"
            ),
            "\u043d\u0430\u043f\u043e\u043c\u0438\u043d\u0430\u043d\u0438\u0435",
            "\u043e\u0442\u0437\u044b\u0432",
            (
                "\u0442\u0443\u0440\u0438\u0441\u0442 "
                "\u043e\u0431\u043d\u043e\u0432\u0438\u043b "
                "\u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044e"
            ),
            "message to order",
            "message for order",
            "message about order",
            "message to booking",
            "message for booking",
            "message about booking",
        ],
    ):
        return "provider review/message notification"
    if re.search(
        r"\b(review|rate your|how was your|feedback|newsletter|digest|"
        r"guest\s*list|guestlist|report|reminder|question about activity|"
        r"inquiry|enquiry|promotion|marketing|survey|payout|invoice)\b",
        subject_lower,
        re.IGNORECASE,
    ):
        return "general non-booking notification"
    if re.search(
        r"\b(was viewed by|viewed by|interested|pre-booking|"
        r"you have received a message|updated information|"
        r"no participants|new group tour bookings)\b",
        haystack,
        re.IGNORECASE,
    ):
        return "general non-booking notification"
    if re.search(
        r"интересовал(?:ись|ся)|обновил информацию|нет участников", haystack, re.I
    ):
        return "general non-booking notification"
    if _unsubscribe_only_body(body_text):
        return "unsubscribe-only message"
    if _has_booking_intent(haystack):
        return ""
    return ""


def _has_booking_intent(haystack: str) -> bool:
    return bool(
        re.search(
            r"\b(new booking|booking details|booking reference|booking ref|"
            r"booking number|booking request|booking canceled|booking cancelled|"
            r"booking changed|order id|order number|reference id|confirmed booking|"
            r"cancellation)\b|нов(?:ый|ая)\s+(?:заказ|бронь)|"
            r"отмен(?:а|ён|ен|или|или\s+)?\s+заказ",
            haystack,
            re.IGNORECASE,
        )
    )


def _contains_any(haystack: str, needles: list[str]) -> bool:
    return any(needle.casefold() in haystack for needle in needles)


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


def mark_raw_email_failed(raw_email: RawEmail, exc: Exception, *, title: str) -> None:
    raw_email.parse_status = RawEmail.ParseStatus.FAILED
    raw_email.parse_error = mask_contact_text(str(exc), limit=500)
    raw_email.save(update_fields=["parse_status", "parse_error", "updated_at"])
    _create_review_item(
        raw_email=raw_email,
        booking=None,
        issue_type=ReviewQueueItem.IssueType.PARSER_ERROR,
        title=title,
        details=raw_email.parse_error,
    )


def _unsubscribe_only_body(body_text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", body_text or "").strip().lower()
    if not cleaned:
        return False
    if "unsubscribe" not in cleaned and "отпис" not in cleaned:
        return False
    return not _has_booking_intent(cleaned) and len(cleaned) < 500


def _find_booking_for_parsed(
    *,
    provider: Provider,
    parsed,
    provider_values: dict[str, Any],
) -> Booking | None:
    exact = (
        Booking.objects.select_for_update()
        .filter(
            provider=provider,
            provider_booking_reference=parsed.provider_booking_reference,
        )
        .first()
    )
    if exact:
        return exact
    return _find_bookeo_provisional_booking(parsed, provider_values)


def _find_bookeo_provisional_booking(
    parsed,
    provider_values: dict[str, Any],
) -> Booking | None:
    if parsed.provider_code == "bookeo":
        return None
    bookeo_provider = Provider.objects.filter(code="bookeo").first()
    if not bookeo_provider:
        return None

    bookeo_number = parsed.raw_fields.get("bookeo_booking_number")
    if bookeo_number:
        order_reference = f"Bookeo {bookeo_number}"
        by_bookeo_number = (
            Booking.objects.select_for_update()
            .filter(provider=bookeo_provider)
            .filter(
                Q(provider_booking_reference=bookeo_number)
                | Q(provider_order_reference=order_reference)
            )
            .order_by("-last_email_received_at", "-id")
            .first()
        )
        if by_bookeo_number:
            return by_bookeo_number

    if not (
        parsed.travel_date
        and parsed.start_time
        and parsed.traveler_count is not None
        and parsed.lead_traveler_name
    ):
        return None

    candidates = (
        Booking.objects.select_for_update()
        .filter(
            provider=bookeo_provider,
            provider_travel_date=parsed.travel_date,
            provider_start_time=parsed.start_time,
            provider_traveler_count=parsed.traveler_count,
            lead_traveler_name__iexact=parsed.lead_traveler_name,
        )
        .exclude(status__in=[Booking.Status.CANCELLED, Booking.Status.REJECTED])
        .order_by("-last_email_received_at", "-id")
    )
    if parsed.raw_product_name:
        candidates = candidates.filter(
            Q(raw_product_name__iexact=parsed.raw_product_name)
            | Q(raw_product_name__icontains=provider_values.get("raw_product_name", ""))
            | Q(raw_product_name__icontains=parsed.provider_code)
            | Q(raw_product_name="")
        )
    return candidates.first()


def _promote_booking_identity_if_needed(
    *,
    booking: Booking,
    provider: Provider,
    parsed,
    raw_email: RawEmail,
) -> None:
    old_values = {}
    new_values = {}
    if booking.provider_id != provider.id:
        old_values["provider"] = booking.provider.code
        new_values["provider"] = provider.code
    if booking.provider_booking_reference != parsed.provider_booking_reference:
        old_values["provider_booking_reference"] = booking.provider_booking_reference
        new_values["provider_booking_reference"] = parsed.provider_booking_reference

    if not new_values:
        return

    conflict = (
        Booking.objects.filter(
            provider=provider,
            provider_booking_reference=parsed.provider_booking_reference,
        )
        .exclude(id=booking.id)
        .first()
    )
    if conflict:
        _create_review_item(
            raw_email=raw_email,
            booking=booking,
            issue_type=ReviewQueueItem.IssueType.POSSIBLE_DUPLICATE,
            title="Cross-channel duplicate candidate",
            details=(
                "A matching OTA identity already exists on booking "
                f"{conflict.provider.code} {conflict.provider_booking_reference}."
            ),
        )
        return

    booking.provider = provider
    booking.provider_booking_reference = parsed.provider_booking_reference
    booking.save(update_fields=["provider", "provider_booking_reference", "updated_at"])
    _create_booking_event(
        booking=booking,
        raw_email=raw_email,
        event_type=BookingEvent.EventType.EMAIL_UPDATE,
        old_values=_json_safe(old_values),
        new_values={
            "cross_channel_identity_merge": True,
            "changed_values": _json_safe(new_values),
        },
    )


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
    resolution = resolve_schedule_slot_details(
        activity=alias.linked_activity,
        travel_date=parsed.travel_date,
        start_time=parsed.start_time,
        slot_type=parsed.slot_type,
        fallback_slot=alias.linked_slot,
    )
    return resolution.slot


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
