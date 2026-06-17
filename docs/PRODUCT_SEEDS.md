# Bookeo-Inspired Activity Seeds

TicketMirror has a safe production seed for the known Bookeo/local activity
families. Bookeo is used only as functional inspiration; do not copy Bookeo
branding, UI text, icons, CSS, or trade dress.

## Production Catalog Seed

Coolify runs the full Bookeo product catalog seed automatically after
migrations and before `collectstatic`:

```bash
python manage.py seed_bookeo_products
python manage.py repair_parsed_booking_display_fields
```

The seed is idempotent and creates:

- Bookeo plus configured direct OTA providers used by deterministic parsers
- one `TourActivity` for each inspected Bookeo product
- a current and other `ActivitySchedule` for every activity
- `ActivityScheduleSlot` rows where inspected times and capacity were visible
- one `ActivityPeopleRule` per activity
- approved canonical provider aliases, approved Bookeo `Tour:` aliases, and
  approved direct-OTA aliases confirmed from representative sample emails

Ambiguous inspected items are marked with
`ProviderAlias.needs_manual_confirmation=True` as an advisory flag only; approved
aliases still match automatically. This includes transfer timing, SL-1 /
SL-(2-3) meaning, shared inventory assumptions, future seasonal times, and the
yacht capacity/schedule special case. The command also prints alias coverage for
confirmed incoming sample product strings and reports sample strings that remain
unmapped.

`repair_parsed_booking_display_fields` then scans stored `RawEmail` records and
fills missing booking display fields or alias links without deleting raw emails,
bookings, booking events, or manual override values. It is safe to rerun after
new aliases are added.

Deprecated wrappers:

```bash
python manage.py seed_defaults
python manage.py seed_products
```

Both currently delegate to `seed_bookeo_products` so older setup notes fail
softly without recreating the removed product/variant/capacity-rule schema.
