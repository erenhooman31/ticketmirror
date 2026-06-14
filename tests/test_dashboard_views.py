from datetime import date, time

import pytest
from django.urls import reverse
from django.utils import timezone
from helpers import create_activity_setup, create_booking

from apps.accounts.models import UserProfile
from apps.bookings.models import ActivityScheduleSlot, Booking, BookingEvent, Provider


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
    setup = create_activity_setup(
        activity_name="City Tour",
        start_time=time(9, 0),
        capacity=5,
    )
    booking = create_booking(
        setup,
        "BR-1",
        status=Booking.Status.CONFIRMED,
        pax=2,
        lead_name="Alex Sample",
    )
    return {**setup, "booking": booking}


def edit_payload(booking_data, **overrides):
    slot = booking_data["slot"]
    payload = {
        "status": Booking.Status.CONFIRMED,
        "activity": str(booking_data["activity"].id),
        "schedule_slot": str(slot.id),
        "active_travel_date": "2026-06-21",
        "active_start_time": "09:00",
        "active_end_time": "",
        "active_slot_type": ActivityScheduleSlot.SlotType.FIXED_TIME,
        "active_traveler_count": "2",
        "lead_traveler_name": "Alex Sample",
        "lead_traveler_email": "alex.sample@example.test",
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
        "reason": "Updated from test.",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    response = client.get(reverse("core:dashboard"))

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_dashboard_renders_messages_and_agenda(client, users, booking_data):
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
    assert b"City Tour" in response.content
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
        edit_payload(
            booking_data,
            next="/?date=2026-06-21&range=3",
            status=Booking.Status.MODIFIED,
            active_start_time="10:30",
            active_traveler_count="5",
            lead_traveler_name="Alex Updated",
            reason="Edited from dashboard popup.",
        ),
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
    client.force_login(users["operator"])
    response = client.get(reverse("bookings:edit", args=[booking_data["booking"].id]))

    assert response.status_code == 200
    assert b"Edit booking" in response.content


@pytest.mark.django_db
def test_manual_edit_creates_event(client, users, booking_data):
    booking = booking_data["booking"]
    client.force_login(users["operator"])
    response = client.post(
        reverse("bookings:edit", args=[booking.id]),
        edit_payload(
            booking_data,
            active_traveler_count="4",
            reason="Updated pax after phone call.",
        ),
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
def test_calendar_default_shows_cancelled_and_manual_review_counts(
    client,
    users,
    booking_data,
):
    create_booking(
        booking_data,
        "BR-MANUAL",
        status=Booking.Status.MANUAL_REVIEW,
        pax=3,
    )
    create_booking(
        booking_data,
        "BR-CANCEL",
        status=Booking.Status.CANCELLED,
        pax=4,
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("bookings:daily"), {"date": "2026-06-21"})

    row = response.context["rows"][0]
    assert row["confirmed"] == 2
    assert row["manual_review"] == 3
    assert row["cancelled_count"] == 1
    assert row["remaining"] == 3


@pytest.mark.django_db
def test_calendar_visibility_toggles_hide_manual_review_counts(
    client,
    users,
    booking_data,
):
    create_booking(
        booking_data,
        "BR-MANUAL",
        status=Booking.Status.MANUAL_REVIEW,
        pax=3,
    )

    client.force_login(users["viewer"])
    response = client.get(
        reverse("bookings:daily"),
        {
            "date": "2026-06-21",
            "show_manual_review": "0",
        },
    )

    row = response.context["rows"][0]
    assert row["manual_review"] == 0
    assert row["confirmed"] == 2
    assert row["remaining"] == 3


@pytest.mark.django_db
def test_calendar_search_and_provider_filter_preserve_slot_capacity_math(
    client,
    users,
    booking_data,
):
    gyg = Provider.objects.create(name="GetYourGuide", code="getyourguide")
    create_booking(
        booking_data,
        "GYG-1",
        status=Booking.Status.CONFIRMED,
        pax=1,
        provider=gyg,
        lead_name="Jordan Provider",
    )

    client.force_login(users["viewer"])
    provider_response = client.get(
        reverse("bookings:daily"),
        {"date": "2026-06-21", "provider": str(gyg.id)},
    )
    email_response = client.get(
        reverse("bookings:daily"),
        {"date": "2026-06-21", "q": "br-1@example.test"},
    )

    provider_row = provider_response.context["rows"][0]
    assert provider_row["confirmed"] == 3
    assert provider_row["capacity"] == 5
    assert provider_row["remaining"] == 2
    assert email_response.context["rows"][0]["confirmed"] == 3


@pytest.mark.django_db
def test_calendar_activity_and_category_filters_limit_rows(client, users, booking_data):
    other = create_activity_setup(
        provider_code="direct",
        provider_name="Direct",
        activity_name="Museum Entry",
        category="other",
        start_time=time(11, 0),
        capacity=10,
        alias=False,
    )

    client.force_login(users["viewer"])
    activity_response = client.get(
        reverse("bookings:daily"),
        {"date": "2026-06-21", "activity": str(booking_data["activity"].id)},
    )
    category_response = client.get(
        reverse("bookings:daily"),
        {"date": "2026-06-21", "category": "other"},
    )

    assert {row["activity"] for row in activity_response.context["rows"]} == {
        booking_data["activity"]
    }
    assert {row["activity"] for row in category_response.context["rows"]} == {
        other["activity"]
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


@pytest.mark.django_db
def test_customers_directory_search_alpha_and_detail(client, users, booking_data):
    second_alex = create_booking(
        booking_data,
        "BR-2",
        status=Booking.Status.CONFIRMED,
        pax=1,
        lead_name="Alex Sample",
    )
    second_alex.lead_traveler_email = booking_data["booking"].lead_traveler_email
    second_alex.lead_traveler_phone = booking_data["booking"].lead_traveler_phone
    second_alex.save(update_fields=["lead_traveler_email", "lead_traveler_phone"])
    create_booking(
        booking_data,
        "BR-3",
        status=Booking.Status.CONFIRMED,
        pax=3,
        lead_name="Bella Guest",
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("core:customers"), {"q": "alex"})

    assert response.status_code == 200
    html = response.content.decode()
    assert "Customers" in html
    assert "Alphabet filter" in html
    assert "Alex Sample" in html
    assert "Bella Guest" not in html
    assert "Total people:" in html
    assert "BR-1" in html
    assert "BR-2" in html

    alpha_response = client.get(reverse("core:customers"), {"letter": "B"})
    alpha_html = alpha_response.content.decode()

    assert "Bella Guest" in alpha_html
    assert "Alex Sample" not in alpha_html
