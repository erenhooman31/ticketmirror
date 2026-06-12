from django.db import transaction

from apps.bookings.models import (
    Booking,
    BookingEvent,
    ProductAlias,
    Provider,
    ReviewQueueItem,
)
from apps.ingestion.parsers.common import extract_forwarded_headers

from .models import RawEmail


@transaction.atomic
def store_raw_email(payload: dict) -> RawEmail:
    forwarded = extract_forwarded_headers(payload.get("body_text", ""))
    raw_email, _created = RawEmail.objects.update_or_create(
        gmail_message_id=payload["gmail_message_id"],
        defaults={
            "gmail_thread_id": payload.get("gmail_thread_id"),
            "gmail_history_id": payload.get("gmail_history_id"),
            "gmail_outer_sender": payload.get("gmail_outer_sender", ""),
            "original_forwarded_sender": payload.get("original_forwarded_sender")
            or forwarded.sender,
            "subject": payload.get("subject", ""),
            "received_at": payload["received_at"],
            "body_text": payload.get("body_text", ""),
            "body_html": payload.get("body_html"),
        },
    )
    return raw_email


@transaction.atomic
def upsert_booking_from_parsed(raw_email: RawEmail, parsed) -> Booking:
    provider, _ = Provider.objects.get_or_create(
        code=parsed.provider_code,
        defaults={
            "name": parsed.provider_code.replace("-", " ").title(),
            "parser_key": parsed.provider_code,
        },
    )
    raw_email.provider_detected = provider
    raw_email.parse_status = RawEmail.ParseStatus.PARSED
    raw_email.parse_error = None
    raw_email.save(
        update_fields=[
            "provider_detected",
            "parse_status",
            "parse_error",
            "updated_at",
        ]
    )

    alias = _find_product_alias(provider=provider, parsed=parsed)
    defaults = {
        "provider_order_reference": parsed.provider_order_reference,
        "status": parsed.status,
        "raw_product_name": parsed.raw_product_name,
        "raw_option_name": parsed.raw_option_name,
        "provider_product_code": parsed.provider_product_code,
        "provider_option_code": parsed.provider_option_code,
        "provider_travel_date": parsed.travel_date,
        "provider_start_time": parsed.start_time,
        "provider_end_time": parsed.end_time,
        "provider_slot_type": parsed.slot_type,
        "active_travel_date": parsed.travel_date,
        "active_start_time": parsed.start_time,
        "active_end_time": parsed.end_time,
        "active_slot_type": parsed.slot_type,
        "provider_traveler_count": parsed.traveler_count,
        "active_traveler_count": parsed.traveler_count,
        "lead_traveler_name": parsed.lead_traveler_name,
        "lead_traveler_email": parsed.lead_traveler_email,
        "lead_traveler_phone": parsed.lead_traveler_phone,
        "traveler_names": parsed.traveler_names,
        "ticket_breakdown": parsed.ticket_breakdown,
        "language": parsed.language,
        "pickup_location": parsed.pickup_location,
        "meeting_point": parsed.meeting_point,
        "special_requirements": parsed.special_requirements,
        "customer_message": parsed.customer_message,
        "price": parsed.price,
        "payment_status": parsed.payment_status,
        "source_thread_id": raw_email.gmail_thread_id,
        "last_email_received_at": raw_email.received_at,
    }
    if alias:
        defaults["canonical_product"] = alias.canonical_product
        defaults["canonical_variant"] = alias.canonical_variant

    booking, created = Booking.objects.update_or_create(
        provider=provider,
        provider_booking_reference=parsed.provider_booking_reference,
        defaults=defaults,
    )
    BookingEvent.objects.create(
        booking=booking,
        event_type=(
            parsed.event_type if created else BookingEvent.EventType.EMAIL_UPDATE
        ),
        source=BookingEvent.Source.EMAIL,
        old_values={},
        new_values=parsed.payload,
        raw_email=raw_email,
    )

    if not alias and parsed.raw_product_name:
        ReviewQueueItem.objects.create(
            booking=booking,
            raw_email=raw_email,
            issue_type=ReviewQueueItem.IssueType.PRODUCT_ALIAS_MISSING,
            title="Unmapped provider product",
            details=parsed.raw_product_name,
        )
        BookingEvent.objects.create(
            booking=booking,
            event_type=BookingEvent.EventType.CONFLICT_DETECTED,
            source=BookingEvent.Source.SYSTEM,
            old_values={},
            new_values={"raw_product_name": parsed.raw_product_name},
            raw_email=raw_email,
        )

    return booking


def _find_product_alias(*, provider: Provider, parsed):
    queryset = ProductAlias.objects.filter(provider=provider, approved=True)
    if parsed.provider_product_code:
        alias = queryset.filter(
            provider_product_code=parsed.provider_product_code,
            provider_option_code=parsed.provider_option_code,
        ).first()
        if alias:
            return alias

    if parsed.raw_product_name:
        return queryset.filter(
            raw_product_name__iexact=parsed.raw_product_name,
            raw_option_name__iexact=parsed.raw_option_name or "",
        ).first()

    return None
