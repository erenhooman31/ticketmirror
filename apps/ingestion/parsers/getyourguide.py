import re
from dataclasses import replace

from .base import ParsedBooking, ProviderEmailParser
from .common import (
    EVENT_CANCELLATION,
    EVENT_NEW_BOOKING,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    confidence_score,
    normalize_whitespace,
    parse_date_flexible,
    parse_labeled_booking,
    parse_time_flexible,
    strip_forwarded_header_block,
)


class GetYourGuideParser(ProviderEmailParser):
    provider_code = "getyourguide"

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
            traveler_count_labels=[
                "Number of participants",
                "Participants",
                "Travelers",
                "Guests",
            ],
            name_labels=[
                "Main customer",
                "Customer",
                "Lead traveler",
                "Lead traveller",
            ],
            date_labels=["Date"],
            start_time_labels=["Date", "Time", "Start time"],
        )
        content_text = strip_forwarded_header_block(body_text)
        inline_values = _inline_booking_detail_change_values(content_text)
        service_value = inline_values.get("date") or _service_date_value(content_text)
        product = (
            parsed.raw_product_name
            or inline_values.get("product")
            or _product_from_image_block(content_text)
            or _tour_value(content_text)
        )
        option = parsed.raw_option_name or inline_values.get("option")
        traveler_count = (
            inline_values.get("traveler_count")
            or _participants_count(content_text)
            or parsed.traveler_count
        )
        lead_name = parsed.lead_traveler_name or _customer_name(content_text)
        subject_reference = _reference_from_subject(subject)
        event_type = parsed.event_type
        status = parsed.status
        if _is_cancellation_subject(subject):
            event_type = EVENT_CANCELLATION
            status = STATUS_CANCELLED
        elif _is_new_booking_subject(subject):
            event_type = EVENT_NEW_BOOKING
            status = STATUS_CONFIRMED
        reference = parsed.provider_booking_reference or subject_reference
        travel_date = (
            parse_date_flexible(_date_text(service_value))
            or parse_date_flexible(service_value)
            or parsed.travel_date
        )
        start_time = parse_time_flexible(service_value) or parsed.start_time
        raw_product_name = product
        language = parsed.language or inline_values.get("language")
        lead_phone = _lead_phone(parsed.lead_traveler_phone, content_text)
        confidence, warnings = confidence_score(
            provider_found=True,
            reference=reference,
            travel_date=travel_date,
            product_name=raw_product_name,
            traveler_count=traveler_count,
        )
        if parsed.raw_fields.get("forwarded_from"):
            warnings.append("forwarded_email")
        return replace(
            parsed,
            provider_booking_reference=reference,
            event_type=event_type,
            status=status,
            raw_product_name=raw_product_name,
            raw_option_name=option,
            travel_date=travel_date,
            start_time=start_time,
            traveler_count=traveler_count,
            lead_traveler_name=lead_name,
            lead_traveler_phone=lead_phone,
            language=language,
            confidence=confidence,
            warnings=warnings,
        )


def _inline_booking_detail_change_values(body_text: str) -> dict:
    text = normalize_whitespace(body_text)
    if "booking has changed" not in text.lower():
        return {}
    values = {}
    product_match = re.search(
        r"following booking has changed\.\s+(.+?)\s+Booking reference\s+GYG[A-Z0-9-]+",
        text,
        re.I,
    )
    if product_match:
        values.update(_split_inline_product_option(product_match.group(1)))
    date_match = re.search(
        r"\bDate\s+(?:New\s+)?"
        r"([A-Z][a-z]+ \d{1,2}, 20\d{2} at \d{1,2}:\d{2}\s*(?:AM|PM))",
        text,
        re.I,
    )
    if date_match:
        values["date"] = date_match.group(1)
    participants_match = re.search(r"\bNumber of participants\s+(\d+)\b", text, re.I)
    if participants_match:
        values["traveler_count"] = int(participants_match.group(1))
    language_match = re.search(
        r"\bLanguage\s+(.+?)\s+(?:>\s*)?Contact customer\b",
        text,
        re.I,
    )
    if language_match:
        values["language"] = normalize_whitespace(language_match.group(1))
    return values


def _split_inline_product_option(value: str) -> dict[str, str]:
    value = normalize_whitespace(value)
    option_match = re.search(
        r"\b(\d+\s*[- ]?\s*(?:hour|minute)s?\b.*)$",
        value,
        re.I,
    )
    if not option_match:
        return {"product": value}
    option = normalize_whitespace(option_match.group(1))
    product = normalize_whitespace(value[: option_match.start()])
    return {"product": product or value, "option": option}


def _date_text(value: str) -> str:
    return normalize_whitespace(
        re.sub(
            r"\s+at\s+\d{1,2}:\d{2}\s*(?:AM|PM)\b",
            "",
            value or "",
            flags=re.I,
        )
    )


def _product_from_image_block(body_text: str) -> str:
    lines = [line.strip("* ") for line in body_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line.startswith("[image:") and "logo" not in line.lower():
            for candidate in lines[index + 1 : index + 4]:
                if not candidate.startswith("[image:") and not re.match(
                    r"^(Reference number|Date|Number of participants)$",
                    candidate,
                    flags=re.I,
                ):
                    return candidate
    return ""


def _service_date_value(body_text: str) -> str:
    lines = [line.strip("* ") for line in body_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line.rstrip(":").lower() == "date":
            for candidate in lines[index + 1 : index + 4]:
                if candidate and not candidate.startswith("[image:"):
                    return candidate
    return ""


def _tour_value(body_text: str) -> str:
    lines = [line.strip("* ") for line in body_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line.rstrip(":").lower() != "tour":
            continue
        for candidate in lines[index + 1 : index + 5]:
            if not candidate.startswith("[image:") and not candidate.startswith("<"):
                return candidate
    return ""


def _participants_count(body_text: str) -> int | None:
    match = re.search(r"\((\d+)\*?\s*Persons?\)", body_text, re.I)
    if match:
        return int(match.group(1))
    return None


def _lead_phone(value: str | None, body_text: str) -> str | None:
    if not value:
        return None
    if re.search(
        r"\b(?:phone|mobile|tel|telephone)\b\s*[:#-]?\s*\+?\d",
        body_text,
        re.I,
    ):
        return value
    return None


def _customer_name(body_text: str) -> str | None:
    lines = [line.strip("* ") for line in body_text.splitlines() if line.strip()]
    for label in ("main customer", "name"):
        for index, line in enumerate(lines):
            if line.rstrip(":").lower() != label:
                continue
            for candidate in lines[index + 1 : index + 4]:
                if "@" not in candidate and not candidate.lower().startswith("phone:"):
                    return candidate
    return None


def _reference_from_subject(subject: str) -> str:
    match = re.search(r"\b(GYG[A-Z0-9-]+)\b", subject or "", flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _is_cancellation_subject(subject: str) -> bool:
    return bool(
        re.search(
            r"\b(cancelled|canceled|cancellation)\b",
            subject or "",
            flags=re.IGNORECASE,
        )
    )


def _is_new_booking_subject(subject: str) -> bool:
    return bool(re.search(r"\bnew booking received\b", subject or "", re.I))
