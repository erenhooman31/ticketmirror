import csv
from collections.abc import Mapping
from io import StringIO
from typing import Any

from django.db import transaction
from django.db.models import Count, Q, Sum

from .models import Booking, BookingEvent, CapacityRule, ProductVariant

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


def capacity_snapshot(
    *,
    product_variant,
    service_date,
    start_time=None,
) -> dict[str, int]:
    snapshot = get_capacity_for_variant_date_slot(
        product_variant,
        service_date,
        start_time,
    )
    return {
        "capacity": snapshot["capacity"] or 0,
        "confirmed": snapshot["confirmed_pax"],
        "pending": snapshot["pending_pax"],
        "remaining": snapshot["remaining"] or 0,
    }


def get_capacity_for_variant_date_slot(
    variant: ProductVariant,
    service_date,
    slot=None,
) -> dict[str, Any]:
    bookings = get_slot_bookings(service_date, variant, slot)
    confirmed_pax = _sum_pax(bookings, CONFIRMED_CAPACITY_STATUSES)
    pending_pax = _sum_pax(bookings, PENDING_CAPACITY_STATUSES)
    manual_review_pax = _sum_pax(bookings, MANUAL_REVIEW_CAPACITY_STATUSES)
    capacity = _configured_capacity(variant, service_date, slot)
    remaining = None if capacity is None else capacity - confirmed_pax
    return {
        "date": service_date,
        "product": variant.product,
        "variant": variant,
        "slot": slot,
        "slot_label": _slot_label(slot),
        "confirmed_pax": confirmed_pax,
        "pending_pax": pending_pax,
        "manual_review_pax": manual_review_pax,
        "capacity": capacity,
        "remaining": remaining,
    }


def get_daily_capacity_summary(service_date) -> list[dict[str, Any]]:
    slots: dict[tuple[int, Any], dict[str, Any]] = {}

    bookings = _capacity_bookings_queryset().filter(active_travel_date=service_date)
    for booking in bookings:
        if not booking.canonical_variant_id:
            continue
        slot = _slot_for_booking(booking)
        slots[(booking.canonical_variant_id, slot)] = {
            "variant": booking.canonical_variant,
            "slot": slot,
        }

    rule_variants = ProductVariant.objects.select_related("product").filter(
        capacity_rules__in=_matching_capacity_rules(service_date)
    )
    for variant in rule_variants.distinct():
        variant_rules = _matching_capacity_rules(service_date).filter(
            product_variant=variant
        )
        for rule in variant_rules:
            if _generic_timed_rule_without_bookings(variant, rule, slots):
                continue
            slot = _slot_for_rule(variant, rule)
            slots.setdefault((variant.id, slot), {"variant": variant, "slot": slot})

    rows = [
        get_capacity_for_variant_date_slot(data["variant"], service_date, data["slot"])
        for data in slots.values()
    ]
    return sorted(rows, key=_capacity_row_sort_key)


def get_slot_bookings(service_date, variant: ProductVariant, slot):
    queryset = (
        Booking.objects.filter(
            canonical_variant=variant,
            active_travel_date=service_date,
        )
        .exclude(status__in=EXCLUDED_CAPACITY_STATUSES)
        .select_related("provider", "canonical_product", "canonical_variant")
        .order_by("provider__name", "provider_booking_reference")
    )
    return _filter_bookings_for_slot(queryset, variant, slot)


