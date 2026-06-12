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
            "provider_reference",
            "service_date",
            "time_slot",
            "product",
            "variant",
            "guest_name",
            "party_size",
            "status",
        ]
    )
    queryset = Booking.objects.select_related(
        "provider", "product", "variant"
    ).order_by("service_date", "time_slot", "provider_reference")
    for booking in queryset:
        writer.writerow(
            [
                booking.provider.name,
                booking.provider_reference,
                booking.service_date or "",
                booking.time_slot or "",
                booking.product.name if booking.product else "",
                booking.variant.name if booking.variant else "",
                booking.guest_name,
                booking.party_size,
                booking.status,
            ]
        )
    return response
