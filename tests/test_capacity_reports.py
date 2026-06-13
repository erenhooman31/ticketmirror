import csv
from datetime import date, time
from io import StringIO

import pytest

from apps.bookings.models import (
    Booking,
    CapacityRule,
    Product,
    ProductVariant,
    Provider,
)
from apps.bookings.services import (
    export_capacity_summary_csv,
    export_daily_manifest_csv,
    export_provider_summary_csv,
    get_capacity_for_variant_date_slot,
    get_daily_capacity_summary,
)


@pytest.fixture
def capacity_data():
    provider = Provider.objects.create(name="Viator", code="viator")
    product = Product.objects.create(canonical_name="City Tour")
    fixed = ProductVariant.objects.create(
        product=product,
        variant_name="Morning",
        slot_type=ProductVariant.SlotType.FIXED_TIME,
        default_capacity=8,
    )
    full_day = ProductVariant.objects.create(
        product=product,
        variant_name="Full day",
        slot_type=ProductVariant.SlotType.FULL_DAY,
        default_capacity=20,
    )
    service_date = date(2026, 6, 21)
    CapacityRule.objects.create(
        product_variant=fixed,
        date_from=service_date,
        date_to=service_date,
        slot_start_time=time(9, 0),
        capacity=10,
    )
    CapacityRule.objects.create(
        product_variant=full_day,
        date_from=service_date,
        date_to=service_date,
        capacity=25,
    )
    return {
        "provider": provider,
        "product": product,
        "fixed": fixed,
        "full_day": full_day,
        "date": service_date,
    }


def _booking(data, reference, *, status, pax, variant=None, service_date=None):
    variant = variant or data["fixed"]
    service_date = service_date or data["date"]
    slot_type = variant.slot_type
    start_time = time(9, 0) if slot_type == ProductVariant.SlotType.FIXED_TIME else None
    return Booking.objects.create(
        provider=data["provider"],
        provider_booking_reference=reference,
        status=status,
        canonical_product=data["product"],
        canonical_variant=variant,
        active_travel_date=service_date,
        active_start_time=start_time,
        active_slot_type=slot_type,
        active_traveler_count=pax,
        lead_traveler_name=f"Lead {reference}",
        lead_traveler_phone="+1 555 0100",
        lead_traveler_email=f"{reference.lower()}@example.test",
        pickup_location="Hotel",
        meeting_point="Pier",
        language="English",
        special_requirements="Window seat",
    )


def _rows(csv_text):
    return list(csv.DictReader(StringIO(csv_text)))


@pytest.mark.django_db
def test_fixed_time_capacity_calculation(capacity_data):
    _booking(capacity_data, "CONF-1", status=Booking.Status.CONFIRMED, pax=3)
    _booking(capacity_data, "MOD-1", status=Booking.Status.MODIFIED, pax=1)

    snapshot = get_capacity_for_variant_date_slot(
        capacity_data["fixed"],
        capacity_data["date"],
        time(9, 0),
    )

    assert snapshot["capacity"] == 10
    assert snapshot["confirmed_pax"] == 4
    assert snapshot["remaining"] == 6


@pytest.mark.django_db
def test_full_day_capacity_calculation(capacity_data):
    _booking(
        capacity_data,
        "FULL-1",
        status=Booking.Status.CONFIRMED,
        pax=6,
        variant=capacity_data["full_day"],
    )
    _booking(
        capacity_data,
        "FULL-2",
        status=Booking.Status.CONFIRMED,
        pax=4,
        variant=capacity_data["full_day"],
    )

    summary = get_daily_capacity_summary(capacity_data["date"])
    full_day_row = next(
        row for row in summary if row["variant"] == capacity_data["full_day"]
    )

    assert full_day_row["slot"] == ProductVariant.SlotType.FULL_DAY
    assert full_day_row["capacity"] == 25
    assert full_day_row["confirmed_pax"] == 10
    assert full_day_row["remaining"] == 15


@pytest.mark.django_db
def test_pending_and_manual_review_pax_are_separate(capacity_data):
    _booking(
        capacity_data,
        "PEND-1",
        status=Booking.Status.PENDING_PROVIDER_ACCEPTANCE,
        pax=2,
    )
    _booking(capacity_data, "REV-1", status=Booking.Status.MANUAL_REVIEW, pax=5)

    snapshot = get_capacity_for_variant_date_slot(
        capacity_data["fixed"],
        capacity_data["date"],
        time(9, 0),
    )

    assert snapshot["confirmed_pax"] == 0
    assert snapshot["pending_pax"] == 2
    assert snapshot["manual_review_pax"] == 5
    assert snapshot["remaining"] == 10


@pytest.mark.django_db
def test_cancelled_bookings_are_excluded(capacity_data):
    _booking(capacity_data, "CONF-1", status=Booking.Status.CONFIRMED, pax=3)
    _booking(capacity_data, "CANCEL-1", status=Booking.Status.CANCELLED, pax=9)

    snapshot = get_capacity_for_variant_date_slot(
        capacity_data["fixed"],
        capacity_data["date"],
        time(9, 0),
    )

    assert snapshot["confirmed_pax"] == 3
    assert snapshot["pending_pax"] == 0
    assert snapshot["remaining"] == 7


@pytest.mark.django_db
def test_csv_columns_are_correct(capacity_data):
    _booking(capacity_data, "CONF-1", status=Booking.Status.CONFIRMED, pax=3)

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
        "product",
        "variant",
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
        "product",
        "variant",
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
    _booking(capacity_data, "IN-1", status=Booking.Status.CONFIRMED, pax=3)
    _booking(
        capacity_data,
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
