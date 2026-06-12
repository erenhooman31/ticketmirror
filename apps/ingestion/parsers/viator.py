from .base import ParsedBooking, ProviderEmailParser
from .common import parse_labeled_booking


class ViatorParser(ProviderEmailParser):
    provider_code = "viator"

    def parse_content(
        self,
        *,
        subject: str,
        sender: str,
        body_text: str,
    ) -> ParsedBooking:
        return parse_labeled_booking(
            provider_code=self.provider_code,
            subject=subject,
            sender=sender,
            body_text=body_text,
            reference_patterns=[
                r"\b(BR-[A-Z0-9-]+)\b",
                r"Booking reference\s*[:#-]\s*([A-Z0-9-]+)",
                r"Booking ref\s*[:#-]\s*([A-Z0-9-]+)",
            ],
            order_patterns=[
                r"Order reference\s*[:#-]\s*([A-Z0-9-]+)",
                r"Order number\s*[:#-]\s*([A-Z0-9-]+)",
            ],
            product_labels=["Product", "Experience", "Tour"],
            option_labels=["Option", "Travel option"],
            traveler_count_labels=["Travelers", "Travellers", "Participants"],
            name_labels=["Lead traveler", "Lead traveller", "Customer"],
        )
