from datetime import datetime, timedelta

from django import forms
from django.core.exceptions import ValidationError

from .models import (
    ActivityPeopleRule,
    ActivitySchedule,
    ActivityScheduleSlot,
    Booking,
    ProviderAlias,
    TourActivity,
)

DISPLAY_SETTING_FIELDS = [
    ("visible_internally", "Visible internally"),
    ("show_in_calendar", "Show in calendar"),
    ("show_in_reports", "Show in reports"),
]


class BookingEditForm(forms.ModelForm):
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Required audit note for this manual edit.",
    )

    class Meta:
        model = Booking
        fields = [
            "status",
            "activity",
            "schedule_slot",
            "active_travel_date",
            "active_start_time",
            "active_end_time",
            "active_slot_type",
            "active_traveler_count",
            "lead_traveler_name",
            "lead_traveler_email",
            "lead_traveler_phone",
            "traveler_names",
            "ticket_breakdown",
            "language",
            "pickup_location",
            "meeting_point",
            "special_requirements",
            "customer_message",
            "price",
            "payment_status",
            "reason",
        ]
        widgets = {
            "active_travel_date": forms.DateInput(attrs={"type": "date"}),
            "active_start_time": forms.TimeInput(attrs={"type": "time"}),
            "active_end_time": forms.TimeInput(attrs={"type": "time"}),
            "pickup_location": forms.Textarea(attrs={"rows": 2}),
            "meeting_point": forms.Textarea(attrs={"rows": 2}),
            "special_requirements": forms.Textarea(attrs={"rows": 2}),
            "customer_message": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["activity"].queryset = TourActivity.objects.order_by("name")
        self.fields["schedule_slot"].queryset = (
            ActivityScheduleSlot.objects.select_related(
                "schedule", "schedule__activity"
            )
            .filter(active=True)
            .order_by("schedule__activity__name", "start_time")
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class TourActivityForm(forms.ModelForm):
    visible_internally = forms.BooleanField(required=False, initial=True)
    show_in_calendar = forms.BooleanField(required=False, initial=True)
    show_in_reports = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = TourActivity
        fields = [
            "name",
            "internal_display_name",
            "active",
            "category",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        settings = self.instance.display_settings if self.instance.pk else {}
        for key, _label in DISPLAY_SETTING_FIELDS:
            self.fields[key].initial = settings.get(key, True)
            self.fields[key].widget.attrs["class"] = "form-check-input"
        for name, field in self.fields.items():
            if name not in {key for key, _label in DISPLAY_SETTING_FIELDS}:
                field.widget.attrs.setdefault("class", "form-control")
        self.fields["active"].widget.attrs["class"] = "form-check-input"

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.display_settings = {
            key: bool(self.cleaned_data.get(key))
            for key, _label in DISPLAY_SETTING_FIELDS
        }
        if commit:
            instance.save()
        return instance


class ActivityScheduleSectionForm(forms.ModelForm):
    slot_lines = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="One line per slot: HH:MM,capacity,duration_minutes,slot_type",
    )

    class Meta:
        model = ActivitySchedule
        fields = [
            "name",
            "active",
            "date_from",
            "date_to",
            "days_of_week",
            "timezone",
            "priority",
        ]
        widgets = {
            "date_from": forms.DateInput(attrs={"type": "date"}),
            "date_to": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, schedule_kind, **kwargs):
        self.schedule_kind = schedule_kind
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["active"].widget.attrs["class"] = "form-check-input"
        self.fields["days_of_week"].help_text = (
            "Use 0-6 where Monday is 0. Leave empty for every day."
        )
        if self.instance.pk:
            self.fields["slot_lines"].initial = "\n".join(
                _slot_to_line(slot)
                for slot in self.instance.slots.order_by("start_time")
            )

    def clean_days_of_week(self):
        value = self.cleaned_data.get("days_of_week")
        if value is None or value == "":
            return []
        if not isinstance(value, list):
            raise ValidationError("Days of week must be a JSON list such as [0,1,2].")
        cleaned = []
        for day in value:
            try:
                day_int = int(day)
            except (TypeError, ValueError) as exc:
                raise ValidationError("Days of week values must be 0-6.") from exc
            if day_int not in range(7):
                raise ValidationError("Days of week values must be 0-6.")
            if day_int not in cleaned:
                cleaned.append(day_int)
        return cleaned

    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if date_from and date_to and date_to < date_from:
            raise ValidationError("Schedule end date must be after the start date.")
        cleaned["parsed_slots"] = _parse_slot_lines(
            cleaned.get("slot_lines", ""),
            self.add_error,
        )
        return cleaned

    def save(self, *, activity):
        schedule = super().save(commit=False)
        schedule.activity = activity
        schedule.schedule_kind = self.schedule_kind
        schedule.save()
        schedule.slots.all().delete()
        for slot in self.cleaned_data["parsed_slots"]:
            ActivityScheduleSlot.objects.create(schedule=schedule, **slot)
        return schedule


class ActivityPeopleRuleForm(forms.ModelForm):
    class Meta:
        model = ActivityPeopleRule
        fields = [
            "min_people_per_booking",
            "max_people_per_booking",
            "default_capacity",
            "capacity_note",
        ]
        widgets = {
            "capacity_note": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        min_people = cleaned.get("min_people_per_booking")
        max_people = cleaned.get("max_people_per_booking")
        if min_people and max_people and max_people < min_people:
            raise ValidationError(
                "Maximum people must be greater than or equal to minimum people."
            )
        return cleaned


class ProviderAliasForm(forms.ModelForm):
    class Meta:
        model = ProviderAlias
        fields = [
            "provider",
            "raw_product_name",
            "raw_option_name",
            "provider_product_code",
            "provider_option_code",
            "linked_activity",
            "linked_schedule",
            "linked_slot",
            "approved",
            "needs_manual_confirmation",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        activity = kwargs.pop("activity", None)
        super().__init__(*args, **kwargs)
        self.fields["linked_activity"].queryset = TourActivity.objects.order_by("name")
        self.fields["linked_schedule"].queryset = (
            ActivitySchedule.objects.select_related("activity").order_by(
                "activity__name", "schedule_kind", "priority"
            )
        )
        self.fields["linked_slot"].queryset = (
            ActivityScheduleSlot.objects.select_related(
                "schedule", "schedule__activity"
            ).order_by("schedule__activity__name", "start_time")
        )
        if activity:
            self.fields["linked_activity"].initial = activity
            self.fields["linked_schedule"].queryset = self.fields[
                "linked_schedule"
            ].queryset.filter(activity=activity)
            self.fields["linked_slot"].queryset = self.fields[
                "linked_slot"
            ].queryset.filter(schedule__activity=activity)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["approved"].widget.attrs["class"] = "form-check-input"
        self.fields["needs_manual_confirmation"].widget.attrs[
            "class"
        ] = "form-check-input"


def _slot_to_line(slot):
    return ",".join(
        [
            slot.start_time.strftime("%H:%M"),
            str(slot.capacity),
            str(slot.duration_minutes),
            slot.slot_type,
        ]
    )


def _parse_slot_lines(value, add_error):
    rows = []
    seen = set()
    valid_slot_types = {choice[0] for choice in ActivityScheduleSlot.SlotType.choices}
    for line_number, raw_line in enumerate(value.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) not in {2, 3, 4}:
            add_error(
                "slot_lines",
                f"Line {line_number}: use HH:MM,capacity,duration_minutes,slot_type.",
            )
            continue
        time_text = parts[0]
        capacity_text = parts[1]
        duration_text = parts[2] if len(parts) >= 3 and parts[2] else "120"
        slot_type = (
            parts[3]
            if len(parts) == 4 and parts[3]
            else ActivityScheduleSlot.SlotType.FIXED_TIME
        )
        try:
            start_time = forms.TimeField(input_formats=["%H:%M"]).clean(time_text)
        except ValidationError:
            add_error("slot_lines", f"Line {line_number}: invalid time '{time_text}'.")
            continue
        try:
            capacity = int(capacity_text)
            duration = int(duration_text)
        except ValueError:
            add_error(
                "slot_lines",
                f"Line {line_number}: capacity and duration must be numbers.",
            )
            continue
        if capacity < 0:
            add_error("slot_lines", f"Line {line_number}: capacity cannot be negative.")
            continue
        if duration < 1:
            add_error("slot_lines", f"Line {line_number}: duration must be positive.")
            continue
        if slot_type not in valid_slot_types:
            add_error("slot_lines", f"Line {line_number}: invalid slot type.")
            continue
        if start_time in seen:
            add_error("slot_lines", f"Line {line_number}: duplicate time {time_text}.")
            continue
        seen.add(start_time)
        rows.append(
            {
                "start_time": start_time,
                "end_time": _end_time(start_time, duration),
                "duration_minutes": duration,
                "slot_type": slot_type,
                "capacity": capacity,
                "active": True,
            }
        )
    return rows


def _end_time(start_time, duration_minutes):
    end = datetime.combine(datetime(2000, 1, 1).date(), start_time) + timedelta(
        minutes=duration_minutes
    )
    if end.date() != datetime(2000, 1, 1).date():
        return None
    return end.time()
