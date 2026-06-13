from datetime import date, time

import pytest
from django.contrib.admin.sites import AdminSite
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.bookings.admin import BookingAdmin
from apps.bookings.models import (
    Booking,
    BookingEvent,
    Product,
    ProductAlias,
    ProductVariant,
    Provider,
    ReviewQueueItem,
)
from apps.core.privacy import mask_contact_text


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
    admin = django_user_model.objects.create_superuser(
        username="admin",
        email="admin@example.test",
        password="password",
    )
    return {"viewer": viewer, "operator": operator, "admin": admin}


@pytest.fixture
def booking_setup():
    provider = Provider.objects.create(name="Viator", code="viator")
    product = Product.objects.create(canonical_name="City Tour")
    variant = ProductVariant.objects.create(
        product=product,
        variant_name="Morning",
        slot_type=ProductVariant.SlotType.FIXED_TIME,
    )
    booking = Booking.objects.create(
        provider=provider,
        provider_booking_reference="BR-SEARCH-1",
        provider_order_reference="ORDER-1",
        status=Booking.Status.CONFIRMED,
        canonical_product=product,
        canonical_variant=variant,
        raw_product_name="Raw City Walk",
        active_travel_date=date(2026, 6, 21),
        active_start_time=time(9, 0),
        active_slot_type=ProductVariant.SlotType.FIXED_TIME,
        active_traveler_count=2,
        lead_traveler_name="Alex Search",
        lead_traveler_phone="+1 555 123 4567",
        lead_traveler_email="alex.search@example.test",
    )
    alias = ProductAlias.objects.create(
        provider=provider,
        raw_product_name="Raw City Walk",
        raw_option_name="Morning",
        canonical_product=product,
        canonical_variant=variant,
        approved=False,
    )
    return {
        "provider": provider,
        "product": product,
        "variant": variant,
        "booking": booking,
        "alias": alias,
    }


@pytest.mark.django_db
def test_internal_pages_require_login(client, booking_setup):
    urls = [
        reverse("core:dashboard"),
        reverse("core:search"),
        reverse("bookings:daily"),
        reverse("bookings:detail", args=[booking_setup["booking"].id]),
        reverse("review_queue"),
        reverse("reports:index"),
    ]

    for url in urls:
        response = client.get(url)
        assert response.status_code == 302
        assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_viewer_is_read_only_for_mutation_views(client, users, booking_setup):
    client.force_login(users["viewer"])

    edit_response = client.get(
        reverse("bookings:edit", args=[booking_setup["booking"].id])
    )
    review_item = ReviewQueueItem.objects.create(
        booking=booking_setup["booking"],
        issue_type=ReviewQueueItem.IssueType.LOW_CONFIDENCE_PARSE,
        title="Check",
    )
    review_response = client.post(
        reverse("review_action", args=[review_item.id]),
        {"action": "resolve"},
    )
    alias_response = client.post(
        reverse("approve_alias", args=[booking_setup["alias"].id])
    )
    alias_create_response = client.post(
        reverse("product_aliases"),
        {
            "provider": booking_setup["provider"].id,
            "raw_product_name": "Other",
            "canonical_product": booking_setup["product"].id,
            "canonical_variant": booking_setup["variant"].id,
            "confidence": "1",
        },
    )

    assert edit_response.status_code == 403
    assert review_response.status_code == 403
    assert alias_response.status_code == 403
    assert alias_create_response.status_code == 403


@pytest.mark.django_db
def test_viewer_can_read_aliases_without_form_actions(client, users, booking_setup):
    client.force_login(users["viewer"])

    response = client.get(reverse("product_aliases"))

    assert response.status_code == 200
    assert b"Raw City Walk" in response.content
    assert b"Save alias" not in response.content
    assert b"btn-outline-success" not in response.content


@pytest.mark.django_db
def test_operator_manual_edit_audits_old_and_new_values(client, users, booking_setup):
    booking = booking_setup["booking"]
    client.force_login(users["operator"])

    response = client.post(
        reverse("bookings:edit", args=[booking.id]),
        {
            "status": Booking.Status.CONFIRMED,
            "active_travel_date": "2026-06-21",
            "active_start_time": "09:00",
            "active_end_time": "",
            "active_slot_type": ProductVariant.SlotType.FIXED_TIME,
            "active_traveler_count": "4",
            "lead_traveler_name": "Alex Search",
            "lead_traveler_email": "alex.search@example.test",
            "lead_traveler_phone": "+1 555 123 4567",
            "traveler_names": "[]",
            "ticket_breakdown": "{}",
            "language": "",
            "pickup_location": "",
            "meeting_point": "",
            "special_requirements": "",
            "customer_message": "",
            "price": "{}",
            "payment_status": "",
            "reason": "Capacity correction",
        },
    )

    assert response.status_code == 302
    event = BookingEvent.objects.get(
        booking=booking,
        event_type=BookingEvent.EventType.MANUAL_EDIT,
    )
    assert event.old_values["active_traveler_count"] == "2"
    assert event.new_values["active_traveler_count"] == "4"
    assert event.new_values["reason"] == "Capacity correction"
    assert event.created_by == users["operator"]


