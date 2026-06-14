from datetime import date, time

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
from apps.bookings.services import get_daily_capacity_summary


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
def test_people_tab_preserves_capacity_note_when_scoped_form_omits_it(client, users):
    setup = create_activity_setup(activity_name="People Note Tour", capacity=50)
    activity = setup["activity"]
    activity.people_rule.capacity_note = "Keep this operational note."
    activity.people_rule.save(update_fields=["capacity_note"])

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_detail", args=[activity.id]),
        {
            "action": "save_people",
            "min_people_per_booking": "1",
            "max_people_per_booking": "10",
            "default_capacity": "45",
        },
    )
    activity.people_rule.refresh_from_db()

    assert response.status_code == 302
    assert activity.people_rule.default_capacity == 45
    assert activity.people_rule.capacity_note == "Keep this operational note."


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
    assert b"Other schedules" in response.content
    assert b'data-testid="weekly-schedule-grid"' in response.content
    for day in [
        b"Monday",
        b"Tuesday",
        b"Wednesday",
        b"Thursday",
        b"Friday",
        b"Saturday",
        b"Sunday",
    ]:
        assert day in response.content
    assert b"09:00" in response.content
    assert b"Duration" in response.content
    assert b"* Duration:" in response.content
    assert b"Click on a tour to edit or delete it." in response.content


@pytest.mark.django_db
def test_schedule_edit_time_modal_uses_scoped_action_rail(client, users):
    setup = create_activity_setup(activity_name="Scoped Modal Tour")

    client.force_login(users["admin"])
    response = client.get(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {"tab": "scheduling", "edit_slot": str(setup["slot"].id), "day": "0"},
    )
    html = response.content.decode()

    assert response.status_code == 200
    assert "Edit tour" in html
    assert "Day:" in html
    assert "Start:" in html
    assert "* Seats:" in html
    assert "tm-bookeo-dialog-rail" in html
    assert "Delete" in html


@pytest.mark.django_db
def test_people_tab_only_shows_scoped_capacity_controls(client, users):
    setup = create_activity_setup(activity_name="Scoped People Tour")

    client.force_login(users["admin"])
    response = client.get(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {"tab": "people"},
    )
    html = response.content.decode()

    assert response.status_code == 200
    assert "Number of people per booking" in html
    assert "Assigned capacity:" in html
    assert "Max.:" in html
    assert "Min.:" in html
    assert "Note:" not in html


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
        "Schedule",
        "Current schedule",
        "Other schedules",
        "Duration",
        "* Duration:",
        "Copy...",
        "Change seats for all times",
    ]:
        assert human_label in html
    assert "New/change schedule" in html


@pytest.mark.django_db
def test_weekly_grid_uses_slot_weekdays_and_capacity(client, users):
    setup = create_activity_setup(activity_name="Grid Day Tour")
    schedule = setup["schedule"]
    monday_slot = setup["slot"]
    monday_slot.days_of_week = [0]
    monday_slot.capacity = 12
    monday_slot.save()
    every_day_slot = ActivityScheduleSlot.objects.create(
        schedule=schedule,
        start_time=time(15, 0),
        duration_minutes=120,
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=30,
        days_of_week=[],
        active=True,
    )

    client.force_login(users["admin"])
    response = client.get(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {"tab": "scheduling"},
    )
    grid = response.context["current_schedule_grid"]

    assert monday_slot in grid[0]["slots"]
    assert every_day_slot in grid[0]["slots"]
    assert monday_slot not in grid[1]["slots"]
    assert every_day_slot in grid[1]["slots"]
    assert "12 seats" in response.content.decode()
    assert "30 seats" in response.content.decode()


@pytest.mark.django_db
def test_deleting_slot_from_specific_day_keeps_other_days(client, users):
    setup = create_activity_setup(activity_name="Specific Day Delete Tour")
    slot = setup["slot"]

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {
            "action": "deactivate_time_slot",
            "slot_id": str(slot.id),
            "slot_days": "0",
        },
    )

    assert response.status_code == 302
    slot.refresh_from_db()
    assert slot.active is True
    assert slot.days_of_week == [1, 2, 3, 4, 5, 6]

    response = client.get(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {"tab": "scheduling"},
    )
    grid = response.context["current_schedule_grid"]

    assert slot not in grid[0]["slots"]
    assert slot in grid[1]["slots"]


@pytest.mark.django_db
def test_multiple_other_schedules_render_as_rows(client, users):
    setup = create_activity_setup(activity_name="Season Rows Tour")
    activity = setup["activity"]
    ActivitySchedule.objects.create(
        activity=activity,
        schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
        name="Summer season",
        active=True,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 8, 31),
        priority=210,
    )
    ActivitySchedule.objects.create(
        activity=activity,
        schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
        name="Winter season",
        active=False,
        date_from=date(2026, 12, 1),
        date_to=date(2027, 2, 28),
        priority=220,
    )

    client.force_login(users["admin"])
    response = client.get(
        reverse("settings_tour_activity_detail", args=[activity.id]),
        {"tab": "scheduling"},
    )
    html = response.content.decode()

    assert "Summer season" in html
    assert "Winter season" in html
    assert "2026" in html
    assert "Start" in html
    assert "End" in html
    assert "Name" in html
    assert "edit_schedule=" in html


