from django.urls import path

from .views import dashboard, search

app_name = "core"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("search/", search, name="search"),
]
