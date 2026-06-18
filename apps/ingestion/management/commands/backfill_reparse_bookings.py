from dataclasses import dataclass, field

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from apps.bookings.models import Booking, BookingEvent
from apps.ingestion.models import RawEmail
from apps.ingestion.services import process_raw_email

DEFAULT_STATUSES = [
    RawEmail.ParseStatus.PARSED,
    RawEmail.ParseStatus.NEEDS_REVIEW,
]

DIFF_FIELDS = [
    "active_traveler_count",
    "schedule_slot_id",
    "activity_id",
]


@dataclass
class BackfillSummary:
    processed: int = 0
    errors: int = 0
    changed_booking_ids: set[int] = field(default_factory=set)

    @property
    def changed_bookings(self) -> int:
        return len(self.changed_booking_ids)


class Command(BaseCommand):
    help = (
        "One-shot backfill that re-runs already parsed/review raw emails through "
        "the current parser. Run after merge_stale_audio_guide_activity and "
        "seed_bookeo_products."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Actually re-process matching rows. Without this, only prints "
                "a dry run."
            ),
        )
        parser.add_argument(
            "--status",
            action="append",
            choices=[choice[0] for choice in RawEmail.ParseStatus.choices],
            help=(
                "RawEmail parse status to backfill. Repeatable. Defaults to "
                "parsed and needs_review."
            ),
        )
        parser.add_argument(
            "--provider",
            action="append",
            help="Filter by detected provider code. Repeatable.",
        )
        parser.add_argument("--date-from", help="Filter received_at date, YYYY-MM-DD.")
        parser.add_argument("--date-to", help="Filter received_at date, YYYY-MM-DD.")
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of RawEmail rows to process per progress batch.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if batch_size <= 0:
            raise CommandError("--batch-size must be greater than 0.")

        queryset = _candidate_queryset(options)
        total = queryset.count()
        limit = options["limit"]
        if limit is not None:
            queryset = queryset[: max(limit, 0)]

        selected_ids = list(queryset.values_list("id", flat=True))
        if not options["apply"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: {len(selected_ids)} of {total} matching raw emails "
                    "would be reparsed. Pass --apply to process them."
                )
            )
            for raw_email in RawEmail.objects.select_related(
                "provider_detected",
            ).filter(id__in=selected_ids[:25]):
                self.stdout.write(_row_summary(raw_email))
            if len(selected_ids) > 25:
                self.stdout.write(f"... {len(selected_ids) - 25} more")
            return

        summary = BackfillSummary()
        total_selected = len(selected_ids)
        for batch_start in range(0, total_selected, batch_size):
            batch_ids = selected_ids[batch_start : batch_start + batch_size]
            for raw_email_id in batch_ids:
                try:
                    changed_booking_id = _reparse_and_detect_changed_booking(
                        raw_email_id,
                    )
                    summary.processed += 1
                    if changed_booking_id:
                        summary.changed_booking_ids.add(changed_booking_id)
                except Exception as exc:
                    summary.errors += 1
                    self.stderr.write(
                        self.style.ERROR(
                            f"RawEmail {raw_email_id} backfill failed: {exc}",
                        )
                    )

            self.stdout.write(
                "Progress: "
                f"{min(batch_start + batch_size, total_selected)}/{total_selected} "
                f"raw emails processed; changed_bookings={summary.changed_bookings}; "
                f"errors={summary.errors}."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Backfill reparse completed: "
                f"processed={summary.processed}; "
                f"errors={summary.errors}; "
                f"changed_bookings={summary.changed_bookings}."
            )
        )


def _candidate_queryset(options):
    statuses = options["status"] or list(DEFAULT_STATUSES)
    queryset = RawEmail.objects.select_related("provider_detected").filter(
        parse_status__in=statuses,
    )
    if options["provider"]:
        queryset = queryset.filter(provider_detected__code__in=options["provider"])
    if options["date_from"]:
        queryset = queryset.filter(
            received_at__date__gte=_parse_date(options["date_from"]),
        )
    if options["date_to"]:
        queryset = queryset.filter(
            received_at__date__lte=_parse_date(options["date_to"]),
        )
    return queryset.order_by("received_at", "id")


def _reparse_and_detect_changed_booking(raw_email_id: int) -> int | None:
    before = _booking_snapshots_for_raw_email(raw_email_id)
    booking = process_raw_email(raw_email_id)
    if not booking:
        return None
    after = _booking_snapshot(booking.id)
    if before.get(booking.id) and _snapshot_changed(before[booking.id], after):
        return booking.id
    return None


def _booking_snapshots_for_raw_email(raw_email_id: int) -> dict[int, dict]:
    booking_ids = (
        BookingEvent.objects.filter(raw_email_id=raw_email_id, booking_id__isnull=False)
        .order_by()
        .values_list("booking_id", flat=True)
        .distinct()
    )
    return {
        booking["id"]: booking
        for booking in Booking.objects.filter(id__in=booking_ids).values(
            "id",
            *DIFF_FIELDS,
        )
    }


def _booking_snapshot(booking_id: int) -> dict:
    return Booking.objects.values("id", *DIFF_FIELDS).get(id=booking_id)


def _snapshot_changed(before: dict, after: dict) -> bool:
    return any(before[field] != after[field] for field in DIFF_FIELDS)


def _parse_date(value: str):
    parsed = parse_date(value)
    if parsed is None:
        raise CommandError(f"Invalid date: {value}. Expected YYYY-MM-DD.")
    return parsed


def _row_summary(raw_email: RawEmail) -> str:
    provider = raw_email.provider_detected.code if raw_email.provider_detected else "-"
    return (
        f"id={raw_email.id} status={raw_email.parse_status} provider={provider} "
        f"received={raw_email.received_at:%Y-%m-%d %H:%M} "
        f"subject={raw_email.subject[:100]}"
    )
