from django.urls import path

from .views import (
    customers,
    dashboard,
    healthz,
    search,
    settings_customer_fields,
    settings_home,
    settings_users_roles,
)

app_name = "core"

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("", dashboard, name="dashboard"),
    path("customers/", customers, name="customers"),
    path("search/", search, name="search"),
    path("settings/", settings_home, name="settings"),
    path(
        "settings/customer-fields/",
        settings_customer_fields,
        name="settings_customer_fields",
    ),
    path("settings/users/", settings_users_roles, name="settings_users_roles"),
]
