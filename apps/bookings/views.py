from calendar import Calendar
from datetime import date as datetime_date
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.permissions import (
    admin_required,
    can_mutate,
    operator_required,
    viewer_required,
)
from apps.bookings.services import (
    apply_manual_override,
    capacity_snapshot,
    get_capacity_for_variant_date_slot,
    get_daily_capacity_summary,
    get_slot_bookings,
)
from apps.ingestion.models import RawEmail

from .forms import (
    BookingEditForm,
    ProductAliasForm,
    ProductScheduleForm,
    ProductSettingsForm,
)
from .models import (
    Booking,
    BookingEvent,
    CapacityRule,
    Product,
    ProductAlias,
    ProductVariant,
    Provider,
    ReviewQueueItem,
)

ALLOWED_RANGE_DAYS = {1, 3, 7, 14}
DEFAULT_RANGE_DAYS = 1
WEEKDAYS = [
    ("monday", "Monday", 0),
    ("tuesday", "Tuesday", 1),
    ("wednesday", "Wednesday", 2),
    ("thursday", "Thursday", 3),
    ("friday", "Friday", 4),
    ("saturday", "Saturday", 5),
    ("sunday", "Sunday", 6),
]


@viewer_required
def daily_operations(request):
    selected_date = _parse_date(request.GET.get("date")) or timezone.localdate()
    range_days = _parse_range_days(request.GET.get("range"))
    query = request.GET.get("q", "").strip()
    filters = _calendar_filters(request)
    date_range = _date_range(selected_date, range_days)
    base_bookings = (
        Booking.objects.filter(active_travel_date__in=date_range)
        .select_related("provider", "canonical_product", "canonical_variant")
        .order_by(
            "active_travel_date",
            "canonical_product__canonical_name",
            "canonical_variant__variant_name",
            "active_start_time",
            "provider_booking_reference",
        )
    )
    matching_bookings = _filter_calendar_bookings(base_bookings, filters)
    restrict_to_bookings = _requires_booking_match(filters)
    base_params = _base_calendar_params(selected_date, range_days, filters)
    range_options = [
        {
            "days": days,
            "active": days == range_days,
            "url": _calendar_url(base_params, range=days),
        }
        for days in sorted(ALLOWED_RANGE_DAYS)
    ]
    day_sections = [
        {
            "date": service_date,
            "label": _calendar_day_label(service_date),
            "rows": _capacity_rows(
                service_date,
                matching_bookings.filter(active_travel_date=service_date),
                filters=filters,
                restrict_to_bookings=restrict_to_bookings,
                url_params=base_params,
            ),
        }
        for service_date in date_range
    ]

    context = {
        "selected_date": selected_date,
        "range_days": range_days,
        "range_options": range_options,
        "query": query,
        "filters": filters,
        "day_sections": day_sections,
        "rows": day_sections[0]["rows"] if day_sections else [],
        "mini_calendar": _mini_calendar(selected_date, base_params),
        "product_options": Product.objects.filter(active=True).order_by(
            "canonical_name"
        ),
        "category_options": _category_options(),
        "provider_options": Provider.objects.filter(active=True).order_by("name"),
        "previous_url": _calendar_url(
            base_params,
            date=selected_date - timedelta(days=range_days),
        ),
        "today_url": _calendar_url(base_params, date=timezone.localdate()),
        "next_url": _calendar_url(
            base_params,
            date=selected_date + timedelta(days=range_days),
        ),
    }
    return render(request, "bookings/daily.html", context)


@viewer_required
def slot_detail(request, date, variant_id, time):
    selected_date = _parse_date(date) or timezone.localdate()
    variant = get_object_or_404(
        ProductVariant.objects.select_related("product"),
        id=variant_id,
    )
    slot = _parse_slot(time)
    bookings = get_slot_bookings(selected_date, variant, slot)
    snapshot = capacity_snapshot(
        product_variant=variant,
        service_date=selected_date,
        start_time=slot,
    )
    return render(
        request,
        "bookings/slot_detail.html",
        {
            "selected_date": selected_date,
            "variant": variant,
            "slot": slot if hasattr(slot, "hour") else None,
            "bookings": bookings,
            "capacity": snapshot,
        },
    )


