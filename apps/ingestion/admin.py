from django.contrib import admin

from .models import RawEmail


@admin.register(RawEmail)
class RawEmailAdmin(admin.ModelAdmin):
    readonly_fields = (
        "gmail_message_id",
        "gmail_thread_id",
        "provider",
        "subject",
        "sender",
        "received_at",
        "body_text",
        "body_html",
        "headers",
        "processing_status",
        "processing_error",
        "created_at",
        "updated_at",
    )
    list_display = ("subject", "provider", "sender", "received_at", "processing_status")
    list_filter = ("provider", "processing_status", "received_at")
    search_fields = ("subject", "sender", "gmail_message_id", "body_text")
