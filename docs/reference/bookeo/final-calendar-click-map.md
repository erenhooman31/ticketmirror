# Bookeo Calendar Click Map

Inspection date: 2026-06-14

Source: authenticated Bookeo Calendar at `book_viewSchedules.html`.

Local screenshot saved at `docs/reference/bookeo/screenshots/bookeo-calendar-2026-06-14.png`.
Screenshots from the live Bookeo account are kept local because the Customers view includes real contact data.

No Bookeo mutations were submitted. New booking, save, delete, and sign-out actions were not clicked.

## Structure

Bookeo Calendar has:

- left mini-calendar for month/day navigation
- left category tree with `Group tours` and nested `Boat`
- main date header: `Group tours - Sunday, 14 June 2026`
- search field with placeholder `Customer name, booking number or voucher code`
- view controls: `Rows`, `Boxes`, `Canceled`
- previous-day and next-day controls
- slot capacity blocks
- legend: `No bookings`, `Some bookings`, `Fully booked`, `Blocked`
- footer actions: `iCal`, `Print`

## Mini Calendar

Controls inspected:

- previous/next month arrows
- `Today`
- individual day cells
- `Select date`

Behavior:

- Day/month controls navigate calendar date.
- Selected day changes the main schedule date.

TicketMirror parity:

- TicketMirror Calendar includes a mini-calendar, previous/next month links, active day styling, and date field.

## Main Calendar Controls

Controls inspected:

- Search field: filters by customer name, booking number, or voucher code.
- `Rows`: shows tours as dense rows.
- `Boxes`: shows tours as slot blocks.
- `Canceled`: toggles canceled tour visibility.
- Previous/next day controls move the selected date.
- `Print`: read-only output action.
- `iCal`: read-only subscription/export action; intentionally not implemented because external calendar feed is outside scope.

TicketMirror parity:

- Calendar search covers traveler name, phone, email, and provider references.
- Rows view is the default operational table.
- Boxes view is implemented as compact slot cards.
- Canceled visibility is represented by the existing `Show canceled` filter and a visible `Canceled` mode control.
- Print maps to the existing manifest CSV export.

## Slot Blocks

Bookeo row/box entries show:

- time
- product name
- booked count
- blocked count when present
- available count
- plus icon for new booking

Examples observed on 2026-06-14:

- `11:00`, `VIATOR 2H`, `9 booked`, `241 available`
- `17:00`, `VIATOR 1 SAAT`, `24 booked, 2 blocked`, `224 available`
- `19:00`, `GYG - 2 SAAT SL-(2-3)`, `11 booked`, `239 available`

TicketMirror parity:

- Calendar rows and boxes show time, activity, confirmed/pending/manual/canceled counts, capacity, remaining, and status.
- Clicking a row or capacity block opens slot detail.
- Blocked/canceled data is represented in capacity services and filters.

## Skipped

- New booking plus icons: booking creation is out of current scope.
- `iCal`: not implemented intentionally.
- Mutating booking/detail save actions: not submitted.
- Marketing/public booking/payment/report flows: out of scope.
