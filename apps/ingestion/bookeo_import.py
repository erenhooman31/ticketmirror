import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.bookings.models import (
    ActivitySchedule,
    ActivityScheduleSlot,
    Booking,
    BookingEvent,
    Provider,
    ProviderAlias,
    ReviewQueueItem,
)
from apps.bookings.services import is_manually_overridden
from apps.ingestion.providers import provider_display_name

BOOKEO_BASE_URL = "https://api.bookeo.com/v2"
DEFAULT_FROM_DATE = date(2024, 5, 19)
DEFAULT_FORWARD_DAYS = 365
DEFAULT_ITEMS_PER_PAGE = 100
DEFAULT_THROTTLE_SECONDS = 0.25


@dataclass
class BookeoImportStats:
    windows_processed: int = 0
    fetched: int = 0
    created: int = 0
    updated: int = 0
    unmapped_to_review: int = 0
    skipped: int = 0

    def add_result(self, result: str) -> None:
        if result == "created":
            self.created += 1
        elif result == "updated":
            self.updated += 1
        elif result == "unmapped":
            self.unmapped_to_review += 1
        elif result == "skipped":
            self.skipped += 1

    def as_dict(self) -> dict[str, int]:
        return {
            "windows_processed": self.windows_processed,
            "fetched": self.fetched,
            "created": self.created,
            "updated": self.updated,
            "unmapped_to_review": self.unmapped_to_review,
            "skipped": self.skipped,
        }


@dataclass(frozen=True)
class BookingIdentity:
    provider_code: str
    reference: str
    bookeo_booking_number: str
    underlying_provider_code: str = ""
    underlying_reference: str = ""


@dataclass
class ImportOutcome:
    result: str
    booking: Booking | None = None
    unmapped: bool = False


@dataclass
class BookeoNormalizedBooking:
    identity: BookingIdentity
    raw_product_name: str
    provider_product_code: str | None
    provider_values: dict[str, Any]
    active_values: dict[str, Any]
    raw_payload: dict[str, Any]
    alias: ProviderAlias | None = None
    schedule_slot: ActivityScheduleSlot | None = None
    warnings: list[str] = field(default_factory=list)


class BookeoApiClient:
    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        base_url: str = BOOKEO_BASE_URL,
        timeout: int = 30,
        throttle_seconds: float = DEFAULT_THROTTLE_SECONDS,
        max_retries: int = 5,
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.throttle_seconds = throttle_seconds
        self.max_retries = max_retries

    def list_bookings(
        self,
        *,
        begin_date: date,
        end_date: date,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        page_navigation_token: str | None = None,
        page_number: int = 1,
    ) -> dict[str, Any]:
        if page_navigation_token:
            params = {
                "pageNavigationToken": page_navigation_token,
                "pageNumber": page_number,
            }
        else:
            params = {
                "beginDate": begin_date.isoformat(),
                "endDate": end_date.isoformat(),
                "itemsPerPage": min(items_per_page, DEFAULT_ITEMS_PER_PAGE),
                "expandParticipants": "true",
                "expandCustomer": "true",
            }
        return self._request_json("GET", "/bookings", params=params)

    def get_booking(self, booking_number: str) -> dict[str, Any]:
        return self._request_json("GET", f"/bookings/{booking_number}", params={})

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if self.throttle_seconds:
            time.sleep(self.throttle_seconds)
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Bookeo-apiKey": self.api_key,
                "X-Bookeo-secretKey": self.secret_key,
            },
        )
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = response.read().decode("utf-8")
                    return json.loads(body) if body else {}
            except urllib.error.HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504}:
                    raise
                if attempt >= self.max_retries:
                    raise
                retry_after = exc.headers.get("Retry-After")
                sleep_for = float(retry_after) if retry_after else delay
                time.sleep(sleep_for)
                delay *= 2
        return {}


class JsonCheckpointStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"completed_windows": [], "current_window": None}
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def window_completed(self, begin_date: date, end_date: date) -> bool:
        state = self.load()
        return _window_key(begin_date, end_date) in state.get("completed_windows", [])

    def current_page(self, begin_date: date, end_date: date) -> tuple[int, str | None]:
        state = self.load()
        current = state.get("current_window") or {}
        if current.get("key") != _window_key(begin_date, end_date):
            return 1, None
        return int(current.get("next_page") or 1), current.get("page_navigation_token")

    def save_page(
        self,
        *,
        begin_date: date,
        end_date: date,
        next_page: int,
        page_navigation_token: str | None,
    ) -> None:
        state = self.load()
        state["current_window"] = {
            "key": _window_key(begin_date, end_date),
            "begin": begin_date.isoformat(),
            "end": end_date.isoformat(),
            "next_page": next_page,
            "page_navigation_token": page_navigation_token,
        }
        state["updated_at"] = timezone.now().isoformat()
        self._write(state)

    def complete_window(self, begin_date: date, end_date: date) -> None:
        state = self.load()
        completed = set(state.get("completed_windows", []))
        completed.add(_window_key(begin_date, end_date))
        state["completed_windows"] = sorted(completed)
        state["current_window"] = None
        state["updated_at"] = timezone.now().isoformat()
        self._write(state)

    def _write(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)


class BookeoHistoryImporter:
    def __init__(
        self,
        *,
        client: BookeoApiClient,
        checkpoint_store: JsonCheckpointStore,
        dry_run: bool = False,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
    ):
        self.client = client
        self.checkpoint_store = checkpoint_store
        self.dry_run = dry_run
        self.items_per_page = min(items_per_page, DEFAULT_ITEMS_PER_PAGE)

    def run(self, *, date_from: date, date_to: date) -> BookeoImportStats:
        stats = BookeoImportStats()
        for begin_date, end_date in monthly_windows(date_from, date_to):
            if not self.dry_run and self.checkpoint_store.window_completed(
                begin_date, end_date
            ):
                continue
            self._process_window(begin_date, end_date, stats)
        return stats

    def _process_window(
        self,
        begin_date: date,
        end_date: date,
        stats: BookeoImportStats,
    ) -> None:
        stats.windows_processed += 1
        page_number, token = self.checkpoint_store.current_page(begin_date, end_date)
        while True:
            payload = self.client.list_bookings(
                begin_date=begin_date,
                end_date=end_date,
                items_per_page=self.items_per_page,
                page_navigation_token=token,
                page_number=page_number,
            )
            bookings = _payload_list(payload)
            for raw_booking in bookings:
                raw_booking = self._full_booking_payload(raw_booking)
                stats.fetched += 1
                outcome = import_bookeo_booking(raw_booking, dry_run=self.dry_run)
                stats.add_result(outcome.result)
                if outcome.unmapped:
                    stats.unmapped_to_review += 1

            info = payload.get("info") or {}
            total_pages = int(info.get("totalPages") or 1)
            current_page = int(info.get("currentPage") or page_number)
            next_token = info.get("pageNavigationToken") or token
            if current_page >= total_pages or not next_token:
                if not self.dry_run:
                    self.checkpoint_store.complete_window(begin_date, end_date)
                return

            page_number = current_page + 1
            token = next_token
            if not self.dry_run:
                self.checkpoint_store.save_page(
                    begin_date=begin_date,
                    end_date=end_date,
                    next_page=page_number,
                    page_navigation_token=token,
                )

    def _full_booking_payload(self, raw_booking: dict[str, Any]) -> dict[str, Any]:
        if not _is_thin_booking_payload(raw_booking):
            return raw_booking
        booking_number = _booking_number(raw_booking)
        if not booking_number:
            return raw_booking
        detail = self.client.get_booking(booking_number)
        return detail or raw_booking


