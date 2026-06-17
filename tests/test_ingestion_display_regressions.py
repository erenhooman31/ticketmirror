from datetime import date, time
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from helpers import create_activity_setup

from apps.accounts.models import UserProfile
from apps.bookings.models import Booking, Provider, ReviewQueueItem
from apps.ingestion.models import RawEmail
from apps.ingestion.services import process_gmail_message, process_raw_email

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "emails"
RAW_TOKENS = ["{}", "[]", ">None<", ">null<", "{&#x27;", "&#x27;}"]


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


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


def assert_no_raw_structures(html):
    for token in RAW_TOKENS:
        assert token not in html


@pytest.mark.django_db
def test_unknown_provider_goes_to_review_queue_with_clear_reason():
    raw_email = RawEmail.objects.create(
        gmail_message_id="unknown-provider-1",
        gmail_outer_sender="sender@example.test",
        subject="Booking details",
        received_at=timezone.now(),
        body_text="A booking message without known OTA markers.",
    )

    result = process_raw_email(raw_email.id)
    raw_email.refresh_from_db()

    assert result is None
    assert raw_email.parse_status == RawEmail.ParseStatus.NEEDS_REVIEW
    review = ReviewQueueItem.objects.get(raw_email=raw_email)
    assert review.issue_type == ReviewQueueItem.IssueType.PROVIDER_NOT_DETECTED
    assert review.details == "No deterministic provider pattern matched this email."


@pytest.mark.django_db
def test_non_booking_noise_is_ignored_without_review_queue_item():
    raw_email = RawEmail.objects.create(
        gmail_message_id="tiqets-report-noise-1",
        gmail_outer_sender="reports@tiqets.com",
        subject="Tiqets guestlist report",
        received_at=timezone.now(),
        body_text="Daily guestlist report for your venue. No booking action required.",
    )

    result = process_raw_email(raw_email.id)
    raw_email.refresh_from_db()

    assert result is None
    assert raw_email.parse_status == RawEmail.ParseStatus.IGNORED
    assert ReviewQueueItem.objects.filter(raw_email=raw_email).count() == 0


@pytest.mark.django_db
def test_dashboard_renders_imported_messages_without_raw_structures(client, users):
    setup = create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="Evening Bosphorus Cruise",
        raw_product_name="Evening Bosphorus Cruise",
        raw_option_name="Standard deck",
        start_time=time(19, 30),
    )
    raw_email = process_gmail_message(
        {
            "gmail_message_id": "dashboard-viator-1",
            "gmail_thread_id": "thread-dashboard-1",
            "gmail_history_id": "history-dashboard-1",
            "gmail_outer_sender": "bookings@viator.com",
            "subject": "Viator booking BR-123456789 confirmed",
            "received_at": timezone.now(),
            "body_text": fixture("viator_new.txt"),
        }
    )
    booking = Booking.objects.get(provider_booking_reference="BR-123456789")
    assert booking.activity == setup["activity"]
    assert raw_email.parse_status == RawEmail.ParseStatus.PARSED

    client.force_login(users["viewer"])
    response = client.get(reverse("core:dashboard"), {"date": "2026-06-21"})
    html = response.content.decode()

    assert response.status_code == 200
    assert "Viator" in html
    assert "BR-123456789" in html
    assert "Alex Sample" in html
    assert "Evening Bosphorus Cruise" in html
    assert_no_raw_structures(html)