@viewer_required
def booking_detail(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related(
            "provider",
            "canonical_product",
            "canonical_variant",
        ),
        id=booking_id,
    )
    events = booking.events.select_related("raw_email", "created_by").order_by(
        "-created_at"
    )
    raw_emails = RawEmail.objects.filter(booking_events__booking=booking).distinct()
    return render(
        request,
        "bookings/detail.html",
        {
            "booking": booking,
            "events": events,
            "raw_emails": raw_emails,
            "can_edit_booking": can_mutate(request.user),
        },
    )


@operator_required
def booking_edit(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if request.method == "POST":
        original_values = {
            field: getattr(booking, field)
            for field in BookingEditForm.Meta.fields
            if field != "reason"
        }
        form = BookingEditForm(request.POST, instance=booking)
        if form.is_valid():
            changes = {
                field: form.cleaned_data[field]
                for field in form.fields
                if field != "reason"
                and form.cleaned_data.get(field) != original_values[field]
            }
            booking_for_update = Booking.objects.get(id=booking.id)
            apply_manual_override(
                booking=booking_for_update,
                changes=changes,
                user=request.user,
                reason=form.cleaned_data["reason"],
            )
            messages.success(request, "Booking updated.")
            next_url = _safe_next_url(request)
            if next_url:
                return redirect(next_url)
            return redirect("bookings:detail", booking_id=booking.id)
        messages.error(
            request, "Manual edit was not saved. Check the highlighted fields."
        )
    else:
        form = BookingEditForm(instance=booking)
    return render(
        request,
        "bookings/edit.html",
        {"booking": booking, "form": form},
    )


@admin_required
def product_settings(request):
    products = Product.objects.prefetch_related("variants").order_by(
        "canonical_name",
    )
    return render(
        request,
        "bookings/product_settings_list.html",
        {
            "products": products,
            "can_edit_products": True,
        },
    )


@admin_required
def product_settings_new(request):
    if request.method == "POST":
        if not can_mutate(request.user):
            raise PermissionDenied
        form = ProductSettingsForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, "Tour/activity created.")
            return redirect("settings_product_settings_edit", product_id=product.id)
    else:
        form = ProductSettingsForm()
    return render(
        request,
        "bookings/product_settings_form.html",
        {
            "product": None,
            "general_form": form,
            "active_tab": "general",
            "can_edit_products": True,
        },
    )


