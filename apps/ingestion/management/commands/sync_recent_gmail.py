from django.core.management.base import BaseCommand

from apps.ingestion.tasks import daily_reconciliation_sync


class Command(BaseCommand):
    help = "Queue recent Gmail inbox messages for ingestion."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        result = daily_reconciliation_sync.apply(
            kwargs={"limit": options["limit"]}
        ).get()
        self.stdout.write(self.style.SUCCESS(f"Recent Gmail sync queued: {result}"))
