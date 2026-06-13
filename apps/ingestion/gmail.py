from .gmail_client import GmailClient


def fetch_new_messages(limit: int = 100) -> list[dict]:
    client = GmailClient()
    return [
        client.fetch_message(message_id)
        for message_id in client.list_recent_messages(limit=limit)
    ]
