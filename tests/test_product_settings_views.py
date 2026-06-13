from datetime import date, time

import pytest
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.bookings.models import CapacityRule, Product, ProductVariant


@pytest.fixture
def users(django_user_model):
    viewer = django_user_model.objects.create_user(
        username="viewer-products",
        password="password",
    )
    operator = django_user_model.objects.create_user(
        username="operator-products",
        password="password",
    )
    admin = django_user_model.objects.create_user(
        username="admin-products",
        password="password",
    )
    operator.profile.role = UserProfile.Role.OPERATOR
    operator.profile.save()
    admin.profile.role = UserProfile.Role.ADMIN
    admin.profile.save()
    return {"viewer": viewer, "operator": operator, "admin": admin}


@pytest.mark.django_db
def test_product_settings_list_requires_login(client):
    response = client.get(reverse("settings_product_settings"))

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_admin_creates_product_general_settings(client, users):
    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_product_settings_new"),
        {
            "action": "save_general",
            "canonical_name": "Bosphorus Sightseeing Cruise",
            "nickname": "Bosphorus Cruise",
            "category": "Cruise",
            "active": "on",
            "notes": "Shown as a short operations label.",
        },
    )
    product = Product.objects.get(canonical_name="Bosphorus Sightseeing Cruise")

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "settings_product_settings_edit",
        args=[product.id],
    )
    assert product.nickname == "Bosphorus Cruise"
    assert product.category == "Cruise"


@pytest.mark.django_db
def test_schedule_save_creates_time_slot_variants_and_capacity_rules(client, users):
    product = Product.objects.create(
        canonical_name="Old City Tour",
        nickname="Old City",
        category="Walking",
    )

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_product_settings_edit", args=[product.id]),
        {
            "action": "save_schedule",
            "original_schedule_name": "Default season",
            "original_date_from": "",
            "original_date_to": "",
            "schedule_name": "Summer season",
            "date_from": "2026-04-01",
            "date_to": "2026-10-31",
            "duration_days": "0",
            "duration_hours": "2",
            "duration_minutes": "30",
            "default_capacity": "80",
            "monday": "10:00,80\n12:00,60",
            "tuesday": "10:00,80",
            "wednesday": "",
            "thursday": "",
            "friday": "",
            "saturday": "",
            "sunday": "14:00,50",
        },
    )

    assert response.status_code == 302
    assert ProductVariant.objects.filter(product=product).count() == 3
    assert (
        ProductVariant.objects.get(
            product=product,
            variant_name="10:00 fixed slot",
        ).duration_minutes
        == 150
    )
    assert (
        CapacityRule.objects.filter(
            product_variant__product=product,
            schedule_name="Summer season",
            date_from=date(2026, 4, 1),
            date_to=date(2026, 10, 31),
        ).count()
        == 4
    )
    assert CapacityRule.objects.filter(
        product_variant__product=product,
        day_of_week=0,
        slot_start_time=time(12, 0),
        capacity=60,
    ).exists()


@pytest.mark.django_db
def test_schedule_tab_renders_weekly_grid(client, users):
    product = Product.objects.create(canonical_name="Rendered Tour")
    variant = ProductVariant.objects.create(
        product=product,
        variant_name="09:00 fixed slot",
        slot_type=ProductVariant.SlotType.FIXED_TIME,
        duration_minutes=90,
        default_capacity=40,
    )
    CapacityRule.objects.create(
        product_variant=variant,
        schedule_name="Default season",
        day_of_week=0,
        slot_start_time=time(9, 0),
        capacity=40,
    )

    client.force_login(users["admin"])
    response = client.get(
        reverse("settings_product_settings_edit", args=[product.id]),
        {"tab": "schedule"},
    )

    assert response.status_code == 200
    assert b"Current schedule" in response.content
    assert b"Other schedules" in response.content
    assert b"Duration" in response.content
    assert b"09:00" in response.content


@pytest.mark.django_db
def test_viewer_cannot_save_product_schedule(client, users):
    product = Product.objects.create(canonical_name="Readonly Tour")
    client.force_login(users["viewer"])

    response = client.post(
        reverse("settings_product_settings_edit", args=[product.id]),
        {
            "action": "save_schedule",
            "schedule_name": "Default season",
        },
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_operator_cannot_open_product_settings(client, users):
    client.force_login(users["operator"])

    response = client.get(reverse("settings_product_settings"))

    assert response.status_code == 403
