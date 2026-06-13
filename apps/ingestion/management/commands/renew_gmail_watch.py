from django.core.management.base import BaseCommand

from apps.ingestion.tasks import renew_gmail_watch


class Command(BaseCommand):
    help = "Renew the Gmail Pub/Sub watch."

    def handle(self, *args, **options):
        result = renew_gmail_watch.apply().get()
        self.stdout.write(self.style.SUCCESS(f"Gmail watch renewed: {result}"))
