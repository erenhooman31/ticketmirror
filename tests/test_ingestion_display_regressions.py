from datetime import date, time
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from helpers import create_activity_setup

from apps.accounts.models import UserProfile
from apps.bookings.models import Booking, BookingEvent, Provider, ReviewQueueItem
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
@pytest.mark.parametrize(
    "subject",
    [
        (
            "💬 Сообщение к заказу на 19 июня 2026 "
            "«Босфорское путешествие на яхте с остановкой в Бебеке — "
            "в Стамбуле» · №6692715"
        ),
        "💬 Сообщение к заказу №6645992",
        "Напоминание: заказ №6645992 завтра",
        "Новый отзыв по заказу №6645992",
    ],
)
def test_russian_provider_non_booking_notifications_are_ignored(subject):
    raw_email = RawEmail.objects.create(
        gmail_message_id=f"tripster-noise-{abs(hash(subject))}",
        gmail_outer_sender="orders@experience.tripster.com",
        subject=subject,
        received_at=timezone.now(),
        body_text="Это сервисное уведомление по уже существующему заказу.",
    )

    result = process_raw_email(raw_email.id)
    raw_email.refresh_from_db()

    assert result is None
    assert raw_email.parse_status == RawEmail.ParseStatus.IGNORED
    assert ReviewQueueItem.objects.filter(raw_email=raw_email).count() == 0


@pytest.mark.django_db
def test_translated_tripster_message_notification_still_uses_original_text(monkeypatch):
    def fake_to_english(value):
        if "Сообщение к заказу" in value:
            return "Translated service notification without known keywords"
        if "Сообщение туриста" in value:
            return "Translated body without known keywords"
        return value

    monkeypatch.setattr("apps.ingestion.services.to_english", fake_to_english)
    raw_email = RawEmail.objects.create(
        gmail_message_id="translated-tripster-message",
        gmail_outer_sender="support@tripster.ru",
        subject=(
            "💬 Сообщение к заказу на 19 июня 2026 "
            "«Босфорское путешествие на яхте с остановкой в Бебеке — "
            "в Стамбуле» · №6692715"
        ),
        received_at=timezone.now(),
        body_text="Сообщение туриста по заказу №6692715",
    )

    result = process_raw_email(raw_email.id)
    raw_email.refresh_from_db()

    assert result is None
    assert raw_email.parse_status == RawEmail.ParseStatus.IGNORED
    assert ReviewQueueItem.objects.filter(raw_email=raw_email).count() == 0


@pytest.mark.django_db
def test_translated_english_tripster_message_notification_is_ignored():
    raw_email = RawEmail.objects.create(
        gmail_message_id="english-tripster-message",
        gmail_outer_sender="support@tripster.ru",
        subject=(
            "Message to order on June 19 2026 "
            '"Bosphorus voyage on a yacht with a stop in Bebek" No.6692715'
        ),
        received_at=timezone.now(),
        body_text="Message about order No.6692715",
    )

    result = process_raw_email(raw_email.id)
    raw_email.refresh_from_db()

    assert result is None
    assert raw_email.parse_status == RawEmail.ParseStatus.IGNORED
    assert ReviewQueueItem.objects.filter(raw_email=raw_email).count() == 0


