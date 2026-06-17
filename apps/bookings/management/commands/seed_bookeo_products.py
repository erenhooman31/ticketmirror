from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.bookings.models import (
    ActivityPeopleRule,
    ActivitySchedule,
    ActivityScheduleSlot,
    Provider,
    ProviderAlias,
    TourActivity,
)

PROVIDERS = [
    {
        "code": "bookeo",
        "name": "Bookeo",
        "parser_key": "bookeo",
        "known_sender_patterns": ["bookeo", "noreply@bookeo.com"],
        "known_subject_patterns": ["New booking", "Booking changed"],
    },
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
        "code": "klook",
        "name": "Klook",
        "parser_key": "klook",
        "known_sender_patterns": ["klook"],
        "known_subject_patterns": ["Klook", "booking"],
    },
    {
        "code": "tiqets",
        "name": "Tiqets",
        "parser_key": "tiqets",
        "known_sender_patterns": ["tiqets"],
        "known_subject_patterns": ["Tiqets", "booking"],
    },
    {
        "code": "tripster",
        "name": "Tripster",
        "parser_key": "tripster",
        "known_sender_patterns": ["tripster", "experience.tripster"],
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
        "code": "alle",
        "name": "Alle",
        "parser_key": "alle",
        "known_sender_patterns": ["alle", "alletravel"],
        "known_subject_patterns": ["Alle", "booking"],
    },
    {
        "code": "travel-experience",
        "name": "Travel Experience",
        "parser_key": "travel-experience",
        "known_sender_patterns": ["travel-experience", "travelexperience"],
        "known_subject_patterns": ["Travel Experience", "booking"],
    },
    {
        "code": "direct",
        "name": "Direct/internal",
        "parser_key": "direct",
        "known_sender_patterns": ["@example.com", "@internal.local"],
        "known_subject_patterns": ["Direct booking", "internal booking"],
    },
]


