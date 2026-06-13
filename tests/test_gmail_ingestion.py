import base64
import json
from unittest.mock import Mock, patch

import pytest

from apps.ingestion.gmail_client import extract_message_text, normalize_gmail_message
from apps.ingestion.models import RawEmail
from apps.ingestion.tasks import fetch_and_process_gmail_message


def _encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _pubsub_data(value: dict) -> str:
    return base64.b64encode(json.dumps(value).encode("utf-8")).decode("ascii")


def gmail_message(*, message_id="gmail-1", payload=None):
    return {
        "id": message_id,
        "threadId": "thread-1",
        "historyId": "history-1",
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


def normalized_message(message_id="gmail-normalized-1"):
    return normalize_gmail_message(gmail_message(message_id=message_id))


def test_gmail_webhook_enqueues_task(client):
    payload = {
        "message": {
            "messageId": "pubsub-1",
            "data": _pubsub_data(
                {
                    "emailAddress": "bookings@example.com",
                    "historyId": "12345",
                }
            ),
        }
    }

    with patch("apps.ingestion.views.process_gmail_notification.delay") as delay:
        response = client.post(
            "/ingestion/gmail/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    assert response.status_code == 202
    delay.assert_called_once_with(
        {
            "emailAddress": "bookings@example.com",
            "historyId": "12345",
        }
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
def test_duplicate_gmail_message_task_is_ignored():
    RawEmail.objects.create(
        gmail_message_id="duplicate-task-1",
        gmail_outer_sender="bookings@viator.com",
        subject="Already parsed",
        received_at="2026-01-01T10:00:00Z",
        body_text="Booking reference BR-123",
        parse_status=RawEmail.ParseStatus.PARSED,
    )
    with patch("apps.ingestion.tasks.GmailClient") as client_cls:
        result = fetch_and_process_gmail_message.apply(args=["duplicate-task-1"]).get()

    assert result == RawEmail.objects.get(gmail_message_id="duplicate-task-1").id
    client_cls.assert_not_called()
    assert RawEmail.objects.filter(gmail_message_id="duplicate-task-1").count() == 1


@pytest.mark.django_db
def test_process_task_creates_raw_email_and_calls_parser_service():
    gmail_client = Mock()
    gmail_client.fetch_message.return_value = normalized_message("task-created-1")
    with (
        patch("apps.ingestion.services.process_raw_email") as raw_processor,
        patch("apps.ingestion.tasks.GmailClient", return_value=gmail_client),
    ):
        result = fetch_and_process_gmail_message.apply(args=["task-created-1"]).get()

    raw_email = RawEmail.objects.get(gmail_message_id="task-created-1")
    assert result == raw_email.id
    assert raw_email.gmail_outer_sender == "bookings@viator.com"
    raw_processor.assert_called_once_with(raw_email.id)
