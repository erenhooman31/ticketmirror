from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Provider(TimeStampedModel):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=60, unique=True)
    active = models.BooleanField(default=True)
    known_sender_patterns = models.JSONField(default=list, blank=True)
    known_subject_patterns = models.JSONField(default=list, blank=True)
    parser_key = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"], name="provider_code_idx"),
            models.Index(fields=["active"], name="provider_active_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class TourActivity(TimeStampedModel):
    class Category(models.TextChoices):
        CRUISE = "cruise", "Cruise"
        LAND_AND_CRUISE = "land_and_cruise", "Land and cruise"
        YACHT = "yacht", "Yacht"
        OTHER = "other", "Other"

    name = models.CharField(max_length=180, unique=True)
    internal_display_name = models.CharField(max_length=180, blank=True)
    active = models.BooleanField(default=True)
    category = models.CharField(
        max_length=40,
        choices=Category.choices,
        blank=True,
    )
    display_settings = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["active"], name="activity_active_idx"),
            models.Index(
                fields=["category", "active"],
                name="activity_cat_active_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ActivitySchedule(TimeStampedModel):
    class ScheduleKind(models.TextChoices):
        CURRENT = "current", "Current"
        OTHER = "other", "Other"

    class RecurrenceMode(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        DATE_SPECIFIC = "date_specific", "Date specific"
        MANUAL = "manual", "Manual"

    activity = models.ForeignKey(
        TourActivity,
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    schedule_kind = models.CharField(
        max_length=20,
        choices=ScheduleKind.choices,
        default=ScheduleKind.CURRENT,
    )
    name = models.CharField(max_length=120, blank=True)
    active = models.BooleanField(default=True)
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    days_of_week = models.JSONField(default=list, blank=True)
    timezone = models.CharField(max_length=80, default=settings.TIME_ZONE)
    priority = models.PositiveIntegerField(default=100)
    recurrence_mode = models.CharField(
        max_length=30,
        choices=RecurrenceMode.choices,
        default=RecurrenceMode.WEEKLY,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["activity__name", "schedule_kind", "priority", "date_from"]
        indexes = [
            models.Index(
                fields=["activity", "schedule_kind"],
                name="activity_schedule_kind_idx",
            ),
            models.Index(
                fields=["date_from", "date_to"],
                name="activity_schedule_dates_idx",
            ),
            models.Index(fields=["active"], name="activity_schedule_active_idx"),
        ]

    def __str__(self) -> str:
        label = self.name or self.get_schedule_kind_display()
        return f"{self.activity} - {label}"


class ActivityScheduleSlot(TimeStampedModel):
    class SlotType(models.TextChoices):
        FIXED_TIME = "fixed_time", "Fixed time"
        HALF_DAY = "half_day", "Half day"
        FULL_DAY = "full_day", "Full day"
        OPEN_TIME = "open_time", "Open time"
        PRIVATE_GROUP = "private_group", "Private group"

    schedule = models.ForeignKey(
        ActivitySchedule,
        on_delete=models.CASCADE,
        related_name="slots",
    )
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField()
    slot_type = models.CharField(max_length=30, choices=SlotType.choices)
    capacity = models.PositiveIntegerField()
    days_of_week = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["schedule__activity__name", "schedule__schedule_kind", "start_time"]
        indexes = [
            models.Index(
                fields=["schedule", "active"],
                name="act_slot_sched_active_idx",
            ),
            models.Index(fields=["start_time"], name="activity_slot_start_idx"),
            models.Index(fields=["slot_type"], name="activity_slot_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.schedule} {self.start_time:%H:%M}"


class ActivityScheduleException(TimeStampedModel):
    class ExceptionType(models.TextChoices):
        BLOCKED = "blocked", "Blocked"
        CLOSED = "closed", "Closed"
        OVERRIDE_CAPACITY = "override_capacity", "Override capacity"
        EXTRA_SLOT = "extra_slot", "Extra slot"
        REMOVED_SLOT = "removed_slot", "Removed slot"

    schedule = models.ForeignKey(
        ActivitySchedule,
        on_delete=models.CASCADE,
        related_name="exceptions",
    )
    exception_type = models.CharField(max_length=40, choices=ExceptionType.choices)
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    reason = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["schedule__activity__name", "date", "start_time", "id"]
        indexes = [
            models.Index(
                fields=["schedule", "date", "active"],
                name="schedule_exception_date_idx",
            ),
            models.Index(
                fields=["exception_type", "active"],
                name="schedule_exception_type_idx",
            ),
        ]

    def __str__(self) -> str:
        label = self.get_exception_type_display()
        time_text = self.start_time.strftime("%H:%M") if self.start_time else "all day"
        return f"{self.schedule} {self.date} {time_text} {label}"


class ActivityPeopleRule(TimeStampedModel):
    activity = models.OneToOneField(
        TourActivity,
        on_delete=models.CASCADE,
        related_name="people_rule",
    )
    min_people_per_booking = models.PositiveIntegerField(null=True, blank=True)
    max_people_per_booking = models.PositiveIntegerField(null=True, blank=True)
    default_capacity = models.PositiveIntegerField(null=True, blank=True)
    capacity_note = models.TextField(blank=True)

    class Meta:
        ordering = ["activity__name"]

    def __str__(self) -> str:
        return f"{self.activity} people rule"


class ProviderAlias(TimeStampedModel):
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="provider_aliases",
    )
    raw_product_name = models.CharField(max_length=240)
    raw_option_name = models.CharField(max_length=240, null=True, blank=True)
    provider_product_code = models.CharField(max_length=120, null=True, blank=True)
    provider_option_code = models.CharField(max_length=120, null=True, blank=True)
    linked_activity = models.ForeignKey(
        TourActivity,
        on_delete=models.PROTECT,
        related_name="provider_aliases",
    )
    linked_schedule = models.ForeignKey(
        ActivitySchedule,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="provider_aliases",
    )
    linked_slot = models.ForeignKey(
        ActivityScheduleSlot,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="provider_aliases",
    )
    approved = models.BooleanField(default=False)
    needs_manual_confirmation = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["provider__name", "raw_product_name", "raw_option_name"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "provider",
                    "raw_product_name",
                    "raw_option_name",
                    "provider_product_code",
                    "provider_option_code",
                ],
                name="unique_provider_alias",
            )
        ]
        indexes = [
            models.Index(
                fields=["provider", "raw_product_name"],
                name="alias_provider_name_idx",
            ),
            models.Index(
                fields=["provider", "provider_product_code"],
                name="alias_provider_code_idx",
            ),
            models.Index(fields=["approved"], name="alias_approved_idx"),
            models.Index(
                fields=["needs_manual_confirmation"],
                name="alias_manual_confirm_idx",
            ),
        ]

    def __str__(self) -> str:
        option = f" / {self.raw_option_name}" if self.raw_option_name else ""
        return f"{self.provider}: {self.raw_product_name}{option}"

    def save(self, *args, **kwargs):
        self.raw_option_name = self.raw_option_name or ""
        self.provider_product_code = self.provider_product_code or ""
        self.provider_option_code = self.provider_option_code or ""
        super().save(*args, **kwargs)


class Booking(TimeStampedModel):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        PENDING_PROVIDER_ACCEPTANCE = (
            "pending_provider_acceptance",
            "Pending provider acceptance",
        )
        CANCELLED = "cancelled", "Cancelled"
        REJECTED = "rejected", "Rejected"
        MODIFIED = "modified", "Modified"
        MANUAL_REVIEW = "manual_review", "Manual review"
        PARSE_FAILED = "parse_failed", "Parse failed"
        DUPLICATE_IGNORED = "duplicate_ignored", "Duplicate ignored"

    class AttendanceStatus(models.TextChoices):
        CLEAR = "", "CLEAR"
        GELDI = "geldi", "GELDI"
        GELMEDI = "gelmedi", "GELMEDI"
        SONRA_GELECEK = "sonra_gelecek", "SONRA GELECEK"

    provider = models.ForeignKey(
        Provider,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    provider_booking_reference = models.CharField(max_length=120)
    provider_order_reference = models.CharField(max_length=120, null=True, blank=True)
    status = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.PENDING_PROVIDER_ACCEPTANCE,
    )
    attendance_status = models.CharField(
        max_length=30,
        choices=AttendanceStatus.choices,
        blank=True,
        default=AttendanceStatus.CLEAR,
    )
    activity = models.ForeignKey(
        TourActivity,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bookings",
    )
    schedule_slot = models.ForeignKey(
        ActivityScheduleSlot,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bookings",
    )
    raw_product_name = models.CharField(max_length=240, blank=True)
    raw_option_name = models.CharField(max_length=240, null=True, blank=True)
    provider_product_code = models.CharField(max_length=120, null=True, blank=True)
    provider_option_code = models.CharField(max_length=120, null=True, blank=True)
    provider_travel_date = models.DateField(null=True, blank=True)
    provider_start_time = models.TimeField(null=True, blank=True)
    provider_end_time = models.TimeField(null=True, blank=True)
    provider_slot_type = models.CharField(
        max_length=30,
        choices=ActivityScheduleSlot.SlotType.choices,
        blank=True,
    )
    active_travel_date = models.DateField(null=True, blank=True)
    active_start_time = models.TimeField(null=True, blank=True)
    active_end_time = models.TimeField(null=True, blank=True)
    active_slot_type = models.CharField(
        max_length=30,
        choices=ActivityScheduleSlot.SlotType.choices,
        blank=True,
    )
    provider_traveler_count = models.PositiveIntegerField(null=True, blank=True)
    active_traveler_count = models.PositiveIntegerField(null=True, blank=True)
    lead_traveler_name = models.CharField(max_length=180, null=True, blank=True)
    lead_traveler_email = models.EmailField(null=True, blank=True)
    lead_traveler_phone = models.CharField(max_length=80, null=True, blank=True)
    traveler_names = models.JSONField(default=list, blank=True)
    ticket_breakdown = models.JSONField(default=dict, blank=True)
    language = models.CharField(max_length=80, null=True, blank=True)
    pickup_location = models.TextField(null=True, blank=True)
    meeting_point = models.TextField(null=True, blank=True)
    special_requirements = models.TextField(null=True, blank=True)
    customer_message = models.TextField(null=True, blank=True)
    price = models.JSONField(default=dict, blank=True)
    payment_status = models.CharField(max_length=80, null=True, blank=True)
    source_thread_id = models.CharField(max_length=180, null=True, blank=True)
    last_email_received_at = models.DateTimeField(null=True, blank=True)
    manual_override_fields = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = [
            "-active_travel_date",
            "active_start_time",
            "provider_booking_reference",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_booking_reference"],
                name="unique_provider_booking_reference",
            )
        ]
        indexes = [
            models.Index(fields=["active_travel_date"], name="booking_active_date_idx"),
            models.Index(fields=["status"], name="booking_status_idx"),
            models.Index(
                fields=["activity", "active_travel_date"],
                name="booking_activity_date_idx",
            ),
            models.Index(
                fields=["schedule_slot", "active_travel_date"],
                name="booking_slot_date_idx",
            ),
            models.Index(
                fields=["provider", "status"],
                name="booking_provider_status_idx",
            ),
            models.Index(
                fields=["provider", "provider_order_reference"],
                name="booking_provider_order_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.provider.code} {self.provider_booking_reference}"

    @property
    def is_active_for_capacity(self) -> bool:
        if self.attendance_status == self.AttendanceStatus.GELMEDI:
            return False
        return self.status not in {
            self.Status.CANCELLED,
            self.Status.REJECTED,
            self.Status.PARSE_FAILED,
            self.Status.DUPLICATE_IGNORED,
        }

    @property
    def has_manual_overrides(self) -> bool:
        return bool(self.manual_override_fields)


class BookingEvent(models.Model):
    class EventType(models.TextChoices):
        EMAIL_NEW_BOOKING = "email_new_booking", "Email new booking"
        EMAIL_BOOKING_REQUEST = "email_booking_request", "Email booking request"
        EMAIL_UPDATE = "email_update", "Email update"
        EMAIL_CANCELLATION = "email_cancellation", "Email cancellation"
        MANUAL_EDIT = "manual_edit", "Manual edit"
        MANUAL_STATUS_CHANGE = "manual_status_change", "Manual status change"
        PARSER_REVIEW_RESOLVED = (
            "parser_review_resolved",
            "Parser review resolved",
        )
        PROVIDER_ALIAS_CHANGED = "provider_alias_changed", "Provider alias changed"
        CONFLICT_DETECTED = "conflict_detected", "Conflict detected"

    class Source(models.TextChoices):
        EMAIL = "email", "Email"
        MANUAL = "manual", "Manual"
        SYSTEM = "system", "System"

    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    source = models.CharField(max_length=20, choices=Source.choices)
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    raw_email = models.ForeignKey(
        "ingestion.RawEmail",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_events",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["event_type", "created_at"],
                name="event_type_created_idx",
            ),
            models.Index(
                fields=["source", "created_at"],
                name="event_source_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} at {self.created_at:%Y-%m-%d %H:%M}"


class ReviewQueueItem(models.Model):
    class IssueType(models.TextChoices):
        PROVIDER_NOT_DETECTED = "provider_not_detected", "Provider not detected"
        REFERENCE_MISSING = "reference_missing", "Reference missing"
        DATE_MISSING = "date_missing", "Date missing"
        TIME_MISSING = "time_missing", "Time missing"
        TRAVELER_COUNT_MISSING = (
            "traveler_count_missing",
            "Traveler count missing",
        )
        LEAD_TRAVELER_MISSING = "lead_traveler_missing", "Lead traveler missing"
        PROVIDER_ALIAS_MISSING = "provider_alias_missing", "Provider alias missing"
        PRODUCT_MISMATCH = "product_mismatch", "Product mismatch"
        LOW_CONFIDENCE_PARSE = "low_confidence_parse", "Low confidence parse"
        POSSIBLE_DUPLICATE = "possible_duplicate", "Possible duplicate"
        MANUAL_OVERRIDE_CONFLICT = (
            "manual_override_conflict",
            "Manual override conflict",
        )
        CANCELLATION_WITHOUT_BOOKING = (
            "cancellation_without_booking",
            "Cancellation without booking",
        )
        CAPACITY_OVERBOOKED = "capacity_overbooked", "Capacity overbooked"
        PARSER_ERROR = "parser_error", "Parser error"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        IGNORED = "ignored", "Ignored"

    raw_email = models.ForeignKey(
        "ingestion.RawEmail",
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
    issue_type = models.CharField(max_length=40, choices=IssueType.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    title = models.CharField(max_length=180)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_review_items",
    )

    class Meta:
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(
                fields=["issue_type", "status"],
                name="review_issue_status_idx",
            ),
            models.Index(fields=["created_at"], name="review_created_idx"),
        ]

    def __str__(self) -> str:
        return self.title