@admin_required
def product_settings_edit(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    active_tab = request.GET.get("tab", "general")
    selected_group = _selected_schedule_group(product, request)

    if request.method == "POST":
        if not can_mutate(request.user):
            raise PermissionDenied
        action = request.POST.get("action", "save_general")
        if action == "save_general":
            general_form = ProductSettingsForm(request.POST, instance=product)
            if general_form.is_valid():
                general_form.save()
                messages.success(request, "General settings saved.")
                return redirect(
                    "settings_product_settings_edit",
                    product_id=product.id,
                )
            schedule_form = _schedule_form_for_group(product, selected_group)
            active_tab = "general"
        elif action == "save_schedule":
            schedule_form = ProductScheduleForm(request.POST)
            general_form = ProductSettingsForm(instance=product)
            if schedule_form.is_valid():
                _replace_product_schedule(product, schedule_form, request.POST)
                messages.success(request, "Schedule saved.")
                url = reverse(
                    "settings_product_settings_edit",
                    kwargs={"product_id": product.id},
                )
                return redirect(f"{url}?tab=schedule")
            active_tab = "schedule"
        elif action == "delete_schedule":
            _delete_product_schedule(product, request.POST)
            messages.success(request, "Schedule deleted.")
            url = reverse(
                "settings_product_settings_edit",
                kwargs={"product_id": product.id},
            )
            return redirect(f"{url}?tab=schedule")
        else:
            messages.error(request, "Unsupported product settings action.")
            return redirect("settings_product_settings_edit", product_id=product.id)
    else:
        general_form = ProductSettingsForm(instance=product)
        schedule_form = _schedule_form_for_group(product, selected_group)

    schedule_groups = _product_schedule_groups(product)
    selected_group = _selected_schedule_group(product, request)
    current_group = _current_schedule_group(product)
    return render(
        request,
        "bookings/product_settings_form.html",
        {
            "product": product,
            "general_form": general_form,
            "schedule_form": schedule_form,
            "schedule_groups": schedule_groups,
            "selected_group": selected_group,
            "current_group": current_group,
            "weekly_schedule": _weekly_schedule(product, selected_group),
            "weekdays": WEEKDAYS,
            "active_tab": active_tab,
            "can_edit_products": True,
        },
    )


def _safe_next_url(request):
    next_url = request.POST.get("next") or request.GET.get("next")
    if not next_url:
        return ""
    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return ""


def _product_schedule_groups(product):
    groups = []
    seen = set()
    rules = (
        CapacityRule.objects.filter(product_variant__product=product)
        .select_related("product_variant")
        .order_by("date_from", "date_to", "schedule_name")
    )
    for rule in rules:
        key = _schedule_key(rule.schedule_name, rule.date_from, rule.date_to)
        if key in seen:
            continue
        seen.add(key)
        group = _schedule_group(rule.schedule_name, rule.date_from, rule.date_to)
        groups.append(group)
    if not groups:
        groups.append(_schedule_group("Default season", None, None))
    return groups


def _current_schedule_group(product):
    today = timezone.localdate()
    groups = _product_schedule_groups(product)
    for group in groups:
        starts_ok = not group["date_from"] or group["date_from"] <= today
        ends_ok = not group["date_to"] or group["date_to"] >= today
        if starts_ok and ends_ok:
            return group
    return groups[0]


def _selected_schedule_group(product, request):
    groups = _product_schedule_groups(product)
    if "schedule_name" not in request.GET:
        return _current_schedule_group(product)
    schedule_name = request.GET.get("schedule_name", "")
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    selected_key = _schedule_key(schedule_name, date_from, date_to)
    for group in groups:
        if group["key"] == selected_key:
            return group
    return _schedule_group(schedule_name or "New schedule", date_from, date_to)


def _schedule_form_for_group(product, group):
    rows = _weekly_schedule(product, group)
    duration = _product_duration_minutes(product)
    initial = {
        "schedule_name": group["schedule_name"],
        "date_from": group["date_from"],
        "date_to": group["date_to"],
        "duration_days": duration // 1440,
        "duration_hours": (duration % 1440) // 60,
        "duration_minutes": f"{duration % 60:02d}",
        "default_capacity": _product_default_capacity(product),
    }
    for field_name, _label, day_index in WEEKDAYS:
        initial[field_name] = "\n".join(
            f"{row['time'].strftime('%H:%M')},{row['capacity']}"
            for row in rows[day_index]
        )
    return ProductScheduleForm(initial=initial)


def _weekly_schedule(product, group):
    rows = {day_index: [] for _field, _label, day_index in WEEKDAYS}
    rules = _rules_for_schedule_group(product, group).order_by(
        "day_of_week",
        "slot_start_time",
        "capacity",
    )
    for rule in rules:
        if rule.day_of_week is None or rule.slot_start_time is None:
            continue
        rows.setdefault(rule.day_of_week, []).append(
            {
                "time": rule.slot_start_time,
                "capacity": rule.capacity,
                "variant": rule.product_variant,
            }
        )
    return rows


def _replace_product_schedule(product, form, post_data):
    original_group = _schedule_group(
        post_data.get("original_schedule_name", ""),
        _parse_date(post_data.get("original_date_from")),
        _parse_date(post_data.get("original_date_to")),
    )
    _rules_for_schedule_group(product, original_group).delete()

    schedule_name = form.cleaned_data["schedule_name"] or "Default season"
    date_from = form.cleaned_data["date_from"]
    date_to = form.cleaned_data["date_to"]
    duration_minutes = form.duration_minutes_total
    default_capacity = form.cleaned_data["default_capacity"]

    for variant in product.variants.all():
        variant.duration_minutes = duration_minutes
        if variant.default_capacity is None:
            variant.default_capacity = default_capacity
        variant.save(
            update_fields=["duration_minutes", "default_capacity", "updated_at"]
        )

    for day_index, entries in form.cleaned_data["parsed_rows"].items():
        for entry in entries:
            variant = _variant_for_time_slot(
                product,
                entry["time"],
                duration_minutes,
                entry["capacity"],
            )
            CapacityRule.objects.create(
                product_variant=variant,
                schedule_name=schedule_name,
                date_from=date_from,
                date_to=date_to,
                day_of_week=day_index,
                slot_start_time=entry["time"],
                slot_end_time=_end_time(entry["time"], duration_minutes),
                capacity=entry["capacity"],
                active=True,
            )


def _delete_product_schedule(product, post_data):
    group = _schedule_group(
        post_data.get("original_schedule_name", ""),
        _parse_date(post_data.get("original_date_from")),
        _parse_date(post_data.get("original_date_to")),
    )
    _rules_for_schedule_group(product, group).delete()


def _variant_for_time_slot(product, start_time, duration_minutes, capacity):
    variant_name = f"{start_time.strftime('%H:%M')} fixed slot"
    variant, _created = ProductVariant.objects.get_or_create(
        product=product,
        variant_name=variant_name,
        defaults={
            "slot_type": ProductVariant.SlotType.FIXED_TIME,
            "duration_minutes": duration_minutes,
            "default_capacity": capacity,
            "active": True,
        },
    )
    updates = []
    if variant.slot_type != ProductVariant.SlotType.FIXED_TIME:
        variant.slot_type = ProductVariant.SlotType.FIXED_TIME
        updates.append("slot_type")
    if variant.duration_minutes != duration_minutes:
        variant.duration_minutes = duration_minutes
        updates.append("duration_minutes")
    if variant.default_capacity != capacity:
        variant.default_capacity = capacity
        updates.append("default_capacity")
    if not variant.active:
        variant.active = True
        updates.append("active")
    if updates:
        variant.save(update_fields=[*updates, "updated_at"])
    return variant


def _rules_for_schedule_group(product, group):
    return CapacityRule.objects.filter(
        product_variant__product=product,
        schedule_name=group["schedule_name"],
        date_from=group["date_from"],
        date_to=group["date_to"],
    )


def _schedule_group(schedule_name, date_from, date_to):
    name = schedule_name or "Default season"
    return {
        "schedule_name": name,
        "date_from": date_from,
        "date_to": date_to,
        "key": _schedule_key(name, date_from, date_to),
        "url": f"?{urlencode({
            'tab': 'schedule',
            'schedule_name': name,
            'date_from': date_from.isoformat() if date_from else '',
            'date_to': date_to.isoformat() if date_to else '',
        })}",
    }