@pytest.mark.django_db
def test_reprocess_tripster_message_notification_closes_old_review_items():
    provider = Provider.objects.create(
        name="Tripster",
        code="tripster",
        parser_key="tripster",
    )
    raw_email = RawEmail.objects.create(
        gmail_message_id="tripster-message-old-reviews",
        gmail_thread_id="thread-tripster-message-old-reviews",
        gmail_outer_sender="support@tripster.ru",
        subject=(
            "💬 Сообщение к заказу на 19 июня 2026 "
            "«Босфорское путешествие на яхте с остановкой в Бебеке — "
            "в Стамбуле» · №6692715"
        ),
        received_at=timezone.now(),
        body_text="Сообщение туриста по заказу №6692715",
        provider_detected=provider,
        parse_status=RawEmail.ParseStatus.NEEDS_REVIEW,
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="6692715",
        status=Booking.Status.CONFIRMED,
        raw_product_name="Bosphorus voyage on a yacht with a stop in Bebek",
        provider_travel_date=date(2026, 6, 19),
        provider_start_time=time(11, 30),
        provider_traveler_count=5,
        source_thread_id=raw_email.gmail_thread_id,
    )
    BookingEvent.objects.create(
        booking=booking,
        raw_email=raw_email,
        event_type=BookingEvent.EventType.EMAIL_UPDATE,
        source=BookingEvent.Source.EMAIL,
    )
    reviews = [
        ReviewQueueItem.objects.create(
            raw_email=raw_email,
            booking=booking,
            issue_type=issue_type,
            title=title,
        )
        for issue_type, title in [
            (ReviewQueueItem.IssueType.DATE_MISSING, "Booking date missing"),
            (ReviewQueueItem.IssueType.TIME_MISSING, "Booking time missing"),
            (
                ReviewQueueItem.IssueType.TRAVELER_COUNT_MISSING,
                "Traveler count missing",
            ),
            (ReviewQueueItem.IssueType.PRODUCT_MISMATCH, "Product title is not mapped"),
        ]
    ]

    result = process_raw_email(raw_email.id)
    raw_email.refresh_from_db()
    booking.refresh_from_db()

    assert result is None
    assert raw_email.parse_status == RawEmail.ParseStatus.IGNORED
    assert booking.status == Booking.Status.CANCELLED
    for review in reviews:
        review.refresh_from_db()
        assert review.status == ReviewQueueItem.Status.RESOLVED
    event = booking.events.filter(
        event_type=BookingEvent.EventType.CONFLICT_DETECTED,
        source=BookingEvent.Source.SYSTEM,
    ).latest("id")
    assert event.new_values["non_booking_reclassified"] is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("subject", "sender", "body_text"),
    [
        (
            "You have a new review on GetYourGuide - 259500 (Istanbul)",
            "supplier@getyourguide.example",
            "A customer left a review.",
        ),
        (
            "Re: GYG32L5NAVZZ - Question about the activity",
            "supplier@getyourguide.example",
            "Question about the activity for booking code GYG32L5NAVZZ.",
        ),
        (
            "GetYourGuide Ticket received - Ticket ID [#12345] - "
            "Question about the activity",
            "supplier@getyourguide.example",
            "Support ticket body.",
        ),
        (
            "GetYourGuide supplier digest",
            "news@sup.getyourguide.com",
            "Newsletter body.",
        ),
    ],
)
def test_getyourguide_service_notifications_are_ignored_before_reference_parsing(
    subject,
    sender,
    body_text,
):
    raw_email = RawEmail.objects.create(
        gmail_message_id=f"gyg-service-{abs(hash(subject))}",
        gmail_outer_sender=sender,
        subject=subject,
        received_at=timezone.now(),
        body_text=body_text,
    )

    result = process_raw_email(raw_email.id)
    raw_email.refresh_from_db()

    assert result is None
    assert raw_email.parse_status == RawEmail.ParseStatus.IGNORED
    assert "Ignored - not a booking" in raw_email.parse_error
    assert Booking.objects.count() == 0
    assert ReviewQueueItem.objects.filter(raw_email=raw_email).count() == 0


