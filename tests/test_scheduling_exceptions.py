from datetime import date, time

import pytest

from apps.bookings.models import (
    ActivitySchedule,
    ActivityScheduleException,
    ActivityScheduleSlot,
)
from apps.bookings.services import get_daily_capacity_summary, resolve_active_schedule
from tests.helpers import create_activity_setup


@pytest.mark.django_db
def test_narrow_other_schedule_wins_over_current_schedule():
    setup = create_activity_setup(activity_name="Seasonal Cruise")
    activity = setup["activity"]
    service_date = date(2026, 7, 15)
    other_schedule = ActivitySchedule.objects.create(
        activity=activity,
        schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
        name="High season",
        active=True,
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
        priority=50,
    )
    ActivityScheduleSlot.objects.create(
        schedule=other_schedule,
        start_time=time(14, 0),
        duration_minutes=120,
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=250,
        active=True,
    )

    assert resolve_active_schedule(activity, service_date) == other_schedule
    rows = get_daily_capacity_summary(service_date)

    assert [row["slot"].start_time for row in rows] == [time(14, 0)]


@pytest.mark.django_db
def test_current_schedule_wins_when_date_specificity_ties():
    setup = create_activity_setup(activity_name="Tie Break Cruise")
    activity = setup["activity"]
    current_schedule = setup["schedule"]
    current_schedule.date_from = date(2026, 6, 1)
    current_schedule.date_to = date(2026, 6, 30)
    current_schedule.save()
    other_schedule = ActivitySchedule.objects.create(
        activity=activity,
        schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
        name="Alternate",
        active=True,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        priority=1,
    )
    ActivityScheduleSlot.objects.create(
        schedule=other_schedule,
        start_time=time(19, 0),
        duration_minutes=120,
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=250,
        active=True,
    )

    assert resolve_active_schedule(activity, date(2026, 6, 15)) == current_schedule


@pytest.mark.django_db
def test_schedule_exceptions_remove_override_and_add_slots():
    setup = create_activity_setup(activity_name="Exception Cruise", capacity=100)
    schedule = setup["schedule"]
    slot = setup["slot"]
    service_date = date(2026, 6, 21)
    ActivityScheduleException.objects.create(
        schedule=schedule,
        exception_type=ActivityScheduleException.ExceptionType.OVERRIDE_CAPACITY,
        date=service_date,
        start_time=slot.start_time,
        capacity=80,
    )
    ActivityScheduleException.objects.create(
        schedule=schedule,
        exception_type=ActivityScheduleException.ExceptionType.EXTRA_SLOT,
        date=service_date,
        start_time=time(15, 0),
        end_time=time(17, 0),
        capacity=40,
    )

    rows = get_daily_capacity_summary(service_date)

    assert [(row["slot_label"], row["capacity"]) for row in rows] == [
        ("09:00", 80),
        ("15:00 Extra slot", 40),
    ]

    ActivityScheduleException.objects.create(
        schedule=schedule,
        exception_type=ActivityScheduleException.ExceptionType.REMOVED_SLOT,
        date=service_date,
        start_time=slot.start_time,
    )

    rows = get_daily_capacity_summary(service_date)

    assert [(row["slot"], row["slot_label"], row["capacity"]) for row in rows] == [
        (None, "15:00 Extra slot", 40)
    ]


@pytest.mark.django_db
def test_weekday_filter_must_allow_service_date():
    setup = create_activity_setup(activity_name="Weekday Cruise")
    schedule = setup["schedule"]
    schedule.days_of_week = [0]
    schedule.save()

    assert get_daily_capacity_summary(date(2026, 6, 21)) == []