BOOKEO_PRODUCTS = [
    {
        "name": "Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR",
        "display_name": "VIATOR 2H",
        "category": TourActivity.Category.CRUISE,
        "provider": "viator",
        "duration": 120,
        "slot_type": ActivityScheduleSlot.SlotType.FIXED_TIME,
        "capacity": 250,
        "times": ["11:00", "14:00", "19:00"],
        "current_from": "2026-04-04",
        "current_to": "2026-07-31",
        "other_schedules": [
            ("2027-04-01", None, "SUMMER season 2027"),
            ("2026-10-01", "2027-03-31", "WINTER season"),
            ("2026-08-01", "2026-09-30", "AUTMUN season"),
            ("2026-04-01", "2026-04-03", "summer season"),
            ("2025-10-01", "2026-03-31", "WINTER season"),
            ("2024-05-19", "2025-09-30", "Default season"),
        ],
        "manual": True,
        "notes": "2-hour Viator alias. Confirm future-season times.",
    },
    {
        "name": "2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR",
        "display_name": "NEW VIATOR 2H V2",
        "category": TourActivity.Category.CRUISE,
        "provider": "viator",
        "duration": 120,
        "slot_type": ActivityScheduleSlot.SlotType.FIXED_TIME,
        "capacity": 250,
        "times": ["11:00", "14:00", "19:00"],
        "current_from": "2026-04-01",
        "current_to": "2026-07-31",
        "other_schedules": [
            ("2027-04-01", None, "autumon season"),
            ("2026-10-01", "2027-03-31", "WINTER season"),
            ("2026-08-01", "2026-09-30", "autumon season"),
            ("2025-10-01", "2026-03-31", "winter season"),
            ("2024-05-19", "2025-09-30", "Default season"),
        ],
        "manual": True,
        "notes": "2-hour Viator alias V2. Confirm alias relationship.",
    },
    {
        "name": "2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER",
        "display_name": "NEW VIATOR 2H TRANSFER",
        "category": TourActivity.Category.CRUISE,
        "provider": "viator",
        "duration": 120,
        "slot_type": ActivityScheduleSlot.SlotType.FIXED_TIME,
        "capacity": 250,
        "times": ["11:00", "14:00", "19:00"],
        "current_from": "2026-04-01",
        "current_to": None,
        "other_schedules": [
            ("2025-10-01", "2026-03-31", "WINTER season"),
            ("2024-05-19", "2025-09-30", "Default season"),
        ],
        "manual": True,
        "notes": "Transfer variant. Confirm pickup timing and shared capacity.",
    },
    {
        "name": "2 Hours Bosphorus Tour SL-1",
        "display_name": "GYG - 2 SAAT (SL-1)",
        "category": TourActivity.Category.CRUISE,
        "provider": "getyourguide",
        "duration": 120,
        "slot_type": ActivityScheduleSlot.SlotType.FIXED_TIME,
        "capacity": 250,
        "times": ["11:00"],
        "current_from": "2025-10-01",
        "current_to": None,
        "other_schedules": [
            ("2024-05-19", "2025-09-30", "Default season"),
        ],
        "manual": True,
        "notes": "GYG SL-1 split. Confirm meaning of SL-1.",
    },
    {
        "name": "GYG 2 Hours Bosphorus Tour SL-(2-3)",
        "display_name": "GYG - 2 SAAT SL-(2-3)",
        "category": TourActivity.Category.CRUISE,
        "provider": "getyourguide",
        "duration": 120,
        "slot_type": ActivityScheduleSlot.SlotType.FIXED_TIME,
        "capacity": 250,
        "times": ["14:00", "19:00"],
        "current_from": "2026-04-01",
        "current_to": "2026-07-31",
        "other_schedules": [
            ("2026-10-01", None, "winter season2"),
            ("2026-08-01", "2026-09-30", "autumn season"),
            ("2026-02-04", "2026-03-31", "winter season"),
            ("2025-10-01", "2026-02-03", "winter season"),
            ("2024-05-19", "2025-09-30", "Default season"),
        ],
        "manual": True,
        "notes": "GYG SL-(2-3) split from SL-1.",
    },
    {
        "name": "Istanbul Old City And Bosphorus Tour",
        "display_name": "OLD CITY VIATOR",
        "show_home_agenda": True,
        "category": TourActivity.Category.LAND_AND_CRUISE,
        "provider": "viator",
        "duration": 240,
        "slot_type": ActivityScheduleSlot.SlotType.HALF_DAY,
        "capacity": 50,
        "times": ["08:30"],
        "current_from": "2025-08-01",
        "current_to": None,
        "other_schedules": [
            ("2024-05-19", "2025-07-31", "Default season"),
        ],
        "manual": True,
        "notes": "Half-day Viator alias. Confirm duration and shared inventory.",
    },
    {
        "name": "Istanbul Two Continents Tour By Bus And Bosphorus Cruise",
        "display_name": "VIATOR-TWO CONTINENTS",
        "category": TourActivity.Category.LAND_AND_CRUISE,
        "provider": "viator",
        "duration": 480,
        "slot_type": ActivityScheduleSlot.SlotType.FULL_DAY,
        "capacity": 50,
        "times": ["08:15"],
        "current_from": "2026-05-31",
        "current_to": None,
        "other_schedules": [
            ("2024-05-19", "2026-05-30", "Default season"),
        ],
        "manual": True,
        "notes": "Full-day Viator alias. Confirm duration.",
    },
    {
        "name": "Istanbul Old City And Bosphorus Tour - GYG",
        "display_name": "OLD CITY GYG",
        "show_home_agenda": True,
        "category": TourActivity.Category.LAND_AND_CRUISE,
        "provider": "getyourguide",
        "duration": 240,
        "slot_type": ActivityScheduleSlot.SlotType.HALF_DAY,
        "capacity": 50,
        "times": ["08:15"],
        "current_from": "2025-08-01",
        "current_to": None,
        "other_schedules": [
            ("2024-05-19", "2025-07-31", "Default season"),
        ],
        "manual": True,
        "notes": "Half-day GYG alias. Confirm why time differs from Viator alias.",
    },
    {
        "name": "Istanbul Two Continents Tour By Bus And Bosphorus Cruise - GYG",
        "display_name": "GYG - TWO CONTINENTS",
        "category": TourActivity.Category.LAND_AND_CRUISE,
        "provider": "getyourguide",
        "duration": 480,
        "slot_type": ActivityScheduleSlot.SlotType.FULL_DAY,
        "capacity": 50,
        "times": ["08:15"],
        "current_from": None,
        "current_to": None,
        "other_schedules": [],
        "manual": True,
        "notes": "Full-day GYG alias. Confirm shared inventory with Viator alias.",
    },
    {
        "name": "1 Hours Bosphorus Tour viator",
        "display_name": "VIATOR 1 SAAT",
        "category": TourActivity.Category.CRUISE,
        "provider": "viator",
        "duration": 60,
        "slot_type": ActivityScheduleSlot.SlotType.FIXED_TIME,
        "capacity": 250,
        "times": ["17:00"],
        "current_from": None,
        "current_to": None,
        "other_schedules": [],
        "manual": True,
        "notes": "1-hour Viator alias. Confirm shared capacity.",
    },
    {
        "name": "1 Hours Bosphorus Tour GYG",
        "display_name": "GYG - 1 Hours",
        "category": TourActivity.Category.CRUISE,
        "provider": "getyourguide",
        "duration": 60,
        "slot_type": ActivityScheduleSlot.SlotType.FIXED_TIME,
        "capacity": 250,
        "times": ["17:00"],
        "current_from": "2026-02-17",
        "current_to": None,
        "other_schedules": [],
        "manual": True,
        "notes": "1-hour GYG alias. Confirm shared capacity.",
    },
    {
        "name": "gyg yacht",
        "category": TourActivity.Category.YACHT,
        "provider": "getyourguide",
        "duration": 60,
        "slot_type": ActivityScheduleSlot.SlotType.PRIVATE_GROUP,
        "capacity": None,
        "times": [],
        "duration_only": True,
        "current_from": None,
        "current_to": None,
        "other_schedules": [],
        "manual": True,
        "notes": (
            "Yacht special case. Confirm capacity, duration, and scheduling model."
        ),
    },
]


