from datetime import date, time

import pytest
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.bookings.models import (
    Booking,
    BookingEvent,
    CapacityRule,
    Product,
    ProductVariant,
    Provider,
)


@pytest.fixture
def users(django_user_model):
    viewer = django_user_model.objects.create_user(
        username="viewer",
        password="password",
    )
    operator = django_user_model.objects.create_user(
        username="operator",
        password="password",
    )
    operator.profile.role = UserProfile.Role.OPERATOR
    operator.profile.save()
    return {"viewer": viewer, "operator": operator}


@pytest.fixture
def booking_data():
    provider = Provider.objects.create(name="Viator", code="viator")
    product = Product.objects.create(canonical_name="City Tour")
    variant = ProductVariant.objects.create(
        product=product,
        variant_name="Morning",
        slot_type=ProductVariant.SlotType.FIXED_TIME,
        default_capacity=5,
    )
    CapacityRule.objects.create(
        product_variant=variant,
        date_from=date(2026, 6, 21),
        date_to=date(2026, 6, 21),
        slot_start_time=time(9, 0),
        capacity=5,
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="BR-1",
        status=Booking.Status.CONFIRMED,
        canonical_product=product,
        canonical_variant=variant,
        raw_product_name="City Tour",
        raw_option_name="Morning",
        provider_travel_date=date(2026, 6, 21),
        provider_start_time=time(9, 0),
        provider_traveler_count=2,
        active_travel_date=date(2026, 6, 21),
        active_start_time=time(9, 0),
        active_traveler_count=2,
        lead_traveler_name="Alex Sample",
        lead_traveler_phone="+1 555 0100",
    )
    return {
        "provider": provider,
        "product": product,
        "variant": variant,
        "booking": booking,
    }


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    response = client.get(reverse("core:dashboard"))

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_viewer_cannot_edit_booking(client, users, booking_data):
    client.force_login(users["viewer"])
    response = client.get(reverse("bookings:edit", args=[booking_data["booking"].id]))

    assert response.status_code == 403


@pytest.mark.django_db
def test_operator_can_edit_booking(client, users, booking_data):
    booking = booking_data["booking"]
    client.force_login(users["operator"])
    response = client.get(reverse("bookings:edit", args=[booking.id]))

    assert response.status_code == 200
    assert b"Edit booking" in response.content


@pytest.mark.django_db
def test_manual_edit_creates_event(client, users, booking_data):
    booking = booking_data["booking"]
    client.force_login(users["operator"])
    response = client.post(
        reverse("bookings:edit", args=[booking.id]),
        {
            "status": Booking.Status.CONFIRMED,
            "active_travel_date": "2026-06-21",
            "active_start_time": "09:00",
            "active_end_time": "",
            "active_slot_type": ProductVariant.SlotType.FIXED_TIME,
            "active_traveler_count": "4",
            "lead_traveler_name": "Alex Sample",
            "lead_traveler_email": "",
            "lead_traveler_phone": "+1 555 0100",
            "traveler_names": "[]",
            "ticket_breakdown": "{}",
            "language": "",
            "pickup_location": "",
            "meeting_point": "",
            "special_requirements": "",
            "customer_message": "",
            "price": "{}",
            "payment_status": "",
            "reason": "Updated pax after phone call.",
        },
    )
    booking.refresh_from_db()

    assert response.status_code == 302
    assert booking.active_traveler_count == 4
    assert "active_traveler_count" in booking.manual_override_fields
    assert BookingEvent.objects.filter(
        booking=booking,
        event_type=BookingEvent.EventType.MANUAL_EDIT,
    ).exists()


@pytest.mark.django_db
def test_daily_capacity_view_calculates_correctly(client, users, booking_data):
    client.force_login(users["viewer"])
    response = client.get(reverse("bookings:daily"), {"date": "2026-06-21"})

    assert response.status_code == 200
    assert response.context["rows"][0]["confirmed"] == 2
    assert response.context["rows"][0]["capacity"] == 5
    assert response.context["rows"][0]["remaining"] == 3


@pytest.mark.django_db
def test_csv_export_works(client, users, booking_data):
    client.force_login(users["viewer"])
    response = client.get(
        reverse("reports:daily_manifest_csv"),
        {"date": "2026-06-21"},
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert b"provider_booking_reference" in response.content
    assert b"BR-1" in response.content
