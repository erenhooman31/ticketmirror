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


def test_detect_provider_rejects_spoofed_body_from_unknown_sender():
    provider_code, confidence = detect_provider(
        subject="Viator booking BR-SPOOF confirmed",
        sender="attacker@example.net",
        body_text="Viator\nBooking reference: BR-SPOOF\nTravelers: 2",
    )

    assert provider_code is None
    assert confidence == 0


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


def test_parse_realistic_getyourguide_new_booking():
    parsed = parse_by_provider(
        "getyourguide",
        "Urgent: New booking received - S259500 - GYGZXCVB1234",
        "supplier@getyourguide.example",
        fixture("real_getyourguide_new.txt"),
    )

    assert parsed.provider_booking_reference == "GYGZXCVB1234"
    assert parsed.raw_product_name == "Istanbul: Luxury Yacht on Bosphorus"
    assert parsed.travel_date.isoformat() == "2026-04-12"
    assert parsed.start_time.isoformat() == "17:00:00"
    assert parsed.traveler_count == 9
    assert parsed.lead_traveler_email == "alex.sample@example.test"
    assert parsed.lead_traveler_phone == "+1 555 010 1000"
    assert parsed.language == "English"


def test_parse_realistic_tiqets_new_booking():
    parsed = parse_by_provider(
        "tiqets",
        "Booking notification from Tiqets.com (order number: 1640917411)",
        "orders@tiqets.example",
        fixture("real_tiqets_new.txt"),
    )

    assert parsed.provider_booking_reference == "1640917411"
    assert parsed.provider_order_reference == "1640917411"
    assert (
        parsed.raw_product_name
        == "Istanbul: Guided Bosphorus Sightseeing Cruise + Audio Guide"
    )
    assert parsed.travel_date.isoformat() == "2026-06-12"
    assert parsed.start_time.isoformat() == "19:00:00"
    assert parsed.traveler_count == 4
    assert parsed.language == "French"


def test_parse_realistic_viator_pending_request():
    parsed = parse_by_provider(
        "viator",
        "URGENT Booking Request: Please Respond: Thu, Jun 04, 2026 (#BR-1406321057)",
        "notifications@viator.example",
        fixture("real_viator_request.txt"),
    )

    assert parsed.provider_booking_reference == "BR-1406321057"
    assert parsed.event_type == EVENT_REQUEST
    assert parsed.raw_product_name == "Istanbul Private Luxury Yacht on Bosphorus"
    assert parsed.raw_option_name == "2 Hours Yacht 20:00"
    assert parsed.provider_product_code == "307447P7"
    assert parsed.provider_option_code == "TG3~20:00"
    assert parsed.travel_date.isoformat() == "2026-06-04"
    assert parsed.start_time.isoformat() == "20:00:00"
    assert parsed.traveler_count == 4
    assert parsed.language == "Spanish - Audio"


def test_parse_realistic_viator_new_booking():
    parsed = parse_by_provider(
        "viator",
        "Action Required: New Booking for Sun, Apr 13, 2025 (BR-1247362085)",
        "notifications@viator.example",
        fixture("real_viator_new.txt"),
    )

    assert parsed.provider_booking_reference == "BR-1247362085"
    assert parsed.raw_product_name == "Guided Bosphorus Cruise Boat Tour In Istanbul"
    assert (
        parsed.raw_option_name == "Guided Bosphorus Cruise Boat Tour In Istanbul 10:00"
    )
    assert parsed.travel_date.isoformat() == "2025-04-13"
    assert parsed.start_time.isoformat() == "10:00:00"
    assert parsed.traveler_count == 2


def test_parse_realistic_tripster_russian_new_booking():
    subject = (
        "Новый заказ на 1 июля в 08:30 "
        "«Великолепный Стамбул в Европе и Азии» · №6645992"
    )
    parsed = parse_by_provider(
        "tripster",
        subject,
        "orders@experience.tripster.example",
        fixture("real_tripster_new_ru.txt"),
    )

    assert parsed.provider_booking_reference == "6645992"
    assert parsed.raw_product_name == "Великолепный Стамбул в Европе и Азии"
    assert parsed.travel_date.isoformat() == "2026-07-01"
    assert parsed.start_time.isoformat() == "08:30:00"
    assert parsed.traveler_count == 3
    assert parsed.lead_traveler_email == "alexey.ivanov@example.test"


def test_parse_realistic_sputnik8_russian_new_booking():
    subject = (
        "Новая бронь на экскурсию "
        "'Морская прогулка по Босфору с аудиогидом' "
        "на 12 апреля в 19:00 (воскресенье), заказ 5349319"
    )
    parsed = parse_by_provider(
        "sputnik8",
        subject,
        "orders@sputnik8.example",
        fixture("real_sputnik8_new_ru.txt"),
    )

    assert parsed.provider_booking_reference == "5349319"
    assert parsed.raw_product_name == "Морская прогулка по Босфору с аудиогидом"
    assert parsed.travel_date.isoformat() == "2026-04-12"
    assert parsed.start_time.isoformat() == "19:00:00"
    assert parsed.traveler_count == 2


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


def test_parse_alle_booking():
    body = """
    Booking reference: ALLE-2026-42
    Product: Bosphorus Sunset Cruise
    Option: Upper deck
    Travel date: 2026-06-27
    Start time: 18:30
    Travelers: 3
    Lead traveler: Aylin Example
    Email: aylin@example.test
    """

    parsed = parse_by_provider(
        "alle",
        "Alle booking ALLE-2026-42",
        "bookings@alletravel.example",
        body,
    )

    assert parsed.provider_booking_reference == "ALLE-2026-42"
    assert parsed.raw_product_name == "Bosphorus Sunset Cruise"
    assert parsed.travel_date.isoformat() == "2026-06-27"
    assert parsed.start_time.isoformat() == "18:30:00"
    assert parsed.traveler_count == 3


def test_parse_travel_experience_booking():
    body = """
    Booking reference: TE-2026-99
    Product: Istanbul Old City Tour
    Travel date: 2026-06-28
    Start time: 09:15
    Travelers: 2
    Lead traveler: Morgan Example
    """

    parsed = parse_by_provider(
        "travel-experience",
        "Travel Experience booking TE-2026-99",
        "ops@travel-experience.example",
        body,
    )

    assert parsed.provider_booking_reference == "TE-2026-99"
    assert parsed.raw_product_name == "Istanbul Old City Tour"
    assert parsed.travel_date.isoformat() == "2026-06-28"
    assert parsed.start_time.isoformat() == "09:15:00"
    assert parsed.traveler_count == 2


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
