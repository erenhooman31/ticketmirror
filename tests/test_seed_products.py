import pytest
from django.core.management import call_command

from apps.bookings.management.commands.seed_bookeo_products import DIRECT_OTA_ALIASES
from apps.bookings.models import (
    ActivitySchedule,
    ActivityScheduleSlot,
    Provider,
    ProviderAlias,
    TourActivity,
)
from apps.ingestion.parsers.base import ParsedBooking
from apps.ingestion.services import match_product_alias


@pytest.mark.django_db
def test_seed_bookeo_products_command_creates_12_activities():
    call_command("seed_bookeo_products")

    assert TourActivity.objects.count() == 12
    assert Provider.objects.filter(code="viator").exists()
    assert Provider.objects.filter(code="getyourguide").exists()


@pytest.mark.django_db
def test_seed_bookeo_products_command_is_idempotent():
    call_command("seed_bookeo_products")
    call_command("seed_bookeo_products")

    assert TourActivity.objects.count() == 12
    assert ActivitySchedule.objects.count() == 34
    assert ProviderAlias.objects.count() == 32


@pytest.mark.django_db
def test_seed_bookeo_products_aliases_link_to_activity_and_slot():
    call_command("seed_bookeo_products")

    alias = ProviderAlias.objects.get(
        provider__code="viator",
        raw_product_name="Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR",
    )

    assert alias.provider.code == "viator"
    assert alias.linked_activity.name == alias.raw_product_name
    assert alias.linked_slot.start_time.strftime("%H:%M") == "11:00"
    assert alias.approved is True
    assert alias.needs_manual_confirmation is True

    bookeo_alias = ProviderAlias.objects.get(
        provider__code="bookeo",
        raw_product_name="Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR",
    )
    assert bookeo_alias.linked_activity == alias.linked_activity
    assert bookeo_alias.approved is True


@pytest.mark.django_db
def test_seed_bookeo_products_sets_home_agenda_display_labels():
    call_command("seed_bookeo_products")

    viator = TourActivity.objects.get(
        name="Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR"
    )
    old_city = TourActivity.objects.get(name="Istanbul Old City And Bosphorus Tour")

    assert viator.internal_display_name == "VIATOR 2H"
    assert viator.display_settings["show_home_agenda"] is True
    assert old_city.internal_display_name == "OLD CITY VIATOR"
    assert old_city.display_settings["show_home_agenda"] is True


@pytest.mark.django_db
def test_seed_bookeo_products_creates_expected_slots_and_capacity():
    call_command("seed_bookeo_products")

    activity = TourActivity.objects.get(name="GYG 2 Hours Bosphorus Tour SL-(2-3)")
    slots = {
        slot.start_time.strftime("%H:%M"): slot.capacity
        for slot in ActivityScheduleSlot.objects.filter(
            schedule__activity=activity,
            schedule__schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
        )
    }

    assert slots == {"14:00": 250, "19:00": 250}


@pytest.mark.django_db
def test_seed_bookeo_products_creates_exact_transfer_current_schedule():
    call_command("seed_bookeo_products")

    activity = TourActivity.objects.get(
        name="2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER"
    )
    schedule = ActivitySchedule.objects.get(
        activity=activity,
        schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
    )
    slots = {
        slot.start_time.strftime("%H:%M"): slot.capacity
        for slot in schedule.slots.order_by("start_time")
    }

    assert schedule.date_from.isoformat() == "2026-04-01"
    assert schedule.date_to is None
    assert slots == {"11:00": 250, "14:00": 250, "19:00": 250}
    assert {slot.duration_minutes for slot in schedule.slots.all()} == {120}


@pytest.mark.django_db
def test_seed_bookeo_products_creates_real_other_schedule_rows_only():
    call_command("seed_bookeo_products")

    activity = TourActivity.objects.get(
        name="Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR"
    )
    rows = [
        (
            date_from.isoformat(),
            date_to.isoformat() if date_to else None,
            name,
        )
        for date_from, date_to, name in ActivitySchedule.objects.filter(
            activity=activity,
            schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
        )
        .order_by("priority")
        .values_list("date_from", "date_to", "name")
    ]

    assert rows == [
        ("2027-04-01", None, "SUMMER season 2027"),
        ("2026-10-01", "2027-03-31", "WINTER season"),
        ("2026-08-01", "2026-09-30", "AUTMUN season"),
        ("2026-04-01", "2026-04-03", "summer season"),
        ("2025-10-01", "2026-03-31", "WINTER season"),
        ("2024-05-19", "2025-09-30", "Default season"),
    ]
    assert not ActivitySchedule.objects.filter(
        name__in=["Other schedule (unconfirmed)", "Copy of Current schedule"]
    ).exists()


@pytest.mark.django_db
def test_seed_bookeo_products_other_schedules_have_non_empty_bookeo_values():
    call_command("seed_bookeo_products")

    rows = ActivitySchedule.objects.filter(
        schedule_kind=ActivitySchedule.ScheduleKind.OTHER
    )

    assert rows.count() == 22
    assert all(row.date_from for row in rows)
    assert all(row.name for row in rows)
    assert all(row.date_to or "season" in row.name.lower() for row in rows)


