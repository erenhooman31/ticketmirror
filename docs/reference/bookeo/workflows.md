# Workflows

These workflows describe TicketMirror behavior inspired by the observed Bookeo operator surfaces. They are intentionally functional and do not specify Bookeo styling, wording, icons, or layout.

## Operator Reviews The Day

Actor: operator.

Goal: understand what changed and what is upcoming.

Flow:

1. Operator opens the TicketMirror dashboard.
2. Operator reviews recent booking events, cancellations, changes, parser events, and manual-review items.
3. Operator filters between all events and unread events.
4. Operator changes the agenda range between today and short future windows.
5. Operator clicks an event or slot row.
6. TicketMirror opens the relevant booking or slot context.

Expected outcome:

- The operator can triage the day without leaving the dashboard.
- Read/unread state and event filters do not affect booking data.
- Slot capacity numbers match the capacity service.

Acceptance criteria:

- Given events exist, they are ordered with newest or most urgent first according to the screen definition.
- Given an event references a booking, opening it preserves a return path to the dashboard.
- Given a parser failure exists, it is visible as an operational event without exposing unsafe raw content by default.

## Operator Uses Calendar To Investigate Capacity

Actor: operator.

Goal: inspect availability and booking load for a date or product.

Flow:

1. Operator opens the schedule calendar.
2. Operator selects a date with previous, next, today, or date-picker controls.
3. Operator filters by product/category or searches for a booking reference.
4. Operator toggles canceled visibility when needed.
5. Operator opens a slot.
6. TicketMirror shows booking groups and capacity summary for that slot.

Expected outcome:

- Operators can answer whether a product/time is full, open, blocked, or in review.
- Canceled bookings remain available for audit but do not count as active capacity.
- Filters narrow displayed records without corrupting slot totals.

Acceptance criteria:

- Given a product filter is applied, unrelated rows are hidden.
- Given a search matches one booking, its slot context remains visible.
- Given a slot is blocked, it is differentiated from a full slot.

## Operator Opens A Booking From Context

Actor: operator or viewer.

Goal: inspect or update one booking.

Flow:

1. User opens a booking from dashboard, calendar, slot detail, or search.
2. TicketMirror shows booking summary, provider reference, product, date/time, participants, contact fields allowed by role, notes, parser source, and audit trail.
3. Viewer reviews read-only data.
4. Operator edits permitted operational fields.
5. TicketMirror validates and saves through audit-safe services.

Expected outcome:

- Booking context is reachable from multiple operational screens.
- Role permissions are consistent across entry points.
- Mutations are audited with old and new values.

Acceptance criteria:

- Given a viewer opens a booking, save controls are unavailable.
- Given an operator changes an allowed field, the audit trail records the change.
- Given validation fails, no partial update is saved.

## Admin Configures Products And Schedules

Actor: admin.

Goal: define the operational products and capacity rules used by operators.

Flow:

1. Admin opens product administration.
2. Admin creates or edits a canonical product.
3. Admin configures internal display name, provider aliases, active state, duration, and operational notes.
4. Admin defines weekday slots with time and capacity.
5. Admin optionally creates seasonal schedules with start/end dates.
6. Admin saves.
7. Operators see the resulting slots in dashboard and calendar views.

Expected outcome:

- Product setup remains admin-only.
- Schedule changes are deterministic and traceable.
- Operators use configured products but do not modify setup.

Acceptance criteria:

- Given a schedule has overlapping effective ranges, save is rejected or a deterministic precedence rule applies.
- Given capacity changes affect future slots, the audit event records the admin and changed values.
- Given a product is inactive, it is hidden from normal operator creation flows but historical bookings remain visible.

## Admin Manages Operational Field Requirements

Actor: admin.

Goal: decide which customer, participant, and provider fields TicketMirror stores and shows.

Flow:

1. Admin opens field requirement settings.
2. Admin reviews standard customer and participant fields.
3. Admin marks fields as ignored, optional, required for review, or required for manual entry.
4. Admin saves.
5. Ingestion and booking screens apply the new rules.

Expected outcome:

- TicketMirror keeps data collection intentional.
- Missing provider data creates review work only when the field is operationally required.
- Sensitive fields remain controlled by role permissions.

Acceptance criteria:

- Given a required operational field is missing, ingestion creates a review flag.
- Given an optional field is missing, booking creation continues.
- Given a role cannot view a field, it remains masked everywhere.

## Admin Reviews Deferred Platform Areas

Actor: admin or product owner.

Goal: decide whether non-core areas should become TicketMirror scope.

Flow:

1. Product owner reviews deferred references: public booking, marketing, customer accounts, memberships, payments, vouchers, waivers, taxes, and third-party integrations.
2. Product owner records whether each area is rejected, deferred, or accepted for discovery.
3. Accepted areas receive a new TicketMirror-specific reference document before implementation.

Expected outcome:

- TicketMirror does not accidentally expand into a public booking or marketing platform.
- Deferred features remain visible but do not distract from operator workflows.

Acceptance criteria:

- No P3 item is implemented without a separate accepted scope.
- Accepted discovery items include permissions, data ownership, external transmission risks, and testable acceptance criteria.
