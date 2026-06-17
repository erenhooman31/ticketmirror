import re
from dataclasses import replace

from .base import ParsedBooking, ProviderEmailParser
from .common import (
    EVENT_CANCELLATION,
    EVENT_NEW_BOOKING,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    confidence_score,
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
        service_value = _service_date_value(content_text)
        product = _product_from_image_block(content_text) or _tour_value(content_text)
        traveler_count = _participants_count(content_text) or parsed.traveler_count
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
        travel_date = parse_date_flexible(service_value) or parsed.travel_date
        start_time = parse_time_flexible(service_value) or parsed.start_time
        raw_product_name = parsed.raw_product_name or product
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
            travel_date=travel_date,
            start_time=start_time,
            traveler_count=traveler_count,
            lead_traveler_name=lead_name,
            confidence=confidence,
            warnings=warnings,
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
