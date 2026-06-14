# Home Agenda Exact Map

Inspection date: 2026-06-14

Scope: Bookeo Home -> Agenda only. Bookeo was inspected read-only; no save, edit, delete, create, publish, or unpublish action was used.

## Bookeo Agenda Visual Structure

- Home is a two-column operational page. Agenda is the right panel with a blue `AGENDA` header.
- Agenda rows are grouped by date header.
- Single-day view uses `Today`.
- 3-day view uses `Today`, `Tomorrow`, then an explicit date such as `Tuesday, 16 June`.
- 7-day view stacks seven date groups from today through the sixth following day.
- Slot rows are dense, full-width cards, about one compact line of main text plus capacity text.
- Empty slot rows use a white card style.
- Rows with bookings use a green card style.
- Rows show a small left icon, then `time - product/tour`, then capacity text, with a green plus icon aligned at the right edge.

## Bookeo Agenda Controls

- Footer controls are `Today`, `3 days`, `7 days`, and `Print`.
- `Today` refreshes the Agenda to one day.
- `3 days` refreshes the Agenda to three grouped days.
- `7 days` refreshes the Agenda to seven grouped days.
- `Print` opens a separate Bookeo print URL: `bookprint_printUpcomingBookings.html`.
- No previous/next date controls were visible inside Agenda.

## Bookeo Row/Card Fields

Observed row text pattern:

- `8:15 - VIATOR-TWO CONTINENTS`
- `0 booked, 50 available`
- `17:00 - GYG - 1 Hours`
- `13 booked, 2 blocked, 235 available`

Fields shown:

- Start time without slot-type suffix.
- Product/tour name.
- Booked count.
- Blocked count when applicable.
- Available count.
- Right-side plus icon for starting a new booking in that slot.

Fields not shown in the Agenda row:

- Internal status codes.
- Raw parser fields.
- Separate pending/manual-review counters.
- Provider import metadata.
- Customer email/phone.

## Bookeo Click Behavior

- Clicking an empty row opens an in-page slot popup without navigating away from Home.
- Clicking a booked row opens the same slot popup with booking entries in the Bookings tab.
- The slot popup includes slot fields for time, seats, private flag, tabs for `Bookings`, `Access`, and `Notes`, and action buttons `Save`, `Cancel`, `New`, `Block`, and `Print`.
- Empty slots show `There are no bookings`.
- Clicking the green plus icon opens a `New booking` popup prefilled for the selected slot. This was canceled without saving.

## TicketMirror Mismatch List

- Before: Agenda rows linked directly to slot pages instead of opening a Home popup.
- Before: Agenda row text exposed TicketMirror-specific pending/review counters.
- Before: Agenda used Calendar slot labels such as `Full day`/`Fixed time` in the Agenda time column.
- Before: Agenda sorting could be activity/string oriented rather than Bookeo's clock-time order.
- Before: Product-matched review bookings did not have a Bookeo-aligned warning surface in Agenda.
- Before: Product-mismatch review bookings could be counted if attached to a slot.
- Before: GELMEDI visibility/counting behavior was not Agenda-specific.

## Required Fixes Implemented

- Agenda rows now open a Home slot popup.
- Rows use the Bookeo-style text shape: `time - product`, then `booked, available`.
- Agenda time labels are clock-only and do not include slot type.
- Agenda rows are sorted by numeric time, then title.
- Range controls remain `Today`, `3 days`, `7 days`, `Print`; previous/next controls are not introduced.
- Date grouping labels follow Bookeo structure: `Today`, `Tomorrow`, or `Weekday, day Month`.
- Product-mismatch review bookings are excluded from Agenda rows and slot popup booking lists.
- Product-matched manual-review/pending bookings remain visible and add a warning marker.
- GELMEDI bookings remain visible in the slot popup but do not count toward active capacity.
- GELDI and SONRA GELECEK attendance states remain visible in slot booking entries.
- Booking edits continue creating Home Messages and Agenda reflects updated traveler/status/capacity on refresh.

## Visual Proof

| Proof | File |
|---|---|
| Bookeo Agenda today | `docs/reference/bookeo/final-pass/bookeo-home-agenda-today-2026-06-14.png` |
| Bookeo Agenda 3 days | `docs/reference/bookeo/final-pass/bookeo-home-agenda-3-days-2026-06-14.png` |
| Bookeo Agenda 7 days | `docs/reference/bookeo/final-pass/bookeo-home-agenda-7-days-2026-06-14.png` |
| TicketMirror Agenda before | `docs/reference/bookeo/final-pass/ticketmirror-home-agenda-before-2026-06-14.png` |
| TicketMirror Agenda after | `docs/reference/bookeo/final-pass/ticketmirror-home-agenda-after-2026-06-14.png` |

## Final PASS/FAIL Table

| Requirement | Result |
|---|---|
| Same Agenda placement and structure | PASS |
| Today / 3 days / 7 days / Print controls | PASS |
| Row/card density and capacity text | PASS |
| Date grouping behavior | PASS |
| Booking/slot row click opens Home popup | PASS |
| Empty slot state | PASS |
| Product-matched needs-review booking visible with warning | PASS |
| Product-mismatch booking excluded from Agenda | PASS |
| GELDI visible as attended | PASS |
| GELMEDI excluded from active capacity | PASS |
| SONRA GELECEK remains visible | PASS |
| Booking edits create Home Messages and update Agenda on refresh | PASS |
| No raw/developer Agenda labels | PASS |