@pytest.mark.django_db
def test_status_only_change_uses_status_audit_event(client, users, booking_setup):
    booking = booking_setup["booking"]
    client.force_login(users["operator"])

    response = client.post(
        reverse("bookings:edit", args=[booking.id]),
        {
            "status": Booking.Status.CANCELLED,
            "active_travel_date": "2026-06-21",
            "active_start_time": "09:00",
            "active_end_time": "",
            "active_slot_type": ProductVariant.SlotType.FIXED_TIME,
            "active_traveler_count": "2",
            "lead_traveler_name": "Alex Search",
            "lead_traveler_email": "alex.search@example.test",
            "lead_traveler_phone": "+1 555 123 4567",
            "traveler_names": "[]",
            "ticket_breakdown": "{}",
            "language": "",
            "pickup_location": "",
            "meeting_point": "",
            "special_requirements": "",
            "customer_message": "",
            "price": "{}",
            "payment_status": "",
            "reason": "Customer cancelled",
        },
    )

    assert response.status_code == 302
    event = BookingEvent.objects.get(
        booking=booking,
        event_type=BookingEvent.EventType.MANUAL_STATUS_CHANGE,
    )
    assert event.old_values["status"] == Booking.Status.CONFIRMED
    assert event.new_values["status"] == Booking.Status.CANCELLED


@pytest.mark.django_db
def test_alias_approval_is_audited(client, users, booking_setup):
    alias = booking_setup["alias"]
    client.force_login(users["operator"])

    response = client.post(reverse("approve_alias", args=[alias.id]))

    assert response.status_code == 302
    event = BookingEvent.objects.get(
        event_type=BookingEvent.EventType.PRODUCT_ALIAS_CHANGED
    )
    assert event.old_values["approved"] is False
    assert event.new_values["approved"] is True
    assert event.created_by == users["operator"]


@pytest.mark.django_db
def test_review_queue_resolution_stores_user_and_timestamp(
    client, users, booking_setup
):
    review_item = ReviewQueueItem.objects.create(
        booking=booking_setup["booking"],
        issue_type=ReviewQueueItem.IssueType.PROVIDER_NOT_DETECTED,
        title="Provider missing",
    )
    client.force_login(users["operator"])

    response = client.post(
        reverse("review_action", args=[review_item.id]),
        {"action": "ignore"},
    )
    review_item.refresh_from_db()

    assert response.status_code == 302
    assert review_item.status == ReviewQueueItem.Status.IGNORED
    assert review_item.resolved_by == users["operator"]
    assert review_item.resolved_at is not None
    assert review_item.resolved_at <= timezone.now()


@pytest.mark.django_db
def test_global_search_finds_supported_booking_fields(client, users, booking_setup):
    client.force_login(users["viewer"])

    for query in [
        "BR-SEARCH-1",
        "Alex Search",
        "555 123",
        "alex.search@example.test",
        "Viator",
        "Raw City",
    ]:
        response = client.get(reverse("core:search"), {"q": query})
        assert response.status_code == 200
        assert b"BR-SEARCH-1" in response.content


def test_contact_masking_removes_email_and_phone():
    masked = mask_contact_text(
        "Parser failed for alex.search@example.test at +1 555 123 4567"
    )

    assert "alex.search@example.test" not in masked
    assert "+1 555 123 4567" not in masked
    assert "example.test" in masked
    assert "4567" in masked


@pytest.mark.django_db
def test_admin_pages_smoke(client, users, booking_setup):
    client.force_login(users["admin"])

    for url in [
        reverse("admin:bookings_booking_changelist"),
        reverse("admin:bookings_product_changelist"),
        reverse("admin:bookings_productvariant_changelist"),
        reverse("admin:bookings_productalias_changelist"),
        reverse("admin:bookings_bookingevent_changelist"),
        reverse("admin:bookings_reviewqueueitem_changelist"),
        reverse("admin:ingestion_rawemail_changelist"),
    ]:
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
def test_booking_admin_provider_reference_readonly_after_creation(
    rf,
    users,
    booking_setup,
):
    request = rf.get("/")
    request.user = users["admin"]
    model_admin = BookingAdmin(Booking, AdminSite())

    add_fields = model_admin.get_readonly_fields(request, obj=None)
    change_fields = model_admin.get_readonly_fields(
        request,
        obj=booking_setup["booking"],
    )

    assert "provider" not in add_fields
    assert "provider_booking_reference" not in add_fields
    assert "provider" in change_fields
    assert "provider_booking_reference" in change_fields
