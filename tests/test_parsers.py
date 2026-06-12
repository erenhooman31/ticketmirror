from pathlib import Path

from apps.ingestion.parsers import detect_provider, parse_by_provider
from apps.ingestion.parsers.common import (
    EVENT_CANCELLATION,
    EVENT_REQUEST,
    EVENT_UPDATE,
    STATUS_CANCELLED,
    STATUS_MANUAL_REVIEW,
    extract_forwarded_headers,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "emails"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_detect_provider_uses_forwarded_sender_before_outer_sender():
    body = fixture("forwarded_viator.txt")

    provider_code, confidence = detect_provider(
        subject="Fwd: OTA booking",
        sender="owner@gmail.com",
        body_text=body,
    )

    assert provider_code == "viator"
    assert confidence >= 0.7


def test_extract_forwarded_headers():
    headers = extract_forwarded_headers(fixture("forwarded_viator.txt"))

    assert headers.sender == "bookings@viator.com"
    assert headers.subject == "Viator booking BR-FWD-42 confirmed"
    assert headers.date == "Wed, 17 Jun 2026 at 10:01"


def test_parse_viator_new_booking():
    parsed = parse_by_provider(
        "viator",
        "Viator booking BR-123456789 confirmed",
        "bookings@viator.com",
        fixture("viator_new.txt"),
    )

    assert parsed.provider_code == "viator"
    assert parsed.provider_booking_reference == "BR-123456789"
    assert parsed.raw_product_name == "Evening Bosphorus Cruise"
    assert parsed.raw_option_name == "Standard deck"
    assert parsed.travel_date.isoformat() == "2026-06-21"
    assert parsed.start_time.isoformat() == "19:30:00"
    assert parsed.traveler_count == 2
    assert parsed.confidence == 1
    assert parsed.warnings == []


def test_parse_getyourguide_update():
    parsed = parse_by_provider(
        "getyourguide",
        "GetYourGuide booking update",
        "supplier@getyourguide.com",
        fixture("getyourguide_update.txt"),
    )

    assert parsed.provider_booking_reference == "GYGABC12345"
    assert parsed.event_type == EVENT_UPDATE
    assert parsed.status == "modified"
    assert parsed.raw_product_name == "Old Town Walking Tour"
    assert parsed.traveler_count == 3


def test_parse_tiqets_cancellation():
    parsed = parse_by_provider(
        "tiqets",
        "Tiqets cancellation",
        "orders@tiqets.com",
        fixture("tiqets_cancellation.txt"),
    )

    assert parsed.provider_booking_reference == "987654321"
    assert parsed.event_type == EVENT_CANCELLATION
    assert parsed.status == STATUS_CANCELLED
    assert parsed.travel_date.isoformat() == "2026-06-23"


def test_parse_tripster_pending_request():
    parsed = parse_by_provider(
        "tripster",
        "Urgent Tripster request",
        "orders@tripster.com",
        fixture("tripster_request.txt"),
    )

    assert parsed.provider_booking_reference == "TS-555888"
    assert parsed.event_type == EVENT_REQUEST
    assert parsed.raw_product_name == "Theme Park Admission"
    assert parsed.traveler_count == 4


def test_parse_sputnik8_new_booking():
    parsed = parse_by_provider(
        "sputnik8",
        "New Sputnik8 order",
        "orders@sputnik8.com",
        fixture("sputnik8_new.txt"),
    )

    assert parsed.provider_booking_reference == "SP8-998877"
    assert parsed.raw_product_name == "Private City Excursion"
    assert parsed.slot_type == "private_group"
    assert parsed.meeting_point == "Main square information desk"
    assert parsed.special_requirements == "Wheelchair access requested"


def test_parse_direct_internal_booking():
    parsed = parse_by_provider(
        "direct",
        "Direct booking",
        "ops@example.com",
        fixture("direct_new.txt"),
    )

    assert parsed.provider_booking_reference == "DIR-2026-001"
    assert parsed.raw_product_name == "Custom Shore Excursion"
    assert parsed.travel_date.isoformat() == "2026-06-26"
    assert parsed.traveler_count == 6
    assert parsed.pickup_location == "Cruise port gate"


def test_klook_graceful_failure_for_missing_required_fields():
    parsed = parse_by_provider(
        "klook",
        "Klook activity notification",
        "noreply@klook.com",
        fixture("klook_missing.txt"),
    )

    assert parsed.provider_code == "klook"
    assert parsed.provider_booking_reference == ""
    assert parsed.status == STATUS_MANUAL_REVIEW
    assert "reference_missing" in parsed.warnings
    assert "travel_date_missing" in parsed.warnings
    assert "traveler_count_missing" in parsed.warnings
    assert "needs_review" in parsed.warnings
    assert parsed.confidence < 1
