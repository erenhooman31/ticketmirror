from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.bookings.models import Provider, ProviderAlias, TourActivity


@dataclass(frozen=True)
class ActivitySeed:
    name: str
    category: str
    notes: str


@dataclass(frozen=True)
class AliasSeed:
    provider_code: str
    raw_product_name: str
    activity_name: str
    notes: str


PROVIDER_SEEDS = [
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
]


ACTIVITY_SEEDS = [
    ActivitySeed(
        name="Bosphorus Cruise",
        category=TourActivity.Category.CRUISE,
        notes=(
            "Canonical activity from Bookeo product-inspection evidence for "
            "1-hour and 2-hour Bosphorus cruise variants."
        ),
    ),
    ActivitySeed(
        name="Istanbul Old City and Bosphorus Tour",
        category=TourActivity.Category.LAND_AND_CRUISE,
        notes=(
            "Canonical activity from Bookeo product-inspection evidence for "
            "Old City and Bosphorus Viator/GYG variants."
        ),
    ),
    ActivitySeed(
        name="Istanbul Two Continents Tour",
        category=TourActivity.Category.LAND_AND_CRUISE,
        notes=(
            "Canonical activity from Bookeo product-inspection evidence for "
            "Two Continents bus and Bosphorus cruise Viator/GYG variants."
        ),
    ),
    ActivitySeed(
        name="Yacht Experience",
        category=TourActivity.Category.YACHT,
        notes=(
            "Canonical activity from Bookeo product-inspection evidence for "
            "gyg yacht."
        ),
    ),
]


ALIAS_SEEDS = [
    AliasSeed(
        provider_code="viator",
        raw_product_name="Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR",
        activity_name="Bosphorus Cruise",
        notes="2-hour Viator Bosphorus cruise alias from Bookeo inspection.",
    ),
    AliasSeed(
        provider_code="viator",
        raw_product_name="2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR",
        activity_name="Bosphorus Cruise",
        notes="2-hour Viator Bosphorus cruise V2 alias from Bookeo inspection.",
    ),
    AliasSeed(
        provider_code="viator",
        raw_product_name=(
            "2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER"
        ),
        activity_name="Bosphorus Cruise",
        notes="2-hour Viator Bosphorus cruise transfer alias from Bookeo inspection.",
    ),
    AliasSeed(
        provider_code="getyourguide",
        raw_product_name="2 Hours Bosphorus Tour SL-1",
        activity_name="Bosphorus Cruise",
        notes="2-hour GYG SL-1 Bosphorus cruise alias from Bookeo inspection.",
    ),
    AliasSeed(
        provider_code="getyourguide",
        raw_product_name="GYG 2 Hours Bosphorus Tour SL-(2-3)",
        activity_name="Bosphorus Cruise",
        notes="2-hour GYG SL-(2-3) Bosphorus cruise alias from Bookeo inspection.",
    ),
    AliasSeed(
        provider_code="viator",
        raw_product_name="1 Hours Bosphorus Tour viator",
        activity_name="Bosphorus Cruise",
        notes="1-hour Viator Bosphorus cruise alias from Bookeo inspection.",
    ),
    AliasSeed(
        provider_code="getyourguide",
        raw_product_name="1 Hours Bosphorus Tour GYG",
        activity_name="Bosphorus Cruise",
        notes="1-hour GYG Bosphorus cruise alias from Bookeo inspection.",
    ),
    AliasSeed(
        provider_code="viator",
        raw_product_name="Istanbul Old City And Bosphorus Tour",
        activity_name="Istanbul Old City and Bosphorus Tour",
        notes="Viator Old City and Bosphorus tour alias from Bookeo inspection.",
    ),
    AliasSeed(
        provider_code="getyourguide",
        raw_product_name="Istanbul Old City And Bosphorus Tour - GYG",
        activity_name="Istanbul Old City and Bosphorus Tour",
        notes="GYG Old City and Bosphorus tour alias from Bookeo inspection.",
    ),
    AliasSeed(
        provider_code="viator",
        raw_product_name="Istanbul Two Continents Tour By Bus And Bosphorus Cruise",
        activity_name="Istanbul Two Continents Tour",
        notes="Viator Two Continents tour alias from Bookeo inspection.",
    ),
    AliasSeed(
        provider_code="getyourguide",
        raw_product_name=(
            "Istanbul Two Continents Tour By Bus And Bosphorus Cruise - GYG"
        ),
        activity_name="Istanbul Two Continents Tour",
        notes="GYG Two Continents tour alias from Bookeo inspection.",
    ),
    AliasSeed(
        provider_code="getyourguide",
        raw_product_name="gyg yacht",
        activity_name="Yacht Experience",
        notes=(
            "GYG yacht alias from Bookeo inspection; schedule model needs "
            "confirmation."
        ),
    ),
]


