from django.contrib import admin

from .models import (
    Booking,
    BookingEvent,
    CapacityRule,
    ManualOverride,
    ProductAlias,
    ProductVariant,
    Provider,
    ReviewQueueItem,
    ServiceProduct,
)


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(ServiceProduct)
class ServiceProductAdmin(admin.ModelAdmin):
    inlines = [ProductVariantInline]
    list_display = ("name", "duration_type", "is_active", "created_at")
    list_filter = ("duration_type", "is_active")
    search_fields = ("name",)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "start_time", "default_capacity", "is_active")
    list_filter = ("is_active", "product")
    search_fields = ("name", "product__name")


@admin.register(ProductAlias)
class ProductAliasAdmin(admin.ModelAdmin):
    list_display = (
        "provider_product_name",
        "provider",
        "product",
        "variant",
        "is_active",
    )
    list_filter = ("provider", "product", "is_active")
    search_fields = ("provider_product_name", "provider_product_code", "product__name")


@admin.register(CapacityRule)
class CapacityRuleAdmin(admin.ModelAdmin):
    list_display = ("product", "variant", "service_date", "time_slot", "capacity")
    list_filter = ("service_date", "product", "variant")
    search_fields = ("product__name", "variant__name")


class BookingEventInline(admin.TabularInline):
    model = BookingEvent
    extra = 0
    readonly_fields = ("event_type", "message", "changed_by", "metadata", "created_at")
    can_delete = False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    inlines = [BookingEventInline]
    readonly_fields = ("provider", "provider_reference", "created_at", "updated_at")
    list_display = (
        "provider_reference",
        "provider",
        "service_date",
        "time_slot",
        "product",
        "variant",
        "party_size",
        "status",
    )
    list_filter = ("provider", "status", "service_date", "product", "variant")
    search_fields = (
        "provider_reference",
        "guest_name",
        "guest_email",
        "provider__name",
        "product__name",
    )
    date_hierarchy = "service_date"


@admin.register(BookingEvent)
class BookingEventAdmin(admin.ModelAdmin):
    readonly_fields = (
        "booking",
        "event_type",
        "message",
        "changed_by",
        "metadata",
        "created_at",
    )
    list_display = ("booking", "event_type", "changed_by", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("booking__provider_reference", "message")


@admin.register(ManualOverride)
class ManualOverrideAdmin(admin.ModelAdmin):
    readonly_fields = (
        "booking",
        "field_name",
        "old_value",
        "new_value",
        "changed_by",
        "created_at",
    )
    list_display = ("booking", "field_name", "changed_by", "created_at")
    search_fields = ("booking__provider_reference", "field_name")


@admin.register(ReviewQueueItem)
class ReviewQueueItemAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "provider", "booking", "raw_email", "created_at")
    list_filter = ("status", "provider", "created_at")
    search_fields = ("title", "notes", "booking__provider_reference")
