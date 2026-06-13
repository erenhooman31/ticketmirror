import re

import pytest
from django.urls import reverse

from apps.accounts.models import UserProfile


@pytest.fixture
def users(django_user_model):
    viewer = django_user_model.objects.create_user(
        username="nav-viewer",
        password="password",
    )
    operator = django_user_model.objects.create_user(
        username="nav-operator",
        password="password",
    )
    admin = django_user_model.objects.create_user(
        username="nav-admin",
        password="password",
    )
    operator.profile.role = UserProfile.Role.OPERATOR
    operator.profile.save()
    admin.profile.role = UserProfile.Role.ADMIN
    admin.profile.save()
    return {"viewer": viewer, "operator": operator, "admin": admin}


def _primary_nav_labels(response):
    html = response.content.decode()
    match = re.search(
        r'<div class="navbar-nav me-auto" data-testid="primary-nav">(.*?)</div>',
        html,
        re.S,
    )
    assert match, "primary nav was not rendered"
    return re.findall(r'<a class="nav-link"[^>]*>(.*?)</a>', match.group(1))


@pytest.mark.django_db
def test_primary_navigation_contains_only_product_pages(client, users):
    client.force_login(users["viewer"])

    response = client.get(reverse("core:dashboard"))

    assert response.status_code == 200
    assert _primary_nav_labels(response) == [
        "Home",
        "Calendar",
        "Customers",
        "Settings",
    ]
    nav_html = response.content.decode().split('data-testid="primary-nav"', 1)[1]
    nav_html = nav_html.split("</div>", 1)[0]
    for forbidden in [
        "Admin",
        "Dashboard",
        "Bookings",
        "Reports",
        "Review",
        "Products",
        "Providers",
        "Ingestion",
    ]:
        assert f">{forbidden}<" not in nav_html


@pytest.mark.django_db
def test_main_product_pages_require_login(client):
    for url in [
        reverse("core:dashboard"),
        reverse("bookings:daily"),
        reverse("core:customers"),
        reverse("core:settings"),
    ]:
        response = client.get(url)
        assert response.status_code == 302
        assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_admin_sees_settings_sections_for_configuration(client, users):
    client.force_login(users["admin"])

    response = client.get(reverse("core:settings"))

    assert response.status_code == 200
    for label in [
        b"Products &amp; Schedules",
        b"Capacity Rules",
        b"Customer Fields",
        b"Users &amp; Roles",
        b"Gmail / Ingestion",
        b"Provider Aliases",
        b"Reports / Exports",
    ]:
        assert label in response.content


@pytest.mark.django_db
def test_operator_settings_hide_restricted_admin_sections(client, users):
    client.force_login(users["operator"])

    response = client.get(reverse("core:settings"))

    assert response.status_code == 200
    assert b"Provider Aliases" in response.content
    assert b"Reports / Exports" in response.content
    assert b"Products &amp; Schedules" not in response.content
    assert b"Users &amp; Roles" not in response.content
    assert b"Customer Fields" not in response.content


@pytest.mark.django_db
def test_restricted_settings_urls_deny_operator(client, users):
    client.force_login(users["operator"])

    for url in [
        reverse("settings_product_settings"),
        reverse("core:settings_users_roles"),
        reverse("core:settings_customer_fields"),
    ]:
        response = client.get(url)
        assert response.status_code == 403
