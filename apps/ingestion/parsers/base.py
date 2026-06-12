from dataclasses import dataclass, field
from datetime import date, datetime, time


@dataclass(frozen=True)
class ParsedBooking:
    provider_code: str
    provider_reference: str
    provider_product_name: str = ""
    provider_product_code: str = ""
    service_date: date | None = None
    time_slot: time | None = None
    guest_name: str = ""
    guest_email: str = ""
    guest_phone: str = ""
    party_size: int = 1
    status: str = "pending"
    provider_notes: str = ""
    source_created_at: datetime | None = None
    source_updated_at: datetime | None = None
    payload: dict = field(default_factory=dict)


class ProviderEmailParser:
    provider_code: str

    def parse(self, raw_email) -> ParsedBooking:
        raise NotImplementedError
