from django.core.management.base import BaseCommand
from django.db import transaction

from apps.bookings.models import Booking, BookingEvent, ReviewQueueItem
from apps.bookings.services import is_manually_overridden
from apps.ingestion.models import RawEmail
from apps.ingestion.parsers import detect_provider, get_parser
from apps.ingestion.services import (
    _create_review_item,
    _get_or_create_provider,
    _should_ignore_non_booking_email,
    match_product_alias,
    upsert_booking_from_parsed,
)


class Command(BaseCommand):
    help = (
        "Safely fill missing booking display fields from stored raw emails and "
        "parser output without deleting raw records."
    )

    def handle(self, *args, **options):
        stats = {
            "scanned": 0,
            "repaired": 0,
            "sent_to_review": 0,
            "skipped": 0,
        }
        for raw_email in RawEmail.objects.order_by("received_at", "id"):
            stats["scanned"] += 1
            result = self._repair_raw_email(raw_email)
            stats[result] += 1

        self.stdout.write(
            "scanned={scanned} repaired={repaired} sent_to_review={sent_to_review} "
            "skipped={skipped}".format(**stats)
        )

    @transaction.atomic
    def _repair_raw_email(self, raw_email):
        provider_code, _confidence = detect_provider(
            raw_email.subject,
            raw_email.gmail_outer_sender,
            raw_email.body_text,
        )
        if not provider_code:
            if _should_ignore_non_booking_email(raw_email):
                raw_email.parse_status = RawEmail.ParseStatus.IGNORED
                raw_email.parse_error = "Ignored non-booking email."
                raw_email.save(
                    update_fields=["parse_status", "parse_error", "updated_at"]
                )
                return "skipped"
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
            return "sent_to_review"

        provider = _get_or_create_provider(provider_code)
        parser = get_parser(provider.parser_key or provider.code)
        if parser is None:
            raw_email.parse_status = RawEmail.ParseStatus.FAILED
            raw_email.parse_error = f"No parser registered for {provider.code}."
            raw_email.provider_detected = provider
            raw_email.save(
                update_fields=[
                    "provider_detected",
                    "parse_status",
                    "parse_error",
                    "updated_at",
                ]
            )
            _create_review_item(
                raw_email=raw_email,
                booking=None,
                issue_type=ReviewQueueItem.IssueType.PARSER_ERROR,
                title="Parser not registered",
                details=raw_email.parse_error,
            )
            return "sent_to_review"

        parsed = parser.parse(raw_email)
        booking_provider = _get_or_create_provider(parsed.provider_code)
        raw_email.provider_detected = booking_provider
        if not parsed.provider_booking_reference:
            raw_email.parse_status = RawEmail.ParseStatus.NEEDS_REVIEW
            raw_email.parse_error = "Parser could not find a booking reference."
            raw_email.save(
                update_fields=[
                    "provider_detected",
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
            return "sent_to_review"

        booking = Booking.objects.filter(
            provider=booking_provider,
            provider_booking_reference=parsed.provider_booking_reference,
        ).first()
        if booking is None:
            upsert_booking_from_parsed(raw_email, parsed)
            return "repaired"

        changed = self._fill_missing_booking_fields(booking, raw_email, parsed)
        self._ensure_missing_reviews(raw_email, booking)
        resolved_reviews = self._resolve_obsolete_reviews(raw_email, booking)
        raw_email.parse_error = None
        has_open_review = self._has_open_review(raw_email, booking)
        if (
            changed
            or resolved_reviews
            or raw_email.parse_status == RawEmail.ParseStatus.NEEDS_REVIEW
        ):
            raw_email.parse_status = (
                RawEmail.ParseStatus.NEEDS_REVIEW
                if has_open_review
                else RawEmail.ParseStatus.PARSED
            )
            raw_email.save(
                update_fields=[
                    "provider_detected",
                    "parse_status",
                    "parse_error",
                    "updated_at",
                ]
            )
            return "sent_to_review" if has_open_review and not changed else "repaired"

        raw_email.save(update_fields=["provider_detected", "parse_error", "updated_at"])
        if has_open_review:
            return "sent_to_review"
        return "skipped"

    def _fill_missing_booking_fields(self, booking, raw_email, parsed):
        fields = {
            "provider_order_reference": parsed.provider_order_reference,
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
        active_fields = {
            "active_travel_date": parsed.travel_date,
            "active_start_time": parsed.start_time,
            "active_end_time": parsed.end_time,
            "active_slot_type": parsed.slot_type,
            "active_traveler_count": parsed.traveler_count,
        }
        changes = {}
        for field_name, value in fields.items():
            if self._is_empty(getattr(booking, field_name)) and not self._is_empty(
                value
            ):
                setattr(booking, field_name, value)
                changes[field_name] = value

        for field_name, value in active_fields.items():
            if is_manually_overridden(booking, field_name):
                continue
            if self._is_empty(getattr(booking, field_name)) and not self._is_empty(
                value
            ):
                setattr(booking, field_name, value)
                changes[field_name] = value

        alias_match = match_product_alias(parsed)
        if alias_match.alias:
            if booking.activity_id is None:
                booking.activity = alias_match.alias.linked_activity
                changes["activity"] = booking.activity.name
            if booking.schedule_slot_id is None and alias_match.alias.linked_slot:
                booking.schedule_slot = alias_match.alias.linked_slot
                changes["schedule_slot"] = str(booking.schedule_slot)

        if not changes:
            return False

        booking.last_email_received_at = raw_email.received_at
        booking.source_thread_id = raw_email.gmail_thread_id
        booking.save()
        BookingEvent.objects.create(
            booking=booking,
            event_type=BookingEvent.EventType.EMAIL_UPDATE,
            source=BookingEvent.Source.SYSTEM,
            raw_email=raw_email,
            new_values={"repair_changes": self._json_safe(changes)},
        )
        return True

    def _ensure_missing_reviews(self, raw_email, booking):
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
                booking.active_start_time is None
                and booking.active_slot_type not in {"full_day", "half_day"},
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
        for failed, issue_type, title, details in checks:
            if failed:
                _create_review_item(
                    raw_email=raw_email,
                    booking=booking,
                    issue_type=issue_type,
                    title=title,
                    details=details,
                )

    def _resolve_obsolete_reviews(self, raw_email, booking):
        resolved_types = []
        if booking.activity_id:
            resolved_types.extend(
                [
                    ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
                    ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
                ]
            )
        if booking.active_travel_date:
            resolved_types.append(ReviewQueueItem.IssueType.DATE_MISSING)
        if booking.active_start_time or booking.active_slot_type in {
            "full_day",
            "half_day",
        }:
            resolved_types.append(ReviewQueueItem.IssueType.TIME_MISSING)
        if booking.active_traveler_count is not None:
            resolved_types.append(ReviewQueueItem.IssueType.TRAVELER_COUNT_MISSING)
        if booking.lead_traveler_name:
            resolved_types.append(ReviewQueueItem.IssueType.LEAD_TRAVELER_MISSING)
        if raw_email.provider_detected_id:
            resolved_types.append(ReviewQueueItem.IssueType.PROVIDER_NOT_DETECTED)

        if not resolved_types:
            return 0
        return ReviewQueueItem.objects.filter(
            raw_email=raw_email,
            booking=booking,
            status=ReviewQueueItem.Status.OPEN,
            issue_type__in=resolved_types,
        ).update(
            status=ReviewQueueItem.Status.RESOLVED, resolved_at=raw_email.updated_at
        )

    def _has_open_review(self, raw_email, booking):
        return ReviewQueueItem.objects.filter(
            raw_email=raw_email,
            booking=booking,
            status=ReviewQueueItem.Status.OPEN,
        ).exists()

    def _is_empty(self, value):
        return value in (None, "", [], {})

    def _json_safe(self, values):
        safe = {}
        for key, value in values.items():
            if hasattr(value, "isoformat"):
                safe[key] = value.isoformat()
            elif hasattr(value, "pk"):
                safe[key] = str(value)
            elif isinstance(value, list):
                safe[key] = [str(item) for item in value]
            elif isinstance(value, dict):
                safe[key] = {
                    item_key: str(item_value) for item_key, item_value in value.items()
                }
            else:
                safe[key] = value
        return safe
