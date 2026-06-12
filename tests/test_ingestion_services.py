from datetime import date, time
from pathlib import Path

import pytest
from django.utils import timezone

from apps.bookings.models import (
    Booking,
    BookingEvent,
    Product,
    ProductAlias,
    ProductVariant,
    Provider,
    ReviewQueueItem,
)
from apps.ingestion.models import RawEmail
from apps.ingestion.parsers.base import ParsedBooking
from apps.ingestion.parsers.common import (
    EVENT_CANCELLATION,
    EVENT_NEW_BOOKING,
    EVENT_UPDATE,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
)
from apps.ingestion.services import (
    process_gmail_message,
    upsert_booking_from_parsed,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "emails"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.fixture
def viator_provider():
    return Provider.objects.create(name="Viator", code="viator", parser_key="viator")


@pytest.fixture
def viator_alias(viator_provider):
    product = Product.objects.create(canonical_name="Evening Bosphorus Cruise")
    variant = ProductVariant.objects.create(
        product=product,
        variant_name="Standard deck",
        slot_type=ProductVariant.SlotType.FIXED_TIME,
        default_capacity=30,
    )
    return ProductAlias.objects.create(
        provider=viator_provider,
        raw_product_name="Evening Bosphorus Cruise",
        raw_option_name="Standard deck",
        canonical_product=product,
        canonical_variant=variant,
        approved=True,
    )


def raw_email(provider_code="viator", message_id="raw-1") -> RawEmail:
    return RawEmail.objects.create(
        gmail_message_id=message_id,
        gmail_outer_sender=f"bookings@{provider_code}.com",
        subject="Provider booking",
        received_at=timezone.now(),
        body_text="Synthetic body",
    )


def parsed_booking(**overrides) -> ParsedBooking:
    values = {
        "provider_code": "viator",
        "provider_booking_reference": "BR-123456789",
        "event_type": EVENT_UPDATE,
        "status": STATUS_CONFIRMED,
        "raw_product_name": "Evening Bosphorus Cruise",
        "raw_option_name": "Standard deck",
        "travel_date": date(2026, 6, 21),
        "start_time": time(19, 30),
        "end_time": time(22, 0),
        "slot_type": ProductVariant.SlotType.FIXED_TIME,
        "traveler_count": 2,
        "lead_traveler_name": "Alex Sample",
        "lead_traveler_email": "alex.sample@example.test",
        "lead_traveler_phone": "+1 555 010 1000",
        "confidence": 1,
    }
    values.update(overrides)
    return ParsedBooking(**values)


def viator_message(message_id="gmail-viator-1") -> dict:
    return {
        "gmail_message_id": message_id,
        "gmail_thread_id": "thread-1",
        "gmail_history_id": "history-1",
        "gmail_outer_sender": "bookings@viator.com",
        "subject": "Viator booking BR-123456789 confirmed",
        "received_at": timezone.now(),
        "body_text": fixture("viator_new.txt"),
    }


@pytest.mark.django_db
def test_process_gmail_message_creates_booking_and_event(viator_alias):
    raw = process_gmail_message(viator_message())
    booking = Booking.objects.get(provider_booking_reference="BR-123456789")

    assert raw.parse_status == RawEmail.ParseStatus.PARSED
    assert booking.provider.code == "viator"
    assert booking.provider_travel_date == date(2026, 6, 21)
    assert booking.active_travel_date == date(2026, 6, 21)
    assert booking.provider_traveler_count == 2
    assert booking.active_traveler_count == 2
    assert booking.canonical_product == viator_alias.canonical_product
    assert booking.events.get().event_type == BookingEvent.EventType.EMAIL_NEW_BOOKING


@pytest.mark.django_db
def test_duplicate_raw_email_is_ignored_after_first_processing(viator_alias):
    process_gmail_message(viator_message("duplicate-1"))
    process_gmail_message(viator_message("duplicate-1"))

    assert RawEmail.objects.filter(gmail_message_id="duplicate-1").count() == 1
    assert Booking.objects.count() == 1
    assert BookingEvent.objects.count() == 1


@pytest.mark.django_db
def test_update_email_updates_provider_and_active_fields(viator_alias):
    raw = process_gmail_message(viator_message("update-base"))
    booking = Booking.objects.get()

    update_raw = raw_email(message_id="update-raw")
    parsed = parsed_booking(traveler_count=4)
    updated = upsert_booking_from_parsed(update_raw, parsed)
    event = updated.events.order_by("-created_at").first()

    booking.refresh_from_db()
    assert booking.provider_traveler_count == 4
    assert booking.active_traveler_count == 4
    assert event.event_type == BookingEvent.EventType.EMAIL_UPDATE
    assert event.old_values["provider_traveler_count"] == 2
    assert event.new_values["changed_values"]["provider_traveler_count"] == 4
    assert raw.parse_status == RawEmail.ParseStatus.PARSED


@pytest.mark.django_db
def test_manual_override_prevents_active_field_overwrite(viator_alias):
    process_gmail_message(viator_message("manual-base"))
    booking = Booking.objects.get()
    booking.active_traveler_count = 2
    booking.manual_override_fields = ["active_traveler_count"]
    booking.save()

    update_raw = raw_email(message_id="manual-update")
    updated = upsert_booking_from_parsed(
        update_raw,
        parsed_booking(traveler_count=5),
    )

    updated.refresh_from_db()
    assert updated.provider_traveler_count == 5
    assert updated.active_traveler_count == 2
    assert ReviewQueueItem.objects.filter(
        booking=updated,
        issue_type=ReviewQueueItem.IssueType.MANUAL_OVERRIDE_CONFLICT,
    ).exists()
    assert updated.events.filter(
        event_type=BookingEvent.EventType.CONFLICT_DETECTED
    ).exists()


@pytest.mark.django_db
def test_cancellation_updates_booking_status(viator_alias):
    process_gmail_message(viator_message("cancel-base"))
    cancel_raw = raw_email(message_id="cancel-raw")

    booking = upsert_booking_from_parsed(
        cancel_raw,
        parsed_booking(
            event_type=EVENT_CANCELLATION,
            status=STATUS_CANCELLED,
        ),
    )

    booking.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED
    assert booking.events.filter(
        event_type=BookingEvent.EventType.EMAIL_CANCELLATION
    ).exists()


@pytest.mark.django_db
def test_missing_reference_creates_review_item_without_booking(viator_provider):
    raw = raw_email(message_id="missing-reference")
    result = upsert_booking_from_parsed(
        raw,
        parsed_booking(provider_booking_reference="", confidence=0.8),
    )
    raw.refresh_from_db()

    assert result is None
    assert raw.parse_status == RawEmail.ParseStatus.NEEDS_REVIEW
    assert Booking.objects.count() == 0
    assert ReviewQueueItem.objects.filter(
        raw_email=raw,
        issue_type=ReviewQueueItem.IssueType.REFERENCE_MISSING,
    ).exists()


@pytest.mark.django_db
def test_missing_product_alias_creates_review_item(viator_provider):
    booking = upsert_booking_from_parsed(
        raw_email(message_id="missing-alias"),
        parsed_booking(event_type=EVENT_NEW_BOOKING),
    )

    assert booking is not None
    assert ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.PRODUCT_ALIAS_MISSING,
    ).exists()


@pytest.mark.django_db
def test_capacity_impacting_traveler_count_update_is_audited(viator_alias):
    process_gmail_message(viator_message("audit-base"))
    booking = Booking.objects.get()

    upsert_booking_from_parsed(
        raw_email(message_id="audit-update"),
        parsed_booking(traveler_count=7),
    )
    event = booking.events.filter(event_type=BookingEvent.EventType.EMAIL_UPDATE).get()

    assert event.old_values["provider_traveler_count"] == 2
    assert event.new_values["changed_values"]["provider_traveler_count"] == 7
    assert event.new_values["changed_values"]["active_traveler_count"] == 7
