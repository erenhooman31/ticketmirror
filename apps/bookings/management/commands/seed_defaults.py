from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed default TicketMirror providers and Bookeo-inspired activities."

    def handle(self, *args, **options):
        call_command("seed_bookeo_products")