def import_bookeo_booking(
    raw_booking: dict[str, Any],
    *,
    dry_run: bool = False,
) -> ImportOutcome:
    normalized = normalize_bookeo_booking(raw_booking)
    if not normalized.identity.reference:
        return ImportOutcome(result="skipped")

    provider = _get_or_create_provider(normalized.identity.provider_code)
    booking = Booking.objects.filter(
        provider=provider,
        provider_booking_reference=normalized.identity.reference,
    ).first()
    if dry_run:
        result = "updated" if booking else "created"
        return ImportOutcome(
            result=result, booking=booking, unmapped=not normalized.alias
        )

    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update()
            .filter(
                provider=provider,
                provider_booking_reference=normalized.identity.reference,
            )
            .first()
        )
        if booking is None:
            booking = _create_booking(provider=provider, normalized=normalized)
            _create_import_event(booking=booking, normalized=normalized, created=True)
            if not normalized.alias:
                _create_unmapped_review(booking, normalized)
                return ImportOutcome(result="created", booking=booking, unmapped=True)
            return ImportOutcome(result="created", booking=booking)

        changed = _update_booking(booking=booking, normalized=normalized)
        if changed:
            _create_import_event(booking=booking, normalized=normalized, created=False)
        if not normalized.alias:
            _create_unmapped_review(booking, normalized)
            return ImportOutcome(
                result="updated" if changed else "skipped",
                booking=booking,
                unmapped=True,
            )
        return ImportOutcome(
            result="updated" if changed else "skipped", booking=booking
        )


def normalize_bookeo_booking(raw_booking: dict[str, Any]) -> BookeoNormalizedBooking:
    bookeo_number = _booking_number(raw_booking)
    product_name = _product_name(raw_booking)
    product_code = _product_code(raw_booking)
    notes = _notes_text(raw_booking)
    underlying_provider, underlying_reference = _underlying_ota_identity(notes)
    provider_code = underlying_provider or "bookeo"
    reference = underlying_reference or bookeo_number
    identity = BookingIdentity(
        provider_code=provider_code,
        reference=reference,
        bookeo_booking_number=bookeo_number,
        underlying_provider_code=underlying_provider,
        underlying_reference=underlying_reference,
    )
    start_dt = _parse_bookeo_datetime(_first_value(raw_booking, "startTime"))
    end_dt = _parse_bookeo_datetime(_first_value(raw_booking, "endTime"))
    customer = _customer(raw_booking)
    participants = _participants(raw_booking)
    traveler_count = _traveler_count(raw_booking, participants)
    alias = _match_bookeo_alias(product_name=product_name, product_code=product_code)
    slot = _slot_for_alias_and_time(alias, start_dt.time() if start_dt else None)
    provider_slot_type = slot.slot_type if slot else _slot_type_from_times(start_dt)
    provider_values = {
        "provider_order_reference": (
            f"Bookeo {bookeo_number}"
            if underlying_reference and bookeo_number
            else None
        ),
        "status": _booking_status(raw_booking),
        "raw_product_name": product_name,
        "raw_option_name": _option_name(raw_booking),
        "provider_product_code": product_code,
        "provider_option_code": _option_code(raw_booking),
        "provider_travel_date": start_dt.date() if start_dt else None,
        "provider_start_time": (
            start_dt.time().replace(second=0, microsecond=0) if start_dt else None
        ),
        "provider_end_time": (
            end_dt.time().replace(second=0, microsecond=0) if end_dt else None
        ),
        "provider_slot_type": provider_slot_type,
        "provider_traveler_count": traveler_count,
        "lead_traveler_name": _customer_name(customer),
        "lead_traveler_email": _first_non_empty(
            customer.get("email"),
            raw_booking.get("customerEmail"),
        ),
        "lead_traveler_phone": _first_non_empty(
            customer.get("phone"),
            customer.get("mobilePhone"),
            raw_booking.get("customerPhone"),
        ),
        "traveler_names": _traveler_names(participants),
        "ticket_breakdown": _ticket_breakdown(participants),
        "language": _first_non_empty(
            customer.get("language"), raw_booking.get("language")
        ),
        "pickup_location": _first_value(raw_booking, "pickupLocation"),
        "meeting_point": _first_value(raw_booking, "meetingPoint"),
        "special_requirements": notes or None,
        "customer_message": _first_value(raw_booking, "customerMessage"),
        "price": _price(raw_booking),
        "payment_status": _first_value(raw_booking, "paymentStatus"),
    }
    active_values = {
        "active_travel_date": provider_values["provider_travel_date"],
        "active_start_time": provider_values["provider_start_time"],
        "active_end_time": provider_values["provider_end_time"],
        "active_slot_type": provider_values["provider_slot_type"],
        "active_traveler_count": provider_values["provider_traveler_count"],
    }
    return BookeoNormalizedBooking(
        identity=identity,
        raw_product_name=product_name,
        provider_product_code=product_code,
        provider_values=provider_values,
        active_values=active_values,
        raw_payload=raw_booking,
        alias=alias,
        schedule_slot=slot,
    )


