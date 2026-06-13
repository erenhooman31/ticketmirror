from django.urls import path

from .views import dashboard, healthz, search

app_name = "core"

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("", dashboard, name="dashboard"),
    path("search/", search, name="search"),
]
