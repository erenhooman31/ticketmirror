from datetime import date, time

import pytest
from django.urls import reverse
from django.utils import timezone

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
        lead_traveler_email="alex.sample@example.test",
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
def test_dashboard_renders_bookeo_style_messages_and_agenda(
    client,
    users,
    booking_data,
):
    BookingEvent.objects.create(
        booking=booking_data["booking"],
        event_type=BookingEvent.EventType.EMAIL_NEW_BOOKING,
        source=BookingEvent.Source.EMAIL,
        created_at=timezone.now(),
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("core:dashboard"), {"date": "2026-06-21"})

    assert response.status_code == 200
    assert b"MESSAGES" in response.content
    assert b"AGENDA" in response.content
    assert b"New booking - Alex Sample" in response.content
    assert b'data-bs-toggle="modal"' in response.content
    assert b"Booking</button>" in response.content
    assert b"Traveler</button>" in response.content
    assert b"Notes *</button>" in response.content
    assert b"Audit</button>" in response.content
    assert b"Open full booking" in response.content
    assert b">Save</button>" not in response.content
    assert b"City Tour - Morning" in response.content
    assert response.context["agenda_sections"][0]["rows"][0]["booked"] == 2


@pytest.mark.django_db
def test_dashboard_range_groups_agenda_days(client, users, booking_data):
    client.force_login(users["viewer"])
    response = client.get(
        reverse("core:dashboard"),
        {"date": "2026-06-21", "range": "3"},
    )

    assert response.status_code == 200
    assert response.context["range_days"] == 3
    assert [section["date"] for section in response.context["agenda_sections"]] == [
        date(2026, 6, 21),
        date(2026, 6, 22),
        date(2026, 6, 23),
    ]
    assert "date=2026-06-24" in response.context["next_url"]


@pytest.mark.django_db
def test_dashboard_modal_post_updates_booking_and_returns_to_dashboard(
    client,
    users,
    booking_data,
):
    booking = booking_data["booking"]
    client.force_login(users["operator"])
    response = client.post(
        reverse("bookings:edit", args=[booking.id]),
        {
            "next": "/?date=2026-06-21&range=3",
            "status": Booking.Status.MODIFIED,
            "canonical_product": str(booking_data["product"].id),
            "canonical_variant": str(booking_data["variant"].id),
            "active_travel_date": "2026-06-21",
            "active_start_time": "10:30",
            "active_end_time": "",
            "active_slot_type": ProductVariant.SlotType.FIXED_TIME,
            "active_traveler_count": "5",
            "lead_traveler_name": "Alex Updated",
            "lead_traveler_email": "alex.updated@example.test",
            "lead_traveler_phone": "+1 555 0199",
            "traveler_names": '["Alex Updated"]',
            "ticket_breakdown": '{"adult": 5}',
            "language": "en",
            "pickup_location": "Hotel lobby",
            "meeting_point": "Pier 1",
            "special_requirements": "Window seat",
            "customer_message": "Please confirm pickup.",
            "price": '{"currency": "USD", "amount": "100.00"}',
            "payment_status": "paid",
            "reason": "Edited from dashboard popup.",
        },
    )
    booking.refresh_from_db()

    assert response.status_code == 302
    assert response["Location"] == "/?date=2026-06-21&range=3"
    assert booking.status == Booking.Status.MODIFIED
    assert booking.active_start_time == time(10, 30)
    assert booking.active_traveler_count == 5
    assert booking.lead_traveler_name == "Alex Updated"
    assert BookingEvent.objects.filter(
        booking=booking,
        event_type=BookingEvent.EventType.MANUAL_STATUS_CHANGE,
    ).exists()


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
def test_calendar_range_groups_multiple_days(client, users, booking_data):
    client.force_login(users["viewer"])
    response = client.get(
        reverse("bookings:daily"),
        {"date": "2026-06-21", "range": "3"},
    )

    assert response.status_code == 200
    assert response.context["range_days"] == 3
    assert [section["date"] for section in response.context["day_sections"]] == [
        date(2026, 6, 21),
        date(2026, 6, 22),
        date(2026, 6, 23),
    ]
    assert "date=2026-06-24" in response.context["next_url"]


@pytest.mark.django_db
def test_calendar_default_shows_cancelled_and_manual_review_counts(
    client,
    users,
    booking_data,
):
    Booking.objects.create(
        provider=booking_data["provider"],
        provider_booking_reference="BR-MANUAL",
        status=Booking.Status.MANUAL_REVIEW,
        canonical_product=booking_data["product"],
        canonical_variant=booking_data["variant"],
        active_travel_date=date(2026, 6, 21),
        active_start_time=time(9, 0),
        active_slot_type=ProductVariant.SlotType.FIXED_TIME,
        active_traveler_count=3,
    )
    Booking.objects.create(
        provider=booking_data["provider"],
        provider_booking_reference="BR-CANCEL",
        status=Booking.Status.CANCELLED,
        canonical_product=booking_data["product"],
        canonical_variant=booking_data["variant"],
        active_travel_date=date(2026, 6, 21),
        active_start_time=time(9, 0),
        active_slot_type=ProductVariant.SlotType.FIXED_TIME,
        active_traveler_count=4,
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("bookings:daily"), {"date": "2026-06-21"})

    row = response.context["rows"][0]
    assert row["confirmed"] == 2
    assert row["manual_review"] == 3
    assert row["cancelled_count"] == 1
    assert row["remaining"] == 3


