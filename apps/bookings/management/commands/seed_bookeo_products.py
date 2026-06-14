from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
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


BOOKEO_PRODUCTS = [
    {
        "name": "Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR",
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
        "duration": None,
        "slot_type": ActivityScheduleSlot.SlotType.PRIVATE_GROUP,
        "capacity": None,
        "times": [],
        "current_from": None,
        "current_to": None,
        "other_schedules": [],
        "manual": True,
        "notes": (
            "Yacht special case. Confirm capacity, duration, and scheduling model."
        ),
    },
]


class Command(BaseCommand):
    help = "Seed the 12 inspected Bookeo products as TicketMirror activities."

    @transaction.atomic
    def handle(self, *args, **options):
        providers = seed_providers()
        stats = {
            "activities": 0,
            "schedules": 0,
            "slots": 0,
            "people_rules": 0,
            "aliases": 0,
        }

        for payload in BOOKEO_PRODUCTS:
            activity, created = TourActivity.objects.update_or_create(
                name=payload["name"],
                defaults={
                    "internal_display_name": payload["name"],
                    "active": True,
                    "category": payload["category"],
                    "display_settings": {
                        "visible_internally": True,
                        "show_in_calendar": True,
                        "show_in_reports": True,
                    },
                    "notes": payload["notes"],
                },
            )
            stats["activities"] += int(created)
            stats["people_rules"] += seed_people_rule(activity, payload)
            current_schedule, schedule_created = seed_schedule(
                activity,
                ActivitySchedule.ScheduleKind.CURRENT,
                "Current schedule",
                active=True,
                priority=100,
                date_from=payload["current_from"],
                date_to=payload["current_to"],
            )
            stats["schedules"] += int(schedule_created)
            stats["schedules"] += seed_other_schedules(activity, payload)
            stats["slots"] += seed_slots(current_schedule, payload)
            provider = providers[payload["provider"]]
            linked_slot = current_schedule.slots.order_by("start_time").first()
            stats["aliases"] += seed_alias(
                provider=provider,
                activity=activity,
                slot=linked_slot,
                payload=payload,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded Bookeo-inspired activities: "
                f"{stats['activities']} activities, "
                f"{stats['schedules']} schedules, "
                f"{stats['slots']} slots, "
                f"{stats['people_rules']} people rules, "
                f"{stats['aliases']} aliases created."
            )
        )


def seed_providers():
    providers = {}
    for payload in PROVIDERS:
        provider, _created = Provider.objects.update_or_create(
            code=payload["code"],
            defaults={
                "name": payload["name"],
                "active": True,
                "parser_key": payload["parser_key"],
                "known_sender_patterns": payload["known_sender_patterns"],
                "known_subject_patterns": payload["known_subject_patterns"],
            },
        )
        providers[provider.code] = provider
    return providers


def seed_people_rule(activity, payload):
    _rule, created = ActivityPeopleRule.objects.update_or_create(
        activity=activity,
        defaults={
            "min_people_per_booking": 1,
            "max_people_per_booking": 20 if payload["capacity"] else None,
            "default_capacity": payload["capacity"],
            "capacity_note": payload["notes"],
        },
    )
    return int(created)


def seed_schedule(activity, schedule_kind, name, active, priority, date_from, date_to):
    return ActivitySchedule.objects.update_or_create(
        activity=activity,
        schedule_kind=schedule_kind,
        priority=priority,
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
    created_count = 0
    for priority, (date_from, date_to, name) in enumerate(
        payload["other_schedules"], start=200
    ):
        schedule, created = seed_schedule(
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
        created_count += int(created)

    stale = ActivitySchedule.objects.filter(
        activity=activity,
        schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
    )
    if kept_ids:
        stale = stale.exclude(id__in=kept_ids)
    stale.delete()
    return created_count


def seed_slots(schedule, payload):
    wanted_times = {_parse_time(value) for value in payload["times"]}
    schedule.slots.exclude(start_time__in=wanted_times).delete()
    created_count = 0
    for value in payload["times"]:
        start_time = _parse_time(value)
        duration = payload["duration"] or 1
        slot, created = ActivityScheduleSlot.objects.update_or_create(
            schedule=schedule,
            start_time=start_time,
            defaults={
                "end_time": _end_time(start_time, duration),
                "duration_minutes": duration,
                "slot_type": payload["slot_type"],
                "capacity": payload["capacity"] or 0,
                "days_of_week": [],
                "active": True,
            },
        )
        created_count += int(created and slot is not None)
    return created_count


def seed_alias(provider, activity, slot, payload):
    _alias, created = ProviderAlias.objects.update_or_create(
        provider=provider,
        raw_product_name=payload["name"],
        raw_option_name="",
        provider_product_code="",
        provider_option_code="",
        defaults={
            "linked_activity": activity,
            "linked_schedule": slot.schedule if slot else None,
            "linked_slot": slot,
            "approved": not payload["manual"],
            "needs_manual_confirmation": payload["manual"],
            "notes": payload["notes"],
        },
    )
    return int(created)


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
