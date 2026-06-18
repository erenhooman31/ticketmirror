import os
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ingestion.bookeo_import import (
    DEFAULT_FROM_DATE,
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_THROTTLE_SECONDS,
    BookeoApiClient,
    BookeoHistoryImporter,
    JsonCheckpointStore,
    default_to_date,
)


class Command(BaseCommand):
    help = "Import historical bookings from the operator's Bookeo account."

    def add_arguments(self, parser):
        parser.add_argument(
            "--from",
            dest="date_from",
            type=_parse_date,
            default=DEFAULT_FROM_DATE,
            help="First Bookeo event date to import, YYYY-MM-DD.",
        )
        parser.add_argument(
            "--to",
            dest="date_to",
            type=_parse_date,
            default=default_to_date(),
            help="Last Bookeo event date to import, YYYY-MM-DD.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and classify bookings without writing to the database.",
        )
        parser.add_argument(
            "--state-file",
            default=str(settings.BASE_DIR / ".bookeo_history_import_state.json"),
            help="JSON checkpoint file used to resume interrupted imports.",
        )
        parser.add_argument(
            "--items-per-page",
            type=int,
            default=DEFAULT_ITEMS_PER_PAGE,
            help="Bookeo page size. Bookeo caps this at 100.",
        )
        parser.add_argument(
            "--throttle-seconds",
            type=float,
            default=DEFAULT_THROTTLE_SECONDS,
            help="Delay between API requests to avoid Bookeo throttling.",
        )

    def handle(self, *args, **options):
        api_key = _bookeo_api_key()
        secret_key = os.environ.get("BOOKEO_SECRET_KEY", "").strip()
        if not api_key or not secret_key:
            raise CommandError(
                "BBOKEO_AUTHORIZED_API or BOOKEO_API_KEY, plus "
                "BOOKEO_SECRET_KEY, must be set before importing."
            )
        date_from = options["date_from"]
        date_to = options["date_to"]
        if date_from > date_to:
            raise CommandError("--from must be before or equal to --to.")

        client = BookeoApiClient(
            api_key=api_key,
            secret_key=secret_key,
            throttle_seconds=options["throttle_seconds"],
        )
        importer = BookeoHistoryImporter(
            client=client,
            checkpoint_store=JsonCheckpointStore(Path(options["state_file"])),
            dry_run=options["dry_run"],
            items_per_page=options["items_per_page"],
        )
        stats = importer.run(date_from=date_from, date_to=date_to)
        mode = "DRY RUN " if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}Bookeo history import complete: "
                f"windows_processed={stats.windows_processed} "
                f"fetched={stats.fetched} "
                f"created={stats.created} "
                f"updated={stats.updated} "
                f"unmapped_to_review={stats.unmapped_to_review} "
                f"skipped={stats.skipped}."
            )
        )
        if options["dry_run"]:
            self.stdout.write(
                "Dry run did not write bookings, events, reviews, or state."
            )
        else:
            self.stdout.write(f"Checkpoint state: {options['state_file']}")


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CommandError(f"Invalid date {value!r}; expected YYYY-MM-DD.") from exc


def _bookeo_api_key() -> str:
    return (
        os.environ.get("BBOKEO_AUTHORIZED_API", "").strip()
        or os.environ.get("BOOKEO_AUTHORIZED_API", "").strip()
        or os.environ.get("BOOKEO_API_KEY", "").strip()
    )
