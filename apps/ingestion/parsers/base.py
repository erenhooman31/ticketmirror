from dataclasses import dataclass, field, replace
from datetime import date, time


@dataclass(frozen=True)
class ParsedBooking:
    provider_code: str
    provider_booking_reference: str = ""
    provider_order_reference: str | None = None
    event_type: str = "email_new_booking"
    status: str = "pending_provider_acceptance"
    raw_product_name: str = ""
    raw_option_name: str | None = None
    provider_product_code: str | None = None
    provider_option_code: str | None = None
    travel_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    slot_type: str = ""
    traveler_count: int | None = None
    lead_traveler_name: str | None = None
    lead_traveler_email: str | None = None
    lead_traveler_phone: str | None = None
    traveler_names: list[str] = field(default_factory=list)
    ticket_breakdown: dict = field(default_factory=dict)
    language: str | None = None
    pickup_location: str | None = None
    meeting_point: str | None = None
    special_requirements: str | None = None
    customer_message: str | None = None
    price: dict = field(default_factory=dict)
    payment_status: str | None = None
    confidence: float = 0
    warnings: list[str] = field(default_factory=list)
    raw_fields: dict = field(default_factory=dict)

    @property
    def payload(self) -> dict:
        return {
            "provider_code": self.provider_code,
            "provider_booking_reference": self.provider_booking_reference,
            "provider_order_reference": self.provider_order_reference,
            "event_type": self.event_type,
            "status": self.status,
            "raw_product_name": self.raw_product_name,
            "raw_option_name": self.raw_option_name,
            "provider_product_code": self.provider_product_code,
            "provider_option_code": self.provider_option_code,
            "travel_date": self.travel_date.isoformat() if self.travel_date else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "slot_type": self.slot_type,
            "traveler_count": self.traveler_count,
            "lead_traveler_name": self.lead_traveler_name,
            "lead_traveler_email": self.lead_traveler_email,
            "lead_traveler_phone": self.lead_traveler_phone,
            "traveler_names": self.traveler_names,
            "ticket_breakdown": self.ticket_breakdown,
            "language": self.language,
            "pickup_location": self.pickup_location,
            "meeting_point": self.meeting_point,
            "special_requirements": self.special_requirements,
            "customer_message": self.customer_message,
            "price": self.price,
            "payment_status": self.payment_status,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "raw_fields": self.raw_fields,
        }


class ProviderEmailParser:
    provider_code: str

    def parse(self, raw_email) -> ParsedBooking:
        from apps.ingestion.translate import contains_cyrillic, to_english

        original_subject = raw_email.subject
        original_body = raw_email.body_text
        translated_subject = to_english(original_subject)
        translated_body = to_english(original_body)
        parsed = self.parse_content(
            subject=translated_subject,
            sender=getattr(raw_email, "original_forwarded_sender", None)
            or raw_email.gmail_outer_sender,
            body_text=translated_body,
        )
        if translated_subject == original_subject and translated_body == original_body:
            return parsed

        return replace(
            parsed,
            raw_fields={
                **parsed.raw_fields,
                "translation_applied": True,
                "translation_source_language": (
                    "ru"
                    if contains_cyrillic(f"{original_subject}\n{original_body}")
                    else ""
                ),
                "translated_subject": translated_subject,
                "translated_body": translated_body,
                "original_subject": original_subject,
            },
        )

    def parse_content(
        self,
        *,
        subject: str,
        sender: str,
        body_text: str,
    ) -> ParsedBooking:
        raise NotImplementedError
