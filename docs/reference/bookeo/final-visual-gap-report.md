# Final Bookeo Visual Gap Report

Audit date: 2026-06-14

Scope: Home; Schedule tab Current schedule, Other schedules, New/change schedule flow, Duration; People assigned capacity and number of people only; Calendar; Customers.

## Evidence

Bookeo live screenshots:

- `docs/reference/bookeo/bookeo-live/01-home-navigation-crop-2026-06-14.png`
- `docs/reference/bookeo/bookeo-live/02-schedule-tab-full-page-2026-06-14.png`
- `docs/reference/bookeo/bookeo-live/03-current-schedule-edit-time-modal-2026-06-14.png`
- `docs/reference/bookeo/bookeo-live/04-other-schedules-table-2026-06-14.png`
- `docs/reference/bookeo/bookeo-live/05-new-change-schedule-flow-modal-2026-06-14.png`
- `docs/reference/bookeo/bookeo-live/06-duration-section-2026-06-14.png`
- `docs/reference/bookeo/bookeo-live/07-people-tab-number-of-people-section-2026-06-14.png`
- `docs/reference/bookeo/bookeo-live/08-calendar-full-page-rows-2026-06-14.png`
- `docs/reference/bookeo/bookeo-live/09-calendar-row-state-2026-06-14.png`
- `docs/reference/bookeo/bookeo-live/10-calendar-card-state-boxes-2026-06-14.png`
- `docs/reference/bookeo/bookeo-live/11-calendar-empty-slot-detail-2026-06-14.png`
- `docs/reference/bookeo/bookeo-live/12-customers-list-redacted-2026-06-14.png`
- `docs/reference/bookeo/bookeo-live/13-customer-detail-redacted-2026-06-14.png`

TicketMirror before screenshots:

- `docs/reference/bookeo/ticketmirror-before/01-home-full-page.png`
- `docs/reference/bookeo/ticketmirror-before/02-settings-tours-scheduling-full-page.png`
- `docs/reference/bookeo/ticketmirror-before/03-current-schedule-edit-time-modal.png`
- `docs/reference/bookeo/ticketmirror-before/04-other-schedules-table.png`
- `docs/reference/bookeo/ticketmirror-before/05-new-change-schedule-flow-modal.png`
- `docs/reference/bookeo/ticketmirror-before/06-duration-section.png`
- `docs/reference/bookeo/ticketmirror-before/07-people-number-capacity-section.png`
- `docs/reference/bookeo/ticketmirror-before/08-calendar-full-page-rows.png`
- `docs/reference/bookeo/ticketmirror-before/09-calendar-row-state.png`
- `docs/reference/bookeo/ticketmirror-before/10-calendar-card-state.png`
- `docs/reference/bookeo/ticketmirror-before/11-calendar-slot-detail-state.png`
- `docs/reference/bookeo/ticketmirror-before/12-customers-list-empty.png`

TicketMirror after screenshots:

- `docs/reference/bookeo/ticketmirror-after/01-home-after.png`
- `docs/reference/bookeo/ticketmirror-after/02-home-booking-modal-after.png`
- `docs/reference/bookeo/ticketmirror-after/03-schedule-full-after.png`
- `docs/reference/bookeo/ticketmirror-after/04-current-schedule-edit-time-after.png`
- `docs/reference/bookeo/ticketmirror-after/05-new-change-schedule-after.png`
- `docs/reference/bookeo/ticketmirror-after/06-people-capacity-after.png`
- `docs/reference/bookeo/ticketmirror-after/07-calendar-rows-after.png`
- `docs/reference/bookeo/ticketmirror-after/08-calendar-boxes-after.png`
- `docs/reference/bookeo/ticketmirror-after/09-calendar-slot-detail-after.png`
- `docs/reference/bookeo/ticketmirror-after/10-customers-list-detail-after.png`

Exact schedule data proof screenshots:

- `docs/reference/bookeo/bookeo-live/02-schedule-tab-full-page-2026-06-14.png`
- `docs/reference/bookeo/exact-schedule-proof/ticketmirror-2-hours-bosphorus-cruise-boat-tour-in-istanbul-viator-transfer.png`
- `docs/reference/bookeo/exact-schedule-proof/ticketmirror-bosphorus-cruise-tour-in-istanbul-for-2-hours-viator.png`
- `docs/reference/bookeo/exact-schedule-proof/ticketmirror-2-hours-bosphorus-cruise-boat-tour-in-istanbul-viator.png`
- `docs/reference/bookeo/exact-schedule-proof/ticketmirror-2-hours-bosphorus-tour-sl-1.png`
- `docs/reference/bookeo/exact-schedule-proof/ticketmirror-gyg-2-hours-bosphorus-tour-sl-2-3.png`
- `docs/reference/bookeo/exact-schedule-proof/ticketmirror-istanbul-old-city-and-bosphorus-tour.png`
- `docs/reference/bookeo/exact-schedule-proof/ticketmirror-istanbul-two-continents-tour-by-bus-and-bosphorus-cruise.png`
- `docs/reference/bookeo/exact-schedule-proof/ticketmirror-istanbul-old-city-and-bosphorus-tour-gyg.png`
- `docs/reference/bookeo/exact-schedule-proof/ticketmirror-istanbul-two-continents-tour-by-bus-and-bosphorus-cruise-gyg.png`
- `docs/reference/bookeo/exact-schedule-proof/ticketmirror-1-hours-bosphorus-tour-viator.png`
- `docs/reference/bookeo/exact-schedule-proof/ticketmirror-1-hours-bosphorus-tour-gyg.png`
- `docs/reference/bookeo/exact-schedule-proof/ticketmirror-gyg-yacht.png`

