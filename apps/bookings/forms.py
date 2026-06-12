from django import forms

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
