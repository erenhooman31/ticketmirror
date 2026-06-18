import csv
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import time
from io import StringIO
from typing import Any

from django.db import transaction
from django.db.models import Count, Q, Sum

from apps.accounts.permissions import is_admin

from .models import (
    ActivitySchedule,
    ActivityScheduleException,
    ActivityScheduleSlot,
    Booking,
    BookingEvent,
    Provider,
    ReviewQueueItem,
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
EXCLUDED_ATTENDANCE_STATUSES = {
    Booking.AttendanceStatus.GELMEDI,
}


class CapacityExceededError(ValueError):
    pass


@dataclass(frozen=True)
class ScheduleSlotResolution:
    slot: ActivityScheduleSlot | None
    matched_by_time: bool = False
    used_single_slot_fallback: bool = False
    used_alias_fallback: bool = False
    no_match_for_time: bool = False


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


def create_internal_booking(
    *,
    service_date,
    schedule_slot: ActivityScheduleSlot,
    traveler_count: int,
    lead_traveler_name: str = "",
    lead_traveler_email: str | None = None,
    lead_traveler_phone: str | None = None,
    special_requirements: str | None = None,
    customer_message: str | None = None,
    user=None,
    allow_overcapacity: bool = False,
    override_reason: str = "",
) -> Booking:
    traveler_count = max(int(traveler_count or 0), 0)
    override_reason = (override_reason or "").strip()
    with transaction.atomic():
        slot = (
            ActivityScheduleSlot.objects.select_for_update()
            .select_related("schedule", "schedule__activity")
            .get(id=schedule_slot.id)
        )
        if allow_overcapacity and not is_admin(user):
            raise CapacityExceededError("Only admins can override slot capacity.")
        if allow_overcapacity and not override_reason:
            raise CapacityExceededError("A capacity override reason is required.")

        snapshot = get_capacity_for_slot_date(slot, service_date)
        projected_remaining = snapshot["remaining"] - traveler_count
        if projected_remaining < 0 and not allow_overcapacity:
            raise CapacityExceededError("This booking would exceed the slot capacity.")

        provider, _created = Provider.objects.get_or_create(
            code="direct",
            defaults={
                "name": "Direct",
                "active": True,
                "known_sender_patterns": [],
                "known_subject_patterns": [],
                "parser_key": "direct",
            },
        )
        reference = _next_internal_reference(slot)
        booking = Booking.objects.create(
            provider=provider,
            provider_booking_reference=reference,
            status=Booking.Status.CONFIRMED,
            activity=slot.schedule.activity,
            schedule_slot=slot,
            raw_product_name=slot.schedule.activity.name,
            provider_travel_date=service_date,
            provider_start_time=slot.start_time,
            provider_end_time=slot.end_time,
            provider_slot_type=slot.slot_type,
            active_travel_date=service_date,
            active_start_time=slot.start_time,
            active_end_time=slot.end_time,
            active_slot_type=slot.slot_type,
            provider_traveler_count=traveler_count,
            active_traveler_count=traveler_count,
            lead_traveler_name=lead_traveler_name.strip() or "New customer",
            lead_traveler_email=lead_traveler_email or None,
            lead_traveler_phone=lead_traveler_phone or None,
            special_requirements=special_requirements or None,
            customer_message=customer_message or None,
        )
        event_values = {
            "reference": reference,
            "traveler_count": traveler_count,
        }
        if projected_remaining < 0:
            event_values["capacity_override_reason"] = override_reason
            create_capacity_overbooked_review_item(
                booking=booking,
                details=(
                    f"Internal booking exceeded capacity by "
                    f"{abs(projected_remaining)} pax. Reason: {override_reason}"
                ),
            )
        BookingEvent.objects.create(
            booking=booking,
            event_type=BookingEvent.EventType.EMAIL_NEW_BOOKING,
            source=BookingEvent.Source.MANUAL,
            new_values=event_values,
            created_by=user,
        )
    return booking


def create_capacity_overbooked_review_item(
    *,
    booking: Booking,
    raw_email=None,
    details: str = "",
) -> ReviewQueueItem | None:
    if not booking.schedule_slot_id or not booking.active_travel_date:
        return None
    review, _created = ReviewQueueItem.objects.update_or_create(
        raw_email=raw_email,
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.CAPACITY_OVERBOOKED,
        status=ReviewQueueItem.Status.OPEN,
        defaults={
            "title": "Capacity overbooked",
            "details": details or _capacity_overbooked_details(booking),
        },
    )
    return review


def warn_if_capacity_overbooked(*, booking: Booking, raw_email=None) -> bool:
    if not booking.schedule_slot_id or not booking.active_travel_date:
        return False
    snapshot = get_capacity_for_slot_date(
        booking.schedule_slot, booking.active_travel_date
    )
    if snapshot["remaining"] >= 0:
        return False
    had_open_review = ReviewQueueItem.objects.filter(
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.CAPACITY_OVERBOOKED,
        status=ReviewQueueItem.Status.OPEN,
    ).exists()
    create_capacity_overbooked_review_item(
        booking=booking,
        raw_email=raw_email,
        details=_capacity_overbooked_details(booking, snapshot=snapshot),
    )
    if not had_open_review:
        BookingEvent.objects.create(
            booking=booking,
            event_type=BookingEvent.EventType.CONFLICT_DETECTED,
            source=BookingEvent.Source.SYSTEM,
            raw_email=raw_email,
            new_values={
                "issue_type": ReviewQueueItem.IssueType.CAPACITY_OVERBOOKED,
                "remaining": snapshot["remaining"],
                "capacity": snapshot["capacity"],
                "active_pax": snapshot["active_pax"],
            },
        )
    return True


def is_manually_overridden(booking: Booking, field_name: str) -> bool:
    return field_name in set(booking.manual_override_fields or [])


def booking_has_parsed_travel_date(booking: Booking) -> bool:
    return bool(booking.active_travel_date or booking.provider_travel_date)


def booking_has_parsed_time(booking: Booking) -> bool:
    slot_types = {
        booking.active_slot_type,
        booking.provider_slot_type,
    }
    return bool(
        booking.active_start_time
        or booking.provider_start_time
        or slot_types.intersection({"full_day", "half_day"})
    )


def booking_has_parsed_traveler_count(booking: Booking) -> bool:
    return (
        booking.active_traveler_count is not None
        or booking.provider_traveler_count is not None
    )


def booking_has_parsed_product(booking: Booking) -> bool:
    return bool(booking.activity_id or booking.raw_product_name)


def booking_provider_omits_lead_name(raw_email, booking: Booking) -> bool:
    provider_code = ""
    if raw_email and getattr(raw_email, "provider_detected_id", None):
        provider_code = raw_email.provider_detected.code
    if not provider_code and booking.provider_id:
        provider_code = booking.provider.code
    return provider_code in {"tripster", "sputnik8"}


def booking_has_required_parse_content(raw_email, booking: Booking) -> bool:
    return all(
        [
            booking.provider_booking_reference,
            booking_has_parsed_product(booking),
            booking_has_parsed_travel_date(booking),
            booking_has_parsed_time(booking),
            booking_has_parsed_traveler_count(booking),
            booking.lead_traveler_name
            or booking_provider_omits_lead_name(raw_email, booking),
        ]
    )


def review_issue_is_obsolete(
    *,
    issue_type: str,
    title: str,
    booking,
    raw_email,
) -> bool:
    if issue_type == ReviewQueueItem.IssueType.PROVIDER_NOT_DETECTED:
        return bool(raw_email and raw_email.provider_detected_id)
    if issue_type == ReviewQueueItem.IssueType.REFERENCE_MISSING:
        if raw_email and raw_email.parse_status == "ignored":
            return True
        return bool(booking and booking.provider_booking_reference)
    if not booking:
        return False
    if issue_type in {
        ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
        ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
    }:
        return bool(booking.activity_id)
    if issue_type == ReviewQueueItem.IssueType.DATE_MISSING:
        return booking_has_parsed_travel_date(booking)
    if issue_type == ReviewQueueItem.IssueType.TIME_MISSING:
        if title == "Schedule slot needs confirmation":
            return False
        return booking_has_parsed_time(booking)
    if issue_type == ReviewQueueItem.IssueType.TRAVELER_COUNT_MISSING:
        return booking_has_parsed_traveler_count(booking)
    if issue_type == ReviewQueueItem.IssueType.LEAD_TRAVELER_MISSING:
        return bool(booking.lead_traveler_name) or booking_provider_omits_lead_name(
            raw_email,
            booking,
        )
    if issue_type == ReviewQueueItem.IssueType.LOW_CONFIDENCE_PARSE:
        return booking_has_required_parse_content(raw_email, booking)
    return False


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


def resolve_schedule_slot(
    *,
    activity,
    travel_date,
    start_time,
    slot_type="",
    fallback_slot: ActivityScheduleSlot | None = None,
) -> ActivityScheduleSlot | None:
    return resolve_schedule_slot_details(
        activity=activity,
        travel_date=travel_date,
        start_time=start_time,
        slot_type=slot_type,
        fallback_slot=fallback_slot,
    ).slot


def resolve_schedule_slot_details(
    *,
    activity,
    travel_date,
    start_time,
    slot_type="",
    fallback_slot: ActivityScheduleSlot | None = None,
) -> ScheduleSlotResolution:
    if not activity:
        return ScheduleSlotResolution(slot=fallback_slot, used_alias_fallback=True)

    slots = _candidate_slots_for_booking(
        activity=activity,
        travel_date=travel_date,
        slot_type=slot_type,
    )
    if start_time:
        for slot in slots:
            if slot.start_time == start_time:
                return ScheduleSlotResolution(slot=slot, matched_by_time=True)
        if len(slots) == 1:
            return ScheduleSlotResolution(
                slot=slots[0],
                used_single_slot_fallback=True,
            )
        return ScheduleSlotResolution(
            slot=fallback_slot,
            used_alias_fallback=bool(fallback_slot),
            no_match_for_time=True,
        )

    if len(slots) == 1:
        return ScheduleSlotResolution(slot=slots[0], used_single_slot_fallback=True)
    return ScheduleSlotResolution(slot=fallback_slot, used_alias_fallback=True)


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
    active_pax = confirmed_pax + pending_pax + manual_review_pax
    capacity = slot.capacity
    blocked_pax = _blocked_pax_for_slot(slot, service_date)
    remaining = capacity - active_pax - blocked_pax
    return {
        "date": service_date,
        "activity": slot.schedule.activity,
        "schedule": slot.schedule,
        "slot": slot,
        "exception": None,
        "is_unscheduled": False,
        "slot_label": slot_label(slot),
        "confirmed_pax": confirmed_pax,
        "pending_pax": pending_pax,
        "manual_review_pax": manual_review_pax,
        "active_pax": active_pax,
        "blocked_pax": blocked_pax,
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
            if not _slot_applies_to_weekday(slot, service_date):
                continue
            if _slot_removed_by_exception(slot, service_date):
                continue
            rows.append(get_capacity_for_slot_date(slot, service_date))
        rows.extend(_extra_slot_rows(schedule, service_date))

    booking_slots = (
        Booking.objects.exclude(status__in=EXCLUDED_CAPACITY_STATUSES)
        .exclude(
            review_items__status=ReviewQueueItem.Status.OPEN,
            review_items__issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
        )
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

    unscheduled = _unscheduled_booking_row(service_date)
    if unscheduled:
        rows.append(unscheduled)

    return sorted(rows, key=_capacity_row_sort_key)


def overbooked_capacity_rows(date_from, date_to) -> list[dict[str, Any]]:
    return [
        row
        for service_date in _date_range(date_from, date_to)
        for row in get_daily_capacity_summary(service_date)
        if row["remaining"] is not None and row["remaining"] < 0
    ]


def get_slot_bookings(service_date, slot: ActivityScheduleSlot):
    return (
        Booking.objects.filter(
            schedule_slot=slot,
            active_travel_date=service_date,
        )
        .exclude(status__in=EXCLUDED_CAPACITY_STATUSES)
        .exclude(attendance_status__in=EXCLUDED_ATTENDANCE_STATUSES)
        .exclude(
            review_items__status=ReviewQueueItem.Status.OPEN,
            review_items__issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
        )
        .select_related("provider", "activity", "schedule_slot")
        .order_by("provider__name", "provider_booking_reference")
        .distinct()
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


def export_overcapacity_csv(date_from, date_to) -> str:
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
            "overbooked pax",
        ]
    )
    for row in overbooked_capacity_rows(date_from, date_to):
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
                abs(row["remaining"]),
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


def _slot_applies_to_weekday(slot, service_date):
    if not slot.days_of_week:
        return True
    return service_date.weekday() in slot.days_of_week


def _candidate_slots_for_booking(*, activity, travel_date, slot_type=""):
    if travel_date:
        schedule = resolve_active_schedule(activity, travel_date)
        if not schedule or not _schedule_applies_to_weekday(schedule, travel_date):
            return []
        queryset = schedule.slots.filter(active=True).select_related(
            "schedule",
            "schedule__activity",
        )
        slots = [
            slot
            for slot in queryset
            if _slot_applies_to_weekday(slot, travel_date)
            and not _slot_removed_by_exception(slot, travel_date)
        ]
    else:
        slots = list(
            ActivityScheduleSlot.objects.filter(
                schedule__activity=activity,
                active=True,
            )
            .select_related("schedule", "schedule__activity")
            .order_by("schedule__priority", "start_time", "id")
        )
    if slot_type:
        typed_slots = [slot for slot in slots if slot.slot_type == slot_type]
        if typed_slots:
            slots = typed_slots
    return sorted(slots, key=lambda slot: (slot.start_time, slot.id))


def _schedule_exceptions(schedule, service_date):
    return list(
        schedule.exceptions.filter(active=True, date=service_date).order_by("id")
    )


def _slot_removed_by_exception(slot, service_date) -> bool:
    for exception in _schedule_exceptions(slot.schedule, service_date):
        if (
            exception.exception_type
            == ActivityScheduleException.ExceptionType.REMOVED_SLOT
            and _exception_matches_slot(exception, slot)
        ):
            return True
    return False


def _blocked_pax_for_slot(slot, service_date) -> int:
    blocked = 0
    for exception in _schedule_exceptions(slot.schedule, service_date):
        if not _exception_matches_slot(exception, slot):
            continue
        if exception.exception_type in {
            ActivityScheduleException.ExceptionType.BLOCKED,
            ActivityScheduleException.ExceptionType.CLOSED,
        }:
            return slot.capacity
        if (
            exception.exception_type
            == ActivityScheduleException.ExceptionType.OVERRIDE_CAPACITY
            and exception.capacity is not None
        ):
            blocked = max(blocked, slot.capacity - exception.capacity)
    return blocked


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
                "active_pax": 0,
                "blocked_pax": 0,
                "capacity": capacity,
                "remaining": capacity,
                "is_unscheduled": False,
                "bookings": [],
            }
        )
    return rows


