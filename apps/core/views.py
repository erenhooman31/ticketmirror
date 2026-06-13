from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.accounts.permissions import admin_required, is_admin, is_operator
from apps.bookings.models import (
    ActivityScheduleSlot,
    Booking,
    BookingEvent,
    ReviewQueueItem,
    TourActivity,
)
from apps.bookings.services import capacity_snapshot, get_daily_capacity_summary
from apps.ingestion.models import RawEmail

AGENDA_RANGE_OPTIONS = (1, 3, 7)
DEFAULT_AGENDA_RANGE = 1
MESSAGE_LIMIT = 40


def healthz(request):
    return JsonResponse({"status": "ok"})


@login_required
def dashboard(request):
    selected_date = _parse_date(request.GET.get("date")) or timezone.localdate()
    range_days = _parse_range_days(request.GET.get("range"))
    bookings_today = Booking.objects.filter(active_travel_date=selected_date)
    context = {
        "today": selected_date,
        "selected_date": selected_date,
        "range_days": range_days,
        "previous_url": _dashboard_url(
            selected_date - timedelta(days=range_days),
            range_days,
        ),
        "today_url": _dashboard_url(timezone.localdate(), range_days),
        "next_url": _dashboard_url(
            selected_date + timedelta(days=range_days),
            range_days,
        ),
        "range_options": [
            {
                "days": days,
                "active": days == range_days,
                "url": _dashboard_url(selected_date, days),
            }
            for days in AGENDA_RANGE_OPTIONS
        ],
        "dashboard_messages": _dashboard_messages(),
        "agenda_sections": _agenda_sections(selected_date, range_days),
        "booking_status_options": Booking.Status.choices,
        "activity_options": TourActivity.objects.filter(active=True).order_by("name"),
        "slot_options": ActivityScheduleSlot.objects.filter(active=True)
        .select_related("schedule", "schedule__activity")
        .order_by("schedule__activity__name", "start_time"),
        "slot_type_options": ActivityScheduleSlot.SlotType.choices,
        "bookings_today_count": bookings_today.count(),
        "confirmed_pax_today": bookings_today.filter(
            status=Booking.Status.CONFIRMED
        ).aggregate(total=Sum("active_traveler_count"))["total"]
        or 0,
        "pending_pax_today": bookings_today.filter(
            status=Booking.Status.PENDING_PROVIDER_ACCEPTANCE
        ).aggregate(total=Sum("active_traveler_count"))["total"]
        or 0,
        "open_review_count": ReviewQueueItem.objects.filter(
            status=ReviewQueueItem.Status.OPEN
        ).count(),
        "failed_parser_count": RawEmail.objects.filter(
            parse_status=RawEmail.ParseStatus.FAILED
        ).count(),
        "capacity_warning_count": _capacity_warning_count(selected_date),
        "status_counts": Booking.objects.values("status")
        .annotate(count=Count("id"))
        .order_by("status"),
    }
    return render(request, "core/dashboard.html", context)


