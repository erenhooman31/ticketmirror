import re
from dataclasses import replace
from datetime import date, time

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

RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
    "ÑÐ½Ð²Ð°Ñ€Ñ": 1,
    "Ñ„ÐµÐ²Ñ€Ð°Ð»Ñ": 2,
    "Ð¼Ð°Ñ€Ñ‚Ð°": 3,
    "Ð°Ð¿Ñ€ÐµÐ»Ñ": 4,
    "Ð¼Ð°Ñ": 5,
    "Ð¸ÑŽÐ½Ñ": 6,
    "Ð¸ÑŽÐ»Ñ": 7,
    "Ð°Ð²Ð³ÑƒÑÑ‚Ð°": 8,
    "ÑÐµÐ½Ñ‚ÑÐ±Ñ€Ñ": 9,
    "Ð¾ÐºÑ‚ÑÐ±Ñ€Ñ": 10,
    "Ð½Ð¾ÑÐ±Ñ€Ñ": 11,
    "Ð´ÐµÐºÐ°Ð±Ñ€Ñ": 12,
}


class TripsterParser(ProviderEmailParser):
    provider_code = "tripster"

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
                r"(?:№|No\.)\s*(\d{6,})",
                r"booking\s*#(\d{6,})",
                r"заказ[а]?\s*(\d{6,})",
                r"Ð·Ð°ÐºÐ°Ð·[Ð°]?\s*(\d{6,})",
                r"Order number\s*[:#-]\s*([A-Z0-9-]+)",
                r"Tripster order\s*[:#-]\s*([A-Z0-9-]+)",
                r"\b(TS-[A-Z0-9-]+)\b",
            ],
            order_patterns=[r"Order number\s*[:#-]\s*([A-Z0-9-]+)"],
            product_labels=["Product", "Activity", "Attraction", "Экскурсия", "Тур"],
            option_labels=["Ticket type", "Option", "Тип билета"],
            date_labels=["Дата", "Дата и время", "Date"],
            start_time_labels=["Время", "Время начала", "Дата и время", "Time"],
            traveler_count_labels=[
                "Ticket count",
                "Tickets",
                "Guests",
                "Участников",
                "Участники",
                "Кол-во",
                "Количество",
                "Туристов",
                "Гостей",
                "Билеты",
            ],
            name_labels=[
                "Customer name",
                "Customer",
                "Клиент",
                "Имя",
                "Турист",
                "ФИО",
                "Контактное лицо",
                "Гость",
            ],
            language_labels=["Language", "Язык"],
            meeting_labels=["Meeting point", "Meeting location", "Место встречи"],
            requirements_labels=[
                "Special requirements",
                "Notes",
                "Комментарий туриста",
            ],
            message_labels=["Customer message", "Message", "Сообщение клиента"],
        )
        content_text = _clean_layout_text(strip_forwarded_header_block(body_text))
        effective_subject = _clean_layout_text(
            parsed.raw_fields.get("effective_subject") or subject
        )
        if not re.search(r"(№|No\.|заказ|order|booking #)", effective_subject, re.I):
            return parsed

        service_date, start_time = _service_date_time(effective_subject, content_text)
        traveler_count = parsed.traveler_count or _traveler_count(
            effective_subject, content_text
        )
        reason = _cancellation_reason(content_text)
        event_type = parsed.event_type
        status = parsed.status
        if _is_cancellation(effective_subject, content_text):
            event_type = EVENT_CANCELLATION
            status = STATUS_CANCELLED
        reference = parsed.provider_booking_reference or _reference(
            effective_subject, content_text
        )
        product = parsed.raw_product_name or _product(effective_subject, content_text)
        lead_name = parsed.lead_traveler_name or _lead_name(content_text)

        parsed = replace(
            parsed,
            provider_booking_reference=reference,
            event_type=event_type,
            status=status,
            raw_product_name=product,
            travel_date=parsed.travel_date or service_date,
            start_time=parsed.start_time or start_time,
            traveler_count=traveler_count,
            lead_traveler_name=lead_name,
            ticket_breakdown=parsed.ticket_breakdown
            or ({"adult": traveler_count} if traveler_count else {}),
            customer_message=reason or parsed.customer_message,
            raw_fields={**parsed.raw_fields, "cancellation_reason": reason},
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


def _reference(subject: str, body_text: str) -> str:
    actual_match = re.search(
        r"(?:№|No\.)\s*(\d{6,})|booking\s*#(\d{6,})",
        subject,
        re.I,
    )
    if not actual_match:
        actual_match = re.search(
            r"(?:Order No\.|Заказ №|заказ)\s*(\d{6,})",
            body_text,
            re.I,
        )
    if actual_match:
        return next(group for group in actual_match.groups() if group)

    match = re.search(r"(?:№|No\.)\s*(\d{6,})|booking\s*#(\d{6,})", subject, re.I)
    if not match:
        match = re.search(
            r"(?:Order No\.|Заказ №|заказ|Ð·Ð°ÐºÐ°Ð·)\s*(\d{6,})", body_text, re.I
        )
    if not match:
        return ""
    return next(group for group in match.groups() if group)


def _clean_layout_text(value: str) -> str:
    cleaned = re.sub(r"[\u200c\u2800\xa0]+", " ", value or "")
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def _product(subject: str, body_text: str) -> str:
    for value in (subject, body_text):
        match = re.search(r"[«\"](.+?)[»\"]", value)
        if match:
            return match.group(1).replace("\xa0", " ")
    match = re.search(r"traveler canceled the \"(.+?)\" booking", body_text, re.I)
    return match.group(1) if match else ""


def _service_date_time(subject: str, body_text: str) -> tuple[date | None, time | None]:
    candidates = [
        _first_match(
            r"(?:заказ на|на)\s+"
            r"(\d{1,2}\s+[А-Яа-яЁё]+(?:\s+20\d{2})?)"
            r"\s+в\s+(\d{1,2}:\d{2})",
            body_text,
        ),
        _first_match(
            r"(?:for|на)\s+([A-Za-zА-Яа-яЁё]+\s+\d{1,2}(?:,\s+20\d{2})?|\d{1,2}\s+[А-Яа-яЁё]+(?:\s+20\d{2})?)\s+(?:at|в)\s+(\d{1,2}:\d{2}\s*(?:AM|PM)?)",
            subject,
        ),
        _first_match(
            r"\*([A-Za-z]{3},\s+[A-Za-z]+\s+\d{1,2})\*\s+(\d{1,2}:\d{2})", body_text
        ),
        _first_match(
            r"for\s+([A-Za-z]+\s+\d{1,2}(?:,\s+20\d{2})?),?\s+at\s+(\d{1,2}:\d{2}\s*(?:AM|PM)?)",
            body_text,
        ),
        _first_match(
            r"(?:заказ на|на)\s+"
            r"(\d{1,2}\s+[А-Яа-яЁё]+(?:\s+20\d{2})?)"
            r"\s+в\s+(\d{1,2}:\d{2})",
            body_text,
        ),
        _first_match(
            r"(?:for|на)\s+([A-Za-zА-Яа-яЁё]+\s+\d{1,2}(?:,\s+20\d{2})?|\d{1,2}\s+[А-Яа-яЁё]+(?:\s+20\d{2})?)\s+(?:at|в)\s+(\d{1,2}:\d{2}\s*(?:AM|PM)?)",
            subject,
        ),
    ]
    for date_value, time_value in candidates:
        if not date_value:
            continue
        year = _year(subject, body_text)
        date_value = re.sub(r"^[A-Za-z]{3},\s+", "", date_value)
        if year and not re.search(r"\b20\d{2}\b", date_value):
            date_value = f"{date_value} {year}"
        parsed_date = parse_date_flexible(date_value)
        parsed_time = parse_time_flexible(time_value)
        if parsed_date or parsed_time:
            return parsed_date, parsed_time
    return None, None


def _traveler_count(subject: str, body_text: str) -> int | None:
    patterns = [
        r"\*(\d+)\*\s+\d+\s*(?:·|Â·|Ã‚Â·|-)?\s*(?:Standard|Стандарт\w*)",
        r"\b(\d+)\s+\d+\s*(?:·|Â·|Ã‚Â·|-)\s*(?:Standard|Стандарт\w*)\b",
        r"\b(\d+)\s*(?:человека|человек|чел\.?|adults?|people|travelers?)\b",
        r"\*(\d+)\*\s+\d+\s*(?:·|Â·|-)\s*Standard",
        r"\b(\d+)\s*(?:человека|человек|people)\b",
    ]
    for value in (body_text, subject):
        for pattern in patterns:
            match = re.search(pattern, value, re.I)
            if match:
                return int(match.group(1))
    return None


def _lead_name(body_text: str) -> str | None:
    lines = [line.strip("* ") for line in body_text.splitlines() if line.strip()]
    markers = {"traveler", "путешественник", "турист"}
    for index, line in enumerate(lines):
        if line.lower() in markers and index:
            return lines[index - 1]
        if line.lower() == "traveler" and index:
            return lines[index - 1]
    name_word = r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё.'’-]+"
    initial = r"[A-ZА-ЯЁ]\."
    name_token = rf"(?:{name_word}|{initial})"
    match = re.search(
        rf"({name_token}(?:\s+{name_token}){{0,3}})\s+"
        r"(?:Traveler|Путешественник|Турист)\b",
        body_text,
    )
    if match:
        return match.group(1).strip("* ")
    return None


def _cancellation_reason(body_text: str) -> str:
    match = re.search(r"Reason for cancellation:\s*([^*\n]+)", body_text, re.I)
    if not match:
        match = re.search(r"Причина отмены:\s*([^*\n]+)", body_text, re.I)
    return match.group(1).strip() if match else ""


def _is_cancellation(subject: str, body_text: str) -> bool:
    if re.search(r"отмен", f"{subject}\n{body_text}", re.I):
        return True
    return bool(
        re.search(r"\b(cancelled|canceled)\b|отмен", f"{subject}\n{body_text}", re.I)
    )


def _first_match(pattern: str, value: str) -> tuple[str, str]:
    match = re.search(pattern, value, re.I | re.S)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def _year(subject: str, body_text: str) -> str:
    match = re.search(r"\b(20\d{2})\b", f"{subject}\n{body_text}")
    return match.group(1) if match else str(date.today().year)
