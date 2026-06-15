import csv
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.bookings.models import Booking, ReviewQueueItem
from apps.bookings.services import (
    export_capacity_summary_csv,
    export_daily_manifest_csv,
    export_overcapacity_csv,
    export_provider_summary_csv,
)
from apps.ingestion.models import RawEmail


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


@login_required
def overcapacity_csv(request):
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    selected_date = _parse_date(request.GET.get("date")) or timezone.localdate()
    date_from = date_from or selected_date
    date_to = date_to or selected_date
    response = _csv_response(f"overcapacity-{date_from}-to-{date_to}.csv")
    response.write(export_overcapacity_csv(date_from, date_to))
    return response


@login_required
def unmapped_provider_products_csv(request):
    response = _csv_response("unmapped-provider-products.csv")
    writer = csv.writer(response)
    writer.writerow(
        [
            "created_at",
            "provider",
            "reference",
            "raw_product_name",
            "raw_option_name",
            "issue_type",
            "details",
        ]
    )
    rows = (
        ReviewQueueItem.objects.filter(
            issue_type__in=[
                ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
                ReviewQueueItem.IssueType.PRODUCT_MISMATCH,
            ],
            status=ReviewQueueItem.Status.OPEN,
        )
        .select_related("booking", "booking__provider")
        .order_by("-created_at")
    )
    for item in rows:
        booking = item.booking
        writer.writerow(
            [
                item.created_at,
                booking.provider.name if booking and booking.provider_id else "",
                booking.provider_booking_reference if booking else "",
                booking.raw_product_name if booking else "",
                booking.raw_option_name if booking else "",
                item.issue_type,
                item.details,
            ]
        )
    return response


@login_required
def parser_failures_csv(request):
    response = _csv_response("parser-failures.csv")
    writer = csv.writer(response)
    writer.writerow(
        [
            "received_at",
            "gmail_message_id",
            "provider",
            "subject",
            "parse_status",
            "parse_error",
        ]
    )
    rows = (
        RawEmail.objects.filter(
            parse_status__in=[
                RawEmail.ParseStatus.FAILED,
                RawEmail.ParseStatus.NEEDS_REVIEW,
            ]
        )
        .select_related("provider_detected")
        .order_by("-received_at")
    )
    for raw_email in rows:
        writer.writerow(
            [
                raw_email.received_at,
                raw_email.gmail_message_id,
                (
                    raw_email.provider_detected.name
                    if raw_email.provider_detected_id
                    else ""
                ),
                raw_email.subject,
                raw_email.parse_status,
                raw_email.parse_error or "",
            ]
        )
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
