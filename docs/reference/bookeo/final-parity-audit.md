# Final Scoped Parity Audit

Audit date: 2026-06-14

Bookeo reference screenshots saved locally:

- `docs/reference/bookeo/screenshots/bookeo-home-2026-06-14.png`
- `docs/reference/bookeo/screenshots/bookeo-calendar-2026-06-14.png`
- `docs/reference/bookeo/screenshots/bookeo-customers-2026-06-14.png`

TicketMirror verification screenshots saved locally:

- `docs/reference/bookeo/screenshots/ticketmirror-home-2026-06-14.png`
- `docs/reference/bookeo/screenshots/ticketmirror-calendar-rows-2026-06-14.png`
- `docs/reference/bookeo/screenshots/ticketmirror-calendar-boxes-2026-06-14.png`
- `docs/reference/bookeo/screenshots/ticketmirror-customers-2026-06-14.png`
- `docs/reference/bookeo/screenshots/ticketmirror-schedule-2026-06-14.png`
- `docs/reference/bookeo/screenshots/ticketmirror-people-2026-06-14.png`

The screenshot files are local verification artifacts and are not committed because the Bookeo Customers capture includes real customer contact data.

## Scope

Implemented and audited:

- Home
- Schedule tab: Current schedule, Other schedules, Duration
- People tab: assigned capacity / number of people per booking only
- Calendar
- Customers

Explicitly excluded:

- Additional times
- Marketing
- Price
- Accept/deny
- Resources
- Options
- Messages
- Reports beyond existing print/export links
- Public booking
- Payments

## Home

Bookeo:

- Two-panel Home with `MESSAGES` and `AGENDA`.
- Message rows show event, customer, product, time, and party count.
- Agenda rows show time, product, booked count, available count, and plus action.
- Footer controls include All/Unread/Mark all as read and Today/3 days/7 days/Print.

TicketMirror:

- Matches the two-panel structure.
- Messages panel supports message rows and empty state.
- Agenda rows show time, activity, booked/pending/review/available counts.
- Date/range controls work and slot rows open slot detail.
- Primary nav remains only Home, Calendar, Customers, Settings.

Intentional differences:

- New booking plus action is visual/slot-detail oriented only; full manual booking creation is out of scope.
- Marketing nav is omitted by requirement.

Status: complete for scoped behavior.

## Schedule

Bookeo fixed-tour products:

- Current schedule weekly grid, Monday-Sunday.
- Plus per day opens `Edit new tour`.
- Time rows open `Edit tour`.
- Time modal fields: Day, Start, Seats, Save, Cancel, Delete.
- `Copy...` opens weekday copy modal.
- `Change seats for all times` opens Seats modal.
- Other schedules table columns: Start, End, Name.
- Existing other schedule row opens full schedule editor with Name, Start date, End date, Schedule grid, Copy schedule, Save, Cancel, Delete.
- `New/change schedule` opens copy-source modal, then schedule editor.
- Duration uses days/hours/minutes selects.

TicketMirror:

- Current schedule grid implemented with add/edit/delete time flow.
- Day-specific delete removes only that weekday from a multi-day slot.
- Copy days and change-all-seats modals implemented.
- Other schedules table uses Start, End, Name and row-click edit.
- New/change schedule no longer creates blank/random schedules; it opens a copy-source step and requires name/start before save.
- Existing other schedules can be edited or deleted.
- Duration form saves days/hours/minutes to current schedule slots.
- Additional times removed from visible Scheduling tab because it is excluded in this request.

Intentional differences:

- Bookeo yacht uses `Time settings`, not Current/Other schedules. TicketMirror keeps yacht unresolved/open-time behavior out of Current/Other parity until its product model is separately defined.

Status: complete for fixed-tour scoped behavior.

## People

Bookeo:

- `Number of people per booking`.
- Total max/min controls.
- Adults/Children/Infants max/min/default controls.
- Page-level Save/Cancel.

TicketMirror:

- Implements scoped total max/min and assigned/default capacity.
- Keeps capacity on schedule slots and party-size limits in people rules.
- Does not implement participant category pricing/details, waivers, or public-booking participant collection.

Status: complete for assigned-capacity scope.

## Calendar

Bookeo:

- Mini-calendar, category tree, customer/booking search.
- Rows/Boxes/Canceled controls.
- Day navigation.
- Slot blocks show time, product, booked/blocked/available.
- Legend for booking/capacity states.
- iCal and Print output actions.

TicketMirror:

- Mini-calendar, date navigation, range links, search, activity/category/provider filters.
- Rows and Boxes views implemented.
- Canceled visibility filter implemented.
- Slot rows/cards show capacity and booking counts.
- Clicking rows/cards opens slot detail.
- Print maps to daily manifest CSV.

Intentional differences:

- iCal is not implemented; external calendar feed is outside the scoped app request.
- Category tree is represented as filters rather than a collapsible tree, preserving function without Bookeo trade dress.

Status: complete for scoped operational behavior.

## Customers

Bookeo:

- Search by customer name/email.
- Alphabet filter.
- Pagination.
- Two-column directory cells with initials, name, email, phone.
- Customer cells open profile/detail.

TicketMirror:

- Search by customer/contact/reference/product/provider data.
- Alphabet filter.
- Two-column directory cards with initials, name, email, phone.
- Selected customer details show contact, language, booking count, total people.
- Booking history rows link to booking detail.
- Running local dev database had zero bookings, so browser screenshot shows empty state; tests cover populated rows.

Intentional differences:

- No bulk Bookeo customer PII import was committed. TicketMirror mirrors customer records from local booking data. Real Bookeo PII import/export/merge requires a separate privacy/audit flow.
- Import/export/merge/customer flags/waivers/membership are deferred as out of scope.

Status: complete for scoped booking-backed customer behavior.

## Verification Notes

Manual browser verification used `http://127.0.0.1:8000`:

- Home loaded with scoped primary nav and two-panel layout.
- Calendar loaded in rows and boxes modes.
- Customers loaded with search/alphabet/directory empty state.
- Schedule loaded current grid, other schedules, and duration.
- People loaded number-of-people/assigned-capacity controls.

Automated checks are recorded in the final task response.
