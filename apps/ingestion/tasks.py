from .gmail import fetch_new_messages
from .gmail_client import GmailClient
from .models import RawEmail
from .polling import poll_gmail_once, process_pending_raw_emails, sync_recent_gmail
from .services import process_gmail_message, store_raw_email


def fetch_gmail_messages() -> int:
    count = 0
    for payload in fetch_new_messages():
        store_raw_email(payload)
        count += 1
    return count


def fetch_and_process_gmail_message(message_id: str) -> int:
    existing = RawEmail.objects.filter(gmail_message_id=message_id).first()
    if existing and existing.parse_status != RawEmail.ParseStatus.PENDING:
        return existing.id

    client = GmailClient()
    message_data = client.fetch_message(message_id)
    raw_email = process_gmail_message(message_data)
    return raw_email.id


def daily_reconciliation_sync(limit: int = 100) -> dict:
    return sync_recent_gmail(limit=limit)


__all__ = [
    "daily_reconciliation_sync",
    "fetch_and_process_gmail_message",
    "fetch_gmail_messages",
    "poll_gmail_once",
    "process_pending_raw_emails",
]