def _schedule_key(schedule_name, date_from, date_to):
    return (
        schedule_name or "Default season",
        date_from.isoformat() if date_from else "",
        date_to.isoformat() if date_to else "",
    )


def _product_duration_minutes(product):
    variant = product.variants.exclude(duration_minutes__isnull=True).first()
    return variant.duration_minutes if variant else 120


def _product_default_capacity(product):
    rule = CapacityRule.objects.filter(product_variant__product=product).first()
    if rule:
        return rule.capacity
    variant = product.variants.exclude(default_capacity__isnull=True).first()
    return variant.default_capacity if variant else 50


def _end_time(start_time, duration_minutes):
    if not duration_minutes:
        return None
    start = datetime.combine(datetime_date(2000, 1, 1), start_time)
    end = start + timedelta(minutes=duration_minutes)
    if end.date() != start.date():
        return None
    return end.time()


@viewer_required
def review_queue(request):
    issues = (
        ReviewQueueItem.objects.filter(status=ReviewQueueItem.Status.OPEN)
        .select_related("booking", "raw_email")
        .order_by("-created_at")
    )
    return render(
        request,
        "bookings/review_queue.html",
        {"issues": issues, "can_edit_queue": can_mutate(request.user)},
    )


@require_POST
@operator_required
def review_action(request, item_id):
    item = get_object_or_404(ReviewQueueItem, id=item_id)
    action = request.POST.get("action")
    if action == "resolve":
        item.status = ReviewQueueItem.Status.RESOLVED
    elif action == "ignore":
        item.status = ReviewQueueItem.Status.IGNORED
    else:
        messages.error(request, "Unsupported review action.")
        return redirect("review_queue")
    item.resolved_by = request.user
    item.resolved_at = timezone.now()
    item.save(update_fields=["status", "resolved_by", "resolved_at"])
    messages.success(request, "Review item updated.")
    return redirect("review_queue")


