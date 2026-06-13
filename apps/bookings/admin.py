from django.contrib import admin

from .models import (
    ActivityPeopleRule,
    ActivitySchedule,
    ActivityScheduleSlot,
    Booking,
    BookingEvent,
    Provider,
    ProviderAlias,
    ReviewQueueItem,
    TourActivity,
)


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "active", "parser_key", "created_at")
    list_filter = ("active",)
    search_fields = ("name", "code", "parser_key")


class ActivityScheduleInline(admin.TabularInline):
    model = ActivitySchedule
    extra = 0
    fields = (
        "schedule_kind",
        "name",
        "active",
        "date_from",
        "date_to",
        "days_of_week",
        "priority",
    )
    show_change_link = True


class ActivityPeopleRuleInline(admin.StackedInline):
    model = ActivityPeopleRule
    extra = 0
    max_num = 1


class ProviderAliasForActivityInline(admin.TabularInline):
    model = ProviderAlias
    fk_name = "linked_activity"
    extra = 0
    fields = (
        "provider",
        "raw_product_name",
        "raw_option_name",
        "linked_slot",
        "approved",
        "needs_manual_confirmation",
    )
    show_change_link = True


@admin.register(TourActivity)
class TourActivityAdmin(admin.ModelAdmin):
    inlines = [
        ActivityPeopleRuleInline,
        ActivityScheduleInline,
        ProviderAliasForActivityInline,
    ]
    list_display = (
        "name",
        "internal_display_name",
        "category",
        "active",
        "schedule_count",
        "alias_count",
        "created_at",
    )
    list_filter = ("category", "active")
    search_fields = ("name", "internal_display_name", "category", "notes")

    @admin.display(description="Schedules")
    def schedule_count(self, obj):
        return obj.schedules.count()

    @admin.display(description="Aliases")
    def alias_count(self, obj):
        return obj.provider_aliases.count()


class ActivityScheduleSlotInline(admin.TabularInline):
    model = ActivityScheduleSlot
    extra = 0
    fields = (
        "start_time",
        "end_time",
        "duration_minutes",
        "slot_type",
        "capacity",
        "active",
    )


@admin.register(ActivitySchedule)
class ActivityScheduleAdmin(admin.ModelAdmin):
    inlines = [ActivityScheduleSlotInline]
    list_display = (
        "activity",
        "schedule_kind",
        "name",
        "active",
        "date_from",
        "date_to",
        "priority",
    )
    list_filter = ("schedule_kind", "active", "activity")
    search_fields = ("name", "activity__name")


@admin.register(ActivityScheduleSlot)
class ActivityScheduleSlotAdmin(admin.ModelAdmin):
    list_display = (
        "schedule",
        "start_time",
        "end_time",
        "duration_minutes",
        "slot_type",
        "capacity",
        "active",
    )
    list_filter = ("slot_type", "active", "schedule__activity")
    search_fields = ("schedule__name", "schedule__activity__name")


@admin.register(ActivityPeopleRule)
class ActivityPeopleRuleAdmin(admin.ModelAdmin):
    list_display = (
        "activity",
        "min_people_per_booking",
        "max_people_per_booking",
        "default_capacity",
    )
    search_fields = ("activity__name", "capacity_note")


@admin.register(ProviderAlias)
class ProviderAliasAdmin(admin.ModelAdmin):
    list_display = (
        "raw_product_name",
        "raw_option_name",
        "provider",
        "linked_activity",
        "linked_slot",
        "approved",
        "needs_manual_confirmation",
    )
    list_filter = (
        "provider",
        "approved",
        "needs_manual_confirmation",
        "linked_activity",
    )
    search_fields = (
        "raw_product_name",
        "raw_option_name",
        "provider_product_code",
        "provider_option_code",
        "linked_activity__name",
        "linked_slot__schedule__name",
    )


class BookingEventInline(admin.TabularInline):
    model = BookingEvent
    extra = 0
    readonly_fields = (
        "event_type",
        "source",
        "old_values",
        "new_values",
        "raw_email",
        "created_by",
        "created_at",
    )
    fields = readonly_fields
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    inlines = [BookingEventInline]
    readonly_fields = ("created_at", "updated_at")
    list_display = (
        "provider_booking_reference",
        "provider",
        "status",
        "active_travel_date",
        "active_start_time",
        "activity",
        "schedule_slot",
        "active_traveler_count",
        "lead_traveler_name",
        "has_manual_overrides",
    )
    list_filter = (
        "provider",
        "status",
        "active_travel_date",
        "activity",
        "schedule_slot",
        "active_slot_type",
    )
    search_fields = (
        "provider_booking_reference",
        "provider_order_reference",
        "lead_traveler_name",
        "lead_traveler_email",
        "lead_traveler_phone",
        "raw_product_name",
        "raw_option_name",
        "provider__name",
        "provider__code",
        "activity__name",
        "schedule_slot__schedule__name",
    )
    date_hierarchy = "active_travel_date"
    fieldsets = (
        (
            "Provider identity",
            {
                "fields": (
                    "provider",
                    "provider_booking_reference",
                    "provider_order_reference",
                    "status",
                    "source_thread_id",
                    "last_email_received_at",
                )
            },
        ),
        (
            "Activity mapping",
            {
                "fields": (
                    "activity",
                    "schedule_slot",
                    "raw_product_name",
                    "raw_option_name",
                    "provider_product_code",
                    "provider_option_code",
                )
            },
        ),
        (
            "Provider schedule",
            {
                "fields": (
                    "provider_travel_date",
                    "provider_start_time",
                    "provider_end_time",
                    "provider_slot_type",
                    "provider_traveler_count",
                )
            },
        ),
        (
            "Active operations",
            {
                "fields": (
                    "active_travel_date",
                    "active_start_time",
                    "active_end_time",
                    "active_slot_type",
                    "active_traveler_count",
                    "manual_override_fields",
                )
            },
        ),
        (
            "Traveler details",
            {
                "fields": (
                    "lead_traveler_name",
                    "lead_traveler_email",
                    "lead_traveler_phone",
                    "traveler_names",
                    "ticket_breakdown",
                    "language",
                )
            },
        ),
        (
            "Operational notes",
            {
                "fields": (
                    "pickup_location",
                    "meeting_point",
                    "special_requirements",
                    "customer_message",
                    "price",
                    "payment_status",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly_fields.extend(["provider", "provider_booking_reference"])
        return readonly_fields


@admin.register(BookingEvent)
class BookingEventAdmin(admin.ModelAdmin):
    readonly_fields = (
        "booking",
        "event_type",
        "source",
        "old_values",
        "new_values",
        "raw_email",
        "created_by",
        "created_at",
    )
    list_display = ("booking", "event_type", "source", "created_by", "created_at")
    list_filter = ("event_type", "source", "created_at")
    search_fields = (
        "booking__provider_booking_reference",
        "booking__provider__name",
        "booking__provider__code",
    )


@admin.register(ReviewQueueItem)
class ReviewQueueItemAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "issue_type",
        "status",
        "booking",
        "raw_email",
        "created_at",
        "resolved_at",
    )
    list_filter = ("issue_type", "status", "created_at", "resolved_at")
    search_fields = (
        "title",
        "details",
        "booking__provider_booking_reference",
        "raw_email__subject",
    )
