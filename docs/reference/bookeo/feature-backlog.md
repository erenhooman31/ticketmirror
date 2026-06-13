# Feature Backlog

This backlog translates the observed Bookeo areas into TicketMirror feature candidates. These are not commitments until selected, scoped, and converted into implementation issues.

## Priority Guide

- P1: directly supports current TicketMirror booking operations, capacity visibility, review queues, or admin setup.
- P2: useful after core operations are stable.
- P3: out of scope for now, retained only as a reference.

## P1 Candidates

### Operations Home

Reference area: Bookeo home-like operator dashboard.

TicketMirror direction:

- Show recent booking, cancellation, update, parser, and review events.
- Show upcoming agenda slots grouped by date/time.
- Show product, provider, capacity, confirmed pax, pending pax, manual-review pax, canceled status, and remaining availability.
- Provide all/unread event filtering and short date ranges such as today, three days, and seven days.
- Open booking or slot details from rows without losing dashboard context.

Acceptance criteria:

- Given an operator opens the dashboard, recent booking events and upcoming slot capacity are visible.
- Given a viewer opens the dashboard, mutation commands are unavailable.
- Given a message references a booking, clicking it opens the TicketMirror booking detail or modal.
- Given an event is already read, unread filtering excludes it.
- Given no events exist, an empty state is shown.

### Schedule Calendar

Reference area: Bookeo calendar-like schedule workspace.

TicketMirror direction:

- Provide date navigation: previous day, next day, today, and date picker.
- Support category/product filters and a search box for booking identifier, provider reference, traveler name, or voucher code where permitted.
- Support compact and expanded slot display modes if both solve real operator tasks.
- Allow canceled visibility toggling.
- Show slot capacity, booked count, available count, blocked state, and manual-review indicators.
- Provide print/export only after data-masking rules are defined.

Acceptance criteria:

- Given an operator changes date, the slot list refreshes for that date.
- Given a search matches a booking, the related slot remains discoverable.
- Given canceled visibility is off, canceled bookings do not appear as active bookings or count toward active capacity.
- Given provider or search filters are applied, slot-wide capacity totals remain mathematically correct.

### Slot Detail

Reference area: calendar row or agenda row detail.

TicketMirror direction:

- Show a selected date/time/product slot with confirmed, pending, canceled, and review bookings.
- Show capacity rule source and remaining availability.
- Link each booking to the audit-safe booking detail screen.
- Provide a create-manual-booking entry only if that workflow is explicitly approved.

Acceptance criteria:

- Given a slot is opened, bookings are grouped by operational status.
- Given the slot has no bookings, the capacity summary still renders.
- Given a booking row is clicked, the operator can return to the same slot context.

### Booking Detail Modal Or Page

Reference area: clicking booking messages or calendar rows.

TicketMirror direction:

- Show booking fields, provider fields, participants, customer/contact data allowed by role, notes, raw email references, parser result, and audit history.
- Allow permitted edits through existing booking update services.
- Record all mutations as audit events.

Acceptance criteria:

- Given JavaScript is available, dashboard and calendar clicks may open an in-page detail.
- Given JavaScript is unavailable, links navigate to the booking detail page.
- Given a viewer opens a booking, fields are read-only.
- Given an operator saves allowed fields, old and new values are audited.

### Product And Schedule Administration

Reference area: settings area for tours/activities and schedule setup.

TicketMirror direction:

- Admins configure canonical products, provider aliases, internal display names, active state, duration, schedule names, weekday slots, seasonal date ranges, and capacity.
- Operators consume configured products but cannot modify schedule setup.
- Seasonal schedules should have explicit start/end dates and deterministic overlap rules.

Acceptance criteria:

- Given an admin creates a product schedule, generated slots appear in dashboard/calendar views.
- Given an invalid date range is entered, save is blocked with a field-level error.
- Given duplicate times exist on one weekday, the system rejects or normalizes them deterministically.
- Given an operator attempts admin setup access, access is denied.

### Customer Detail Requirements

Reference area: settings for collected customer and participant fields.

TicketMirror direction:

- Define which traveler/customer fields TicketMirror stores, displays, masks, imports, or ignores.
- Separate provider-supplied data from operator-entered corrections.
- Keep role-based visibility explicit for email, phone, country, participant count, and notes.

Acceptance criteria:

- Given a role lacks access to a personal field, the value is masked or omitted.
- Given parser data lacks an optional field, ingestion still succeeds.
- Given a required internal field is missing, the booking enters review rather than failing silently.

## P2 Candidates

### Customer Directory

Reference area: customer list and search.

TicketMirror direction:

- Provide search by traveler/contact name, email, phone, and provider reference where permitted.
- Provide alphabetical browsing only if the data volume justifies it.
- Support duplicate review/merge as an admin-only audited workflow.
- Import/export remains admin-only and must apply masking and purpose checks.

Acceptance criteria:

- Search respects role-based masking.
- Merge requires confirmation and records source/target records.
- Export is unavailable until an approved data-export policy exists.

### Waiting List Management

Reference area: settings for waitlist behavior.

TicketMirror direction:

- Track interest for full slots only if TicketMirror owns the operational follow-up workflow.
- Define waitlist mode, notification interval, max size, email/SMS templates, and opt-in records before implementation.

Acceptance criteria:

- A waitlist entry cannot affect confirmed capacity.
- Notifications are not sent without an explicit approved messaging integration.
- Removal and conversion to booking are audited.

### Closure Periods And Blocked Slots

Reference area: settings for business-wide closed periods and calendar blocked state.

TicketMirror direction:

- Admins define closed date ranges or blocked slots.
- Calendar and capacity services treat blocked slots differently from full slots.

Acceptance criteria:

- Closed periods prevent new internal bookings for affected slots.
- Existing bookings remain visible with warning context.
- Overlapping closures are rejected or merged deterministically.

### Pricing Seasons

Reference area: settings for effective-date price periods.

TicketMirror direction:

- Defer until TicketMirror handles internal pricing.
- If implemented, model effective periods separately from capacity schedules.

Acceptance criteria:

- Price seasons never change capacity counts.
- Effective ranges validate start/end and recurrence rules.

### Notifications And Message Templates

Reference area: settings for notifications, reminders, post-visit emails, and custom messages.

TicketMirror direction:

- Defer outbound customer messaging until email/SMS ownership is clear.
- Internal operator notifications may be considered for parser errors, review queues, and capacity risks.

Acceptance criteria:

- No external message is sent without explicit operator action or approved automation.
- Template edits are admin-only and versioned.
- Failed notifications create internal system events.

### Resources

Reference area: resource setup such as vehicles, guides, or equipment.

TicketMirror direction:

- Consider only if capacity must be constrained by guide, boat, vehicle, or shared inventory.

Acceptance criteria:

- Resource conflicts are visible before saving.
- Resource capacity and product capacity have deterministic precedence.

## P3 / Deferred References

### Public Booking And Marketing

Reference area: public booking links, promotions, vouchers, prepaid packages, reviews, social channels, campaigns, abandoned-booking follow-up, customer account area, memberships, and analytics.

Decision:

- Out of scope for TicketMirror unless the product direction expands beyond provider-email mirroring and operator tooling.

### Theme, Layout, Business Profile, Taxes, And Integrations

Reference area: brand/profile setup, localization, taxes, page styling, and third-party integrations.

Decision:

- Most of this is not needed for current TicketMirror operations.
- Keep localization/timezone and integrations as future technical considerations only.

### Waivers

Reference area: waiver templates and signed document collection.

Decision:

- Defer unless providers send waiver status that operators must track.