@viewer_required
def product_aliases(request):
    can_edit_aliases = can_mutate(request.user)
    review_item = None
    if request.GET.get("review_id"):
        review_item = get_object_or_404(ReviewQueueItem, id=request.GET["review_id"])

    if request.method == "POST":
        if not can_edit_aliases:
            raise PermissionDenied
        alias = None
        old_values = {}
        if request.POST.get("alias_id"):
            alias = get_object_or_404(ProductAlias, id=request.POST["alias_id"])
            old_values = _alias_audit_values(alias)
            form = ProductAliasForm(request.POST, instance=alias)
        else:
            form = ProductAliasForm(request.POST)
        if form.is_valid():
            alias = form.save()
            _record_alias_change(
                alias=alias,
                user=request.user,
                review_item=review_item,
                old_values=old_values,
            )
            messages.success(request, "Product alias saved.")
            return redirect("settings_provider_aliases")
        messages.error(request, "Alias was not saved. Check the highlighted fields.")
    else:
        initial = {}
        if review_item:
            initial = _alias_initial_from_review(review_item)
        form = ProductAliasForm(initial=initial)

    aliases = (
        ProductAlias.objects.select_related(
            "provider",
            "canonical_product",
            "canonical_variant",
        )
        .all()
        .order_by("provider__name", "raw_product_name")
    )
    return render(
        request,
        "bookings/aliases.html",
        {
            "aliases": aliases,
            "form": form,
            "review_item": review_item,
            "can_edit_aliases": can_edit_aliases,
        },
    )


@require_POST
@operator_required
def approve_alias(request, alias_id):
    alias = get_object_or_404(ProductAlias, id=alias_id)
    old_values = _alias_audit_values(alias)
    alias.approved = True
    alias.save(update_fields=["approved", "updated_at"])
    _record_alias_change(
        alias=alias,
        user=request.user,
        review_item=None,
        old_values=old_values,
    )
    messages.success(request, "Product alias approved.")
    return redirect("settings_provider_aliases")


@viewer_required
def raw_email_detail(request, raw_email_id):
    raw_email = get_object_or_404(
        RawEmail.objects.select_related("provider_detected"),
        id=raw_email_id,
    )
    return render(request, "bookings/raw_email_detail.html", {"raw_email": raw_email})


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_range_days(value):
    try:
        range_days = int(value or DEFAULT_RANGE_DAYS)
    except ValueError:
        return DEFAULT_RANGE_DAYS
    if range_days not in ALLOWED_RANGE_DAYS:
        return DEFAULT_RANGE_DAYS
    return range_days


def _date_range(start_date, days):
    return [start_date + timedelta(days=offset) for offset in range(days)]


def _calendar_filters(request):
    product = _parse_int(request.GET.get("product"))
    provider = _parse_int(request.GET.get("provider"))
    return {
        "query": request.GET.get("q", "").strip(),
        "category": request.GET.get("category", "").strip(),
        "product": product,
        "provider": provider,
        "show_cancelled": request.GET.get("show_cancelled", "1") != "0",
        "show_manual_review": request.GET.get("show_manual_review", "1") != "0",
    }


def _parse_int(value):
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _filter_calendar_bookings(queryset, filters):
    queryset = _filter_product_category(queryset, filters)
    if filters["provider"]:
        queryset = queryset.filter(provider_id=filters["provider"])
    if filters["query"]:
        queryset = _search_bookings(queryset, filters["query"])
    if not filters["show_cancelled"]:
        queryset = queryset.exclude(status=Booking.Status.CANCELLED)
    if not filters["show_manual_review"]:
        queryset = queryset.exclude(status=Booking.Status.MANUAL_REVIEW)
    return queryset


def _filter_product_category(queryset, filters):
    if filters["product"]:
        queryset = queryset.filter(canonical_product_id=filters["product"])
    if filters["category"]:
        queryset = queryset.filter(canonical_product__category=filters["category"])
    return queryset


def _requires_booking_match(filters):
    return bool(filters["query"] or filters["provider"])


