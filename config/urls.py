from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.bookings import views as booking_views

urlpatterns = [
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
    path("review/", booking_views.review_queue, name="review_queue"),
    path(
        "review/<int:item_id>/action/",
        booking_views.review_action,
        name="review_action",
    ),
    path("products/aliases/", booking_views.product_aliases, name="product_aliases"),
    path(
        "products/aliases/<int:alias_id>/approve/",
        booking_views.approve_alias,
        name="approve_alias",
    ),
    path("reports/", include("apps.reports.urls")),
]
