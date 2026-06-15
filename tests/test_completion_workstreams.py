from datetime import date, time
from unittest.mock import Mock, patch

import pytest
from django.urls import reverse
from django.utils import timezone
from helpers import create_activity_setup, create_booking

from apps.accounts.models import UserProfile
from apps.bookings.models import (
    ActivityScheduleSlot,
    Booking,
    BookingEvent,
    ReviewQueueItem,
)
from apps.bookings.services import CapacityExceededError, create_internal_booking
from apps.ingestion.models import RawEmail
from apps.ingestion.parsers.base import ParsedBooking
from apps.ingestion.parsers.common import EVENT_NEW_BOOKING, STATUS_CONFIRMED
from apps.ingestion.services import upsert_booking_from_parsed


@pytest.fixture
def users(django_user_model):
    viewer = django_user_model.objects.create_user(
        username="completion-viewer",
        password="password",
    )
    operator = django_user_model.objects.create_user(
        username="completion-operator",
        password="password",
    )
    admin = django_user_model.objects.create_user(
        username="completion-admin",
        password="password",
    )
    operator.profile.role = UserProfile.Role.OPERATOR
    operator.profile.save()
    admin.profile.role = UserProfile.Role.ADMIN
    admin.profile.save()
    return {"viewer": viewer, "operator": operator, "admin": admin}


@pytest.fixture
def raw_email():
    return RawEmail.objects.create(
        gmail_message_id="completion-raw-1",
        gmail_outer_sender="bookings@viator.com",
        subject="Provider booking",
        received_at=timezone.now(),
        body_text="Synthetic provider email",
    )


def parsed_booking(**overrides):
    values = {
        "provider_code": "viator",
        "provider_booking_reference": "OTA-OVER-1",
        "event_type": EVENT_NEW_BOOKING,
        "status": STATUS_CONFIRMED,
        "raw_product_name": "Capacity Tour",
        "raw_option_name": "Morning",
        "travel_date": date(2026, 6, 21),
        "start_time": time(9, 0),
        "end_time": time(11, 0),
        "slot_type": ActivityScheduleSlot.SlotType.FIXED_TIME,
        "traveler_count": 1,
        "lead_traveler_name": "OTA Lead",
        "lead_traveler_email": "ota@example.test",
        "lead_traveler_phone": "+1 555 0100",
        "confidence": 1.0,
        "warnings": [],
    }
    values.update(overrides)
    return ParsedBooking(**values)


@pytest.mark.django_db
def test_create_internal_booking_under_capacity_creates_event(users):
    setup = create_activity_setup(capacity=5)

    booking = create_internal_booking(
        service_date=setup["date"],
        schedule_slot=setup["slot"],
        traveler_count=3,
        lead_traveler_name="Direct Lead",
        user=users["operator"],
    )

    assert booking.provider.code == "direct"
    assert booking.active_traveler_count == 3
    assert booking.events.filter(
        event_type=BookingEvent.EventType.EMAIL_NEW_BOOKING,
        source=BookingEvent.Source.MANUAL,
    ).exists()


@pytest.mark.django_db
def test_operator_internal_booking_overcapacity_is_rejected(users):
    setup = create_activity_setup(capacity=2)
    create_booking(setup, "FULL-1", pax=2)

    with pytest.raises(CapacityExceededError):
        create_internal_booking(
            service_date=setup["date"],
            schedule_slot=setup["slot"],
            traveler_count=1,
            user=users["operator"],
        )

    assert Booking.objects.filter(provider__code="direct").count() == 0


@pytest.mark.django_db
def test_admin_internal_booking_override_requires_reason(users):
    setup = create_activity_setup(capacity=2)
    create_booking(setup, "FULL-1", pax=2)

    with pytest.raises(CapacityExceededError):
        create_internal_booking(
            service_date=setup["date"],
            schedule_slot=setup["slot"],
            traveler_count=1,
            user=users["admin"],
            allow_overcapacity=True,
        )

    booking = create_internal_booking(
        service_date=setup["date"],
        schedule_slot=setup["slot"],
        traveler_count=1,
        user=users["admin"],
        allow_overcapacity=True,
        override_reason="Manager approved walk-up.",
    )

    assert booking.review_items.filter(
        issue_type=ReviewQueueItem.IssueType.CAPACITY_OVERBOOKED
    ).exists()


