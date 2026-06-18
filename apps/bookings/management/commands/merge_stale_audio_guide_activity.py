from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.bookings.models import (
    ActivitySchedule,
    ActivityScheduleSlot,
    Booking,
    ProviderAlias,
    TourActivity,
)

STALE_ACTIVITY_NAME = "Istanbul: Bosphorus Sightseeing Cruise Tour with Audio Guide"
CANONICAL_ACTIVITY_NAME = "GYG 2 Hours Bosphorus Tour SL-(2-3)"


class Command(BaseCommand):
    help = "Merge the stale audio-guide activity into the canonical Bookeo activity."

    @transaction.atomic
    def handle(self, *args, **options):
        stale = TourActivity.objects.filter(name=STALE_ACTIVITY_NAME).first()
        if not stale:
            self.stdout.write("Stale audio-guide activity not found; no changes made.")
            return

        canonical = TourActivity.objects.filter(name=CANONICAL_ACTIVITY_NAME).first()
        if not canonical:
            raise CommandError(
                f"Canonical activity {CANONICAL_ACTIVITY_NAME!r} was not found."
            )

        moved_count = self._move_bookings(stale=stale, canonical=canonical)
        alias_count = self._delete_stale_aliases(stale=stale)
        stale.delete()

        self.stdout.write(
            self.style.SUCCESS(
                "Merged stale audio-guide activity: "
                f"bookings moved={moved_count}; aliases deleted={alias_count}."
            )
        )

    def _move_bookings(self, *, stale, canonical) -> int:
        moved_count = 0
        bookings = Booking.objects.filter(activity=stale).order_by("id")
        for booking in bookings:
            slot = _canonical_slot(canonical, booking.active_start_time)
            booking.activity = canonical
            booking.schedule_slot = slot
            if slot:
                if not booking.active_start_time:
                    booking.active_start_time = slot.start_time
                if not booking.active_end_time:
                    booking.active_end_time = slot.end_time
                if not booking.active_slot_type:
                    booking.active_slot_type = slot.slot_type
            booking.save(
                update_fields=[
                    "activity",
                    "schedule_slot",
                    "active_start_time",
                    "active_end_time",
                    "active_slot_type",
                    "updated_at",
                ]
            )
            moved_count += 1
            self.stdout.write(f"Reassigned booking id={booking.id}")
        return moved_count

    def _delete_stale_aliases(self, *, stale) -> int:
        stale_aliases = (
            ProviderAlias.objects.filter(linked_activity=stale)
            | ProviderAlias.objects.filter(linked_schedule__activity=stale)
            | ProviderAlias.objects.filter(linked_slot__schedule__activity=stale)
        )
        count = stale_aliases.distinct().count()
        stale_aliases.distinct().delete()
        return count


def _canonical_slot(activity, start_time):
    slots = ActivityScheduleSlot.objects.filter(
        schedule__activity=activity,
        schedule__active=True,
        active=True,
    )
    if start_time:
        matched = (
            slots.filter(start_time=start_time)
            .order_by(
                "schedule__schedule_kind",
                "schedule__priority",
                "start_time",
                "id",
            )
            .first()
        )
        if matched:
            return matched
    return (
        slots.filter(schedule__schedule_kind=ActivitySchedule.ScheduleKind.CURRENT)
        .order_by("start_time", "id")
        .first()
        or slots.order_by("start_time", "id").first()
    )
