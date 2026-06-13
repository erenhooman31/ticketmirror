import csv
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.services import (
    export_capacity_summary_csv,
    export_daily_manifest_csv,
    export_provider_summary_csv,
)


@login_required
def reports_index(request):
    today = timezone.localdate()
    return render(
        request,
        "reports/index.html",
        {
            "today": today,
            "date_from": request.GET.get("date_from", today.isoformat()),
            "date_to": request.GET.get("date_to", today.isoformat()),
        },
    )


@login_required
def daily_manifest_csv(request):
    selected_date = _parse_date(request.GET.get("date")) or timezone.localdate()
    response = _csv_response(f"daily-manifest-{selected_date}.csv")
    response.write(export_daily_manifest_csv(selected_date))
    return response


@login_required
def bookings_csv(request):
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    queryset = _bookings_queryset()
    if date_from:
        queryset = queryset.filter(active_travel_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(active_travel_date__lte=date_to)
    response = _csv_response("bookings.csv")
    writer = csv.writer(response)
    _write_booking_header(writer)
    for booking in queryset:
        _write_booking_row(writer, booking)
    return response


@login_required
def capacity_summary_csv(request):
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    selected_date = _parse_date(request.GET.get("date")) or timezone.localdate()
    date_from = date_from or selected_date
    date_to = date_to or selected_date
    response = _csv_response(f"capacity-summary-{date_from}-to-{date_to}.csv")
    response.write(export_capacity_summary_csv(date_from, date_to))
    return response


@login_required
def provider_summary_csv(request):
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    response = _csv_response("provider-summary.csv")
    response.write(export_provider_summary_csv(date_from, date_to))
    return response


def _bookings_queryset():
    return Booking.objects.select_related(
        "provider",
        "activity",
        "schedule_slot",
    ).order_by("active_travel_date", "active_start_time", "provider_booking_reference")


def _csv_response(filename):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _write_booking_header(writer):
    writer.writerow(
        [
            "provider",
            "provider_booking_reference",
            "provider_order_reference",
            "active_travel_date",
            "active_start_time",
            "active_end_time",
            "activity",
            "slot",
            "lead_traveler_name",
            "active_traveler_count",
            "status",
            "pickup_location",
            "meeting_point",
            "language",
        ]
    )


def _write_booking_row(writer, booking):
    writer.writerow(
        [
            booking.provider.name,
            booking.provider_booking_reference,
            booking.provider_order_reference or "",
            booking.active_travel_date or "",
            booking.active_start_time or "",
            booking.active_end_time or "",
            booking.activity.name if booking.activity else "",
            booking.schedule_slot.start_time if booking.schedule_slot else "",
            booking.lead_traveler_name or "",
            booking.active_traveler_count or "",
            booking.status,
            booking.pickup_location or "",
            booking.meeting_point or "",
            booking.language or "",
        ]
    )


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