LIVE_BOOKEO_PRODUCT_NAMES = tuple(payload["name"] for payload in BOOKEO_PRODUCTS)


DIRECT_OTA_ALIASES = [
    {
        "provider": "viator",
        "raw_product_name": "Guided Bosphorus Cruise Boat Tour In Istanbul",
        "activity_name": "2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR",
        "slot_start_time": "11:00",
        "notes": (
            "Confirmed from tests/fixtures/emails/real_viator_new.txt. "
            "Parser may provide a provider time that picks a different slot."
        ),
    },
    {
        "provider": "viator",
        "raw_product_name": "Istanbul Private Luxury Yacht on Bosphorus",
        "activity_name": "gyg yacht",
        "slot_start_time": None,
        "notes": "Confirmed from tests/fixtures/emails/real_viator_request.txt.",
    },
    {
        "provider": "getyourguide",
        "raw_product_name": "Istanbul: Luxury Yacht on Bosphorus",
        "activity_name": "gyg yacht",
        "slot_start_time": None,
        "notes": "Confirmed from tests/fixtures/emails/real_getyourguide_new.txt.",
    },
    {
        "provider": "getyourguide",
        "raw_product_name": (
            "Istanbul: Bosphorus Sightseeing Cruise Tour with Audio Guide"
        ),
        "activity_name": "GYG 2 Hours Bosphorus Tour SL-(2-3)",
        "slot_start_time": "19:00",
        "notes": "Confirmed from real GetYourGuide cancellation sample.",
    },
    {
        "provider": "klook",
        "raw_product_name": (
            "Istanbul: Bosphorus Sightseeing Cruise Tour with Audio Guide"
        ),
        "activity_name": "GYG 2 Hours Bosphorus Tour SL-(2-3)",
        "slot_start_time": "19:00",
        "notes": "Confirmed from real Klook confirmation/cancellation samples.",
    },
    {
        "provider": "tiqets",
        "raw_product_name": (
            "Istanbul: Guided Bosphorus Sightseeing Cruise + Audio Guide"
        ),
        "activity_name": "GYG 2 Hours Bosphorus Tour SL-(2-3)",
        "slot_start_time": "19:00",
        "notes": "Confirmed from tests/fixtures/emails/real_tiqets_new.txt.",
    },
    {
        "provider": "tripster",
        "raw_product_name": "Великолепный Стамбул в Европе и Азии",
        "activity_name": "Istanbul Two Continents Tour By Bus And Bosphorus Cruise",
        "slot_start_time": "08:15",
        "notes": "Confirmed from tests/fixtures/emails/real_tripster_new_ru.txt.",
    },
    {
        "provider": "tripster",
        "raw_product_name": "Морская прогулка по Босфору с аудиогидом",
        "activity_name": "GYG 2 Hours Bosphorus Tour SL-(2-3)",
        "slot_start_time": "19:00",
        "notes": (
            "Audio-guide Bosphorus Russian title; provisional pending "
            "Tripster body capture."
        ),
    },
    {
        "provider": "sputnik8",
        "raw_product_name": "Морская прогулка по Босфору с аудиогидом",
        "activity_name": "GYG 2 Hours Bosphorus Tour SL-(2-3)",
        "slot_start_time": "19:00",
        "notes": "Confirmed from tests/fixtures/emails/real_sputnik8_new_ru.txt.",
    },
    {
        "provider": "sputnik8",
        "raw_product_name": "Великолепный Стамбул в Европе и Азии",
        "activity_name": "Istanbul Two Continents Tour By Bus And Bosphorus Cruise",
        "slot_start_time": "08:15",
        "notes": (
            "Russian Old City/continents title; provisional pending "
            "Sputnik8 body capture."
        ),
    },
    {
        "provider": "tripster",
        "raw_product_name": "Bosphorus boat trip with audio guide",
        "activity_name": "GYG 2 Hours Bosphorus Tour SL-(2-3)",
        "slot_start_time": "19:00",
        "notes": "Confirmed from real Tripster English forwarded subject.",
    },
    {
        "provider": "tripster",
        "raw_product_name": "Bosphorus Boat Cruise with Audio Guide",
        "activity_name": "GYG 2 Hours Bosphorus Tour SL-(2-3)",
        "slot_start_time": "19:00",
        "notes": "Confirmed from real Tripster English order body.",
    },
    {
        "provider": "sputnik8",
        "raw_product_name": "Bosphorus Boat Cruise with Audio Guide",
        "activity_name": "GYG 2 Hours Bosphorus Tour SL-(2-3)",
        "slot_start_time": "19:00",
        "notes": "Confirmed from real Sputnik8 reservation body.",
    },
    {
        "provider": "sputnik8",
        "raw_product_name": "Bosphorus boat trip with an audio guide",
        "activity_name": "GYG 2 Hours Bosphorus Tour SL-(2-3)",
        "slot_start_time": "19:00",
        "notes": "Confirmed from real Sputnik8 forwarded subject.",
    },
]

