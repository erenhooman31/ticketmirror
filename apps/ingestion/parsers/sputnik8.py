import re
from dataclasses import replace
from datetime import date, time

from .base import ParsedBooking, ProviderEmailParser
from .common import (
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


class Sputnik8Parser(ProviderEmailParser):
    provider_code = "sputnik8"

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
                r"(?:заказа?|order)\s*(?:No\.)?\s*(\d{6,})",
                r"Ð·Ð°ÐºÐ°Ð·[Ð°]?\s*(\d{6,})",
                r"Order No\.\s*(\d{6,})",
                r"Order number\s*[:#-]\s*([A-Z0-9-]+)",
                r"Booking number\s*[:#-]\s*([A-Z0-9-]+)",
                r"\b(SP8-[A-Z0-9-]+)\b",
            ],
            order_patterns=[r"Order ID\s*[:#-]\s*([A-Z0-9-]+)"],
            product_labels=["Excursion", "Tour", "Product", "Экскурсия", "Тур"],
            option_labels=["Option", "Route", "Тип билета"],
            date_labels=[
                "Excursion date",
                "Date",
                "Travel date",
                "Date and time",
                "Дата",
                "Дата и время",
            ],
            start_time_labels=[
                "Excursion time",
                "Time",
                "Start time",
                "Date and time",
                "Время",
                "Время начала",
                "Дата и время",
            ],
            traveler_count_labels=[
                "Participants",
                "Participants (tickets)",
                "Persons",
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
                "Customer",
                "Lead traveler",
                "Name",
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
        content_text = strip_forwarded_header_block(body_text)
        effective_subject = parsed.raw_fields.get("effective_subject") or subject
        if not re.search(r"(заказа?|order|reservation|бронь)", effective_subject, re.I):
            return parsed

        cal_date, cal_time, cal_count, cal_product = _calendar_fields(body_text)
        date_time_value = _date_time_value(content_text)
        guide_name = _guide_name(content_text)
        lead_name = parsed.lead_traveler_name
        if lead_name and guide_name and lead_name.casefold() == guide_name.casefold():
            lead_name = None

        parsed = replace(
            parsed,
            provider_booking_reference=parsed.provider_booking_reference
            or _reference(effective_subject),
            raw_product_name=(
                parsed.raw_product_name
                or cal_product
                or _body_product(content_text)
                or _quoted_product(effective_subject)
            ),
            travel_date=parsed.travel_date
            or cal_date
            or parse_date_flexible(date_time_value)
            or _subject_date(effective_subject, body_text),
            start_time=parsed.start_time
            or cal_time
            or parse_time_flexible(date_time_value)
            or _subject_time(effective_subject, body_text),
            traveler_count=parsed.traveler_count or cal_count,
            lead_traveler_name=lead_name,
            lead_traveler_email=None,
            lead_traveler_phone=None,
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


def _reference(subject: str) -> str:
    match = re.search(
        r"(?:заказа?|order|Ð·Ð°ÐºÐ°Ð·[Ð°]?)\s*(?:No\.)?\s*(\d{6,})",
        subject,
        re.I,
    )
    return match.group(1) if match else ""


def _quoted_product(subject: str) -> str:
    match = re.search(r"[«Â«'](.+?)[»Â»']", subject)
    return match.group(1).replace("\xa0", " ") if match else ""


def _subject_date(subject: str, body_text: str) -> date | None:
    match = re.search(
        r"(?:на|for|Ð½Ð°)\s+(\d{1,2})\s+([A-Za-zА-Яа-яЁёÐ°-ÑÑ‘]+)",
        subject,
        re.I,
    )
    if not match:
        return None
    year_match = re.search(r"\b(20\d{2})\b", f"{subject}\n{body_text}")
    year = int(year_match.group(1)) if year_match else date.today().year
    month = RU_MONTHS.get(match.group(2).lower())
    if not month:
        return None
    return date(year, month, int(match.group(1)))


def _subject_time(subject: str, body_text: str) -> time | None:
    match = re.search(
        r"(?:в|at|Ð²)\s+(\d{1,2})[:_](\d{2})\s*(AM|PM)?",
        subject,
        re.I,
    )
    if not match:
        match = re.search(r"\bat\s+(\d{1,2}):(\d{2})\s*(AM|PM)?", body_text, re.I)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    marker = match.group(3).upper() if match.group(3) else ""
    if marker == "PM" and hour < 12:
        hour += 12
    if marker == "AM" and hour == 12:
        hour = 0
    return time(hour, minute)


def _date_time_value(body_text: str) -> str:
    match = re.search(r"Date and time:\s*(.+)", body_text, re.I)
    return match.group(1).strip() if match else ""


def _body_product(body_text: str) -> str:
    match = re.search(
        r"Your excursion\s+(.+?)\s*(?:<|\nhas been booked)",
        body_text,
        re.I | re.S,
    )
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _guide_name(body_text: str) -> str:
    match = re.search(r"You will be met by:\s*(.+)", body_text, re.I)
    return match.group(1).strip() if match else ""


def _calendar_fields(
    body_text: str,
) -> tuple[date | None, time | None, int | None, str]:
    start = re.search(r"^DTSTART:(\d{8})T(\d{4,6})", body_text, re.M)
    summary = re.search(r"^SUMMARY:(.+(?:\n[ \t].+)*)", body_text, re.M)
    travel_date = None
    start_time = None
    count = None
    product = ""
    if start:
        raw_date, raw_time = start.groups()
        travel_date = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:8]))
        start_time = time(int(raw_time[:2]), int(raw_time[2:4]))
    if summary:
        unfolded = re.sub(r"\r?\n[ \t]", "", summary.group(1))
        match = re.search(r"\[(\d+)\]\s*/\s*(.+)$", unfolded)
        if match:
            count = int(match.group(1))
            product = re.sub(r"\s+", " ", match.group(2)).strip()
    return travel_date, start_time, count, product
