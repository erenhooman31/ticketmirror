import logging
from datetime import UTC, datetime

from django.conf import settings
from django.utils import timezone

from apps.bookings.models import ReviewQueueItem
from apps.core.privacy import mask_contact_text
from config.celery import app

from .gmail import fetch_new_messages
from .gmail_client import GmailClient
from .models import GmailSyncState, RawEmail
from .services import process_gmail_message, process_raw_email, store_raw_email

logger = logging.getLogger(__name__)


@app.task
def fetch_gmail_messages() -> int:
    count = 0
    for payload in fetch_new_messages():
        store_raw_email(payload)
        count += 1
    return count


@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_gmail_notification(self, notification: dict) -> dict:
    mailbox = notification["emailAddress"]
    notified_history_id = str(notification["historyId"])
    state, _created = GmailSyncState.objects.get_or_create(mailbox_email=mailbox)
    start_history_id = state.latest_history_id or notified_history_id

    client = GmailClient()
    history = client.list_history(start_history_id)
    for message_id in history["message_ids"]:
        fetch_and_process_gmail_message.delay(message_id)

    state.latest_history_id = str(history.get("history_id") or notified_history_id)
    state.last_successful_sync = timezone.now()
    state.last_error = None
    state.save(
        update_fields=[
            "latest_history_id",
            "last_successful_sync",
            "last_error",
            "updated_at",
        ]
    )
    return {
        "queued": len(history["message_ids"]),
        "latest_history_id": state.latest_history_id,
    }


@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def fetch_and_process_gmail_message(self, message_id: str) -> int:
    existing = RawEmail.objects.filter(gmail_message_id=message_id).first()
    if existing and existing.parse_status != RawEmail.ParseStatus.PENDING:
        return existing.id

    client = GmailClient()
    message_data = client.fetch_message(message_id)
    raw_email = process_gmail_message(message_data)
    return raw_email.id


@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def renew_gmail_watch(self) -> dict:
    client = GmailClient()
    response = client.setup_watch()
    mailbox = settings.GMAIL_MAILBOX or response.get("emailAddress") or "me"
    state, _created = GmailSyncState.objects.get_or_create(mailbox_email=mailbox)
    state.latest_history_id = str(response.get("historyId") or state.latest_history_id)
    state.watch_expiration = _watch_expiration(response.get("expiration"))
    state.last_successful_sync = timezone.now()
    state.last_error = None
    state.save()
    return {
        "mailbox": state.mailbox_email,
        "latest_history_id": state.latest_history_id,
        "watch_expiration": (
            state.watch_expiration.isoformat() if state.watch_expiration else None
        ),
    }


@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def daily_reconciliation_sync(self, limit: int = 100) -> dict:
    client = GmailClient()
    message_ids = client.list_recent_messages(limit=limit)
    processed = 0
    for message_id in message_ids:
        fetch_and_process_gmail_message.delay(message_id)
        processed += 1
    pending_result = process_pending_raw_emails.apply(kwargs={"limit": limit}).get()
    return {
        "queued_recent_messages": processed,
        "processed_pending_raw_emails": pending_result,
    }


@app.task
def process_pending_raw_emails(limit: int | None = None) -> int:
    queryset = RawEmail.objects.filter(parse_status=RawEmail.ParseStatus.PENDING)
    queryset = queryset.order_by("received_at")
    if limit:
        queryset = queryset[:limit]

    processed = 0
    for raw_email in queryset:
        try:
            process_raw_email(raw_email.id)
            processed += 1
        except Exception as exc:
            logger.exception("Failed to process pending RawEmail %s", raw_email.id)
            _mark_raw_email_failed(raw_email, exc)
    return processed


def _mark_raw_email_failed(raw_email: RawEmail, exc: Exception) -> None:
    raw_email.parse_status = RawEmail.ParseStatus.FAILED
    raw_email.parse_error = mask_contact_text(str(exc), limit=500)
    raw_email.save(update_fields=["parse_status", "parse_error", "updated_at"])
    ReviewQueueItem.objects.update_or_create(
        raw_email=raw_email,
        booking=None,
        issue_type=ReviewQueueItem.IssueType.PARSER_ERROR,
        status=ReviewQueueItem.Status.OPEN,
        defaults={
            "title": "Pending raw email processing failed",
            "details": raw_email.parse_error,
        },
    )


def _watch_expiration(value: str | int | None):
    if not value:
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
