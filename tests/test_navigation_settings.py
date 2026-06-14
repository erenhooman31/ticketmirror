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
        "Inbox",
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
        reverse("inbox"),
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
        b"Tours &amp; Activities",
        b"Users &amp; Roles",
    ]:
        assert label in response.content
    for forbidden in [
        b"Customer Fields",
        b"Gmail / Ingestion",
        b"Provider Aliases",
        b"Reports / Exports",
    ]:
        assert forbidden not in response.content


@pytest.mark.django_db
def test_operator_settings_hide_restricted_admin_sections(client, users):
    client.force_login(users["operator"])

    response = client.get(reverse("core:settings"))

    assert response.status_code == 200
    assert b"Tours &amp; Activities" in response.content
    assert b"Users &amp; Roles" not in response.content
    assert b"Customer Fields" not in response.content


@pytest.mark.django_db
def test_restricted_settings_urls_deny_operator(client, users):
    client.force_login(users["operator"])

    for url in [
        reverse("core:settings_users_roles"),
        reverse("core:settings_customer_fields"),
    ]:
        response = client.get(url)
        assert response.status_code == 403


@pytest.mark.django_db
def test_admin_can_create_user_from_settings(client, users, django_user_model):
    client.force_login(users["admin"])

    response = client.post(
        reverse("core:settings_users_roles"),
        {
            "action": "create_user",
            "username": "created-operator",
            "email": "created@example.test",
            "password": "temporary-password",
            "role": UserProfile.Role.OPERATOR,
        },
    )

    created = django_user_model.objects.get(username="created-operator")
    assert response.status_code == 302
    assert created.email == "created@example.test"
    assert created.profile.role == UserProfile.Role.OPERATOR


@pytest.mark.django_db
def test_operator_can_open_tours_and_activities_readonly(client, users):
    client.force_login(users["operator"])

    response = client.get(reverse("settings_tour_activities"))

    assert response.status_code == 200
    assert b"New activity" not in response.content
