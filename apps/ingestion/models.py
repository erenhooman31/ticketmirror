from django.db import models


class RawEmail(models.Model):
    class ParseStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PARSED = "parsed", "Parsed"
        FAILED = "failed", "Failed"
        IGNORED = "ignored", "Ignored"
        NEEDS_REVIEW = "needs_review", "Needs review"

    gmail_message_id = models.CharField(max_length=180, unique=True)
    gmail_thread_id = models.CharField(max_length=180, null=True, blank=True)
    gmail_history_id = models.CharField(max_length=180, null=True, blank=True)
    gmail_outer_sender = models.EmailField()
    original_forwarded_sender = models.EmailField(null=True, blank=True)
    subject = models.CharField(max_length=255)
    received_at = models.DateTimeField()
    body_text = models.TextField()
    body_html = models.TextField(null=True, blank=True)
    provider_detected = models.ForeignKey(
        "bookings.Provider",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raw_emails",
    )
    parse_status = models.CharField(
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.PENDING,
    )
    parse_error = models.TextField(null=True, blank=True)
    parser_version = models.CharField(max_length=80, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["gmail_thread_id"], name="raw_email_thread_idx"),
            models.Index(fields=["received_at"], name="raw_email_received_idx"),
            models.Index(fields=["parse_status"], name="raw_email_parse_status_idx"),
            models.Index(
                fields=["provider_detected", "parse_status"],
                name="raw_email_provider_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.subject} ({self.gmail_message_id})"


class GmailSyncState(models.Model):
    mailbox_email = models.EmailField(unique=True)
    latest_history_id = models.CharField(max_length=180, null=True, blank=True)
    watch_expiration = models.DateTimeField(null=True, blank=True)
    last_successful_sync = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    poll_lock_token = models.CharField(max_length=64, null=True, blank=True)
    poll_lock_acquired_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["mailbox_email"]

    def __str__(self) -> str:
        return self.mailbox_email
