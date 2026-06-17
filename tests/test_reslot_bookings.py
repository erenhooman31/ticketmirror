from datetime import time
from io import StringIO

import pytest
from django.core.management import call_command
from helpers import create_activity_setup, create_booking

from apps.bookings.models import ActivityScheduleSlot, BookingEvent, ReviewQueueItem
from apps.bookings.services import get_capacity_for_slot_date


@pytest.mark.django_db
def test_reslot_bookings_moves_mismatched_booking_and_is_idempotent():
    setup = create_activity_setup(
        provider_code="reslot-viator",
        provider_name="Viator",
        activity_name="Reslot Cruise",
        start_time=time(11, 0),
        capacity=250,
    )
    slot_19 = ActivityScheduleSlot.objects.create(
        schedule=setup["schedule"],
        start_time=time(19, 0),
        duration_minutes=120,
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=250,
        active=True,
    )
    booking = create_booking(setup, "BR-RESLOT", pax=4)
    booking.active_start_time = time(19, 0)
    booking.provider_start_time = time(19, 0)
    booking.save(
        update_fields=["active_start_time", "provider_start_time", "updated_at"]
    )

    output = StringIO()
    call_command("reslot_bookings", stdout=output)
    booking.refresh_from_db()

    assert (
        "scanned=1 reslotted=1 unchanged=0 no_match=0 skipped_manual=0"
        in output.getvalue()
    )
    assert booking.schedule_slot == slot_19
    assert (
        get_capacity_for_slot_date(setup["slot"], setup["date"])["confirmed_pax"] == 0
    )
    assert get_capacity_for_slot_date(slot_19, setup["date"])["confirmed_pax"] == 4
    assert BookingEvent.objects.filter(
        booking=booking,
        event_type=BookingEvent.EventType.EMAIL_UPDATE,
        source=BookingEvent.Source.SYSTEM,
        new_values__repair="reslot_bookings",
    ).exists()

    second_output = StringIO()
    call_command("reslot_bookings", stdout=second_output)

    assert (
        "scanned=1 reslotted=0 unchanged=1 no_match=0 skipped_manual=0"
        in second_output.getvalue()
    )


@pytest.mark.django_db
def test_reslot_bookings_leaves_single_slot_and_manual_override_unchanged():
    single = create_activity_setup(
        provider_code="reslot-single",
        provider_name="Single",
        activity_name="Single Slot Tour",
        start_time=time(9, 0),
    )
    manual = create_activity_setup(
        provider_code="reslot-manual",
        provider_name="Manual",
        activity_name="Manual Slot Tour",
        start_time=time(11, 0),
    )
    manual_slot_19 = ActivityScheduleSlot.objects.create(
        schedule=manual["schedule"],
        start_time=time(19, 0),
        duration_minutes=120,
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=10,
        active=True,
    )
    single_booking = create_booking(single, "BR-SINGLE", pax=1)
    manual_booking = create_booking(manual, "BR-MANUAL", pax=2)
    manual_booking.active_start_time = time(19, 0)
    manual_booking.manual_override_fields = ["schedule_slot"]
    manual_booking.save(
        update_fields=[
            "active_start_time",
            "manual_override_fields",
            "updated_at",
        ]
    )

    output = StringIO()
    call_command("reslot_bookings", stdout=output)
    single_booking.refresh_from_db()
    manual_booking.refresh_from_db()

    assert (
        "scanned=2 reslotted=0 unchanged=1 no_match=0 skipped_manual=1"
        in output.getvalue()
    )
    assert single_booking.schedule_slot == single["slot"]
    assert manual_booking.schedule_slot == manual["slot"]
    assert manual_booking.schedule_slot != manual_slot_19


@pytest.mark.django_db
def test_reslot_bookings_keeps_current_slot_when_time_has_no_multi_slot_match():
    setup = create_activity_setup(
        provider_code="reslot-no-match",
        provider_name="No Match",
        activity_name="No Match Tour",
        start_time=time(11, 0),
        capacity=10,
    )
    ActivityScheduleSlot.objects.create(
        schedule=setup["schedule"],
        start_time=time(14, 0),
        duration_minutes=120,
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=10,
        active=True,
    )
    booking = create_booking(setup, "BR-NOMATCH", pax=2)
    booking.active_start_time = time(19, 0)
    booking.save(update_fields=["active_start_time", "updated_at"])

    output = StringIO()
    call_command("reslot_bookings", stdout=output)
    booking.refresh_from_db()

    assert (
        "scanned=1 reslotted=0 unchanged=0 no_match=1 skipped_manual=0"
        in output.getvalue()
    )
    assert booking.schedule_slot == setup["slot"]
    assert ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.TIME_MISSING,
        title="Schedule slot needs confirmation",
    ).exists()
