from dataclasses import dataclass, field
from datetime import date, time


@dataclass(frozen=True)
class ParsedBooking:
    provider_code: str
    provider_booking_reference: str
    provider_order_reference: str | None = None
    provider_product_name: str = ""
    provider_option_name: str | None = None
    provider_product_code: str | None = None
    provider_option_code: str | None = None
    service_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    slot_type: str = ""
    traveler_count: int | None = None
    status: str = "pending_provider_acceptance"
    lead_traveler_name: str | None = None
    lead_traveler_email: str | None = None
    lead_traveler_phone: str | None = None
    traveler_names: list[str] = field(default_factory=list)
    ticket_breakdown: dict = field(default_factory=dict)
    language: str | None = None
    pickup_location: str | None = None
    meeting_point: str | None = None
    special_requirements: str | None = None
    customer_message: str | None = None
    price: dict = field(default_factory=dict)
    payment_status: str | None = None
    payload: dict = field(default_factory=dict)


class ProviderEmailParser:
    provider_code: str

    def parse(self, raw_email) -> ParsedBooking:
        raise NotImplementedError
