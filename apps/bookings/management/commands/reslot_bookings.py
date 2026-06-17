from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime

from apps.bookings.models import Booking, BookingEvent, ReviewQueueItem
from apps.bookings.services import is_manually_overridden, resolve_schedule_slot_details

EXCLUDED_ACTIVE_STATUSES = {
    Booking.Status.CANCELLED,
    Booking.Status.REJECTED,
    Booking.Status.PARSE_FAILED,
    Booking.Status.DUPLICATE_IGNORED,
}


class Command(BaseCommand):
    help = "Re-resolve booking schedule slots from active date/time and activity."

    def add_arguments(self, parser):
        parser.add_argument(
            "--since",
            help="Only scan bookings with active_travel_date on/after this ISO date.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of bookings to scan. Defaults to all.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without updating bookings or writing events.",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress the summary line.",
        )

    def handle(self, *args, **options):
        stats = {
            "scanned": 0,
            "reslotted": 0,
            "unchanged": 0,
            "no_match": 0,
            "skipped_manual": 0,
        }
        quiet = options["quiet"]
        for booking in self._queryset(options):
            stats["scanned"] += 1
            try:
                result = self._reslot_booking(booking, dry_run=options["dry_run"])
                stats[result] += 1
            except Exception as exc:
                stats["no_match"] += 1
                if not quiet:
                    self.stderr.write(
                        f"booking {booking.id} failed during reslot: {exc}"
                    )

        if not quiet:
            self.stdout.write(
                "scanned={scanned} reslotted={reslotted} unchanged={unchanged} "
                "no_match={no_match} skipped_manual={skipped_manual}".format(**stats)
            )

    def _queryset(self, options):
        queryset = (
            Booking.objects.filter(
                activity__isnull=False,
                active_travel_date__isnull=False,
                active_start_time__isnull=False,
            )
            .exclude(status__in=EXCLUDED_ACTIVE_STATUSES)
            .select_related("activity", "schedule_slot", "schedule_slot__schedule")
            .order_by("active_travel_date", "id")
        )
        since = self._parse_since(options.get("since"))
        if since:
            queryset = queryset.filter(active_travel_date__gte=since)
        limit = options.get("limit")
        if limit is not None:
            queryset = queryset[: max(limit, 0)]
        return queryset

    def _parse_since(self, value):
        if not value:
            return None
        parsed_datetime = parse_datetime(value)
        if parsed_datetime is not None:
            return parsed_datetime.date()
        parsed_date = parse_date(value)
        if parsed_date is None:
            raise ValueError("--since must be an ISO date or datetime.")
        return parsed_date

    @transaction.atomic
    def _reslot_booking(self, booking, *, dry_run=False):
        if is_manually_overridden(booking, "schedule_slot"):
            return "skipped_manual"

        resolution = resolve_schedule_slot_details(
            activity=booking.activity,
            travel_date=booking.active_travel_date,
            start_time=booking.active_start_time,
            slot_type=booking.active_slot_type,
            fallback_slot=booking.schedule_slot,
        )
        if resolution.no_match_for_time or resolution.slot is None:
            if not dry_run:
                self._create_slot_confirmation_review(booking)
            return "no_match"

        if resolution.slot.id == booking.schedule_slot_id:
            return "unchanged"

        if dry_run:
            return "reslotted"

        old_slot = booking.schedule_slot
        booking.schedule_slot = resolution.slot
        booking.save(update_fields=["schedule_slot"])
        BookingEvent.objects.create(
            booking=booking,
            event_type=BookingEvent.EventType.EMAIL_UPDATE,
            source=BookingEvent.Source.SYSTEM,
            old_values={
                "schedule_slot": self._slot_value(old_slot),
            },
            new_values={
                "schedule_slot": self._slot_value(resolution.slot),
                "repair": "reslot_bookings",
            },
        )
        return "reslotted"

    def _create_slot_confirmation_review(self, booking):
        ReviewQueueItem.objects.update_or_create(
            booking=booking,
            raw_email=None,
            issue_type=ReviewQueueItem.IssueType.TIME_MISSING,
            status=ReviewQueueItem.Status.OPEN,
            defaults={
                "title": "Schedule slot needs confirmation",
                "details": (
                    f"Active start time {booking.active_start_time:%H:%M} did not "
                    "match an active schedule slot for this activity/date. The "
                    "current schedule slot was kept for now."
                ),
            },
        )

    def _slot_value(self, slot):
        if not slot:
            return None
        return {
            "id": slot.id,
            "activity": slot.schedule.activity.name,
            "start_time": slot.start_time.isoformat(timespec="minutes"),
        }
