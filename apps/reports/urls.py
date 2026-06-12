from django.urls import path

from .views import bookings_csv

app_name = "reports"

urlpatterns = [
    path("bookings.csv", bookings_csv, name="bookings_csv"),
]
