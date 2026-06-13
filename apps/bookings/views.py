from datetime import datetime

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.permissions import can_mutate, operator_required, viewer_required
from apps.bookings.services import (
    apply_manual_override,
    capacity_snapshot,
    get_daily_capacity_summary,
    get_slot_bookings,
)
from apps.ingestion.models import RawEmail

from .forms import BookingEditForm, ProductAliasForm
from .models import (
    Booking,
    BookingEvent,
    ProductAlias,
    ProductVariant,
    ReviewQueueItem,
)


@viewer_required
def daily_operations(request):
    selected_date = _parse_date(request.GET.get("date")) or timezone.localdate()
    query = request.GET.get("q", "").strip()
    bookings = (
        Booking.objects.filter(active_travel_date=selected_date)
        .select_related("provider", "canonical_product", "canonical_variant")
        .order_by(
            "canonical_product__canonical_name",
            "canonical_variant__variant_name",
            "active_start_time",
            "provider_booking_reference",
        )
    )
    if query:
        bookings = _search_bookings(bookings, query)

    rows = _capacity_rows(selected_date, bookings, restrict_to_bookings=bool(query))

    context = {
        "selected_date": selected_date,
        "query": query,
        "rows": rows,
    }
    return render(request, "bookings/daily.html", context)


@viewer_required
def slot_detail(request, date, variant_id, time):
    selected_date = _parse_date(date) or timezone.localdate()
    variant = get_object_or_404(
        ProductVariant.objects.select_related("product"),
        id=variant_id,
    )
    slot = _parse_slot(time)
    bookings = get_slot_bookings(selected_date, variant, slot)
    snapshot = capacity_snapshot(
        product_variant=variant,
        service_date=selected_date,
        start_time=slot,
    )
    return render(
        request,
        "bookings/slot_detail.html",
        {
            "selected_date": selected_date,
            "variant": variant,
            "slot": slot if hasattr(slot, "hour") else None,
            "bookings": bookings,
            "capacity": snapshot,
        },
    )


@viewer_required
def booking_detail(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related(
            "provider",
            "canonical_product",
            "canonical_variant",
        ),
        id=booking_id,
    )
    events = booking.events.select_related("raw_email", "created_by").order_by(
        "-created_at"
    )
    raw_emails = RawEmail.objects.filter(booking_events__booking=booking).distinct()
    return render(
        request,
        "bookings/detail.html",
        {
            "booking": booking,
            "events": events,
            "raw_emails": raw_emails,
            "can_edit_booking": can_mutate(request.user),
        },
    )


