from django.core.management.base import BaseCommand

from apps.ingestion.polling import sync_recent_gmail


class Command(BaseCommand):
    help = "Queue recent Gmail inbox messages for ingestion."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        result = sync_recent_gmail(limit=options["limit"])
        self.stdout.write(self.style.SUCCESS(f"Recent Gmail sync processed: {result}"))
