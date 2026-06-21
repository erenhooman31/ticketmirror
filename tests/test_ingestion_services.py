from datetime import date, time
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from helpers import create_activity_setup

from apps.bookings.display import product_label
from apps.bookings.models import (
    ActivitySchedule,
    ActivityScheduleSlot,
    Booking,
    BookingEvent,
    Provider,
    ProviderAlias,
    ReviewQueueItem,
    TourActivity,
)
from apps.bookings.services import get_daily_capacity_summary
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
    process_raw_email,
    upsert_booking_from_parsed,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "emails"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.fixture
def viator_provider():
    return Provider.objects.create(name="Viator", code="viator", parser_key="viator")


@pytest.fixture
def viator_alias():
    setup = create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="Evening Bosphorus Cruise",
        start_time=time(19, 30),
        duration_minutes=150,
        raw_product_name="Evening Bosphorus Cruise",
        raw_option_name="Standard deck",
    )
    return setup["alias"]


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
        "slot_type": ActivityScheduleSlot.SlotType.FIXED_TIME,
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


def bookeo_message(message_id="gmail-bookeo-1") -> dict:
    return {
        "gmail_message_id": message_id,
        "gmail_thread_id": "thread-bookeo-1",
        "gmail_history_id": "history-bookeo-1",
        "gmail_outer_sender": "noreply@bookeo.com",
        "subject": "New booking - Alex Bookeo",
        "received_at": timezone.now(),
        "body_text": fixture("bookeo_viator_new.txt"),
    }


def forwarded_payload(
    *,
    message_id: str,
    subject: str,
    forwarded_from: str,
    forwarded_subject: str,
    body: str = "",
) -> dict:
    return {
        "gmail_message_id": message_id,
        "gmail_thread_id": f"thread-{message_id}",
        "gmail_history_id": f"history-{message_id}",
        "gmail_outer_sender": "owner@gmail.com",
        "subject": f"Fwd: {subject}",
        "received_at": timezone.now(),
        "body_text": "\n".join(
            [
                "---------- Forwarded message ---------",
                f"From: {forwarded_from}",
                "Date: Wed, Jun 17, 2026 at 10:01 AM",
                f"Subject: {forwarded_subject}",
                "To: <ops@example.test>",
                "",
                body,
            ]
        ),
    }


def bookeo_body_without_ota_reference() -> str:
    return fixture("bookeo_viator_new.txt").replace(
        "Notes by Viator, please confirm at the pier. Booking reference: 1411335703",
        "Notes by operator: no OTA reference supplied yet.",
    )


def viator_same_booking_message(message_id="gmail-viator-same-1") -> dict:
    return {
        "gmail_message_id": message_id,
        "gmail_thread_id": "thread-viator-same-1",
        "gmail_history_id": "history-viator-same-1",
        "gmail_outer_sender": "bookings@viator.com",
        "subject": "Viator booking 1411335703 confirmed",
        "received_at": timezone.now(),
        "body_text": """
        Booking reference: 1411335703
        Tour Name: 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR
        Travel date: 2026-06-17
        Start time: 11:00
        Participants: 3
        Lead traveler: Alex Bookeo
        """,
    }


def getyourguide_sparse_cancellation(
    message_id="gmail-gyg-cancel-1",
    reference="GYG6H8ARWV5Y",
) -> dict:
    return {
        "gmail_message_id": message_id,
        "gmail_thread_id": "thread-gyg-cancel",
        "gmail_history_id": "history-gyg-cancel",
        "gmail_outer_sender": "supplier@getyourguide.example",
        "subject": f"A booking has been canceled - S259500 - {reference}",
        "received_at": timezone.now(),
        "body_text": "This booking has been canceled.",
    }


def getyourguide_new_message(
    message_id="gmail-gyg-new-1",
    reference="GYG6H8ARWV5Y",
) -> dict:
    body = fixture("real_getyourguide_new.txt").replace("GYGZXCVB1234", reference)
    return {
        "gmail_message_id": message_id,
        "gmail_thread_id": "thread-gyg-new",
        "gmail_history_id": "history-gyg-new",
        "gmail_outer_sender": "supplier@getyourguide.example",
        "subject": f"Urgent: New booking received - S259500 - {reference}",
        "received_at": timezone.now(),
        "body_text": body,
    }


