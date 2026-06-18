import logging
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from urllib.error import HTTPError

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .gmail_client import GmailClient
from .models import GmailSyncState, RawEmail
from .services import mark_raw_email_failed, process_raw_email, store_raw_email

logger = logging.getLogger(__name__)

DEFAULT_RECENT_LIMIT = 500
DEFAULT_FALLBACK_DAYS = 7
LOCK_STALE_AFTER = timedelta(minutes=10)


class PollAlreadyRunning(RuntimeError):
    pass


@dataclass(frozen=True)
class PollResult:
    mailbox: str
    fetched: int = 0
    stored: int = 0
    processed: int = 0
    deduped: int = 0
    failed: int = 0
    skipped: int = 0
    latest_history_id: str | None = None
    fallback_used: bool = False
    lock_skipped: bool = False

    def as_dict(self) -> dict:
        return {
            "mailbox": self.mailbox,
            "fetched": self.fetched,
            "stored": self.stored,
            "processed": self.processed,
            "deduped": self.deduped,
            "failed": self.failed,
            "skipped": self.skipped,
            "latest_history_id": self.latest_history_id,
            "fallback_used": self.fallback_used,
            "lock_skipped": self.lock_skipped,
        }


def poll_gmail_once(
    *,
    client: GmailClient | None = None,
    mailbox: str | None = None,
    limit: int = DEFAULT_RECENT_LIMIT,
    fallback_days: int = DEFAULT_FALLBACK_DAYS,
    process: bool = True,
    force_recent: bool = False,
) -> PollResult:
    mailbox = mailbox or settings.GMAIL_MAILBOX or "me"
    token = _acquire_poll_lock(mailbox)
    if token is None:
        return PollResult(mailbox=mailbox, lock_skipped=True)

    client = client or GmailClient()
    fallback_used = False
    fetched = stored = processed = deduped = failed = skipped = 0
    latest_history_id = None
    try:
        state = GmailSyncState.objects.get(mailbox_email=mailbox)
        start_history_id = state.latest_history_id
        if force_recent:
            fallback_used = True
            message_ids = client.list_recent_messages(limit=limit)
        elif start_history_id:
            try:
                history = client.list_history(start_history_id)
                message_ids = history["message_ids"]
                latest_history_id = str(history.get("history_id") or start_history_id)
            except HTTPError as exc:
                if exc.code != 404:
                    raise
                fallback_used = True
                message_ids = client.list_recent_messages(limit=limit)
        else:
            fallback_used = True
            message_ids = client.list_recent_messages(limit=limit)

        for message_id in message_ids[: max(limit, 0)]:
            fetched += 1
            existing = RawEmail.objects.filter(gmail_message_id=message_id).first()
            if existing and existing.parse_status != RawEmail.ParseStatus.PENDING:
                deduped += 1
                latest_history_id = _newer_history_id(
                    latest_history_id,
                    existing.gmail_history_id,
                )
                continue

            try:
                payload = client.fetch_message(message_id)
                raw_email = store_raw_email(payload)
                raw_email.refresh_from_db()
                stored += 1
                latest_history_id = _newer_history_id(
                    latest_history_id,
                    raw_email.gmail_history_id,
                )
                if process:
                    try:
                        process_raw_email(raw_email.id)
                        processed += 1
                    except Exception as exc:
                        logger.exception("Failed to process RawEmail %s", raw_email.id)
                        mark_raw_email_failed(
                            raw_email,
                            exc,
                            title="Gmail poller processing failed",
                        )
                        failed += 1
            except HTTPError as exc:
                if exc.code != 404:
                    raise
                logger.warning(
                    "Skipping Gmail message %s because messages.get returned 404.",
                    message_id,
                )
                skipped += 1
                continue

        state.latest_history_id = latest_history_id or state.latest_history_id
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
        return PollResult(
            mailbox=mailbox,
            fetched=fetched,
            stored=stored,
            processed=processed,
            deduped=deduped,
            failed=failed,
            skipped=skipped,
            latest_history_id=state.latest_history_id,
            fallback_used=fallback_used,
        )
    except Exception as exc:
        GmailSyncState.objects.filter(mailbox_email=mailbox).update(
            last_error=str(exc),
            updated_at=timezone.now(),
        )
        raise
    finally:
        _release_poll_lock(mailbox, token)


def poll_gmail_loop(*, interval: int, **kwargs):
    while True:
        try:
            yield poll_gmail_once(**kwargs)
        except Exception:
            logger.exception("Gmail polling cycle failed")
        time.sleep(interval)


def process_pending_raw_emails(limit: int | None = None) -> int:
    queryset = RawEmail.objects.filter(parse_status=RawEmail.ParseStatus.PENDING)
    queryset = queryset.order_by("received_at", "id")
    if limit:
        queryset = queryset[:limit]

    processed = 0
    for raw_email in queryset:
        try:
            process_raw_email(raw_email.id)
            processed += 1
        except Exception as exc:
            logger.exception("Failed to process pending RawEmail %s", raw_email.id)
            mark_raw_email_failed(
                raw_email,
                exc,
                title="Pending raw email processing failed",
            )
    return processed


def sync_recent_gmail(
    *,
    limit: int = 50,
    client: GmailClient | None = None,
    mailbox: str | None = None,
) -> dict:
    return poll_gmail_once(
        client=client,
        mailbox=mailbox,
        limit=limit,
        fallback_days=DEFAULT_FALLBACK_DAYS,
        force_recent=True,
    ).as_dict()


def _acquire_poll_lock(mailbox: str) -> str | None:
    token = uuid.uuid4().hex
    now = timezone.now()
    stale_before = now - LOCK_STALE_AFTER
    state, _created = GmailSyncState.objects.get_or_create(mailbox_email=mailbox)
    with transaction.atomic():
        updated = (
            GmailSyncState.objects.select_for_update()
            .filter(id=state.id)
            .filter(
                Q(poll_lock_token__isnull=True)
                | Q(poll_lock_token="")
                | Q(poll_lock_acquired_at__lt=stale_before)
            )
            .update(
                poll_lock_token=token,
                poll_lock_acquired_at=now,
                updated_at=now,
            )
        )
    return token if updated else None


def _release_poll_lock(mailbox: str, token: str) -> None:
    GmailSyncState.objects.filter(
        mailbox_email=mailbox,
        poll_lock_token=token,
    ).update(
        poll_lock_token=None,
        poll_lock_acquired_at=None,
        updated_at=timezone.now(),
    )


def _newer_history_id(current: str | None, candidate: str | None) -> str | None:
    if not candidate:
        return current
    if not current:
        return str(candidate)
    try:
        return str(max(int(current), int(candidate)))
    except ValueError:
        return str(candidate)
