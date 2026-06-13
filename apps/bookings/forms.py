from django import forms
from django.core.exceptions import ValidationError

from .models import Booking, Product, ProductAlias, ProductVariant


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
            "canonical_product",
            "canonical_variant",
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
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ProductAliasForm(forms.ModelForm):
    class Meta:
        model = ProductAlias
        fields = [
            "provider",
            "raw_product_name",
            "raw_option_name",
            "provider_product_code",
            "provider_option_code",
            "canonical_product",
            "canonical_variant",
            "confidence",
            "approved",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["canonical_product"].queryset = Product.objects.filter(
            active=True
        ).order_by("canonical_name")
        self.fields["canonical_variant"].queryset = ProductVariant.objects.filter(
            active=True
        ).select_related("product")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["approved"].widget.attrs["class"] = "form-check-input"


class ProductSettingsForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["canonical_name", "nickname", "category", "active", "notes"]
        labels = {
            "canonical_name": "Name",
            "nickname": "Nickname / display label",
            "notes": "Display settings",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["active"].widget.attrs["class"] = "form-check-input"


class ProductScheduleForm(forms.Form):
    schedule_name = forms.CharField(
        required=False,
        label="Schedule name",
        max_length=120,
    )
    date_from = forms.DateField(
        required=False,
        label="Start",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        label="End",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    duration_days = forms.IntegerField(min_value=0, max_value=30, initial=0)
    duration_hours = forms.IntegerField(min_value=0, max_value=24, initial=2)
    duration_minutes = forms.ChoiceField(
        choices=[(str(value), f"{value:02d}") for value in range(0, 60, 5)],
        initial="00",
    )
    default_capacity = forms.IntegerField(min_value=0, initial=50)
    monday = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    tuesday = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    wednesday = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 4})
    )
    thursday = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    friday = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    saturday = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    sunday = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    day_fields = [
        ("monday", 0),
        ("tuesday", 1),
        ("wednesday", 2),
        ("thursday", 3),
        ("friday", 4),
        ("saturday", 5),
        ("sunday", 6),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        day_field_names = {field_name for field_name, _day_index in self.day_fields}
        for field_name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-control")
            if field_name in day_field_names:
                field.widget.attrs["class"] += " tm-weekday-lines"
        self.fields["duration_minutes"].widget.attrs["class"] = "form-select"

    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if date_from and date_to and date_to < date_from:
            raise ValidationError("Schedule end date must be after the start date.")
        parsed_rows = {}
        for field_name, day_index in self.day_fields:
            parsed_rows[day_index] = _parse_schedule_lines(
                cleaned.get(field_name, ""),
                self.add_error,
                field_name,
            )
        cleaned["parsed_rows"] = parsed_rows
        return cleaned

    @property
    def duration_minutes_total(self):
        return (
            (self.cleaned_data["duration_days"] * 24 * 60)
            + (self.cleaned_data["duration_hours"] * 60)
            + int(self.cleaned_data["duration_minutes"])
        )


def _parse_schedule_lines(value, add_error, field_name):
    rows = []
    seen = set()
    for line_number, raw_line in enumerate(value.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if "," in line:
            time_text, capacity_text = [part.strip() for part in line.split(",", 1)]
        else:
            parts = line.split()
            if len(parts) != 2:
                add_error(field_name, f"Line {line_number}: use HH:MM,capacity.")
                continue
            time_text, capacity_text = parts
        try:
            start_time = forms.TimeField(input_formats=["%H:%M"]).clean(time_text)
        except ValidationError:
            add_error(field_name, f"Line {line_number}: invalid time '{time_text}'.")
            continue
        try:
            capacity = int(capacity_text)
        except ValueError:
            add_error(
                field_name,
                f"Line {line_number}: invalid capacity '{capacity_text}'.",
            )
            continue
        if capacity < 0:
            add_error(field_name, f"Line {line_number}: capacity cannot be negative.")
            continue
        if start_time in seen:
            add_error(field_name, f"Line {line_number}: duplicate time {time_text}.")
            continue
        seen.add(start_time)
        rows.append({"time": start_time, "capacity": capacity})
    return rows
