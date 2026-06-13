from calendar import Calendar
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
    is_admin,
    operator_required,
    viewer_required,
)
from apps.bookings.services import (
    apply_manual_override,
    capacity_snapshot,
    get_daily_capacity_summary,
    get_slot_bookings,
    slot_label,
)
from apps.ingestion.models import RawEmail

from .forms import (
    ActivityPeopleRuleForm,
    ActivityScheduleExceptionForm,
    ActivityScheduleSectionForm,
    BookingEditForm,
    ProviderAliasForm,
    TourActivityForm,
)
from .models import (
    ActivityPeopleRule,
    ActivitySchedule,
    ActivityScheduleException,
    ActivityScheduleSlot,
    Booking,
    BookingEvent,
    Provider,
    ProviderAlias,
    ReviewQueueItem,
    TourActivity,
)

ALLOWED_RANGE_DAYS = {1, 3, 7, 14}
DEFAULT_RANGE_DAYS = 1


@viewer_required
def daily_operations(request):
    selected_date = _parse_date(request.GET.get("date")) or timezone.localdate()
    range_days = _parse_range_days(request.GET.get("range"))
    query = request.GET.get("q", "").strip()
    filters = _calendar_filters(request)
    date_range = _date_range(selected_date, range_days)
    base_bookings = (
        Booking.objects.filter(active_travel_date__in=date_range)
        .select_related("provider", "activity", "schedule_slot")
        .order_by(
            "active_travel_date",
            "activity__name",
            "schedule_slot__start_time",
            "provider_booking_reference",
        )
    )
    matching_bookings = _filter_calendar_bookings(base_bookings, filters)
    restrict_to_bookings = _requires_booking_match(filters)
    base_params = _base_calendar_params(selected_date, range_days, filters)
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
        "range_options": [
            {
                "days": days,
                "active": days == range_days,
                "url": _calendar_url(base_params, range=days),
            }
            for days in sorted(ALLOWED_RANGE_DAYS)
        ],
        "query": query,
        "filters": filters,
        "day_sections": day_sections,
        "rows": day_sections[0]["rows"] if day_sections else [],
        "mini_calendar": _mini_calendar(selected_date, base_params),
        "activity_options": TourActivity.objects.filter(active=True).order_by("name"),
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
def slot_detail(request, date, slot_id):
    selected_date = _parse_date(date) or timezone.localdate()
    slot = get_object_or_404(
        ActivityScheduleSlot.objects.select_related("schedule", "schedule__activity"),
        id=slot_id,
    )
    bookings = get_slot_bookings(selected_date, slot)
    snapshot = capacity_snapshot(schedule_slot=slot, service_date=selected_date)
    return render(
        request,
        "bookings/slot_detail.html",
        {
            "selected_date": selected_date,
            "slot": slot,
            "activity": slot.schedule.activity,
            "bookings": bookings,
            "capacity": snapshot,
        },
    )


