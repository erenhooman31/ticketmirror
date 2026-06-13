# Bookeo-Inspired Activity Seeds

TicketMirror seeds the 12 inspected Bookeo products as internal
`TourActivity` records. Bookeo is used only as functional inspiration; do not
copy Bookeo branding, UI text, icons, CSS, or trade dress.

Run after migrations:

```bash
python manage.py seed_bookeo_products
```

The command is idempotent. It creates or updates:

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
