from datetime import date, time

from apps.bookings.models import (
    ActivityPeopleRule,
    ActivitySchedule,
    ActivityScheduleSlot,
    Booking,
    Provider,
    ProviderAlias,
    TourActivity,
)


def create_activity_setup(
    *,
    provider_code="viator",
    provider_name="Viator",
    activity_name="City Tour",
    category=TourActivity.Category.CRUISE,
    schedule_kind=ActivitySchedule.ScheduleKind.CURRENT,
    schedule_name="Current schedule",
    start_time=time(9, 0),
    duration_minutes=120,
    slot_type=ActivityScheduleSlot.SlotType.FIXED_TIME,
    capacity=10,
    service_date=date(2026, 6, 21),
    raw_product_name=None,
    raw_option_name="Morning",
    alias=True,
):
    provider = Provider.objects.create(
        name=provider_name,
        code=provider_code,
        parser_key=provider_code,
    )
    activity = TourActivity.objects.create(
        name=activity_name,
        internal_display_name=activity_name,
        category=category,
        active=True,
        display_settings={"show_home_agenda": True},
    )
    ActivityPeopleRule.objects.create(
        activity=activity,
        min_people_per_booking=1,
        max_people_per_booking=capacity,
        default_capacity=capacity,
    )
    schedule = ActivitySchedule.objects.create(
        activity=activity,
        schedule_kind=schedule_kind,
        name=schedule_name,
        active=True,
        priority=100,
    )
    slot = ActivityScheduleSlot.objects.create(
        schedule=schedule,
        start_time=start_time,
        end_time=_end_time(start_time, duration_minutes),
        duration_minutes=duration_minutes,
        slot_type=slot_type,
        capacity=capacity,
        active=True,
    )
    provider_alias = None
    if alias:
        provider_alias = ProviderAlias.objects.create(
            provider=provider,
            raw_product_name=raw_product_name or activity_name,
            raw_option_name=raw_option_name or "",
            provider_product_code="",
            provider_option_code="",
            linked_activity=activity,
            linked_schedule=schedule,
            linked_slot=slot,
            approved=True,
        )
    return {
        "provider": provider,
        "activity": activity,
        "schedule": schedule,
        "slot": slot,
        "alias": provider_alias,
        "date": service_date,
    }


def create_booking(
    setup,
    reference="BR-1",
    *,
    status=Booking.Status.CONFIRMED,
    pax=2,
    service_date=None,
    provider=None,
    lead_name=None,
):
    slot = setup["slot"]
    return Booking.objects.create(
        provider=provider or setup["provider"],
        provider_booking_reference=reference,
        status=status,
        activity=setup["activity"],
        schedule_slot=slot,
        raw_product_name=setup["activity"].name,
        raw_option_name="Morning",
        provider_travel_date=service_date or setup["date"],
        provider_start_time=slot.start_time,
        provider_end_time=slot.end_time,
        provider_slot_type=slot.slot_type,
        provider_traveler_count=pax,
        active_travel_date=service_date or setup["date"],
        active_start_time=slot.start_time,
        active_end_time=slot.end_time,
        active_slot_type=slot.slot_type,
        active_traveler_count=pax,
        lead_traveler_name=lead_name or f"Lead {reference}",
        lead_traveler_phone="+1 555 0100",
        lead_traveler_email=f"{reference.lower()}@example.test",
        pickup_location="Hotel",
        meeting_point="Pier",
        language="English",
        special_requirements="Window seat",
    )


def _end_time(start_time, duration_minutes):
    hour = start_time.hour + (start_time.minute + duration_minutes) // 60
    minute = (start_time.minute + duration_minutes) % 60
    if hour >= 24:
        return None
    return time(hour, minute)