@pytest.mark.django_db
def test_seed_bookeo_products_duration_matches_inspected_products():
    call_command("seed_bookeo_products")

    expectations = {
        "Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR": 120,
        "2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR": 120,
        "2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER": 120,
        "2 Hours Bosphorus Tour SL-1": 120,
        "GYG 2 Hours Bosphorus Tour SL-(2-3)": 120,
        "1 Hours Bosphorus Tour viator": 60,
        "1 Hours Bosphorus Tour GYG": 60,
    }
    for product_name, expected_minutes in expectations.items():
        assert set(
            ActivityScheduleSlot.objects.filter(
                schedule__activity__name=product_name,
                schedule__schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
            ).values_list("duration_minutes", flat=True)
        ) == {expected_minutes}


@pytest.mark.django_db
def test_seed_bookeo_products_people_capacity_does_not_replace_slot_capacity():
    call_command("seed_bookeo_products")

    activity = TourActivity.objects.get(
        name="2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER"
    )

    assert activity.people_rule.max_people_per_booking == 20
    assert activity.people_rule.default_capacity == 250


@pytest.mark.django_db
def test_seed_bookeo_products_keeps_yacht_unconfirmed_without_fixed_slot():
    call_command("seed_bookeo_products")

    activity = TourActivity.objects.get(name="gyg yacht")
    alias = ProviderAlias.objects.get(
        linked_activity=activity,
        provider__code="getyourguide",
        raw_product_name="gyg yacht",
    )

    assert activity.category == TourActivity.Category.YACHT
    assert activity.schedules.count() == 1
    assert (
        ActivityScheduleSlot.objects.filter(
            schedule__activity=activity,
            active=True,
        ).count()
        == 0
    )
    duration_slot = ActivityScheduleSlot.objects.get(schedule__activity=activity)
    assert duration_slot.duration_minutes == 60
    assert duration_slot.active is False
    assert alias.linked_slot is None
    assert alias.needs_manual_confirmation is True


@pytest.mark.django_db
def test_seed_bookeo_products_aliases_real_incoming_product_strings():
    call_command("seed_bookeo_products")

    direct_alias = ProviderAlias.objects.get(
        provider__code="sputnik8",
        raw_product_name=next(
            item["raw_product_name"]
            for item in DIRECT_OTA_ALIASES
            if item["provider"] == "sputnik8"
        ),
    )

    assert direct_alias.approved is True
    assert direct_alias.needs_manual_confirmation is False
    assert direct_alias.linked_activity.name == "GYG 2 Hours Bosphorus Tour SL-(2-3)"
    assert direct_alias.linked_slot.start_time.strftime("%H:%M") == "19:00"

    tripster_alias = ProviderAlias.objects.get(
        provider__code="tripster",
        raw_product_name=next(
            item["raw_product_name"]
            for item in DIRECT_OTA_ALIASES
            if item["provider"] == "tripster"
        ),
    )
    assert (
        tripster_alias.linked_activity.name
        == "Istanbul Two Continents Tour By Bus And Bosphorus Cruise"
    )

    tripster_audio = ProviderAlias.objects.get(
        provider__code="tripster",
        raw_product_name="Морская прогулка по Босфору с аудиогидом",
    )
    sputnik_big_istanbul = ProviderAlias.objects.get(
        provider__code="sputnik8",
        raw_product_name="Великолепный Стамбул в Европе и Азии",
    )
    assert tripster_audio.approved is True
    assert tripster_audio.linked_activity.name == "GYG 2 Hours Bosphorus Tour SL-(2-3)"
    assert sputnik_big_istanbul.approved is True
    assert (
        sputnik_big_istanbul.linked_activity.name
        == "Istanbul Two Continents Tour By Bus And Bosphorus Cruise"
    )


@pytest.mark.django_db
def test_match_product_alias_normalizes_whitespace_and_ignores_case():
    call_command("seed_bookeo_products")

    parsed = ParsedBooking(
        provider_code="viator",
        raw_product_name="  guided   bosphorus cruise boat tour in istanbul  ",
        raw_option_name="Guided Bosphorus Cruise Boat Tour In Istanbul 10:00",
    )

    alias_match = match_product_alias(parsed)

    assert alias_match.alias is not None
    assert (
        alias_match.alias.linked_activity.name
        == "2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR"
    )


@pytest.mark.django_db
def test_match_product_alias_resolves_seeded_russian_products():
    call_command("seed_bookeo_products")

    parsed = ParsedBooking(
        provider_code="tripster",
        raw_product_name="  морская   прогулка по босфору с аудиогидом  ",
    )

    alias_match = match_product_alias(parsed)

    assert alias_match.alias is not None
    assert (
        alias_match.alias.linked_activity.name == "GYG 2 Hours Bosphorus Tour SL-(2-3)"
    )


@pytest.mark.django_db
def test_seed_bookeo_products_allows_operator_created_extra_activity():
    TourActivity.objects.create(
        name="Unexpected public checkout tour",
        internal_display_name="Unexpected",
        active=True,
        category=TourActivity.Category.OTHER,
    )

    call_command("seed_bookeo_products")

    assert TourActivity.objects.filter(name="Unexpected public checkout tour").exists()
    assert TourActivity.objects.count() == 13


@pytest.mark.django_db
def test_seed_bookeo_products_creates_catalog_expected_after_deploy_seed():
    call_command("seed_bookeo_products")

    seeded_names = set(TourActivity.objects.values_list("name", flat=True))
    assert len(seeded_names) == 12
    assert ProviderAlias.objects.filter(approved=True).count() >= 24
    for product_name in seeded_names:
        assert ProviderAlias.objects.filter(
            linked_activity__name=product_name,
            approved=True,
        ).exists()


@pytest.mark.django_db
def test_deprecated_seed_wrappers_run_bookeo_seed():
    call_command("seed_defaults")
    call_command("seed_products")

    assert TourActivity.objects.count() == 12
