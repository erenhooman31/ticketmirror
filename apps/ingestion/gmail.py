from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class GmailSettings:
    client_id: str
    client_secret: str
    refresh_token: str
    inbox_label: str


def get_gmail_settings() -> GmailSettings:
    return GmailSettings(
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
        refresh_token=settings.GMAIL_REFRESH_TOKEN,
        inbox_label=settings.GMAIL_INBOX_LABEL,
    )


def fetch_new_messages() -> list[dict]:
    settings_payload = get_gmail_settings()
    if not settings_payload.refresh_token:
        return []

    raise NotImplementedError(
        "Gmail API fetch implementation is intentionally scaffolded."
    )
