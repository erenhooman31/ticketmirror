import json
from datetime import time

import pytest
from django.core.management import call_command

from apps.bookings.models import CapacityRule, Product, ProductAlias, ProductVariant


def write_seed_file(tmp_path):
    seed_path = tmp_path / "products.json"
    seed_path.write_text(
        json.dumps(
            {
                "products": [
                    {
                        "canonical_name": "Bosphorus Sightseeing Cruise",
                        "category": "Cruise",
                        "variants": [
                            {
                                "variant_name": "Morning fixed slot",
                                "slot_type": "fixed_time",
                                "duration_minutes": 90,
                                "default_capacity": 80,
                                "slots": ["10:00", "12:00"],
                                "aliases": [
                                    {
                                        "provider": "getyourguide",
                                        "raw_product_name": (
                                            "Istanbul: Guided Bosphorus "
                                            "Sightseeing Cruise + Audio Guide"
                                        ),
                                        "provider_product_code": "GYG-BOS-CRUISE",
                                        "provider_option_code": "MORNING",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return seed_path


@pytest.mark.django_db
def test_seed_products_command_creates_products(tmp_path):
    seed_path = write_seed_file(tmp_path)

    call_command("seed_products", "--file", str(seed_path))

    product = Product.objects.get(canonical_name="Bosphorus Sightseeing Cruise")
    variant = ProductVariant.objects.get(
        product=product,
        variant_name="Morning fixed slot",
    )

    assert product.category == "Cruise"
    assert variant.slot_type == ProductVariant.SlotType.FIXED_TIME
    assert variant.duration_minutes == 90
    assert variant.default_capacity == 80


@pytest.mark.django_db
def test_seed_products_command_is_idempotent(tmp_path):
    seed_path = write_seed_file(tmp_path)

    call_command("seed_products", "--file", str(seed_path))
    call_command("seed_products", "--file", str(seed_path))

    assert Product.objects.count() == 1
    assert ProductVariant.objects.count() == 1
    assert ProductAlias.objects.count() == 1
    assert CapacityRule.objects.count() == 2


@pytest.mark.django_db
def test_seed_products_aliases_link_correctly(tmp_path):
    seed_path = write_seed_file(tmp_path)

    call_command("seed_products", "--file", str(seed_path))

    alias = ProductAlias.objects.get(provider__code="getyourguide")

    assert alias.canonical_product.canonical_name == "Bosphorus Sightseeing Cruise"
    assert alias.canonical_variant.variant_name == "Morning fixed slot"
    assert alias.raw_product_name.startswith("Istanbul: Guided Bosphorus")
    assert alias.provider_product_code == "GYG-BOS-CRUISE"
    assert alias.provider_option_code == "MORNING"
    assert alias.approved is True


@pytest.mark.django_db
def test_seed_products_capacity_rules_are_created(tmp_path):
    seed_path = write_seed_file(tmp_path)

    call_command("seed_products", "--file", str(seed_path))

    variant = ProductVariant.objects.get(variant_name="Morning fixed slot")
    slots = {
        rule.slot_start_time: rule.capacity
        for rule in CapacityRule.objects.filter(product_variant=variant)
    }

    assert slots == {
        time(10, 0): 80,
        time(12, 0): 80,
    }


@pytest.mark.django_db
def test_sample_products_yaml_loads():
    call_command("seed_products")

    assert Product.objects.filter(
        canonical_name="Bosphorus Sightseeing Cruise",
    ).exists()
    assert ProductVariant.objects.filter(
        product__canonical_name="Private Bosphorus Yacht",
        variant_name="Private group charter",
    ).exists()
    assert CapacityRule.objects.filter(
        product_variant__product__canonical_name="Historic Istanbul Full-Day Tour",
        capacity=25,
    ).exists()