@pytest.mark.django_db
def test_tripster_order_without_customer_does_not_create_lead_missing_review():
    call_command("seed_bookeo_products")
    raw_email = RawEmail.objects.create(
        gmail_message_id="tripster-no-customer",
        gmail_outer_sender="orders@experience.tripster.com",
        subject=(
            "Новый заказ на 1 июля в 19:00 "
            "«Морская прогулка по Босфору с аудиогидом» · №6645994 · 2 человека"
        ),
        received_at=timezone.now(),
        body_text="\n".join(
            [
                "Новый заказ",
                "Экскурсия: Морская прогулка по Босфору с аудиогидом",
                "Дата: 1 июля 2026",
                "Время: 19:00",
            ]
        ),
    )

    booking = process_raw_email(raw_email.id)
    raw_email.refresh_from_db()

    assert booking is not None
    assert raw_email.parse_status == RawEmail.ParseStatus.PARSED
    assert booking.lead_traveler_name is None
    assert not ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.LEAD_TRAVELER_MISSING,
    ).exists()


@pytest.mark.django_db
def test_stale_review_sweep_resolves_obsolete_provider_review_idempotently():
    provider = Provider.objects.create(name="Viator", code="viator")
    raw_email = RawEmail.objects.create(
        gmail_message_id="stale-provider-review",
        gmail_outer_sender="bookings@viator.com",
        subject="Viator booking BR-STALE confirmed",
        received_at=timezone.now(),
        body_text=fixture("viator_new.txt"),
        provider_detected=provider,
        parse_status=RawEmail.ParseStatus.PARSED,
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="BR-STALE",
        status=Booking.Status.CONFIRMED,
    )
    review = ReviewQueueItem.objects.create(
        raw_email=raw_email,
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.PROVIDER_NOT_DETECTED,
        title="Provider not detected",
    )

    output = StringIO()
    call_command("resolve_stale_booking_reviews", stdout=output)
    review.refresh_from_db()

    assert "scanned=1 resolved=1 unchanged=0 failed=0" in output.getvalue()
    assert review.status == ReviewQueueItem.Status.RESOLVED

    second_output = StringIO()
    call_command("resolve_stale_booking_reviews", stdout=second_output)
    assert "scanned=0 resolved=0 unchanged=0 failed=0" in second_output.getvalue()


@pytest.mark.django_db
def test_stale_review_sweep_resolves_orphan_reference_review_from_raw_email_event():
    provider = Provider.objects.create(name="Klook", code="klook", parser_key="klook")
    raw_email = RawEmail.objects.create(
        gmail_message_id="stale-orphan-reference-review",
        gmail_outer_sender="noreply@klook.com",
        subject="Klook order confirmed - CRG348822",
        received_at=timezone.now(),
        body_text="Klook order confirmed",
        provider_detected=provider,
        parse_status=RawEmail.ParseStatus.PARSED,
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="CRG348822",
        status=Booking.Status.CONFIRMED,
    )
    BookingEvent.objects.create(
        booking=booking,
        raw_email=raw_email,
        event_type=BookingEvent.EventType.EMAIL_NEW_BOOKING,
        source=BookingEvent.Source.EMAIL,
    )
    review = ReviewQueueItem.objects.create(
        raw_email=raw_email,
        booking=None,
        issue_type=ReviewQueueItem.IssueType.REFERENCE_MISSING,
        title="Reference missing",
    )

    call_command("resolve_stale_booking_reviews", stdout=StringIO())
    review.refresh_from_db()

    assert review.status == ReviewQueueItem.Status.RESOLVED


@pytest.mark.django_db
def test_reprocessing_resolves_orphan_missing_review_for_repaired_booking():
    provider = Provider.objects.create(
        name="Viator",
        code="viator",
        parser_key="viator",
    )
    raw_email = RawEmail.objects.create(
        gmail_message_id="reprocess-orphan-missing-review",
        gmail_outer_sender="bookings@viator.com",
        subject="Viator booking BR-123456789 confirmed",
        received_at=timezone.now(),
        body_text=fixture("viator_new.txt"),
        parse_status=RawEmail.ParseStatus.NEEDS_REVIEW,
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="BR-123456789",
        status=Booking.Status.MANUAL_REVIEW,
    )
    review = ReviewQueueItem.objects.create(
        raw_email=raw_email,
        booking=None,
        issue_type=ReviewQueueItem.IssueType.DATE_MISSING,
        title="Booking date missing",
    )

    process_raw_email(raw_email.id)
    booking.refresh_from_db()
    review.refresh_from_db()

    assert booking.active_travel_date == date(2026, 6, 21)
    assert review.status == ReviewQueueItem.Status.RESOLVED
    assert review.resolved_at is not None


