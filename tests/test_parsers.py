from pathlib import Path

import pytest

from apps.ingestion.parsers import detect_provider, parse_by_provider
from apps.ingestion.parsers.common import (
    EVENT_CANCELLATION,
    EVENT_REQUEST,
    EVENT_UPDATE,
    STATUS_CANCELLED,
    STATUS_MANUAL_REVIEW,
    STATUS_MODIFIED,
    extract_forwarded_headers,
    infer_event_type,
    parse_date_flexible,
    status_for_event,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "emails"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


PROVIDER_EVENT_SAMPLES = {
    "viator": {
        "sender": "notifications@viator.example",
        "reference": "BR-EVENT-1",
        "reference_line": "Booking reference: BR-EVENT-1",
        "product_line": "Tour Name: Event Matrix Tour",
        "count_line": "Travelers: 2",
    },
    "klook": {
        "sender": "noreply@klook.example",
        "reference": "KL12345",
        "reference_line": "Booking ID: KL12345",
        "product_line": "Activity: Event Matrix Tour",
        "count_line": "Participants: 2",
    },
    "tiqets": {
        "sender": "orders@tiqets.example",
        "reference": "1234567",
        "reference_line": "Order ID: 1234567",
        "product_line": "Venue: Event Matrix Tour",
        "date_line": "Visit date: 2026-06-27",
        "count_line": "Tickets: 2",
    },
    "tripster": {
        "sender": "orders@tripster.example",
        "reference": "TS-EVENT-1",
        "reference_line": "Order number: TS-EVENT-1",
        "product_line": "Product: Event Matrix Tour",
        "date_line": "Date: 2026-06-27",
        "count_line": "Tickets: 2",
    },
    "sputnik8": {
        "sender": "orders@sputnik8.example",
        "reference": "SP8-EVENT-1",
        "reference_line": "Booking number: SP8-EVENT-1",
        "product_line": "Excursion: Event Matrix Tour",
        "count_line": "Participants: 2",
    },
    "alle": {
        "sender": "bookings@alletravel.example",
        "reference": "ALLE-EVENT-1",
        "reference_line": "Booking reference: ALLE-EVENT-1",
        "product_line": "Product: Event Matrix Tour",
        "count_line": "Travelers: 2",
    },
    "travel-experience": {
        "sender": "ops@travel-experience.example",
        "reference": "TE-EVENT-1",
        "reference_line": "Booking reference: TE-EVENT-1",
        "product_line": "Product: Event Matrix Tour",
        "count_line": "Travelers: 2",
    },
}


def event_matrix_body(sample: dict) -> str:
    return "\n".join(
        [
            sample["reference_line"],
            sample["product_line"],
            sample.get("date_line", "Travel date: 2026-06-27"),
            "Start time: 18:30",
            sample["count_line"],
            "Lead traveler: Event Sample",
            "Email: event.sample@example.test",
        ]
    )


def test_detect_provider_uses_forwarded_sender_before_outer_sender():
    body = fixture("forwarded_viator.txt")

    provider_code, confidence = detect_provider(
        subject="Fwd: OTA booking",
        sender="owner@gmail.com",
        body_text=body,
    )

    assert provider_code == "viator"
    assert confidence >= 0.7


def test_detect_provider_identifies_bookeo_notifications():
    body = fixture("bookeo_viator_new.txt")

    provider_code, confidence = detect_provider(
        subject="New booking - Alex Bookeo",
        sender="noreply@bookeo.com",
        body_text=body,
    )

    assert provider_code == "bookeo"
    assert confidence == 1


def test_detect_provider_rejects_spoofed_body_from_unknown_sender():
    provider_code, confidence = detect_provider(
        subject="Viator booking BR-SPOOF confirmed",
        sender="attacker@example.net",
        body_text="Booking reference: BR-SPOOF\nTravelers: 2",
    )

    assert provider_code is None
    assert confidence == 0


def test_detect_provider_allows_forwarded_tiqets_without_recovered_sender():
    provider_code, confidence = detect_provider(
        subject="Fwd: Booking notification from Tiqets.com (order number: 1640917411)",
        sender="owner@gmail.com",
        body_text=fixture("real_tiqets_new.txt"),
    )

    assert provider_code == "tiqets"
    assert confidence >= 0.5


def test_detect_provider_allows_forwarded_getyourguide_without_recovered_sender():
    provider_code, confidence = detect_provider(
        subject="Fwd: Urgent: New booking received - S259500 - GYGZXCVB1234",
        sender="owner@gmail.com",
        body_text=fixture("real_getyourguide_new.txt"),
    )

    assert provider_code == "getyourguide"
    assert confidence >= 0.5


def test_extract_forwarded_headers():
    headers = extract_forwarded_headers(fixture("forwarded_viator.txt"))

    assert headers.sender == "bookings@viator.com"
    assert headers.subject == "Viator booking BR-FWD-42 confirmed"
    assert headers.date == "Wed, 17 Jun 2026 at 10:01"


def test_extract_forwarded_headers_unfolds_gmail_wrapped_headers():
    headers = extract_forwarded_headers(fixture("real_sputnik8_calendar_forwarded.txt"))

    assert headers.sender == "gid@sputnik8.com"
    assert (
        headers.subject == "New reservation for the excursion "
        "'Bosphorus boat trip with an audio guide' for April 13 at 7:00 PM "
        "(Monday), order 5353542"
    )


@pytest.mark.parametrize("provider_code", sorted(PROVIDER_EVENT_SAMPLES))
@pytest.mark.parametrize(
    ("subject_prefix", "expected_event", "expected_status"),
    [
        ("New booking", "email_new_booking", "pending_provider_acceptance"),
        ("Booking update", EVENT_UPDATE, STATUS_MODIFIED),
        ("Booking cancellation", EVENT_CANCELLATION, STATUS_CANCELLED),
    ],
)
def test_direct_ota_parser_event_matrix(
    provider_code,
    subject_prefix,
    expected_event,
    expected_status,
):
    sample = PROVIDER_EVENT_SAMPLES[provider_code]

    parsed = parse_by_provider(
        provider_code,
        f"{subject_prefix} {sample['reference']}",
        sample["sender"],
        event_matrix_body(sample),
    )

    assert parsed.provider_booking_reference == sample["reference"]
    assert parsed.event_type == expected_event
    assert parsed.status == expected_status
    assert parsed.raw_product_name == "Event Matrix Tour"
    assert parsed.travel_date.isoformat() == "2026-06-27"
    assert parsed.traveler_count == 2


def test_shared_russian_date_parsing_for_labeled_values():
    assert parse_date_flexible("1 июля 2026").isoformat() == "2026-07-01"
    assert parse_date_flexible("Дата и время: 12 апреля 2026 в 19:00").isoformat() == (
        "2026-04-12"
    )
    assert parse_date_flexible("12.04.2026").isoformat() == "2026-04-12"


def test_shared_russian_event_and_status_detection():
    cancellation = infer_event_type(
        "Отмена заказа №6645992",
        "Бронирование отменено клиентом.",
    )
    update = infer_event_type(
        "Изменение заказа №6645992",
        "Изменилось время начала экскурсии.",
    )

    assert cancellation == EVENT_CANCELLATION
    assert status_for_event(cancellation, "отменено") == STATUS_CANCELLED
    assert update == EVENT_UPDATE
    assert status_for_event(update, "изменено") == STATUS_MODIFIED


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


def test_parse_viator_sums_labeled_participant_categories():
    parsed = parse_by_provider(
        "viator",
        "Viator booking BR-PAX-1 confirmed",
        "bookings@viator.example",
        "\n".join(
            [
                "Booking reference: BR-PAX-1",
                "Tour Name: Synthetic Bosphorus Cruise",
                "Travel date: 2026-06-21",
                "Tour Option: 14:00",
                "Participants: 7 adults , 1 child",
            ]
        ),
    )

    assert parsed.traveler_count == 8
    assert parsed.ticket_breakdown == {"adult": 7, "child": 1}


def test_parse_viator_sums_unlabeled_participant_categories():
    parsed = parse_by_provider(
        "viator",
        "Viator booking BR-PAX-2 confirmed",
        "bookings@viator.example",
        "\n".join(
            [
                "Booking reference: BR-PAX-2",
                "Tour Name: Synthetic Bosphorus Cruise",
                "Travel date: 2026-06-21",
                "Tour Option: 14:00",
                "Party size detail: 3 adults, 1 child, 1 infant",
            ]
        ),
    )

    assert parsed.traveler_count == 5
    assert parsed.ticket_breakdown == {"adult": 3, "child": 1, "infant": 1}


@pytest.mark.parametrize("count_line", ["Travelers: 4", "Participants: 4"])
def test_parse_viator_keeps_single_total_traveler_count(count_line):
    parsed = parse_by_provider(
        "viator",
        "Viator booking BR-PAX-3 confirmed",
        "bookings@viator.example",
        "\n".join(
            [
                "Booking reference: BR-PAX-3",
                "Tour Name: Synthetic Bosphorus Cruise",
                "Travel date: 2026-06-21",
                "Tour Option: 14:00",
                count_line,
            ]
        ),
    )

    assert parsed.traveler_count == 4
    assert parsed.ticket_breakdown == {}


def test_parse_viator_keeps_single_category_traveler_count():
    parsed = parse_by_provider(
        "viator",
        "Viator booking BR-PAX-4 confirmed",
        "bookings@viator.example",
        "\n".join(
            [
                "Booking reference: BR-PAX-4",
                "Tour Name: Synthetic Bosphorus Cruise",
                "Travel date: 2026-06-21",
                "Tour Option: 14:00",
                "Party size detail: 2 adults",
            ]
        ),
    )

    assert parsed.traveler_count == 2
    assert parsed.ticket_breakdown == {"adult": 2}


def test_parse_bookeo_notification_uses_underlying_ota_identity():
    parsed = parse_by_provider(
        "bookeo",
        "New booking - Alex Bookeo",
        "noreply@bookeo.com",
        fixture("bookeo_viator_new.txt"),
    )

    assert parsed.provider_code == "viator"
    assert parsed.provider_booking_reference == "1411335703"
    assert parsed.provider_order_reference == "Bookeo 2557606167491444"
    assert (
        parsed.raw_product_name
        == "2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR"
    )
    assert parsed.travel_date.isoformat() == "2026-06-17"
    assert parsed.start_time.isoformat() == "11:00:00"
    assert parsed.traveler_count == 3
    assert parsed.lead_traveler_name == "Alex Bookeo"
    assert parsed.lead_traveler_email == "alex.bookeo@example.test"
    assert parsed.lead_traveler_phone == "+1 555 010 2222"
    assert parsed.traveler_names == [
        "Alex Bookeo",
        "Casey Bookeo",
        "Jordan Bookeo",
    ]
    assert parsed.confidence == 1


def test_parse_bookeo_notification_falls_back_to_bookeo_booking_number():
    body = fixture("bookeo_viator_new.txt").replace(
        "Notes by Viator, please confirm at the pier. Booking reference: 1411335703",
        "Notes by operator: no OTA reference supplied yet.",
    )

    parsed = parse_by_provider(
        "bookeo",
        "New booking - Alex Bookeo",
        "noreply@bookeo.com",
        body,
    )

    assert parsed.provider_code == "bookeo"
    assert parsed.provider_booking_reference == "2557606167491444"
    assert parsed.provider_order_reference == "Bookeo 2557606167491444"
    assert parsed.status != STATUS_MANUAL_REVIEW
    assert "underlying_reference_missing" in parsed.warnings


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
    assert parsed.lead_traveler_name == "Alex Sample"
    assert parsed.lead_traveler_email == "alex.sample@example.test"
    assert parsed.lead_traveler_phone == "+1 555 010 1000"
    assert parsed.language == "English"


def test_parse_real_getyourguide_yacht_forwarded_booking():
    parsed = parse_by_provider(
        "getyourguide",
        "Fwd: Urgent: New booking received - S259500 - GYGKBGARYBZ5",
        "owner@gmail.com",
        fixture("real_getyourguide_yacht_forwarded.txt"),
    )

    assert parsed.provider_booking_reference == "GYGKBGARYBZ5"
    assert parsed.event_type == "email_new_booking"
    assert parsed.status == "confirmed"
    assert parsed.raw_product_name == "Istanbul: Luxury Yacht on Bosphorus"
    assert parsed.travel_date.isoformat() == "2026-06-15"
    assert parsed.start_time.isoformat() == "16:00:00"
    assert parsed.traveler_count == 6
    assert parsed.lead_traveler_name == "Yohan Muluka"
    assert parsed.language == "French"
    assert "travel_date_missing" not in parsed.warnings


def test_parse_real_getyourguide_forwarded_cancellation():
    parsed = parse_by_provider(
        "getyourguide",
        "Fwd: A booking has been canceled - S259500 - GYGZGZZX7RW7",
        "owner@gmail.com",
        fixture("real_getyourguide_cancel_forwarded.txt"),
    )

    assert parsed.provider_booking_reference == "GYGZGZZX7RW7"
    assert parsed.event_type == EVENT_CANCELLATION
    assert parsed.status == STATUS_CANCELLED
    assert (
        parsed.raw_product_name
        == "Istanbul: Bosphorus Sightseeing Cruise Tour with Audio Guide"
    )
    assert parsed.travel_date.isoformat() == "2026-06-21"
    assert parsed.start_time.isoformat() == "20:00:00"
    assert parsed.lead_traveler_name == "NAN ZHANG"


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
    assert parsed.lead_traveler_name == "Alex Sample"
    assert parsed.lead_traveler_phone == "+1 555 010 1001"


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


def test_parse_real_tripster_forwarded_new_order():
    parsed = parse_by_provider(
        "tripster",
        (
            'Fwd: Новый заказ на 17 июня в 14:00 "Морская прогулка по Босфору '
            'с аудиогидом" · №6686856'
        ),
        "owner@gmail.com",
        fixture("real_tripster_new_forwarded.txt"),
    )

    assert parsed.provider_booking_reference == "6686856"
    assert parsed.raw_product_name == "Bosphorus boat trip with audio guide"
    assert parsed.travel_date.isoformat() == "2026-06-17"
    assert parsed.start_time.isoformat() == "14:00:00"
    assert parsed.traveler_count == 2
    assert parsed.lead_traveler_name == "Tatyana K."
    assert parsed.ticket_breakdown == {"adult": 2}


def test_parse_tripster_flattened_russian_positional_body():
    subject = (
        "\u041d\u043e\u0432\u044b\u0439 \u0437\u0430\u043a\u0430\u0437 "
        "\u043d\u0430 17 \u0438\u044e\u043d\u044f 2026 "
        "\u0432 14:00 "
        "\u00ab\u041c\u043e\u0440\u0441\u043a\u0430\u044f "
        "\u043f\u0440\u043e\u0433\u0443\u043b\u043a\u0430 "
        "\u043f\u043e \u0411\u043e\u0441\u0444\u043e\u0440\u0443 "
        "\u0441 \u0430\u0443\u0434\u0438\u043e\u0433\u0438\u0434\u043e\u043c"
        "\u00bb \u00b7 \u21166686856"
    )
    body = (
        "\u0417\u0430\u043a\u0430\u0437 "
        "\u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441"
        "\u043a\u0438 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436"
        "\u0434\u0435\u043d. "
        "\u041d\u043e\u0432\u044b\u0439 \u0437\u0430\u043a\u0430\u0437 "
        "\u041d\u0430 17 \u0438\u044e\u043d\u044f \u0432 14:00 "
        "\u00ab\u041c\u043e\u0440\u0441\u043a\u0430\u044f "
        "\u043f\u0440\u043e\u0433\u0443\u043b\u043a\u0430 "
        "\u043f\u043e \u0411\u043e\u0441\u0444\u043e\u0440\u0443 "
        "\u0441 \u0430\u0443\u0434\u0438\u043e\u0433\u0438\u0434\u043e\u043c"
        "\u00bb, \u21166686856. "
        "\u0422\u0430\u0442\u044c\u044f\u043d\u0430 \u041a. "
        "\u041f\u0443\u0442\u0435\u0448\u0435\u0441\u0442\u0432\u0435"
        "\u043d\u043d\u0438\u043a 17 \u0438\u044e\u043d, "
        "\u0441\u0440 14:00\u201416:00 "
        "2 2 \u00b7 \u0421\u0442\u0430\u043d\u0434\u0430\u0440"
        "\u0442\u043d\u044b\u0439"
    )

    parsed = parse_by_provider(
        "tripster",
        subject,
        "orders@experience.tripster.com",
        body,
    )

    assert parsed.provider_booking_reference == "6686856"
    assert (
        parsed.raw_product_name == "\u041c\u043e\u0440\u0441\u043a\u0430\u044f "
        "\u043f\u0440\u043e\u0433\u0443\u043b\u043a\u0430 "
        "\u043f\u043e \u0411\u043e\u0441\u0444\u043e\u0440\u0443 "
        "\u0441 \u0430\u0443\u0434\u0438\u043e\u0433\u0438\u0434\u043e\u043c"
    )
    assert parsed.travel_date.isoformat() == "2026-06-17"
    assert parsed.start_time.isoformat() == "14:00:00"
    assert parsed.traveler_count == 2
    assert (
        parsed.lead_traveler_name
        == "\u0422\u0430\u0442\u044c\u044f\u043d\u0430 \u041a."
    )
    assert parsed.ticket_breakdown == {"adult": 2}


def test_parse_real_tripster_forwarded_cancellation_reason():
    parsed = parse_by_provider(
        "tripster",
        (
            "Fwd: Отменен заказ на 16 июня 2026 в 19:00 «Морская прогулка "
            "по Босфору с аудиогидом» · №6683974"
        ),
        "owner@gmail.com",
        fixture("real_tripster_cancel_forwarded.txt"),
    )

    assert parsed.provider_booking_reference == "6683974"
    assert parsed.event_type == EVENT_CANCELLATION
    assert parsed.status == STATUS_CANCELLED
    assert parsed.raw_product_name == "Морская прогулка по Босфору с аудиогидом"
    assert parsed.travel_date.isoformat() == "2026-06-16"
    assert parsed.start_time.isoformat() == "19:00:00"
    assert parsed.raw_fields["cancellation_reason"] == "организатор не выходит на связь"


def test_tripster_uses_subject_participant_count_when_body_omits_it():
    subject = (
        "Новый заказ на 1 июля в 08:30 "
        "«Морская прогулка по Босфору с аудиогидом» · №6645993 · 11 человек"
    )
    body = """
    Экскурсия: Морская прогулка по Босфору с аудиогидом
    Дата: 1 июля 2026
    Время: 08:30
    """

    parsed = parse_by_provider(
        "tripster",
        subject,
        "orders@experience.tripster.example",
        body,
    )

    assert parsed.provider_booking_reference == "6645993"
    assert parsed.traveler_count == 11
    assert parsed.ticket_breakdown == {"adult": 11}
    assert "traveler_count_missing" not in parsed.warnings


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
    assert parsed.ticket_breakdown == {"adult": 2}


def test_parse_real_sputnik8_forwarded_calendar_without_customer_false_positive():
    parsed = parse_by_provider(
        "sputnik8",
        (
            "Fwd: Новая бронь на экскурсию 'Морская прогулка по Босфору "
            "с аудиогидом' на 13 апреля в 19:00 (понедельник), заказ 5353542"
        ),
        "owner@gmail.com",
        fixture("real_sputnik8_calendar_forwarded.txt"),
    )

    assert parsed.provider_booking_reference == "5353542"
    assert parsed.raw_product_name == "Морская прогулка по Босфору с аудиогидом"
    assert parsed.travel_date.isoformat() == "2026-04-13"
    assert parsed.start_time.isoformat() == "19:00:00"
    assert parsed.traveler_count == 2
    assert parsed.lead_traveler_name is None
    assert parsed.lead_traveler_email is None
    assert parsed.lead_traveler_phone is None


def test_parse_tripster_russian_cancellation_is_not_new_booking():
    body = """
    Отмена заказа
    Экскурсия: Великолепный Стамбул в Европе и Азии
    Дата: 1 июля 2026
    Время: 08:30
    Участников: 3
    Тип билета: взрослый 2; ребёнок 1; младенец 1
    Стоимость: 1500 RUB
    Клиент: Алексей Иванов
    Телефон: +1 555 010 1002
    Электронная почта: alexey.ivanov@example.test
    """

    parsed = parse_by_provider(
        "tripster",
        "Отмена заказа №6645992",
        "orders@experience.tripster.example",
        body,
    )

    assert parsed.provider_booking_reference == "6645992"
    assert parsed.event_type == EVENT_CANCELLATION
    assert parsed.status == STATUS_CANCELLED
    assert parsed.travel_date.isoformat() == "2026-07-01"
    assert parsed.traveler_count == 3
    assert parsed.ticket_breakdown == {"adult": 2, "child": 1, "infant": 1}
    assert parsed.price == {"amount": "1500", "currency": "RUB"}


def test_parse_sputnik8_russian_update_status():
    body = """
    Изменение бронирования
    Экскурсия: Морская прогулка по Босфору
    Дата и время: 12 апреля 2026 в 19:00
    Участников: 2
    Имя: Alex Sample
    Телефон: +1 555 010 1003
    Email: alex.sample@example.test
    """

    parsed = parse_by_provider(
        "sputnik8",
        "Изменение заказа 5349319",
        "orders@sputnik8.example",
        body,
    )

    assert parsed.provider_booking_reference == "5349319"
    assert parsed.event_type == EVENT_UPDATE
    assert parsed.status == STATUS_MODIFIED
    assert parsed.travel_date.isoformat() == "2026-04-12"
    assert parsed.start_time.isoformat() == "19:00:00"


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


def test_parse_alle_russian_labels_and_event_words():
    product = (
        "\u041f\u0440\u043e\u0433\u0443\u043b\u043a\u0430 "
        "\u043f\u043e \u0411\u043e\u0441\u0444\u043e\u0440\u0443"
    )
    date_time_label = "\u0414\u0430\u0442\u0430 \u0438 \u0432\u0440\u0435\u043c\u044f"
    cancellation_subject = (
        "\u041e\u0442\u043c\u0435\u043d\u0430 "
        "\u0437\u0430\u043a\u0430\u0437\u0430 ALLE-RU-42"
    )
    body = "\n".join(
        [
            "Booking reference: ALLE-RU-42",
            f"\u042d\u043a\u0441\u043a\u0443\u0440\u0441\u0438\u044f: {product}",
            f"{date_time_label}: 12 "
            "\u0430\u043f\u0440\u0435\u043b\u044f 2026 \u0432 19:00",
            "\u0423\u0447\u0430\u0441\u0442\u043d\u0438\u043a\u043e\u0432: 3",
            "\u041a\u043b\u0438\u0435\u043d\u0442: "
            "\u0410\u043b\u0435\u043a\u0441\u0435\u0439 "
            "\u0418\u0432\u0430\u043d\u043e\u0432",
            "\u042f\u0437\u044b\u043a: Russian",
        ]
    )

    parsed = parse_by_provider(
        "alle",
        cancellation_subject,
        "bookings@alletravel.example",
        body,
    )

    assert parsed.provider_booking_reference == "ALLE-RU-42"
    assert parsed.event_type == EVENT_CANCELLATION
    assert parsed.status == STATUS_CANCELLED
    assert parsed.raw_product_name == product
    assert parsed.travel_date.isoformat() == "2026-04-12"
    assert parsed.start_time.isoformat() == "19:00:00"
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


def test_klook_order_confirmed_subject_extracts_reference_product_date_customer():
    subject = (
        "Klook order confirmed - Bosphorus Sunset Cruise - "
        "2026-06-28 18:30:00 - Riley Klook - CRG348822"
    )

    parsed = parse_by_provider(
        "klook",
        subject,
        "noreply@klook.com",
        "Klook order confirmed",
    )

    assert parsed.provider_booking_reference == "CRG348822"
    assert parsed.raw_product_name == "Bosphorus Sunset Cruise"
    assert parsed.travel_date.isoformat() == "2026-06-28"
    assert parsed.start_time.isoformat() == "18:30:00"
    assert parsed.lead_traveler_name == "Riley Klook"
    assert "reference_missing" not in parsed.warnings