@pytest.mark.django_db
@override_settings(TRANSLATE_ENABLED=True)
def test_process_raw_email_translates_before_provider_detection(monkeypatch):
    subject = "\u0411\u0440\u043e\u043d\u044c ALLE-RU-1"
    body = "\n".join(
        [
            "\u042d\u043a\u0441\u043a\u0443\u0440\u0441\u0438\u044f: "
            "\u0411\u043e\u0441\u0444\u043e\u0440",
            "\u0414\u0430\u0442\u0430: 2026-06-17",
            "\u0412\u0440\u0435\u043c\u044f: 14:00",
            "\u0423\u0447\u0430\u0441\u0442\u043d\u0438\u043a\u0438: 2",
            "\u041a\u043b\u0438\u0435\u043d\u0442: Tatyana K.",
        ]
    )
    translations = {
        subject: "Alle booking: ALLE-RU-1",
        body: "\n".join(
            [
                "Booking reference: ALLE-RU-1",
                "Product: Bosphorus Boat Cruise with Audio Guide",
                "Date: 2026-06-17",
                "Time: 14:00",
                "Participants: 2",
                "Customer: Tatyana K.",
            ]
        ),
    }
    monkeypatch.setattr(
        "apps.ingestion.translate._translate_text",
        lambda text: translations[text],
    )
    raw = RawEmail.objects.create(
        gmail_message_id="translated-before-detect",
        gmail_outer_sender="owner@gmail.com",
        subject=subject,
        received_at=timezone.now(),
        body_text=body,
    )

    booking = process_raw_email(raw.id)
    raw.refresh_from_db()

    assert booking is not None
    assert raw.provider_detected.code == "alle"
    assert raw.body_text == body
    assert booking.provider_booking_reference == "ALLE-RU-1"
    assert booking.provider_travel_date.isoformat() == "2026-06-17"
    assert booking.provider_start_time.isoformat() == "14:00:00"
    assert booking.provider_traveler_count == 2
    assert booking.lead_traveler_name == "Tatyana K."
    event = booking.events.latest("id")
    assert event.new_values["raw_fields"]["translation_applied"] is True
    assert event.new_values["raw_fields"]["original_subject"] == subject
    assert event.new_values["raw_fields"]["translated_subject"] == (
        "Alle booking: ALLE-RU-1"
    )


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
    assert booking.activity == viator_alias.linked_activity
    assert booking.schedule_slot == viator_alias.linked_slot
    assert booking.events.get().event_type == BookingEvent.EventType.EMAIL_NEW_BOOKING


@pytest.mark.django_db
def test_bookeo_and_direct_ota_messages_merge_on_underlying_reference():
    create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="Bosphorus Cruise",
        raw_product_name="2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR",
        raw_option_name="",
        start_time=time(11, 0),
        service_date=date(2026, 6, 17),
    )

    bookeo_raw = process_gmail_message(bookeo_message())
    direct_raw = process_gmail_message(viator_same_booking_message())
    booking = Booking.objects.get()

    assert bookeo_raw.parse_status == RawEmail.ParseStatus.PARSED
    assert direct_raw.parse_status == RawEmail.ParseStatus.PARSED
    assert booking.provider.code == "viator"
    assert booking.provider_booking_reference == "1411335703"
    assert booking.provider_order_reference == "Bookeo 2557606167491444"
    assert booking.provider_traveler_count == 3
    assert Booking.objects.count() == 1
    assert booking.events.count() == 2


@pytest.mark.django_db
def test_bookeo_without_ota_reference_still_creates_bookeo_booking():
    create_activity_setup(
        provider_code="bookeo",
        provider_name="Bookeo",
        activity_name="Bosphorus Cruise",
        raw_product_name="2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR",
        raw_option_name="",
        start_time=time(11, 0),
        service_date=date(2026, 6, 17),
    )
    payload = bookeo_message("gmail-bookeo-no-ota")
    payload["body_text"] = bookeo_body_without_ota_reference()

    raw = process_gmail_message(payload)
    booking = Booking.objects.get()

    assert raw.parse_status == RawEmail.ParseStatus.PARSED
    assert booking.provider.code == "bookeo"
    assert booking.provider_booking_reference == "2557606167491444"
    assert booking.provider_order_reference == "Bookeo 2557606167491444"
    assert booking.status == Booking.Status.CONFIRMED


