from .base import ParsedBooking, ProviderEmailParser
from .common import parse_labeled_booking


class TripsterParser(ProviderEmailParser):
    provider_code = "tripster"

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
                r"Order number\s*[:#-]\s*([A-Z0-9-]+)",
                r"Tripster order\s*[:#-]\s*([A-Z0-9-]+)",
                r"\b(TS-[A-Z0-9-]+)\b",
            ],
            order_patterns=[r"Order number\s*[:#-]\s*([A-Z0-9-]+)"],
            product_labels=["Product", "Activity", "Attraction"],
            option_labels=["Ticket type", "Option"],
            traveler_count_labels=["Ticket count", "Tickets", "Guests"],
            name_labels=["Customer name", "Customer"],
        )
