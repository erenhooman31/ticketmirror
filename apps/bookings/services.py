from collections.abc import Mapping
from typing import Any

from django.db import transaction
from django.db.models import Q, Sum

from .models import Booking, BookingEvent, CapacityRule

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
            BookingEvent.objects.create(
                booking=booking,
                event_type=BookingEvent.EventType.MANUAL_EDIT,
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


def capacity_snapshot(
    *,
    product_variant,
    service_date,
    start_time=None,
) -> dict[str, int]:
    rules = CapacityRule.objects.filter(
        product_variant=product_variant,
        active=True,
    )
    rules = rules.filter(
        Q(date_from__isnull=True) | Q(date_from__lte=service_date),
        Q(date_to__isnull=True) | Q(date_to__gte=service_date),
        Q(day_of_week__isnull=True) | Q(day_of_week=service_date.weekday()),
    )
    if start_time is not None:
        rules = rules.filter(slot_start_time__isnull=True) | rules.filter(
            slot_start_time=start_time
        )
    rule = rules.order_by("-date_from", "-created_at").first()

    configured_capacity = (
        rule.capacity
        if rule
        else (
            product_variant.default_capacity if product_variant.default_capacity else 0
        )
    )
    bookings = Booking.objects.filter(
        canonical_variant=product_variant,
        active_travel_date=service_date,
        active_start_time=start_time,
    )
    confirmed = (
        bookings.filter(status=Booking.Status.CONFIRMED).aggregate(
            total=Sum("active_traveler_count")
        )["total"]
        or 0
    )
    pending = (
        bookings.filter(status=Booking.Status.PENDING_PROVIDER_ACCEPTANCE).aggregate(
            total=Sum("active_traveler_count")
        )["total"]
        or 0
    )

    return {
        "capacity": configured_capacity,
        "confirmed": confirmed,
        "pending": pending,
        "remaining": max(configured_capacity - confirmed, 0),
    }
