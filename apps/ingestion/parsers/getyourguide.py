from .base import ParsedBooking, ProviderEmailParser
from .common import parse_labeled_booking


class GetYourGuideParser(ProviderEmailParser):
    provider_code = "getyourguide"

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
                r"\b(GYG[A-Z0-9-]+)\b",
                r"Booking reference\s*[:#-]\s*([A-Z0-9-]+)",
                r"Reference number\s*[:#-]\s*([A-Z0-9-]+)",
            ],
            order_patterns=[
                r"Order reference\s*[:#-]\s*([A-Z0-9-]+)",
                r"Order ID\s*[:#-]\s*([A-Z0-9-]+)",
            ],
            product_labels=["Activity", "Tour", "Product"],
            option_labels=["Option", "Rate option"],
            traveler_count_labels=["Participants", "Travelers", "Guests"],
            name_labels=["Customer", "Lead traveler", "Lead traveller"],
        )
