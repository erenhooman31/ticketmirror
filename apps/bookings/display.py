from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from typing import Any

from django.utils import timezone

RAW_EMPTY_STRINGS = {"", "none", "null", "{}", "[]"}
RAW_STRUCTURE_RE = re.compile(r"(^\s*[\[{].*[\]}]\s*$)|(\{['\"])|(\[['\"])")


def clean_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        text = re.sub(r"\s+", " ", value).strip()
        if text.lower() in RAW_EMPTY_STRINGS:
            return fallback
        if RAW_STRUCTURE_RE.search(text):
            return fallback
        return text
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return fallback
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        parts = [clean_text(item) for item in value]
        parts = [part for part in parts if part]
        return ", ".join(parts) if parts else fallback
    return str(value).strip() or fallback


def provider_label(provider, fallback: str = "Unknown provider") -> str:
    if not provider:
        return fallback
    return clean_text(getattr(provider, "name", ""), fallback) or clean_text(
        getattr(provider, "code", ""),
        fallback,
    )


def reference_label(booking, fallback: str = "Missing reference") -> str:
    if not booking:
        return fallback
    return (
        clean_text(getattr(booking, "provider_booking_reference", ""))
        or clean_text(getattr(booking, "provider_order_reference", ""))
        or fallback
    )


def customer_label(booking, fallback: str = "Missing customer") -> str:
    if not booking:
        return fallback
    return clean_text(getattr(booking, "lead_traveler_name", ""), fallback)


def activity_label(booking, fallback: str = "Missing tour/activity") -> str:
    if not booking:
        return fallback
    activity = getattr(booking, "activity", None)
    if activity:
        return clean_text(
            getattr(activity, "internal_display_name", ""),
        ) or clean_text(getattr(activity, "name", ""), fallback)
    return clean_text(getattr(booking, "raw_product_name", ""), fallback)


def product_label(booking, fallback: str = "Missing tour/activity") -> str:
    if not booking:
        return fallback
    activity = getattr(booking, "activity", None)
    slot = getattr(booking, "schedule_slot", None)
    if activity and slot:
        name = clean_text(getattr(activity, "internal_display_name", "")) or clean_text(
            getattr(activity, "name", ""),
        )
        if name and getattr(slot, "start_time", None):
            return f"{name} - {slot.start_time:%H:%M}"
        if name:
            return name
    return activity_label(booking, fallback)


def datetime_label(booking, fallback: str = "Missing date/time") -> str:
    if not booking:
        return fallback
    service_date = getattr(booking, "active_travel_date", None) or getattr(
        booking,
        "provider_travel_date",
        None,
    )
    start_time = getattr(booking, "active_start_time", None) or getattr(
        booking,
        "provider_start_time",
        None,
    )
    slot_type = clean_text(getattr(booking, "active_slot_type", "")) or clean_text(
        getattr(booking, "provider_slot_type", ""),
    )
    if not service_date:
        return fallback
    date_text = service_date.strftime("%A, %d %B %Y")
    if start_time:
        return f"{date_text} {start_time:%H:%M}"
    if slot_type in {"full_day", "half_day", "open_time", "private_group"}:
        return f"{date_text} {slot_type.replace('_', ' ')}"
    return date_text


def short_datetime_label(booking, fallback: str = "Missing date/time") -> str:
    if not booking:
        return fallback
    service_date = getattr(booking, "active_travel_date", None) or getattr(
        booking,
        "provider_travel_date",
        None,
    )
    start_time = getattr(booking, "active_start_time", None) or getattr(
        booking,
        "provider_start_time",
        None,
    )
    if not service_date:
        return fallback
    if start_time:
        return f"{service_date:%Y-%m-%d} {start_time:%H:%M}"
    return f"{service_date:%Y-%m-%d}"


def traveler_count_label(booking, fallback: str = "Missing participant count") -> str:
    if not booking:
        return fallback
    count = getattr(booking, "active_traveler_count", None)
    if count is None:
        count = getattr(booking, "provider_traveler_count", None)
    if count is None:
        return fallback
    label = "participant" if count == 1 else "participants"
    return f"{count} {label}"


def status_label(booking, fallback: str = "Needs review") -> str:
    if not booking:
        return fallback
    if hasattr(booking, "get_status_display"):
        return booking.get_status_display()
    return clean_text(getattr(booking, "status", ""), fallback)


def review_reason_label(review_item, fallback: str = "Needs review") -> str:
    if not review_item:
        return fallback
    details = clean_text(getattr(review_item, "details", ""))
    if details:
        return details
    if hasattr(review_item, "get_issue_type_display"):
        return review_item.get_issue_type_display()
    return clean_text(getattr(review_item, "title", ""), fallback)


def review_details_label(review_item, fallback: str = "Needs review") -> str:
    if not review_item:
        return fallback
    details = getattr(review_item, "details", "") or ""
    lines = []
    for line in str(details).splitlines():
        clean_line = clean_text(line)
        if not clean_line:
            continue
        if clean_line.lower().startswith("suggestions:"):
            lines.append("Similar aliases available; open review to choose a mapping.")
            continue
        lines.append(clean_line)
    if lines:
        return " ".join(lines)
    return review_reason_label(review_item, fallback)


def email_subject_label(raw_email, fallback: str = "Email without subject") -> str:
    return clean_text(getattr(raw_email, "subject", ""), fallback)


def parse_error_label(raw_email, fallback: str = "Needs review") -> str:
    return clean_text(getattr(raw_email, "parse_error", ""), fallback)


def received_label(value) -> str:
    if not value:
        return ""
    local_value = timezone.localtime(value)
    return f"{local_value:%Y-%m-%d %H:%M}"
