import json

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def get_item(mapping, key):
    if not mapping:
        return None
    if hasattr(mapping, "fields") and key in mapping.fields:
        return mapping[key]
    return mapping.get(key)


@register.filter
def field_overridden(booking, field_name):
    return field_name in set(booking.manual_override_fields or [])


@register.filter
def status_class(status):
    return {
        "confirmed": "success",
        "pending_provider_acceptance": "warning",
        "cancelled": "secondary",
        "rejected": "danger",
        "modified": "info",
        "manual_review": "danger",
        "parse_failed": "danger",
        "duplicate_ignored": "secondary",
    }.get(status, "secondary")


@register.filter
def json_dumps(value):
    return mark_safe(conditional_escape(json.dumps(value, ensure_ascii=False)))
