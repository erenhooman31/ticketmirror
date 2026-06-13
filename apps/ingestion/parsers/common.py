import re
from dataclasses import dataclass
from datetime import date, datetime, time
from email.utils import parseaddr

from .base import ParsedBooking

EVENT_CANCELLATION = "email_cancellation"
EVENT_NEW_BOOKING = "email_new_booking"
EVENT_REQUEST = "email_booking_request"
EVENT_UPDATE = "email_update"

STATUS_CANCELLED = "cancelled"
STATUS_CONFIRMED = "confirmed"
STATUS_MANUAL_REVIEW = "manual_review"
STATUS_MODIFIED = "modified"
STATUS_PENDING = "pending_provider_acceptance"

SLOT_FIXED_TIME = "fixed_time"
SLOT_FULL_DAY = "full_day"
SLOT_HALF_DAY = "half_day"
SLOT_OPEN_TIME = "open_time"
SLOT_PRIVATE_GROUP = "private_group"

EMAIL_RE = re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
MONEY_RE = re.compile(
    r"(?P<currency>USD|EUR|GBP|TRY|\$|€|£)\s*(?P<amount>\d+(?:[,.]\d{2})?)"
    r"|(?P<amount_alt>\d+(?:[,.]\d{2})?)\s*(?P<currency_alt>USD|EUR|GBP|TRY|€|£)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ForwardedHeaders:
    sender: str | None = None
    subject: str | None = None
    date: str | None = None


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def labeled_value(text: str, labels: list[str]) -> str:
    lines = text.splitlines()
    for label in sorted(labels, key=len, reverse=True):
        pattern = re.compile(
            rf"^\s*{re.escape(label)}\s*(?P<separator>[:#-]|\s)\s*(?P<value>.+?)\s*$",
            re.IGNORECASE | re.MULTILINE,
        )
        match = pattern.search(text)
        if match:
            value = _clean_labeled_value(match.group("value"))
            if _short_label_false_positive(label, value, match.group("separator")):
                continue
            return value

        for index, line in enumerate(lines):
            if normalize_whitespace(line).lower() != label.lower():
                continue
            for candidate in lines[index + 1 : index + 6]:
                value = _clean_labeled_value(candidate)
                if value and not value.lower().startswith("[image:"):
                    return value
    return ""


def first_match(text: str, patterns: list[str], flags: int = re.IGNORECASE) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            for value in match.groups():
                if value:
                    return normalize_whitespace(value)
    return ""


def parse_date_flexible(value: str | None) -> date | None:
    value = normalize_whitespace(value)
    if not value:
        return None
    value = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\bat\b\s+\d{1,2}:\d{2}\s*(?:AM|PM)?", "", value, flags=re.I)
    value_without_time = re.sub(
        r"\s+\d{1,2}:\d{2}\s*(?:AM|PM)?$", "", value, flags=re.I
    )
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%d-%m-%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%B %d, %Y %I:%M %p",
        "%b %d, %Y %I:%M %p",
        "%A, %B %d, %Y",
        "%A, %d %B %Y",
        "%a, %b %d, %Y",
        "%A, %b %d, %Y",
    ]
    for candidate in (value, value_without_time):
        for date_format in formats:
            try:
                return datetime.strptime(candidate, date_format).date()
            except ValueError:
                continue
    return None


def parse_time_flexible(value: str | None) -> time | None:
    value = normalize_whitespace(value)
    if not value:
        return None
    value = value.replace(".", ":")
    value = re.sub(r"\s+", " ", value).upper()
    time_match = re.search(r"\b(\d{1,2}):(\d{2})\s*(AM|PM)?\b", value)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        marker = time_match.group(3)
        if marker == "PM" and hour < 12:
            hour += 12
        if marker == "AM" and hour == 12:
            hour = 0
        if hour <= 23 and minute <= 59:
            return time(hour=hour, minute=minute)
    formats = ["%H:%M", "%H:%M:%S", "%I:%M %p", "%I %p"]
    for time_format in formats:
        try:
            return datetime.strptime(value, time_format).time()
        except ValueError:
            continue
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?\b", value)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    marker = match.group(3)
    if marker == "PM" and hour < 12:
        hour += 12
    if marker == "AM" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return time(hour=hour, minute=minute)


