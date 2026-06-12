from .base import ParsedBooking, ProviderEmailParser
from .common import parse_labeled_booking


class Sputnik8Parser(ProviderEmailParser):
    provider_code = "sputnik8"

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
                r"Booking number\s*[:#-]\s*([A-Z0-9-]+)",
                r"\b(SP8-[A-Z0-9-]+)\b",
            ],
            order_patterns=[r"Order ID\s*[:#-]\s*([A-Z0-9-]+)"],
            product_labels=["Excursion", "Tour", "Product"],
            option_labels=["Option", "Route"],
            date_labels=["Excursion date", "Date", "Travel date"],
            start_time_labels=["Excursion time", "Time", "Start time"],
            traveler_count_labels=["Participants", "Persons", "Guests"],
            name_labels=["Customer", "Lead traveler"],
        )