UNMAPPED_SAMPLE_PRODUCT_STRINGS = [
    {
        "provider": "klook",
        "raw_product_name": "Airport Transfer",
        "reason": (
            "Sample email is missing a booking reference and is not a Bookeo tour."
        ),
    },
]


class Command(BaseCommand):
    help = "Seed the 12 inspected Bookeo products as TicketMirror activities."

    @transaction.atomic
    def handle(self, *args, **options):
        providers, provider_stats = seed_providers()
        stats = {
            "activities": _stats(),
            "schedules": _stats(),
            "slots": _stats(),
            "people_rules": _stats(),
            "aliases": _stats(),
        }
        activities = {}

        for payload in BOOKEO_PRODUCTS:
            activity, status = _update_or_create_tracked(
                TourActivity,
                lookup={"name": payload["name"]},
                defaults={
                    "internal_display_name": payload.get(
                        "display_name",
                        payload["name"],
                    ),
                    "active": True,
                    "category": payload["category"],
                    "display_settings": {
                        "visible_internally": True,
                        "show_in_calendar": True,
                        "show_in_reports": True,
                        "show_home_agenda": payload.get("show_home_agenda", True),
                    },
                    "notes": payload["notes"],
                },
            )
            activities[activity.name] = activity
            _count(stats["activities"], status)
            _count(stats["people_rules"], seed_people_rule(activity, payload))
            current_schedule, schedule_status = seed_schedule(
                activity,
                ActivitySchedule.ScheduleKind.CURRENT,
                "Current schedule",
                active=True,
                priority=100,
                date_from=payload["current_from"],
                date_to=payload["current_to"],
            )
            _count(stats["schedules"], schedule_status)
            _merge_stats(stats["schedules"], seed_other_schedules(activity, payload))
            _merge_stats(stats["slots"], seed_slots(current_schedule, payload))
            provider = providers[payload["provider"]]
            linked_slot = (
                current_schedule.slots.filter(active=True)
                .order_by("start_time")
                .first()
            )
            _count(
                stats["aliases"],
                seed_alias(
                    provider=provider,
                    activity=activity,
                    slot=linked_slot,
                    raw_product_name=payload["name"],
                    manual=payload["manual"],
                    notes=payload["notes"],
                ),
            )
            _count(
                stats["aliases"],
                seed_alias(
                    provider=providers["bookeo"],
                    activity=activity,
                    slot=linked_slot,
                    raw_product_name=payload["name"],
                    manual=payload["manual"],
                    notes=f"Bookeo Tour field for {payload['name']}.",
                ),
            )

        _merge_stats(
            stats["aliases"],
            seed_direct_ota_aliases(providers=providers, activities=activities),
        )
        assert_catalog_drift()
        alias_coverage = build_alias_coverage()

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded Bookeo catalog: "
                f"providers created={provider_stats['created']} "
                f"updated={provider_stats['updated']} "
                f"skipped={provider_stats['skipped']}; "
                f"activities created={stats['activities']['created']} "
                f"updated={stats['activities']['updated']} "
                f"skipped={stats['activities']['skipped']}; "
                f"schedules created={stats['schedules']['created']} "
                f"updated={stats['schedules']['updated']} "
                f"skipped={stats['schedules']['skipped']}; "
                f"slots created={stats['slots']['created']} "
                f"updated={stats['slots']['updated']} "
                f"skipped={stats['slots']['skipped']}; "
                f"people rules created={stats['people_rules']['created']} "
                f"updated={stats['people_rules']['updated']} "
                f"skipped={stats['people_rules']['skipped']}; "
                f"aliases created={stats['aliases']['created']} "
                f"updated={stats['aliases']['updated']} "
                f"skipped={stats['aliases']['skipped']}."
            )
        )
        self.stdout.write(
            "Alias coverage: "
            f"{len(alias_coverage['mapped'])} incoming product strings map; "
            f"{len(alias_coverage['unmapped'])} sample strings remain unmapped."
        )
        if alias_coverage["unmapped"]:
            self.stdout.write("Unmapped incoming sample strings:")
            for item in alias_coverage["unmapped"]:
                self.stdout.write(
                    f"- {item['provider']}: {item['raw_product_name']} "
                    f"({item['reason']})"
                )
        if alias_coverage["manual_products"]:
            self.stdout.write("Products still lacking confirmed direct-OTA strings:")
            for product_name in alias_coverage["manual_products"]:
                self.stdout.write(f"- {product_name}")


