# Schedule Seed Acceptance Audit

Audit date: 2026-06-14

Source of truth: `docs/reference/bookeo/exact-product-schedule-data.md`

Local verification path:

- Opened local TicketMirror at `http://127.0.0.1:8000`.
- Re-ran `python manage.py seed_bookeo_products` before inspection.
- For each seeded product, opened Settings > Tours & Activities > Schedule and People.
- Compared only Current schedule, Other schedules, Duration, and scoped People capacity / number-of-people values.
- Did not inspect or implement Additional times, Marketing, Price, Accept/deny, Resources, Options, Messages, Reports, Public booking, or Payments.

Screenshot folder: `docs/reference/bookeo/schedule-seed-acceptance/`

## Summary

All 12 seeded products pass the final Schedule seed/data parity audit against `exact-product-schedule-data.md`.

One scoped defect was found during the first audit pass and fixed before this final audit:

- `gyg yacht` initially displayed TicketMirror's default `0 days, 2 hours, 00 minutes` duration because the product has no active fixed schedule slots. The seed now stores a duration-only inactive slot, and the duration display uses it only as a no-active-slot fallback. No yacht fixed time appears in the weekly grid.

## Product Results

### Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR

- Status: PASS
- Screenshot path:
  - Schedule: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-schedule-bosphorus-cruise-tour-in-istanbul-for-2-hours-viator.png`
  - People: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-people-bosphorus-cruise-tour-in-istanbul-for-2-hours-viator.png`
- Verified values:
  - Product name matches.
  - Current schedule effective from Saturday, 4 April 2026 to Friday, 31 July 2026.
  - Monday through Sunday show 11:00, 14:00, 19:00.
  - Every visible time shows 250 seats.
  - Other schedules match: `1/4/2027 / blank / SUMMER season 2027`; `1/10/2026 / 31/3/2027 / WINTER season`; `1/8/2026 / 30/9/2026 / AUTMUN season`; `1/4/2026 / 3/4/2026 / summer season`; `1/10/2025 / 31/3/2026 / WINTER season`; `19/5/2024 / 30/9/2025 / Default season`.
  - Duration is 0 days, 2 hours, 00 minutes.
  - People values show min 1, max 20, assigned capacity 250.
- Mismatches: none
- Exact fix required if failed: none

### 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR

- Status: PASS
- Screenshot path:
  - Schedule: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-schedule-2-hours-bosphorus-cruise-boat-tour-in-istanbul-viator.png`
  - People: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-people-2-hours-bosphorus-cruise-boat-tour-in-istanbul-viator.png`
- Verified values:
  - Product name matches.
  - Current schedule effective from Wednesday, 1 April 2026 to Friday, 31 July 2026.
  - Monday through Sunday show 11:00, 14:00, 19:00.
  - Every visible time shows 250 seats.
  - Other schedules match: `1/4/2027 / blank / autumon season`; `1/10/2026 / 31/3/2027 / WINTER season`; `1/8/2026 / 30/9/2026 / autumon season`; `1/10/2025 / 31/3/2026 / winter season`; `19/5/2024 / 30/9/2025 / Default season`.
  - Duration is 0 days, 2 hours, 00 minutes.
  - People values show min 1, max 20, assigned capacity 250.
- Mismatches: none
- Exact fix required if failed: none

### 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER

- Status: PASS
- Screenshot path:
  - Schedule: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-schedule-2-hours-bosphorus-cruise-boat-tour-in-istanbul-viator-transfer.png`
  - People: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-people-2-hours-bosphorus-cruise-boat-tour-in-istanbul-viator-transfer.png`
- Verified values:
  - Product name matches.
  - Current schedule effective from Wednesday, 1 April 2026 with no end date.
  - Monday through Sunday show 11:00, 14:00, 19:00.
  - Every visible time shows 250 seats.
  - Other schedules match: `1/10/2025 / 31/3/2026 / WINTER season`; `19/5/2024 / 30/9/2025 / Default season`.
  - Duration is 0 days, 2 hours, 00 minutes.
  - People values show min 1, max 20, assigned capacity 250.
- Mismatches: none
- Exact fix required if failed: none

### 2 Hours Bosphorus Tour SL-1

- Status: PASS
- Screenshot path:
  - Schedule: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-schedule-2-hours-bosphorus-tour-sl-1.png`
  - People: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-people-2-hours-bosphorus-tour-sl-1.png`
- Verified values:
  - Product name matches.
  - Current schedule effective from Wednesday, 1 October 2025 with no end date.
  - Monday through Sunday show 11:00.
  - Every visible time shows 250 seats.
  - Other schedules match: `19/5/2024 / 30/9/2025 / Default season`.
  - Duration is 0 days, 2 hours, 00 minutes.
  - People values show min 1, max 20, assigned capacity 250.
- Mismatches: none
- Exact fix required if failed: none

### GYG 2 Hours Bosphorus Tour SL-(2-3)

- Status: PASS
- Screenshot path:
  - Schedule: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-schedule-gyg-2-hours-bosphorus-tour-sl-2-3.png`
  - People: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-people-gyg-2-hours-bosphorus-tour-sl-2-3.png`
