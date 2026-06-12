from collections.abc import Mapping
from typing import Any

from django.db import transaction
from django.db.models import Sum

from .models import Booking, BookingEvent, CapacityRule, ManualOverride

MANUAL_EDIT_BLOCKLIST = {"provider", "provider_id", "provider_reference"}


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
        changed_fields = []
        for field_name, new_value in changes.items():
            old_value = getattr(booking, field_name)
            if old_value == new_value:
                continue

            ManualOverride.objects.create(
                booking=booking,
                field_name=field_name,
                old_value=str(old_value or ""),
                new_value=str(new_value or ""),
                changed_by=user,
                reason=reason,
            )
            setattr(booking, field_name, new_value)
            changed_fields.append(field_name)

        if changed_fields:
            booking.save(update_fields=[*changed_fields, "updated_at"])
            BookingEvent.objects.create(
                booking=booking,
                event_type=BookingEvent.EventType.MANUAL_OVERRIDE,
                message="Manual override applied.",
                changed_by=user,
                metadata={"fields": changed_fields, "reason": reason},
            )

    return booking


def capacity_snapshot(
    *, product, service_date, variant=None, time_slot=None
) -> dict[str, int]:
    rule = (
        CapacityRule.objects.filter(
            product=product,
            variant=variant,
            service_date=service_date,
            time_slot=time_slot,
        )
        .order_by("-created_at")
        .first()
    )
    configured_capacity = (
        rule.capacity if rule else (variant.default_capacity if variant else 0)
    )

    bookings = Booking.objects.filter(
        product=product,
        variant=variant,
        service_date=service_date,
        time_slot=time_slot,
    )
    confirmed = (
        bookings.filter(status=Booking.Status.CONFIRMED).aggregate(
            total=Sum("party_size")
        )["total"]
        or 0
    )
    pending = (
        bookings.filter(status=Booking.Status.PENDING).aggregate(
            total=Sum("party_size")
        )["total"]
        or 0
    )

    return {
        "capacity": configured_capacity,
        "confirmed": confirmed,
        "pending": pending,
        "remaining": max(configured_capacity - confirmed, 0),
    }
