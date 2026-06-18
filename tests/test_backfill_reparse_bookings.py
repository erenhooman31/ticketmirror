from datetime import date, time
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.bookings.models import ActivityScheduleSlot, ProviderAlias
from apps.ingestion.models import RawEmail
from apps.ingestion.services import process_raw_email
from tests.helpers import create_activity_setup


def viator_body(
    *,
    reference="BR-BACKFILL-PAX",
    product_name="Synthetic Bosphorus Cruise",
    start_time="14:00",
    participants="7 adults, 1 child",
) -> str:
    return "\n".join(
        [
            f"Booking reference: {reference}",
            f"Tour Name: {product_name}",
            "Travel date: 2026-06-21",
            f"Tour Option: {start_time}",
            f"Participants: {participants}",
            "Lead traveler: Alex Sample",
        ]
    )


def create_viator_raw_email(
    *,
    message_id,
    reference="BR-BACKFILL-PAX",
    body=None,
    status=RawEmail.ParseStatus.PENDING,
):
    return RawEmail.objects.create(
        gmail_message_id=message_id,
        gmail_thread_id=f"thread-{message_id}",
        gmail_history_id=f"history-{message_id}",
        gmail_outer_sender="bookings@viator.example",
        subject=f"Viator booking {reference} confirmed",
        received_at=timezone.now(),
        body_text=body or viator_body(reference=reference),
        parse_status=status,
    )


def create_viator_setup(*, alias=True):
    return create_activity_setup(
        provider_code="viator",
        provider_name="Viator",
        activity_name="Synthetic Bosphorus Cruise",
        raw_product_name="Synthetic Bosphorus Cruise",
        raw_option_name="",
        start_time=time(14, 0),
        duration_minutes=120,
        service_date=date(2026, 6, 21),
        alias=alias,
    )


@pytest.mark.django_db
def test_backfill_reparse_corrects_legacy_viator_participant_count():
    create_viator_setup()
    raw_email = create_viator_raw_email(message_id="backfill-pax-1")
    booking = process_raw_email(raw_email.id)
    booking.provider_traveler_count = 7
    booking.active_traveler_count = 7
    booking.save(
        update_fields=[
            "provider_traveler_count",
            "active_traveler_count",
            "updated_at",
        ]
    )
    output = StringIO()

    call_command("backfill_reparse_bookings", "--apply", stdout=output)

    booking.refresh_from_db()
    assert booking.provider_traveler_count == 8
    assert booking.active_traveler_count == 8
    assert "processed=1" in output.getvalue()
    assert "changed_bookings=1" in output.getvalue()


@pytest.mark.django_db
def test_backfill_reparse_preserves_manual_override_field():
    create_viator_setup()
    raw_email = create_viator_raw_email(message_id="backfill-manual-1")
    booking = process_raw_email(raw_email.id)
    booking.provider_traveler_count = 7
    booking.active_traveler_count = 99
    booking.manual_override_fields = ["active_traveler_count"]
    booking.save(
        update_fields=[
            "provider_traveler_count",
            "active_traveler_count",
            "manual_override_fields",
            "updated_at",
        ]
    )

    call_command("backfill_reparse_bookings", "--apply", stdout=StringIO())

    booking.refresh_from_db()
    assert booking.provider_traveler_count == 8
    assert booking.active_traveler_count == 99
    assert booking.manual_override_fields == ["active_traveler_count"]


@pytest.mark.django_db
def test_backfill_reparse_is_idempotent_after_first_correction():
    create_viator_setup()
    raw_email = create_viator_raw_email(message_id="backfill-idempotent-1")
    booking = process_raw_email(raw_email.id)
    booking.provider_traveler_count = 7
    booking.active_traveler_count = 7
    booking.save(
        update_fields=[
            "provider_traveler_count",
            "active_traveler_count",
            "updated_at",
        ]
    )
    first_output = StringIO()
    second_output = StringIO()

    call_command("backfill_reparse_bookings", "--apply", stdout=first_output)
    call_command("backfill_reparse_bookings", "--apply", stdout=second_output)

    booking.refresh_from_db()
    assert booking.active_traveler_count == 8
    assert "changed_bookings=1" in first_output.getvalue()
    assert "changed_bookings=0" in second_output.getvalue()


@pytest.mark.django_db
def test_backfill_reparse_recategorizes_needs_review_email_that_now_maps():
    setup = create_viator_setup(alias=False)
    raw_email = create_viator_raw_email(
        message_id="backfill-needs-review-1",
        reference="BR-BACKFILL-MAP",
        body=viator_body(reference="BR-BACKFILL-MAP"),
    )
    booking = process_raw_email(raw_email.id)
    raw_email.refresh_from_db()
    assert raw_email.parse_status == RawEmail.ParseStatus.NEEDS_REVIEW
    assert booking.activity_id is None
    assert booking.schedule_slot_id is None

    ProviderAlias.objects.create(
        provider=setup["provider"],
        raw_product_name="Synthetic Bosphorus Cruise",
        raw_option_name="",
        provider_product_code="",
        provider_option_code="",
        linked_activity=setup["activity"],
        linked_schedule=setup["schedule"],
        linked_slot=setup["slot"],
        approved=True,
    )
    output = StringIO()

    call_command("backfill_reparse_bookings", "--apply", stdout=output)

    raw_email.refresh_from_db()
    booking.refresh_from_db()
    assert raw_email.parse_status == RawEmail.ParseStatus.PARSED
    assert booking.activity == setup["activity"]
    assert booking.schedule_slot == setup["slot"]
    assert booking.active_start_time == time(14, 0)
    assert booking.active_slot_type == ActivityScheduleSlot.SlotType.FIXED_TIME
    assert "changed_bookings=1" in output.getvalue()
