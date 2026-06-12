from .base import ParsedBooking, ProviderEmailParser
from .common import parse_labeled_booking


class TiqetsParser(ProviderEmailParser):
    provider_code = "tiqets"

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
                r"Order ID\s*[:#-]\s*(\d{5,})",
                r"Reference\s*[:#-]\s*(\d{5,})",
                r"\bTiqets order\s*(\d{5,})\b",
            ],
            order_patterns=[r"Order number\s*[:#-]\s*(\d{5,})"],
            product_labels=["Venue", "Product", "Ticket"],
            option_labels=["Ticket type", "Option"],
            date_labels=["Visit date", "Date"],
            start_time_labels=["Visit time", "Time"],
            traveler_count_labels=["Tickets", "Guests", "Visitors"],
            name_labels=["Customer", "Lead visitor"],
        )
