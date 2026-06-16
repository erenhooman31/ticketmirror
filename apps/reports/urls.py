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
    path("overcapacity.csv", views.overcapacity_csv, name="overcapacity_csv"),
    path(
        "unmapped-provider-products.csv",
        views.unmapped_provider_products_csv,
        name="unmapped_provider_products_csv",
    ),
    path("parser-failures.csv", views.parser_failures_csv, name="parser_failures_csv"),
]
