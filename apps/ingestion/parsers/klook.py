import re
from dataclasses import replace

from .base import ParsedBooking, ProviderEmailParser
from .common import (
    confidence_score,
    parse_date_flexible,
    parse_labeled_booking,
    parse_time_flexible,
)


class KlookParser(ProviderEmailParser):
    provider_code = "klook"

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
                r"Booking reference\s*[:#-]\s*([A-Z0-9-]+)",
                r"Booking ID\s*[:#-]\s*([A-Z0-9-]+)",
                r"\b([A-Z]{2,4}\d{5,})\b",
                r"\b(KL[A-Z0-9-]*\d[A-Z0-9-]*)\b",
            ],
            order_patterns=[r"Order ID\s*[:#-]\s*([A-Z0-9-]+)"],
            product_labels=["Activity", "Package", "Product"],
            option_labels=["Package option", "Option"],
            traveler_count_labels=["Participants", "Guests", "Quantity"],
            name_labels=["Guest", "Customer", "Lead traveler"],
        )
        subject_fields = _subject_fields(subject)
        if not subject_fields:
            return parsed
        parsed = replace(
            parsed,
            provider_booking_reference=parsed.provider_booking_reference
            or subject_fields.get("reference", ""),
            raw_product_name=parsed.raw_product_name
            or subject_fields.get("product", ""),
            travel_date=parsed.travel_date or subject_fields.get("date"),
            start_time=parsed.start_time or subject_fields.get("time"),
            lead_traveler_name=parsed.lead_traveler_name
            or subject_fields.get("customer"),
        )
        confidence, warnings = confidence_score(
            provider_found=True,
            reference=parsed.provider_booking_reference,
            travel_date=parsed.travel_date,
            product_name=parsed.raw_product_name,
            traveler_count=parsed.traveler_count,
        )
        if parsed.raw_fields.get("forwarded_from"):
            warnings.append("forwarded_email")
        if not parsed.provider_booking_reference:
            warnings.append("needs_review")
        return replace(parsed, confidence=confidence, warnings=warnings)


def _subject_fields(subject: str) -> dict:
    if not re.search(r"\bklook\s+order\s+confirmed\b", subject, re.I):
        return {}
    reference = re.search(r"\b([A-Z]{2,4}\d{5,})\b", subject)
    parts = [part.strip() for part in subject.split(" - ")]
    if len(parts) < 5:
        return {"reference": reference.group(1) if reference else ""}
    date_text = parts[-3]
    return {
        "product": parts[1],
        "date": parse_date_flexible(date_text.split(" ", 1)[0]),
        "time": parse_time_flexible(date_text),
        "customer": parts[-2],
        "reference": reference.group(1) if reference else parts[-1],
    }
