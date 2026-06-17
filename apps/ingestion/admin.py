from django.contrib import admin
from django.template.defaultfilters import truncatechars
from django.utils.html import format_html

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
        "body_text_preview",
        "body_html_preview",
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
        "original_forwarded_sender",
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
        "parse_error",
    )
    date_hierarchy = "received_at"
    fieldsets = (
        (
            "Message",
            {
                "fields": (
                    "gmail_message_id",
                    "gmail_thread_id",
                    "gmail_history_id",
                    "subject",
                    "gmail_outer_sender",
                    "original_forwarded_sender",
                    "received_at",
                )
            },
        ),
        (
            "Parsing",
            {
                "fields": (
                    "provider_detected",
                    "parse_status",
                    "parse_error",
                    "parser_version",
                )
            },
        ),
        (
            "Body preview",
            {
                "fields": ("body_text_preview", "body_html_preview"),
                "classes": ("collapse",),
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Body text")
    def body_text_preview(self, obj):
        style = "white-space:pre-wrap;max-height:24rem;overflow:auto;"
        return format_html(
            '<pre style="{}">{}</pre>',
            style,
            truncatechars(obj.body_text, 6000),
        )

    @admin.display(description="Body HTML")
    def body_html_preview(self, obj):
        if not obj.body_html:
            return ""
        style = "white-space:pre-wrap;max-height:18rem;overflow:auto;"
        return format_html(
            '<pre style="{}">{}</pre>',
            style,
            truncatechars(obj.body_html, 4000),
        )


@admin.register(GmailSyncState)
class GmailSyncStateAdmin(admin.ModelAdmin):
    list_display = (
        "mailbox_email",
        "latest_history_id",
        "poll_lock_acquired_at",
        "last_successful_sync",
        "updated_at",
    )
    list_filter = ("last_successful_sync", "poll_lock_acquired_at", "updated_at")
    search_fields = ("mailbox_email", "latest_history_id", "last_error")
    readonly_fields = ("updated_at",)
