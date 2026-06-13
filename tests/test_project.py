import pytest
from django.core.management import call_command
from django.db import IntegrityError
from helpers import create_activity_setup

from apps.accounts.models import UserProfile
from apps.bookings.models import (
    ActivitySchedule,
    ActivityScheduleSlot,
    Booking,
    BookingEvent,
    Provider,
    ProviderAlias,
    TourActivity,
)
from apps.ingestion.models import GmailSyncState, RawEmail


def test_django_check_passes():
    call_command("check")


@pytest.mark.django_db
def test_user_profile_role_helpers(django_user_model):
    user = django_user_model.objects.create_user(username="operator")

    assert user.profile.role == UserProfile.Role.VIEWER
    assert user.profile.is_viewer
    assert not user.profile.can_edit_bookings

    user.profile.role = UserProfile.Role.OPERATOR
    user.profile.save()

    assert user.profile.is_operator
    assert user.profile.can_edit_bookings


@pytest.mark.django_db
def test_booking_reference_is_unique_per_provider():
    provider = Provider.objects.create(name="Viator", code="viator")
    Booking.objects.create(provider=provider, provider_booking_reference="ABC123")

    with pytest.raises(IntegrityError):
        Booking.objects.create(provider=provider, provider_booking_reference="ABC123")


@pytest.mark.django_db
def test_booking_status_default_is_pending_provider_acceptance():
    provider = Provider.objects.create(name="Klook", code="klook")
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="KL-1",
    )

    assert booking.status == Booking.Status.PENDING_PROVIDER_ACCEPTANCE


@pytest.mark.django_db
def test_model_string_representations():
    setup = create_activity_setup(
        provider_code="getyourguide",
        provider_name="GetYourGuide",
        activity_name="Full-Day City Highlights Tour",
        schedule_name="Full day",
        slot_type=ActivityScheduleSlot.SlotType.FULL_DAY,
        raw_product_name="City Tour",
        raw_option_name="Full Day",
    )
    provider = setup["provider"]
    activity = setup["activity"]
    schedule = setup["schedule"]
    slot = setup["slot"]
    alias = setup["alias"]
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="GYG-1",
        activity=activity,
        schedule_slot=slot,
    )
    event = BookingEvent.objects.create(
        booking=booking,
        event_type=BookingEvent.EventType.EMAIL_NEW_BOOKING,
        source=BookingEvent.Source.EMAIL,
        new_values={"provider_booking_reference": "GYG-1"},
    )

    assert str(provider) == "GetYourGuide"
    assert str(activity) == "Full-Day City Highlights Tour"
    assert str(schedule) == "Full-Day City Highlights Tour - Full day"
    assert str(slot).endswith("09:00")
    assert str(alias) == "GetYourGuide: City Tour / Full Day"
    assert str(booking) == "getyourguide GYG-1"
    assert "email_new_booking" in str(event)


@pytest.mark.django_db
def test_provider_alias_unique_constraint():
    setup = create_activity_setup(
        provider_code="tiqets",
        provider_name="Tiqets",
        activity_name="Museum Timed Entry",
        raw_product_name="Museum",
        raw_option_name="Timed",
    )
    provider = setup["provider"]
    activity = setup["activity"]

    with pytest.raises(IntegrityError):
        ProviderAlias.objects.create(
            provider=provider,
            raw_product_name="Museum",
            raw_option_name="Timed",
            provider_product_code="",
            provider_option_code="",
            linked_activity=activity,
        )


@pytest.mark.django_db
def test_ingestion_string_representations():
    provider = Provider.objects.create(name="Direct", code="direct")
    raw_email = RawEmail.objects.create(
        gmail_message_id="msg-1",
        gmail_outer_sender="ops@example.com",
        subject="New direct booking",
        received_at="2026-01-01T10:00:00Z",
        body_text="Booking reference D-1",
        provider_detected=provider,
    )
    sync_state = GmailSyncState.objects.create(mailbox_email="bookings@example.com")

    assert str(raw_email) == "New direct booking (msg-1)"
    assert str(sync_state) == "bookings@example.com"


@pytest.mark.django_db
def test_seed_defaults_creates_providers_and_bookeo_activities():
    call_command("seed_defaults")

    assert Provider.objects.filter(code="getyourguide").exists()
    assert Provider.objects.filter(code="viator").exists()
    assert TourActivity.objects.filter(name="gyg yacht").exists()
    assert ActivitySchedule.objects.filter(
        activity__name="1 Hours Bosphorus Tour GYG",
        schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
    ).exists()
