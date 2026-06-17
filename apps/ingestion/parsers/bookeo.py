import re

from .base import ParsedBooking, ProviderEmailParser
from .common import (
    confidence_score,
    first_match,
    infer_event_type,
    infer_slot_type,
    labeled_value,
    normalize_whitespace,
    parse_date_flexible,
    parse_time_flexible,
    split_names,
    status_for_event,
)


class BookeoParser(ProviderEmailParser):
    provider_code = "bookeo"

    def parse_content(
        self,
        *,
        subject: str,
        sender: str,
        body_text: str,
    ) -> ParsedBooking:
        raw_product_name = labeled_value(body_text, ["Tour"])
        bookeo_reference = labeled_value(body_text, ["Booking number"])
        underlying_provider = _underlying_provider(body_text, raw_product_name)
        underlying_reference = _underlying_reference(body_text)
        if underlying_reference:
            provider_code = underlying_provider
            provider_reference = underlying_reference
        else:
            provider_code = self.provider_code
            provider_reference = bookeo_reference
        event_type = infer_event_type(subject, body_text)
        travel_date = parse_date_flexible(labeled_value(body_text, ["Date"]))
        start_time = parse_time_flexible(labeled_value(body_text, ["Time"]))
        traveler_count = _participants_count(body_text)
        lead_name = labeled_value(body_text, ["Customer"]) or _name_from_subject(
            subject,
        )
        traveler_names = _participant_names(body_text)
        if not lead_name and traveler_names:
            lead_name = traveler_names[0]

        confidence, warnings = confidence_score(
            provider_found=bool(underlying_provider),
            reference=provider_reference,
            travel_date=travel_date,
            product_name=raw_product_name,
            traveler_count=traveler_count,
        )
        if not underlying_provider:
            warnings.append("underlying_provider_missing")
        if not underlying_reference:
            warnings.append("underlying_reference_missing")

        status = status_for_event(event_type, body_text)

        return ParsedBooking(
            provider_code=provider_code,
            provider_booking_reference=provider_reference,
            provider_order_reference=(
                f"Bookeo {bookeo_reference}" if bookeo_reference else None
            ),
            event_type=event_type,
            status=status,
            raw_product_name=raw_product_name,
            travel_date=travel_date,
            start_time=start_time,
            slot_type=infer_slot_type(start_time, body_text),
            traveler_count=traveler_count,
            lead_traveler_name=lead_name,
            lead_traveler_email=labeled_value(body_text, ["Email"]) or None,
            lead_traveler_phone=labeled_value(body_text, ["Phone"]) or None,
            traveler_names=traveler_names,
            ticket_breakdown=_ticket_breakdown(body_text),
            language=labeled_value(body_text, ["Preferred language", "Language"])
            or None,
            special_requirements=labeled_value(body_text, ["Notes"]) or None,
            confidence=confidence,
            warnings=warnings,
            raw_fields={
                "subject": subject,
                "sender": sender,
                "source_channel": "bookeo",
                "bookeo_booking_number": bookeo_reference,
                "underlying_provider": underlying_provider,
                "underlying_reference": underlying_reference,
            },
        )


def _underlying_reference(body_text: str) -> str:
    notes_reference = first_match(
        body_text,
        [
            r"Notes\s+by\s+[^,\n]+.*?Booking reference\s*[:#-]\s*([A-Z0-9-]+)",
            r"Booking reference\s*[:#-]\s*([A-Z0-9-]+)",
        ],
        flags=re.IGNORECASE | re.DOTALL,
    )
    return notes_reference


def _underlying_provider(body_text: str, raw_product_name: str) -> str:
    notes_provider = first_match(
        body_text,
        [r"Notes\s+by\s+([^,\n]+)"],
    )
    return (
        _provider_code(notes_provider) or _provider_code(raw_product_name) or "bookeo"
    )


def _provider_code(value: str) -> str:
    normalized = normalize_whitespace(value).lower()
    if not normalized:
        return ""
    patterns = [
        ("getyourguide", r"\b(getyourguide|gyg)\b"),
        ("viator", r"\b(viator|tripadvisor)\b"),
        ("klook", r"\bklook\b"),
        ("tiqets", r"\btiqets\b"),
        ("tripster", r"\btripster\b"),
        ("sputnik8", r"\bsputnik\s*8\b|\bsputnik8\b"),
        ("alle", r"\balle\b"),
        ("travel-experience", r"\btravel\s+experience\b"),
    ]
    for code, pattern in patterns:
        if re.search(pattern, normalized, re.IGNORECASE):
            return code
    return ""


def _participants_count(body_text: str) -> int | None:
    participants = labeled_value(body_text, ["Participants"])
    match = re.search(r"\d+", participants)
    return int(match.group(0)) if match else None


def _participant_names(body_text: str) -> list[str]:
    names = []
    for match in re.finditer(
        r"^\s*(?:Adult|Child|Infant)\s+\d+\s*[:#-]\s*(.+?)\s*$",
        body_text,
        re.IGNORECASE | re.MULTILINE,
    ):
        value = normalize_whitespace(match.group(1))
        if value:
            names.append(value)
    if names:
        return names
    return split_names(labeled_value(body_text, ["Participants"]))


def _ticket_breakdown(body_text: str) -> dict:
    participants = labeled_value(body_text, ["Participants"])
    breakdown = {}
    for label in ("adult", "child", "infant"):
        match = re.search(rf"(\d+)\s+{label}s?\b", participants, re.IGNORECASE)
        if match:
            breakdown[label] = int(match.group(1))
    return breakdown


def _name_from_subject(subject: str) -> str | None:
    match = re.search(
        r"^(?:New booking|Booking canceled|Booking cancelled|Booking changed)"
        r"\s*-\s*(.+)$",
        subject,
        re.IGNORECASE,
    )
    if not match:
        return None
    return normalize_whitespace(match.group(1)) or None
