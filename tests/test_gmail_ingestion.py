from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.ingestion.gmail_client import (
    GmailClient,
    extract_message_text,
    normalize_gmail_message,
)
from apps.ingestion.models import GmailSyncState, RawEmail
from apps.ingestion.polling import poll_gmail_once, sync_recent_gmail
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


class RecordingGmailClient(GmailClient):
    def __init__(self, pages):
        super().__init__(access_token="test-token")
        self.pages = list(pages)
        self.requests = []

    def _request(
        self,
        path,
        *,
        method="GET",
        query=None,
        body=None,
    ):
        self.requests.append(
            {
                "path": path,
                "method": method,
                "query": query or {},
                "body": body,
            }
        )
        return self.pages.pop(0)


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


@override_settings(
    GMAIL_SYNC_QUERY="newer_than:90d -in:spam -in:trash",
    GMAIL_SYNC_LABEL_IDS=[],
)
def test_gmail_list_uses_default_sync_query_without_inbox_label():
    client = RecordingGmailClient([{"messages": [{"id": "msg-1"}]}])

    assert client.list_recent_messages(limit=10) == ["msg-1"]

    query = client.requests[0]["query"]
    assert query["q"] == "newer_than:90d -in:spam -in:trash"
    assert "labelIds" not in query
    assert "in:inbox" not in query["q"].lower()


@override_settings(
    GMAIL_SYNC_QUERY="newer_than:90d -in:spam -in:trash category:updates",
    GMAIL_SYNC_LABEL_IDS=[],
)
def test_gmail_list_passes_category_updates_query():
    client = RecordingGmailClient([{"messages": [{"id": "msg-1"}]}])

    client.list_recent_messages(limit=10)

    assert client.requests[0]["query"]["q"] == (
        "newer_than:90d -in:spam -in:trash category:updates"
    )
    assert "labelIds" not in client.requests[0]["query"]


@override_settings(
    GMAIL_SYNC_QUERY="newer_than:90d -in:spam -in:trash label:SomeCustomLabel",
    GMAIL_SYNC_LABEL_IDS=[],
)
def test_gmail_list_passes_custom_label_query():
    client = RecordingGmailClient([{"messages": [{"id": "msg-1"}]}])

    client.list_recent_messages(limit=10)

    assert client.requests[0]["query"]["q"] == (
        "newer_than:90d -in:spam -in:trash label:SomeCustomLabel"
    )
    assert "labelIds" not in client.requests[0]["query"]


@override_settings(
    GMAIL_SYNC_QUERY="newer_than:90d -in:spam -in:trash",
    GMAIL_SYNC_LABEL_IDS=["Label_123", "CATEGORY_UPDATES"],
)
def test_gmail_list_uses_label_ids_only_when_configured():
    client = RecordingGmailClient([{"messages": [{"id": "msg-1"}]}])

    client.list_recent_messages(limit=10)

    assert client.requests[0]["query"]["labelIds"] == [
        "Label_123",
        "CATEGORY_UPDATES",
    ]


@override_settings(
    GMAIL_SYNC_QUERY="newer_than:90d -in:spam -in:trash",
    GMAIL_SYNC_LABEL_IDS=[],
)
def test_gmail_list_paginates_safely():
    client = RecordingGmailClient(
        [
            {
                "messages": [{"id": "msg-1"}],
                "nextPageToken": "next-page",
            },
            {"messages": [{"id": "msg-2"}]},
        ]
    )

    assert client.list_recent_messages(limit=2) == ["msg-1", "msg-2"]
    assert client.requests[1]["query"]["pageToken"] == "next-page"


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
def test_sync_recent_gmail_forces_configured_recent_search():
    GmailSyncState.objects.create(
        mailbox_email="bookings@example.com",
        latest_history_id="100",
    )
    client = Mock()
    client.list_recent_messages.return_value = ["updates-msg-1"]
    client.fetch_message.return_value = normalized_message("updates-msg-1", "111")

    with patch("apps.ingestion.polling.process_raw_email"):
        result = sync_recent_gmail(client=client, mailbox="bookings@example.com")

    assert result["fallback_used"] is True
    client.list_history.assert_not_called()
    client.list_recent_messages.assert_called_once()
    assert RawEmail.objects.filter(gmail_message_id="updates-msg-1").exists()


@pytest.mark.django_db
def test_poll_gmail_imports_message_from_configured_non_inbox_search():
    client = Mock()
    client.list_recent_messages.return_value = ["archived-msg-1"]
    client.fetch_message.return_value = normalized_message("archived-msg-1", "120")

    with patch("apps.ingestion.polling.process_raw_email"):
        result = poll_gmail_once(client=client, mailbox="bookings@example.com")

    assert result.fallback_used is True
    assert result.stored == 1
    client.list_recent_messages.assert_called_once()
    assert RawEmail.objects.filter(gmail_message_id="archived-msg-1").count() == 1


@pytest.mark.django_db
def test_repeated_recent_sync_remains_idempotent():
    client = Mock()
    client.list_recent_messages.return_value = ["custom-label-msg-1"]
    client.fetch_message.return_value = normalized_message("custom-label-msg-1", "130")

    with patch("apps.ingestion.polling.process_raw_email"):
        sync_recent_gmail(client=client, mailbox="bookings@example.com")
        sync_recent_gmail(client=client, mailbox="bookings@example.com")

    assert RawEmail.objects.filter(gmail_message_id="custom-label-msg-1").count() == 1


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