@pytest.mark.django_db
def test_bookeo_without_ota_reference_merges_with_later_direct_ota_email():
    create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="Bosphorus Cruise",
        raw_product_name="2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR",
        raw_option_name="",
        start_time=time(11, 0),
        service_date=date(2026, 6, 17),
    )
    bookeo_payload = bookeo_message("gmail-bookeo-provisional")
    bookeo_payload["body_text"] = bookeo_body_without_ota_reference()
    process_gmail_message(bookeo_payload)

    direct_raw = process_gmail_message(viator_same_booking_message("gmail-direct-ota"))
    booking = Booking.objects.get()

    assert direct_raw.parse_status == RawEmail.ParseStatus.PARSED
    assert booking.provider.code == "viator"
    assert booking.provider_booking_reference == "1411335703"
    assert booking.provider_order_reference == "Bookeo 2557606167491444"
    assert Booking.objects.count() == 1
    assert booking.events.filter(new_values__cross_channel_identity_merge=True).exists()


@pytest.mark.django_db
def test_bookeo_cancellation_raw_email_updates_existing_booking():
    create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="Bosphorus Cruise",
        raw_product_name="2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR",
        raw_option_name="",
        start_time=time(11, 0),
        service_date=date(2026, 6, 17),
    )
    process_gmail_message(bookeo_message("gmail-bookeo-cancel-base"))
    cancel_payload = bookeo_message("gmail-bookeo-cancel")
    cancel_payload["subject"] = "Booking canceled - Alex Bookeo"

    process_gmail_message(cancel_payload)
    booking = Booking.objects.get()

    assert booking.status == Booking.Status.CANCELLED
    assert booking.events.filter(
        event_type=BookingEvent.EventType.EMAIL_CANCELLATION,
    ).exists()


