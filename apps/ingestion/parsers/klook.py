import re
from dataclasses import replace

from .base import ParsedBooking, ProviderEmailParser
from .common import (
    EVENT_CANCELLATION,
    STATUS_CANCELLED,
    confidence_score,
    parse_date_flexible,
    parse_labeled_booking,
    parse_time_flexible,
    strip_forwarded_header_block,
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
            name_labels=["Guest", "Customer", "Lead traveler", "Lead participant"],
        )
        effective_subject = parsed.raw_fields.get("effective_subject") or subject
        content_text = strip_forwarded_header_block(body_text)
        subject_fields = _subject_fields(effective_subject) or _subject_fields(subject)
        if not subject_fields:
            return parsed
        product = _body_product(content_text) or subject_fields.get("product", "")
        if _looks_like_url_product(parsed.raw_product_name):
            raw_product_name = product
        else:
            raw_product_name = parsed.raw_product_name or product
        event_type = parsed.event_type
        status = parsed.status
        if subject_fields.get("cancelled"):
            event_type = EVENT_CANCELLATION
            status = STATUS_CANCELLED
        parsed = replace(
            parsed,
            provider_booking_reference=parsed.provider_booking_reference
            or subject_fields.get("reference", ""),
            event_type=event_type,
            status=status,
            raw_product_name=raw_product_name,
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
    if not re.search(
        r"\bklook\s+order\s+(?:confirmed|canceled|cancelled)\b", subject, re.I
    ):
        return {}
    reference = re.search(r"\b([A-Z]{2,4}\d{5,})\b", subject)
    parts = [part.strip() for part in subject.split(" - ")]
    if len(parts) == 4:
        date_text = parts[-2]
        return {
            "product": parts[1],
            "date": parse_date_flexible(date_text.split(" ", 1)[0]),
            "time": parse_time_flexible(date_text),
            "customer": parts[-1],
            "reference": reference.group(1) if reference else "",
            "cancelled": bool(re.search(r"\bcancell?ed\b", subject, re.I)),
        }
    if len(parts) < 5:
        return {"reference": reference.group(1) if reference else ""}
    date_text = parts[-3]
    return {
        "product": parts[1],
        "date": parse_date_flexible(date_text.split(" ", 1)[0]),
        "time": parse_time_flexible(date_text),
        "customer": parts[-2],
        "reference": reference.group(1) if reference else parts[-1],
        "cancelled": bool(re.search(r"\bcancell?ed\b", subject, re.I)),
    }


def _body_product(body_text: str) -> str:
    patterns = [
        r"Klook has confirmed an order for\s+(.+?)(?:\s+-\s+|\s+and issued|<|$)",
        r"following Klook order has now been cancelled\.\s+(.+?)\s*(?:\n|Package:)",
        r"following Klook booking has been canceled:\s+(.+?)\s+(?:<|Booking ID|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, body_text, re.I | re.S)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def _looks_like_url_product(value: str) -> bool:
    return bool(re.match(r"URL:\s*https?://", value or "", re.I))
