import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.bookings.models import (
    CapacityRule,
    Product,
    ProductAlias,
    ProductVariant,
    Provider,
)

DEFAULT_SEED_PATH = Path("data/sample_products.yml")


class Command(BaseCommand):
    help = "Create or update products, variants, capacity rules, and aliases."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(DEFAULT_SEED_PATH),
            help="Path to a YAML or JSON product seed file.",
        )

    def handle(self, *args, **options):
        seed_path = Path(options["file"])
        if not seed_path.is_absolute():
            seed_path = Path.cwd() / seed_path

        payload = load_seed_file(seed_path)
        stats = {
            "products_created": 0,
            "products_updated": 0,
            "variants_created": 0,
            "variants_updated": 0,
            "capacity_rules_created": 0,
            "capacity_rules_updated": 0,
            "aliases_created": 0,
            "aliases_updated": 0,
        }

        with transaction.atomic():
            for product_payload in require_list(payload, "products", "root"):
                seed_product(product_payload, stats)

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded products: "
                f"{stats['products_created']} created, "
                f"{stats['products_updated']} updated; "
                "variants: "
                f"{stats['variants_created']} created, "
                f"{stats['variants_updated']} updated; "
                "capacity rules: "
                f"{stats['capacity_rules_created']} created, "
                f"{stats['capacity_rules_updated']} updated; "
                "aliases: "
                f"{stats['aliases_created']} created, "
                f"{stats['aliases_updated']} updated."
            )
        )


def load_seed_file(seed_path):
    if not seed_path.exists():
        raise CommandError(f"Seed file does not exist: {seed_path}")

    if seed_path.suffix.lower() == ".json":
        with seed_path.open(encoding="utf-8") as seed_file:
            return json.load(seed_file)

    if seed_path.suffix.lower() not in {".yml", ".yaml"}:
        raise CommandError("Seed file must be YAML (.yml/.yaml) or JSON (.json).")

    try:
        import yaml
    except ImportError as exc:
        raise CommandError(
            "PyYAML is required to load YAML seed files. Install requirements.txt."
        ) from exc

    with seed_path.open(encoding="utf-8") as seed_file:
        data = yaml.safe_load(seed_file)

    if data is None:
        raise CommandError(f"Seed file is empty: {seed_path}")
    return data


def seed_product(product_payload, stats):
    context = "product"
    canonical_name = require_string(product_payload, "canonical_name", context)
    product_defaults = {
        "category": string_or_blank(product_payload.get("category")),
        "active": bool(product_payload.get("active", True)),
        "notes": string_or_blank(product_payload.get("notes")),
    }
    product, created = Product.objects.update_or_create(
        canonical_name=canonical_name,
        defaults=product_defaults,
    )
    increment(stats, "products", created)

    for alias_payload in product_payload.get("aliases", []):
        seed_alias(alias_payload, product, None, stats)

    variants = require_list(product_payload, "variants", canonical_name)
    for variant_payload in variants:
        seed_variant(product, variant_payload, stats)


def seed_variant(product, variant_payload, stats):
    context = f"{product.canonical_name} variant"
    variant_name = require_string(variant_payload, "variant_name", context)
    slot_type = require_string(variant_payload, "slot_type", context)
    valid_slot_types = {choice[0] for choice in ProductVariant.SlotType.choices}
    if slot_type not in valid_slot_types:
        raise CommandError(
            f"{context} {variant_name!r} has invalid slot_type {slot_type!r}."
        )

    default_capacity = optional_positive_int(
        variant_payload.get("default_capacity"),
        f"{context} {variant_name} default_capacity",
    )
    variant, created = ProductVariant.objects.update_or_create(
        product=product,
        variant_name=variant_name,
        defaults={
            "slot_type": slot_type,
            "duration_minutes": optional_positive_int(
                variant_payload.get("duration_minutes"),
                f"{context} {variant_name} duration_minutes",
            ),
            "default_capacity": default_capacity,
            "active": bool(variant_payload.get("active", True)),
        },
    )
    increment(stats, "variants", created)

    capacity_rule_count = 0
    for slot_payload in variant_payload.get("slots", []):
        seed_capacity_rule(variant, slot_payload, default_capacity, stats)
        capacity_rule_count += 1

    for rule_payload in variant_payload.get("capacity_rules", []):
        seed_capacity_rule(variant, rule_payload, default_capacity, stats)
        capacity_rule_count += 1

    if capacity_rule_count == 0 and default_capacity is not None:
        seed_capacity_rule(
            variant, {"capacity": default_capacity}, default_capacity, stats
        )

    for alias_payload in variant_payload.get("aliases", []):
        seed_alias(alias_payload, product, variant, stats)