class Command(BaseCommand):
    help = (
        "Safely seed canonical Bookeo/local activities and provider aliases without "
        "overwriting operator setup."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        providers, provider_stats = seed_providers()
        activities, activity_stats = seed_activities()
        alias_stats = seed_aliases(providers=providers, activities=activities)

        total_created = (
            provider_stats["created"]
            + activity_stats["created"]
            + alias_stats["created"]
        )
        total_updated = (
            provider_stats["updated"]
            + activity_stats["updated"]
            + alias_stats["updated"]
        )
        total_skipped = (
            provider_stats["skipped"]
            + activity_stats["skipped"]
            + alias_stats["skipped"]
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded Bookeo activities: "
                f"created={total_created}, updated={total_updated}, "
                f"skipped={total_skipped}; "
                f"providers created={provider_stats['created']} "
                f"updated={provider_stats['updated']} "
                f"skipped={provider_stats['skipped']}; "
                f"activities created={activity_stats['created']} "
                f"updated={activity_stats['updated']} "
                f"skipped={activity_stats['skipped']}; "
                f"aliases created={alias_stats['created']} "
                f"updated={alias_stats['updated']} "
                f"skipped={alias_stats['skipped']}."
            )
        )


def seed_providers():
    providers = {}
    stats = _stats()
    for payload in PROVIDER_SEEDS:
        provider, created = Provider.objects.get_or_create(
            code=payload["code"],
            defaults={
                "name": payload["name"],
                "active": True,
                "parser_key": payload["parser_key"],
                "known_sender_patterns": payload["known_sender_patterns"],
                "known_subject_patterns": payload["known_subject_patterns"],
            },
        )
        if created:
            stats["created"] += 1
        else:
            changed = _fill_blank_provider_fields(provider, payload)
            stats["updated" if changed else "skipped"] += 1
        providers[provider.code] = provider
    return providers, stats


def seed_activities():
    activities = {}
    stats = _stats()
    for seed in ACTIVITY_SEEDS:
        activity, created = TourActivity.objects.get_or_create(
            name=seed.name,
            defaults={
                "internal_display_name": seed.name,
                "active": True,
                "category": seed.category,
                "display_settings": {
                    "visible_internally": True,
                    "show_in_calendar": True,
                    "show_in_reports": True,
                    "show_home_agenda": True,
                },
                "notes": seed.notes,
            },
        )
        if created:
            stats["created"] += 1
        else:
            changed = _fill_blank_activity_fields(activity, seed)
            stats["updated" if changed else "skipped"] += 1
        activities[activity.name] = activity
    return activities, stats


def seed_aliases(*, providers, activities):
    stats = _stats()
    for seed in ALIAS_SEEDS:
        provider = providers[seed.provider_code]
        activity = activities[seed.activity_name]
        alias, created = ProviderAlias.objects.get_or_create(
            provider=provider,
            raw_product_name=seed.raw_product_name,
            raw_option_name="",
            provider_product_code="",
            provider_option_code="",
            defaults={
                "linked_activity": activity,
                "linked_schedule": None,
                "linked_slot": None,
                "approved": True,
                "needs_manual_confirmation": True,
                "notes": seed.notes,
            },
        )
        if created:
            stats["created"] += 1
            continue

        changed = False
        if not alias.notes:
            alias.notes = seed.notes
            changed = True
        if changed:
            alias.save(update_fields=["notes", "updated_at"])
        stats["updated" if changed else "skipped"] += 1
    return stats


def _fill_blank_provider_fields(provider, payload):
    update_fields = []
    for field in [
        "parser_key",
        "known_sender_patterns",
        "known_subject_patterns",
    ]:
        value = getattr(provider, field)
        if value in ("", [], {}, None):
            setattr(provider, field, payload[field])
            update_fields.append(field)
    if update_fields:
        provider.save(update_fields=[*update_fields, "updated_at"])
        return True
    return False


def _fill_blank_activity_fields(activity, seed):
    update_fields = []
    if not activity.internal_display_name:
        activity.internal_display_name = seed.name
        update_fields.append("internal_display_name")
    if not activity.category:
        activity.category = seed.category
        update_fields.append("category")
    if activity.display_settings == {}:
        activity.display_settings = {
            "visible_internally": True,
            "show_in_calendar": True,
            "show_in_reports": True,
            "show_home_agenda": True,
        }
        update_fields.append("display_settings")
    if not activity.notes:
        activity.notes = seed.notes
        update_fields.append("notes")
    if update_fields:
        activity.save(update_fields=[*update_fields, "updated_at"])
        return True
    return False


def _stats():
    return {"created": 0, "updated": 0, "skipped": 0}
