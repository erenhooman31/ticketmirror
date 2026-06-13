# Feature Backlog

This backlog captures Bookeo-inspired operational capabilities for TicketMirror. Items here are not commitments until they are scoped, accepted, and converted into implementation tasks.

## Evaluation Criteria

Each candidate feature should answer:

- Which TicketMirror user role needs this?
- Which existing models and services support it?
- What new data, if any, is required?
- Does it affect booking capacity, audit history, parser behavior, or permissions?
- Can it be tested without real provider credentials or personal data?

## Candidate Features

### Admin Tour/Activity Setup

Admin users manage canonical tours and activities from the admin area.

Relevant sections:

- General: product name and display label.
- Schedule: current weekly schedule, other schedules, duration, slot capacities.

Acceptance direction:

- Product setup is not exposed as a normal operator dashboard feature.
- Time slots define internal operational variants.
- Operators use configured products; admins maintain them.

### Operations Home

Operators see a split operational workspace with recent messages and agenda/capacity rows.

Acceptance direction:

- Messages show booking, cancellation, update, parser, and review events.
- Agenda rows show date/time, product, capacity, booked/pending/review counts, and remaining availability.
- Clicking a booking message opens an in-page booking dialog.

### Booking Dialog

Operators can inspect and edit a booking without leaving the operations workspace.

Acceptance direction:

- Dialog shows booking, traveler/contact, provider notes, and audit history.
- Editable fields submit through existing audit-safe booking update services.
- Viewers see read-only data.
- Operators/admins can save permitted fields.

### Calendar Workspace

Operators scan capacity across one or more days.

Acceptance direction:

- Date navigation supports previous, today, next, and range toggles.
- Filters include category, product, provider, text search, canceled visibility, and manual-review visibility.
- Capacity math remains slot-wide even when provider/search filters are applied.

### Schedule Maintenance

Admins maintain weekly and seasonal schedules.

Acceptance direction:

- Current schedule shows a weekday grid of time/capacity slots.
- Other schedules show effective date ranges and names.
- Adding/editing/deleting a time slot updates capacity rules deterministically.
- Duration applies to generated time-slot variants.

## Not In Scope Unless Explicitly Requested

- Public booking engine.
- Payment collection.
- Marketing pages.
- Customer self-service account portal.
- Bookeo API, scraping, or synchronization.
- Copying Bookeo visual identity, CSS, icons, copy, or branding.
