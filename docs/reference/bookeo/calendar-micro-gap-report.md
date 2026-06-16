# Calendar Micro Gap Report

Date: 2026-06-14

Scope: Calendar only. Home remains COMPLETE_FOR_HOME and was not intentionally changed.

Bookeo live status: OPEN. The in-app browser had no existing Bookeo session. `https://signin.bookeo.com/` and `https://signin.bookeo.com/login` were blocked with `net::ERR_BLOCKED_BY_CLIENT`; `https://app.bookeo.com/` and `https://my.bookeo.com/` returned `Not found`. No authenticated Bookeo Calendar page could be inspected from scratch in this run.

iCal: explicitly out of scope.

## Micro-Scope: Calendar Capacity, Product Mismatch, Review Warning, GELMEDI

- Bookeo screenshot path: `docs/reference/bookeo/calendar-loop/bookeo-signin-entry-blocked-2026-06-14.png` (Bookeo sign-in entry only; authenticated Calendar unavailable)
- TicketMirror before screenshot path: not captured before the patch because the actionable mismatch was found in Calendar code/tests while Bookeo live access was blocked
- TicketMirror after screenshot path:
  - `docs/reference/bookeo/calendar-loop/ticketmirror-calendar-capacity-review-after-2026-06-14.png`
  - `docs/reference/bookeo/calendar-loop/ticketmirror-calendar-review-warning-boxes-after-2026-06-14.png`
- Bookeo fields/controls: not verified live; Bookeo Calendar unavailable
- TicketMirror fields/controls: date navigation, mini-calendar, date input, search, category/activity/provider filters, canceled/manual-review visibility, rows/boxes switch, print link, slot rows/cards
- Missing in TicketMirror: not assessed against live Bookeo in this micro-scope
- Extra in TicketMirror: not assessed against live Bookeo in this micro-scope
- Wrong behavior:
  - Open product-mismatch review bookings could be included in Calendar capacity/search/slot drill-in paths.
  - Matched manual-review bookings did not expose a Calendar warning marker.
- Fix applied:
  - Excluded open `PRODUCT_MISMATCH` review bookings from `get_slot_bookings()`, extra booking-slot discovery in capacity summary, and Calendar filtered booking querysets.
  - Added `has_warning` on Calendar rows for matched pending/manual-review bookings.
  - Added compact accessible warning marker in Calendar rows, boxes, and slot drill-in.
  - Added Calendar tests for product-mismatch exclusion, matched review warning, GELMEDI capacity exclusion, and no raw/developer labels on Calendar pages.
- Status: VERIFIED locally, OPEN for Bookeo live parity

## Verification

- `python manage.py check`: pass
- `python manage.py makemigrations --check --dry-run`: pass; warning only because default Postgres host `postgres` is unavailable
- `pytest`: bare command not on PATH; `.venv\Scripts\python.exe -m pytest -q` pass
- `ruff check .`: bare command not on PATH; `.venv\Scripts\ruff.exe check .` pass
- `black --check .`: bare command not on PATH; `.venv\Scripts\python.exe -m black --check .` pass

## Remaining Open Work

- Complete Bookeo live Calendar inspection from an authenticated, unblocked Bookeo session.
- Click every visible Bookeo Calendar field, control, button, dropdown, row, slot, booking, search/filter, date control, view toggle, print/export control, canceled visibility control, and modal/popup path.
- Break remaining Calendar work into micro-scopes discovered from live Bookeo, then patch one micro-scope at a time.
- Do not commit until Bookeo live Calendar parity is fully verified.