def _search_bookings(queryset, query):
    return queryset.filter(
        Q(provider_booking_reference__icontains=query)
        | Q(provider_order_reference__icontains=query)
        | Q(lead_traveler_name__icontains=query)
        | Q(lead_traveler_phone__icontains=query)
        | Q(lead_traveler_email__icontains=query)
        | Q(provider__name__icontains=query)
        | Q(provider__code__icontains=query)
        | Q(raw_product_name__icontains=query)
        | Q(raw_option_name__icontains=query)
    )


def _capacity_status(remaining, pending):
    if remaining is None:
        return "unknown"
    if remaining < 0:
        return "over"
    if remaining == 0 and pending:
        return "waitlist"
    if remaining <= 3:
        return "tight"
    return "ok"


def _slot_url(selected_date, variant, slot, url_params=None):
    if not variant:
        return ""
    slot_value = slot.strftime("%H:%M") if hasattr(slot, "strftime") else slot or "open"
    url = reverse(
        "bookings:slot_detail",
        kwargs={
            "date": selected_date.isoformat(),
            "variant_id": variant.id,
            "time": slot_value,
        },
    )
    if url_params:
        return f"{url}?{urlencode(url_params)}"
    return url


def _capacity_rows(
    selected_date,
    filtered_bookings,
    *,
    filters,
    restrict_to_bookings=False,
    url_params=None,
):
    allowed_keys = {
        (booking.canonical_variant_id, _slot_for_capacity_view(booking))
        for booking in filtered_bookings
        if booking.canonical_variant_id
    }
    if restrict_to_bookings and not allowed_keys:
        return []
    rows = []
    seen_keys = set()
    for summary in get_daily_capacity_summary(selected_date):
        key = (summary["variant"].id, summary["slot"])
        if filters["product"] and summary["product"].id != filters["product"]:
            continue
        if filters["category"] and summary["product"].category != filters["category"]:
            continue
        if restrict_to_bookings and key not in allowed_keys:
            continue
        rows.append(
            _calendar_row(
                selected_date,
                summary,
                filtered_bookings,
                filters,
                url_params,
            )
        )
        seen_keys.add(key)

    for variant_id, slot in allowed_keys - seen_keys:
        variant = ProductVariant.objects.select_related("product").get(id=variant_id)
        if filters["product"] and variant.product_id != filters["product"]:
            continue
        if filters["category"] and variant.product.category != filters["category"]:
            continue
        summary = get_daily_capacity_summary(selected_date)
        fallback = next(
            (
                row
                for row in summary
                if row["variant"].id == variant_id and row["slot"] == slot
            ),
            None,
        )
        if fallback:
            rows.append(
                _calendar_row(
                    selected_date,
                    fallback,
                    filtered_bookings,
                    filters,
                    url_params,
                )
            )
            continue
        rows.append(
            _calendar_row(
                selected_date,
                get_capacity_for_variant_date_slot(variant, selected_date, slot),
                filtered_bookings,
                filters,
                url_params,
            )
        )
    return sorted(rows, key=_calendar_row_sort_key)


def _calendar_row(selected_date, summary, filtered_bookings, filters, url_params):
    matching_slot_bookings = [
        booking
        for booking in filtered_bookings
        if booking.canonical_variant_id == summary["variant"].id
        and _slot_for_capacity_view(booking) == summary["slot"]
    ]
    cancelled_count = sum(
        1
        for booking in matching_slot_bookings
        if booking.status == Booking.Status.CANCELLED
    )
    return {
        "date": selected_date,
        "product": summary["product"],
        "variant": summary["variant"],
        "slot": summary["slot"],
        "slot_label": summary["slot_label"],
        "confirmed": summary["confirmed_pax"],
        "pending": summary["pending_pax"],
        "manual_review": (
            summary["manual_review_pax"] if filters["show_manual_review"] else 0
        ),
        "cancelled_count": cancelled_count if filters["show_cancelled"] else 0,
        "capacity": summary["capacity"],
        "remaining": summary["remaining"],
        "status": _capacity_status(summary["remaining"], summary["pending_pax"]),
        "slot_url": _slot_url(
            selected_date,
            summary["variant"],
            summary["slot"],
            url_params,
        ),
    }


