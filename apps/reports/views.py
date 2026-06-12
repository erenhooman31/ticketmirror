import csv
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.services import capacity_snapshot


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
    queryset = _bookings_queryset().filter(active_travel_date=selected_date)
    response = _csv_response(f"daily-manifest-{selected_date}.csv")
    writer = csv.writer(response)
    _write_booking_header(writer)
    for booking in queryset:
        _write_booking_row(writer, booking)
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
    selected_date = _parse_date(request.GET.get("date")) or timezone.localdate()
    response = _csv_response(f"capacity-summary-{selected_date}.csv")
    writer = csv.writer(response)
    writer.writerow(
        [
            "date",
            "product",
            "variant",
            "slot",
            "confirmed_pax",
            "pending_pax",
            "capacity",
            "remaining_capacity",
        ]
    )
    seen = set()
    bookings = _bookings_queryset().filter(
        active_travel_date=selected_date,
        canonical_variant__isnull=False,
    )
    for booking in bookings:
        key = (booking.canonical_variant_id, booking.active_start_time)
        if key in seen:
            continue
        seen.add(key)
        snapshot = capacity_snapshot(
            product_variant=booking.canonical_variant,
            service_date=selected_date,
            start_time=booking.active_start_time,
        )
        writer.writerow(
            [
                selected_date,
                (
                    booking.canonical_product.canonical_name
                    if booking.canonical_product
                    else ""
                ),
                booking.canonical_variant.variant_name,
                booking.active_start_time or "",
                snapshot["confirmed"],
                snapshot["pending"],
                snapshot["capacity"],
                snapshot["remaining"],
            ]
        )
    return response


@login_required
def provider_summary_csv(request):
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    queryset = Booking.objects.select_related("provider")
    if date_from:
        queryset = queryset.filter(active_travel_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(active_travel_date__lte=date_to)
    response = _csv_response("provider-summary.csv")
    writer = csv.writer(response)
    writer.writerow(["provider", "booking_count", "confirmed_pax", "pending_pax"])
    rows = (
        queryset.values("provider__name")
        .annotate(
            booking_count=Count("id"),
            confirmed_pax=Sum(
                "active_traveler_count",
                filter=Q(status=Booking.Status.CONFIRMED),
            ),
            pending_pax=Sum(
                "active_traveler_count",
                filter=Q(status=Booking.Status.PENDING_PROVIDER_ACCEPTANCE),
            ),
        )
        .order_by("provider__name")
    )
    for row in rows:
        writer.writerow(
            [
                row["provider__name"],
                row["booking_count"],
                row["confirmed_pax"] or 0,
                row["pending_pax"] or 0,
            ]
        )
    return response


def _bookings_queryset():
    return Booking.objects.select_related(
        "provider",
        "canonical_product",
        "canonical_variant",
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
            "product",
            "variant",
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
            (
                booking.canonical_product.canonical_name
                if booking.canonical_product
                else ""
            ),
            (
                booking.canonical_variant.variant_name
                if booking.canonical_variant
                else ""
            ),
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
