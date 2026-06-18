from datetime import date

import pytest
from django.core.management import call_command

from apps.bookings.models import Booking, BookingEvent, Provider, ReviewQueueItem
from apps.ingestion.bookeo_import import (
    BookeoHistoryImporter,
    JsonCheckpointStore,
    import_bookeo_booking,
)
from apps.ingestion.management.commands.import_bookeo_history import _bookeo_api_key


@pytest.fixture
def seeded_bookeo_catalog():
    call_command("seed_bookeo_products")


def bookeo_payload(**overrides):
    payload = {
        "bookingNumber": "2557606167491444",
        "productName": "2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR",
        "productId": "bookeo-product-1",
        "startTime": "2026-06-17T19:00:00+03:00",
        "endTime": "2026-06-17T21:00:00+03:00",
        "status": "confirmed",
        "participants": [
            {"name": "Alex Bookeo", "category": "adult", "number": 2},
            {"name": "Casey Bookeo", "category": "child", "number": 1},
        ],
        "customer": {
            "firstName": "Alex",
            "lastName": "Bookeo",
            "email": "alex.bookeo@example.test",
            "phone": "+1 555 010 2222",
            "language": "English",
        },
        "notes": (
            "Notes by Viator, please confirm at the pier. "
            "Booking reference: BR-1411335703"
        ),
    }
    payload.update(overrides)
    return payload


def test_bookeo_api_key_prefers_business_authorized_env(monkeypatch):
    monkeypatch.setenv("BOOKEO_API_KEY", "developer-key")
    monkeypatch.setenv("BBOKEO_AUTHORIZED_API", "business-authorized-key")

    assert _bookeo_api_key() == "business-authorized-key"


@pytest.mark.django_db
def test_import_bookeo_booking_maps_fields_and_raw_event(seeded_bookeo_catalog):
    outcome = import_bookeo_booking(bookeo_payload())

    booking = Booking.objects.get()
    event = booking.events.get()

    assert outcome.result == "created"
    assert booking.provider.code == "viator"
    assert booking.provider_booking_reference == "BR-1411335703"
    assert booking.provider_order_reference == "Bookeo 2557606167491444"
    assert booking.raw_product_name == (
        "2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR"
    )
    assert booking.activity.name == (
        "2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR"
    )
    assert booking.schedule_slot.start_time.strftime("%H:%M") == "19:00"
    assert booking.provider_travel_date.isoformat() == "2026-06-17"
    assert booking.provider_start_time.strftime("%H:%M") == "19:00"
    assert booking.provider_traveler_count == 3
    assert booking.active_traveler_count == 3
    assert booking.ticket_breakdown == {"adult": 2, "child": 1}
    assert booking.lead_traveler_name == "Alex Bookeo"
    assert booking.lead_traveler_email == "alex.bookeo@example.test"
    assert booking.language == "English"
    assert event.event_type == BookingEvent.EventType.BOOKEO_HISTORY_IMPORT
    assert event.source == BookingEvent.Source.SYSTEM
    assert event.new_values["raw_bookeo_payload"]["bookingNumber"] == (
        "2557606167491444"
    )


@pytest.mark.django_db
def test_import_bookeo_cancelled_booking_maps_status(seeded_bookeo_catalog):
    import_bookeo_booking(
        bookeo_payload(
            bookingNumber="BKG-CANCEL",
            status="cancelled",
            notes="",
        )
    )

    booking = Booking.objects.get(provider_booking_reference="BKG-CANCEL")

    assert booking.provider.code == "bookeo"
    assert booking.status == Booking.Status.CANCELLED


@pytest.mark.django_db
def test_import_bookeo_unmapped_product_creates_review(seeded_bookeo_catalog):
    outcome = import_bookeo_booking(
        bookeo_payload(
            bookingNumber="BKG-UNMAPPED",
            productName="Unmapped Bookeo Product",
            notes="",
        )
    )

    booking = Booking.objects.get(provider_booking_reference="BKG-UNMAPPED")

    assert outcome.unmapped is True
    assert booking.activity is None
    assert ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
        status=ReviewQueueItem.Status.OPEN,
    ).exists()


