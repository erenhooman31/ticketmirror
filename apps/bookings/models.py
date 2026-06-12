from django.conf import settings
from django.db import models
from django.db.models import Q


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Provider(TimeStampedModel):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=60, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ServiceProduct(TimeStampedModel):
    class DurationType(models.TextChoices):
        FULL_DAY = "full_day", "Full day"
        HALF_DAY = "half_day", "Half day"
        FIXED_SLOT = "fixed_slot", "Fixed time slot"

    name = models.CharField(max_length=180, unique=True)
    duration_type = models.CharField(max_length=20, choices=DurationType.choices)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(
        ServiceProduct,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    name = models.CharField(max_length=180)
    start_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    default_capacity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["product__name", "start_time", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "name", "start_time"],
                name="unique_product_variant_name_time",
            )
        ]

    def __str__(self) -> str:
        return f"{self.product} - {self.name}"


class ProductAlias(TimeStampedModel):
    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name="aliases"
    )
    product = models.ForeignKey(
        ServiceProduct,
        on_delete=models.PROTECT,
        related_name="provider_aliases",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="provider_aliases",
    )
    provider_product_name = models.CharField(max_length=240)
    provider_product_code = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["provider__name", "provider_product_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_product_name", "provider_product_code"],
                name="unique_provider_product_alias",
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider}: {self.provider_product_name}"


class CapacityRule(TimeStampedModel):
    product = models.ForeignKey(
        ServiceProduct,
        on_delete=models.CASCADE,
        related_name="capacity_rules",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="capacity_rules",
    )
    service_date = models.DateField()
    time_slot = models.TimeField(null=True, blank=True)
    capacity = models.PositiveIntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["service_date", "time_slot", "product__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "variant", "service_date", "time_slot"],
                name="unique_capacity_rule_scope",
            )
        ]

    def __str__(self) -> str:
        return f"{self.product} {self.service_date} {self.time_slot or ''}".strip()


class Booking(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "No show"

    provider = models.ForeignKey(
        Provider, on_delete=models.PROTECT, related_name="bookings"
    )
    provider_reference = models.CharField(max_length=120)
    raw_email = models.ForeignKey(
        "ingestion.RawEmail",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )
    provider_payload = models.JSONField(default=dict, blank=True)

    product = models.ForeignKey(
        ServiceProduct,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bookings",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bookings",
    )
    service_date = models.DateField(null=True, blank=True)
    time_slot = models.TimeField(null=True, blank=True)

    guest_name = models.CharField(max_length=180, blank=True)
    guest_email = models.EmailField(blank=True)
    guest_phone = models.CharField(max_length=80, blank=True)
    party_size = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    provider_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    source_created_at = models.DateTimeField(null=True, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-service_date", "time_slot", "provider_reference"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_reference"],
                name="unique_provider_booking_reference",
            ),
            models.CheckConstraint(
                condition=Q(party_size__gte=1),
                name="booking_party_size_gte_1",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.provider} {self.provider_reference}"

    @property
    def is_active_for_capacity(self) -> bool:
        return self.status == self.Status.CONFIRMED


class BookingEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "created", "Created"
        PROVIDER_UPDATE = "provider_update", "Provider update"
        MANUAL_OVERRIDE = "manual_override", "Manual override"
        STATUS_CHANGE = "status_change", "Status change"
        REVIEW_REQUIRED = "review_required", "Review required"

    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    message = models.TextField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_events",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.booking} {self.event_type}"


class ManualOverride(models.Model):
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="manual_overrides"
    )
    field_name = models.CharField(max_length=80)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manual_overrides",
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.booking} {self.field_name}"


class ReviewQueueItem(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        IGNORED = "ignored", "Ignored"

    provider = models.ForeignKey(
        Provider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_items",
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_items",
    )
    raw_email = models.ForeignKey(
        "ingestion.RawEmail",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_items",
    )
    title = models.CharField(max_length=180)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_review_items",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-created_at"]

    def __str__(self) -> str:
        return self.title