def export_daily_manifest_csv(service_date) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "product",
            "variant",
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
        .select_related("provider", "canonical_product", "canonical_variant")
        .order_by(
            "canonical_product__canonical_name",
            "canonical_variant__variant_name",
            "active_start_time",
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
            "product",
            "variant",
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
                    row["product"].canonical_name,
                    row["variant"].variant_name,
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


def _capacity_bookings_queryset():
    return (
        Booking.objects.exclude(status__in=EXCLUDED_CAPACITY_STATUSES)
        .select_related("canonical_product", "canonical_variant__product")
        .order_by()
    )


def _matching_capacity_rules(service_date):
    return CapacityRule.objects.filter(
        active=True,
    ).filter(
        Q(date_from__isnull=True) | Q(date_from__lte=service_date),
        Q(date_to__isnull=True) | Q(date_to__gte=service_date),
        Q(day_of_week__isnull=True) | Q(day_of_week=service_date.weekday()),
    )


def _configured_capacity(variant: ProductVariant, service_date, slot) -> int | None:
    rules = _matching_capacity_rules(service_date).filter(product_variant=variant)
    if _slot_is_time(slot):
        rules = rules.filter(Q(slot_start_time__isnull=True) | Q(slot_start_time=slot))
    else:
        rules = rules.filter(slot_start_time__isnull=True)

    rule = rules.order_by(
        "-slot_start_time",
        "-date_from",
        "-created_at",
    ).first()
    if rule:
        return rule.capacity
    return variant.default_capacity


def _slot_for_booking(booking: Booking):
    slot_type = booking.active_slot_type or (
        booking.canonical_variant.slot_type if booking.canonical_variant else ""
    )
    if slot_type in {
        ProductVariant.SlotType.FULL_DAY,
        ProductVariant.SlotType.HALF_DAY,
    }:
        return slot_type
    if slot_type == ProductVariant.SlotType.FIXED_TIME:
        return booking.active_start_time
    if slot_type == ProductVariant.SlotType.PRIVATE_GROUP:
        return booking.active_start_time or ProductVariant.SlotType.PRIVATE_GROUP
    return booking.active_start_time or slot_type or None


def _slot_for_rule(variant: ProductVariant, rule: CapacityRule):
    if variant.slot_type in {
        ProductVariant.SlotType.FULL_DAY,
        ProductVariant.SlotType.HALF_DAY,
    }:
        return variant.slot_type
    return rule.slot_start_time or variant.slot_type


def _generic_timed_rule_without_bookings(
    variant: ProductVariant,
    rule: CapacityRule,
    slots: dict[tuple[int, Any], dict[str, Any]],
) -> bool:
    if rule.slot_start_time is not None:
        return False
    if variant.slot_type not in {
        ProductVariant.SlotType.FIXED_TIME,
        ProductVariant.SlotType.PRIVATE_GROUP,
    }:
        return False
    return any(variant_id == variant.id for variant_id, _slot in slots)


def _filter_bookings_for_slot(queryset, variant: ProductVariant, slot):
    if _slot_is_time(slot):
        return queryset.filter(active_start_time=slot)
    if slot in {ProductVariant.SlotType.FULL_DAY, ProductVariant.SlotType.HALF_DAY}:
        return queryset.filter(
            Q(active_slot_type=slot)
            | Q(active_slot_type="", canonical_variant__slot_type=slot)
        )
    if slot == ProductVariant.SlotType.PRIVATE_GROUP:
        return queryset.filter(
            Q(active_slot_type=slot)
            | Q(active_slot_type="", canonical_variant__slot_type=slot)
        )
    if slot is None:
        return queryset.filter(active_start_time__isnull=True)
    return queryset.filter(active_slot_type=slot)


def _sum_pax(queryset, statuses: set[str]) -> int:
    return (
        queryset.filter(status__in=statuses).aggregate(
            total=Sum("active_traveler_count")
        )["total"]
        or 0
    )


def _slot_is_time(slot) -> bool:
    return hasattr(slot, "hour") and hasattr(slot, "minute")


def _slot_label(slot) -> str:
    if _slot_is_time(slot):
        return slot.strftime("%H:%M")
    if not slot:
        return "Open"
    return str(slot).replace("_", " ").title()


def _capacity_row_sort_key(row: dict[str, Any]):
    slot = row["slot"]
    slot_sort = slot.strftime("%H:%M") if _slot_is_time(slot) else str(slot or "")
    return (
        row["product"].canonical_name,
        row["variant"].variant_name,
        slot_sort,
    )


def _daily_manifest_row(booking: Booking) -> list[Any]:
    return [
        booking.active_travel_date or "",
        (booking.canonical_product.canonical_name if booking.canonical_product else ""),
        booking.canonical_variant.variant_name if booking.canonical_variant else "",
        _slot_label(_slot_for_booking(booking)),
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