## Resolved Mismatches

| Area | Bookeo behavior/structure | TicketMirror before | File/component responsible | Required fix | Status |
| --- | --- | --- | --- | --- | --- |
| Home messages populated state | Home has a two-panel Messages/Agenda structure with booking/event cards and agenda rows. | Before proof showed an empty Messages panel, so populated card structure could not be verified. | `apps/core/templates/core/dashboard.html`; local visual fixture data. | Added a synthetic local booking event for final proof and verified a populated message card without real PII. | verified |
| Home Agenda footer | Bookeo footer shows compact `Today`, `3 days`, `7 days`, `Print` controls. | TicketMirror showed extra `Previous`, `1 day`, `Next`, date picker, `Go`, and `Calendar` controls. | `apps/core/templates/core/dashboard.html` agenda footer. | Removed the extra footer controls from Home and kept the scoped Bookeo-like controls. | verified |
| Home booking modal raw/developer UI | Bookeo booking dialog exposes user-facing booking fields and action controls, not raw payload fields. | TicketMirror showed audit tab, slot type enum, JSON textareas, payment/price, raw provider import, full booking link, and disabled email controls. | `apps/core/templates/core/dashboard.html`. | Removed visible raw/internal sections and preserved values with hidden inputs for save behavior. | verified |
| Schedule tab label | Bookeo labels the tab `Schedule`. | TicketMirror labeled it `Scheduling`. | `apps/bookings/templates/bookings/tour_activity_detail.html`. | Renamed visible tab to `Schedule` while keeping the existing internal query value. | verified |
| Current schedule grid/table styling | Bookeo current schedule and other schedule tables use compact blue header rows. | TicketMirror used pale table headers and looser rows. | `apps/core/templates/base/base.html`. | Updated scoped schedule grid and other-schedule table headers/row density to match TicketMirror's Bookeo-like internal language. | verified |
| Current schedule edit time modal | Bookeo existing time opens `Edit tour` with Day, Start, Seats, and right action rail Save/Cancel/Delete. | TicketMirror before used footer actions; add-time state could show `Edit new tour` without Delete. | `apps/bookings/templates/bookings/tour_activity_detail.html`; existing `edit_slot` click path. | Existing slot click now verifies `Edit tour`, initialized time, seats, and right action rail with Delete. | verified |
| New/change schedule modal | Bookeo opens Copy schedule in a larger shell with right action rail and current schedule copy source first. | TicketMirror before defaulted to empty schedule and used footer actions. | `apps/bookings/templates/bookings/tour_activity_detail.html`. | Defaulted to the first copy source when present and moved Ok/Cancel into the right rail. | verified |
| Duration section | Bookeo duration controls are inline: days, hours, minutes. | TicketMirror stacked controls vertically and had a local section Save. | `apps/bookings/templates/bookings/tour_activity_detail.html`; `apps/core/templates/base/base.html`. | Rendered duration controls inline and moved Save/Cancel to the page action rail. | verified |
| People scoped controls | Scoped request only includes number of people and assigned capacity. | TicketMirror included an extra `Note` textarea. | `apps/bookings/templates/bookings/tour_activity_detail.html`. | Removed the unscoped Note row and moved Save/Cancel to the page action rail. | verified |
| Calendar rows/boxes/detail | Bookeo has rows, boxes/card state, and slot detail interaction. | TicketMirror already had rows/boxes/detail, but before proof used an empty local booking state. | `apps/bookings/templates/bookings/daily.html`; `apps/bookings/templates/bookings/slot_detail.html`. | Final proof captures rows, boxes, and slot detail with local sample data. No code change required. | verified |
| Customers list/detail | Bookeo customer screenshots contain PII and were redacted. | TicketMirror before proof had no customer rows because local DB had no bookings. | `apps/core/templates/core/customers.html`; local visual fixture data. | Final proof uses synthetic local customer bookings and captures list/detail behavior. No code change required. | verified |
| Schedule seed data parity | Bookeo product schedule rows use exact product-specific current schedule dates, times, seats, duration, and real Other schedule date/name rows. | TicketMirror seeded generic current dates and fake blank `Other schedule (unconfirmed)` rows, so the visual grid could not match Bookeo data. | `apps/bookings/management/commands/seed_bookeo_products.py`; `tests/test_seed_products.py`. | Replaced placeholder schedule seeding with per-product Bookeo current schedule dates, daily times, seat counts, durations, and real Other schedule rows; removed fake/duplicate Other schedules on reseed; added tests for exact transfer grid, real Other schedule rows, durations, capacity, and fake-row absence. | verified for captured same-product proof; manual-confirmation flags documented in `docs/reference/bookeo/exact-product-schedule-data.md` |

## Out Of Scope By Request

These Bookeo sections remain intentionally absent or unimplemented: Additional times, Marketing, Price, Accept/deny, Resources, Options, Messages, Reports, Public booking, Payments, and unscoped People category rows such as Adults/Children/Infants.

Primary navigation remains only Home, Calendar, Customers, Settings.

## Verification

- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `pytest` (`110 passed`)
- `ruff check .`
- `black --check .`
- Final screenshots in `docs/reference/bookeo/ticketmirror-after/` verify the scoped visual states.
