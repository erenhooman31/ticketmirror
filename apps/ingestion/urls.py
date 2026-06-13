from django.urls import path

from . import views

app_name = "ingestion"

urlpatterns = [
    path("gmail/webhook/", views.gmail_webhook, name="gmail_webhook"),
]
