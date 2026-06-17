from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.bookings.models import Booking, BookingEvent, ReviewQueueItem
from apps.ingestion.models import RawEmail
from apps.ingestion.services import non_booking_ignore_reason, translated_raw_email_view


class Command(BaseCommand):
    help = "Resolve open parser review items that no longer apply."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of open review items to scan. Defaults to all.",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress the summary line.",
        )

    def handle(self, *args, **options):
        stats = {
            "raw_scanned": 0,
            "raw_ignored": 0,
            "raw_resolved_reviews": 0,
            "cancelled_bookings": 0,
            "scanned": 0,
            "resolved": 0,
            "unchanged": 0,
            "failed": 0,
        }
        for raw_email in self._raw_email_queryset(options):
            stats["raw_scanned"] += 1
            try:
                result = self._reclassify_non_booking_email(raw_email)
                if result["ignored"]:
                    stats["raw_ignored"] += 1
                    stats["raw_resolved_reviews"] += result["resolved_reviews"]
                    stats["cancelled_bookings"] += result["cancelled_bookings"]
            except Exception as exc:
                stats["failed"] += 1
                if not options["quiet"]:
                    self.stderr.write(
                        f"raw_email {raw_email.id} failed during stale sweep: {exc}"
                    )

        for review in self._queryset(options):
            stats["scanned"] += 1
            try:
                if self._resolve_if_stale(review):
                    stats["resolved"] += 1
                else:
                    stats["unchanged"] += 1
            except Exception as exc:
                stats["failed"] += 1
                if not options["quiet"]:
                    self.stderr.write(
                        f"review {review.id} failed during stale sweep: {exc}"
                    )

        if not options["quiet"]:
            self.stdout.write(
                "scanned={scanned} resolved={resolved} unchanged={unchanged} "
                "failed={failed} raw_scanned={raw_scanned} "
                "raw_ignored={raw_ignored} raw_resolved_reviews={raw_resolved_reviews} "
                "cancelled_bookings={cancelled_bookings}".format(**stats)
            )

    def _raw_email_queryset(self, options):
        queryset = RawEmail.objects.select_related("provider_detected").order_by(
            "received_at", "id"
        )
        limit = options.get("limit")
        if limit is not None:
            queryset = queryset[: max(limit, 0)]
        return queryset

    def _queryset(self, options):
        queryset = (
            ReviewQueueItem.objects.filter(status=ReviewQueueItem.Status.OPEN)
            .select_related("raw_email", "raw_email__provider_detected")
            .select_related("booking", "booking__provider", "booking__activity")
            .order_by("created_at", "id")
        )
        limit = options.get("limit")
        if limit is not None:
            queryset = queryset[: max(limit, 0)]
        return queryset

    @transaction.atomic
    def _reclassify_non_booking_email(self, raw_email: RawEmail) -> dict:
        raw_email = RawEmail.objects.select_for_update().get(id=raw_email.id)
        reason = non_booking_ignore_reason(translated_raw_email_view(raw_email))
        if not reason:
            return {"ignored": False, "resolved_reviews": 0, "cancelled_bookings": 0}

        raw_email.parse_status = RawEmail.ParseStatus.IGNORED
        raw_email.parse_error = f"Ignored - not a booking: {reason}."
        raw_email.save(update_fields=["parse_status", "parse_error", "updated_at"])

        resolved_reviews = ReviewQueueItem.objects.filter(
            raw_email=raw_email,
            status=ReviewQueueItem.Status.OPEN,
        ).update(status=ReviewQueueItem.Status.RESOLVED, resolved_at=timezone.now())

        cancelled_bookings = 0
        booking_ids = (
            BookingEvent.objects.filter(raw_email=raw_email, booking__isnull=False)
            .values_list("booking_id", flat=True)
            .distinct()
        )
        for booking in Booking.objects.select_for_update().filter(id__in=booking_ids):
            if not self._safe_to_cancel_non_booking(booking, raw_email):
                continue
            old_status = booking.status
            booking.status = Booking.Status.CANCELLED
            booking.save(update_fields=["status", "updated_at"])
            BookingEvent.objects.create(
                booking=booking,
                raw_email=raw_email,
                event_type=BookingEvent.EventType.CONFLICT_DETECTED,
                source=BookingEvent.Source.SYSTEM,
                old_values={"status": old_status},
                new_values={
                    "status": Booking.Status.CANCELLED,
                    "non_booking_reclassified": True,
                    "reason": reason,
                },
            )
            cancelled_bookings += 1

        return {
            "ignored": True,
            "resolved_reviews": resolved_reviews,
            "cancelled_bookings": cancelled_bookings,
        }

    def _safe_to_cancel_non_booking(
        self,
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

    def _resolve_if_stale(self, review: ReviewQueueItem) -> bool:
        if not self._is_obsolete(review):
            return False
        review.status = ReviewQueueItem.Status.RESOLVED
        review.resolved_at = timezone.now()
        review.save(update_fields=["status", "resolved_at"])
        return True

    def _is_obsolete(self, review: ReviewQueueItem) -> bool:
        booking = review.booking or self._booking_from_raw_email(review.raw_email)
        raw_email = review.raw_email
        issue_type = review.issue_type
        if issue_type == ReviewQueueItem.IssueType.PROVIDER_NOT_DETECTED:
            return bool(raw_email and raw_email.provider_detected_id)
        if issue_type == ReviewQueueItem.IssueType.REFERENCE_MISSING:
            if raw_email and raw_email.parse_status == RawEmail.ParseStatus.IGNORED:
                return True
            return bool(booking and booking.provider_booking_reference)
        if not booking:
            return False
        if issue_type in {
            ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
            ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
        }:
            return bool(booking.activity_id)
        if issue_type == ReviewQueueItem.IssueType.DATE_MISSING:
            return bool(booking.active_travel_date)
        if issue_type == ReviewQueueItem.IssueType.TIME_MISSING:
            if review.title == "Schedule slot needs confirmation":
                return False
            return bool(
                booking.active_start_time
                or booking.active_slot_type
                in {
                    "full_day",
                    "half_day",
                }
            )
        if issue_type == ReviewQueueItem.IssueType.TRAVELER_COUNT_MISSING:
            return booking.active_traveler_count is not None
        if issue_type == ReviewQueueItem.IssueType.LEAD_TRAVELER_MISSING:
            return bool(booking.lead_traveler_name) or _provider_omits_lead_name(
                raw_email,
                booking,
            )
        return False

    def _booking_from_raw_email(self, raw_email: RawEmail | None) -> Booking | None:
        if not raw_email:
            return None
        event = (
            BookingEvent.objects.filter(raw_email=raw_email, booking__isnull=False)
            .select_related("booking", "booking__provider", "booking__activity")
            .order_by("-created_at", "-id")
            .first()
        )
        return event.booking if event else None


def _provider_omits_lead_name(raw_email, booking: Booking) -> bool:
    provider_code = ""
    if raw_email and raw_email.provider_detected_id:
        provider_code = raw_email.provider_detected.code
    if not provider_code and booking.provider_id:
        provider_code = booking.provider.code
    return provider_code == "tripster"
