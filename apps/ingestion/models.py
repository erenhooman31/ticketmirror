from django.db import models


class RawEmail(models.Model):
    class ProcessingStatus(models.TextChoices):
        STORED = "stored", "Stored"
        PARSED = "parsed", "Parsed"
        REVIEW_REQUIRED = "review_required", "Review required"
        FAILED = "failed", "Failed"

    gmail_message_id = models.CharField(max_length=180, unique=True)
    gmail_thread_id = models.CharField(max_length=180, blank=True)
    provider = models.ForeignKey(
        "bookings.Provider",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raw_emails",
    )
    subject = models.CharField(max_length=255)
    sender = models.EmailField(blank=True)
    received_at = models.DateTimeField()
    body_text = models.TextField()
    body_html = models.TextField(blank=True)
    headers = models.JSONField(default=dict, blank=True)
    processing_status = models.CharField(
        max_length=30,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.STORED,
    )
    processing_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self) -> str:
        return self.subject