def extract_email(text: str) -> str | None:
    match = EMAIL_RE.search(text)
    return match.group(0) if match else None


def extract_phone(text: str) -> str | None:
    match = PHONE_RE.search(text)
    if not match:
        return None
    return normalize_whitespace(match.group(0))


def extract_forwarded_headers(body_text: str) -> ForwardedHeaders:
    lines = body_text.splitlines()
    sender = subject = sent_date = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("from:"):
            nearby = "\n".join(lines[max(0, index - 2) : index + 6]).lower()
            if "forwarded" not in nearby and "original message" not in nearby:
                continue
            sender = _address_header_value(stripped)
        elif stripped.lower().startswith("subject:") and sender:
            subject = _plain_header_value(stripped)
        elif stripped.lower().startswith(("date:", "sent:")) and sender:
            sent_date = _plain_header_value(stripped)
        if sender and subject and sent_date:
            break
    return ForwardedHeaders(sender=sender, subject=subject, date=sent_date)


def extract_money(text: str) -> dict:
    match = MONEY_RE.search(text)
    if not match:
        return {}
    currency = match.group("currency") or match.group("currency_alt")
    amount = match.group("amount") or match.group("amount_alt")
    return {
        "amount": amount.replace(",", "."),
        "currency": _normalize_currency(currency),
    }


