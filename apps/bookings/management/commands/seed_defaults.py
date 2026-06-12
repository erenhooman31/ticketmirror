from django.core.management.base import BaseCommand
from django.db import transaction

from apps.bookings.models import Product, ProductVariant, Provider

DEFAULT_PROVIDERS = [
    {
        "code": "getyourguide",
        "name": "GetYourGuide",
        "parser_key": "getyourguide",
        "known_sender_patterns": ["getyourguide", "gyg"],
        "known_subject_patterns": ["GetYourGuide", "booking"],
    },
    {
        "code": "viator",
        "name": "Viator",
        "parser_key": "viator",
        "known_sender_patterns": ["viator", "tripadvisor"],
        "known_subject_patterns": ["Viator", "booking"],
    },
    {
        "code": "tiqets",
        "name": "Tiqets",
        "parser_key": "tiqets",
        "known_sender_patterns": ["tiqets"],
        "known_subject_patterns": ["Tiqets", "order"],
    },
    {
        "code": "tripster",
        "name": "Tripster",
        "parser_key": "tripster",
        "known_sender_patterns": ["tripster"],
        "known_subject_patterns": ["Tripster", "booking"],
    },
    {
        "code": "sputnik8",
        "name": "Sputnik8",
        "parser_key": "sputnik8",
        "known_sender_patterns": ["sputnik8"],
        "known_subject_patterns": ["Sputnik8", "booking"],
    },
    {
        "code": "klook",
        "name": "Klook",
        "parser_key": "klook",
        "known_sender_patterns": ["klook"],
        "known_subject_patterns": ["Klook", "booking"],
    },
    {
        "code": "direct",
        "name": "Direct",
        "parser_key": "direct",
        "known_sender_patterns": [],
        "known_subject_patterns": [],
    },
]

SAMPLE_PRODUCTS = [
    {
        "canonical_name": "Full-Day City Highlights Tour",
        "category": "city_tour",
        "variants": [
            {
                "variant_name": "Full day",
                "slot_type": ProductVariant.SlotType.FULL_DAY,
                "duration_minutes": 480,
                "default_capacity": 24,
            }
        ],
    },
    {
        "canonical_name": "Half-Day Old Town Walk",
        "category": "walking_tour",
        "variants": [
            {
                "variant_name": "Morning",
                "slot_type": ProductVariant.SlotType.HALF_DAY,
                "duration_minutes": 240,
                "default_capacity": 20,
            },
            {
                "variant_name": "Afternoon",
                "slot_type": ProductVariant.SlotType.HALF_DAY,
                "duration_minutes": 240,
                "default_capacity": 20,
            },
        ],
    },
    {
        "canonical_name": "Museum Timed Entry",
        "category": "ticket",
        "variants": [
            {
                "variant_name": "Fixed time slot",
                "slot_type": ProductVariant.SlotType.FIXED_TIME,
                "duration_minutes": 90,
                "default_capacity": 30,
            }
        ],
    },
]


class Command(BaseCommand):
    help = "Seed default OTA providers and sample canonical products."

    @transaction.atomic
    def handle(self, *args, **options):
        provider_count = 0
        product_count = 0
        variant_count = 0

        for payload in DEFAULT_PROVIDERS:
            _provider, created = Provider.objects.update_or_create(
                code=payload["code"],
                defaults={
                    "name": payload["name"],
                    "parser_key": payload["parser_key"],
                    "known_sender_patterns": payload["known_sender_patterns"],
                    "known_subject_patterns": payload["known_subject_patterns"],
                    "active": True,
                },
            )
            provider_count += int(created)

        for product_payload in SAMPLE_PRODUCTS:
            product, created = Product.objects.update_or_create(
                canonical_name=product_payload["canonical_name"],
                defaults={
                    "category": product_payload["category"],
                    "active": True,
                },
            )
            product_count += int(created)
            for variant_payload in product_payload["variants"]:
                _variant, variant_created = ProductVariant.objects.update_or_create(
                    product=product,
                    variant_name=variant_payload["variant_name"],
                    defaults={
                        "slot_type": variant_payload["slot_type"],
                        "duration_minutes": variant_payload["duration_minutes"],
                        "default_capacity": variant_payload["default_capacity"],
                        "active": True,
                    },
                )
                variant_count += int(variant_created)

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded defaults: "
                f"{provider_count} providers, "
                f"{product_count} products, "
                f"{variant_count} variants created."
            )
        )
