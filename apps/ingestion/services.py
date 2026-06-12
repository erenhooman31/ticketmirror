from django.db import transaction

from apps.bookings.models import (
    Booking,
    BookingEvent,
    ProductAlias,
    Provider,
    ReviewQueueItem,
)

from .models import RawEmail


@transaction.atomic
def store_raw_email(payload: dict) -> RawEmail:
    raw_email, _created = RawEmail.objects.update_or_create(
        gmail_message_id=payload["gmail_message_id"],
        defaults={
            "gmail_thread_id": payload.get("gmail_thread_id", ""),
            "subject": payload.get("subject", ""),
            "sender": payload.get("sender", ""),
            "received_at": payload["received_at"],
            "body_text": payload.get("body_text", ""),
            "body_html": payload.get("body_html", ""),
            "headers": payload.get("headers", {}),
        },
    )
    return raw_email


@transaction.atomic
def upsert_booking_from_parsed(raw_email: RawEmail, parsed) -> Booking:
    provider, _ = Provider.objects.get_or_create(
        code=parsed.provider_code,
        defaults={"name": parsed.provider_code.replace("-", " ").title()},
    )
    raw_email.provider = provider
    raw_email.processing_status = RawEmail.ProcessingStatus.PARSED
    raw_email.processing_error = ""
    raw_email.save(
        update_fields=[
            "provider",
            "processing_status",
            "processing_error",
            "updated_at",
        ]
    )

    alias = None
    if parsed.provider_product_name:
        alias = ProductAlias.objects.filter(
            provider=provider,
            provider_product_name__iexact=parsed.provider_product_name,
            is_active=True,
        ).first()

    defaults = {
        "raw_email": raw_email,
        "provider_payload": parsed.payload,
        "service_date": parsed.service_date,
        "time_slot": parsed.time_slot,
        "guest_name": parsed.guest_name,
        "guest_email": parsed.guest_email,
        "guest_phone": parsed.guest_phone,
        "party_size": parsed.party_size,
        "status": parsed.status,
        "provider_notes": parsed.provider_notes,
        "source_created_at": parsed.source_created_at,
        "source_updated_at": parsed.source_updated_at,
    }
    if alias:
        defaults["product"] = alias.product
        defaults["variant"] = alias.variant

    booking, created = Booking.objects.update_or_create(
        provider=provider,
        provider_reference=parsed.provider_reference,
        defaults=defaults,
    )
    BookingEvent.objects.create(
        booking=booking,
        event_type=(
            BookingEvent.EventType.CREATED
            if created
            else BookingEvent.EventType.PROVIDER_UPDATE
        ),
        message=(
            "Booking created from provider email."
            if created
            else "Booking updated from provider email."
        ),
        metadata={"raw_email_id": raw_email.id, "provider_payload": parsed.payload},
    )

    if not alias and parsed.provider_product_name:
        ReviewQueueItem.objects.create(
            provider=provider,
            booking=booking,
            raw_email=raw_email,
            title="Unmapped provider product",
            notes=parsed.provider_product_name,
        )
        BookingEvent.objects.create(
            booking=booking,
            event_type=BookingEvent.EventType.REVIEW_REQUIRED,
            message="Provider product alias could not be mapped.",
            metadata={"provider_product_name": parsed.provider_product_name},
        )

    return booking