def _calendar_row_sort_key(row):
    slot = row["slot"]
    slot_sort = slot.strftime("%H:%M") if hasattr(slot, "strftime") else str(slot or "")
    return (
        row["date"],
        slot_sort,
        row["product"].canonical_name,
        row["variant"].variant_name,
    )


def _slot_for_capacity_view(booking):
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


def _base_calendar_params(selected_date, range_days, filters):
    params = {
        "date": selected_date.isoformat(),
        "range": str(range_days),
        "show_cancelled": "1" if filters["show_cancelled"] else "0",
        "show_manual_review": "1" if filters["show_manual_review"] else "0",
    }
    if filters["query"]:
        params["q"] = filters["query"]
    if filters["category"]:
        params["category"] = filters["category"]
    if filters["product"]:
        params["product"] = str(filters["product"])
    if filters["provider"]:
        params["provider"] = str(filters["provider"])
    return params


def _calendar_url(base_params, **overrides):
    params = base_params.copy()
    for key, value in overrides.items():
        if key == "date" and hasattr(value, "isoformat"):
            value = value.isoformat()
        if value in {None, ""}:
            params.pop(key, None)
        else:
            params[key] = str(value)
    return f"{reverse('bookings:daily')}?{urlencode(params)}"


def _mini_calendar(selected_date, base_params):
    calendar = Calendar(firstweekday=0)
    weeks = []
    for week in calendar.monthdatescalendar(selected_date.year, selected_date.month):
        weeks.append(
            [
                {
                    "date": day,
                    "day": day.day,
                    "is_current_month": day.month == selected_date.month,
                    "is_selected": day == selected_date,
                    "url": _calendar_url(base_params, date=day),
                }
                for day in week
            ]
        )
    return {
        "month_label": selected_date.strftime("%B %Y"),
        "weeks": weeks,
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "previous_month_url": _calendar_url(
            base_params,
            date=(selected_date.replace(day=1) - timedelta(days=1)).replace(day=1),
        ),
        "next_month_url": _calendar_url(
            base_params,
            date=_next_month(selected_date),
        ),
    }


def _next_month(value):
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1, day=1)
    return value.replace(month=value.month + 1, day=1)


def _category_options():
    return (
        Product.objects.filter(active=True)
        .exclude(category="")
        .order_by("category")
        .values_list("category", flat=True)
        .distinct()
    )


def _calendar_day_label(service_date):
    return service_date.strftime("%A, %d %B %Y")


def _parse_slot(value):
    if value in {"open", "", None}:
        return None
    if value in ProductVariant.SlotType.values:
        return value
    return datetime.strptime(value, "%H:%M").time()


def _record_alias_change(*, alias, user, review_item, old_values=None):
    booking = review_item.booking if review_item else None
    BookingEvent.objects.create(
        booking=booking,
        event_type=BookingEvent.EventType.PRODUCT_ALIAS_CHANGED,
        source=BookingEvent.Source.MANUAL,
        old_values=old_values or {},
        new_values={
            "alias_id": alias.id,
            "provider": alias.provider.code,
            "raw_product_name": alias.raw_product_name,
            "raw_option_name": alias.raw_option_name,
            "canonical_product": alias.canonical_product.canonical_name,
            "canonical_variant": (
                alias.canonical_variant.variant_name
                if alias.canonical_variant
                else None
            ),
            "approved": alias.approved,
        },
        created_by=user,
    )


def _alias_audit_values(alias):
    return {
        "alias_id": alias.id,
        "provider": alias.provider.code,
        "raw_product_name": alias.raw_product_name,
        "raw_option_name": alias.raw_option_name,
        "canonical_product": alias.canonical_product.canonical_name,
        "canonical_variant": (
            alias.canonical_variant.variant_name if alias.canonical_variant else None
        ),
        "approved": alias.approved,
    }


def _alias_initial_from_review(review_item):
    booking = review_item.booking
    if not booking:
        return {}
    return {
        "provider": booking.provider,
        "raw_product_name": booking.raw_product_name,
        "raw_option_name": booking.raw_option_name,
        "provider_product_code": booking.provider_product_code,
        "provider_option_code": booking.provider_option_code,
        "approved": True,
    }
