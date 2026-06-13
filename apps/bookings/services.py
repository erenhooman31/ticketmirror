import csv
from collections.abc import Mapping
from datetime import time
from io import StringIO
from typing import Any

from django.db import transaction
from django.db.models import Count, Q, Sum

from .models import (
    ActivitySchedule,
    ActivityScheduleException,
    ActivityScheduleSlot,
    Booking,
    BookingEvent,
)

PROVIDER_TO_ACTIVE_FIELD_MAP = {
    "provider_travel_date": "active_travel_date",
    "provider_start_time": "active_start_time",
    "provider_end_time": "active_end_time",
    "provider_slot_type": "active_slot_type",
    "provider_traveler_count": "active_traveler_count",
    "status": "status",
}

MANUAL_EDIT_BLOCKLIST = {
    "provider",
    "provider_id",
    "provider_booking_reference",
}

CONFIRMED_CAPACITY_STATUSES = {
    Booking.Status.CONFIRMED,
    Booking.Status.MODIFIED,
}
PENDING_CAPACITY_STATUSES = {
    Booking.Status.PENDING_PROVIDER_ACCEPTANCE,
}
MANUAL_REVIEW_CAPACITY_STATUSES = {
    Booking.Status.MANUAL_REVIEW,
}
EXCLUDED_CAPACITY_STATUSES = {
    Booking.Status.CANCELLED,
    Booking.Status.REJECTED,
    Booking.Status.PARSE_FAILED,
    Booking.Status.DUPLICATE_IGNORED,
}


def apply_manual_override(
    *,
    booking: Booking,
    changes: Mapping[str, Any],
    user=None,
    reason: str = "",
) -> Booking:
    blocked_fields = MANUAL_EDIT_BLOCKLIST.intersection(changes)
    if blocked_fields:
        blocked = ", ".join(sorted(blocked_fields))
        raise ValueError(f"Manual edits are not allowed for: {blocked}")

    with transaction.atomic():
        old_values = {}
        new_values = {}
        changed_fields = []
        manual_override_fields = set(booking.manual_override_fields or [])

        for field_name, new_value in changes.items():
            old_value = getattr(booking, field_name)
            if old_value == new_value:
                continue

            old_values[field_name] = str(old_value or "")
            new_values[field_name] = str(new_value or "")
            setattr(booking, field_name, new_value)
            changed_fields.append(field_name)
            manual_override_fields.add(field_name)

        if changed_fields:
            booking.manual_override_fields = sorted(manual_override_fields)
            booking.save(
                update_fields=[
                    *changed_fields,
                    "manual_override_fields",
                    "updated_at",
                ]
            )
            event_type = (
                BookingEvent.EventType.MANUAL_STATUS_CHANGE
                if "status" in changed_fields
                else BookingEvent.EventType.MANUAL_EDIT
            )
            BookingEvent.objects.create(
                booking=booking,
                event_type=event_type,
                source=BookingEvent.Source.MANUAL,
                old_values=old_values,
                new_values={**new_values, "reason": reason},
                created_by=user,
            )

    return booking


def is_manually_overridden(booking: Booking, field_name: str) -> bool:
    return field_name in set(booking.manual_override_fields or [])


def active_field_for_provider_field(field_name: str) -> str | None:
    return PROVIDER_TO_ACTIVE_FIELD_MAP.get(field_name)


