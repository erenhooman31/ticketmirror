import base64
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from apps.ingestion.parsers.common import extract_forwarded_headers

logger = logging.getLogger(__name__)

GMAIL_API_BASE_URL = "https://gmail.googleapis.com/gmail/v1"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


@dataclass(frozen=True)
class GmailConfig:
    mailbox: str
    client_id: str
    client_secret: str
    refresh_token: str
    pubsub_topic: str
    google_cloud_project: str

    @property
    def user_id(self) -> str:
        return self.mailbox or "me"

    @property
    def topic_name(self) -> str:
        if self.pubsub_topic.startswith("projects/"):
            return self.pubsub_topic
        if self.google_cloud_project and self.pubsub_topic:
            return f"projects/{self.google_cloud_project}/topics/{self.pubsub_topic}"
        return self.pubsub_topic


class GmailClient:
    def __init__(
        self,
        config: GmailConfig | None = None,
        *,
        access_token: str | None = None,
    ) -> None:
        self.config = config or GmailConfig(
            mailbox=settings.GMAIL_MAILBOX,
            client_id=settings.GMAIL_CLIENT_ID,
            client_secret=settings.GMAIL_CLIENT_SECRET,
            refresh_token=settings.GMAIL_REFRESH_TOKEN,
            pubsub_topic=settings.GMAIL_PUBSUB_TOPIC,
            google_cloud_project=settings.GOOGLE_CLOUD_PROJECT,
        )
        self._access_token = access_token

    def authenticate(self) -> str:
        if self._access_token:
            return self._access_token
        if not all(
            [
                self.config.client_id,
                self.config.client_secret,
                self.config.refresh_token,
            ]
        ):
            raise ImproperlyConfigured(
                "Gmail OAuth settings are incomplete. Configure "
                "GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, and GMAIL_REFRESH_TOKEN."
            )

        payload = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "refresh_token": self.config.refresh_token,
            "grant_type": "refresh_token",
        }
        response = self._http_json(
            GOOGLE_TOKEN_URL,
            method="POST",
            body=urlencode(payload).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            authenticated=False,
        )
        token = response.get("access_token")
        if not token:
            raise ImproperlyConfigured(
                "Google OAuth token response omitted access_token."
            )
        self._access_token = token
        return token

    def fetch_message(self, message_id: str) -> dict[str, Any]:
        message = self._request(
            f"/users/{self.config.user_id}/messages/{message_id}",
            query={"format": "full"},
        )
        return normalize_gmail_message(message)

    def list_history(self, start_history_id: str) -> dict[str, Any]:
        if not start_history_id:
            raise ValueError("start_history_id is required")

        message_ids: list[str] = []
        seen = set()
        latest_history_id = start_history_id
        page_token = None

        while True:
            query = {
                "startHistoryId": start_history_id,
                "historyTypes": "messageAdded",
            }
            if page_token:
                query["pageToken"] = page_token
            response = self._request(
                f"/users/{self.config.user_id}/history",
                query=query,
            )
            latest_history_id = response.get("historyId") or latest_history_id
            for history_item in response.get("history", []):
                for message_added in history_item.get("messagesAdded", []):
                    message = message_added.get("message", {})
                    message_id = message.get("id")
                    if message_id and message_id not in seen:
                        seen.add(message_id)
                        message_ids.append(message_id)
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return {
            "history_id": latest_history_id,
            "message_ids": message_ids,
        }

    def list_recent_messages(self, *, limit: int = 100, query: str = "newer_than:7d"):
        remaining = limit
        page_token = None
        message_ids: list[str] = []
        while remaining > 0:
            request_query: dict[str, Any] = {
                "maxResults": min(remaining, 100),
                "labelIds": "INBOX",
            }
            if query:
                request_query["q"] = query
            if page_token:
                request_query["pageToken"] = page_token
            response = self._request(
                f"/users/{self.config.user_id}/messages",
                query=request_query,
            )
            batch = [
                item["id"] for item in response.get("messages", []) if item.get("id")
            ]
            message_ids.extend(batch)
            remaining = limit - len(message_ids)
            page_token = response.get("nextPageToken")
            if not page_token or not batch:
                break
        return message_ids

    def setup_watch(self) -> dict[str, Any]:
        topic_name = self.config.topic_name
        if not topic_name:
            raise ImproperlyConfigured(
                "GMAIL_PUBSUB_TOPIC is required for Gmail watch."
            )
        return self._request(
            f"/users/{self.config.user_id}/watch",
            method="POST",
            body={
                "topicName": topic_name,
                "labelIds": ["INBOX"],
                "labelFilterBehavior": "INCLUDE",
            },
        )

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{GMAIL_API_BASE_URL}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {"Authorization": f"Bearer {self.authenticate()}"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        return self._http_json(url, method=method, body=data, headers=headers)

    def _http_json(
        self,
        url: str,
        *,
        method: str,
        body: bytes | None,
        headers: dict[str, str],
        authenticated: bool = True,
    ) -> dict[str, Any]:
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            logger.exception("Gmail API request failed with status %s", exc.code)
            raise
        except Exception:
            action = "authenticated" if authenticated else "OAuth"
            logger.exception("Gmail %s request failed", action)
            raise
        return json.loads(raw) if raw else {}


def normalize_gmail_message(message: dict[str, Any]) -> dict[str, Any]:
    headers = extract_headers(message)
    text_parts = extract_message_text(message)
    body_text = text_parts["body_text"]
    forwarded = extract_forwarded_headers(body_text)

    return {
        "gmail_message_id": message["id"],
        "gmail_thread_id": message.get("threadId"),
        "gmail_history_id": message.get("historyId"),
        "gmail_outer_sender": headers.get("from_email") or headers.get("from", ""),
        "original_forwarded_sender": forwarded.sender,
        "subject": headers.get("subject", ""),
        "received_at": _received_at(message, headers),
        "body_text": body_text,
        "body_html": text_parts["body_html"],
    }


def extract_headers(message: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    payload_headers = message.get("payload", {}).get("headers", [])
    for item in payload_headers:
        name = item.get("name", "").lower()
        value = item.get("value", "")
        if name and name not in headers:
            headers[name] = value
    display_name, email_address = parseaddr(headers.get("from", ""))
    if email_address:
        headers["from_email"] = email_address
    elif display_name:
        headers["from_email"] = display_name
    return headers


def extract_message_text(message: dict[str, Any]) -> dict[str, str]:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    _collect_message_parts(message.get("payload", {}), plain_parts, html_parts)

    body_html = "\n".join(part for part in html_parts if part).strip()
    body_text = "\n".join(part for part in plain_parts if part).strip()
    if not body_text and body_html:
        body_text = _html_to_text(body_html)
    return {
        "body_text": body_text,
        "body_html": body_html,
    }


def _collect_message_parts(
    part: dict[str, Any],
    plain_parts: list[str],
    html_parts: list[str],
) -> None:
    mime_type = part.get("mimeType", "")
    data = part.get("body", {}).get("data")
    if data and mime_type == "text/plain":
        plain_parts.append(_decode_body_data(data))
    elif data and mime_type == "text/html":
        html_parts.append(_decode_body_data(data))

    for child in part.get("parts", []) or []:
        _collect_message_parts(child, plain_parts, html_parts)


def _decode_body_data(data: str) -> str:
    padding = "=" * (-len(data) % 4)
    decoded = base64.urlsafe_b64decode(f"{data}{padding}")
    for encoding in ("utf-8", "latin-1"):
        try:
            return decoded.decode(encoding)
        except UnicodeDecodeError:
            continue
    return decoded.decode("utf-8", errors="replace")


def _html_to_text(value: str) -> str:
    without_scripts = re.sub(
        r"<(script|style).*?>.*?</\1>",
        "",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )
    with_breaks = re.sub(r"</?(br|p|div|tr|li|h[1-6])\b[^>]*>", "\n", without_scripts)
    without_tags = re.sub(r"<[^>]+>", " ", with_breaks)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()


def _received_at(message: dict[str, Any], headers: dict[str, str]):
    internal_date = message.get("internalDate")
    if internal_date:
        return datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC)
    date_header = headers.get("date")
    if date_header:
        parsed = parsedate_to_datetime(date_header)
        if parsed.tzinfo is None:
            parsed = timezone.make_aware(parsed, UTC)
        return parsed
    return timezone.now()