@pytest.mark.django_db
def test_bookeo_change_raw_email_updates_existing_booking_fields():
    create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="Bosphorus Cruise",
        raw_product_name="2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR",
        raw_option_name="",
        start_time=time(11, 0),
        service_date=date(2026, 6, 17),
    )
    process_gmail_message(bookeo_message("gmail-bookeo-change-base"))
    change_payload = bookeo_message("gmail-bookeo-change")
    change_payload["subject"] = "Booking changed - Alex Bookeo"
    change_payload["body_text"] = fixture("bookeo_viator_new.txt").replace(
        "Participants: 3 adults",
        "Participants: 5 adults",
    )

    process_gmail_message(change_payload)
    booking = Booking.objects.get()

    assert booking.status == Booking.Status.MODIFIED
    assert booking.provider_traveler_count == 5
    assert booking.active_traveler_count == 5
    assert booking.events.filter(
        event_type=BookingEvent.EventType.EMAIL_UPDATE
    ).exists()


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
def test_getyourguide_sparse_cancellation_creates_no_missing_field_reviews():
    raw = process_gmail_message(getyourguide_sparse_cancellation())
    booking = Booking.objects.get(provider_booking_reference="GYG6H8ARWV5Y")

    assert raw.parse_status == RawEmail.ParseStatus.PARSED
    assert booking.status == Booking.Status.CANCELLED
    assert booking.events.filter(
        event_type=BookingEvent.EventType.EMAIL_CANCELLATION
    ).exists()
    missing_issue_types = {
        ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
        ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
        ReviewQueueItem.IssueType.DATE_MISSING,
        ReviewQueueItem.IssueType.TIME_MISSING,
        ReviewQueueItem.IssueType.TRAVELER_COUNT_MISSING,
        ReviewQueueItem.IssueType.LEAD_TRAVELER_MISSING,
        ReviewQueueItem.IssueType.LOW_CONFIDENCE_PARSE,
    }
    assert not ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type__in=missing_issue_types,
    ).exists()
    assert (
        ReviewQueueItem.objects.filter(
            booking=booking,
            issue_type=ReviewQueueItem.IssueType.CANCELLATION_WITHOUT_BOOKING,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_getyourguide_cancellation_first_converges_when_original_arrives_later():
    create_activity_setup(
        provider_code="getyourguide",
        provider_name="GetYourGuide",
        activity_name="GYG Yacht",
        raw_product_name="Istanbul: Luxury Yacht on Bosphorus",
        raw_option_name="",
        start_time=time(17, 0),
        service_date=date(2026, 4, 12),
    )
    process_gmail_message(
        getyourguide_sparse_cancellation(
            "gmail-gyg-cancel-before-original",
            "GYGLATER123",
        )
    )

    raw = process_gmail_message(getyourguide_new_message(reference="GYGLATER123"))
    booking = Booking.objects.get(provider_booking_reference="GYGLATER123")

    assert raw.parse_status == RawEmail.ParseStatus.PARSED
    assert booking.status == Booking.Status.CANCELLED
    assert booking.activity.name == "GYG Yacht"
    assert booking.schedule_slot.start_time == time(17, 0)
    assert booking.active_travel_date == date(2026, 4, 12)
    assert booking.active_traveler_count == 9
    assert Booking.objects.count() == 1
    assert not ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type__in=[
            ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
            ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
            ReviewQueueItem.IssueType.DATE_MISSING,
            ReviewQueueItem.IssueType.TIME_MISSING,
            ReviewQueueItem.IssueType.TRAVELER_COUNT_MISSING,
            ReviewQueueItem.IssueType.LEAD_TRAVELER_MISSING,
        ],
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("message_id", "subject", "forwarded_from", "forwarded_subject", "body"),
    [
        (
            "ignore-gyg-review",
            "Новый отзыв на вашу экскурсию (5/5)",
            "Sputnik team <gid@sputnik8.com>",
            "New review of your excursion (5/5)",
            "Natalia I. left a review for your tour.",
        ),
        (
            "ignore-sputnik-viewed",
            "Вашей экскурсией интересовались",
            "Oleg <message-1@example.messages.sputnik8.com>",
            (
                "Your excursion was viewed by: "
                "'Bosphorus boat trip with an audio guide', order 5353542"
            ),
            "Hello, Aziz!",
        ),
        (
            "ignore-sputnik-message",
            "Вам пришло сообщение",
            "Pantoni <message-2@messages.sputnik8.com>",
            (
                "You have received a message: "
                "'Bosphorus boat trip with an audio guide', order 5349622"
            ),
            "Please answer the tourist.",
        ),
        (
            "ignore-tripster-reminder",
            "Напоминание об экскурсии 19 июня",
            "Tripster <support@tripster.ru>",
            "Reminder about the excursion on June 19",
            (
                "Tour reminder. Unfortunately, there are no registered or paid "
                "participants."
            ),
        ),
        (
            "ignore-sputnik-updated-info",
            "Заказ №5351794, турист обновил информацию",
            "Sputnik team <gid@sputnik8.com>",
            "Заказ №5351794, турист обновил информацию",
            "Здравствуйте! Турист обновил данные по подтвержденному заказу.",
        ),
    ],
)
def test_process_raw_email_ignores_real_non_booking_notifications(
    message_id,
    subject,
    forwarded_from,
    forwarded_subject,
    body,
):
    raw = process_gmail_message(
        forwarded_payload(
            message_id=message_id,
            subject=subject,
            forwarded_from=forwarded_from,
            forwarded_subject=forwarded_subject,
            body=body,
        )
    )

    assert raw.parse_status == RawEmail.ParseStatus.IGNORED
    assert raw.parse_error.startswith("Ignored - not a booking")
    assert Booking.objects.count() == 0
    assert ReviewQueueItem.objects.count() == 0


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
def test_missing_provider_alias_creates_review_item(viator_provider):
    raw = raw_email(message_id="missing-alias")
    booking = upsert_booking_from_parsed(
        raw,
        parsed_booking(event_type=EVENT_NEW_BOOKING),
    )
    raw.refresh_from_db()

    assert booking is not None
    assert raw.parse_status == RawEmail.ParseStatus.NEEDS_REVIEW
    assert ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
    ).exists()
    assert ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
    ).exists()


