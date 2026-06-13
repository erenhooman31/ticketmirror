from django.contrib import admin

from .models import (
    Booking,
    BookingEvent,
    CapacityRule,
    Product,
    ProductAlias,
    ProductVariant,
    Provider,
    ReviewQueueItem,
)


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "active", "parser_key", "created_at")
    list_filter = ("active",)
    search_fields = ("name", "code", "parser_key")


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = (
        "variant_name",
        "slot_type",
        "duration_minutes",
        "default_capacity",
        "active",
    )


class ProductAliasForProductInline(admin.TabularInline):
    model = ProductAlias
    fk_name = "canonical_product"
    extra = 0
    fields = (
        "provider",
        "raw_product_name",
        "raw_option_name",
        "canonical_variant",
        "confidence",
        "approved",
    )
    show_change_link = True


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductVariantInline, ProductAliasForProductInline]
    list_display = (
        "canonical_name",
        "category",
        "active",
        "variant_count",
        "alias_count",
        "created_at",
    )
    list_filter = ("category", "active")
    search_fields = ("canonical_name", "category", "notes")

    @admin.display(description="Variants")
    def variant_count(self, obj):
        return obj.variants.count()

    @admin.display(description="Aliases")
    def alias_count(self, obj):
        return obj.provider_aliases.count()


class ProductAliasForVariantInline(admin.TabularInline):
    model = ProductAlias
    fk_name = "canonical_variant"
    extra = 0
    fields = (
        "provider",
        "raw_product_name",
        "raw_option_name",
        "confidence",
        "approved",
    )
    show_change_link = True


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    inlines = [ProductAliasForVariantInline]
    list_display = (
        "variant_name",
        "product",
        "slot_type",
        "duration_minutes",
        "default_capacity",
        "active",
        "alias_count",
    )
    list_filter = ("slot_type", "active", "product")
    search_fields = ("variant_name", "product__canonical_name")

    @admin.display(description="Aliases")
    def alias_count(self, obj):
        return obj.provider_aliases.count()


@admin.register(ProductAlias)
class ProductAliasAdmin(admin.ModelAdmin):
    list_display = (
        "raw_product_name",
        "raw_option_name",
        "provider",
        "canonical_product",
        "canonical_variant",
        "confidence",
        "approved",
    )
    list_filter = ("provider", "approved", "canonical_product")
    search_fields = (
        "raw_product_name",
        "raw_option_name",
        "provider_product_code",
        "provider_option_code",
        "canonical_product__canonical_name",
        "canonical_variant__variant_name",
    )


@admin.register(CapacityRule)
class CapacityRuleAdmin(admin.ModelAdmin):
    list_display = (
        "product_variant",
        "date_from",
        "date_to",
        "day_of_week",
        "slot_start_time",
        "slot_end_time",
        "capacity",
        "active",
    )
    list_filter = ("active", "day_of_week", "product_variant__product")
    search_fields = (
        "product_variant__variant_name",
        "product_variant__product__canonical_name",
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
        "canonical_product",
        "canonical_variant",
        "active_traveler_count",
        "lead_traveler_name",
        "has_manual_overrides",
    )
    list_filter = (
        "provider",
        "status",
        "active_travel_date",
        "canonical_product",
        "canonical_variant",
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
        "canonical_product__canonical_name",
        "canonical_variant__variant_name",
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
            "Product mapping",
            {
                "fields": (
                    "canonical_product",
                    "canonical_variant",
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
