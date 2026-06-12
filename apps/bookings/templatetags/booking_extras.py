from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    if not mapping:
        return None
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