@pytest.mark.django_db
def test_stale_review_sweep_resolves_reference_review_for_ignored_raw_email():
    raw_email = RawEmail.objects.create(
        gmail_message_id="ignored-stale-reference-review",
        gmail_outer_sender="supplier@getyourguide.example",
        subject="Re: GYG32L5NAVZZ - Question about the activity",
        received_at=timezone.now(),
        body_text="Question about the activity for booking code GYG32L5NAVZZ.",
        parse_status=RawEmail.ParseStatus.IGNORED,
    )
    review = ReviewQueueItem.objects.create(
        raw_email=raw_email,
        booking=None,
        issue_type=ReviewQueueItem.IssueType.REFERENCE_MISSING,
        title="Reference missing",
    )

    call_command("resolve_stale_booking_reviews", stdout=StringIO())
    review.refresh_from_db()

    assert review.status == ReviewQueueItem.Status.RESOLVED


@pytest.mark.django_db
def test_stale_review_sweep_resolves_missing_reviews_from_provider_fields():
    provider = Provider.objects.create(name="Tripster", code="tripster")
    raw_email = RawEmail.objects.create(
        gmail_message_id="provider-only-missing-reviews",
        gmail_outer_sender="support@tripster.ru",
        subject="Tripster booking 6692715",
        received_at=timezone.now(),
        body_text="Synthetic body",
        provider_detected=provider,
        parse_status=RawEmail.ParseStatus.NEEDS_REVIEW,
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="6692715",
        status=Booking.Status.CONFIRMED,
        provider_travel_date=date(2026, 6, 19),
        provider_start_time=time(11, 30),
        provider_traveler_count=5,
    )
    BookingEvent.objects.create(
        booking=booking,
        raw_email=raw_email,
        event_type=BookingEvent.EventType.EMAIL_UPDATE,
        source=BookingEvent.Source.EMAIL,
    )
    reviews = [
        ReviewQueueItem.objects.create(
            raw_email=raw_email,
            booking=booking,
            issue_type=issue_type,
            title=title,
        )
        for issue_type, title in [
            (ReviewQueueItem.IssueType.DATE_MISSING, "Booking date missing"),
            (ReviewQueueItem.IssueType.TIME_MISSING, "Booking time missing"),
            (
                ReviewQueueItem.IssueType.TRAVELER_COUNT_MISSING,
                "Traveler count missing",
            ),
        ]
    ]

    call_command("resolve_stale_booking_reviews", stdout=StringIO())

    for review in reviews:
        review.refresh_from_db()
        assert review.status == ReviewQueueItem.Status.RESOLVED


@pytest.mark.django_db
def test_stale_review_sweep_resolves_obsolete_low_confidence_review():
    provider = Provider.objects.create(name="Tripster", code="tripster")
    raw_email = RawEmail.objects.create(
        gmail_message_id="obsolete-low-confidence",
        gmail_outer_sender="support@tripster.ru",
        subject="Tripster booking 6692715",
        received_at=timezone.now(),
        body_text="Synthetic body",
        provider_detected=provider,
        parse_status=RawEmail.ParseStatus.NEEDS_REVIEW,
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="6692715",
        status=Booking.Status.CONFIRMED,
        raw_product_name="Bosphorus voyage on a yacht with a stop in Bebek",
        provider_travel_date=date(2026, 6, 19),
        provider_start_time=time(11, 30),
        provider_traveler_count=5,
    )
    BookingEvent.objects.create(
        booking=booking,
        raw_email=raw_email,
        event_type=BookingEvent.EventType.EMAIL_UPDATE,
        source=BookingEvent.Source.EMAIL,
    )
    review = ReviewQueueItem.objects.create(
        raw_email=raw_email,
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.LOW_CONFIDENCE_PARSE,
        title="Low confidence parse",
    )

    call_command("resolve_stale_booking_reviews", stdout=StringIO())
    review.refresh_from_db()

    assert review.status == ReviewQueueItem.Status.RESOLVED


