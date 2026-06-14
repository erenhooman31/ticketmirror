from datetime import date, time

import pytest
from django.urls import reverse
from django.utils import timezone
from helpers import create_activity_setup, create_booking

from apps.accounts.models import UserProfile
from apps.bookings.models import (
    ActivityScheduleSlot,
    Booking,
    BookingEvent,
    Provider,
    ReviewQueueItem,
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
        "attendance_status": "",
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
def test_dashboard_message_footer_filters_stay_on_home(client, users, booking_data):
    BookingEvent.objects.create(
        booking=booking_data["booking"],
        event_type=BookingEvent.EventType.EMAIL_NEW_BOOKING,
        source=BookingEvent.Source.EMAIL,
        created_at=timezone.now(),
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("core:dashboard"), {"date": "2026-06-21"})
    html = response.content.decode()

    assert 'href="/?date=2026-06-21&amp;range=1&amp;messages=all"' in html
    assert 'href="/?date=2026-06-21&amp;range=1&amp;messages=unread"' in html
    assert 'href="/customers/">All</a>' not in html


@pytest.mark.django_db
def test_dashboard_agenda_controls_match_bookeo_home(client, users, booking_data):
    client.force_login(users["viewer"])
    response = client.get(reverse("core:dashboard"), {"date": "2026-06-21"})
    html = response.content.decode()

    assert ">Today</a>" in html
    assert ">3 days</a>" in html
    assert ">7 days</a>" in html
    assert ">Print</a>" in html
    assert "Previous" not in html
    assert "Next" not in html


@pytest.mark.django_db
def test_dashboard_booking_modal_hides_raw_internal_sections(
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

    client.force_login(users["operator"])
    response = client.get(reverse("core:dashboard"), {"date": "2026-06-21"})
    html = response.content.decode()

    assert "Booking" in html
    assert "Traveler" in html
    assert "Notes *" in html
    for raw_label in [
        "Audit note",
        "Audit</button>",
        "Slot type:",
        "Ticket breakdown:",
        "Provider import",
        "Raw product",
        "Payments",
        "Price:",
        "Open full booking",
        "Send email",
        "manual_review_pax",
        "active_pax",
    ]:
        assert raw_label not in html


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
    assert [section["label"] for section in response.context["agenda_sections"]] == [
        "Sunday, 21 June",
        "Monday, 22 June",
        "Tuesday, 23 June",
    ]


@pytest.mark.django_db
def test_dashboard_agenda_sorts_rows_by_clock_time(client, users, booking_data):
    create_activity_setup(
        provider_code="direct",
        provider_name="Direct",
        activity_name="Early Tour",
        start_time=time(8, 15),
        capacity=10,
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("core:dashboard"), {"date": "2026-06-21"})
    rows = response.context["agenda_sections"][0]["rows"]

    assert [row["time"] for row in rows[:2]] == ["8:15", "9:00"]


@pytest.mark.django_db
def test_dashboard_agenda_item_opens_slot_modal(client, users, booking_data):
    client.force_login(users["viewer"])
    response = client.get(reverse("core:dashboard"), {"date": "2026-06-21"})
    row = response.context["agenda_sections"][0]["rows"][0]
    html = response.content.decode()

    assert f'data-bs-target="#{row["modal_id"]}"' in html
    assert f'id="{row["modal_id"]}"' in html
    assert "Bookings" in html
    assert "Access" in html
    assert "Notes" in html
    assert "Alex Sample" in html
    assert "Booking number: BR-1" in html
    assert "09:00 Fixed time" not in html


@pytest.mark.django_db
def test_dashboard_agenda_excludes_product_mismatch_bookings(
    client,
    users,
    booking_data,
):
    mismatch = create_booking(
        booking_data,
        "BR-MISMATCH",
        status=Booking.Status.MANUAL_REVIEW,
        pax=3,
        lead_name="Mismatch Guest",
    )
    ReviewQueueItem.objects.create(
        booking=mismatch,
        issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
        status=ReviewQueueItem.Status.OPEN,
        title="Product mismatch",
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("core:dashboard"), {"date": "2026-06-21"})
    row = response.context["agenda_sections"][0]["rows"][0]

    assert row["booked"] == 2
    assert all(card["reference"] != "BR-MISMATCH" for card in row["bookings"])


@pytest.mark.django_db
def test_dashboard_agenda_shows_product_matched_review_with_warning(
    client,
    users,
    booking_data,
):
    review = create_booking(
        booking_data,
        "BR-REVIEW",
        status=Booking.Status.MANUAL_REVIEW,
        pax=1,
        lead_name="Review Guest",
    )
    ReviewQueueItem.objects.create(
        booking=review,
        issue_type=ReviewQueueItem.IssueType.LOW_CONFIDENCE_PARSE,
        status=ReviewQueueItem.Status.OPEN,
        title="Review matched booking",
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("core:dashboard"), {"date": "2026-06-21"})
    row = response.context["agenda_sections"][0]["rows"][0]
    html = response.content.decode()

    assert row["booked"] == 3
    assert row["has_warning"] is True
    assert "Review Guest" in html
    assert "Needs review" in html


@pytest.mark.django_db
def test_dashboard_agenda_attendance_capacity_rules(client, users, booking_data):
    booking_data["booking"].attendance_status = Booking.AttendanceStatus.GELDI
    booking_data["booking"].save(update_fields=["attendance_status", "updated_at"])
    gelmedi = create_booking(
        booking_data,
        "BR-GELMEDI",
        status=Booking.Status.CONFIRMED,
        pax=3,
        lead_name="No Show Guest",
    )
    gelmedi.attendance_status = Booking.AttendanceStatus.GELMEDI
    gelmedi.save(update_fields=["attendance_status", "updated_at"])
    sonra = create_booking(
        booking_data,
        "BR-SONRA",
        status=Booking.Status.CONFIRMED,
        pax=1,
        lead_name="Later Guest",
    )
    sonra.attendance_status = Booking.AttendanceStatus.SONRA_GELECEK
    sonra.save(update_fields=["attendance_status", "updated_at"])

    client.force_login(users["viewer"])
    response = client.get(reverse("core:dashboard"), {"date": "2026-06-21"})
    row = response.context["agenda_sections"][0]["rows"][0]
    html = response.content.decode()

    assert row["booked"] == 3
    assert row["available"] == 2
    assert "GELDI" in html
    assert "No Show Guest" in html
    assert "Does not count toward active capacity" in html
    assert "Later Guest" in html
    assert "SONRA GELECEK" in html


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

    refreshed = client.get(reverse("core:dashboard"), {"date": "2026-06-21"})
    refreshed_html = refreshed.content.decode()
    refreshed_row = refreshed.context["agenda_sections"][0]["rows"][0]
    assert refreshed_row["booked"] == 5
    assert "Alex Updated" in refreshed_html
    assert "Modified" in refreshed_html
    assert "Status changed - Alex Updated" in refreshed_html


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
def test_operator_can_mark_attendance_status(client, users, booking_data):
    booking = booking_data["booking"]
    client.force_login(users["operator"])
    response = client.post(
        reverse("bookings:edit", args=[booking.id]),
        edit_payload(
            booking_data,
            attendance_status=Booking.AttendanceStatus.GELDI,
            reason="",
        ),
    )
    booking.refresh_from_db()

    assert response.status_code == 302
    assert booking.attendance_status == Booking.AttendanceStatus.GELDI
    assert "attendance_status" in booking.manual_override_fields
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
    assert row["remaining"] == 0


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
    assert row["remaining"] == 0


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