def seed_providers():
    providers = {}
    stats = _stats()
    for payload in PROVIDERS:
        provider, status = _update_or_create_tracked(
            Provider,
            lookup={"code": payload["code"]},
            defaults={
                "name": payload["name"],
                "active": True,
                "parser_key": payload["parser_key"],
                "known_sender_patterns": payload["known_sender_patterns"],
                "known_subject_patterns": payload["known_subject_patterns"],
            },
        )
        _count(stats, status)
        providers[provider.code] = provider
    return providers, stats


def seed_people_rule(activity, payload):
    _rule, status = _update_or_create_tracked(
        ActivityPeopleRule,
        lookup={"activity": activity},
        defaults={
            "min_people_per_booking": 1,
            "max_people_per_booking": 20 if payload["capacity"] else None,
            "default_capacity": payload["capacity"],
            "capacity_note": payload["notes"],
        },
    )
    return status


def seed_schedule(activity, schedule_kind, name, active, priority, date_from, date_to):
    return _update_or_create_tracked(
        ActivitySchedule,
        lookup={
            "activity": activity,
            "schedule_kind": schedule_kind,
            "priority": priority,
        },
        defaults={
            "name": name,
            "active": active,
            "date_from": _parse_date(date_from),
            "date_to": _parse_date(date_to),
            "days_of_week": [],
            "recurrence_mode": ActivitySchedule.RecurrenceMode.WEEKLY,
            "notes": "Seeded from exact Bookeo product schedule inspection.",
        },
    )


def seed_other_schedules(activity, payload):
    kept_ids = []
    stats = _stats()
    for priority, (date_from, date_to, name) in enumerate(
        payload["other_schedules"], start=200
    ):
        schedule, status = seed_schedule(
            activity,
            ActivitySchedule.ScheduleKind.OTHER,
            name,
            active=False,
            priority=priority,
            date_from=date_from,
            date_to=date_to,
        )
        schedule.slots.all().delete()
        kept_ids.append(schedule.id)
        _count(stats, status)

    stale = ActivitySchedule.objects.filter(
        activity=activity,
        schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
    )
    if kept_ids:
        stale = stale.exclude(id__in=kept_ids)
    stale.delete()
    return stats


