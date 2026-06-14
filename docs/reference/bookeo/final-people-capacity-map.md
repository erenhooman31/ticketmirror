# Bookeo People Capacity Map

Inspection date: 2026-06-14

Source: authenticated Bookeo People tab for `Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR`.

No Bookeo mutations were submitted. Save and other page-level mutation controls were not clicked.

## Scoped Structure

Bookeo People page starts with:

```text
Input here the minimum and maximum number of people that a booking can be for.
```

Scoped section:

- `Number of people per booking`

Visible rows:

- `Total: Max.: 20 Min.: 1`
- `Adults: Max.: 20 Min.: 0 Default: 0`
- `Children: Max.: 20 Min.: 0 Default: 0`
- `Infants: Max.: 20 Min.: 0 Default: 0`

Each value is a native select with `Other...` where applicable.

Help text:

- Defaults apply to bookings created by staff, not customer-created bookings.
- Min/max constraints only affect customer-created bookings.
- The system ensures at least one person for each booking.

Page-level controls:

- `Save`
- `Cancel`

## TicketMirror Mapping

TicketMirror implements only the scoped assigned-capacity/people behavior:

- Total minimum people per booking -> `ActivityPeopleRule.min_people_per_booking`
- Total maximum people per booking -> `ActivityPeopleRule.max_people_per_booking`
- Assigned/default capacity -> `ActivityPeopleRule.default_capacity`
- Internal note -> `ActivityPeopleRule.capacity_note`

TicketMirror intentionally does not implement full participant detail policy, waiver timing, participant category pricing, or Bookeo customer/public booking complexity.

## Product Capacity Reference

From Schedule inspection:

- `Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR`: 250 seats per 11:00, 14:00, 19:00 slot.
- `1 Hours Bosphorus Tour GYG`: 250 seats at 17:00.
- `GYG 2 Hours Bosphorus Tour SL-(2-3)`: 250 seats per 14:00 and 19:00 slot.
- `gyg yacht`: capacity behavior not represented by fixed Current/Other schedule; treat as open/private-time inventory until separately modeled.

Capacity belongs on schedule slots; people-per-booking min/max is a booking party-size rule, not the slot capacity itself.
