from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("", views.booking_list, name="list"),
    path("daily/", views.daily_operations, name="daily"),
    path(
        "slots/<str:date>/<int:slot_id>/",
        views.slot_detail,
        name="slot_detail",
    ),
    path("<int:booking_id>/", views.booking_detail, name="detail"),
    path("<int:booking_id>/edit/", views.booking_edit, name="edit"),
    path(
        "raw-emails/<int:raw_email_id>/",
        views.raw_email_detail,
        name="raw_email_detail",
    ),
    path("aliases/", views.provider_aliases, name="aliases"),
]
