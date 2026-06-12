import pytest
from django.core.management import call_command
from django.db import IntegrityError

from apps.accounts.models import UserProfile
from apps.bookings.models import (
    Booking,
    BookingEvent,
    Product,
    ProductAlias,
    ProductVariant,
    Provider,
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
    provider = Provider.objects.create(name="GetYourGuide", code="getyourguide")
    product = Product.objects.create(
        canonical_name="Full-Day City Highlights Tour",
        category="city_tour",
    )
    variant = ProductVariant.objects.create(
        product=product,
        variant_name="Full day",
        slot_type=ProductVariant.SlotType.FULL_DAY,
    )
    alias = ProductAlias.objects.create(
        provider=provider,
        raw_product_name="City Tour",
        raw_option_name="Full Day",
        provider_product_code="P1",
        provider_option_code="O1",
        canonical_product=product,
        canonical_variant=variant,
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="GYG-1",
        canonical_product=product,
        canonical_variant=variant,
    )
    event = BookingEvent.objects.create(
        booking=booking,
        event_type=BookingEvent.EventType.EMAIL_NEW_BOOKING,
        source=BookingEvent.Source.EMAIL,
        new_values={"provider_booking_reference": "GYG-1"},
    )

    assert str(provider) == "GetYourGuide"
    assert str(product) == "Full-Day City Highlights Tour"
    assert str(variant) == "Full-Day City Highlights Tour - Full day"
    assert str(alias) == "GetYourGuide: City Tour / Full Day"
    assert str(booking) == "getyourguide GYG-1"
    assert "email_new_booking" in str(event)


@pytest.mark.django_db
def test_product_alias_unique_constraint():
    provider = Provider.objects.create(name="Tiqets", code="tiqets")
    product = Product.objects.create(canonical_name="Museum Timed Entry")
    ProductAlias.objects.create(
        provider=provider,
        raw_product_name="Museum",
        raw_option_name="Timed",
        provider_product_code="M1",
        provider_option_code="T1",
        canonical_product=product,
    )

    with pytest.raises(IntegrityError):
        ProductAlias.objects.create(
            provider=provider,
            raw_product_name="Museum",
            raw_option_name="Timed",
            provider_product_code="M1",
            provider_option_code="T1",
            canonical_product=product,
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
def test_seed_defaults_creates_providers_and_sample_products():
    call_command("seed_defaults")

    assert Provider.objects.filter(code="getyourguide").exists()
    assert Provider.objects.filter(code="direct").exists()
    assert Product.objects.filter(canonical_name="Museum Timed Entry").exists()
    assert ProductVariant.objects.filter(
        product__canonical_name="Half-Day Old Town Walk",
        variant_name="Morning",
    ).exists()