def diff_field_values(instance, values: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    diffs = {}
    for field_name, new_value in values.items():
        old_value = getattr(instance, field_name)
        if old_value != new_value:
            diffs[field_name] = {"old": old_value, "new": new_value}
    return diffs


def provider_update_conflicts(
    *,
    booking: Booking,
    provider_values: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    conflicts = {}
    for provider_field, provider_value in provider_values.items():
        active_field = active_field_for_provider_field(provider_field)
        if not active_field or not is_manually_overridden(booking, active_field):
            continue
        active_value = getattr(booking, active_field)
        if active_value != provider_value:
            conflicts[active_field] = {
                "provider_field": provider_field,
                "provider_value": provider_value,
                "active_value": active_value,
            }
    return conflicts


def active_updates_from_provider_values(
    *,
    booking: Booking,
    provider_values: Mapping[str, Any],
) -> dict[str, Any]:
    updates = {}
    for provider_field, provider_value in provider_values.items():
        active_field = active_field_for_provider_field(provider_field)
        if not active_field or is_manually_overridden(booking, active_field):
            continue
        updates[active_field] = provider_value
    return updates


def resolve_active_schedule(activity, service_date) -> ActivitySchedule | None:
    schedules = activity.schedules.filter(active=True).filter(
        Q(date_from__isnull=True) | Q(date_from__lte=service_date),
        Q(date_to__isnull=True) | Q(date_to__gte=service_date),
    )
    candidates = list(schedules)
    if not candidates:
        return None
    return sorted(candidates, key=_schedule_precedence_key)[0]


def capacity_snapshot(
    *,
    schedule_slot,
    service_date,
) -> dict[str, int]:
    snapshot = get_capacity_for_slot_date(schedule_slot, service_date)
    return {
        "capacity": snapshot["capacity"] or 0,
        "confirmed": snapshot["confirmed_pax"],
        "pending": snapshot["pending_pax"],
        "remaining": snapshot["remaining"] or 0,
    }


def get_capacity_for_slot_date(
    slot: ActivityScheduleSlot,
    service_date,
) -> dict[str, Any]:
    bookings = get_slot_bookings(service_date, slot)
    confirmed_pax = _sum_pax(bookings, CONFIRMED_CAPACITY_STATUSES)
    pending_pax = _sum_pax(bookings, PENDING_CAPACITY_STATUSES)
    manual_review_pax = _sum_pax(bookings, MANUAL_REVIEW_CAPACITY_STATUSES)
    capacity = _capacity_for_slot(slot, service_date)
    remaining = capacity - confirmed_pax
    return {
        "date": service_date,
        "activity": slot.schedule.activity,
        "schedule": slot.schedule,
        "slot": slot,
        "slot_label": slot_label(slot),
        "confirmed_pax": confirmed_pax,
        "pending_pax": pending_pax,
        "manual_review_pax": manual_review_pax,
        "capacity": capacity,
        "remaining": remaining,
    }


def get_daily_capacity_summary(service_date) -> list[dict[str, Any]]:
    slots = {}
    for schedule in ActivitySchedule.objects.select_related("activity").filter(
        activity__active=True,
        active=True,
    ):
        if schedule.activity_id in slots:
            continue
        active_schedule = resolve_active_schedule(schedule.activity, service_date)
        if not active_schedule:
            continue
        if not _schedule_applies_to_weekday(active_schedule, service_date):
            continue
        slots[schedule.activity_id] = active_schedule

    rows = []
    for schedule in slots.values():
        for slot in schedule.slots.filter(active=True).select_related(
            "schedule", "schedule__activity"
        ):
            if _slot_removed_by_exception(slot, service_date):
                continue
            rows.append(get_capacity_for_slot_date(slot, service_date))
        rows.extend(_extra_slot_rows(schedule, service_date))

    booking_slots = (
        Booking.objects.exclude(status__in=EXCLUDED_CAPACITY_STATUSES)
        .filter(active_travel_date=service_date, schedule_slot__isnull=False)
        .select_related("schedule_slot", "schedule_slot__schedule__activity")
        .values_list("schedule_slot_id", flat=True)
        .distinct()
    )
    seen_slot_ids = {row["slot"].id for row in rows if row["slot"]}
    for slot in ActivityScheduleSlot.objects.filter(id__in=booking_slots).exclude(
        id__in=seen_slot_ids
    ):
        rows.append(get_capacity_for_slot_date(slot, service_date))

    return sorted(rows, key=_capacity_row_sort_key)


def get_slot_bookings(service_date, slot: ActivityScheduleSlot):
    return (
        Booking.objects.filter(
            schedule_slot=slot,
            active_travel_date=service_date,
        )
        .exclude(status__in=EXCLUDED_CAPACITY_STATUSES)
        .select_related("provider", "activity", "schedule_slot")
        .order_by("provider__name", "provider_booking_reference")
    )


def export_daily_manifest_csv(service_date) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "activity",
            "slot",
            "provider",
            "reference",
            "lead traveler",
            "phone",
            "email",
            "pax",
            "pickup",
            "meeting point",
            "language",
            "status",
            "notes",
        ]
    )
    bookings = (
        Booking.objects.filter(active_travel_date=service_date)
        .exclude(status__in=EXCLUDED_CAPACITY_STATUSES)
        .select_related("provider", "activity", "schedule_slot")
        .order_by(
            "activity__name",
            "schedule_slot__start_time",
            "provider__name",
            "provider_booking_reference",
        )
    )
    for booking in bookings:
        writer.writerow(_daily_manifest_row(booking))
    return output.getvalue()


def export_capacity_summary_csv(date_from, date_to) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "activity",
            "slot",
            "confirmed pax",
            "pending pax",
            "manual review pax",
            "capacity",
            "remaining",
        ]
    )
    for service_date in _date_range(date_from, date_to):
        for row in get_daily_capacity_summary(service_date):
            writer.writerow(
                [
                    row["date"],
                    row["activity"].name,
                    row["slot_label"],
                    row["confirmed_pax"],
                    row["pending_pax"],
                    row["manual_review_pax"],
                    _csv_number(row["capacity"]),
                    _csv_number(row["remaining"]),
                ]
            )
    return output.getvalue()