@pytest.mark.django_db
def test_inbox_renders_partial_imports_without_raw_structures(client, users):
    raw_email = RawEmail.objects.create(
        gmail_message_id="partial-inbox-1",
        gmail_outer_sender="sender@example.test",
        subject="Unsupported provider booking",
        received_at=timezone.now(),
        body_text="Unsupported provider booking.",
        parse_status=RawEmail.ParseStatus.NEEDS_REVIEW,
        parse_error="Provider could not be detected.",
    )
    ReviewQueueItem.objects.create(
        raw_email=raw_email,
        issue_type=ReviewQueueItem.IssueType.PROVIDER_NOT_DETECTED,
        title="Provider not detected",
        details="No deterministic provider pattern matched this email.",
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("inbox"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Unknown provider" in html
    assert "Missing customer" in html
    assert "Missing tour/activity" in html
    assert "Missing date/time" in html
    assert "Missing participant count" in html
    assert_no_raw_structures(html)


@pytest.mark.django_db
def test_customers_render_missing_optional_fields_without_raw_structures(client, users):
    provider = Provider.objects.create(name="Viator", code="viator")
    Booking.objects.create(
        provider=provider,
        provider_booking_reference="BR-MISSING-OPTIONAL",
        status=Booking.Status.MANUAL_REVIEW,
        lead_traveler_name="Missing Optional Guest",
        active_traveler_count=1,
        active_travel_date=date(2026, 6, 21),
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("core:customers"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Missing Optional Guest" in html
    assert "Missing email" in html
    assert "Missing phone" in html
    assert "Missing tour/activity" in html
    assert_no_raw_structures(html)


@pytest.mark.django_db
def test_bookings_list_renders_display_safe_rows(client, users):
    provider = Provider.objects.create(name="GetYourGuide", code="getyourguide")
    Booking.objects.create(
        provider=provider,
        provider_booking_reference="GYG123",
        status=Booking.Status.MANUAL_REVIEW,
        lead_traveler_name="List Guest",
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("bookings:list"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "GetYourGuide" in html
    assert "GYG123" in html
    assert "List Guest" in html
    assert "Missing tour/activity" in html
    assert "Missing date/time" in html
    assert "Missing participant count" in html
    assert_no_raw_structures(html)


@pytest.mark.django_db
def test_repeated_gmail_sync_is_idempotent_for_same_message():
    create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="Evening Bosphorus Cruise",
        raw_product_name="Evening Bosphorus Cruise",
        raw_option_name="Standard deck",
        start_time=time(19, 30),
    )
    message = {
        "gmail_message_id": "idempotent-real-viator",
        "gmail_thread_id": "thread-idempotent",
        "gmail_history_id": "history-idempotent",
        "gmail_outer_sender": "bookings@viator.com",
        "subject": "Viator booking BR-123456789 confirmed",
        "received_at": timezone.now(),
        "body_text": fixture("viator_new.txt"),
    }

    first = process_gmail_message(message)
    second = process_gmail_message(message)

    assert first.id == second.id
    assert (
        RawEmail.objects.filter(gmail_message_id="idempotent-real-viator").count() == 1
    )
    assert (
        Booking.objects.filter(provider_booking_reference="BR-123456789").count() == 1
    )


@pytest.mark.django_db
def test_repair_command_fills_missing_booking_display_fields_idempotently():
    create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="Evening Bosphorus Cruise",
        raw_product_name="Evening Bosphorus Cruise",
        raw_option_name="Standard deck",
        start_time=time(19, 30),
    )
    raw_email = RawEmail.objects.create(
        gmail_message_id="repair-viator-1",
        gmail_thread_id="thread-repair-1",
        gmail_outer_sender="bookings@viator.com",
        subject="Viator booking BR-123456789 confirmed",
        received_at=timezone.now(),
        body_text=fixture("viator_new.txt"),
        parse_status=RawEmail.ParseStatus.PARSED,
    )
    provider = Provider.objects.get(code="viator")
    Booking.objects.create(
        provider=provider,
        provider_booking_reference="BR-123456789",
        status=Booking.Status.MANUAL_REVIEW,
    )

    first_output = StringIO()
    call_command("repair_parsed_booking_display_fields", stdout=first_output)
    booking = Booking.objects.get(provider_booking_reference="BR-123456789")

    assert "scanned=1 repaired=1" in first_output.getvalue()
    assert booking.lead_traveler_name == "Alex Sample"
    assert booking.raw_product_name == "Evening Bosphorus Cruise"
    assert booking.active_travel_date == date(2026, 6, 21)
    assert booking.active_traveler_count == 2
    assert booking.last_email_received_at == raw_email.received_at

    second_output = StringIO()
    call_command("repair_parsed_booking_display_fields", stdout=second_output)
    assert "scanned=1 repaired=0" in second_output.getvalue()


@pytest.mark.django_db
def test_repair_command_resolves_product_mismatch_after_alias_seed():
    raw_email = RawEmail.objects.create(
        gmail_message_id="repair-product-mismatch-1",
        gmail_thread_id="thread-repair-product",
        gmail_outer_sender="bookings@viator.com",
        subject="Viator booking BR-123456789 confirmed",
        received_at=timezone.now(),
        body_text=fixture("viator_new.txt"),
        parse_status=RawEmail.ParseStatus.NEEDS_REVIEW,
    )
    provider = Provider.objects.create(
        name="Viator", code="viator", parser_key="viator"
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="BR-123456789",
        status=Booking.Status.MANUAL_REVIEW,
        raw_product_name="Evening Bosphorus Cruise",
    )
    review = ReviewQueueItem.objects.create(
        raw_email=raw_email,
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
        title="Product title is not mapped",
    )
    setup = create_activity_setup(
        provider_code="viator-seeded",
        provider_name="Viator",
        activity_name="Evening Bosphorus Cruise",
        raw_product_name="Evening Bosphorus Cruise",
        raw_option_name="Standard deck",
        start_time=time(19, 30),
    )
    setup["alias"].provider = provider
    setup["alias"].save(update_fields=["provider", "updated_at"])

    output = StringIO()
    call_command("repair_parsed_booking_display_fields", stdout=output)
    booking.refresh_from_db()
    raw_email.refresh_from_db()
    review.refresh_from_db()

    assert "scanned=1 repaired=1" in output.getvalue()
    assert booking.activity == setup["activity"]
    assert raw_email.parse_status == RawEmail.ParseStatus.PARSED
    assert review.status == ReviewQueueItem.Status.RESOLVED
