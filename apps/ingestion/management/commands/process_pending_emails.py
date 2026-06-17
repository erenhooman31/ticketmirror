from django.core.management.base import BaseCommand

from apps.ingestion.polling import process_pending_raw_emails


class Command(BaseCommand):
    help = "Process pending raw emails already stored in the database."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        processed = process_pending_raw_emails(limit=options["limit"])
        self.stdout.write(
            self.style.SUCCESS(f"Processed {processed} pending raw emails.")
        )
