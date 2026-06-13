from datetime import time

import pytest
from django.urls import reverse
from helpers import create_activity_setup

from apps.accounts.models import UserProfile
from apps.bookings.models import (
    ActivitySchedule,
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
def test_schedule_save_creates_current_schedule_slots(client, users):
    setup = create_activity_setup(activity_name="Old City Tour", alias=False)
    activity = setup["activity"]

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_detail", args=[activity.id]),
        {
            "action": "save_current_schedule",
            "current-name": "Summer season",
            "current-active": "on",
            "current-date_from": "2026-04-01",
            "current-date_to": "2026-10-31",
            "current-days_of_week": "[0,1,6]",
            "current-timezone": "Europe/Istanbul",
            "current-priority": "10",
            "current-slot_lines": "10:00,80,150,fixed_time\n12:00,60,150,fixed_time",
        },
    )

    assert response.status_code == 302
    schedule = ActivitySchedule.objects.get(
        activity=activity,
        schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
        name="Summer season",
    )
    assert schedule.days_of_week == [0, 1, 6]
    assert schedule.slots.count() == 2
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
            "exception_type": ActivityScheduleException.ExceptionType.EXTRA_SLOT,
            "date": "2026-06-21",
            "start_time": "15:00",
            "end_time": "17:00",
            "capacity": "40",
            "reason": "One-off provider opening.",
            "active": "on",
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
    assert b"Current schedule" in response.content
    assert b"Other schedule" in response.content
    assert b"09:00" in response.content


@pytest.mark.django_db
def test_viewer_cannot_save_activity_schedule(client, users):
    setup = create_activity_setup(activity_name="Readonly Tour")
    client.force_login(users["viewer"])

    response = client.post(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {
            "action": "save_current_schedule",
            "current-name": "Default season",
        },
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_operator_cannot_open_tour_activity_settings(client, users):
    client.force_login(users["operator"])

    response = client.get(reverse("settings_tour_activities"))

    assert response.status_code == 403
