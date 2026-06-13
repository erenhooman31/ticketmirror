# Workflows

These workflows describe functional behavior TicketMirror may implement. They are intentionally not visual specifications.

## Admin Configures A Tour Or Activity

Actor: admin.

Goal: create or update a canonical product and its schedule.

Flow:

1. Admin opens the admin area.
2. Admin selects Tours/Activities.
3. Admin opens an existing tour/activity or creates a new one.
4. Admin edits General fields: name, nickname/display label, category, active status, and display notes.
5. Admin opens Schedule.
6. Admin defines the current schedule with weekday time/capacity entries.
7. Admin optionally creates other schedules with start/end dates.
8. Admin sets duration.
9. Admin saves.

Expected outcome:

- Product is created or updated.
- Time slots create or update internal fixed-time product variants.
- Capacity rules are created for the schedule date range and weekday.
- Operators can use the configured product in bookings and capacity views.

Acceptance criteria:

- Operators and viewers cannot access product schedule setup.
- Admin changes are deterministic and repeatable.
- Time slots define operational variants; the UI does not expose a separate variants/options workflow.

## Operator Reviews Messages

Actor: operator.

Goal: scan booking events and act on the relevant booking.

Flow:

1. Operator opens the operations dashboard.
2. Operator scans message rows for new bookings, updates, cancellations, parser failures, and review items.
3. Operator clicks a booking-related message.
4. TicketMirror opens an in-page booking dialog.
5. Operator reviews booking, traveler, notes, and audit tabs.
6. Operator saves permitted edits or closes the dialog.

Expected outcome:

- The dashboard remains in context behind the dialog.
- Booking edits use existing audit-safe update services.
- Viewers can inspect but not mutate.

Acceptance criteria:

- Clicking a message does not require full-page navigation when JavaScript is available.
- Non-JavaScript fallback links to the booking detail page.
- Saved changes create a booking audit event with old and new values.

## Operator Uses Agenda

Actor: operator.

Goal: understand upcoming scheduled slots and capacity.

Flow:

1. Operator opens the operations dashboard.
2. Operator reviews agenda rows by day and time.
3. Operator sees product, slot, booked count, pending count, manual-review count, capacity, and remaining availability.
4. Operator clicks a slot.
5. TicketMirror opens the slot detail or calendar context for that slot.

Expected outcome:

- Capacity math remains consistent with capacity services.
- Canceled bookings are not counted as confirmed/pending capacity.
- Manual-review pax is displayed separately.

Acceptance criteria:

- Agenda rows use TicketMirror product and capacity data.
- Slot clicks preserve enough date/slot context to return to operations.

## Admin Maintains Seasonal Schedules

Actor: admin.

Goal: create future or historical schedules without changing current operations unexpectedly.

Flow:

1. Admin opens a tour/activity Schedule tab.
2. Admin reviews Current schedule.
3. Admin opens or creates an Other schedule with a start date and optional end date.
4. Admin edits weekday time/capacity entries.
5. Admin saves.

Expected outcome:

- New capacity rules apply only to the defined schedule date range.
- Current operational dates continue to use the schedule effective for those dates.

Acceptance criteria:

- Schedule date ranges are validated.
- End date cannot be before start date.
- Duplicate times within a weekday are rejected or normalized deterministically.
