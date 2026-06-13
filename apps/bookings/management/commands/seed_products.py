from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Deprecated wrapper for seed_bookeo_products."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "seed_products is deprecated; running seed_bookeo_products instead."
            )
        )
        call_command("seed_bookeo_products")