@operator_required
def booking_edit(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if request.method == "POST":
        original_values = {
            field: getattr(booking, field)
            for field in BookingEditForm.Meta.fields
            if field != "reason"
        }
        form = BookingEditForm(request.POST, instance=booking)
        if form.is_valid():
            changes = {
                field: form.cleaned_data[field]
                for field in form.fields
                if field != "reason"
                and form.cleaned_data.get(field) != original_values[field]
            }
            booking_for_update = Booking.objects.get(id=booking.id)
            apply_manual_override(
                booking=booking_for_update,
                changes=changes,
                user=request.user,
                reason=form.cleaned_data["reason"],
            )
            messages.success(request, "Booking updated.")
            return redirect("bookings:detail", booking_id=booking.id)
        messages.error(
            request, "Manual edit was not saved. Check the highlighted fields."
        )
    else:
        form = BookingEditForm(instance=booking)
    return render(
        request,
        "bookings/edit.html",
        {"booking": booking, "form": form},
    )


@viewer_required
def review_queue(request):
    issues = (
        ReviewQueueItem.objects.filter(status=ReviewQueueItem.Status.OPEN)
        .select_related("booking", "raw_email")
        .order_by("-created_at")
    )
    return render(
        request,
        "bookings/review_queue.html",
        {"issues": issues, "can_edit_queue": can_mutate(request.user)},
    )


@require_POST
@operator_required
def review_action(request, item_id):
    item = get_object_or_404(ReviewQueueItem, id=item_id)
    action = request.POST.get("action")
    if action == "resolve":
        item.status = ReviewQueueItem.Status.RESOLVED
    elif action == "ignore":
        item.status = ReviewQueueItem.Status.IGNORED
    else:
        messages.error(request, "Unsupported review action.")
        return redirect("review_queue")
    item.resolved_by = request.user
    item.resolved_at = timezone.now()
    item.save(update_fields=["status", "resolved_by", "resolved_at"])
    messages.success(request, "Review item updated.")
    return redirect("review_queue")


@viewer_required
def product_aliases(request):
    can_edit_aliases = can_mutate(request.user)
    review_item = None
    if request.GET.get("review_id"):
        review_item = get_object_or_404(ReviewQueueItem, id=request.GET["review_id"])

    if request.method == "POST":
        if not can_edit_aliases:
            raise PermissionDenied
        alias = None
        old_values = {}
        if request.POST.get("alias_id"):
            alias = get_object_or_404(ProductAlias, id=request.POST["alias_id"])
            old_values = _alias_audit_values(alias)
            form = ProductAliasForm(request.POST, instance=alias)
        else:
            form = ProductAliasForm(request.POST)
        if form.is_valid():
            alias = form.save()
            _record_alias_change(
                alias=alias,
                user=request.user,
                review_item=review_item,
                old_values=old_values,
            )
            messages.success(request, "Product alias saved.")
            return redirect("bookings:aliases")
        messages.error(request, "Alias was not saved. Check the highlighted fields.")
    else:
        initial = {}
        if review_item:
            initial = _alias_initial_from_review(review_item)
        form = ProductAliasForm(initial=initial)

    aliases = (
        ProductAlias.objects.select_related(
            "provider",
            "canonical_product",
            "canonical_variant",
        )
        .all()
        .order_by("provider__name", "raw_product_name")
    )
    return render(
        request,
        "bookings/aliases.html",
        {
            "aliases": aliases,
            "form": form,
            "review_item": review_item,
            "can_edit_aliases": can_edit_aliases,
        },
    )


@require_POST
@operator_required
def approve_alias(request, alias_id):
    alias = get_object_or_404(ProductAlias, id=alias_id)
    old_values = _alias_audit_values(alias)
    alias.approved = True
    alias.save(update_fields=["approved", "updated_at"])
    _record_alias_change(
        alias=alias,
        user=request.user,
        review_item=None,
        old_values=old_values,
    )
    messages.success(request, "Product alias approved.")
    return redirect("bookings:aliases")


@viewer_required
def raw_email_detail(request, raw_email_id):
    raw_email = get_object_or_404(
        RawEmail.objects.select_related("provider_detected"),
        id=raw_email_id,
    )
    return render(request, "bookings/raw_email_detail.html", {"raw_email": raw_email})


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _search_bookings(queryset, query):
    return queryset.filter(
        Q(provider_booking_reference__icontains=query)
        | Q(provider_order_reference__icontains=query)
        | Q(lead_traveler_name__icontains=query)
        | Q(lead_traveler_phone__icontains=query)
        | Q(provider__name__icontains=query)
        | Q(provider__code__icontains=query)
    )


def _capacity_status(remaining, pending):
    if remaining is None:
        return "unknown"
    if remaining < 0:
        return "over"
    if remaining == 0 and pending:
        return "waitlist"
    if remaining <= 3:
        return "tight"
    return "ok"


def _slot_url(selected_date, variant, slot):
    if not variant:
        return ""
    slot_value = slot.strftime("%H:%M") if hasattr(slot, "strftime") else slot or "open"
    return reverse(
        "bookings:slot_detail",
        kwargs={
            "date": selected_date.isoformat(),
            "variant_id": variant.id,
            "time": slot_value,
        },
    )


def _capacity_rows(selected_date, filtered_bookings, *, restrict_to_bookings=False):
    allowed_keys = {
        (booking.canonical_variant_id, _slot_for_capacity_view(booking))
        for booking in filtered_bookings
        if booking.canonical_variant_id
    }
    if restrict_to_bookings and not allowed_keys:
        return []
    rows = []
    for summary in get_daily_capacity_summary(selected_date):
        key = (summary["variant"].id, summary["slot"])
        if restrict_to_bookings and key not in allowed_keys:
            continue
        rows.append(
            {
                "product": summary["product"],
                "variant": summary["variant"],
                "slot": summary["slot"],
                "slot_label": summary["slot_label"],
                "confirmed": summary["confirmed_pax"],
                "pending": summary["pending_pax"],
                "manual_review": summary["manual_review_pax"],
                "capacity": summary["capacity"],
                "remaining": summary["remaining"],
                "status": _capacity_status(
                    summary["remaining"],
                    summary["pending_pax"],
                ),
                "slot_url": _slot_url(
                    selected_date,
                    summary["variant"],
                    summary["slot"],
                ),
            }
        )
    return rows


def _slot_for_capacity_view(booking):
    slot_type = booking.active_slot_type or (
        booking.canonical_variant.slot_type if booking.canonical_variant else ""
    )
    if slot_type in {
        ProductVariant.SlotType.FULL_DAY,
        ProductVariant.SlotType.HALF_DAY,
    }:
        return slot_type
    if slot_type == ProductVariant.SlotType.FIXED_TIME:
        return booking.active_start_time
    if slot_type == ProductVariant.SlotType.PRIVATE_GROUP:
        return booking.active_start_time or ProductVariant.SlotType.PRIVATE_GROUP
    return booking.active_start_time or slot_type or None


def _parse_slot(value):
    if value in {"open", "", None}:
        return None
    if value in ProductVariant.SlotType.values:
        return value
    return datetime.strptime(value, "%H:%M").time()


def _record_alias_change(*, alias, user, review_item, old_values=None):
    booking = review_item.booking if review_item else None
    BookingEvent.objects.create(
        booking=booking,
        event_type=BookingEvent.EventType.PRODUCT_ALIAS_CHANGED,
        source=BookingEvent.Source.MANUAL,
        old_values=old_values or {},
        new_values={
            "alias_id": alias.id,
            "provider": alias.provider.code,
            "raw_product_name": alias.raw_product_name,
            "raw_option_name": alias.raw_option_name,
            "canonical_product": alias.canonical_product.canonical_name,
            "canonical_variant": (
                alias.canonical_variant.variant_name
                if alias.canonical_variant
                else None
            ),
            "approved": alias.approved,
        },
        created_by=user,
    )


def _alias_audit_values(alias):
    return {
        "alias_id": alias.id,
        "provider": alias.provider.code,
        "raw_product_name": alias.raw_product_name,
        "raw_option_name": alias.raw_option_name,
        "canonical_product": alias.canonical_product.canonical_name,
        "canonical_variant": (
            alias.canonical_variant.variant_name if alias.canonical_variant else None
        ),
        "approved": alias.approved,
    }


def _alias_initial_from_review(review_item):
    booking = review_item.booking
    if not booking:
        return {}
    return {
        "provider": booking.provider,
        "raw_product_name": booking.raw_product_name,
        "raw_option_name": booking.raw_option_name,
        "provider_product_code": booking.provider_product_code,
        "provider_option_code": booking.provider_option_code,
        "approved": True,
    }
