from .base import ParsedBooking, ProviderEmailParser
from .common import parse_labeled_booking


class TravelExperienceParser(ProviderEmailParser):
    provider_code = "travel-experience"

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
                r"Travel Experience booking\s*[:#-]\s*([A-Z0-9-]+)",
                r"Booking reference\s*[:#-]\s*([A-Z0-9-]+)",
                r"\b(TE-[A-Z0-9-]+)\b",
            ],
            order_patterns=[r"Order reference\s*[:#-]\s*([A-Z0-9-]+)"],
            product_labels=["Product", "Tour", "Activity", "Experience"],
            option_labels=["Option", "Ticket option", "Variant"],
            traveler_count_labels=["Travelers", "Participants", "Guests", "Tickets"],
            name_labels=["Lead traveler", "Customer", "Guest"],
        )