def monthly_windows(date_from: date, date_to: date):
    current = date_from
    while current <= date_to:
        end_date = min(current + timedelta(days=30), date_to)
        yield current, end_date
        current = end_date + timedelta(days=1)


def default_to_date() -> date:
    return timezone.localdate() + timedelta(days=DEFAULT_FORWARD_DAYS)


def _create_booking(*, provider: Provider, normalized: BookeoNormalizedBooking):
    values = _booking_create_values(normalized)
    return Booking.objects.create(
        provider=provider,
        provider_booking_reference=normalized.identity.reference,
        activity=normalized.alias.linked_activity if normalized.alias else None,
        schedule_slot=normalized.schedule_slot,
        **values,
    )


def _update_booking(*, booking: Booking, normalized: BookeoNormalizedBooking) -> bool:
    changes = {}
    values = _booking_create_values(normalized)
    values["activity"] = normalized.alias.linked_activity if normalized.alias else None
    values["schedule_slot"] = normalized.schedule_slot
    for field_name, value in values.items():
        if is_manually_overridden(booking, field_name):
            continue
        if getattr(booking, field_name) == value:
            continue
        setattr(booking, field_name, value)
        changes[field_name] = _json_safe_value(value)
    if not changes:
        return False
    booking.save(update_fields=[*changes.keys(), "updated_at"])
    return True


def _booking_create_values(normalized: BookeoNormalizedBooking) -> dict[str, Any]:
    values = dict(normalized.provider_values)
    values.update(normalized.active_values)
    return values


def _create_import_event(
    *,
    booking: Booking,
    normalized: BookeoNormalizedBooking,
    created: bool,
) -> None:
    BookingEvent.objects.create(
        booking=booking,
        event_type=BookingEvent.EventType.BOOKEO_HISTORY_IMPORT,
        source=BookingEvent.Source.SYSTEM,
        old_values={},
        new_values={
            "created": created,
            "bookeo_booking_number": normalized.identity.bookeo_booking_number,
            "underlying_provider": normalized.identity.underlying_provider_code,
            "underlying_reference": normalized.identity.underlying_reference,
            "raw_bookeo_payload": normalized.raw_payload,
        },
    )


def _create_unmapped_review(
    booking: Booking,
    normalized: BookeoNormalizedBooking,
) -> None:
    ReviewQueueItem.objects.update_or_create(
        raw_email=None,
        booking=booking,
        issue_type=ReviewQueueItem.IssueType.PROVIDER_ALIAS_MISSING,
        status=ReviewQueueItem.Status.OPEN,
        defaults={
            "title": "Bookeo product is not mapped",
            "details": (
                "No approved Bookeo provider alias maps this product to a "
                "Tour/Activity. Raw product: "
                f"{normalized.raw_product_name or 'Missing'}"
            ),
        },
    )


def _match_bookeo_alias(
    *,
    product_name: str,
    product_code: str | None,
) -> ProviderAlias | None:
    provider = _get_or_create_provider("bookeo")
    aliases = ProviderAlias.objects.filter(provider=provider, approved=True)
    if product_code:
        alias = aliases.filter(provider_product_code=product_code).first()
        if alias:
            return alias
    target = _normalize_text(product_name)
    for alias in aliases:
        if _normalize_text(alias.raw_product_name) == target:
            return alias
    return None


def _slot_for_alias_and_time(
    alias: ProviderAlias | None,
    start_time,
) -> ActivityScheduleSlot | None:
    if not alias:
        return None
    if not start_time:
        return alias.linked_slot
    return (
        ActivityScheduleSlot.objects.filter(
            schedule__activity=alias.linked_activity,
            schedule__schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
            start_time=start_time.replace(second=0, microsecond=0),
            active=True,
        )
        .order_by("id")
        .first()
    )