@pytest.mark.django_db
def test_stale_review_sweep_reclassifies_non_booking_email_and_cancels_false_booking():
    provider = Provider.objects.create(
        name="GetYourGuide",
        code="getyourguide",
        parser_key="getyourguide",
    )
    raw_email = RawEmail.objects.create(
        gmail_message_id="stale-gyg-question",
        gmail_thread_id="thread-stale-gyg-question",
        gmail_outer_sender="supplier@getyourguide.example",
        subject="Re: GYG32L5NAVZZ - Question about the activity",
        received_at=timezone.now(),
        body_text="Question about the activity for booking code GYG32L5NAVZZ.",
        provider_detected=provider,
        parse_status=RawEmail.ParseStatus.PARSED,
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="GYG32L5NAVZZ",
        status=Booking.Status.CONFIRMED,
        source_thread_id=raw_email.gmail_thread_id,
        last_email_received_at=raw_email.received_at,
    )
    BookingEvent.objects.create(
        booking=booking,
        raw_email=raw_email,
        event_type=BookingEvent.EventType.EMAIL_NEW_BOOKING,
        source=BookingEvent.Source.EMAIL,
    )
    review = ReviewQueueItem.objects.create(
        raw_email=raw_email,
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.LOW_CONFIDENCE_PARSE,
        title="Low confidence parse",
    )

    output = StringIO()
    call_command("resolve_stale_booking_reviews", stdout=output)
    raw_email.refresh_from_db()
    booking.refresh_from_db()
    review.refresh_from_db()

    assert raw_email.parse_status == RawEmail.ParseStatus.IGNORED
    assert review.status == ReviewQueueItem.Status.RESOLVED
    assert booking.status == Booking.Status.CANCELLED
    assert "raw_ignored=1" in output.getvalue()
    assert "raw_resolved_reviews=1" in output.getvalue()
    assert "cancelled_bookings=1" in output.getvalue()
    event = booking.events.filter(
        event_type=BookingEvent.EventType.CONFLICT_DETECTED,
        source=BookingEvent.Source.SYSTEM,
    ).latest("id")
    assert event.new_values["non_booking_reclassified"] is True


