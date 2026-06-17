from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils.dateparse import parse_date

from apps.ingestion.models import RawEmail
from apps.ingestion.services import process_raw_email

DEFAULT_STATUSES = [
    RawEmail.ParseStatus.FAILED,
    RawEmail.ParseStatus.NEEDS_REVIEW,
    RawEmail.ParseStatus.IGNORED,
    RawEmail.ParseStatus.PENDING,
]


class Command(BaseCommand):
    help = "Replay stored raw emails through the current deterministic parser."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually replay matching rows. Without this, only prints a dry run.",
        )
        parser.add_argument(
            "--status",
            action="append",
            choices=[choice[0] for choice in RawEmail.ParseStatus.choices],
            help=(
                "RawEmail parse status to replay. Repeatable. Defaults to failed, "
                "needs_review, ignored, and pending."
            ),
        )
        parser.add_argument(
            "--include-parsed",
            action="store_true",
            help="Include already parsed rows in the default status set.",
        )
        parser.add_argument(
            "--provider",
            action="append",
            help="Filter by detected provider code. Repeatable.",
        )
        parser.add_argument(
            "--subject-contains",
            action="append",
            help="Filter by subject substring. Repeatable, OR behavior.",
        )
        parser.add_argument(
            "--sender-contains",
            action="append",
            help=(
                "Filter by outer or forwarded sender substring. Repeatable, "
                "OR behavior."
            ),
        )
        parser.add_argument(
            "--id",
            action="append",
            type=int,
            help="Replay a specific RawEmail id. Repeatable.",
        )
        parser.add_argument("--date-from", help="Filter received_at date, YYYY-MM-DD.")
        parser.add_argument("--date-to", help="Filter received_at date, YYYY-MM-DD.")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        queryset = _candidate_queryset(options)
        total = queryset.count()

        if options["limit"]:
            queryset = queryset[: max(options["limit"], 0)]

        selected = list(queryset)
        if not options["apply"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: {len(selected)} of {total} matching raw emails "
                    "would be replayed. Pass --apply to process them."
                )
            )
            for raw_email in selected[:25]:
                self.stdout.write(_row_summary(raw_email))
            if len(selected) > 25:
                self.stdout.write(f"... {len(selected) - 25} more")
            return

        processed = 0
        errors = 0
        for raw_email in selected:
            try:
                process_raw_email(raw_email.id)
                processed += 1
            except Exception as exc:
                errors += 1
                self.stderr.write(
                    self.style.ERROR(f"RawEmail {raw_email.id} replay failed: {exc}")
                )

        status_counts = _status_counts(selected)
        self.stdout.write(
            self.style.SUCCESS(
                f"Replayed {processed} raw emails; errors={errors}; "
                f"final_statuses={status_counts}."
            )
        )


def _candidate_queryset(options):
    statuses = options["status"] or list(DEFAULT_STATUSES)
    if options["include_parsed"] and RawEmail.ParseStatus.PARSED not in statuses:
        statuses.append(RawEmail.ParseStatus.PARSED)

    queryset = RawEmail.objects.select_related("provider_detected").filter(
        parse_status__in=statuses
    )

    if options["id"]:
        queryset = queryset.filter(id__in=options["id"])
    if options["provider"]:
        queryset = queryset.filter(provider_detected__code__in=options["provider"])
    if options["subject_contains"]:
        queryset = queryset.filter(_contains_q("subject", options["subject_contains"]))
    if options["sender_contains"]:
        sender_q = Q()
        for value in options["sender_contains"]:
            sender_q |= Q(gmail_outer_sender__icontains=value)
            sender_q |= Q(original_forwarded_sender__icontains=value)
        queryset = queryset.filter(sender_q)
    if options["date_from"]:
        queryset = queryset.filter(
            received_at__date__gte=_parse_date(options["date_from"])
        )
    if options["date_to"]:
        queryset = queryset.filter(
            received_at__date__lte=_parse_date(options["date_to"])
        )

    return queryset.order_by("received_at", "id")


def _contains_q(field_name: str, values: list[str]) -> Q:
    query = Q()
    for value in values:
        query |= Q(**{f"{field_name}__icontains": value})
    return query


def _parse_date(value: str):
    parsed = parse_date(value)
    if parsed is None:
        raise CommandError(f"Invalid date: {value}. Expected YYYY-MM-DD.")
    return parsed


def _status_counts(raw_emails: list[RawEmail]) -> dict[str, int]:
    ids = [raw_email.id for raw_email in raw_emails]
    counts = {}
    for status in RawEmail.objects.filter(id__in=ids).values_list(
        "parse_status",
        flat=True,
    ):
        counts[status] = counts.get(status, 0) + 1
    return counts


def _row_summary(raw_email: RawEmail) -> str:
    provider = raw_email.provider_detected.code if raw_email.provider_detected else "-"
    return (
        f"id={raw_email.id} status={raw_email.parse_status} provider={provider} "
        f"received={raw_email.received_at:%Y-%m-%d %H:%M} "
        f"subject={raw_email.subject[:100]}"
    )
