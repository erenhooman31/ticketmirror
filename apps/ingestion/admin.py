from django.contrib import admin

from .models import GmailSyncState, RawEmail


@admin.register(RawEmail)
class RawEmailAdmin(admin.ModelAdmin):
    readonly_fields = (
        "gmail_message_id",
        "gmail_thread_id",
        "gmail_history_id",
        "gmail_outer_sender",
        "original_forwarded_sender",
        "subject",
        "received_at",
        "body_text",
        "body_html",
        "provider_detected",
        "parse_status",
        "parse_error",
        "parser_version",
        "created_at",
        "updated_at",
    )
    list_display = (
        "subject",
        "provider_detected",
        "gmail_outer_sender",
        "received_at",
        "parse_status",
        "parser_version",
    )
    list_filter = ("provider_detected", "parse_status", "received_at")
    search_fields = (
        "subject",
        "gmail_outer_sender",
        "original_forwarded_sender",
        "gmail_message_id",
        "gmail_thread_id",
        "body_text",
    )


@admin.register(GmailSyncState)
class GmailSyncStateAdmin(admin.ModelAdmin):
    list_display = (
        "mailbox_email",
        "latest_history_id",
        "watch_expiration",
        "last_successful_sync",
        "updated_at",
    )
    search_fields = ("mailbox_email", "latest_history_id", "last_error")
