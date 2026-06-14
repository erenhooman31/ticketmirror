from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.bookings import views as booking_views

urlpatterns = [
    path(
        "settings/tours/",
        booking_views.tour_activity_list,
        name="settings_tour_activities",
    ),
    path(
        "settings/tours/new/",
        booking_views.tour_activity_new,
        name="settings_tour_activity_new",
    ),
    path(
        "settings/tours/<int:activity_id>/",
        booking_views.tour_activity_detail,
        name="settings_tour_activity_detail",
    ),
    path(
        "settings/provider-aliases/",
        booking_views.provider_aliases,
        name="settings_provider_aliases",
    ),
    path(
        "settings/provider-aliases/<int:alias_id>/approve/",
        booking_views.approve_alias,
        name="settings_approve_alias",
    ),
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(next_page="login"),
        name="logout",
    ),
    path("", include("apps.core.urls")),
    path("bookings/", include("apps.bookings.urls")),
    path("ingestion/", include("apps.ingestion.urls")),
    path("inbox/", booking_views.review_queue, name="inbox"),
    path("review/", booking_views.review_queue, name="review_queue"),
    path(
        "inbox/raw-emails/<int:raw_email_id>/action/",
        booking_views.inbox_email_action,
        name="inbox_email_action",
    ),
    path(
        "review/<int:item_id>/action/",
        booking_views.review_action,
        name="review_action",
    ),
    path("reports/", include("apps.reports.urls")),
]
