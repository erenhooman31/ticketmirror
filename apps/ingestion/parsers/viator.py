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
            product_labels=["Tour Name", "Product", "Experience", "Tour"],
            option_labels=["Option", "Travel option", "Tour Option", "Tour Grade"],
            traveler_count_labels=["Travelers", "Travellers", "Participants"],
            name_labels=[
                "Lead traveler",
                "Lead traveller",
                "Lead Traveler Name",
                "Customer",
            ],
            product_code_labels=["Product code", "Product Code"],
            option_code_labels=["Tour Grade Code", "Option code"],
            start_time_labels=["Tour Option", "Tour Grade", "Start time", "Time"],
            language_labels=["Tour Language", "Language"],
            meeting_labels=["Meeting Point", "Meeting point", "Meeting location"],
            requirements_labels=[
                "Special Requirements",
                "Special requirements",
                "Notes",
            ],
        )
