from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import UserProfile
from apps.accounts.permissions import admin_required, can_mutate, is_admin
from apps.bookings.display import (
    activity_label,
    clean_text,
    customer_label,
    datetime_label,
    product_label,
    provider_label,
    reference_label,
    review_details_label,
    short_datetime_label,
    status_label,
    traveler_count_label,
)
from apps.bookings.models import (
    ActivityScheduleSlot,
    Booking,
    BookingEvent,
    ReviewQueueItem,
    TourActivity,
)
from apps.bookings.services import (
    CapacityExceededError,
    apply_manual_override,
    capacity_snapshot,
    create_internal_booking,
    get_daily_capacity_summary,
)
from apps.ingestion.models import GmailSyncState, RawEmail
from apps.ingestion.tasks import (
    daily_reconciliation_sync,
    process_pending_raw_emails,
    renew_gmail_watch,
)

AGENDA_RANGE_OPTIONS = (1, 3, 7)
DEFAULT_AGENDA_RANGE = 1
MESSAGE_LIMIT = 40


def healthz(request):
    return JsonResponse({"status": "ok"})


@login_required
def dashboard(request):
    selected_date = _parse_date(request.GET.get("date")) or timezone.localdate()
    range_days = _parse_range_days(request.GET.get("range"))
    message_filter = request.GET.get("messages", "all")
    if message_filter not in {"all", "unread"}:
        message_filter = "all"
    bookings_today = Booking.objects.filter(active_travel_date=selected_date)
    context = {
        "today": selected_date,
        "selected_date": selected_date,
        "range_days": range_days,
        "message_filter": message_filter,
        "messages_all_url": _dashboard_url(selected_date, range_days, messages="all"),
        "messages_unread_url": _dashboard_url(
            selected_date,
            range_days,
            messages="unread",
        ),
        "agenda_print_url": _agenda_print_url(selected_date, range_days),
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
        "dashboard_messages": _dashboard_messages(
            message_filter,
            read_keys=set(request.session.get("home_read_message_keys", [])),
        ),
        "agenda_sections": _agenda_sections(selected_date, range_days),
        "booking_status_options": Booking.Status.choices,
        "attendance_status_options": Booking.AttendanceStatus.choices,
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
@require_POST
def mark_home_messages_read(request):
    read_keys = set(request.session.get("home_read_message_keys", []))
    read_keys.update(
        message["key"] for message in _dashboard_messages("all", read_keys=set())
    )
    request.session["home_read_message_keys"] = sorted(read_keys)
    request.session.modified = True
    next_url = request.POST.get("next") or reverse("core:dashboard")
    return redirect(next_url)


@login_required
@require_POST
def cancel_home_booking(request, booking_id):
    if not (
        request.user.is_superuser
        or getattr(request.user.profile, "can_edit_bookings", False)
    ):
        return HttpResponseForbidden("You do not have permission to cancel bookings.")
    booking = get_object_or_404(Booking, pk=booking_id)
    apply_manual_override(
        booking=booking,
        changes={"status": Booking.Status.CANCELLED},
        user=request.user,
        reason=request.POST.get("bookingDeclineReason", ""),
    )
    next_url = request.POST.get("next") or reverse("core:dashboard")
    return redirect(next_url)


@login_required
@require_POST
def create_home_booking(request, service_date, slot_id):
    if not (
        request.user.is_superuser
        or getattr(request.user.profile, "can_edit_bookings", False)
    ):
        return HttpResponseForbidden("You do not have permission to create bookings.")
    parsed_date = _parse_date(service_date)
    if not parsed_date:
        return HttpResponseForbidden("Invalid service date.")
    slot = get_object_or_404(
        ActivityScheduleSlot.objects.select_related("schedule", "schedule__activity"),
        pk=slot_id,
        active=True,
    )
    pax = _parse_positive_int(request.POST.get("active_traveler_count"), default=0)
    next_url = request.POST.get("next") or _dashboard_url(parsed_date, 1)
    try:
        create_internal_booking(
            service_date=parsed_date,
            schedule_slot=slot,
            traveler_count=pax,
            lead_traveler_name=request.POST.get("lead_traveler_name", ""),
            lead_traveler_email=request.POST.get("lead_traveler_email", "").strip(),
            lead_traveler_phone=request.POST.get("lead_traveler_phone", "").strip(),
            special_requirements=request.POST.get("special_requirements", "").strip(),
            customer_message=request.POST.get("customer_message", "").strip(),
            user=request.user,
            allow_overcapacity=request.POST.get("allow_overcapacity") == "on",
            override_reason=request.POST.get("capacity_override_reason", ""),
        )
        messages.success(request, "Internal booking created.")
    except CapacityExceededError as exc:
        messages.error(request, str(exc))
    return redirect(next_url)


@login_required
def credits(request):
    credit_packages = [
        {
            "code": "CREDITS-40",
            "credits": 40,
            "price": "$5",
            "unit_price": "$0,12",
        },
        {
            "code": "CREDITS-250",
            "credits": 250,
            "price": "$25",
            "unit_price": "$0,10",
        },
        {
            "code": "CREDITS-1100",
            "credits": 1100,
            "price": "$100",
            "unit_price": "$0,09",
        },
    ]
    return render(
        request,
        "core/credits.html",
        {
            "current_credits": 0,
            "credit_packages": credit_packages,
        },
    )


@login_required
def agenda_print(request):
    selected_date = _parse_date(request.GET.get("date")) or timezone.localdate()
    range_days = _parse_range_days(request.GET.get("range"))
    return render(
        request,
        "core/agenda_print.html",
        {
            "selected_date": selected_date,
            "range_days": range_days,
            "agenda_sections": _agenda_sections(selected_date, range_days),
        },
    )


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
    query = request.GET.get("q", "").strip()
    letter = request.GET.get("letter", "").strip().upper()
    selected_id = request.GET.get("customer")
    bookings = (
        Booking.objects.exclude(lead_traveler_name__isnull=True)
        .exclude(lead_traveler_name="")
        .select_related("provider", "activity", "schedule_slot")
        .order_by("lead_traveler_name", "-active_travel_date")
    )
    if query:
        bookings = _search_customer_bookings(bookings, query)
    if letter and letter != "ALL":
        bookings = bookings.filter(lead_traveler_name__istartswith=letter)

    customer_rows = _customer_rows(bookings)
    selected_customer = _selected_customer(customer_rows, selected_id)
    return render(
        request,
        "core/customers.html",
        {
            "query": query,
            "letter": letter,
            "letters": ["ALL", *[chr(code) for code in range(ord("A"), ord("Z") + 1)]],
            "customer_rows": customer_rows,
            "selected_customer": selected_customer,
        },
    )


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
        action = request.POST.get("action", "update_role")
        if action == "create_user":
            username = request.POST.get("username", "").strip()
            email = request.POST.get("email", "").strip()
            password = request.POST.get("password", "")
            role = request.POST.get("role")
            if not username or not password:
                messages.error(request, "Username and password are required.")
                return redirect("core:settings_users_roles")
            if role not in UserProfile.Role.values:
                messages.error(request, "Unsupported role.")
                return redirect("core:settings_users_roles")
            if User.objects.filter(username__iexact=username).exists():
                messages.error(request, "A user with that username already exists.")
                return redirect("core:settings_users_roles")
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            user.profile.role = role
            user.profile.save(update_fields=["role", "updated_at"])
            messages.success(request, f"Created {user.username}.")
            return redirect("core:settings_users_roles")

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


@login_required
def settings_ingestion(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "process_pending":
            if not can_mutate(request.user):
                return HttpResponseForbidden(
                    "You do not have permission to process emails."
                )
            limit = _parse_positive_int(request.POST.get("limit"), default=50) or 50
            try:
                processed = process_pending_raw_emails.apply(
                    kwargs={"limit": limit}
                ).get()
                messages.success(request, f"Processed {processed} pending email(s).")
            except Exception as exc:
                messages.error(request, f"Pending processing failed: {exc}")
        elif action == "sync_recent":
            if not is_admin(request.user):
                return HttpResponseForbidden(
                    "You do not have permission to sync Gmail."
                )
            limit = _parse_positive_int(request.POST.get("limit"), default=50) or 50
            try:
                result = daily_reconciliation_sync.apply(kwargs={"limit": limit}).get()
                messages.success(request, f"Queued recent Gmail sync: {result}.")
            except Exception as exc:
                messages.error(request, f"Recent Gmail sync failed: {exc}")
        elif action == "renew_watch":
            if not is_admin(request.user):
                return HttpResponseForbidden(
                    "You do not have permission to renew Gmail watch."
                )
            try:
                result = renew_gmail_watch.apply().get()
                messages.success(request, f"Renewed Gmail watch: {result}.")
            except Exception as exc:
                messages.error(request, f"Gmail watch renewal failed: {exc}")
        else:
            messages.error(request, "Unsupported ingestion action.")
        return redirect("core:settings_ingestion")

    raw_counts = {
        status: RawEmail.objects.filter(parse_status=status).count()
        for status in RawEmail.ParseStatus.values
    }
    return render(
        request,
        "core/settings_ingestion.html",
        {
            "gmail_config": _gmail_config_status(),
            "sync_states": GmailSyncState.objects.order_by("mailbox_email"),
            "raw_counts": raw_counts,
            "failed_review_count": RawEmail.objects.filter(
                parse_status__in=[
                    RawEmail.ParseStatus.FAILED,
                    RawEmail.ParseStatus.NEEDS_REVIEW,
                ]
            ).count(),
            "can_process_pending": can_mutate(request.user),
            "can_admin_ingestion": is_admin(request.user),
        },
    )


def _settings_sections(user):
    sections = [
        {
            "title": "Tours & Activities",
            "description": (
                "Manage activity details, seasonal schedules, available times, "
                "duration, and people capacity."
            ),
            "url": reverse("settings_tour_activities"),
        },
        {
            "title": "Ingestion",
            "description": (
                "Review Gmail setup status, parser queue health, and safe email "
                "processing actions."
            ),
            "url": reverse("core:settings_ingestion"),
        },
    ]
    if is_admin(user):
        sections.append(
            {
                "title": "Users & Roles",
                "description": (
                    "Create users and manage internal roles for admin, operator, "
                    "and viewer access."
                ),
                "url": reverse("core:settings_users_roles"),
            }
        )
    return sections


def _gmail_config_status():
    names = [
        "GMAIL_MAILBOX",
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET",
        "GMAIL_REFRESH_TOKEN",
        "GMAIL_PUBSUB_TOPIC",
        "GMAIL_WEBHOOK_AUDIENCE",
        "GOOGLE_CLOUD_PROJECT",
    ]
    rows = []
    for name in names:
        value = getattr(settings, name, "")
        rows.append(
            {
                "name": name,
                "configured": bool(value),
                "display": value if name == "GMAIL_MAILBOX" and value else "",
            }
        )
    return rows


def _customer_rows(bookings):
    rows_by_key = {}
    for booking in bookings:
        key = _customer_key(booking)
        row = rows_by_key.setdefault(
            key,
            {
                "key": key,
                "id": booking.id,
                "name": customer_label(booking),
                "initials": _customer_initials(
                    customer_label(booking, fallback=""),
                ),
                "phone": clean_text(booking.lead_traveler_phone, "Missing phone"),
                "email": clean_text(booking.lead_traveler_email, "Missing email"),
                "language": clean_text(booking.language, "Missing language"),
                "bookings": [],
                "last_booking": None,
                "total_pax": 0,
            },
        )
        row["bookings"].append(booking)
        row["total_pax"] += booking.active_traveler_count or 0
        if not row["last_booking"] or _booking_sort_date(booking) > _booking_sort_date(
            row["last_booking"]
        ):
            row["last_booking"] = booking
    return list(rows_by_key.values())


def _customer_key(booking):
    email = (booking.lead_traveler_email or "").strip().lower()
    if email:
        return f"email:{email}"
    phone = (booking.lead_traveler_phone or "").strip().lower()
    if phone:
        return f"phone:{phone}"
    return f"name:{(booking.lead_traveler_name or '').strip().lower()}"


def _customer_initials(name):
    parts = [part for part in name.replace(",", " ").split() if part]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def _selected_customer(customer_rows, selected_id):
    if not customer_rows:
        return None
    if selected_id:
        for row in customer_rows:
            if str(row["id"]) == selected_id:
                return row
    return customer_rows[0]


def _booking_sort_date(booking):
    return booking.active_travel_date or timezone.datetime.min.date()


def _search_customer_bookings(queryset, query):
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
        rows = [row for row in rows if _show_in_home_agenda(row)]
        rows = sorted(rows, key=_agenda_row_sort_key)
        sections.append(
            {
                "date": service_date,
                "label": _agenda_day_label(service_date),
                "rows": rows,
            }
        )
    return sections


def _agenda_row(service_date, row):
    slot = row["slot"]
    bookings = _agenda_bookings(service_date, slot)
    booking_cards = [_agenda_booking_card(booking) for booking in bookings]
    active_booked = sum(
        card["pax"] for card in booking_cards if card["counts_for_capacity"]
    )
    capacity = row["capacity"]
    available = None if capacity is None else max(capacity - active_booked, 0)
    has_warning = any(card["warning"] for card in booking_cards)
    return {
        "time": _agenda_time_label(row),
        "title": _agenda_title(row),
        "booked": active_booked,
        "blocked": 0,
        "capacity": capacity,
        "available": available,
        "status": _agenda_status(
            capacity=capacity,
            available=available,
            booked=active_booked,
            has_bookings=bool(booking_cards),
            has_warning=has_warning,
        ),
        "has_warning": has_warning,
        "bookings": booking_cards,
        "slot": slot,
        "modal_id": _agenda_modal_id(service_date, row),
        "sort_id": _agenda_sort_id(row),
        "slot_url": _slot_url(service_date, row),
    }


def _agenda_title(row):
    activity = row["activity"]
    return activity.internal_display_name or activity.name


def _show_in_home_agenda(row):
    activity = row["slot"].schedule.activity if row["slot"] else None
    settings = activity.display_settings if activity else {}
    if settings.get("show_home_agenda") is False:
        return False
    if settings.get("show_home_agenda") is True:
        return True
    return bool(row["booked"] or row["bookings"])


def _agenda_time_label(row):
    slot = row["slot"]
    exception = row.get("exception")
    start_time = (
        slot.start_time if slot else exception.start_time if exception else None
    )
    if not start_time:
        return "Open"
    return f"{start_time.hour}:{start_time:%M}"


def _agenda_status(*, capacity, available, booked, has_bookings, has_warning):
    if capacity is None:
        return "unknown"
    if available is not None and available <= 0:
        return "full"
    if has_warning:
        return "warning"
    if booked or has_bookings:
        return "booked"
    return "open"


def _agenda_bookings(service_date, slot):
    if not slot:
        return []
    return (
        Booking.objects.filter(
            active_travel_date=service_date,
            schedule_slot=slot,
        )
        .exclude(
            status__in={
                Booking.Status.CANCELLED,
                Booking.Status.REJECTED,
                Booking.Status.PARSE_FAILED,
                Booking.Status.DUPLICATE_IGNORED,
            }
        )
        .exclude(
            review_items__status=ReviewQueueItem.Status.OPEN,
            review_items__issue_type=ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
        )
        .select_related("provider", "activity", "schedule_slot")
        .order_by("provider__name", "provider_booking_reference")
        .distinct()
    )


def _agenda_booking_card(booking):
    pax_value = booking.active_traveler_count
    if pax_value is None:
        pax_value = booking.provider_traveler_count
    pax = pax_value or 0
    attendance = booking.get_attendance_status_display()
    return {
        "booking": booking,
        "pax": pax,
        "pax_display": traveler_count_label(booking),
        "reference": booking.provider_booking_reference,
        "traveler": customer_label(booking),
        "status": status_label(booking),
        "attendance": attendance if booking.attendance_status else "",
        "warning": booking.status
        in {
            Booking.Status.PENDING_PROVIDER_ACCEPTANCE,
            Booking.Status.MANUAL_REVIEW,
        },
        "counts_for_capacity": booking.is_active_for_capacity,
        "detail_url": reverse("bookings:detail", args=[booking.id]),
    }


def _agenda_modal_id(service_date, row):
    slot = row["slot"]
    if slot:
        return f"agenda-slot-{service_date:%Y%m%d}-{slot.id}"
    exception = row.get("exception")
    return f"agenda-extra-{service_date:%Y%m%d}-{exception.id}"


def _agenda_sort_id(row):
    slot = row["slot"]
    if slot:
        return slot.id
    exception = row.get("exception")
    return exception.id if exception else 0


def _agenda_row_sort_key(row):
    time_label = row["time"]
    try:
        hour, minute = time_label.split(":", 1)
        time_key = (int(hour), int(minute[:2]))
    except ValueError:
        time_key = (99, 99)
    return (time_key, row["sort_id"], row["title"])


def _slot_url(service_date, row):
    slot = row["slot"]
    if not slot:
        return ""
    return reverse(
        "bookings:slot_detail",
        args=[service_date.isoformat(), slot.id],
    )


def _dashboard_messages(message_filter="all", *, read_keys=None):
    read_keys = read_keys or set()
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

    for message in messages:
        message["read"] = message["key"] in read_keys

    if message_filter == "unread":
        messages = [message for message in messages if not message["read"]]

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
        "key": f"event:{event.id}",
        "created_at": event.created_at,
        "created_label": _home_message_created_label(event.created_at),
        "title": title,
        "subtitle": datetime_label(booking),
        "product": product_label(booking),
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
        "key": f"review:{item.id}",
        "created_at": item.created_at,
        "created_label": _home_message_created_label(item.created_at),
        "title": f"Review needed - {item.title}",
        "subtitle": item.get_issue_type_display(),
        "product": product_label(item.booking),
        "meta": review_details_label(item),
        "href": href,
        "booking": item.booking,
        "review_item": item,
        "modal_id": f"booking-modal-review-{item.id}" if item.booking_id else "",
    }


def _message_from_failed_email(raw_email):
    provider_name = provider_label(raw_email.provider_detected)
    subject = clean_text(raw_email.subject, "Email without subject")
    return {
        "kind": "error",
        "key": f"raw-email:{raw_email.id}",
        "created_at": raw_email.received_at,
        "created_label": _home_message_created_label(raw_email.received_at),
        "title": f"Parser failed - {subject}",
        "subtitle": provider_name,
        "product": "",
        "meta": clean_text(raw_email.parse_error, "Parser error"),
        "href": reverse("bookings:raw_email_detail", args=[raw_email.id]),
        "booking": None,
        "raw_email": raw_email,
        "modal_id": "",
    }


def _event_title(event, booking):
    traveler = customer_label(booking, fallback="") if booking else ""
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


def _home_message_created_label(created_at):
    local_created_at = timezone.localtime(created_at)
    if local_created_at.date() == timezone.localdate():
        return f"Today, {local_created_at:%H:%M}"
    return f"{local_created_at:%a, %H:%M}"


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
    return datetime_label(booking, fallback="")


def _booking_product_label(booking):
    return product_label(booking, fallback="")


def _booking_meta_label(booking):
    if not booking:
        return ""
    parts = [
        provider_label(booking.provider),
        reference_label(booking),
        customer_label(booking),
        activity_label(booking),
        short_datetime_label(booking),
        traveler_count_label(booking),
        status_label(booking),
    ]
    return " - ".join(dict.fromkeys(part for part in parts if part))


def _agenda_day_label(service_date):
    today = timezone.localdate()
    if service_date == today:
        return "Today"
    if service_date == today + timedelta(days=1):
        return "Tomorrow"
    return f"{service_date:%A}, {service_date.day} {service_date:%B}"


def _parse_range_days(value):
    try:
        range_days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_AGENDA_RANGE
    if range_days not in AGENDA_RANGE_OPTIONS:
        return DEFAULT_AGENDA_RANGE
    return range_days


def _parse_positive_int(value, *, default=0):
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def _dashboard_url(selected_date, range_days, **overrides):
    params = {
        "date": selected_date.isoformat(),
        "range": range_days,
    }
    params.update({key: value for key, value in overrides.items() if value})
    return f"{reverse('core:dashboard')}?{urlencode(params)}"


def _agenda_print_url(selected_date, range_days):
    params = {
        "date": selected_date.isoformat(),
        "range": range_days,
    }
    return f"{reverse('core:agenda_print')}?{urlencode(params)}"


def _parse_date(value):
    if not value:
        return None
    try:
        return timezone.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