def _get_or_create_provider(provider_code: str) -> Provider:
    provider, _created = Provider.objects.get_or_create(
        code=provider_code,
        defaults={
            "name": provider_display_name(provider_code),
            "parser_key": provider_code,
            "active": True,
        },
    )
    return provider


def _payload_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        return data
    bookings = payload.get("bookings")
    if isinstance(bookings, list):
        return bookings
    if isinstance(payload, list):
        return payload
    return []


def _is_thin_booking_payload(raw_booking: dict[str, Any]) -> bool:
    return not raw_booking.get("participants") or not isinstance(
        raw_booking.get("customer"), dict
    )


def _booking_number(raw_booking: dict[str, Any]) -> str:
    return str(
        _first_non_empty(
            raw_booking.get("bookingNumber"),
            raw_booking.get("bookingNo"),
            raw_booking.get("number"),
            raw_booking.get("id"),
        )
        or ""
    )


def _product_name(raw_booking: dict[str, Any]) -> str:
    product = raw_booking.get("product")
    if isinstance(product, dict):
        return _first_non_empty(
            product.get("name"),
            product.get("title"),
            product.get("productName"),
        )
    return _first_non_empty(
        raw_booking.get("productName"),
        raw_booking.get("productTitle"),
        raw_booking.get("tourName"),
        product if isinstance(product, str) else "",
    )


def _product_code(raw_booking: dict[str, Any]) -> str | None:
    product = raw_booking.get("product")
    value = None
    if isinstance(product, dict):
        value = _first_non_empty(product.get("id"), product.get("productId"))
    value = value or _first_non_empty(
        raw_booking.get("productId"),
        raw_booking.get("productCode"),
    )
    return str(value) if value else None


def _option_name(raw_booking: dict[str, Any]) -> str | None:
    option = raw_booking.get("option")
    if isinstance(option, dict):
        return _first_non_empty(option.get("name"), option.get("title")) or None
    return _first_non_empty(raw_booking.get("optionName"), option) or None


def _option_code(raw_booking: dict[str, Any]) -> str | None:
    option = raw_booking.get("option")
    value = None
    if isinstance(option, dict):
        value = _first_non_empty(option.get("id"), option.get("optionId"))
    value = value or _first_non_empty(
        raw_booking.get("optionId"), raw_booking.get("optionCode")
    )
    return str(value) if value else None


def _first_value(raw_booking: dict[str, Any], label: str) -> str | None:
    aliases = {
        "startTime": ["startTime", "startDateTime", "eventStartTime", "beginDate"],
        "endTime": ["endTime", "endDateTime", "eventEndTime"],
        "pickupLocation": ["pickupLocation", "pickup", "pickupPlace"],
        "meetingPoint": ["meetingPoint", "meetingLocation"],
        "customerMessage": ["customerMessage", "message"],
        "paymentStatus": ["paymentStatus", "paymentState"],
    }
    for key in aliases.get(label, [label]):
        value = raw_booking.get(key)
        if value:
            return str(value)
    event = raw_booking.get("event")
    if isinstance(event, dict):
        for key in aliases.get(label, [label]):
            value = event.get(key)
            if value:
                return str(value)
    return None


def _parse_bookeo_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M")
        except ValueError:
            return None


def _customer(raw_booking: dict[str, Any]) -> dict[str, Any]:
    customer = raw_booking.get("customer")
    if isinstance(customer, dict):
        return customer
    return {
        "name": raw_booking.get("customerName"),
        "email": raw_booking.get("customerEmail"),
        "phone": raw_booking.get("customerPhone"),
        "language": raw_booking.get("language"),
    }


def _participants(raw_booking: dict[str, Any]) -> list[dict[str, Any]]:
    participants = raw_booking.get("participants") or raw_booking.get("people")
    return participants if isinstance(participants, list) else []


def _traveler_count(raw_booking: dict[str, Any], participants: list[dict[str, Any]]):
    explicit = _first_non_empty(
        raw_booking.get("participantsNumber"),
        raw_booking.get("numParticipants"),
        raw_booking.get("peopleNumber"),
        raw_booking.get("totalParticipants"),
    )
    if explicit not in (None, ""):
        return int(explicit)
    count = 0
    for participant in participants:
        count += int(
            _first_non_empty(
                participant.get("number"),
                participant.get("quantity"),
                participant.get("count"),
                1,
            )
        )
    return count or None


