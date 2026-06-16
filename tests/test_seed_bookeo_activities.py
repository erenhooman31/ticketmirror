from datetime import date, time
from io import StringIO

import pytest
from django.core.management import call_command

from apps.bookings.management.commands.seed_bookeo_activities import (
    ACTIVITY_SEEDS,
    ALIAS_SEEDS,
)
from apps.bookings.models import (
    ActivitySchedule,
    ActivityScheduleSlot,
    Booking,
    Provider,
    ProviderAlias,
    ReviewQueueItem,
    TourActivity,
)


@pytest.mark.django_db
def test_seed_bookeo_activities_command_creates_missing_activities():
    call_command("seed_bookeo_activities")

    assert set(TourActivity.objects.values_list("name", flat=True)) == {
        seed.name for seed in ACTIVITY_SEEDS
    }
    assert Provider.objects.filter(code="viator").exists()
    assert Provider.objects.filter(code="getyourguide").exists()
    assert ProviderAlias.objects.count() == len(ALIAS_SEEDS)
    assert ProviderAlias.objects.filter(
        raw_product_name="2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR",
        linked_activity__name="Bosphorus Cruise",
        approved=True,
        needs_manual_confirmation=True,
    ).exists()


@pytest.mark.django_db
def test_seed_bookeo_activities_command_is_idempotent():
    call_command("seed_bookeo_activities")
    call_command("seed_bookeo_activities")

    assert TourActivity.objects.count() == len(ACTIVITY_SEEDS)
    assert Provider.objects.count() == 2
    assert ProviderAlias.objects.count() == len(ALIAS_SEEDS)


@pytest.mark.django_db
def test_seed_bookeo_activities_does_not_overwrite_manual_activity_edits():
    activity = TourActivity.objects.create(
        name="Bosphorus Cruise",
        internal_display_name="Operator Cruise Label",
        active=False,
        category=TourActivity.Category.OTHER,
        display_settings={"show_home_agenda": False, "operator": "custom"},
        notes="Operator edited notes.",
    )

    call_command("seed_bookeo_activities")

    activity.refresh_from_db()
    assert activity.internal_display_name == "Operator Cruise Label"
    assert activity.active is False
    assert activity.category == TourActivity.Category.OTHER
    assert activity.display_settings == {
        "show_home_agenda": False,
        "operator": "custom",
    }
    assert activity.notes == "Operator edited notes."


@pytest.mark.django_db
def test_seed_bookeo_activities_preserves_aliases_schedules_bookings_and_review_queue():
    provider = Provider.objects.create(
        name="Viator",
        code="viator",
        parser_key="operator-parser",
        known_sender_patterns=["operator"],
        known_subject_patterns=["operator subject"],
    )
    activity = TourActivity.objects.create(
        name="Bosphorus Cruise",
        internal_display_name="Bosphorus Cruise",
        category=TourActivity.Category.CRUISE,
        display_settings={"operator": "kept"},
    )
    schedule = ActivitySchedule.objects.create(
        activity=activity,
        schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
        name="Operator current",
        active=False,
        priority=77,
        days_of_week=[1, 2, 3],
        notes="Keep this schedule.",
    )
    slot = ActivityScheduleSlot.objects.create(
        schedule=schedule,
        start_time=time(11, 30),
        end_time=time(13, 30),
        duration_minutes=120,
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=123,
        days_of_week=[1, 2, 3],
        active=False,
    )
    alias = ProviderAlias.objects.create(
        provider=provider,
        raw_product_name="Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR",
        raw_option_name="",
        provider_product_code="",
        provider_option_code="",
        linked_activity=activity,
        linked_schedule=schedule,
        linked_slot=slot,
        approved=False,
        needs_manual_confirmation=False,
        notes="Operator alias note.",
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="VIATOR-KEEP",
        activity=activity,
        schedule_slot=slot,
        raw_product_name=alias.raw_product_name,
        active_travel_date=date(2026, 6, 20),
    )
    review_item = ReviewQueueItem.objects.create(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
        title="Keep review item",
        details="Operator review queue data.",
    )

    call_command("seed_bookeo_activities")

    provider.refresh_from_db()
    schedule.refresh_from_db()
    slot.refresh_from_db()
    alias.refresh_from_db()
    booking.refresh_from_db()
    review_item.refresh_from_db()

    assert provider.parser_key == "operator-parser"
    assert provider.known_sender_patterns == ["operator"]
    assert schedule.name == "Operator current"
    assert schedule.active is False
    assert schedule.priority == 77
    assert schedule.days_of_week == [1, 2, 3]
    assert slot.start_time == time(11, 30)
    assert slot.capacity == 123
    assert slot.active is False
    assert alias.linked_schedule == schedule
    assert alias.linked_slot == slot
    assert alias.approved is False
    assert alias.notes == "Operator alias note."
    assert booking.schedule_slot == slot
    assert review_item.booking == booking


@pytest.mark.django_db
def test_seed_bookeo_activities_output_includes_created_updated_skipped_counts():
    stdout = StringIO()

    call_command("seed_bookeo_activities", stdout=stdout)

    output = stdout.getvalue()
    assert "created=" in output
    assert "updated=" in output
    assert "skipped=" in output
    assert "activities created=4" in output
    assert "aliases created=12" in output
