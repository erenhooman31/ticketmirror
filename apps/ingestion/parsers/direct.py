from .base import ParsedBooking, ProviderEmailParser
from .common import parse_labeled_booking


class DirectParser(ProviderEmailParser):
    provider_code = "direct"

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
                r"Booking reference\s*[:#-]\s*([A-Z0-9-]+)",
                r"Reference\s*[:#-]\s*([A-Z0-9-]+)",
                r"\b(DIR-[A-Z0-9-]+)\b",
            ],
            order_patterns=[r"Order reference\s*[:#-]\s*([A-Z0-9-]+)"],
            product_labels=["Product", "Tour", "Activity"],
            option_labels=["Option", "Variant"],
            traveler_count_labels=["Travelers", "Participants", "Guests"],
            name_labels=["Lead traveler", "Guest", "Customer"],
        )
