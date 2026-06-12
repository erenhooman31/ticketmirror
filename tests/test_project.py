import pytest
from django.core.management import call_command

from apps.accounts.models import UserProfile
from apps.bookings.models import Booking, BookingEvent, Provider


def test_django_check_passes():
    call_command("check")


@pytest.mark.django_db
def test_user_profile_is_created(django_user_model):
    user = django_user_model.objects.create_user(username="operator")

    assert user.profile.role == UserProfile.Role.VIEWER


@pytest.mark.django_db
def test_booking_reference_is_unique_per_provider():
    provider = Provider.objects.create(name="Viator", code="viator")
    Booking.objects.create(provider=provider, provider_reference="ABC123")

    assert (
        Booking.objects.filter(provider=provider, provider_reference="ABC123").count()
        == 1
    )


@pytest.mark.django_db
def test_booking_event_can_audit_provider_update():
    provider = Provider.objects.create(name="Klook", code="klook")
    booking = Booking.objects.create(provider=provider, provider_reference="KL-1")
    event = BookingEvent.objects.create(
        booking=booking,
        event_type=BookingEvent.EventType.PROVIDER_UPDATE,
        message="Updated from incoming email.",
    )

    assert event.booking == booking
