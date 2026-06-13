import base64
import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.privacy import mask_email

from .tasks import process_gmail_notification

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def gmail_webhook(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    message = payload.get("message")
    encoded_data = message.get("data") if isinstance(message, dict) else None
    if not encoded_data:
        return JsonResponse({"error": "Pub/Sub message.data is required."}, status=400)

    try:
        decoded = base64.b64decode(encoded_data).decode("utf-8")
        notification = json.loads(decoded)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Pub/Sub message.data is invalid."}, status=400)

    if not notification.get("emailAddress") or not notification.get("historyId"):
        return JsonResponse(
            {"error": "Notification emailAddress and historyId are required."},
            status=400,
        )

    process_gmail_notification.delay(notification)
    logger.info(
        "Queued Gmail notification for %s history %s",
        mask_email(notification["emailAddress"]),
        notification["historyId"],
    )
    return JsonResponse({"status": "queued"}, status=202)