def seed_slots(schedule, payload):
    stats = _stats()
    if payload.get("duration_only") and payload["duration"]:
        _slot, status = _update_or_create_tracked(
            ActivityScheduleSlot,
            lookup={
                "schedule": schedule,
                "start_time": _parse_time("00:00"),
            },
            defaults={
                "end_time": _end_time(_parse_time("00:00"), payload["duration"]),
                "duration_minutes": payload["duration"],
                "slot_type": payload["slot_type"],
                "capacity": 0,
                "days_of_week": [],
                "active": False,
            },
        )
        _count(stats, status)
        return stats
    wanted_times = {_parse_time(value) for value in payload["times"]}
    schedule.slots.exclude(start_time__in=wanted_times).delete()
    for value in payload["times"]:
        start_time = _parse_time(value)
        duration = payload["duration"] or 1
        _slot, status = _update_or_create_tracked(
            ActivityScheduleSlot,
            lookup={"schedule": schedule, "start_time": start_time},
            defaults={
                "end_time": _end_time(start_time, duration),
                "duration_minutes": duration,
                "slot_type": payload["slot_type"],
                "capacity": payload["capacity"] or 0,
                "days_of_week": [],
                "active": True,
            },
        )
        _count(stats, status)
    return stats


def seed_alias(
    *,
    provider,
    activity,
    slot,
    raw_product_name,
    manual,
    notes,
):
    _alias, status = _update_or_create_tracked(
        ProviderAlias,
        lookup={
            "provider": provider,
            "raw_product_name": raw_product_name,
            "raw_option_name": "",
            "provider_product_code": "",
            "provider_option_code": "",
        },
        defaults={
            "linked_activity": activity,
            "linked_schedule": slot.schedule if slot else None,
            "linked_slot": slot,
            "approved": True,
            "needs_manual_confirmation": manual,
            "notes": notes,
        },
    )
    return status


def seed_direct_ota_aliases(*, providers, activities):
    stats = _stats()
    for payload in DIRECT_OTA_ALIASES:
        activity = activities[payload["activity_name"]]
        slot = _activity_slot(activity, payload["slot_start_time"])
        _count(
            stats,
            seed_alias(
                provider=providers[payload["provider"]],
                activity=activity,
                slot=slot,
                raw_product_name=payload["raw_product_name"],
                manual=False,
                notes=payload["notes"],
            ),
        )
    return stats


def assert_catalog_drift():
    expected = set(LIVE_BOOKEO_PRODUCT_NAMES)
    actual = set(TourActivity.objects.values_list("name", flat=True))
    missing = sorted(expected - actual)
    if missing:
        raise CommandError(f"Bookeo catalog drift detected: missing={missing}")


def build_alias_coverage():
    direct_activity_names = {payload["activity_name"] for payload in DIRECT_OTA_ALIASES}
    mapped = []
    for payload in DIRECT_OTA_ALIASES:
        if ProviderAlias.objects.filter(
            provider__code=payload["provider"],
            raw_product_name=payload["raw_product_name"],
            approved=True,
        ).exists():
            mapped.append(payload)
    manual_products = [
        product_name
        for product_name in LIVE_BOOKEO_PRODUCT_NAMES
        if product_name not in direct_activity_names
    ]
    return {
        "mapped": mapped,
        "unmapped": UNMAPPED_SAMPLE_PRODUCT_STRINGS,
        "manual_products": manual_products,
    }


def _activity_slot(activity, start_time):
    if not start_time:
        return None
    return (
        ActivityScheduleSlot.objects.filter(
            schedule__activity=activity,
            schedule__schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
            start_time=_parse_time(start_time),
            active=True,
        )
        .order_by("id")
        .first()
    )


def _update_or_create_tracked(model, *, lookup, defaults):
    existing = model.objects.filter(**lookup).first()
    changed = False
    if existing:
        changed = any(
            getattr(existing, field_name) != value
            for field_name, value in defaults.items()
        )
    instance, created = model.objects.update_or_create(**lookup, defaults=defaults)
    if created:
        return instance, "created"
    if changed:
        return instance, "updated"
    return instance, "skipped"


def _stats():
    return {"created": 0, "updated": 0, "skipped": 0}


def _count(stats, status):
    stats[status] += 1


def _merge_stats(target, source):
    for key, value in source.items():
        target[key] += value


def _parse_time(value):
    return datetime.strptime(value, "%H:%M").time()


def _parse_date(value):
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _end_time(start_time, duration_minutes):
    end = datetime.combine(datetime(2000, 1, 1).date(), start_time) + timedelta(
        minutes=duration_minutes
    )
    if end.date() != datetime(2000, 1, 1).date():
        return None
    return end.time()
