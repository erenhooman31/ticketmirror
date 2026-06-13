# Product Seeds

Product seeds create and update canonical products, variants, capacity rules, and
provider aliases from `data/sample_products.yml`.

Run the seed command after migrations:

```bash
python manage.py seed_products
```

Use another YAML or JSON file when needed:

```bash
python manage.py seed_products --file data/my_products.yml
```

The command is idempotent. It updates products by `canonical_name`, variants by
`product + variant_name`, aliases by provider/template/code fields, and capacity
rules by variant/date/day/time fields.

## YAML Structure

```yaml
products:
  - canonical_name: "Bosphorus Sightseeing Cruise"
    category: "Cruise"
    variants:
      - variant_name: "Morning fixed slot"
        slot_type: "fixed_time"
        duration_minutes: 90
        default_capacity: 80
        slots:
          - "10:00"
          - "12:00"
        aliases:
          - provider: "getyourguide"
            raw_product_name: "Istanbul: Guided Bosphorus Sightseeing Cruise + Audio Guide"
            provider_product_code: "GYG-BOS-CRUISE"
            provider_option_code: "MORNING"
```

Supported `slot_type` values are `fixed_time`, `half_day`, `full_day`,
`open_time`, and `private_group`.

## Capacity Rules

For simple fixed-time products, list `slots` as `HH:MM` strings. Each slot creates
a capacity rule using the variant `default_capacity`.

Use mapping entries when capacity varies by date or weekday:

```yaml
slots:
  - start_time: "10:00"
    capacity: 80
    day_of_week: 5
  - start_time: "12:00"
    capacity: 60
    date_from: "2026-07-01"
    date_to: "2026-08-31"
```

`day_of_week` uses Django/Python numbering: Monday is `0`, Sunday is `6`.
`date_from` and `date_to` use `YYYY-MM-DD`.

For full-day or half-day products without fixed times, use `capacity_rules`:

```yaml
capacity_rules:
  - capacity: 25
```

If a variant has `default_capacity` but no `slots` or `capacity_rules`, the seed
command creates one general capacity rule for that variant.

## Aliases

Aliases preserve provider template labels and map incoming raw provider values to
canonical products and variants. Put aliases under a variant when the provider
template identifies a specific option. Product-level aliases are also supported
with a top-level `aliases` list under a product.

Use provider codes that match parser/provider codes, such as `getyourguide`,
`viator`, `tiqets`, `tripster`, `sputnik8`, `klook`, or `direct`.

Do not put real traveler names, phone numbers, emails, OAuth credentials, API
keys, or provider account secrets in seed files.