@login_required
def search(request):
    query = request.GET.get("q", "").strip()
    bookings = Booking.objects.none()
    if query:
        bookings = (
            Booking.objects.filter(
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
            .select_related("provider", "activity", "schedule_slot")
            .order_by("-active_travel_date", "provider_booking_reference")[:50]
        )
    return render(
        request,
        "core/search.html",
        {
            "query": query,
            "bookings": bookings,
        },
    )


@login_required
def customers(request):
    return search(request)


@login_required
def settings_home(request):
    sections = _settings_sections(request.user)
    return render(
        request,
        "core/settings.html",
        {
            "sections": sections,
        },
    )


@admin_required
def settings_customer_fields(request):
    return render(request, "core/settings_customer_fields.html")


@admin_required
def settings_users_roles(request):
    User = get_user_model()
    if request.method == "POST":
        target_user = get_object_or_404(User, id=request.POST.get("user_id"))
        role = request.POST.get("role")
        if role not in UserProfile.Role.values:
            messages.error(request, "Unsupported role.")
            return redirect("core:settings_users_roles")
        target_user.profile.role = role
        target_user.profile.save(update_fields=["role", "updated_at"])
        messages.success(request, f"Updated {target_user.username}.")
        return redirect("core:settings_users_roles")

    users = User.objects.select_related("profile").order_by("username")
    return render(
        request,
        "core/settings_users_roles.html",
        {
            "managed_users": users,
            "role_options": UserProfile.Role.choices,
        },
    )


def _settings_sections(user):
    sections = [
        {
            "title": "Tours & Activities",
            "description": (
                "View activities, provider aliases, seasonal schedules, "
                "slots, and capacity setup."
            ),
            "url": reverse("settings_tour_activities"),
        },
    ]
    if is_admin(user):
        sections.extend(
            [
                {
                    "title": "Providers",
                    "description": (
                        "Provider setup is currently maintained through seed "
                        "data and emergency developer tools."
                    ),
                    "url": "",
                },
                {
                    "title": "Customer Fields",
                    "description": (
                        "Define which customer and participant fields are "
                        "operationally required."
                    ),
                    "url": reverse("core:settings_customer_fields"),
                },
                {
                    "title": "Users & Roles",
                    "description": (
                        "Manage internal user roles for admin, operator, and "
                        "viewer access."
                    ),
                    "url": reverse("core:settings_users_roles"),
                },
                {
                    "title": "Gmail / Ingestion",
                    "description": (
                        "Gmail watch and parser status are currently managed "
                        "by internal commands and review events."
                    ),
                    "url": "",
                },
            ]
        )
    if is_admin(user) or is_operator(user):
        sections.append(
            {
                "title": "Provider Aliases",
                "description": (
                    "Map provider product labels to TicketMirror products "
                    "and resolve alias review items."
                ),
                "url": reverse("settings_provider_aliases"),
            }
        )
    sections.append(
        {
            "title": "Reports / Exports",
            "description": (
                "Download operational CSV reports for manifests, "
                "capacity, bookings, and provider summaries."
            ),
            "url": reverse("reports:index"),
        }
    )
    return sections


def _capacity_warning_count(selected_date):
    warnings = 0
    # Use the service snapshot for the final numbers; the lightweight grouping only
    # avoids recomputing the same slot repeatedly.
    seen = set()
    for booking in Booking.objects.filter(
        active_travel_date=selected_date,
        schedule_slot__isnull=False,
    ).select_related("schedule_slot"):
        key = (booking.schedule_slot_id, booking.active_start_time)
        if key in seen:
            continue
        seen.add(key)
        snapshot = capacity_snapshot(
            schedule_slot=booking.schedule_slot,
            service_date=selected_date,
        )
        if snapshot["remaining"] <= 0 and snapshot["pending"]:
            warnings += 1
    return warnings


def _agenda_sections(selected_date, range_days):
    sections = []
    for offset in range(range_days):
        service_date = selected_date + timedelta(days=offset)
        rows = [
            _agenda_row(service_date, row)
            for row in get_daily_capacity_summary(service_date)
        ]
        sections.append(
            {
                "date": service_date,
                "label": _agenda_day_label(service_date),
                "rows": rows,
            }
        )
    return sections


def _agenda_row(service_date, row):
    confirmed = row["confirmed_pax"]
    pending = row["pending_pax"]
    manual_review = row["manual_review_pax"]
    booked = confirmed + pending
    capacity = row["capacity"]
    available = None if capacity is None else max(capacity - confirmed, 0)
    status = _agenda_status(row)
    return {
        "time": row["slot_label"],
        "title": _agenda_title(row),
        "confirmed": confirmed,
        "pending": pending,
        "manual_review": manual_review,
        "booked": booked,
        "capacity": capacity,
        "available": available,
        "status": status,
        "slot_url": _slot_url(service_date, row),
    }


def _agenda_title(row):
    return row["activity"].name


def _agenda_status(row):
    if row["capacity"] is None:
        return "unknown"
    if row["remaining"] is not None and row["remaining"] <= 0:
        return "full"
    if row["confirmed_pax"] or row["pending_pax"] or row["manual_review_pax"]:
        return "booked"
    return "open"


def _slot_url(service_date, row):
    slot = row["slot"]
    if not slot:
        return ""
    return reverse(
        "bookings:slot_detail",
        args=[service_date.isoformat(), slot.id],
    )


def _dashboard_messages():
    messages = []
    events = BookingEvent.objects.select_related(
        "booking",
        "booking__provider",
        "booking__activity",
        "booking__schedule_slot",
        "raw_email",
    ).order_by("-created_at")[:MESSAGE_LIMIT]
    messages.extend(_message_from_event(event) for event in events)

    open_reviews = (
        ReviewQueueItem.objects.filter(status=ReviewQueueItem.Status.OPEN)
        .select_related("booking", "booking__provider", "raw_email")
        .order_by("-created_at")[:10]
    )
    messages.extend(_message_from_review(item) for item in open_reviews)

    failed_emails = (
        RawEmail.objects.filter(parse_status=RawEmail.ParseStatus.FAILED)
        .select_related("provider_detected")
        .order_by("-received_at")[:10]
    )
    messages.extend(
        _message_from_failed_email(raw_email) for raw_email in failed_emails
    )

    return sorted(
        messages,
        key=lambda message: message["created_at"],
        reverse=True,
    )[:MESSAGE_LIMIT]


def _message_from_event(event):
    booking = event.booking
    title = _event_title(event, booking)
    href = reverse("bookings:detail", args=[booking.id]) if booking else ""
    if not href and event.raw_email_id:
        href = reverse("bookings:raw_email_detail", args=[event.raw_email_id])
    return {
        "kind": _event_kind(event.event_type),
        "created_at": event.created_at,
        "title": title,
        "subtitle": _booking_datetime_label(booking),
        "product": _booking_product_label(booking),
        "meta": _booking_meta_label(booking),
        "href": href,
        "booking": booking,
        "event": event,
        "modal_id": f"booking-modal-event-{event.id}" if booking else "",
    }


def _message_from_review(item):
    href = ""
    if item.booking_id:
        href = reverse("bookings:detail", args=[item.booking_id])
    elif item.raw_email_id:
        href = reverse("bookings:raw_email_detail", args=[item.raw_email_id])
    return {
        "kind": "warning",
        "created_at": item.created_at,
        "title": f"Review needed - {item.title}",
        "subtitle": item.get_issue_type_display(),
        "product": _booking_product_label(item.booking),
        "meta": item.details,
        "href": href,
        "booking": item.booking,
        "review_item": item,
        "modal_id": f"booking-modal-review-{item.id}" if item.booking_id else "",
    }


def _message_from_failed_email(raw_email):
    provider_name = (
        raw_email.provider_detected.name if raw_email.provider_detected else ""
    )
    return {
        "kind": "error",
        "created_at": raw_email.received_at,
        "title": f"Parser failed - {raw_email.subject}",
        "subtitle": provider_name,
        "product": "",
        "meta": raw_email.parse_error or "",
        "href": reverse("bookings:raw_email_detail", args=[raw_email.id]),
        "booking": None,
        "raw_email": raw_email,
        "modal_id": "",
    }


def _event_title(event, booking):
    traveler = booking.lead_traveler_name if booking else ""
    if event.event_type == BookingEvent.EventType.EMAIL_CANCELLATION:
        prefix = "Booking canceled"
    elif event.event_type == BookingEvent.EventType.EMAIL_UPDATE:
        prefix = "Booking changed"
    elif event.event_type == BookingEvent.EventType.EMAIL_BOOKING_REQUEST:
        prefix = "Booking request"
    elif event.event_type == BookingEvent.EventType.MANUAL_STATUS_CHANGE:
        prefix = "Status changed"
    elif event.event_type == BookingEvent.EventType.MANUAL_EDIT:
        prefix = "Manual edit"
    elif event.event_type == BookingEvent.EventType.CONFLICT_DETECTED:
        prefix = "Conflict detected"
    else:
        prefix = "New booking"
    return f"{prefix} - {traveler}" if traveler else prefix


def _event_kind(event_type):
    if event_type == BookingEvent.EventType.EMAIL_CANCELLATION:
        return "cancelled"
    if event_type in {
        BookingEvent.EventType.CONFLICT_DETECTED,
        BookingEvent.EventType.PARSER_REVIEW_RESOLVED,
    }:
        return "warning"
    if event_type in {
        BookingEvent.EventType.MANUAL_EDIT,
        BookingEvent.EventType.MANUAL_STATUS_CHANGE,
    }:
        return "changed"
    return "new"


def _booking_datetime_label(booking):
    if not booking or not booking.active_travel_date:
        return ""
    date_label = booking.active_travel_date.strftime("%A, %d %B %Y")
    if booking.active_start_time:
        return f"{date_label} {booking.active_start_time:%H:%M}"
    return date_label


def _booking_product_label(booking):
    if not booking:
        return ""
    if booking.schedule_slot_id:
        activity_name = booking.activity.name if booking.activity else ""
        return f"{activity_name} - {booking.schedule_slot.start_time:%H:%M}"
    if booking.activity_id:
        return booking.activity.name
    return booking.raw_product_name


def _booking_meta_label(booking):
    if not booking:
        return ""
    pax = booking.active_traveler_count or booking.provider_traveler_count or 0
    pax_label = f"{pax} adult" if pax == 1 else f"{pax} adults"
    reference = booking.provider_booking_reference or booking.provider_order_reference
    if reference:
        return f"{pax_label} - {reference}"
    return pax_label


def _agenda_day_label(service_date):
    today = timezone.localdate()
    if service_date == today:
        return "Today"
    if service_date == today + timedelta(days=1):
        return "Tomorrow"
    return service_date.strftime("%A, %d %B %Y")


def _parse_range_days(value):
    try:
        range_days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_AGENDA_RANGE
    if range_days not in AGENDA_RANGE_OPTIONS:
        return DEFAULT_AGENDA_RANGE
    return range_days


def _dashboard_url(selected_date, range_days):
    return f"{reverse('core:dashboard')}?{urlencode({
        'date': selected_date.isoformat(),
        'range': range_days,
    })}"


def _parse_date(value):
    if not value:
        return None
    try:
        return timezone.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