@viewer_required
def booking_detail(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related(
            "provider",
            "activity",
            "schedule_slot",
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
def tour_activity_list(request):
    activities = (
        TourActivity.objects.prefetch_related(
            "schedules",
            "schedules__slots",
            "provider_aliases",
        )
        .select_related("people_rule")
        .order_by("name")
    )
    return render(
        request,
        "bookings/tour_activity_list.html",
        {"activities": activities, "can_edit_activities": True},
    )


@admin_required
def tour_activity_new(request):
    if request.method == "POST":
        if not can_mutate(request.user):
            raise PermissionDenied
        form = TourActivityForm(request.POST)
        if form.is_valid():
            activity = form.save()
            ActivityPeopleRule.objects.create(activity=activity)
            messages.success(request, "Tour/activity created.")
            return redirect("settings_tour_activity_detail", activity_id=activity.id)
    else:
        form = TourActivityForm()
    return render(
        request,
        "bookings/tour_activity_detail.html",
        _activity_context(
            request,
            activity=None,
            active_tab="general",
            general_form=form,
        ),
    )


@admin_required
def tour_activity_detail(request, activity_id):
    activity = get_object_or_404(TourActivity, id=activity_id)
    active_tab = request.GET.get("tab", "general")
    people_rule, _created = ActivityPeopleRule.objects.get_or_create(activity=activity)

    if request.method == "POST":
        if not can_mutate(request.user):
            raise PermissionDenied
        action = request.POST.get("action", "save_general")
        if action == "save_general":
            form = TourActivityForm(request.POST, instance=activity)
            if form.is_valid():
                form.save()
                messages.success(request, "General settings saved.")
                return redirect(
                    "settings_tour_activity_detail", activity_id=activity.id
                )
            active_tab = "general"
            return render(
                request,
                "bookings/tour_activity_detail.html",
                _activity_context(
                    request,
                    activity=activity,
                    active_tab=active_tab,
                    general_form=form,
                ),
            )
        if action in {"save_current_schedule", "save_other_schedule"}:
            schedule_kind = (
                ActivitySchedule.ScheduleKind.CURRENT
                if action == "save_current_schedule"
                else ActivitySchedule.ScheduleKind.OTHER
            )
            instance = _schedule_for_kind(activity, schedule_kind)
            form = ActivityScheduleSectionForm(
                request.POST,
                instance=instance,
                schedule_kind=schedule_kind,
                activity=activity,
                prefix=schedule_kind,
            )
            if form.is_valid():
                form.save(activity=activity)
                messages.success(request, "Schedule saved.")
                return _redirect_activity_tab(activity, "scheduling")
            active_tab = "scheduling"
            return render(
                request,
                "bookings/tour_activity_detail.html",
                _activity_context(
                    request,
                    activity=activity,
                    active_tab=active_tab,
                    schedule_forms={schedule_kind: form},
                ),
            )
        if action == "save_schedule_exception":
            schedule = get_object_or_404(
                ActivitySchedule,
                id=request.POST.get("schedule_id"),
                activity=activity,
            )
            form = ActivityScheduleExceptionForm(request.POST, schedule=schedule)
            if form.is_valid():
                form.save()
                messages.success(request, "Schedule exception saved.")
                return _redirect_activity_tab(activity, "scheduling")
            active_tab = "scheduling"
            return render(
                request,
                "bookings/tour_activity_detail.html",
                _activity_context(
                    request,
                    activity=activity,
                    active_tab=active_tab,
                    exception_forms={schedule.id: form},
                ),
            )
        if action == "delete_schedule_exception":
            exception = get_object_or_404(
                ActivityScheduleException,
                id=request.POST.get("exception_id"),
                schedule__activity=activity,
            )
            exception.delete()
            messages.success(request, "Schedule exception deleted.")
            return _redirect_activity_tab(activity, "scheduling")
        if action == "save_people":
            form = ActivityPeopleRuleForm(request.POST, instance=people_rule)
            if form.is_valid():
                form.save()
                messages.success(request, "People settings saved.")
                return _redirect_activity_tab(activity, "people")
            active_tab = "people"
            return render(
                request,
                "bookings/tour_activity_detail.html",
                _activity_context(
                    request,
                    activity=activity,
                    active_tab=active_tab,
                    people_form=form,
                ),
            )
        if action == "save_alias":
            form = ProviderAliasForm(request.POST, activity=activity)
            if form.is_valid():
                alias = form.save()
                _record_alias_change(alias=alias, user=request.user, old_values={})
                messages.success(request, "Provider alias saved.")
                return _redirect_activity_tab(activity, "general")
            active_tab = "general"
            return render(
                request,
                "bookings/tour_activity_detail.html",
                _activity_context(
                    request,
                    activity=activity,
                    active_tab=active_tab,
                    alias_form=form,
                ),
            )
        messages.error(request, "Unsupported activity action.")
        return redirect("settings_tour_activity_detail", activity_id=activity.id)

    return render(
        request,
        "bookings/tour_activity_detail.html",
        _activity_context(request, activity=activity, active_tab=active_tab),
    )


@viewer_required
def provider_aliases(request):
    can_edit_aliases = is_admin(request.user)
    review_item = None
    if request.GET.get("review_id"):
        review_item = get_object_or_404(ReviewQueueItem, id=request.GET["review_id"])

    if request.method == "POST":
        if not can_edit_aliases:
            raise PermissionDenied
        alias = None
        old_values = {}
        if request.POST.get("alias_id"):
            alias = get_object_or_404(ProviderAlias, id=request.POST["alias_id"])
            old_values = _alias_audit_values(alias)
            form = ProviderAliasForm(request.POST, instance=alias)
        else:
            form = ProviderAliasForm(request.POST)
        if form.is_valid():
            alias = form.save()
            _record_alias_change(alias=alias, user=request.user, old_values=old_values)
            messages.success(request, "Provider alias saved.")
            return redirect("settings_provider_aliases")
        messages.error(request, "Alias was not saved. Check the highlighted fields.")
    else:
        initial = {}
        if review_item:
            initial = _alias_initial_from_review(review_item)
        form = ProviderAliasForm(initial=initial)

    aliases = (
        ProviderAlias.objects.select_related(
            "provider",
            "linked_activity",
            "linked_schedule",
            "linked_slot",
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
@admin_required
def approve_alias(request, alias_id):
    alias = get_object_or_404(ProviderAlias, id=alias_id)
    old_values = _alias_audit_values(alias)
    alias.approved = True
    alias.save(update_fields=["approved", "updated_at"])
    _record_alias_change(alias=alias, user=request.user, old_values=old_values)
    messages.success(request, "Provider alias approved.")
    return redirect("settings_provider_aliases")


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
def raw_email_detail(request, raw_email_id):
    raw_email = get_object_or_404(
        RawEmail.objects.select_related("provider_detected"),
        id=raw_email_id,
    )
    return render(request, "bookings/raw_email_detail.html", {"raw_email": raw_email})


def _activity_context(
    request,
    *,
    activity,
    active_tab,
    general_form=None,
    schedule_forms=None,
    people_form=None,
    alias_form=None,
    exception_forms=None,
):
    current_schedule = (
        _schedule_for_kind(
            activity,
            ActivitySchedule.ScheduleKind.CURRENT,
        )
        if activity
        else None
    )
    other_schedule = (
        _schedule_for_kind(
            activity,
            ActivitySchedule.ScheduleKind.OTHER,
        )
        if activity
        else None
    )
    schedule_forms = schedule_forms or {}
    exception_forms = exception_forms or {}
    return {
        "activity": activity,
        "active_tab": active_tab,
        "general_form": general_form
        or (TourActivityForm(instance=activity) if activity else None),
        "current_schedule_form": schedule_forms.get(
            ActivitySchedule.ScheduleKind.CURRENT
        )
        or ActivityScheduleSectionForm(
            instance=current_schedule,
            schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
            activity=activity,
            prefix=ActivitySchedule.ScheduleKind.CURRENT,
        ),
        "other_schedule_form": schedule_forms.get(ActivitySchedule.ScheduleKind.OTHER)
        or ActivityScheduleSectionForm(
            instance=other_schedule,
            schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
            activity=activity,
            prefix=ActivitySchedule.ScheduleKind.OTHER,
        ),
        "people_form": people_form
        or (
            ActivityPeopleRuleForm(instance=activity.people_rule)
            if activity and hasattr(activity, "people_rule")
            else ActivityPeopleRuleForm()
        ),
        "alias_form": alias_form or ProviderAliasForm(activity=activity),
        "provider_aliases": (
            activity.provider_aliases.select_related("provider", "linked_slot")
            if activity
            else []
        ),
        "current_schedule": current_schedule,
        "other_schedule": other_schedule,
        "current_exception_form": exception_forms.get(
            current_schedule.id if current_schedule else None
        )
        or ActivityScheduleExceptionForm(schedule=current_schedule),
        "other_exception_form": exception_forms.get(
            other_schedule.id if other_schedule else None
        )
        or ActivityScheduleExceptionForm(schedule=other_schedule),
        "can_edit_activities": can_mutate(request.user),
    }


def _schedule_for_kind(activity, schedule_kind):
    if not activity:
        return None
    return (
        activity.schedules.filter(schedule_kind=schedule_kind)
        .order_by("priority", "id")
        .first()
    )


def _redirect_activity_tab(activity, tab):
    url = reverse("settings_tour_activity_detail", kwargs={"activity_id": activity.id})
    return redirect(f"{url}?tab={tab}")


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
    return {
        "query": request.GET.get("q", "").strip(),
        "category": request.GET.get("category", "").strip(),
        "activity": _parse_int(request.GET.get("activity")),
        "provider": _parse_int(request.GET.get("provider")),
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
    if filters["activity"]:
        queryset = queryset.filter(activity_id=filters["activity"])
    if filters["category"]:
        queryset = queryset.filter(activity__category=filters["category"])
    if filters["provider"]:
        queryset = queryset.filter(provider_id=filters["provider"])
    if filters["query"]:
        queryset = _search_bookings(queryset, filters["query"])
    if not filters["show_cancelled"]:
        queryset = queryset.exclude(status=Booking.Status.CANCELLED)
    if not filters["show_manual_review"]:
        queryset = queryset.exclude(status=Booking.Status.MANUAL_REVIEW)
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


def _slot_url(selected_date, slot, url_params=None):
    if not slot:
        return ""
    url = reverse(
        "bookings:slot_detail",
        kwargs={"date": selected_date.isoformat(), "slot_id": slot.id},
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
    allowed_slot_ids = {
        booking.schedule_slot_id
        for booking in filtered_bookings
        if booking.schedule_slot_id
    }
    if restrict_to_bookings and not allowed_slot_ids:
        return []
    rows = []
    seen_slot_ids = set()
    for summary in get_daily_capacity_summary(selected_date):
        slot = summary["slot"]
        if filters["activity"] and summary["activity"].id != filters["activity"]:
            continue
        if filters["category"] and summary["activity"].category != filters["category"]:
            continue
        if restrict_to_bookings and (not slot or slot.id not in allowed_slot_ids):
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
        if slot:
            seen_slot_ids.add(slot.id)

    for slot_id in allowed_slot_ids - seen_slot_ids:
        slot = ActivityScheduleSlot.objects.select_related(
            "schedule", "schedule__activity"
        ).get(id=slot_id)
        if filters["activity"] and slot.schedule.activity_id != filters["activity"]:
            continue
        if (
            filters["category"]
            and slot.schedule.activity.category != filters["category"]
        ):
            continue
        rows.append(
            _calendar_row(
                selected_date,
                _summary_for_slot(selected_date, slot),
                filtered_bookings,
                filters,
                url_params,
            )
        )
    return sorted(rows, key=_calendar_row_sort_key)


def _summary_for_slot(selected_date, slot):
    from apps.bookings.services import get_capacity_for_slot_date

    return get_capacity_for_slot_date(slot, selected_date)


def _calendar_row(selected_date, summary, filtered_bookings, filters, url_params):
    slot = summary["slot"]
    matching_slot_bookings = [
        booking
        for booking in filtered_bookings
        if slot and booking.schedule_slot_id == slot.id
    ]
    cancelled_count = sum(
        1
        for booking in matching_slot_bookings
        if booking.status == Booking.Status.CANCELLED
    )
    return {
        "date": selected_date,
        "activity": summary["activity"],
        "slot": slot,
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
        "slot_url": _slot_url(selected_date, slot, url_params),
    }


def _calendar_row_sort_key(row):
    slot = row["slot"]
    return (
        row["date"],
        slot.start_time if slot else datetime.max.time(),
        row["activity"].name,
    )


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
    if filters["activity"]:
        params["activity"] = str(filters["activity"])
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
        TourActivity.objects.filter(active=True)
        .exclude(category="")
        .order_by("category")
        .values_list("category", flat=True)
        .distinct()
    )


def _calendar_day_label(service_date):
    return service_date.strftime("%A, %d %B %Y")


def _record_alias_change(*, alias, user, old_values=None):
    BookingEvent.objects.create(
        booking=None,
        event_type=BookingEvent.EventType.PROVIDER_ALIAS_CHANGED,
        source=BookingEvent.Source.MANUAL,
        old_values=old_values or {},
        new_values=_alias_audit_values(alias),
        created_by=user,
    )


def _alias_audit_values(alias):
    return {
        "alias_id": alias.id,
        "provider": alias.provider.code,
        "raw_product_name": alias.raw_product_name,
        "raw_option_name": alias.raw_option_name,
        "linked_activity": alias.linked_activity.name,
        "linked_schedule": (
            alias.linked_schedule.name if alias.linked_schedule else None
        ),
        "linked_slot": slot_label(alias.linked_slot) if alias.linked_slot else None,
        "approved": alias.approved,
        "needs_manual_confirmation": alias.needs_manual_confirmation,
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
