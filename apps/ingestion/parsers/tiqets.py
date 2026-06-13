from dataclasses import replace

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
        parsed = parse_labeled_booking(
            provider_code=self.provider_code,
            subject=subject,
            sender=sender,
            body_text=body_text,
            reference_patterns=[
                r"Reference ID\s*(\d{5,})",
                r"Order ID\s*[:#-]\s*(\d{5,})",
                r"Reference\s*[:#-]\s*(\d{5,})",
                r"\bTiqets order\s*(\d{5,})\b",
            ],
            order_patterns=[
                r"order number\s*[:#-]\s*(\d{5,})",
                r"Order number\s*[:#-]\s*(\d{5,})",
            ],
            product_labels=["Venue", "Product", "Ticket"],
            option_labels=["Ticket type", "Option"],
            date_labels=["Visit date", "Date"],
            start_time_labels=["Visit time", "Time"],
            traveler_count_labels=["Tickets", "Guests", "Visitors", "Adult"],
            name_labels=["Customer", "Lead visitor", "First name"],
            language_labels=["Selected language"],
        )
        if parsed.raw_product_name:
            return parsed
        product = _product_after_selected_language(body_text)
        return replace(parsed, raw_product_name=product) if product else parsed


def _product_after_selected_language(body_text: str) -> str:
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line.lower().startswith("selected language"):
            for candidate in lines[index + 1 : index + 4]:
                if not candidate.lower().startswith(("reference id", "visit date")):
                    return candidate
    return ""
