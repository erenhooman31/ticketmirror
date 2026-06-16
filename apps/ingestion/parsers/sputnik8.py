import re
from dataclasses import replace
from datetime import date, time

from .base import ParsedBooking, ProviderEmailParser
from .common import parse_labeled_booking

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
                r"заказ[а]?\s*(\d{6,})",
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
                "Гостей",
                "Билеты",
            ],
            name_labels=["Customer", "Lead traveler", "Name", "Клиент", "Имя"],
            language_labels=["Language", "Язык"],
            meeting_labels=["Meeting point", "Meeting location", "Место встречи"],
            requirements_labels=[
                "Special requirements",
                "Notes",
                "Комментарий туриста",
            ],
            message_labels=["Customer message", "Message", "Сообщение клиента"],
        )
        if "заказ" not in subject.lower():
            return parsed
        return replace(
            parsed,
            provider_booking_reference=parsed.provider_booking_reference
            or _reference(subject),
            raw_product_name=parsed.raw_product_name or _quoted_product(subject),
            travel_date=parsed.travel_date or _subject_date(subject, body_text),
            start_time=parsed.start_time or _subject_time(subject, body_text),
        )


def _reference(subject: str) -> str:
    match = re.search(r"заказ[а]?\s*(\d{6,})", subject, re.I)
    return match.group(1) if match else ""


def _quoted_product(subject: str) -> str:
    match = re.search(r"[«'](.+?)[»']", subject)
    return match.group(1).replace("\xa0", " ") if match else ""


def _subject_date(subject: str, body_text: str) -> date | None:
    match = re.search(r"на\s+(\d{1,2})\s+([а-яё]+)", subject, re.I)
    if not match:
        return None
    year_match = re.search(r"\b(20\d{2})\b", f"{subject}\n{body_text}")
    year = int(year_match.group(1)) if year_match else date.today().year
    month = RU_MONTHS.get(match.group(2).lower())
    if not month:
        return None
    return date(year, month, int(match.group(1)))


def _subject_time(subject: str, body_text: str) -> time | None:
    match = re.search(r"в\s+(\d{1,2})[:_](\d{2})", subject, re.I)
    if not match:
        match = re.search(r"\bat\s+(\d{1,2}):(\d{2})\s*(AM|PM)?", body_text, re.I)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    marker = (
        match.group(3).upper() if len(match.groups()) >= 3 and match.group(3) else ""
    )
    if marker == "PM" and hour < 12:
        hour += 12
    if marker == "AM" and hour == 12:
        hour = 0
    return time(hour, minute)