@pytest.mark.django_db
def test_cancelled_and_no_show_bookings_do_not_block_internal_capacity(users):
    setup = create_activity_setup(capacity=2)
    create_booking(setup, "CANCEL-1", status=Booking.Status.CANCELLED, pax=2)
    no_show = create_booking(setup, "NOSHOW-1", pax=2)
    no_show.attendance_status = Booking.AttendanceStatus.GELMEDI
    no_show.save(update_fields=["attendance_status", "updated_at"])

    booking = create_internal_booking(
        service_date=setup["date"],
        schedule_slot=setup["slot"],
        traveler_count=2,
        user=users["operator"],
    )

    assert booking.active_traveler_count == 2


@pytest.mark.django_db
def test_ota_booking_overcapacity_creates_review_warning(raw_email):
    setup = create_activity_setup(
        activity_name="Capacity Tour",
        raw_product_name="Capacity Tour",
        capacity=2,
    )
    create_booking(setup, "FULL-1", pax=2)

    booking = upsert_booking_from_parsed(raw_email, parsed_booking())

    assert booking.status == Booking.Status.CONFIRMED
    assert raw_email.parse_status == RawEmail.ParseStatus.NEEDS_REVIEW
    assert ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.CAPACITY_OVERBOOKED,
        status=ReviewQueueItem.Status.OPEN,
    ).exists()
    assert booking.events.filter(
        event_type=BookingEvent.EventType.CONFLICT_DETECTED
    ).exists()


@pytest.mark.django_db
def test_ingestion_settings_roles_and_process_action(client, users):
    client.force_login(users["viewer"])
    response = client.get(reverse("core:settings_ingestion"))
    assert response.status_code == 200
    assert "GMAIL_CLIENT_SECRET" in response.content.decode()
    assert "test-secret" not in response.content.decode()

    response = client.post(
        reverse("core:settings_ingestion"),
        {"action": "process_pending"},
    )
    assert response.status_code == 403

    client.force_login(users["operator"])
    task = Mock()
    task.apply.return_value.get.return_value = 3
    with patch("apps.core.views.process_pending_raw_emails", task):
        response = client.post(
            reverse("core:settings_ingestion"),
            {"action": "process_pending", "limit": "10"},
        )
    assert response.status_code == 302
    task.apply.assert_called_once_with(kwargs={"limit": 10})


@pytest.mark.django_db
def test_admin_duplicate_slot_validation(client, users):
    setup = create_activity_setup(capacity=10)
    client.force_login(users["admin"])

    response = client.post(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {
            "action": "save_time_slot",
            "schedule_id": str(setup["schedule"].id),
            "start_time": "09:00",
            "duration_minutes": "120",
            "slot_kind": "fixed-time",
            "capacity": "10",
            "slot_status": "active",
        },
    )

    assert response.status_code == 200
    assert "Available time was not saved" in response.content.decode()
    assert setup["schedule"].slots.filter(start_time=time(9, 0)).count() == 1


@pytest.mark.django_db
def test_new_report_csv_exports(client, users, raw_email):
    setup = create_activity_setup(capacity=1)
    create_booking(setup, "OVER-1", pax=2)
    raw_email.parse_status = RawEmail.ParseStatus.FAILED
    raw_email.parse_error = "Parser failed"
    raw_email.save(update_fields=["parse_status", "parse_error", "updated_at"])
    ReviewQueueItem.objects.create(
        booking=setup["alias"].linked_activity.bookings.first(),
        issue_type=ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
        title="Unmapped",
        details="Missing alias",
    )
    client.force_login(users["viewer"])

    overcapacity = client.get(
        reverse("reports:overcapacity_csv"),
        {"date_from": "2026-06-21", "date_to": "2026-06-21"},
    )
    unmapped = client.get(reverse("reports:unmapped_provider_products_csv"))
    failures = client.get(reverse("reports:parser_failures_csv"))

    assert overcapacity.status_code == 200
    assert "overbooked pax" in overcapacity.content.decode()
    assert "OVER-1" not in overcapacity.content.decode()
    assert "provider_alias_missing" in unmapped.content.decode()
    assert "Parser failed" in failures.content.decode()
