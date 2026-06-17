import re
from dataclasses import replace

from .base import ParsedBooking, ProviderEmailParser
from .common import (
    EVENT_CANCELLATION,
    STATUS_CANCELLED,
    parse_date_flexible,
    parse_labeled_booking,
    parse_time_flexible,
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
        service_value = _service_date_value(body_text)
        product = _product_from_image_block(body_text)
        subject_reference = _reference_from_subject(subject)
        event_type = parsed.event_type
        status = parsed.status
        if _is_cancellation_subject(subject):
            event_type = EVENT_CANCELLATION
            status = STATUS_CANCELLED
        return replace(
            parsed,
            provider_booking_reference=(
                parsed.provider_booking_reference or subject_reference
            ),
            event_type=event_type,
            status=status,
            raw_product_name=parsed.raw_product_name or product,
            travel_date=parse_date_flexible(service_value) or parsed.travel_date,
            start_time=parse_time_flexible(service_value) or parsed.start_time,
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
        if line == "Date":
            for candidate in lines[index + 1 : index + 4]:
                if candidate and not candidate.startswith("[image:"):
                    return candidate
    return ""


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