def _unscheduled_booking_row(service_date) -> dict[str, Any] | None:
    bookings = (
        Booking.objects.filter(active_travel_date=service_date)
        .exclude(status__in=EXCLUDED_CAPACITY_STATUSES)
        .exclude(attendance_status__in=EXCLUDED_ATTENDANCE_STATUSES)
        .filter(
            Q(schedule_slot__isnull=True)
            | Q(
                review_items__status=ReviewQueueItem.Status.OPEN,
                review_items__issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
            )
        )
        .select_related("provider", "activity", "schedule_slot")
        .order_by("provider__name", "provider_booking_reference")
        .distinct()
    )
    if not bookings.exists():
        return None
    confirmed_pax = _sum_pax(bookings, CONFIRMED_CAPACITY_STATUSES)
    pending_pax = _sum_pax(bookings, PENDING_CAPACITY_STATUSES)
    manual_review_pax = _sum_pax(bookings, MANUAL_REVIEW_CAPACITY_STATUSES)
    active_pax = confirmed_pax + pending_pax + manual_review_pax
    return {
        "date": service_date,
        "activity": None,
        "schedule": None,
        "slot": None,
        "exception": None,
        "is_unscheduled": True,
        "slot_label": "Unscheduled / unmapped",
        "confirmed_pax": confirmed_pax,
        "pending_pax": pending_pax,
        "manual_review_pax": manual_review_pax,
        "active_pax": active_pax,
        "blocked_pax": 0,
        "capacity": None,
        "remaining": None,
        "bookings": list(bookings),
    }


def _sum_pax(queryset, statuses: set[str]) -> int:
    return (
        queryset.filter(status__in=statuses).aggregate(
            total=Sum("active_traveler_count")
        )["total"]
        or 0
    )


def _capacity_row_sort_key(row: dict[str, Any]):
    if row.get("is_unscheduled"):
        return ("zzzzzz", time.max, 0)
    slot = row["slot"]
    exception = row.get("exception")
    start_time = slot.start_time if slot else exception.start_time or time.max
    row_id = slot.id if slot else exception.id
    return (
        row["activity"].name if row["activity"] else "zzzzzz",
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


def _next_internal_reference(slot: ActivityScheduleSlot) -> str:
    from django.utils import timezone

    timestamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
    return f"TM-{timestamp}-{slot.id}"


def _capacity_overbooked_details(
    booking: Booking,
    *,
    snapshot: dict[str, Any] | None = None,
) -> str:
    snapshot = snapshot or get_capacity_for_slot_date(
        booking.schedule_slot,
        booking.active_travel_date,
    )
    return (
        f"{booking.provider_booking_reference} has {snapshot['active_pax']} active "
        f"pax against capacity {snapshot['capacity']} for "
        f"{booking.active_travel_date} {slot_label(booking.schedule_slot)}."
    )
