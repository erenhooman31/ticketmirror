from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.bookings.models import Booking, ReviewQueueItem


@login_required
def dashboard(request):
    today = timezone.localdate()
    bookings_today = Booking.objects.filter(active_travel_date=today)
    context = {
        "today": today,
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
        "status_counts": Booking.objects.values("status")
        .annotate(count=Count("id"))
        .order_by("status"),
    }
    return render(request, "core/dashboard.html", context)