def export_provider_summary_csv(date_from, date_to) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "provider",
            "booking count",
            "confirmed pax",
            "pending pax",
            "cancelled count",
        ]
    )
    queryset = Booking.objects.select_related("provider")
    if date_from:
        queryset = queryset.filter(active_travel_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(active_travel_date__lte=date_to)

    rows = (
        queryset.values("provider__name")
        .annotate(
            booking_count=Count("id"),
            confirmed_pax=Sum(
                "active_traveler_count",
                filter=Q(status__in=CONFIRMED_CAPACITY_STATUSES),
            ),
            pending_pax=Sum(
                "active_traveler_count",
                filter=Q(status__in=PENDING_CAPACITY_STATUSES),
            ),
            cancelled_count=Count(
                "id",
                filter=Q(status=Booking.Status.CANCELLED),
            ),
        )
        .order_by("provider__name")
    )
    for row in rows:
        writer.writerow(
            [
                row["provider__name"],
                row["booking_count"],
                row["confirmed_pax"] or 0,
                row["pending_pax"] or 0,
                row["cancelled_count"] or 0,
            ]
        )
    return output.getvalue()


def slot_label(slot: ActivityScheduleSlot | None) -> str:
    if not slot:
        return "Open"
    if slot.slot_type in {
        ActivityScheduleSlot.SlotType.FULL_DAY,
        ActivityScheduleSlot.SlotType.HALF_DAY,
        ActivityScheduleSlot.SlotType.OPEN_TIME,
        ActivityScheduleSlot.SlotType.PRIVATE_GROUP,
    }:
        return f"{slot.start_time:%H:%M} {slot.get_slot_type_display()}"
    return slot.start_time.strftime("%H:%M")


def exception_slot_label(exception: ActivityScheduleException) -> str:
    if exception.start_time:
        return f"{exception.start_time:%H:%M} Extra slot"
    return "Extra slot"


def _schedule_precedence_key(schedule):
    date_span = _schedule_date_span(schedule)
    kind_rank = (
        0 if schedule.schedule_kind == ActivitySchedule.ScheduleKind.CURRENT else 1
    )
    return (date_span, kind_rank, schedule.priority, schedule.id)


def _schedule_date_span(schedule):
    if schedule.date_from and schedule.date_to:
        return (schedule.date_to - schedule.date_from).days
    return 999999


def _schedule_applies_to_weekday(schedule, service_date):
    if not schedule.days_of_week:
        return True
    return service_date.weekday() in schedule.days_of_week


def _schedule_exceptions(schedule, service_date):
    return list(
        schedule.exceptions.filter(active=True, date=service_date).order_by("id")
    )


def _slot_removed_by_exception(slot, service_date) -> bool:
    for exception in _schedule_exceptions(slot.schedule, service_date):
        if exception.exception_type in {
            ActivityScheduleException.ExceptionType.BLOCKED,
            ActivityScheduleException.ExceptionType.CLOSED,
        } and _exception_matches_slot(exception, slot):
            return True
        if (
            exception.exception_type
            == ActivityScheduleException.ExceptionType.REMOVED_SLOT
            and _exception_matches_slot(exception, slot)
        ):
            return True
    return False


def _capacity_for_slot(slot, service_date) -> int:
    capacity = slot.capacity
    for exception in _schedule_exceptions(slot.schedule, service_date):
        if (
            exception.exception_type
            == ActivityScheduleException.ExceptionType.OVERRIDE_CAPACITY
            and exception.capacity is not None
            and _exception_matches_slot(exception, slot)
        ):
            capacity = exception.capacity
    return capacity


def _exception_matches_slot(exception, slot) -> bool:
    if exception.start_time is None:
        return True
    return exception.start_time == slot.start_time


def _extra_slot_rows(schedule, service_date) -> list[dict[str, Any]]:
    rows = []
    for exception in _schedule_exceptions(schedule, service_date):
        if (
            exception.exception_type
            != ActivityScheduleException.ExceptionType.EXTRA_SLOT
        ):
            continue
        capacity = exception.capacity or 0
        rows.append(
            {
                "date": service_date,
                "activity": schedule.activity,
                "schedule": schedule,
                "slot": None,
                "exception": exception,
                "slot_label": exception_slot_label(exception),
                "confirmed_pax": 0,
                "pending_pax": 0,
                "manual_review_pax": 0,
                "capacity": capacity,
                "remaining": capacity,
            }
        )
    return rows


def _sum_pax(queryset, statuses: set[str]) -> int:
    return (
        queryset.filter(status__in=statuses).aggregate(
            total=Sum("active_traveler_count")
        )["total"]
        or 0
    )


def _capacity_row_sort_key(row: dict[str, Any]):
    slot = row["slot"]
    exception = row.get("exception")
    start_time = slot.start_time if slot else exception.start_time or time.max
    row_id = slot.id if slot else exception.id
    return (
        row["activity"].name,
        start_time,
        row_id,
    )


def _daily_manifest_row(booking: Booking) -> list[Any]:
    return [
        booking.active_travel_date or "",
        booking.activity.name if booking.activity else "",
        slot_label(booking.schedule_slot),
        booking.provider.name,
        booking.provider_booking_reference,
        booking.lead_traveler_name or "",
        booking.lead_traveler_phone or "",
        booking.lead_traveler_email or "",
        booking.active_traveler_count or "",
        booking.pickup_location or "",
        booking.meeting_point or "",
        booking.language or "",
        booking.status,
        booking.special_requirements or booking.customer_message or "",
    ]


def _date_range(date_from, date_to):
    if not date_from and not date_to:
        return []
    start = date_from or date_to
    end = date_to or date_from
    current = start
    while current <= end:
        yield current
        current = current.fromordinal(current.toordinal() + 1)


def _csv_number(value):
    return "" if value is None else value
