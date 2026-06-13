import csv
from datetime import date, time
from io import StringIO

import pytest
from helpers import create_activity_setup, create_booking

from apps.bookings.models import ActivityScheduleSlot, Booking
from apps.bookings.services import (
    export_capacity_summary_csv,
    export_daily_manifest_csv,
    export_provider_summary_csv,
    get_capacity_for_slot_date,
    get_daily_capacity_summary,
)


@pytest.fixture
def capacity_data():
    fixed = create_activity_setup(
        activity_name="City Tour",
        start_time=time(9, 0),
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=10,
    )
    full_day = create_activity_setup(
        provider_code="viator-full",
        provider_name="Viator Full",
        activity_name="Full Day City Tour",
        start_time=time(8, 0),
        duration_minutes=480,
        slot_type=ActivityScheduleSlot.SlotType.FULL_DAY,
        capacity=25,
        alias=False,
    )
    return {"fixed": fixed, "full_day": full_day, "date": date(2026, 6, 21)}


def _rows(csv_text):
    return list(csv.DictReader(StringIO(csv_text)))


@pytest.mark.django_db
def test_fixed_time_capacity_calculation(capacity_data):
    create_booking(
        capacity_data["fixed"], "CONF-1", status=Booking.Status.CONFIRMED, pax=3
    )
    create_booking(
        capacity_data["fixed"], "MOD-1", status=Booking.Status.MODIFIED, pax=1
    )

    snapshot = get_capacity_for_slot_date(
        capacity_data["fixed"]["slot"],
        capacity_data["date"],
    )

    assert snapshot["capacity"] == 10
    assert snapshot["confirmed_pax"] == 4
    assert snapshot["remaining"] == 6


@pytest.mark.django_db
def test_full_day_capacity_calculation(capacity_data):
    create_booking(
        capacity_data["full_day"], "FULL-1", status=Booking.Status.CONFIRMED, pax=6
    )
    create_booking(
        capacity_data["full_day"], "FULL-2", status=Booking.Status.CONFIRMED, pax=4
    )

    summary = get_daily_capacity_summary(capacity_data["date"])
    full_day_row = next(
        row for row in summary if row["slot"] == capacity_data["full_day"]["slot"]
    )

    assert full_day_row["slot"].slot_type == ActivityScheduleSlot.SlotType.FULL_DAY
    assert full_day_row["capacity"] == 25
    assert full_day_row["confirmed_pax"] == 10
    assert full_day_row["remaining"] == 15


@pytest.mark.django_db
def test_pending_and_manual_review_pax_are_separate(capacity_data):
    create_booking(
        capacity_data["fixed"],
        "PEND-1",
        status=Booking.Status.PENDING_PROVIDER_ACCEPTANCE,
        pax=2,
    )
    create_booking(
        capacity_data["fixed"], "REV-1", status=Booking.Status.MANUAL_REVIEW, pax=5
    )

    snapshot = get_capacity_for_slot_date(
        capacity_data["fixed"]["slot"],
        capacity_data["date"],
    )

    assert snapshot["confirmed_pax"] == 0
    assert snapshot["pending_pax"] == 2
    assert snapshot["manual_review_pax"] == 5
    assert snapshot["remaining"] == 10


@pytest.mark.django_db
def test_cancelled_bookings_are_excluded(capacity_data):
    create_booking(
        capacity_data["fixed"], "CONF-1", status=Booking.Status.CONFIRMED, pax=3
    )
    create_booking(
        capacity_data["fixed"], "CANCEL-1", status=Booking.Status.CANCELLED, pax=9
    )

    snapshot = get_capacity_for_slot_date(
        capacity_data["fixed"]["slot"],
        capacity_data["date"],
    )

    assert snapshot["confirmed_pax"] == 3
    assert snapshot["pending_pax"] == 0
    assert snapshot["remaining"] == 7


@pytest.mark.django_db
def test_csv_columns_are_correct(capacity_data):
    create_booking(
        capacity_data["fixed"], "CONF-1", status=Booking.Status.CONFIRMED, pax=3
    )

    manifest = csv.reader(StringIO(export_daily_manifest_csv(capacity_data["date"])))
    capacity = csv.reader(
        StringIO(
            export_capacity_summary_csv(capacity_data["date"], capacity_data["date"])
        )
    )
    provider = csv.reader(
        StringIO(
            export_provider_summary_csv(capacity_data["date"], capacity_data["date"])
        )
    )

    assert next(manifest) == [
        "date",
        "activity",
        "slot",
        "provider",
        "reference",
        "lead traveler",
        "phone",
        "email",
        "pax",
        "pickup",
        "meeting point",
        "language",
        "status",
        "notes",
    ]
    assert next(capacity) == [
        "date",
        "activity",
        "slot",
        "confirmed pax",
        "pending pax",
        "manual review pax",
        "capacity",
        "remaining",
    ]
    assert next(provider) == [
        "provider",
        "booking count",
        "confirmed pax",
        "pending pax",
        "cancelled count",
    ]


@pytest.mark.django_db
def test_date_range_filters_work(capacity_data):
    create_booking(
        capacity_data["fixed"], "IN-1", status=Booking.Status.CONFIRMED, pax=3
    )
    create_booking(
        capacity_data["fixed"],
        "OUT-1",
        status=Booking.Status.CONFIRMED,
        pax=4,
        service_date=date(2026, 6, 23),
    )

    capacity_rows = _rows(
        export_capacity_summary_csv(date(2026, 6, 21), date(2026, 6, 21))
    )
    provider_rows = _rows(
        export_provider_summary_csv(date(2026, 6, 21), date(2026, 6, 21))
    )

    assert {row["date"] for row in capacity_rows} == {"2026-06-21"}
    assert provider_rows[0]["booking count"] == "1"
    assert provider_rows[0]["confirmed pax"] == "3"