@pytest.mark.django_db
def test_mapped_update_resolves_stale_product_reviews_for_booking(viator_provider):
    first_raw = raw_email(message_id="stale-product-review-first")
    booking = upsert_booking_from_parsed(
        first_raw,
        parsed_booking(event_type=EVENT_NEW_BOOKING),
    )
    stale_review = ReviewQueueItem.objects.get(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
    )
    activity = TourActivity.objects.create(
        name="Evening Bosphorus Cruise",
        internal_display_name="Evening Bosphorus Cruise",
        active=True,
    )
    schedule = ActivitySchedule.objects.create(
        activity=activity,
        schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
        name="Current schedule",
        active=True,
        priority=100,
    )
    slot = ActivityScheduleSlot.objects.create(
        schedule=schedule,
        start_time=time(19, 30),
        end_time=time(22, 0),
        duration_minutes=150,
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=80,
        active=True,
    )
    ProviderAlias.objects.create(
        provider=viator_provider,
        raw_product_name="Evening Bosphorus Cruise",
        raw_option_name="Standard deck",
        provider_product_code="",
        provider_option_code="",
        linked_activity=activity,
        linked_schedule=schedule,
        linked_slot=slot,
        approved=True,
    )

    second_raw = raw_email(message_id="stale-product-review-second")
    updated = upsert_booking_from_parsed(second_raw, parsed_booking())
    stale_review.refresh_from_db()
    rows = get_daily_capacity_summary(date(2026, 6, 21))
    slotted_row = next(row for row in rows if row["slot"] == slot)

    assert updated.id == booking.id
    assert stale_review.status == ReviewQueueItem.Status.RESOLVED
    assert slotted_row["active_pax"] == 2
    assert not ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
        status=ReviewQueueItem.Status.OPEN,
    ).exists()


@pytest.mark.django_db
def test_missing_booking_fields_create_specific_review_items(viator_provider):
    raw = raw_email(message_id="missing-fields")
    booking = upsert_booking_from_parsed(
        raw,
        parsed_booking(
            travel_date=None,
            start_time=None,
            slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
            traveler_count=None,
            lead_traveler_name="",
            confidence=0.6,
        ),
    )
    raw.refresh_from_db()

    assert booking is not None
    assert raw.parse_status == RawEmail.ParseStatus.NEEDS_REVIEW
    assert set(
        ReviewQueueItem.objects.filter(booking=booking).values_list(
            "issue_type",
            flat=True,
        )
    ) >= {
        ReviewQueueItem.IssueType.DATE_MISSING,
        ReviewQueueItem.IssueType.TIME_MISSING,
        ReviewQueueItem.IssueType.TRAVELER_COUNT_MISSING,
        ReviewQueueItem.IssueType.LEAD_TRAVELER_MISSING,
    }


@pytest.mark.django_db
def test_single_missing_field_does_not_force_manual_review_status(viator_alias):
    raw = raw_email(message_id="missing-lead-only")
    booking = upsert_booking_from_parsed(
        raw,
        parsed_booking(
            lead_traveler_name="",
            confidence=0.6,
            warnings=["lead_traveler_missing"],
        ),
    )
    raw.refresh_from_db()

    assert booking.status == Booking.Status.CONFIRMED
    assert raw.parse_status == RawEmail.ParseStatus.NEEDS_REVIEW
    assert ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.LOW_CONFIDENCE_PARSE,
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


@pytest.mark.django_db
def test_multi_time_product_resolves_schedule_slot_by_parsed_start_time():
    setup = create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="VIATOR 2H",
        raw_product_name="VIATOR 2H",
        raw_option_name="",
        start_time=time(11, 0),
        service_date=date(2026, 6, 21),
    )
    ActivityScheduleSlot.objects.create(
        schedule=setup["schedule"],
        start_time=time(14, 0),
        end_time=time(16, 0),
        duration_minutes=120,
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=10,
        active=True,
    )
    slot_1900 = ActivityScheduleSlot.objects.create(
        schedule=setup["schedule"],
        start_time=time(19, 0),
        end_time=time(21, 0),
        duration_minutes=120,
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=10,
        active=True,
    )

    booking = upsert_booking_from_parsed(
        raw_email(message_id="slot-by-time-1900"),
        parsed_booking(
            raw_product_name="VIATOR 2H",
            raw_option_name="",
            travel_date=date(2026, 6, 21),
            start_time=time(19, 0),
            end_time=time(21, 0),
            provider_booking_reference="BR-SLOT-1900",
        ),
    )

    assert booking.schedule_slot == slot_1900
    assert booking.active_start_time == time(19, 0)
    assert product_label(booking) == "VIATOR 2H - 19:00"
    rows = {
        row["slot"].start_time: row
        for row in get_daily_capacity_summary(date(2026, 6, 21))
        if row.get("slot")
    }
    assert rows[time(11, 0)]["active_pax"] == 0
    assert rows[time(19, 0)]["active_pax"] == 2


