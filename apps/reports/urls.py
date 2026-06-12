from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_index, name="index"),
    path("daily-manifest.csv", views.daily_manifest_csv, name="daily_manifest_csv"),
    path("bookings.csv", views.bookings_csv, name="bookings_csv"),
    path(
        "capacity-summary.csv",
        views.capacity_summary_csv,
        name="capacity_summary_csv",
    ),
    path(
        "provider-summary.csv",
        views.provider_summary_csv,
        name="provider_summary_csv",
    ),
]
