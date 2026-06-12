import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from apps.bookings.models import Booking


@login_required
def bookings_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="bookings.csv"'
    writer = csv.writer(response)
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
        ]
    )
    queryset = Booking.objects.select_related(
        "provider", "canonical_product", "canonical_variant"
    ).order_by("active_travel_date", "active_start_time", "provider_booking_reference")
    for booking in queryset:
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
            ]
        )
    return response
