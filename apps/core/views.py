from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.bookings.models import Booking, ReviewQueueItem
from apps.bookings.services import capacity_snapshot
from apps.ingestion.models import RawEmail


@login_required
def dashboard(request):
    selected_date = _parse_date(request.GET.get("date")) or timezone.localdate()
    bookings_today = Booking.objects.filter(active_travel_date=selected_date)
    context = {
        "today": selected_date,
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


def _capacity_warning_count(selected_date):
    warnings = 0
    # Use the service snapshot for the final numbers; the lightweight grouping only
    # avoids recomputing the same slot repeatedly.
    seen = set()
    for booking in Booking.objects.filter(
        active_travel_date=selected_date,
        canonical_variant__isnull=False,
    ).select_related("canonical_variant"):
        key = (booking.canonical_variant_id, booking.active_start_time)
        if key in seen:
            continue
        seen.add(key)
        snapshot = capacity_snapshot(
            product_variant=booking.canonical_variant,
            service_date=selected_date,
            start_time=booking.active_start_time,
        )
        if snapshot["remaining"] <= 0 and snapshot["pending"]:
            warnings += 1
    return warnings


def _parse_date(value):
    if not value:
        return None
    try:
        return timezone.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
