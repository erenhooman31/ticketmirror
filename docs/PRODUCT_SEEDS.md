# Bookeo-Inspired Activity Seeds

TicketMirror has a safe production seed for the known Bookeo/local activity
families. Bookeo is used only as functional inspiration; do not copy Bookeo
branding, UI text, icons, CSS, or trade dress.

## Production Activity Seed

Run after migrations:

```bash
python manage.py seed_bookeo_activities
```

This command is safe to rerun. It creates missing canonical `TourActivity`
records and missing `ProviderAlias` rows from repository evidence, but it does
not delete anything and does not sync from Bookeo live. It does not create or
replace schedules, slots, bookings, aliases, or review queue data that operators
have already configured.

Canonical activities seeded:

- Bosphorus Cruise
- Istanbul Old City and Bosphorus Tour
- Istanbul Two Continents Tour
- Yacht Experience

Provider aliases are seeded for the inspected Viator and GetYourGuide raw
product names documented under `docs/reference/bookeo/product-inspection/`.

The Coolify startup command currently runs checks, migrations, collectstatic,
and initial admin creation. The activity seed is intentionally not wired into
startup; run it manually after deployment until the team explicitly agrees to
automate it.

## Development Product Seed

The older development seed creates the 12 inspected Bookeo products as internal
`TourActivity` records with schedules and slots:

Run after migrations:

```bash
python manage.py seed_bookeo_products
```

This command is useful for local schedule/capacity fixture setup. It creates or
updates:

- providers for Viator and GetYourGuide
- one `TourActivity` for each inspected Bookeo product
- a current and other `ActivitySchedule` for every activity
- `ActivityScheduleSlot` rows where inspected times and capacity were visible
- one `ActivityPeopleRule` per activity
- one `ProviderAlias` per inspected provider product

Ambiguous inspected items are marked with
`ProviderAlias.needs_manual_confirmation=True`. This includes transfer timing,
SL-1 / SL-(2-3) meaning, shared inventory assumptions, future seasonal times,
and the yacht capacity/schedule special case.

Deprecated wrappers:

```bash
python manage.py seed_defaults
python manage.py seed_products
```

Both currently delegate to `seed_bookeo_products` so older setup notes fail
softly without recreating the removed product/variant/capacity-rule schema.
