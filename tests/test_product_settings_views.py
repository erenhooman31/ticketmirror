from datetime import time

import pytest
from django.urls import reverse
from helpers import create_activity_setup

from apps.accounts.models import UserProfile
from apps.bookings.models import (
    ActivityScheduleException,
    ActivityScheduleSlot,
    ProviderAlias,
    TourActivity,
)


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
def test_tour_activity_list_requires_login(client):
    response = client.get(reverse("settings_tour_activities"))

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_admin_creates_activity_general_settings(client, users):
    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_new"),
        {
            "action": "save_general",
            "name": "Bosphorus Sightseeing Cruise",
            "internal_display_name": "Bosphorus Cruise",
            "category": TourActivity.Category.CRUISE,
            "active": "on",
            "visible_internally": "on",
            "show_in_calendar": "on",
            "show_in_reports": "on",
            "notes": "Shown as a short operations label.",
        },
    )
    activity = TourActivity.objects.get(name="Bosphorus Sightseeing Cruise")

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "settings_tour_activity_detail",
        args=[activity.id],
    )
    assert activity.internal_display_name == "Bosphorus Cruise"
    assert activity.category == TourActivity.Category.CRUISE
    assert activity.display_settings["show_in_calendar"] is True


@pytest.mark.django_db
def test_schedule_save_updates_current_schedule_details_and_adds_slot(client, users):
    setup = create_activity_setup(activity_name="Old City Tour", alias=False)
    activity = setup["activity"]
    schedule = setup["schedule"]

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_detail", args=[activity.id]),
        {
            "action": "save_current_schedule",
            "current-schedule_name": "Summer season",
            "current-schedule_status": "active",
            "current-applies_from": "2026-04-01",
            "current-applies_until": "2026-10-31",
            "current-repeat_days": ["0", "1", "6"],
            "current-timezone": "Europe/Istanbul",
            "current-notes": "Seasonal operating schedule.",
        },
    )

    assert response.status_code == 302
    schedule.refresh_from_db()
    assert schedule.name == "Summer season"
    assert schedule.days_of_week == [0, 1, 6]
    assert schedule.date_from.isoformat() == "2026-04-01"

    response = client.post(
        reverse("settings_tour_activity_detail", args=[activity.id]),
        {
            "action": "save_time_slot",
            "schedule_id": str(schedule.id),
            "start_time": "10:00",
            "duration_minutes": "150",
            "slot_kind": "fixed-time",
            "capacity": "80",
            "slot_status": "active",
        },
    )

    assert response.status_code == 302
    assert (
        ActivityScheduleSlot.objects.get(
            schedule=schedule,
            start_time=time(10, 0),
        ).duration_minutes
        == 150
    )


@pytest.mark.django_db
def test_schedule_tab_adds_exception(client, users):
    setup = create_activity_setup(activity_name="Exception Settings Tour", alias=False)
    activity = setup["activity"]
    schedule = setup["schedule"]

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_detail", args=[activity.id]),
        {
            "action": "save_schedule_exception",
            "schedule_id": str(schedule.id),
            "special_date_kind": "extra-slot",
            "date": "2026-06-21",
            "start_time": "15:00",
            "end_time": "17:00",
            "capacity": "40",
            "reason": "One-off provider opening.",
            "special_date_status": "active",
        },
    )

    assert response.status_code == 302
    exception = ActivityScheduleException.objects.get(schedule=schedule)
    assert (
        exception.exception_type == ActivityScheduleException.ExceptionType.EXTRA_SLOT
    )
    assert exception.capacity == 40


@pytest.mark.django_db
def test_people_tab_updates_capacity_defaults(client, users):
    setup = create_activity_setup(activity_name="People Tour", capacity=50)
    activity = setup["activity"]

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_detail", args=[activity.id]),
        {
            "action": "save_people",
            "min_people_per_booking": "1",
            "max_people_per_booking": "12",
            "default_capacity": "40",
            "capacity_note": "Shared boat capacity.",
        },
    )
    activity.people_rule.refresh_from_db()

    assert response.status_code == 302
    assert activity.people_rule.max_people_per_booking == 12
    assert activity.people_rule.default_capacity == 40


@pytest.mark.django_db
def test_activity_detail_creates_provider_alias(client, users):
    setup = create_activity_setup(activity_name="Alias Tour", alias=False)
    activity = setup["activity"]
    provider = setup["provider"]

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_detail", args=[activity.id]),
        {
            "action": "save_alias",
            "provider": str(provider.id),
            "raw_product_name": "Raw Alias Tour",
            "raw_option_name": "",
            "provider_product_code": "",
            "provider_option_code": "",
            "linked_activity": str(activity.id),
            "linked_schedule": str(setup["schedule"].id),
            "linked_slot": str(setup["slot"].id),
            "approved": "on",
            "notes": "",
        },
    )

    assert response.status_code == 302
    alias = ProviderAlias.objects.get(raw_product_name="Raw Alias Tour")
    assert alias.linked_activity == activity
    assert alias.linked_slot == setup["slot"]


@pytest.mark.django_db
def test_schedule_tab_renders_current_and_other_sections(client, users):
    setup = create_activity_setup(activity_name="Rendered Tour")

    client.force_login(users["admin"])
    response = client.get(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {"tab": "scheduling"},
    )

    assert response.status_code == 200
    assert b"Current Schedule" in response.content
    assert b"Other Schedule" in response.content
    assert b"09:00" in response.content


@pytest.mark.django_db
def test_schedule_tab_uses_operator_labels_not_raw_fields(client, users):
    setup = create_activity_setup(activity_name="Human Schedule Tour")

    client.force_login(users["admin"])
    response = client.get(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {"tab": "scheduling"},
    )
    html = response.content.decode()

    for raw_label in [
        "schedule_kind",
        "recurrence_mode",
        "days_of_week",
        "date_from",
        "date_to",
        "exception_type",
        "slot_type",
        "display_settings",
    ]:
        assert raw_label not in html
    for human_label in [
        "Current Schedule",
        "Other Schedule",
        "Effective dates",
        "Repeats on",
        "Available times",
        "Capacity",
        "Special dates",
        "Blocked dates",
    ]:
        assert human_label in html
    assert "No special dates or blocked dates have been added." in html


@pytest.mark.django_db
def test_viewer_cannot_save_activity_schedule(client, users):
    setup = create_activity_setup(activity_name="Readonly Tour")
    client.force_login(users["viewer"])

    response = client.post(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {
            "action": "save_current_schedule",
            "current-schedule_name": "Default season",
        },
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_operator_can_view_tour_activity_settings_without_mutation_actions(
    client, users
):
    setup = create_activity_setup(activity_name="Operator Visible Tour")
    client.force_login(users["operator"])

    list_response = client.get(reverse("settings_tour_activities"))
    detail_response = client.get(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {"tab": "scheduling"},
    )

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    html = detail_response.content.decode()
    assert "Add time slot" not in html
    assert "Add special date" not in html
    assert "Save schedule details" not in html
    assert "Available times" in html


@pytest.mark.django_db
def test_schedule_validation_error_stays_near_human_field(client, users):
    setup = create_activity_setup(activity_name="Invalid Schedule Tour")

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {
            "action": "save_current_schedule",
            "current-schedule_name": "Invalid season",
            "current-schedule_status": "active",
            "current-applies_from": "2026-10-31",
            "current-applies_until": "2026-04-01",
            "current-timezone": "Europe/Istanbul",
            "current-notes": "",
        },
    )
    html = response.content.decode()

    assert response.status_code == 200
    assert "Applies until" in html
    assert "Applies until must be after Applies from." in html
