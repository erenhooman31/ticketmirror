# Bookeo Home Click Map

Inspection date: 2026-06-14

Source: authenticated Bookeo Home at `book_home.html`.

Local screenshot saved at `docs/reference/bookeo/screenshots/bookeo-home-2026-06-14.png`.
Screenshots from the live Bookeo account are kept local because the Customers view includes real contact data.

No Bookeo mutations were submitted. Sign out, save, email, and destructive actions were not clicked.

## Structure

Bookeo Home is a two-panel operations page:

- `MESSAGES` on the left.
- `AGENDA` on the right.
- Footer controls below both panels.

Primary Bookeo nav contains Home, Calendar, Customers, Marketing, and Settings. TicketMirror intentionally keeps only Home, Calendar, Customers, and Settings per project scope.

## Messages

Visible message rows include:

- status icon
- timestamp such as `Today, 12:42`
- event label such as `New booking`, `Booking changed`, or `Booking canceled`
- customer name
- tour date/time
- product label
- party count text
- booking number for canceled/change messages where present

Click behavior:

- Message rows are clickable detail entries.
- Booking-related messages open a booking/detail workflow.
- Footer `All` and `Unread` filter message visibility.
- `Mark all as read` is a mutation boundary and was not submitted.

TicketMirror parity:

- Home uses the same two-panel Messages/Agenda structure.
- Message rows link to booking detail or modal detail when booking data exists.
- Empty state remains `No messages yet.`

## Agenda

Visible agenda rows include:

- day label, usually `Today`
- time
- product/tour label
- booked count
- available count
- plus icon for new booking

Bookeo footer controls:

- `Today`
- `3 days`
- `7 days`
- `Print`

Click behavior:

- Agenda slot/detail rows open slot details.
- Plus icon is a new-booking entry point; not implemented in TicketMirror because public booking/manual booking creation is out of current scope.
- `Print` is a read-only output action.

TicketMirror parity:

- Home has Previous, Today, 1 day, 3 days, 7 days, Next, date Go, Calendar, and Print.
- Rows show booked/pending/review/available capacity using schedule capacity data.
- Slot rows open TicketMirror slot detail.

## Skipped

- Bookeo `Sign out`: session mutation.
- `Mark all as read`: mutation.
- New booking plus action: booking creation is outside scoped implementation.
- Any email/send/save/delete action: external or destructive mutation.
