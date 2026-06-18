from calendar import Calendar
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
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
from apps.bookings.display import (
    activity_label,
    clean_text,
    customer_label,
    email_subject_label,
    parse_error_label,
    provider_label,
    received_label,
    reference_label,
    short_datetime_label,
    status_label,
    traveler_count_label,
)
from apps.bookings.services import (
    apply_manual_override,
    capacity_snapshot,
    get_daily_capacity_summary,
    get_slot_bookings,
    review_issue_is_obsolete_for_context,
    slot_label,
)
from apps.ingestion.models import RawEmail
from apps.ingestion.services import process_raw_email

from .forms import (
    ActivityPeopleRuleForm,
    BookingEditForm,
    ChangeSeatsForm,
    DurationForm,
    OperatorAdditionalTimeForm,
    OperatorBlockedDateForm,
    OperatorScheduleExceptionForm,
    OperatorScheduleSectionForm,
    OperatorScheduleSlotForm,
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
def booking_list(request):
    query = request.GET.get("q", "").strip()
    queryset = Booking.objects.select_related(
        "provider", "activity", "schedule_slot"
    ).order_by("-active_travel_date", "-created_at")[:200]
    if query:
        queryset = _search_bookings(
            Booking.objects.select_related("provider", "activity", "schedule_slot"),
            query,
        ).order_by("-active_travel_date", "-created_at")[:200]
    rows = [
        {
            "booking": booking,
            "provider": provider_label(booking.provider),
            "reference": reference_label(booking),
            "customer": customer_label(booking),
            "activity": activity_label(booking),
            "datetime": short_datetime_label(booking),
            "participants": traveler_count_label(booking),
            "status": status_label(booking),
        }
        for booking in queryset
    ]
    return render(
        request,
        "bookings/list.html",
        {
            "query": query,
            "rows": rows,
        },
    )


@viewer_required
def daily_operations(request):
    selected_date = _parse_date(request.GET.get("date")) or timezone.localdate()
    range_days = _parse_range_days(request.GET.get("range"))
    query = request.GET.get("q", "").strip()
    view_mode = request.GET.get("view", "rows")
    if view_mode not in {"rows", "boxes"}:
        view_mode = "rows"
    filters = _calendar_filters(request)
    filters["view"] = view_mode
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
        "view_mode": view_mode,
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
            view=view_mode,
        ),
        "today_url": _calendar_url(
            base_params,
            date=timezone.localdate(),
            view=view_mode,
        ),
        "next_url": _calendar_url(
            base_params,
            date=selected_date + timedelta(days=range_days),
            view=view_mode,
        ),
        "rows_view_url": _calendar_url(base_params, view="rows"),
        "boxes_view_url": _calendar_url(base_params, view="boxes"),
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


@viewer_required
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
        {"activities": activities, "can_edit_activities": is_admin(request.user)},
    )


@admin_required
def tour_activity_new(request):
    if request.method == "POST":
        if not is_admin(request.user):
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