def extract_traveler_count(text: str) -> int | None:
    patterns = [
        r"(?:traveler|traveller|participant|guest|ticket|person|people|pax)s?\s*[:#-]?\s*(\d+)",
        r"(\d+)\s*(?:traveler|traveller|participant|guest|ticket|person|people|pax)s?\b",
        r"(?:adult|adults)\s*[:#-]?\s*(\d+)",
        r"\b(?:adult|adults)\s+(\d+)\b",
        r"\b(\d+)\s*(?:pcs|шт|чел|человек)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def split_names(value: str | None) -> list[str]:
    if not value:
        return []
    return [
        normalize_whitespace(name)
        for name in re.split(r",|;|\n", value)
        if normalize_whitespace(name)
    ]


def infer_event_type(subject: str, body_text: str) -> str:
    haystack = f"{subject}\n{body_text}".lower()
    if re.search(r"\b(cancelled|canceled|cancellation)\b", haystack):
        return EVENT_CANCELLATION
    if re.search(r"\b(update|modified|changed|amended)\b", haystack):
        return EVENT_UPDATE
    if re.search(r"\b(request|pending|acceptance required|urgent)\b", haystack):
        return EVENT_REQUEST
    return EVENT_NEW_BOOKING


def status_for_event(event_type: str, body_text: str) -> str:
    haystack = body_text.lower()
    if event_type == EVENT_CANCELLATION:
        return STATUS_CANCELLED
    if event_type == EVENT_UPDATE:
        return STATUS_MODIFIED
    if event_type == EVENT_REQUEST or "pending" in haystack:
        return STATUS_PENDING
    if "confirmed" in haystack or "confirmation" in haystack:
        return STATUS_CONFIRMED
    return STATUS_PENDING


def infer_slot_type(start_time: time | None, body_text: str) -> str:
    haystack = body_text.lower()
    if "private" in haystack:
        return SLOT_PRIVATE_GROUP
    if "full day" in haystack or "full-day" in haystack:
        return SLOT_FULL_DAY
    if "half day" in haystack or "half-day" in haystack:
        return SLOT_HALF_DAY
    if start_time:
        return SLOT_FIXED_TIME
    return SLOT_OPEN_TIME


def confidence_score(
    *,
    provider_found: bool,
    reference: str,
    travel_date: date | None,
    product_name: str,
    traveler_count: int | None,
) -> tuple[float, list[str]]:
    checks = {
        "provider": provider_found,
        "reference": bool(reference),
        "travel_date": travel_date is not None,
        "product_name": bool(product_name),
        "traveler_count": traveler_count is not None,
    }
    warnings = [f"{key}_missing" for key, passed in checks.items() if not passed]
    score = round(sum(checks.values()) / len(checks), 2)
    return score, warnings


def parse_labeled_booking(
    *,
    provider_code: str,
    subject: str,
    sender: str,
    body_text: str,
    reference_patterns: list[str],
    order_patterns: list[str] | None = None,
    product_labels: list[str] | None = None,
    option_labels: list[str] | None = None,
    date_labels: list[str] | None = None,
    start_time_labels: list[str] | None = None,
    end_time_labels: list[str] | None = None,
    traveler_count_labels: list[str] | None = None,
    product_code_labels: list[str] | None = None,
    option_code_labels: list[str] | None = None,
    name_labels: list[str] | None = None,
    language_labels: list[str] | None = None,
    pickup_labels: list[str] | None = None,
    meeting_labels: list[str] | None = None,
    requirements_labels: list[str] | None = None,
    message_labels: list[str] | None = None,
) -> ParsedBooking:
    effective_subject, effective_sender, forwarded = effective_message(
        subject=subject,
        sender=sender,
        body_text=body_text,
    )
    event_type = infer_event_type(effective_subject, body_text)
    status = status_for_event(event_type, body_text)
    reference = first_match(
        f"{effective_subject}\n{body_text}",
        reference_patterns,
    )
    order_reference = first_match(body_text, order_patterns or [])
    raw_product_name = labeled_value(
        body_text,
        product_labels or ["Product", "Tour", "Activity", "Experience"],
    )
    raw_option_name = (
        labeled_value(
            body_text,
            option_labels or ["Option", "Variant", "Ticket option"],
        )
        or None
    )
    provider_product_code = (
        labeled_value(
            body_text,
            product_code_labels or ["Product code", "Activity code"],
        )
        or None
    )
    provider_option_code = (
        labeled_value(
            body_text,
            option_code_labels or ["Option code"],
        )
        or None
    )
    travel_date = parse_date_flexible(
        labeled_value(
            body_text,
            date_labels or ["Travel date", "Date", "Visit date", "Tour date"],
        )
    )
    start_time = parse_time_flexible(
        labeled_value(
            body_text,
            start_time_labels or ["Start time", "Time", "Visit time"],
        )
    )
    end_time = parse_time_flexible(
        labeled_value(body_text, end_time_labels or ["End time"])
    )
    traveler_count = _labeled_traveler_count(
        body_text,
        traveler_count_labels
        or ["Travelers", "Travellers", "Participants", "Guests", "Tickets"],
    )
    if traveler_count is None:
        traveler_count = extract_traveler_count(body_text)
    lead_name = (
        labeled_value(
            body_text,
            name_labels or ["Lead traveler", "Lead traveller", "Customer", "Guest"],
        )
        or None
    )
    email = _lead_email(body_text, sender)
    phone = extract_phone(body_text)
    traveler_names = split_names(
        labeled_value(body_text, ["Traveler names", "Travellers", "Participants"])
    )
    price = extract_money(body_text)
    confidence, warnings = confidence_score(
        provider_found=True,
        reference=reference,
        travel_date=travel_date,
        product_name=raw_product_name,
        traveler_count=traveler_count,
    )
    if forwarded.sender:
        warnings.append("forwarded_email")
    if not reference:
        status = STATUS_MANUAL_REVIEW
        warnings.append("needs_review")

    return ParsedBooking(
        provider_code=provider_code,
        provider_booking_reference=reference,
        provider_order_reference=order_reference or None,
        event_type=event_type,
        status=status,
        raw_product_name=raw_product_name,
        raw_option_name=raw_option_name,
        provider_product_code=provider_product_code,
        provider_option_code=provider_option_code,
        travel_date=travel_date,
        start_time=start_time,
        end_time=end_time,
        slot_type=infer_slot_type(start_time, body_text),
        traveler_count=traveler_count,
        lead_traveler_name=lead_name,
        lead_traveler_email=email,
        lead_traveler_phone=phone,
        traveler_names=traveler_names,
        ticket_breakdown=_ticket_breakdown(body_text),
        language=labeled_value(body_text, language_labels or ["Language"]) or None,
        pickup_location=labeled_value(
            body_text,
            pickup_labels or ["Pickup", "Pickup location"],
        )
        or None,
        meeting_point=labeled_value(
            body_text,
            meeting_labels or ["Meeting point", "Meeting location"],
        )
        or None,
        special_requirements=labeled_value(
            body_text,
            requirements_labels or ["Special requirements", "Notes"],
        )
        or None,
        customer_message=labeled_value(
            body_text,
            message_labels or ["Customer message", "Message"],
        )
        or None,
        price=price,
        payment_status=labeled_value(body_text, ["Payment status", "Payment"]) or None,
        confidence=confidence,
        warnings=warnings,
        raw_fields={
            "subject": subject,
            "sender": sender,
            "effective_subject": effective_subject,
            "effective_sender": effective_sender,
            "forwarded_from": forwarded.sender,
            "forwarded_subject": forwarded.subject,
            "forwarded_date": forwarded.date,
        },
    )


def effective_message(
    *,
    subject: str,
    sender: str,
    body_text: str,
) -> tuple[str, str, ForwardedHeaders]:
    forwarded = extract_forwarded_headers(body_text)
    effective_subject = forwarded.subject or subject
    effective_sender = forwarded.sender or sender
    return effective_subject, effective_sender, forwarded


def _labeled_traveler_count(text: str, labels: list[str]) -> int | None:
    value = labeled_value(text, labels)
    if not value:
        return None
    preferred = re.search(
        r"(\d+)[^\w\d]*(?:persons|people|participants|guests|adults|pcs|чел|человек)\b",
        value,
        re.IGNORECASE,
    )
    if preferred:
        return int(preferred.group(1))
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def _ticket_breakdown(text: str) -> dict:
    breakdown = {}
    for label in ("adult", "child", "infant", "senior", "student"):
        match = re.search(rf"\b{label}s?\s*[:#-]?\s*(\d+)", text, re.IGNORECASE)
        if match:
            breakdown[label] = int(match.group(1))
    return breakdown


def _address_header_value(line: str) -> str:
    _name, value = line.split(":", 1)
    parsed_name, parsed_email = parseaddr(value.strip())
    if parsed_email:
        return parsed_email
    return normalize_whitespace(parsed_name or value)


def _plain_header_value(line: str) -> str:
    _name, value = line.split(":", 1)
    return normalize_whitespace(value)


def _clean_labeled_value(value: str | None) -> str:
    value = normalize_whitespace(value)
    if not value:
        return ""
    value = value.strip("* \t")
    return normalize_whitespace(value)


def _short_label_false_positive(label: str, value: str, separator: str) -> bool:
    if separator != " ":
        return False
    if " " in label:
        return False
    first_word = value.split(" ", 1)[0].rstrip(":").lower()
    return first_word in {
        "code",
        "id",
        "name",
        "grade",
        "language",
        "date",
        "time",
        "location",
        "point",
        "reference",
    }


def _lead_email(body_text: str, sender: str) -> str | None:
    explicit = re.search(
        r"^Email\s*[:#-]?\s*(?P<email>\S+@\S+)$", body_text, re.I | re.M
    )
    if explicit:
        return explicit.group("email")
    emails = []
    for line in body_text.splitlines():
        if line.strip().lower().startswith(("from:", "to:", "subject:", "date:")):
            continue
        emails.extend(EMAIL_RE.findall(line))
    sender_email = extract_email(sender or "")
    for email in emails:
        if email != sender_email:
            return email
    return emails[0] if emails else None


def _normalize_currency(currency: str) -> str:
    mapping = {"$": "USD", "€": "EUR", "£": "GBP"}
    return mapping.get(currency.upper(), currency.upper())