@pytest.mark.django_db
def test_calendar_visibility_toggles_hide_cancelled_and_manual_review_counts(
    client,
    users,
    booking_data,
):
    Booking.objects.create(
        provider=booking_data["provider"],
        provider_booking_reference="BR-MANUAL",
        status=Booking.Status.MANUAL_REVIEW,
        canonical_product=booking_data["product"],
        canonical_variant=booking_data["variant"],
        active_travel_date=date(2026, 6, 21),
        active_start_time=time(9, 0),
        active_slot_type=ProductVariant.SlotType.FIXED_TIME,
        active_traveler_count=3,
    )
    Booking.objects.create(
        provider=booking_data["provider"],
        provider_booking_reference="BR-CANCEL",
        status=Booking.Status.CANCELLED,
        canonical_product=booking_data["product"],
        canonical_variant=booking_data["variant"],
        active_travel_date=date(2026, 6, 21),
        active_start_time=time(9, 0),
        active_slot_type=ProductVariant.SlotType.FIXED_TIME,
        active_traveler_count=4,
    )

    client.force_login(users["viewer"])
    response = client.get(
        reverse("bookings:daily"),
        {
            "date": "2026-06-21",
            "show_cancelled": "0",
            "show_manual_review": "0",
        },
    )

    row = response.context["rows"][0]
    assert row["manual_review"] == 0
    assert row["cancelled_count"] == 0
    assert row["confirmed"] == 2
    assert row["remaining"] == 3


@pytest.mark.django_db
def test_calendar_search_and_provider_filter_preserve_slot_capacity_math(
    client,
    users,
    booking_data,
):
    gyg = Provider.objects.create(name="GetYourGuide", code="getyourguide")
    Booking.objects.create(
        provider=gyg,
        provider_booking_reference="GYG-1",
        status=Booking.Status.CONFIRMED,
        canonical_product=booking_data["product"],
        canonical_variant=booking_data["variant"],
        active_travel_date=date(2026, 6, 21),
        active_start_time=time(9, 0),
        active_slot_type=ProductVariant.SlotType.FIXED_TIME,
        active_traveler_count=1,
        lead_traveler_name="Jordan Provider",
        lead_traveler_phone="+1 555 0101",
        lead_traveler_email="jordan.provider@example.test",
    )

    client.force_login(users["viewer"])
    provider_response = client.get(
        reverse("bookings:daily"),
        {"date": "2026-06-21", "provider": str(gyg.id)},
    )
    email_response = client.get(
        reverse("bookings:daily"),
        {"date": "2026-06-21", "q": "alex.sample@example.test"},
    )

    provider_row = provider_response.context["rows"][0]
    assert provider_row["confirmed"] == 3
    assert provider_row["capacity"] == 5
    assert provider_row["remaining"] == 2
    assert email_response.context["rows"][0]["confirmed"] == 3


@pytest.mark.django_db
def test_calendar_product_and_category_filters_limit_rows(client, users, booking_data):
    other_product = Product.objects.create(
        canonical_name="Museum Entry",
        category="Museum",
    )
    other_variant = ProductVariant.objects.create(
        product=other_product,
        variant_name="Timed entry",
        slot_type=ProductVariant.SlotType.FIXED_TIME,
        default_capacity=10,
    )
    CapacityRule.objects.create(
        product_variant=other_variant,
        date_from=date(2026, 6, 21),
        date_to=date(2026, 6, 21),
        slot_start_time=time(11, 0),
        capacity=10,
    )

    client.force_login(users["viewer"])
    product_response = client.get(
        reverse("bookings:daily"),
        {"date": "2026-06-21", "product": str(booking_data["product"].id)},
    )
    category_response = client.get(
        reverse("bookings:daily"),
        {"date": "2026-06-21", "category": "Museum"},
    )

    assert {row["product"] for row in product_response.context["rows"]} == {
        booking_data["product"]
    }
    assert {row["product"] for row in category_response.context["rows"]} == {
        other_product
    }


@pytest.mark.django_db
def test_csv_export_works(client, users, booking_data):
    client.force_login(users["viewer"])
    response = client.get(
        reverse("reports:daily_manifest_csv"),
        {"date": "2026-06-21"},
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert b"reference" in response.content
    assert b"BR-1" in response.content
