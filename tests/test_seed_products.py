import pytest
from django.core.management import call_command

from apps.bookings.models import (
    ActivitySchedule,
    ActivityScheduleSlot,
    Provider,
    ProviderAlias,
    TourActivity,
)


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
    assert ActivitySchedule.objects.count() == 24
    assert ProviderAlias.objects.count() == 12


@pytest.mark.django_db
def test_seed_bookeo_products_aliases_link_to_activity_and_slot():
    call_command("seed_bookeo_products")

    alias = ProviderAlias.objects.get(
        raw_product_name="Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR"
    )

    assert alias.provider.code == "viator"
    assert alias.linked_activity.name == alias.raw_product_name
    assert alias.linked_slot.start_time.strftime("%H:%M") == "11:00"
    assert alias.needs_manual_confirmation is True


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
def test_seed_bookeo_products_keeps_yacht_unconfirmed_without_fixed_slot():
    call_command("seed_bookeo_products")

    activity = TourActivity.objects.get(name="gyg yacht")
    alias = ProviderAlias.objects.get(linked_activity=activity)

    assert activity.category == TourActivity.Category.YACHT
    assert activity.schedules.count() == 2
    assert ActivityScheduleSlot.objects.filter(schedule__activity=activity).count() == 0
    assert alias.linked_slot is None
    assert alias.needs_manual_confirmation is True


@pytest.mark.django_db
def test_deprecated_seed_wrappers_run_bookeo_seed():
    call_command("seed_defaults")
    call_command("seed_products")

    assert TourActivity.objects.count() == 12
