from .base import ParsedBooking, ProviderEmailParser
from .common import parse_labeled_booking


class AlleParser(ProviderEmailParser):
    provider_code = "alle"

    def parse_content(
        self,
        *,
        subject: str,
        sender: str,
        body_text: str,
    ) -> ParsedBooking:
        return parse_labeled_booking(
            provider_code=self.provider_code,
            subject=subject,
            sender=sender,
            body_text=body_text,
            reference_patterns=[
                r"Alle booking\s*[:#-]\s*([A-Z0-9-]+)",
                r"Booking reference\s*[:#-]\s*([A-Z0-9-]+)",
                r"\b(ALLE-[A-Z0-9-]+)\b",
            ],
            order_patterns=[r"Order reference\s*[:#-]\s*([A-Z0-9-]+)"],
            product_labels=[
                "Product",
                "Tour",
                "Activity",
                "Experience",
                "Экскурсия",
                "Тур",
            ],
            option_labels=["Option", "Ticket option", "Variant", "Тип билета"],
            date_labels=["Travel date", "Date", "Visit date", "Дата", "Дата и время"],
            start_time_labels=[
                "Start time",
                "Time",
                "Visit time",
                "Время",
                "Время начала",
                "Дата и время",
            ],
            traveler_count_labels=[
                "Travelers",
                "Participants",
                "Guests",
                "Tickets",
                "Участников",
                "Участники",
                "Гостей",
                "Билеты",
            ],
            name_labels=["Lead traveler", "Customer", "Guest", "Клиент", "Имя"],
            language_labels=["Language", "Язык"],
            meeting_labels=["Meeting point", "Meeting location", "Место встречи"],
            requirements_labels=[
                "Special requirements",
                "Notes",
                "Комментарий туриста",
            ],
        )
