from django.urls import path

from .views import (
    agenda_print,
    cancel_home_booking,
    create_home_booking,
    credits,
    customers,
    dashboard,
    healthz,
    mark_home_messages_read,
    search,
    settings_customer_fields,
    settings_home,
    settings_ingestion,
    settings_users_roles,
    update_home_booking_attendance,
    update_home_slot_capacity,
)

app_name = "core"

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("", dashboard, name="dashboard"),
    path("agenda/print/", agenda_print, name="agenda_print"),
    path(
        "messages/mark-all-read/",
        mark_home_messages_read,
        name="mark_home_messages_read",
    ),
    path(
        "bookings/<int:booking_id>/cancel/",
        cancel_home_booking,
        name="cancel_home_booking",
    ),
    path(
        "bookings/<int:booking_id>/attendance/",
        update_home_booking_attendance,
        name="update_home_booking_attendance",
    ),
    path(
        "agenda/<str:service_date>/slots/<int:slot_id>/new-booking/",
        create_home_booking,
        name="create_home_booking",
    ),
    path(
        "agenda/<str:service_date>/slots/<int:slot_id>/capacity/",
        update_home_slot_capacity,
        name="update_home_slot_capacity",
    ),
    path("credits/", credits, name="credits"),
    path("customers/", customers, name="customers"),
    path("search/", search, name="search"),
    path("settings/", settings_home, name="settings"),
    path(
        "settings/customer-fields/",
        settings_customer_fields,
        name="settings_customer_fields",
    ),
    path("settings/ingestion/", settings_ingestion, name="settings_ingestion"),
    path("settings/users/", settings_users_roles, name="settings_users_roles"),
]