- Verified values:
  - Product name matches.
  - Current schedule effective from Wednesday, 1 April 2026 to Friday, 31 July 2026.
  - Monday through Sunday show 14:00 and 19:00.
  - Every visible time shows 250 seats.
  - Other schedules match: `1/10/2026 / blank / winter season2`; `1/8/2026 / 30/9/2026 / autumn season`; `4/2/2026 / 31/3/2026 / winter season`; `1/10/2025 / 3/2/2026 / winter season`; `19/5/2024 / 30/9/2025 / Default season`.
  - Duration is 0 days, 2 hours, 00 minutes.
  - People values show min 1, max 20, assigned capacity 250.
- Mismatches: none
- Exact fix required if failed: none

### Istanbul Old City And Bosphorus Tour

- Status: PASS
- Screenshot path:
  - Schedule: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-schedule-istanbul-old-city-and-bosphorus-tour.png`
  - People: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-people-istanbul-old-city-and-bosphorus-tour.png`
- Verified values:
  - Product name matches.
  - Current schedule effective from Friday, 1 August 2025 with no end date.
  - Monday through Sunday show 08:30.
  - Every visible time shows 50 seats.
  - Other schedules match: `19/5/2024 / 31/7/2025 / Default season`.
  - Duration is 0 days, 4 hours, 00 minutes.
  - People values show min 1, max 20, assigned capacity 50.
- Mismatches: none
- Exact fix required if failed: none

### Istanbul Two Continents Tour By Bus And Bosphorus Cruise

- Status: PASS
- Screenshot path:
  - Schedule: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-schedule-istanbul-two-continents-tour-by-bus-and-bosphorus-cruise.png`
  - People: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-people-istanbul-two-continents-tour-by-bus-and-bosphorus-cruise.png`
- Verified values:
  - Product name matches.
  - Current schedule effective from Sunday, 31 May 2026 with no end date.
  - Monday through Sunday show 08:15.
  - Every visible time shows 50 seats.
  - Other schedules match: `19/5/2024 / 30/5/2026 / Default season`.
  - Duration is 0 days, 8 hours, 00 minutes.
  - People values show min 1, max 20, assigned capacity 50.
- Mismatches: none
- Exact fix required if failed: none

### Istanbul Old City And Bosphorus Tour - GYG

- Status: PASS
- Screenshot path:
  - Schedule: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-schedule-istanbul-old-city-and-bosphorus-tour-gyg.png`
  - People: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-people-istanbul-old-city-and-bosphorus-tour-gyg.png`
- Verified values:
  - Product name matches.
  - Current schedule effective from Friday, 1 August 2025 with no end date.
  - Monday through Sunday show 08:15.
  - Every visible time shows 50 seats.
  - Other schedules match: `19/5/2024 / 31/7/2025 / Default season`.
  - Duration is 0 days, 4 hours, 00 minutes.
  - People values show min 1, max 20, assigned capacity 50.
- Mismatches: none
- Exact fix required if failed: none

### Istanbul Two Continents Tour By Bus And Bosphorus Cruise - GYG

- Status: PASS
- Screenshot path:
  - Schedule: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-schedule-istanbul-two-continents-tour-by-bus-and-bosphorus-cruise-gyg.png`
  - People: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-people-istanbul-two-continents-tour-by-bus-and-bosphorus-cruise-gyg.png`
- Verified values:
  - Product name matches.
  - Current schedule has no date limits, matching the `not visible in captured Bookeo schedule material` expectation.
  - Monday through Sunday show 08:15.
  - Every visible time shows 50 seats.
  - Other schedules are empty.
  - Duration is 0 days, 8 hours, 00 minutes.
  - People values show min 1, max 20, assigned capacity 50.
- Mismatches: none
- Exact fix required if failed: none

### 1 Hours Bosphorus Tour viator

- Status: PASS
- Screenshot path:
  - Schedule: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-schedule-1-hours-bosphorus-tour-viator.png`
  - People: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-people-1-hours-bosphorus-tour-viator.png`
- Verified values:
  - Product name matches.
  - Current schedule has no date limits, matching the `not visible in captured Bookeo schedule material` expectation.
  - Monday through Sunday show 17:00.
  - Every visible time shows 250 seats.
  - Other schedules are empty.
  - Duration is 0 days, 1 hour, 00 minutes.
  - People values show min 1, max 20, assigned capacity 250.
- Mismatches: none
- Exact fix required if failed: none

### 1 Hours Bosphorus Tour GYG

- Status: PASS
- Screenshot path:
  - Schedule: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-schedule-1-hours-bosphorus-tour-gyg.png`
  - People: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-people-1-hours-bosphorus-tour-gyg.png`
- Verified values:
  - Product name matches.
  - Current schedule effective from Tuesday, 17 February 2026 with no end date.
  - Monday through Sunday show 17:00.
  - Every visible time shows 250 seats.
  - Other schedules are empty.
  - Duration is 0 days, 1 hour, 00 minutes.
  - People values show min 1, max 20, assigned capacity 250.
- Mismatches: none
- Exact fix required if failed: none

### gyg yacht

- Status: PASS
- Screenshot path:
  - Schedule: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-schedule-gyg-yacht.png`
  - People: `docs/reference/bookeo/schedule-seed-acceptance/ticketmirror-people-gyg-yacht.png`
- Verified values:
  - Product name matches.
  - Current schedule has no date limits and no visible fixed time slots.
  - Other schedules are empty.
  - Duration is 0 days, 1 hour, 00 minutes.
  - People values show min 1 with no assigned capacity, matching the no visible Bookeo capacity value.
- Mismatches: none
- Exact fix required if failed: none

## Final Acceptance Status

PASS: all scoped Schedule seed/data parity values match the expected document after the yacht duration seed correction.
