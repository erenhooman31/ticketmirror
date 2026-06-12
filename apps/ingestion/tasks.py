from config.celery import app

from .gmail import fetch_new_messages
from .services import store_raw_email


@app.task
def fetch_gmail_messages() -> int:
    count = 0
    for payload in fetch_new_messages():
        store_raw_email(payload)
        count += 1
    return count