@pytest.mark.django_db
def test_reprocess_resolves_missing_reviews_when_manual_active_fields_stay_blank():
    setup = create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="Evening Bosphorus Cruise",
        raw_product_name="Evening Bosphorus Cruise",
        raw_option_name="Standard deck",
        start_time=time(19, 30),
    )
    raw_email = RawEmail.objects.create(
        gmail_message_id="manual-active-provider-fields",
        gmail_outer_sender="bookings@viator.com",
        subject="Viator booking BR-123456789 confirmed",
        received_at=timezone.now(),
        body_text=fixture("viator_new.txt"),
        provider_detected=setup["provider"],
        parse_status=RawEmail.ParseStatus.NEEDS_REVIEW,
    )
    booking = Booking.objects.create(
        provider=setup["provider"],
        provider_booking_reference="BR-123456789",
        status=Booking.Status.CONFIRMED,
        manual_override_fields=[
            "active_travel_date",
            "active_start_time",
            "active_traveler_count",
        ],
    )
    reviews = [
        ReviewQueueItem.objects.create(
            raw_email=raw_email,
            booking=booking,
            issue_type=issue_type,
            title=title,
        )
        for issue_type, title in [
            (ReviewQueueItem.IssueType.DATE_MISSING, "Booking date missing"),
            (ReviewQueueItem.IssueType.TIME_MISSING, "Booking time missing"),
            (
                ReviewQueueItem.IssueType.TRAVELER_COUNT_MISSING,
                "Traveler count missing",
            ),
        ]
    ]

    process_raw_email(raw_email.id)
    booking.refresh_from_db()

    assert booking.active_travel_date is None
    assert booking.active_start_time is None
    assert booking.active_traveler_count is None
    assert booking.provider_travel_date == date(2026, 6, 21)
    assert booking.provider_start_time == time(19, 30)
    assert booking.provider_traveler_count == 2
    for review in reviews:
        review.refresh_from_db()
        assert review.status == ReviewQueueItem.Status.RESOLVED


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
def test_inbox_does_not_show_raw_product_as_matched_product(client, users):
    provider = Provider.objects.create(name="Tripster", code="tripster")
    raw_email = RawEmail.objects.create(
        gmail_message_id="unmapped-product-inbox",
        gmail_outer_sender="support@tripster.ru",
        subject="Tripster booking 6692715",
        received_at=timezone.now(),
        body_text="Synthetic body",
        provider_detected=provider,
        parse_status=RawEmail.ParseStatus.NEEDS_REVIEW,
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="6692715",
        status=Booking.Status.CONFIRMED,
        raw_product_name="Bosphorus voyage on a yacht with a stop in Bebek",
    )
    BookingEvent.objects.create(
        booking=booking,
        raw_email=raw_email,
        event_type=BookingEvent.EventType.EMAIL_UPDATE,
        source=BookingEvent.Source.EMAIL,
    )
    ReviewQueueItem.objects.create(
        raw_email=raw_email,
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
        title="Product title is not mapped",
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("inbox"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Raw: Bosphorus voyage on a yacht with a stop in Bebek" in html
    assert "Matched: Missing mapped product" in html


@pytest.mark.django_db
def test_inbox_hides_ignored_raw_emails_without_open_issues(client, users):
    RawEmail.objects.create(
        gmail_message_id="ignored-tripster-message-inbox",
        gmail_outer_sender="support@tripster.ru",
        subject=(
            "💬 Сообщение к заказу на 19 июня 2026 "
            "«Босфорское путешествие на яхте с остановкой в Бебеке — "
            "в Стамбуле» · №6692715"
        ),
        received_at=timezone.now(),
        body_text="Сообщение туриста по заказу №6692715",
        parse_status=RawEmail.ParseStatus.IGNORED,
    )

    client.force_login(users["viewer"])
    response = client.get(reverse("inbox"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Сообщение к заказу" not in html


@pytest.mark.django_db
def test_inbox_filters_obsolete_issue_labels_before_status(client, users):
    provider = Provider.objects.create(name="Tripster", code="tripster")
    raw_email = RawEmail.objects.create(
        gmail_message_id="obsolete-inbox-issues",
        gmail_outer_sender="support@tripster.ru",
        subject="Tripster booking 6692715",
        received_at=timezone.now(),
        body_text="Synthetic body",
        provider_detected=provider,
        parse_status=RawEmail.ParseStatus.NEEDS_REVIEW,
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="6692715",
        status=Booking.Status.CONFIRMED,
        raw_product_name="Bosphorus voyage on a yacht with a stop in Bebek",
        provider_travel_date=date(2026, 6, 19),
        provider_start_time=time(11, 30),
        provider_traveler_count=5,
    )
    BookingEvent.objects.create(
        booking=booking,
        raw_email=raw_email,
        event_type=BookingEvent.EventType.EMAIL_UPDATE,
        source=BookingEvent.Source.EMAIL,
    )
    for issue_type, title in [
        (ReviewQueueItem.IssueType.DATE_MISSING, "Booking date missing"),
        (ReviewQueueItem.IssueType.TIME_MISSING, "Booking time missing"),
        (ReviewQueueItem.IssueType.TRAVELER_COUNT_MISSING, "Traveler count missing"),
        (ReviewQueueItem.IssueType.LOW_CONFIDENCE_PARSE, "Low confidence parse"),
    ]:
        ReviewQueueItem.objects.create(
            raw_email=raw_email,
            booking=booking,
            issue_type=issue_type,
            title=title,
        )

    client.force_login(users["viewer"])
    response = client.get(reverse("inbox"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "6692715" in html
    assert "Complete" in html
    assert "Date missing" not in html
    assert "Time missing" not in html
    assert "Traveler count missing" not in html
    assert "Low confidence parse" not in html


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
    call_command(
        "repair_parsed_booking_display_fields",
        "--status",
        RawEmail.ParseStatus.PARSED,
        stdout=first_output,
    )
    booking = Booking.objects.get(provider_booking_reference="BR-123456789")

    assert "scanned=1 repaired=1" in first_output.getvalue()
    assert booking.lead_traveler_name == "Alex Sample"
    assert booking.raw_product_name == "Evening Bosphorus Cruise"
    assert booking.active_travel_date == date(2026, 6, 21)
    assert booking.active_traveler_count == 2
    assert booking.last_email_received_at == raw_email.received_at

    second_output = StringIO()
    call_command(
        "repair_parsed_booking_display_fields",
        "--status",
        RawEmail.ParseStatus.PARSED,
        stdout=second_output,
    )
    assert "scanned=1 repaired=0" in second_output.getvalue()


@pytest.mark.django_db
def test_repair_command_marks_malformed_email_failed_and_continues(monkeypatch):
    RawEmail.objects.create(
        gmail_message_id="repair-bad-1",
        gmail_outer_sender="bookings@viator.com",
        subject="Viator booking BR-BAD confirmed",
        received_at=timezone.now(),
        body_text="Booking reference BR-BAD",
        parse_status=RawEmail.ParseStatus.PENDING,
    )
    RawEmail.objects.create(
        gmail_message_id="repair-review-1",
        gmail_outer_sender="sender@example.test",
        subject="Booking details",
        received_at=timezone.now(),
        body_text="A booking message without known OTA markers.",
        parse_status=RawEmail.ParseStatus.PENDING,
    )

    class BrokenParser:
        def parse(self, raw_email):
            raise ValueError("broken stored email")

    monkeypatch.setattr(
        "apps.ingestion.management.commands.repair_parsed_booking_display_fields.get_parser",
        lambda provider_code: BrokenParser() if provider_code == "viator" else None,
    )
    output = StringIO()

    call_command("repair_parsed_booking_display_fields", stdout=output)

    failed = RawEmail.objects.get(gmail_message_id="repair-bad-1")
    review = RawEmail.objects.get(gmail_message_id="repair-review-1")
    assert failed.parse_status == RawEmail.ParseStatus.FAILED
    assert "broken stored email" in failed.parse_error
    assert review.parse_status == RawEmail.ParseStatus.NEEDS_REVIEW
    assert "scanned=2" in output.getvalue()
    assert "failed=1" in output.getvalue()


@pytest.mark.django_db
def test_repair_command_default_scan_skips_parsed_status():
    RawEmail.objects.create(
        gmail_message_id="repair-parsed-skip-1",
        gmail_outer_sender="bookings@viator.com",
        subject="Viator booking BR-SKIP confirmed",
        received_at=timezone.now(),
        body_text=fixture("viator_new.txt"),
        parse_status=RawEmail.ParseStatus.PARSED,
    )
    RawEmail.objects.create(
        gmail_message_id="repair-pending-target-1",
        gmail_outer_sender="sender@example.test",
        subject="Booking details",
        received_at=timezone.now(),
        body_text="A booking message without known OTA markers.",
        parse_status=RawEmail.ParseStatus.PENDING,
    )
    output = StringIO()

    call_command("repair_parsed_booking_display_fields", stdout=output)

    assert "scanned=1" in output.getvalue()


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