@viewer_required
def tour_activity_detail(request, activity_id):
    activity = get_object_or_404(TourActivity, id=activity_id)
    active_tab = request.GET.get("tab", "general")
    people_rule, _created = ActivityPeopleRule.objects.get_or_create(activity=activity)

    if request.method == "POST":
        if not is_admin(request.user):
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
            if schedule_kind == ActivitySchedule.ScheduleKind.OTHER:
                instance = None
                if request.POST.get("schedule_id"):
                    instance = get_object_or_404(
                        ActivitySchedule,
                        id=request.POST["schedule_id"],
                        activity=activity,
                        schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
                    )
            form = OperatorScheduleSectionForm(
                request.POST,
                instance=instance,
                schedule_kind=schedule_kind,
                activity=activity,
                prefix=schedule_kind,
            )
            if form.is_valid():
                schedule = form.save(activity=activity)
                if instance is None and request.POST.get("copy_source_id"):
                    source_schedule = get_object_or_404(
                        ActivitySchedule,
                        id=request.POST["copy_source_id"],
                        activity=activity,
                    )
                    _copy_schedule_slots(source_schedule, schedule)
                if (
                    schedule.schedule_kind == ActivitySchedule.ScheduleKind.OTHER
                    and schedule.priority == 100
                ):
                    schedule.priority = _next_schedule_priority(activity)
                    schedule.save(update_fields=["priority", "updated_at"])
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
                    editor_type="schedule",
                    editor_schedule=instance,
                    schedule_copy_source_id=request.POST.get("copy_source_id", ""),
                ),
            )
        if action == "copy_current_schedule":
            current_schedule = _schedule_for_kind(
                activity, ActivitySchedule.ScheduleKind.CURRENT
            )
            if current_schedule:
                _copy_schedule_to_other(current_schedule)
                messages.success(request, "Current schedule copied.")
            return _redirect_activity_tab(activity, "scheduling")
        if action == "copy_existing_schedule":
            source_schedule = get_object_or_404(
                ActivitySchedule,
                id=request.POST.get("schedule_id"),
                activity=activity,
            )
            _copy_schedule_to_other(source_schedule)
            messages.success(request, "Schedule copied.")
            return _redirect_activity_tab(activity, "scheduling")
        if action == "copy_schedule_day":
            current_schedule = _schedule_for_kind(
                activity, ActivitySchedule.ScheduleKind.CURRENT
            )
            if current_schedule:
                copied = _copy_schedule_day(
                    current_schedule,
                    request.POST.get("from_day"),
                    request.POST.getlist("to_days"),
                )
                messages.success(request, f"Copied schedule to {copied} day(s).")
            return _redirect_activity_tab(activity, "scheduling")
        if action == "new_change_schedule":
            current_schedule = _schedule_for_kind(
                activity, ActivitySchedule.ScheduleKind.CURRENT
            )
            source_id = request.POST.get("copy_source", "")
            initial = {
                "schedule_status": "active",
                "timezone": current_schedule.timezone if current_schedule else "",
            }
            if source_id:
                source_schedule = get_object_or_404(
                    ActivitySchedule,
                    id=source_id,
                    activity=activity,
                )
                initial.update(
                    {
                        "schedule_name": source_schedule.name,
                        "repeat_days": [
                            str(day) for day in source_schedule.days_of_week or []
                        ],
                        "timezone": source_schedule.timezone,
                        "notes": source_schedule.notes,
                    }
                )
            form = OperatorScheduleSectionForm(
                schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
                activity=activity,
                prefix=ActivitySchedule.ScheduleKind.OTHER,
                initial=initial,
            )
            return render(
                request,
                "bookings/tour_activity_detail.html",
                _activity_context(
                    request,
                    activity=activity,
                    active_tab="scheduling",
                    schedule_forms={ActivitySchedule.ScheduleKind.OTHER: form},
                    editor_type="schedule",
                    editor_schedule=None,
                    schedule_copy_source_id=source_id,
                ),
            )
        if action == "save_duration":
            current_schedule = _schedule_for_kind(
                activity, ActivitySchedule.ScheduleKind.CURRENT
            )
            form = DurationForm(request.POST)
            if form.is_valid() and current_schedule:
                duration_minutes = form.cleaned_data["duration_minutes"]
                for slot in current_schedule.slots.filter(active=True):
                    slot.duration_minutes = duration_minutes
                    slot.end_time = _slot_end_time(
                        slot.start_time,
                        duration_minutes,
                    )
                    slot.save(
                        update_fields=[
                            "duration_minutes",
                            "end_time",
                            "updated_at",
                        ]
                    )
                messages.success(request, "Duration saved.")
                return _redirect_activity_tab(activity, "scheduling")
            return render(
                request,
                "bookings/tour_activity_detail.html",
                _activity_context(
                    request,
                    activity=activity,
                    active_tab="scheduling",
                    duration_form=form,
                ),
            )
        if action == "delete_schedule":
            schedule = get_object_or_404(
                ActivitySchedule,
                id=request.POST.get("schedule_id"),
                activity=activity,
                schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
            )
            schedule.delete()
            messages.success(request, "Schedule deleted.")
            return _redirect_activity_tab(activity, "scheduling")
        if action == "change_all_seats":
            schedule = get_object_or_404(
                ActivitySchedule,
                id=request.POST.get("schedule_id"),
                activity=activity,
            )
            form = ChangeSeatsForm(request.POST)
            if form.is_valid():
                schedule.slots.update(capacity=form.cleaned_data["capacity"])
                messages.success(request, "Seats updated for all times.")
                warnings = _overbooked_schedule_warnings(schedule)
                if warnings:
                    messages.warning(
                        request,
                        "Capacity is below active bookings for: "
                        + "; ".join(warnings[:5]),
                    )
                return _redirect_activity_tab(activity, "scheduling")
            return render(
                request,
                "bookings/tour_activity_detail.html",
                _activity_context(
                    request,
                    activity=activity,
                    active_tab="scheduling",
                    change_seats_form=form,
                    editor_type="change_seats",
                ),
            )
        if action == "save_time_slot":
            schedule = get_object_or_404(
                ActivitySchedule,
                id=request.POST.get("schedule_id"),
                activity=activity,
            )
            slot = None
            if request.POST.get("slot_id"):
                slot = get_object_or_404(
                    ActivityScheduleSlot,
                    id=request.POST["slot_id"],
                    schedule=schedule,
                )
            form = OperatorScheduleSlotForm(
                request.POST,
                instance=slot,
                schedule=schedule,
            )
            if form.is_valid():
                form.save(schedule=schedule)
                messages.success(request, "Available time saved.")
                return _redirect_activity_tab(activity, "scheduling")
            messages.error(
                request,
                "Available time was not saved. Check the highlighted fields.",
            )
            return render(
                request,
                "bookings/tour_activity_detail.html",
                _activity_context(
                    request,
                    activity=activity,
                    active_tab="scheduling",
                    slot_forms={schedule.id if slot is None else slot.id: form},
                    editor_type="slot",
                    editor_schedule=schedule,
                    editor_slot=slot,
                ),
            )
        if action == "deactivate_time_slot":
            slot = get_object_or_404(
                ActivityScheduleSlot,
                id=request.POST.get("slot_id"),
                schedule__activity=activity,
            )
            _deactivate_slot_for_day(slot, request.POST.get("slot_days"))
            messages.success(request, "Available time deactivated.")
            return _redirect_activity_tab(activity, "scheduling")
        if action == "save_additional_time":
            schedule = get_object_or_404(
                ActivitySchedule,
                id=request.POST.get("schedule_id"),
                activity=activity,
            )
            exception = None
            if request.POST.get("exception_id"):
                exception = get_object_or_404(
                    ActivityScheduleException,
                    id=request.POST["exception_id"],
                    schedule=schedule,
                    exception_type=ActivityScheduleException.ExceptionType.EXTRA_SLOT,
                )
            form = OperatorAdditionalTimeForm(
                request.POST,
                schedule=schedule,
                instance=exception,
            )
            if form.is_valid():
                form.save()
                messages.success(request, "Additional time saved.")
                return _redirect_activity_tab(activity, "scheduling")
            return render(
                request,
                "bookings/tour_activity_detail.html",
                _activity_context(
                    request,
                    activity=activity,
                    active_tab="scheduling",
                    additional_time_form=form,
                    editor_type="additional_time",
                    editor_exception=exception,
                ),
            )
        if action == "save_blocked_date":
            schedule = get_object_or_404(
                ActivitySchedule,
                id=request.POST.get("schedule_id"),
                activity=activity,
            )
            exception = None
            if request.POST.get("exception_id"):
                exception = get_object_or_404(
                    ActivityScheduleException,
                    id=request.POST["exception_id"],
                    schedule=schedule,
                    exception_type__in=[
                        ActivityScheduleException.ExceptionType.BLOCKED,
                        ActivityScheduleException.ExceptionType.CLOSED,
                    ],
                )
            form = OperatorBlockedDateForm(
                request.POST,
                schedule=schedule,
                instance=exception,
            )
            if form.is_valid():
                form.save()
                messages.success(request, "Blocked date saved.")
                return _redirect_activity_tab(activity, "scheduling")
            return render(
                request,
                "bookings/tour_activity_detail.html",
                _activity_context(
                    request,
                    activity=activity,
                    active_tab="scheduling",
                    blocked_date_form=form,
                    editor_type="blocked_date",
                    editor_exception=exception,
                ),
            )
        if action in {"save_special_date", "save_schedule_exception"}:
            schedule = get_object_or_404(
                ActivitySchedule,
                id=request.POST.get("schedule_id"),
                activity=activity,
            )
            exception = None
            if request.POST.get("special_date_id"):
                exception = get_object_or_404(
                    ActivityScheduleException,
                    id=request.POST["special_date_id"],
                    schedule=schedule,
                )
            form = OperatorScheduleExceptionForm(
                request.POST,
                schedule=schedule,
                instance=exception,
            )
            if form.is_valid():
                form.save()
                messages.success(request, "Special date saved.")
                return _redirect_activity_tab(activity, "scheduling")
            return render(
                request,
                "bookings/tour_activity_detail.html",
                _activity_context(
                    request,
                    activity=activity,
                    active_tab="scheduling",
                ),
            )
        if action in {"deactivate_special_date", "delete_schedule_exception"}:
            exception = get_object_or_404(
                ActivityScheduleException,
                id=request.POST.get("exception_id"),
                schedule__activity=activity,
            )
            exception.active = False
            exception.save(update_fields=["active", "updated_at"])
            messages.success(request, "Special date deactivated.")
            return _redirect_activity_tab(activity, "scheduling")
        if action == "save_people":
            people_data = request.POST.copy()
            if "capacity_note" not in people_data:
                people_data["capacity_note"] = people_rule.capacity_note
            form = ActivityPeopleRuleForm(people_data, instance=people_rule)
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
        else:
            alias = _provider_alias_from_post(request.POST)
        if alias:
            old_values = _alias_audit_values(alias)
        form = ProviderAliasForm(request.POST, instance=alias)
        if form.is_valid():
            try:
                alias = form.save()
            except IntegrityError:
                form.add_error(
                    None,
                    "An alias already exists for this provider product. "
                    "Refresh the page and update the existing mapping.",
                )
            else:
                _record_alias_change(
                    alias=alias,
                    user=request.user,
                    old_values=old_values,
                )
                if review_item and review_item.raw_email_id:
                    process_raw_email(review_item.raw_email_id)
                    messages.success(
                        request,
                        "Provider alias saved and the source email was reprocessed.",
                    )
                    return redirect("inbox")
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
    open_issues = (
        ReviewQueueItem.objects.filter(status=ReviewQueueItem.Status.OPEN)
        .select_related("booking", "raw_email")
        .order_by("-created_at")
    )
    issues_by_raw_email = {}
    for issue in open_issues:
        if issue.raw_email_id:
            issues_by_raw_email.setdefault(issue.raw_email_id, []).append(issue)

    raw_emails = (
        RawEmail.objects.select_related("provider_detected")
        .prefetch_related("booking_events__booking__activity")
        .order_by("-received_at", "-id")[:200]
    )
    rows = [
        _inbox_row(raw_email, issues_by_raw_email.get(raw_email.id, []))
        for raw_email in raw_emails
    ]
    rows = [
        row
        for row in rows
        if row["raw_email"].parse_status != RawEmail.ParseStatus.IGNORED
        or row["issues"]
    ]
    return render(
        request,
        "bookings/review_queue.html",
        {
            "rows": rows,
            "issues": open_issues,
            "can_edit_queue": can_mutate(request.user),
        },
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
        return redirect("inbox")
    item.resolved_by = request.user
    item.resolved_at = timezone.now()
    item.save(update_fields=["status", "resolved_by", "resolved_at"])
    messages.success(request, "Review item updated.")
    return redirect("inbox")


@require_POST
@operator_required
def inbox_email_action(request, raw_email_id):
    raw_email = get_object_or_404(RawEmail, id=raw_email_id)
    action = request.POST.get("action")
    if action == "ignore":
        raw_email.parse_status = RawEmail.ParseStatus.IGNORED
        raw_email.save(update_fields=["parse_status", "updated_at"])
        ReviewQueueItem.objects.filter(
            raw_email=raw_email,
            status=ReviewQueueItem.Status.OPEN,
        ).update(
            status=ReviewQueueItem.Status.IGNORED,
            resolved_by=request.user,
            resolved_at=timezone.now(),
        )
        messages.success(request, "Email marked ignored.")
    elif action == "reprocess":
        raw_email.parse_status = RawEmail.ParseStatus.PENDING
        raw_email.parse_error = None
        raw_email.save(update_fields=["parse_status", "parse_error", "updated_at"])
        process_raw_email(raw_email.id)
        messages.success(request, "Email reprocessed.")
    else:
        messages.error(request, "Unsupported inbox action.")
    return redirect("inbox")


@viewer_required
def raw_email_detail(request, raw_email_id):
    raw_email = get_object_or_404(
        RawEmail.objects.select_related("provider_detected"),
        id=raw_email_id,
    )
    return render(request, "bookings/raw_email_detail.html", {"raw_email": raw_email})


def _inbox_row(raw_email, issues):
    booking = _raw_email_booking(raw_email, issues)
    issues = _current_inbox_issues(raw_email, booking, issues)
    status = _inbox_status(raw_email, booking, issues)
    return {
        "raw_email": raw_email,
        "booking": booking,
        "issues": issues,
        "status": status,
        "provider": provider_label(raw_email.provider_detected),
        "sender": clean_text(raw_email.gmail_outer_sender, "Unknown sender"),
        "forwarded_sender": clean_text(raw_email.original_forwarded_sender),
        "subject": email_subject_label(raw_email),
        "parse_error": parse_error_label(raw_email, ""),
        "received_label": received_label(raw_email.received_at),
        "provider_reference": reference_label(booking),
        "raw_product_title": (
            clean_text(booking.raw_product_name, "Missing tour/activity")
            if booking
            else "Missing tour/activity"
        ),
        "matched_product": (
            activity_label(booking)
            if booking and booking.activity_id
            else "Missing mapped product"
        ),
        "booking_date": booking.active_travel_date if booking else None,
        "booking_time": booking.active_start_time if booking else None,
        "booking_datetime": short_datetime_label(booking),
        "traveler_count": traveler_count_label(booking),
        "lead_traveler": customer_label(booking),
        "booking_status": status_label(booking),
        "action_url": _inbox_action_url(raw_email, booking, issues),
        "action_label": _inbox_action_label(booking, issues),
    }


def _current_inbox_issues(raw_email, booking, issues):
    current_issues = []
    for issue in issues:
        if review_issue_is_obsolete_for_context(
            issue_type=issue.issue_type,
            title=issue.title,
            raw_email=raw_email,
            review_booking=issue.booking,
            current_booking=booking,
        ):
            continue
        current_issues.append(issue)
    return current_issues


def _raw_email_booking(raw_email, issues):
    for event in raw_email.booking_events.all():
        if event.booking_id:
            return event.booking
    for issue in issues:
        if issue.booking_id:
            return issue.booking
    return None


def _inbox_status(raw_email, booking, issues):
    if raw_email.parse_status == RawEmail.ParseStatus.IGNORED:
        return "Ignored"
    if raw_email.parse_status == RawEmail.ParseStatus.FAILED:
        return "Parse failed"
    if any(
        issue.issue_type == ReviewQueueItem.IssueType.PRODUCT_MISMATCH
        for issue in issues
    ):
        return "Product mismatch"
    missing_issue_types = {
        ReviewQueueItem.IssueType.REFERENCE_MISSING,
        ReviewQueueItem.IssueType.DATE_MISSING,
        ReviewQueueItem.IssueType.TIME_MISSING,
        ReviewQueueItem.IssueType.TRAVELER_COUNT_MISSING,
        ReviewQueueItem.IssueType.LEAD_TRAVELER_MISSING,
    }
    if any(issue.issue_type in missing_issue_types for issue in issues):
        return "Missing data"
    if issues or (
        raw_email.parse_status == RawEmail.ParseStatus.NEEDS_REVIEW and not booking
    ):
        return "Needs review"
    if booking:
        return "Complete"
    return raw_email.get_parse_status_display()


def _inbox_action_url(raw_email, booking, issues):
    product_mismatch = next(
        (
            issue
            for issue in issues
            if issue.issue_type == ReviewQueueItem.IssueType.PRODUCT_MISMATCH
        ),
        None,
    )
    if product_mismatch:
        return f"{reverse('settings_provider_aliases')}?review_id={product_mismatch.id}"
    if booking:
        return reverse("bookings:edit", args=[booking.id])
    return reverse("bookings:raw_email_detail", args=[raw_email.id])


def _inbox_action_label(booking, issues):
    if any(
        issue.issue_type == ReviewQueueItem.IssueType.PRODUCT_MISMATCH
        for issue in issues
    ):
        return "Map product"
    if issues:
        return "Complete missing data" if booking else "Review"
    return "Open booking" if booking else "View raw email"


def _activity_context(
    request,
    *,
    activity,
    active_tab,
    general_form=None,
    schedule_forms=None,
    people_form=None,
    alias_form=None,
    slot_forms=None,
    additional_time_form=None,
    blocked_date_form=None,
    change_seats_form=None,
    duration_form=None,
    editor_type=None,
    editor_schedule=None,
    editor_slot=None,
    editor_exception=None,
    schedule_copy_source_id="",
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
    slot_forms = slot_forms or {}
    other_schedules = (
        list(
            activity.schedules.filter(schedule_kind=ActivitySchedule.ScheduleKind.OTHER)
            .prefetch_related("slots", "exceptions")
            .order_by("-date_from", "-priority", "-id")
        )
        if activity
        else []
    )
    current_schedule_form = schedule_forms.get(
        ActivitySchedule.ScheduleKind.CURRENT
    ) or (
        OperatorScheduleSectionForm(
            instance=current_schedule,
            schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
            activity=activity,
            prefix=ActivitySchedule.ScheduleKind.CURRENT,
        )
        if current_schedule
        else None
    )
    other_schedule_form = schedule_forms.get(ActivitySchedule.ScheduleKind.OTHER) or (
        OperatorScheduleSectionForm(
            instance=other_schedule,
            schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
            activity=activity,
            prefix=ActivitySchedule.ScheduleKind.OTHER,
        )
        if other_schedule
        else None
    )
    if activity and active_tab == "scheduling" and is_admin(request.user):
        (
            editor_type,
            editor_schedule,
            editor_slot,
            editor_exception,
            current_schedule_form,
            other_schedule_form,
            additional_time_form,
            blocked_date_form,
            change_seats_form,
        ) = _schedule_editor_context(
            request,
            activity=activity,
            current_schedule=current_schedule,
            current_schedule_form=current_schedule_form,
            other_schedule_form=other_schedule_form,
            additional_time_form=additional_time_form,
            blocked_date_form=blocked_date_form,
            change_seats_form=change_seats_form,
            editor_type=editor_type,
            editor_schedule=editor_schedule,
            editor_slot=editor_slot,
            editor_exception=editor_exception,
        )
    additional_times = _schedule_exceptions_for_activity(
        activity,
        {ActivityScheduleException.ExceptionType.EXTRA_SLOT},
    )
    blocked_dates = _schedule_exceptions_for_activity(
        activity,
        {
            ActivityScheduleException.ExceptionType.BLOCKED,
            ActivityScheduleException.ExceptionType.CLOSED,
        },
    )
    editor_grid_schedule = editor_schedule
    if not editor_grid_schedule and schedule_copy_source_id:
        editor_grid_schedule = (
            ActivitySchedule.objects.filter(
                id=schedule_copy_source_id,
                activity=activity,
            )
            .prefetch_related("slots")
            .first()
        )
    return {
        "activity": activity,
        "active_tab": active_tab,
        "show_scheduling_tab": bool(activity and active_tab == "scheduling"),
        "general_form": general_form
        or (TourActivityForm(instance=activity) if activity else None),
        "current_schedule_form": current_schedule_form,
        "other_schedule_form": other_schedule_form,
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
        "current_schedule_summary": _schedule_summary(current_schedule),
        "current_schedule_slot_rows": _schedule_slot_rows(current_schedule),
        "current_schedule_exception_rows": [
            _exception_row(exception)
            for exception in _schedule_exceptions_for_schedule(current_schedule)
        ],
        "other_schedule": other_schedule,
        "other_schedules": [
            _other_schedule_row(schedule) for schedule in other_schedules
        ],
        "bookeo_current_schedule_effective_label": (
            _bookeo_current_schedule_effective_label(current_schedule)
        ),
        "duration_form": duration_form
        or DurationForm(duration_minutes=_schedule_duration_minutes(current_schedule)),
        "schedule_copy_options": [
            _schedule_copy_option(schedule, current_schedule)
            for schedule in list(other_schedules)
            + ([current_schedule] if current_schedule else [])
        ],
        "current_schedule_grid": _weekly_grid(current_schedule),
        "additional_times": [
            _exception_row(exception) for exception in additional_times
        ],
        "blocked_dates": [_exception_row(exception) for exception in blocked_dates],
        "editor_type": editor_type,
        "editor_schedule": editor_schedule,
        "editor_slot": editor_slot,
        "editor_exception": editor_exception,
        "editor_schedule_grid": _weekly_grid(editor_grid_schedule),
        "schedule_copy_source_id": schedule_copy_source_id,
        "slot_editor_day_index": _slot_editor_day_index(request, editor_slot),
        "slot_editor_day_name": _slot_editor_day_name(request, editor_slot),
        "slot_form": slot_forms.get(
            editor_slot.id
            if editor_slot
            else editor_schedule.id if editor_schedule else None
        )
        or _slot_form_for_editor(editor_type, editor_schedule, editor_slot, request),
        "schedule_editor_form": (
            current_schedule_form
            if editor_schedule
            and editor_schedule.schedule_kind == ActivitySchedule.ScheduleKind.CURRENT
            else other_schedule_form
        ),
        "additional_time_form": additional_time_form
        or OperatorAdditionalTimeForm(schedule=current_schedule),
        "blocked_date_form": blocked_date_form
        or OperatorBlockedDateForm(schedule=current_schedule),
        "change_seats_form": change_seats_form or ChangeSeatsForm(),
        "can_edit_activities": is_admin(request.user),
    }


def _schedule_for_kind(activity, schedule_kind):
    if not activity:
        return None
    return (
        activity.schedules.filter(schedule_kind=schedule_kind)
        .order_by("priority", "id")
        .first()
    )


def _overbooked_schedule_warnings(schedule, *, days=14):
    warnings = []
    today = timezone.localdate()
    for offset in range(days):
        service_date = today + timedelta(days=offset)
        for row in get_daily_capacity_summary(service_date):
            slot = row.get("slot")
            if not slot or slot.schedule_id != schedule.id:
                continue
            if row["remaining"] < 0:
                warnings.append(
                    f"{service_date.isoformat()} {slot_label(slot)} "
                    f"({abs(row['remaining'])} over)"
                )
    return warnings


def _schedule_editor_context(
    request,
    *,
    activity,
    current_schedule,
    current_schedule_form,
    other_schedule_form,
    additional_time_form,
    blocked_date_form,
    change_seats_form,
    editor_type,
    editor_schedule,
    editor_slot,
    editor_exception,
):
    if editor_type:
        return (
            editor_type,
            editor_schedule,
            editor_slot,
            editor_exception,
            current_schedule_form,
            other_schedule_form,
            additional_time_form,
            blocked_date_form,
            change_seats_form,
        )
    if request.GET.get("edit_slot"):
        editor_slot = get_object_or_404(
            ActivityScheduleSlot,
            id=request.GET["edit_slot"],
            schedule__activity=activity,
        )
        return (
            "slot",
            editor_slot.schedule,
            editor_slot,
            None,
            current_schedule_form,
            other_schedule_form,
            additional_time_form,
            blocked_date_form,
            change_seats_form,
        )
    if request.GET.get("add_slot"):
        editor_schedule = get_object_or_404(
            ActivitySchedule,
            id=request.GET["add_slot"],
            activity=activity,
        )
        return (
            "slot",
            editor_schedule,
            None,
            None,
            current_schedule_form,
            other_schedule_form,
            additional_time_form,
            blocked_date_form,
            change_seats_form,
        )
    if request.GET.get("edit_schedule"):
        schedule_id = request.GET["edit_schedule"]
        if schedule_id == "current":
            editor_schedule = current_schedule
            current_schedule_form = OperatorScheduleSectionForm(
                instance=current_schedule,
                schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
                activity=activity,
                prefix=ActivitySchedule.ScheduleKind.CURRENT,
            )
        elif schedule_id == "new_other":
            editor_schedule = None
            other_schedule_form = OperatorScheduleSectionForm(
                schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
                activity=activity,
                prefix=ActivitySchedule.ScheduleKind.OTHER,
                initial={
                    "schedule_status": "inactive",
                    "timezone": current_schedule.timezone if current_schedule else "",
                },
            )
        else:
            editor_schedule = get_object_or_404(
                ActivitySchedule,
                id=schedule_id,
                activity=activity,
                schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
            )
            other_schedule_form = OperatorScheduleSectionForm(
                instance=editor_schedule,
                schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
                activity=activity,
                prefix=ActivitySchedule.ScheduleKind.OTHER,
            )
        return (
            "schedule",
            editor_schedule,
            None,
            None,
            current_schedule_form,
            other_schedule_form,
            additional_time_form,
            blocked_date_form,
            change_seats_form,
        )
    if request.GET.get("new_change_schedule"):
        return (
            "schedule_copy",
            None,
            None,
            None,
            current_schedule_form,
            other_schedule_form,
            additional_time_form,
            blocked_date_form,
            change_seats_form,
        )
    if request.GET.get("change_seats"):
        return (
            "change_seats",
            current_schedule,
            None,
            None,
            current_schedule_form,
            other_schedule_form,
            additional_time_form,
            blocked_date_form,
            ChangeSeatsForm(),
        )
    if request.GET.get("copy_days"):
        return (
            "copy_days",
            current_schedule,
            None,
            None,
            current_schedule_form,
            other_schedule_form,
            additional_time_form,
            blocked_date_form,
            change_seats_form,
        )
    if request.GET.get("edit_additional"):
        editor_exception = get_object_or_404(
            ActivityScheduleException,
            id=request.GET["edit_additional"],
            schedule__activity=activity,
            exception_type=ActivityScheduleException.ExceptionType.EXTRA_SLOT,
        )
        additional_time_form = OperatorAdditionalTimeForm(
            schedule=editor_exception.schedule,
            instance=editor_exception,
        )
        return (
            "additional_time",
            editor_exception.schedule,
            None,
            editor_exception,
            current_schedule_form,
            other_schedule_form,
            additional_time_form,
            blocked_date_form,
            change_seats_form,
        )
    if request.GET.get("add_additional"):
        return (
            "additional_time",
            current_schedule,
            None,
            None,
            current_schedule_form,
            other_schedule_form,
            OperatorAdditionalTimeForm(schedule=current_schedule),
            blocked_date_form,
            change_seats_form,
        )
    if request.GET.get("edit_blocked"):
        editor_exception = get_object_or_404(
            ActivityScheduleException,
            id=request.GET["edit_blocked"],
            schedule__activity=activity,
        )
        blocked_date_form = OperatorBlockedDateForm(
            schedule=editor_exception.schedule,
            instance=editor_exception,
        )
        return (
            "blocked_date",
            editor_exception.schedule,
            None,
            editor_exception,
            current_schedule_form,
            other_schedule_form,
            additional_time_form,
            blocked_date_form,
            change_seats_form,
        )
    if request.GET.get("add_blocked"):
        return (
            "blocked_date",
            current_schedule,
            None,
            None,
            current_schedule_form,
            other_schedule_form,
            additional_time_form,
            OperatorBlockedDateForm(schedule=current_schedule),
            change_seats_form,
        )
    return (
        editor_type,
        editor_schedule,
        editor_slot,
        editor_exception,
        current_schedule_form,
        other_schedule_form,
        additional_time_form,
        blocked_date_form,
        change_seats_form,
    )


def _slot_form_for_editor(editor_type, editor_schedule, editor_slot, request):
    if editor_type != "slot" or not editor_schedule:
        return OperatorScheduleSlotForm()
    if editor_slot:
        return OperatorScheduleSlotForm(
            instance=editor_slot,
            schedule=editor_slot.schedule,
        )
    initial = {
        "duration_minutes": 120,
        "slot_kind": "fixed-time",
        "capacity": 250,
        "slot_status": "active",
    }
    if request.GET.get("day") not in {None, ""}:
        initial["slot_days"] = [request.GET["day"]]
    first_slot = editor_schedule.slots.order_by("start_time").first()
    if first_slot:
        initial["duration_minutes"] = first_slot.duration_minutes
        initial["slot_kind"] = "fixed-time"
        initial["capacity"] = first_slot.capacity
    return OperatorScheduleSlotForm(initial=initial, schedule=editor_schedule)


def _slot_editor_day_index(request, slot):
    day = request.GET.get("day")
    if day not in {None, ""}:
        try:
            value = int(day)
        except ValueError:
            return 0
        return value if value in range(7) else 0
    if slot and slot.days_of_week:
        return slot.days_of_week[0]
    return 0


def _slot_editor_day_name(request, slot):
    day_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    return day_names[_slot_editor_day_index(request, slot)]


def _weekly_grid(schedule):
    day_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    if not schedule:
        return [
            {"index": index, "name": name, "slots": []}
            for index, name in enumerate(day_names)
        ]
    slots = list(schedule.slots.filter(active=True).order_by("start_time", "id"))
    rows = []
    for index, name in enumerate(day_names):
        if schedule.days_of_week and index not in schedule.days_of_week:
            day_slots = []
        else:
            day_slots = [
                slot
                for slot in slots
                if not slot.days_of_week or index in slot.days_of_week
            ]
        rows.append({"index": index, "name": name, "slots": day_slots})
    return rows


def _schedule_exceptions_for_activity(activity, exception_types):
    if not activity:
        return []
    return (
        ActivityScheduleException.objects.filter(
            schedule__activity=activity,
            exception_type__in=exception_types,
        )
        .select_related("schedule")
        .order_by("date", "start_time", "id")
    )


def _schedule_exceptions_for_schedule(schedule):
    if not schedule:
        return []
    return schedule.exceptions.filter(active=True).order_by("date", "start_time", "id")


def _schedule_summary(schedule):
    if not schedule:
        return {
            "name": "Current schedule",
            "status_label": "Not configured",
            "effective_label": "No date limits",
            "repeat_labels": ["Every day"],
            "slot_count": 0,
            "active_slot_count": 0,
            "capacity_label": "No capacity",
            "timezone": "",
            "notes": "",
        }
    slots = list(schedule.slots.all())
    active_slots = [slot for slot in slots if slot.active]
    total_capacity = sum(slot.capacity for slot in active_slots)
    if active_slots:
        capacity_label = (
            f"{total_capacity} total seats across {len(active_slots)} times"
        )
    else:
        capacity_label = "No active times"
    return {
        "name": schedule.name or schedule.get_schedule_kind_display(),
        "status_label": "Active" if schedule.active else "Inactive",
        "effective_label": _schedule_effective_label(schedule),
        "repeat_labels": _schedule_repeat_labels(schedule),
        "slot_count": len(slots),
        "active_slot_count": len(active_slots),
        "capacity_label": capacity_label,
        "timezone": schedule.timezone,
        "notes": schedule.notes,
    }


def _schedule_slot_rows(schedule):
    if not schedule:
        return []
    return [
        {
            "slot": slot,
            "time_label": _slot_time_label(slot),
            "repeat_labels": _schedule_repeat_labels(slot),
            "duration_label": f"{slot.duration_minutes} min",
            "type_label": slot.get_slot_type_display(),
            "capacity_label": f"{slot.capacity} seats",
            "status_label": "Active" if slot.active else "Inactive",
        }
        for slot in schedule.slots.order_by("start_time", "id")
    ]


def _exception_row(exception):
    return {
        "item": exception,
        "date": exception.date,
        "time_label": _special_date_time_label(exception),
        "type_label": _special_date_type_label(exception),
        "capacity_label": _special_date_capacity_label(exception),
        "status_label": "Active" if exception.active else "Inactive",
    }


def _other_schedule_row(schedule):
    summary = _schedule_summary(schedule)
    return {
        "schedule": schedule,
        "start": schedule.date_from,
        "end": schedule.date_to,
        "name": schedule.name or "Other schedule",
        "status_label": "Active" if schedule.active else "Inactive",
        "effective_label": _schedule_effective_label(schedule),
        "repeat_labels": summary["repeat_labels"],
        "active_slot_count": summary["active_slot_count"],
        "capacity_label": summary["capacity_label"],
        "time_labels": [
            _slot_time_label(slot)
            for slot in schedule.slots.filter(active=True).order_by("start_time", "id")
        ],
    }


def _schedule_copy_option(schedule, current_schedule):
    start = _bookeo_short_date(schedule.date_from)
    end = _bookeo_short_date(schedule.date_to)
    current = (
        " (current schedule)"
        if current_schedule and schedule.id == current_schedule.id
        else ""
    )
    source_name = schedule.name or schedule.get_schedule_kind_display()
    label = f"Copy from {source_name} ({start} - {end} ){current}"
    return {
        "id": schedule.id,
        "label": label,
    }


def _next_schedule_priority(activity):
    existing = (
        activity.schedules.filter(schedule_kind=ActivitySchedule.ScheduleKind.OTHER)
        .order_by("-priority")
        .first()
    )
    if not existing:
        return 200
    return existing.priority + 10


def _copy_schedule_to_other(schedule):
    copy = ActivitySchedule.objects.create(
        activity=schedule.activity,
        schedule_kind=ActivitySchedule.ScheduleKind.OTHER,
        name=f"Copy of {schedule.name or 'current schedule'}",
        active=False,
        date_from=schedule.date_from,
        date_to=schedule.date_to,
        days_of_week=schedule.days_of_week,
        timezone=schedule.timezone,
        priority=_next_schedule_priority(schedule.activity),
        recurrence_mode=schedule.recurrence_mode,
        notes=schedule.notes,
    )
    _copy_schedule_slots(schedule, copy)
    return copy


def _copy_schedule_slots(source_schedule, target_schedule):
    for slot in source_schedule.slots.all():
        ActivityScheduleSlot.objects.create(
            schedule=target_schedule,
            start_time=slot.start_time,
            end_time=slot.end_time,
            duration_minutes=slot.duration_minutes,
            slot_type=slot.slot_type,
            capacity=slot.capacity,
            days_of_week=slot.days_of_week,
            active=slot.active,
        )


def _copy_schedule_day(schedule, from_day, to_days):
    try:
        source_day = int(from_day)
    except (TypeError, ValueError):
        source_day = 0
    target_days = []
    for value in to_days:
        try:
            day = int(value)
        except (TypeError, ValueError):
            continue
        if day in range(7) and day != source_day and day not in target_days:
            target_days.append(day)
    source_slots = [
        slot
        for slot in schedule.slots.filter(active=True).order_by("start_time", "id")
        if not slot.days_of_week or source_day in slot.days_of_week
    ]
    for target_day in target_days:
        for slot in source_slots:
            target = (
                schedule.slots.filter(
                    start_time=slot.start_time,
                    days_of_week=[target_day],
                )
                .order_by("id")
                .first()
            )
            if target:
                target.end_time = slot.end_time
                target.duration_minutes = slot.duration_minutes
                target.slot_type = slot.slot_type
                target.capacity = slot.capacity
                target.active = slot.active
                target.save()
            else:
                ActivityScheduleSlot.objects.create(
                    schedule=schedule,
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                    duration_minutes=slot.duration_minutes,
                    slot_type=slot.slot_type,
                    capacity=slot.capacity,
                    days_of_week=[target_day],
                    active=slot.active,
                )
    return len(target_days)


def _deactivate_slot_for_day(slot, day_value):
    try:
        day = int(day_value)
    except (TypeError, ValueError):
        day = None
    if day not in range(7):
        slot.active = False
        slot.save(update_fields=["active", "updated_at"])
        return

    if not slot.days_of_week:
        slot.days_of_week = [index for index in range(7) if index != day]
        slot.save(update_fields=["days_of_week", "updated_at"])
        return

    remaining_days = [index for index in slot.days_of_week if index != day]
    if remaining_days:
        slot.days_of_week = remaining_days
        slot.save(update_fields=["days_of_week", "updated_at"])
        return

    slot.active = False
    slot.save(update_fields=["active", "updated_at"])


def _schedule_effective_label(schedule):
    if schedule.date_from and schedule.date_to:
        return f"{schedule.date_from:%b %d, %Y} - {schedule.date_to:%b %d, %Y}"
    if schedule.date_from:
        return f"From {schedule.date_from:%b %d, %Y}"
    if schedule.date_to:
        return f"Until {schedule.date_to:%b %d, %Y}"
    return "No date limits"


def _bookeo_current_schedule_effective_label(schedule):
    if not schedule or (not schedule.date_from and not schedule.date_to):
        return "This schedule has no date limits"
    if schedule.date_from and schedule.date_to:
        starts = _bookeo_long_date(schedule.date_from)
        ends = _bookeo_long_date(schedule.date_to)
        return f"This schedule is effective from {starts} to {ends}"
    if schedule.date_from:
        return (
            f"This schedule is effective from {_bookeo_long_date(schedule.date_from)}"
        )
    return f"This schedule is effective until {_bookeo_long_date(schedule.date_to)}"


def _schedule_duration_minutes(schedule):
    if not schedule:
        return 120
    slot = next(
        (
            slot
            for slot in schedule.slots.all()
            if slot.active and slot.duration_minutes
        ),
        None,
    )
    if not slot:
        slot = next(
            (slot for slot in schedule.slots.all() if slot.duration_minutes),
            None,
        )
    return slot.duration_minutes if slot else 120


def _slot_end_time(start_time, duration_minutes):
    base_date = datetime.today().date()
    end_datetime = datetime.combine(base_date, start_time) + timedelta(
        minutes=duration_minutes,
    )
    if end_datetime.date() != base_date:
        return None
    return end_datetime.time()


def _bookeo_long_date(value):
    return f"{value:%A}, {value.day} {value:%B %Y}"


def _bookeo_short_date(value):
    if not value:
        return ""
    return f"{value.day}/{value.month}/{value.year}"


def _schedule_repeat_labels(schedule):
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if not schedule.days_of_week:
        return ["Every day"]
    return [labels[day] for day in schedule.days_of_week if day in range(7)]


def _slot_time_label(slot):
    if slot.end_time:
        return f"{slot.start_time:%H:%M} - {slot.end_time:%H:%M}"
    return f"{slot.start_time:%H:%M}"


def _special_date_type_label(exception):
    labels = {
        ActivityScheduleException.ExceptionType.BLOCKED: "Blocked",
        ActivityScheduleException.ExceptionType.CLOSED: "Closed",
        ActivityScheduleException.ExceptionType.OVERRIDE_CAPACITY: "Capacity override",
        ActivityScheduleException.ExceptionType.EXTRA_SLOT: "Extra slot",
        ActivityScheduleException.ExceptionType.REMOVED_SLOT: "Removed slot",
    }
    return labels.get(exception.exception_type, exception.get_exception_type_display())


def _special_date_time_label(exception):
    if exception.start_time and exception.end_time:
        return f"{exception.start_time:%H:%M} - {exception.end_time:%H:%M}"
    if exception.start_time:
        return exception.start_time.strftime("%H:%M")
    return "All day"


def _special_date_capacity_label(exception):
    if exception.capacity is None:
        return "-"
    return str(exception.capacity)


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
    queryset = queryset.exclude(
        review_items__status=ReviewQueueItem.Status.OPEN,
        review_items__issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
    )
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
    return queryset.distinct()


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
    allowed_unscheduled = any(
        _booking_is_unscheduled(booking) for booking in filtered_bookings
    )
    if restrict_to_bookings and not allowed_slot_ids and not allowed_unscheduled:
        return []
    rows = []
    seen_slot_ids = set()
    for summary in get_daily_capacity_summary(selected_date):
        slot = summary["slot"]
        is_unscheduled = summary.get("is_unscheduled", False)
        if is_unscheduled:
            if filters["activity"] or filters["category"]:
                continue
            if restrict_to_bookings and not allowed_unscheduled:
                continue
        elif restrict_to_bookings and (not slot or slot.id not in allowed_slot_ids):
            continue
        if filters["activity"] and summary["activity"].id != filters["activity"]:
            continue
        if filters["category"] and summary["activity"].category != filters["category"]:
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
    if summary.get("is_unscheduled"):
        matching_slot_bookings = [
            booking for booking in filtered_bookings if _booking_is_unscheduled(booking)
        ]
        confirmed = _calendar_sum_pax(
            matching_slot_bookings,
            {Booking.Status.CONFIRMED, Booking.Status.MODIFIED},
        )
        pending = _calendar_sum_pax(
            matching_slot_bookings,
            {Booking.Status.PENDING_PROVIDER_ACCEPTANCE},
        )
        manual_review = _calendar_sum_pax(
            matching_slot_bookings,
            {Booking.Status.MANUAL_REVIEW},
        )
    else:
        matching_slot_bookings = [
            booking
            for booking in filtered_bookings
            if slot and booking.schedule_slot_id == slot.id
        ]
        confirmed = summary["confirmed_pax"]
        pending = summary["pending_pax"]
        manual_review = summary["manual_review_pax"]
    cancelled_count = sum(
        1
        for booking in matching_slot_bookings
        if booking.status == Booking.Status.CANCELLED
    )
    has_warning = any(
        booking.status
        in {
            Booking.Status.PENDING_PROVIDER_ACCEPTANCE,
            Booking.Status.MANUAL_REVIEW,
        }
        for booking in matching_slot_bookings
    )
    return {
        "date": selected_date,
        "activity": summary["activity"],
        "slot": slot,
        "slot_label": summary["slot_label"],
        "confirmed": confirmed,
        "pending": pending,
        "manual_review": (manual_review if filters["show_manual_review"] else 0),
        "blocked": summary.get("blocked_pax", 0),
        "cancelled_count": cancelled_count if filters["show_cancelled"] else 0,
        "capacity": summary["capacity"],
        "remaining": summary["remaining"],
        "status": _capacity_status(summary["remaining"], summary["pending_pax"]),
        "slot_url": _slot_url(selected_date, slot, url_params),
        "has_warning": has_warning,
    }


def _calendar_row_sort_key(row):
    if row.get("slot_label") == "Unscheduled / unmapped":
        return (row["date"], datetime.max.time(), "zzzzzz")
    slot = row["slot"]
    return (
        row["date"],
        slot.start_time if slot else datetime.max.time(),
        row["activity"].name if row["activity"] else "zzzzzz",
    )


def _booking_is_unscheduled(booking):
    if booking.schedule_slot_id is None:
        return True
    return booking.review_items.filter(
        status=ReviewQueueItem.Status.OPEN,
        issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
    ).exists()


def _calendar_sum_pax(bookings, statuses):
    return sum(
        booking.active_traveler_count or 0
        for booking in bookings
        if booking.status in statuses
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
    if filters.get("view"):
        params["view"] = filters["view"]
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


def _provider_alias_from_post(post_data):
    provider_id = post_data.get("provider")
    raw_product_name = (post_data.get("raw_product_name") or "").strip()
    if not provider_id or not raw_product_name:
        return None
    return ProviderAlias.objects.filter(
        provider_id=provider_id,
        raw_product_name=raw_product_name,
        raw_option_name=(post_data.get("raw_option_name") or "").strip(),
        provider_product_code=(post_data.get("provider_product_code") or "").strip(),
        provider_option_code=(post_data.get("provider_option_code") or "").strip(),
    ).first()


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
