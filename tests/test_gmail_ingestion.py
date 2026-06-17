from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import pytest
from django.utils import timezone

from apps.ingestion.gmail_client import extract_message_text, normalize_gmail_message
from apps.ingestion.models import GmailSyncState, RawEmail
from apps.ingestion.polling import poll_gmail_once
from apps.ingestion.tasks import fetch_and_process_gmail_message


def _encoded(value: str) -> str:
    import base64

    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def gmail_message(*, message_id="gmail-1", history_id="101", payload=None):
    return {
        "id": message_id,
        "threadId": "thread-1",
        "historyId": history_id,
        "internalDate": "1781527200000",
        "payload": payload
        or {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "Bookings <bookings@viator.com>"},
                {"name": "Subject", "value": "Booking confirmed"},
            ],
            "body": {"data": _encoded("Booking reference BR-123\nTravelers: 2")},
        },
    }


def normalized_message(message_id="gmail-normalized-1", history_id="101"):
    return normalize_gmail_message(
        gmail_message(message_id=message_id, history_id=history_id)
    )


def test_gmail_message_decoding_works_for_plain_text():
    decoded = extract_message_text(gmail_message())

    assert decoded["body_text"] == "Booking reference BR-123\nTravelers: 2"
    assert decoded["body_html"] == ""


def test_gmail_message_decoding_works_for_multipart():
    decoded = extract_message_text(
        gmail_message(
            payload={
                "mimeType": "multipart/alternative",
                "headers": [],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": _encoded("Plain booking body")},
                    },
                    {
                        "mimeType": "text/html",
                        "body": {"data": _encoded("<p>HTML booking body</p>")},
                    },
                ],
            }
        )
    )

    assert decoded["body_text"] == "Plain booking body"
    assert decoded["body_html"] == "<p>HTML booking body</p>"


@pytest.mark.django_db
def test_duplicate_gmail_message_fetch_is_ignored():
    RawEmail.objects.create(
        gmail_message_id="duplicate-task-1",
        gmail_outer_sender="bookings@viator.com",
        subject="Already parsed",
        received_at="2026-01-01T10:00:00Z",
        body_text="Booking reference BR-123",
        parse_status=RawEmail.ParseStatus.PARSED,
    )
    with patch("apps.ingestion.tasks.GmailClient") as client_cls:
        result = fetch_and_process_gmail_message("duplicate-task-1")

    assert result == RawEmail.objects.get(gmail_message_id="duplicate-task-1").id
    client_cls.assert_not_called()
    assert RawEmail.objects.filter(gmail_message_id="duplicate-task-1").count() == 1


@pytest.mark.django_db
def test_process_fetch_creates_raw_email_and_calls_parser_service():
    gmail_client = Mock()
    gmail_client.fetch_message.return_value = normalized_message("task-created-1")
    with (
        patch("apps.ingestion.services.process_raw_email") as raw_processor,
        patch("apps.ingestion.tasks.GmailClient", return_value=gmail_client),
    ):
        result = fetch_and_process_gmail_message("task-created-1")

    raw_email = RawEmail.objects.get(gmail_message_id="task-created-1")
    assert result == raw_email.id
    assert raw_email.gmail_outer_sender == "bookings@viator.com"
    raw_processor.assert_called_once_with(raw_email.id)


@pytest.mark.django_db
def test_poll_gmail_advances_cursor_after_raw_store():
    GmailSyncState.objects.create(
        mailbox_email="bookings@example.com",
        latest_history_id="100",
    )
    client = Mock()
    client.list_history.return_value = {
        "history_id": "105",
        "message_ids": ["msg-1"],
    }
    client.fetch_message.return_value = normalized_message("msg-1", "104")

    with patch("apps.ingestion.polling.process_raw_email"):
        result = poll_gmail_once(client=client, mailbox="bookings@example.com")

    state = GmailSyncState.objects.get(mailbox_email="bookings@example.com")
    assert RawEmail.objects.filter(gmail_message_id="msg-1").exists()
    assert state.latest_history_id == "105"
    assert result.stored == 1


@pytest.mark.django_db
def test_poll_gmail_does_not_advance_cursor_when_fetch_fails_after_store():
    GmailSyncState.objects.create(
        mailbox_email="bookings@example.com",
        latest_history_id="100",
    )
    client = Mock()
    client.list_history.return_value = {
        "history_id": "106",
        "message_ids": ["msg-1", "msg-2"],
    }
    client.fetch_message.side_effect = [
        normalized_message("msg-1", "104"),
        RuntimeError("fetch failed"),
    ]

    with (
        patch("apps.ingestion.polling.process_raw_email"),
        pytest.raises(RuntimeError),
    ):
        poll_gmail_once(client=client, mailbox="bookings@example.com")

    state = GmailSyncState.objects.get(mailbox_email="bookings@example.com")
    assert RawEmail.objects.filter(gmail_message_id="msg-1").exists()
    assert state.latest_history_id == "100"
    assert state.last_error == "fetch failed"


@pytest.mark.django_db
def test_poll_gmail_history_expiry_falls_back_to_recent_list():
    GmailSyncState.objects.create(
        mailbox_email="bookings@example.com",
        latest_history_id="expired",
    )
    client = Mock()
    client.list_history.side_effect = HTTPError(
        url="https://gmail.example/history",
        code=404,
        msg="history expired",
        hdrs=None,
        fp=BytesIO(),
    )
    client.list_recent_messages.return_value = ["msg-1"]
    client.fetch_message.return_value = normalized_message("msg-1", "110")

    with patch("apps.ingestion.polling.process_raw_email"):
        result = poll_gmail_once(client=client, mailbox="bookings@example.com")

    state = GmailSyncState.objects.get(mailbox_email="bookings@example.com")
    assert result.fallback_used is True
    assert state.latest_history_id == "110"
    client.list_recent_messages.assert_called_once()


@pytest.mark.django_db
def test_poll_gmail_dedups_existing_message_id():
    GmailSyncState.objects.create(
        mailbox_email="bookings@example.com",
        latest_history_id="100",
    )
    RawEmail.objects.create(
        gmail_message_id="msg-1",
        gmail_history_id="104",
        gmail_outer_sender="bookings@viator.com",
        subject="Already parsed",
        received_at=datetime(2026, 1, 1, tzinfo=UTC),
        body_text="Booking reference BR-123",
        parse_status=RawEmail.ParseStatus.PARSED,
    )
    client = Mock()
    client.list_history.return_value = {
        "history_id": "105",
        "message_ids": ["msg-1"],
    }

    result = poll_gmail_once(client=client, mailbox="bookings@example.com")

    assert result.deduped == 1
    client.fetch_message.assert_not_called()
    assert RawEmail.objects.filter(gmail_message_id="msg-1").count() == 1


@pytest.mark.django_db
def test_poll_gmail_overlap_lock_prevents_second_cycle():
    GmailSyncState.objects.create(
        mailbox_email="bookings@example.com",
        poll_lock_token="locked",
        poll_lock_acquired_at=timezone.now(),
    )
    client = Mock()

    result = poll_gmail_once(client=client, mailbox="bookings@example.com")

    assert result.lock_skipped is True
    client.list_history.assert_not_called()