@pytest.mark.django_db
def test_import_bookeo_booking_is_idempotent(seeded_bookeo_catalog):
    payload = bookeo_payload()

    first = import_bookeo_booking(payload)
    second = import_bookeo_booking(payload)

    assert first.result == "created"
    assert second.result == "skipped"
    assert Booking.objects.count() == 1
    assert BookingEvent.objects.count() == 1


@pytest.mark.django_db
def test_import_bookeo_dedups_existing_ota_email_booking(seeded_bookeo_catalog):
    provider = Provider.objects.get(code="viator")
    Booking.objects.create(
        provider=provider,
        provider_booking_reference="BR-1411335703",
        lead_traveler_name="Email Name",
    )

    outcome = import_bookeo_booking(bookeo_payload())
    booking = Booking.objects.get()

    assert outcome.result == "updated"
    assert Booking.objects.count() == 1
    assert booking.provider.code == "viator"
    assert booking.provider_booking_reference == "BR-1411335703"
    assert booking.provider_order_reference == "Bookeo 2557606167491444"
    assert booking.lead_traveler_name == "Alex Bookeo"


@pytest.mark.django_db
def test_import_bookeo_preserves_manual_override_fields(seeded_bookeo_catalog):
    provider = Provider.objects.get(code="viator")
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="BR-1411335703",
        active_traveler_count=99,
        manual_override_fields=["active_traveler_count"],
    )

    import_bookeo_booking(bookeo_payload())
    booking.refresh_from_db()

    assert booking.provider_traveler_count == 3
    assert booking.active_traveler_count == 99


@pytest.mark.django_db
def test_import_bookeo_dry_run_does_not_write(seeded_bookeo_catalog):
    outcome = import_bookeo_booking(bookeo_payload(), dry_run=True)

    assert outcome.result == "created"
    assert Booking.objects.count() == 0
    assert BookingEvent.objects.count() == 0


@pytest.mark.django_db
def test_import_bookeo_checkpoint_pagination(tmp_path, seeded_bookeo_catalog):
    client = FakeBookeoClient(
        [
            {
                "data": [bookeo_payload(bookingNumber="BKG-PAGE-1", notes="")],
                "info": {
                    "currentPage": 1,
                    "totalPages": 2,
                    "pageNavigationToken": "token-1",
                },
            },
            {
                "data": [bookeo_payload(bookingNumber="BKG-PAGE-2", notes="")],
                "info": {
                    "currentPage": 2,
                    "totalPages": 2,
                    "pageNavigationToken": "token-1",
                },
            },
        ]
    )
    state_file = tmp_path / "bookeo-state.json"
    importer = BookeoHistoryImporter(
        client=client,
        checkpoint_store=JsonCheckpointStore(state_file),
    )

    stats = importer.run(date_from=date(2026, 6, 1), date_to=date(2026, 6, 1))

    assert stats.fetched == 2
    assert Booking.objects.count() == 2
    assert client.calls[1]["page_navigation_token"] == "token-1"
    assert client.calls[1]["page_number"] == 2
    assert "2026-06-01:2026-06-01" in state_file.read_text(encoding="utf-8")


@pytest.mark.django_db
def test_import_bookeo_fetches_detail_for_thin_list_payload(
    tmp_path,
    seeded_bookeo_catalog,
):
    client = FakeBookeoClient(
        [
            {
                "data": [{"bookingNumber": "BKG-DETAIL", "customerId": "CUST-1"}],
                "info": {"currentPage": 1, "totalPages": 1},
            }
        ],
        details={"BKG-DETAIL": bookeo_payload(bookingNumber="BKG-DETAIL", notes="")},
    )
    importer = BookeoHistoryImporter(
        client=client,
        checkpoint_store=JsonCheckpointStore(tmp_path / "bookeo-state.json"),
    )

    importer.run(date_from=date(2026, 6, 1), date_to=date(2026, 6, 1))

    assert client.detail_calls == ["BKG-DETAIL"]
    assert Booking.objects.filter(provider_booking_reference="BKG-DETAIL").exists()


class FakeBookeoClient:
    def __init__(self, responses, details=None):
        self.responses = list(responses)
        self.details = details or {}
        self.calls = []
        self.detail_calls = []

    def list_bookings(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)

    def get_booking(self, booking_number):
        self.detail_calls.append(booking_number)
        if booking_number not in self.details:
            raise AssertionError(f"Unexpected detail fetch for {booking_number}")
        return self.details[booking_number]