def _traveler_names(participants: list[dict[str, Any]]) -> list[str]:
    names = []
    for participant in participants:
        name = _first_non_empty(
            participant.get("name"),
            _join_name(participant.get("firstName"), participant.get("lastName")),
        )
        if name:
            names.append(name)
    return names


def _ticket_breakdown(participants: list[dict[str, Any]]) -> dict[str, int]:
    breakdown = {}
    for participant in participants:
        label = _first_non_empty(
            participant.get("category"),
            participant.get("peopleCategoryName"),
            participant.get("type"),
            "person",
        )
        quantity = int(
            _first_non_empty(
                participant.get("number"),
                participant.get("quantity"),
                participant.get("count"),
                1,
            )
        )
        key = _normalize_text(label).replace(" ", "_")
        breakdown[key] = breakdown.get(key, 0) + quantity
    return breakdown


def _customer_name(customer: dict[str, Any]) -> str | None:
    return (
        _first_non_empty(
            customer.get("name"),
            _join_name(customer.get("firstName"), customer.get("lastName")),
        )
        or None
    )


def _booking_status(raw_booking: dict[str, Any]) -> str:
    state = _normalize_text(
        _first_non_empty(
            raw_booking.get("status"),
            raw_booking.get("state"),
            raw_booking.get("bookingStatus"),
        )
    )
    if "cancel" in state:
        return Booking.Status.CANCELLED
    if "reject" in state:
        return Booking.Status.REJECTED
    if "confirm" in state or "paid" in state:
        return Booking.Status.CONFIRMED
    if "modif" in state or "chang" in state:
        return Booking.Status.MODIFIED
    return Booking.Status.PENDING_PROVIDER_ACCEPTANCE


def _slot_type_from_times(start_dt: datetime | None) -> str:
    return ActivityScheduleSlot.SlotType.FIXED_TIME if start_dt else ""


def _notes_text(raw_booking: dict[str, Any]) -> str:
    values = []
    for key in ["notes", "internalNotes", "customerNotes", "comments"]:
        if raw_booking.get(key):
            values.append(str(raw_booking[key]))
    custom_fields = raw_booking.get("customFields")
    if isinstance(custom_fields, list):
        for field in custom_fields:
            if isinstance(field, dict):
                values.append(str(field.get("value") or ""))
    return "\n".join(value for value in values if value)


def _underlying_ota_identity(notes: str) -> tuple[str, str]:
    provider = _provider_from_text(notes)
    reference = ""
    patterns = [
        r"Booking reference\s*[:#-]\s*([A-Z0-9-]+)",
        r"Booking ref\s*[:#-]\s*([A-Z0-9-]+)",
        r"Reference number\s*[:#-]\s*([A-Z0-9-]+)",
        r"\b(BR-[A-Z0-9-]+)\b",
        r"\b(GYG[A-Z0-9-]+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, notes, re.IGNORECASE)
        if match:
            reference = match.group(1)
            break
    if reference.startswith("BR-"):
        provider = provider or "viator"
    if reference.startswith("GYG"):
        provider = provider or "getyourguide"
    return provider, reference


def _provider_from_text(value: str) -> str:
    lowered = value.lower()
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
    for provider, pattern in patterns:
        if re.search(pattern, lowered, re.IGNORECASE):
            return provider
    return ""


def _price(raw_booking: dict[str, Any]) -> dict[str, Any]:
    price = raw_booking.get("price") or raw_booking.get("totalPrice")
    if isinstance(price, dict):
        return price
    if price:
        return {"amount": str(price)}
    return {}


def _first_non_empty(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return ""


def _join_name(first_name, last_name) -> str:
    return " ".join(part for part in [first_name, last_name] if part)


def _normalize_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _json_safe_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "pk"):
        return str(value)
    return value


def _window_key(begin_date: date, end_date: date) -> str:
    return f"{begin_date.isoformat()}:{end_date.isoformat()}"