@pytest.mark.django_db
def test_other_schedule_editor_can_delete_schedule(client, users):
    setup = create_activity_setup(activity_name="Delete Schedule Tour")
    activity = setup["activity"]
    schedule = ActivitySchedule.objects.create(
        activity=activity,
        schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
        name="Delete me",
        active=True,
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 30),
        priority=210,
    )

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_detail", args=[activity.id]),
        {
            "action": "delete_schedule",
            "schedule_id": str(schedule.id),
        },
    )

    assert response.status_code == 302
    assert not ActivitySchedule.objects.filter(id=schedule.id).exists()


@pytest.mark.django_db
def test_other_schedule_editor_can_copy_existing_schedule(client, users):
    setup = create_activity_setup(activity_name="Copy Existing Schedule Tour")
    activity = setup["activity"]
    schedule = ActivitySchedule.objects.create(
        activity=activity,
        schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
        name="Copy me",
        active=True,
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 30),
        priority=210,
    )
    ActivityScheduleSlot.objects.create(
        schedule=schedule,
        start_time=time(13, 0),
        end_time=time(15, 0),
        duration_minutes=120,
        slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
        capacity=20,
        active=True,
    )

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_detail", args=[activity.id]),
        {
            "action": "copy_existing_schedule",
            "schedule_id": str(schedule.id),
        },
    )

    copied = ActivitySchedule.objects.get(name="Copy of Copy me")
    assert response.status_code == 302
    assert copied.schedule_kind == ActivitySchedule.ScheduleKind.OTHER
    assert copied.slots.filter(start_time=time(13, 0), capacity=20).exists()


@pytest.mark.django_db
def test_duration_form_updates_current_schedule_slots(client, users):
    setup = create_activity_setup(activity_name="Duration Tour")
    schedule = setup["schedule"]
    slot = setup["slot"]

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {
            "action": "save_duration",
            "days": "0",
            "hours": "1",
            "minutes": "30",
        },
    )
    slot.refresh_from_db()

    assert response.status_code == 302
    assert slot.duration_minutes == 90
    assert slot.end_time == time(10, 30)
    assert schedule.slots.count() == 1


@pytest.mark.django_db
def test_new_change_schedule_opens_editor_without_creating_blank_schedule(
    client, users
):
    setup = create_activity_setup(activity_name="New Change Schedule Tour")
    activity = setup["activity"]

    client.force_login(users["admin"])
    response = client.post(
        reverse("settings_tour_activity_detail", args=[activity.id]),
        {
            "action": "new_change_schedule",
            "copy_source": "",
        },
    )

    assert response.status_code == 200
    assert (
        ActivitySchedule.objects.filter(
            activity=activity,
            schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
        ).count()
        == 0
    )
    html = response.content.decode()
    assert "Name" in html
    assert "Start date" in html
    assert "Schedule" in html

    response = client.post(
        reverse("settings_tour_activity_detail", args=[activity.id]),
        {
            "action": "save_other_schedule",
            "other-schedule_name": "",
            "other-schedule_status": "active",
            "other-applies_from": "",
            "other-applies_until": "",
            "other-timezone": "Europe/Istanbul",
            "other-notes": "",
        },
    )

    assert response.status_code == 200
    assert "Name is required." in response.content.decode()
    assert "Start date is required." in response.content.decode()
    assert (
        ActivitySchedule.objects.filter(
            activity=activity,
            schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_additional_time_renders_and_affects_calendar(client, users):
    setup = create_activity_setup(activity_name="Additional Time Tour")
    schedule = setup["schedule"]
    service_date = setup["date"]
    ActivityScheduleException.objects.create(
        schedule=schedule,
        exception_type=ActivityScheduleException.ExceptionType.EXTRA_SLOT,
        date=service_date,
        start_time=time(15, 0),
        capacity=40,
        active=True,
    )

    client.force_login(users["admin"])
    response = client.get(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {"tab": "scheduling"},
    )
    rows = get_daily_capacity_summary(service_date)

    assert "Additional times" not in response.content.decode()
    assert "15:00" not in response.content.decode()
    assert any(row["slot"] is None and row["capacity"] == 40 for row in rows)


@pytest.mark.django_db
def test_blocked_date_renders_separately_and_removes_calendar_availability(
    client, users
):
    setup = create_activity_setup(activity_name="Blocked Date Tour")
    schedule = setup["schedule"]
    slot = setup["slot"]
    service_date = setup["date"]
    ActivityScheduleException.objects.create(
        schedule=schedule,
        exception_type=ActivityScheduleException.ExceptionType.BLOCKED,
        date=service_date,
        start_time=slot.start_time,
        reason="Boat maintenance",
        active=True,
    )

    client.force_login(users["admin"])
    response = client.get(
        reverse("settings_tour_activity_detail", args=[setup["activity"].id]),
        {"tab": "scheduling"},
    )

    assert response.status_code == 200
    assert get_daily_capacity_summary(service_date) == []


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
    assert "Current schedule" in html
    assert "Other schedules" in html


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
    assert "End date" in html
    assert "Applies until must be after Applies from." in html