@pytest.mark.django_db
def test_unmatched_time_falls_back_to_alias_slot_and_flags_review():
    setup = create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="VIATOR 2H",
        raw_product_name="VIATOR 2H",
        raw_option_name="",
        start_time=time(11, 0),
        service_date=date(2026, 6, 21),
    )
    ActivityScheduleSlot.objects.create(
        schedule=setup["schedule"],
        start_time=time(19, 0),
        end_time=time(21, 0),
        duration_minutes=120,
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=10,
        active=True,
    )

    raw = raw_email(message_id="slot-by-time-missing")
    booking = upsert_booking_from_parsed(
        raw,
        parsed_booking(
            raw_product_name="VIATOR 2H",
            raw_option_name="",
            travel_date=date(2026, 6, 21),
            start_time=time(17, 0),
            provider_booking_reference="BR-SLOT-MISSING",
        ),
    )
    raw.refresh_from_db()

    assert booking.schedule_slot == setup["alias"].linked_slot
    assert booking.active_start_time == time(17, 0)
    assert raw.parse_status == RawEmail.ParseStatus.NEEDS_REVIEW
    assert ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.TIME_MISSING,
        title="Schedule slot needs confirmation",
    ).exists()


@pytest.mark.django_db
def test_single_slot_product_falls_back_without_slot_review():
    setup = create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="Single Slot Tour",
        raw_product_name="Single Slot Tour",
        raw_option_name="",
        start_time=time(11, 0),
        service_date=date(2026, 6, 21),
    )

    raw = raw_email(message_id="single-slot-fallback")
    booking = upsert_booking_from_parsed(
        raw,
        parsed_booking(
            raw_product_name="Single Slot Tour",
            raw_option_name="",
            travel_date=date(2026, 6, 21),
            start_time=time(19, 0),
            provider_booking_reference="BR-SINGLE-SLOT",
        ),
    )

    assert booking.schedule_slot == setup["slot"]
    assert not ReviewQueueItem.objects.filter(
        booking=booking,
        title="Schedule slot needs confirmation",
    ).exists()


@pytest.mark.django_db
def test_seeded_alias_uses_parsed_time_to_select_matching_slot():
    call_command("seed_bookeo_products")
    raw = raw_email(message_id="seeded-slot-time")

    booking = upsert_booking_from_parsed(
        raw,
        ParsedBooking(
            provider_code="viator",
            provider_booking_reference="BR-SEEDED-1900",
            event_type=EVENT_NEW_BOOKING,
            status=STATUS_CONFIRMED,
            raw_product_name="2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR",
            travel_date=date(2026, 6, 21),
            start_time=time(19, 0),
            slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
            traveler_count=2,
            lead_traveler_name="Alex Sample",
            confidence=1,
        ),
    )

    assert booking.schedule_slot.start_time == time(19, 0)
    assert booking.active_start_time == time(19, 0)


@pytest.mark.django_db
def test_seeded_audio_guide_alias_uses_parsed_time_for_1400_slot():
    call_command("seed_bookeo_products")
    raw = raw_email(provider_code="klook", message_id="audio-guide-slot-time")

    booking = upsert_booking_from_parsed(
        raw,
        ParsedBooking(
            provider_code="klook",
            provider_booking_reference="KL-AUDIO-1400",
            event_type=EVENT_NEW_BOOKING,
            status=STATUS_CONFIRMED,
            raw_product_name=(
                "Istanbul: Bosphorus Sightseeing Cruise Tour with Audio Guide"
            ),
            travel_date=date(2026, 6, 21),
            start_time=time(14, 0),
            slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
            traveler_count=2,
            lead_traveler_name="Alex Sample",
            confidence=1,
        ),
    )

    assert booking.activity.name == "GYG 2 Hours Bosphorus Tour SL-(2-3)"
    assert booking.schedule_slot.start_time == time(14, 0)
    assert booking.active_start_time == time(14, 0)
