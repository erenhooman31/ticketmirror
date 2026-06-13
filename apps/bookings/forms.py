from datetime import datetime, timedelta

from django import forms
from django.core.exceptions import ValidationError

from .models import (
    ActivityPeopleRule,
    ActivitySchedule,
    ActivityScheduleException,
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


DAY_CHOICES = [
    ("0", "Mon"),
    ("1", "Tue"),
    ("2", "Wed"),
    ("3", "Thu"),
    ("4", "Fri"),
    ("5", "Sat"),
    ("6", "Sun"),
]

STATUS_CHOICES = [
    ("active", "Active"),
    ("inactive", "Inactive"),
]

SLOT_TYPE_FORM_CHOICES = [
    ("fixed-time", "Fixed time"),
    ("half-day", "Half day"),
    ("full-day", "Full day"),
    ("open-time", "Open time"),
    ("private-group", "Private group"),
]
SLOT_TYPE_TO_MODEL = {
    "fixed-time": ActivityScheduleSlot.SlotType.FIXED_TIME,
    "half-day": ActivityScheduleSlot.SlotType.HALF_DAY,
    "full-day": ActivityScheduleSlot.SlotType.FULL_DAY,
    "open-time": ActivityScheduleSlot.SlotType.OPEN_TIME,
    "private-group": ActivityScheduleSlot.SlotType.PRIVATE_GROUP,
}
MODEL_SLOT_TYPE_TO_FORM = {value: key for key, value in SLOT_TYPE_TO_MODEL.items()}

SPECIAL_DATE_TYPE_CHOICES = [
    ("blocked", "Blocked"),
    ("closed", "Closed"),
    ("capacity-override", "Capacity override"),
    ("extra-slot", "Extra slot"),
    ("removed-slot", "Removed slot"),
]
SPECIAL_DATE_TO_MODEL = {
    "blocked": ActivityScheduleException.ExceptionType.BLOCKED,
    "closed": ActivityScheduleException.ExceptionType.CLOSED,
    "capacity-override": ActivityScheduleException.ExceptionType.OVERRIDE_CAPACITY,
    "extra-slot": ActivityScheduleException.ExceptionType.EXTRA_SLOT,
    "removed-slot": ActivityScheduleException.ExceptionType.REMOVED_SLOT,
}
MODEL_SPECIAL_DATE_TO_FORM = {
    value: key for key, value in SPECIAL_DATE_TO_MODEL.items()
}


class OperatorScheduleSectionForm(forms.Form):
    schedule_name = forms.CharField(
        label="Schedule name",
        max_length=120,
        required=False,
    )
    schedule_status = forms.ChoiceField(
        label="Schedule status",
        choices=STATUS_CHOICES,
    )
    applies_from = forms.DateField(
        label="Applies from",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    applies_until = forms.DateField(
        label="Applies until",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    repeat_days = forms.MultipleChoiceField(
        label="Repeats on",
        choices=DAY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Leave all days unchecked to repeat every day.",
    )
    timezone = forms.CharField(label="Timezone", max_length=80)
    notes = forms.CharField(
        label="Notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, schedule_kind, activity=None, instance=None, **kwargs):
        self.schedule_kind = schedule_kind
        self.activity = activity
        self.instance = instance
        if instance and not args and "initial" not in kwargs:
            kwargs["initial"] = {
                "schedule_name": instance.name,
                "schedule_status": "active" if instance.active else "inactive",
                "applies_from": instance.date_from,
                "applies_until": instance.date_to,
                "repeat_days": [str(day) for day in instance.days_of_week or []],
                "timezone": instance.timezone,
                "notes": instance.notes,
            }
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["repeat_days"].widget.attrs["class"] = "tm-weekday-list"

    def clean(self):
        cleaned = super().clean()
        applies_from = cleaned.get("applies_from")
        applies_until = cleaned.get("applies_until")
        if applies_from and applies_until and applies_until < applies_from:
            self.add_error(
                "applies_until",
                "Applies until must be after Applies from.",
            )
        cleaned["repeat_days"] = [int(day) for day in cleaned.get("repeat_days", [])]
        self._validate_unresolved_overlap(cleaned)
        return cleaned

    def save(self, *, activity):
        schedule = self.instance or ActivitySchedule()
        schedule.activity = activity
        schedule.schedule_kind = self.schedule_kind
        schedule.name = self.cleaned_data["schedule_name"]
        schedule.active = self.cleaned_data["schedule_status"] == "active"
        schedule.date_from = self.cleaned_data["applies_from"]
        schedule.date_to = self.cleaned_data["applies_until"]
        schedule.days_of_week = self.cleaned_data["repeat_days"]
        schedule.timezone = self.cleaned_data["timezone"]
        schedule.notes = self.cleaned_data["notes"]
        schedule.recurrence_mode = ActivitySchedule.RecurrenceMode.WEEKLY
        if schedule.priority is None:
            schedule.priority = 100
        schedule.save()
        return schedule

    def _validate_unresolved_overlap(self, cleaned):
        if not self.activity or cleaned.get("schedule_status") != "active":
            return
        priority = self.instance.priority if self.instance else 100
        queryset = ActivitySchedule.objects.filter(
            activity=self.activity,
            active=True,
            schedule_kind=self.schedule_kind,
            priority=priority,
        )
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        applies_from = cleaned.get("applies_from")
        applies_until = cleaned.get("applies_until")
        for schedule in queryset:
            if _date_ranges_overlap(
                applies_from,
                applies_until,
                schedule.date_from,
                schedule.date_to,
            ):
                self.add_error(
                    "applies_from",
                    "Another active schedule of the same type overlaps these dates.",
                )
                break


class OperatorScheduleSlotForm(forms.Form):
    slot_days = forms.MultipleChoiceField(
        label="Day",
        choices=DAY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Leave all days unchecked to use every day.",
    )
    start_time = forms.TimeField(
        label="Start",
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    duration_minutes = forms.IntegerField(
        label="Duration",
        min_value=1,
        widget=forms.NumberInput(attrs={"min": "1"}),
    )
    slot_kind = forms.ChoiceField(label="Type", choices=SLOT_TYPE_FORM_CHOICES)
    capacity = forms.IntegerField(
        label="Capacity",
        min_value=0,
        widget=forms.NumberInput(attrs={"min": "0"}),
    )
    slot_status = forms.ChoiceField(label="Status", choices=STATUS_CHOICES)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance and not args and "initial" not in kwargs:
            kwargs["initial"] = {
                "slot_days": [str(day) for day in instance.days_of_week or []],
                "start_time": instance.start_time,
                "duration_minutes": instance.duration_minutes,
                "slot_kind": MODEL_SLOT_TYPE_TO_FORM.get(instance.slot_type),
                "capacity": instance.capacity,
                "slot_status": "active" if instance.active else "inactive",
            }
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["slot_days"].widget.attrs["class"] = "tm-weekday-list"

    def clean_slot_days(self):
        return [int(day) for day in self.cleaned_data.get("slot_days", [])]

    def save(self, *, schedule):
        slot = self.instance or ActivityScheduleSlot(schedule=schedule)
        slot.schedule = schedule
        slot.start_time = self.cleaned_data["start_time"]
        slot.duration_minutes = self.cleaned_data["duration_minutes"]
        slot.end_time = _end_time(slot.start_time, slot.duration_minutes)
        slot.slot_type = SLOT_TYPE_TO_MODEL[self.cleaned_data["slot_kind"]]
        slot.capacity = self.cleaned_data["capacity"]
        slot.days_of_week = self.cleaned_data["slot_days"]
        slot.active = self.cleaned_data["slot_status"] == "active"
        slot.save()
        return slot


class OperatorScheduleExceptionForm(forms.Form):
    special_date_kind = forms.ChoiceField(
        label="Type",
        choices=SPECIAL_DATE_TYPE_CHOICES,
    )
    date = forms.DateField(
        label="Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    start_time = forms.TimeField(
        label="Time",
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    end_time = forms.TimeField(
        label="End time",
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    capacity = forms.IntegerField(
        label="Capacity",
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"min": "0"}),
    )
    reason = forms.CharField(
        label="Reason",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    special_date_status = forms.ChoiceField(label="Status", choices=STATUS_CHOICES)

    def __init__(self, *args, schedule=None, instance=None, **kwargs):
        self.schedule = schedule
        self.instance = instance
        if instance and not args and "initial" not in kwargs:
            kwargs["initial"] = {
                "special_date_kind": MODEL_SPECIAL_DATE_TO_FORM.get(
                    instance.exception_type
                ),
                "date": instance.date,
                "start_time": instance.start_time,
                "end_time": instance.end_time,
                "capacity": instance.capacity,
                "reason": instance.reason,
                "special_date_status": "active" if instance.active else "inactive",
            }
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        special_date_type = SPECIAL_DATE_TO_MODEL.get(cleaned.get("special_date_kind"))
        date = cleaned.get("date")
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
        capacity = cleaned.get("capacity")

        if self.schedule and date:
            if self.schedule.date_from and date < self.schedule.date_from:
                self.add_error("date", "Date is before this schedule starts.")
            if self.schedule.date_to and date > self.schedule.date_to:
                self.add_error("date", "Date is after this schedule ends.")

        if start_time and end_time and end_time <= start_time:
            self.add_error("end_time", "End time must be after the start time.")

        capacity_required = {
            ActivityScheduleException.ExceptionType.EXTRA_SLOT,
            ActivityScheduleException.ExceptionType.OVERRIDE_CAPACITY,
        }
        if special_date_type in capacity_required and capacity is None:
            self.add_error("capacity", "Capacity is required for this type.")
        if (
            special_date_type
            in {
                ActivityScheduleException.ExceptionType.EXTRA_SLOT,
                ActivityScheduleException.ExceptionType.REMOVED_SLOT,
                ActivityScheduleException.ExceptionType.OVERRIDE_CAPACITY,
            }
            and not start_time
        ):
            self.add_error("start_time", "Time is required for this type.")
        return cleaned

    def save(self):
        exception = self.instance or ActivityScheduleException(schedule=self.schedule)
        exception.schedule = self.schedule
        exception.exception_type = SPECIAL_DATE_TO_MODEL[
            self.cleaned_data["special_date_kind"]
        ]
        exception.date = self.cleaned_data["date"]
        exception.start_time = self.cleaned_data["start_time"]
        exception.end_time = self.cleaned_data["end_time"]
        exception.capacity = self.cleaned_data["capacity"]
        exception.reason = self.cleaned_data["reason"]
        exception.active = self.cleaned_data["special_date_status"] == "active"
        exception.save()
        return exception


class OperatorAdditionalTimeForm(forms.Form):
    date = forms.DateField(label="Date", widget=forms.DateInput(attrs={"type": "date"}))
    start_time = forms.TimeField(
        label="Start",
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    capacity = forms.IntegerField(
        label="Seats",
        min_value=0,
        widget=forms.NumberInput(attrs={"min": "0"}),
    )
    status = forms.ChoiceField(label="Status", choices=STATUS_CHOICES)

    def __init__(self, *args, schedule=None, instance=None, **kwargs):
        self.schedule = schedule
        self.instance = instance
        if instance and not args and "initial" not in kwargs:
            kwargs["initial"] = {
                "date": instance.date,
                "start_time": instance.start_time,
                "capacity": instance.capacity,
                "status": "active" if instance.active else "inactive",
            }
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def save(self):
        exception = self.instance or ActivityScheduleException(schedule=self.schedule)
        exception.schedule = self.schedule
        exception.exception_type = ActivityScheduleException.ExceptionType.EXTRA_SLOT
        exception.date = self.cleaned_data["date"]
        exception.start_time = self.cleaned_data["start_time"]
        exception.end_time = None
        exception.capacity = self.cleaned_data["capacity"]
        exception.reason = ""
        exception.active = self.cleaned_data["status"] == "active"
        exception.save()
        return exception


class OperatorBlockedDateForm(forms.Form):
    date = forms.DateField(label="Date", widget=forms.DateInput(attrs={"type": "date"}))
    start_time = forms.TimeField(
        label="Time",
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    reason = forms.CharField(
        label="Reason",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    status = forms.ChoiceField(label="Status", choices=STATUS_CHOICES)

    def __init__(self, *args, schedule=None, instance=None, **kwargs):
        self.schedule = schedule
        self.instance = instance
        if instance and not args and "initial" not in kwargs:
            kwargs["initial"] = {
                "date": instance.date,
                "start_time": instance.start_time,
                "reason": instance.reason,
                "status": "active" if instance.active else "inactive",
            }
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def save(self):
        exception = self.instance or ActivityScheduleException(schedule=self.schedule)
        exception.schedule = self.schedule
        exception.exception_type = ActivityScheduleException.ExceptionType.BLOCKED
        exception.date = self.cleaned_data["date"]
        exception.start_time = self.cleaned_data["start_time"]
        exception.end_time = None
        exception.capacity = None
        exception.reason = self.cleaned_data["reason"]
        exception.active = self.cleaned_data["status"] == "active"
        exception.save()
        return exception


class ChangeSeatsForm(forms.Form):
    capacity = forms.IntegerField(
        label="Seats",
        min_value=0,
        widget=forms.NumberInput(attrs={"min": "0"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


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


def _end_time(start_time, duration_minutes):
    end = datetime.combine(datetime(2000, 1, 1).date(), start_time) + timedelta(
        minutes=duration_minutes
    )
    if end.date() != datetime(2000, 1, 1).date():
        return None
    return end.time()


def _date_ranges_overlap(left_from, left_to, right_from, right_to):
    low = datetime.min.date()
    high = datetime.max.date()
    left_start = left_from or low
    left_end = left_to or high
    right_start = right_from or low
    right_end = right_to or high
    return left_start <= right_end and right_start <= left_end