def seed_capacity_rule(variant, rule_payload, default_capacity, stats):
    if isinstance(rule_payload, str):
        rule_payload = {"start_time": rule_payload}
    if not isinstance(rule_payload, dict):
        raise CommandError(f"Capacity rule for {variant} must be a string or mapping.")

    capacity = optional_positive_int(rule_payload.get("capacity"), "capacity")
    if capacity is None:
        capacity = default_capacity
    if capacity is None:
        raise CommandError(f"Capacity rule for {variant} must define capacity.")

    lookup = {
        "product_variant": variant,
        "date_from": optional_date(rule_payload.get("date_from"), "date_from"),
        "date_to": optional_date(rule_payload.get("date_to"), "date_to"),
        "day_of_week": optional_day_of_week(rule_payload.get("day_of_week")),
        "slot_start_time": optional_time(
            rule_payload.get("start_time") or rule_payload.get("slot_start_time"),
            "start_time",
        ),
        "slot_end_time": optional_time(
            rule_payload.get("end_time") or rule_payload.get("slot_end_time"),
            "end_time",
        ),
    }

    defaults = {
        "capacity": capacity,
        "active": bool(rule_payload.get("active", True)),
    }
    existing = CapacityRule.objects.filter(**lookup)
    if existing.exists():
        existing.update(**defaults)
        stats["capacity_rules_updated"] += existing.count()
        return

    CapacityRule.objects.create(**lookup, **defaults)
    stats["capacity_rules_created"] += 1


def seed_alias(alias_payload, product, variant, stats):
    if not isinstance(alias_payload, dict):
        raise CommandError(f"Alias for {product} must be a mapping.")

    provider_code = require_string(alias_payload, "provider", f"{product} alias")
    provider, _created = Provider.objects.get_or_create(
        code=provider_code,
        defaults={
            "name": alias_payload.get("provider_name")
            or provider_code_to_name(provider_code),
            "active": True,
            "parser_key": provider_code,
        },
    )
    raw_product_name = require_string(
        alias_payload,
        "raw_product_name",
        f"{product} alias",
    )

    lookup = {
        "provider": provider,
        "raw_product_name": raw_product_name,
        "raw_option_name": string_or_blank(alias_payload.get("raw_option_name")),
        "provider_product_code": string_or_blank(
            alias_payload.get("provider_product_code")
        ),
        "provider_option_code": string_or_blank(
            alias_payload.get("provider_option_code")
        ),
    }
    defaults = {
        "canonical_product": product,
        "canonical_variant": variant,
        "confidence": Decimal(str(alias_payload.get("confidence", "1.00"))),
        "approved": bool(alias_payload.get("approved", True)),
    }
    _alias, created = ProductAlias.objects.update_or_create(
        **lookup,
        defaults=defaults,
    )
    increment(stats, "aliases", created)


def require_list(payload, key, context):
    value = payload.get(key)
    if not isinstance(value, list):
        raise CommandError(f"{context} must define a list named {key!r}.")
    return value


def require_string(payload, key, context):
    value = payload.get(key)
    if value is None or str(value).strip() == "":
        raise CommandError(f"{context} must define {key!r}.")
    return str(value).strip()


def string_or_blank(value):
    if value is None:
        return ""
    return str(value).strip()


def optional_positive_int(value, context):
    if value in {None, ""}:
        return None
    try:
        int_value = int(value)
    except (TypeError, ValueError) as exc:
        raise CommandError(f"{context} must be a positive integer.") from exc
    if int_value < 1:
        raise CommandError(f"{context} must be a positive integer.")
    return int_value


def optional_day_of_week(value):
    if value in {None, ""}:
        return None
    try:
        int_value = int(value)
    except (TypeError, ValueError) as exc:
        raise CommandError("day_of_week must be 0-6, where Monday is 0.") from exc
    if int_value not in range(7):
        raise CommandError("day_of_week must be 0-6, where Monday is 0.")
    return int_value


def optional_date(value, context):
    if value in {None, ""}:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise CommandError(f"{context} must use YYYY-MM-DD format.") from exc


def optional_time(value, context):
    if value in {None, ""}:
        return None
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return value
    try:
        return datetime.strptime(str(value), "%H:%M").time()
    except ValueError as exc:
        raise CommandError(f"{context} must use HH:MM 24-hour format.") from exc


def provider_code_to_name(provider_code):
    return provider_code.replace("_", " ").replace("-", " ").title()


def increment(stats, noun, created):
    suffix = "created" if created else "updated"
    stats[f"{noun}_{suffix}"] += 1
