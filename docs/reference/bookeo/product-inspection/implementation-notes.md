# Bookeo-Inspired Implementation Notes

These notes are functional references for TicketMirror planning only. Do not copy Bookeo branding, exact UI text, visual design, CSS, icons, layout proportions, or trade dress.

## 1. Same Canonical Product With Different Provider Aliases

- Bosphorus Cruise likely includes the 2-hour Viator products, the 2-hour GYG SL products, and the 1-hour Viator/GYG products as variants or aliases.
- Istanbul Old City and Bosphorus Tour likely includes the Viator and GYG Old City products as provider aliases.
- Istanbul Two Continents Tour likely includes the Viator and GYG Two Continents products as provider aliases.

## 2. Separate Variants

- 2-hour Bosphorus cruise: 11:00, 14:00, and 19:00 fixed departures, with GYG split into SL-1 and SL-(2-3).
- 2-hour transfer cruise: separate variant until transfer pickup rules and shared capacity are confirmed.
- 1-hour Bosphorus cruise: 17:00 fixed departure.
- Old City and Two Continents tours: separate tour products, not cruise-only variants.
- Yacht: separate product until confirmed.

## 3. Transfer Variants

- `2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER` is the only inspected product that explicitly indicates transfer behavior in the product name.
- Transfer timing was not visible in the inspected schedule area, so TicketMirror should not implement pickup timing from this inspection alone.

## 4. GYG Aliases

- `GYG 2 Hours Bosphorus Tour SL-(2-3)`
- `2 Hours Bosphorus Tour SL-1` appears to be GYG from its internal nickname.
- `Istanbul Old City And Bosphorus Tour - GYG`
- `Istanbul Two Continents Tour By Bus And Bosphorus Cruise - GYG`
- `1 Hours Bosphorus Tour GYG`
- `gyg yacht`

## 5. Viator Aliases

- `Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR`
- `2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR`
- `2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER`
- `Istanbul Old City And Bosphorus Tour`
- `Istanbul Two Continents Tour By Bus And Bosphorus Cruise`
- `1 Hours Bosphorus Tour viator`

## 6. Fixed-Time Slot Requirements

TicketMirror needs fixed-time slots for:

- 2-hour Bosphorus cruise: 11:00, 14:00, 19:00.
- 2-hour GYG SL-1: 11:00.
- 2-hour GYG SL-(2-3): 14:00, 19:00.
- Old City and Bosphorus: 8:30 for Viator, 8:15 for GYG.
- Two Continents: 8:15.
- 1-hour Bosphorus cruise: 17:00.

## 7. Full-Day Or Half-Day Modeling

- Old City and Bosphorus should probably be modeled as half-day until operations confirms duration.
- Two Continents should probably be modeled as full-day until operations confirms duration.
- Yacht should not be forced into full-day or half-day until its scheduling model is confirmed.

## 8. Products Needing Capacity Rules First

- Bosphorus cruise variants need 250-seat capacity per fixed departure.
- Old City and Two Continents need 50-seat capacity per fixed departure.
- Transfer capacity needs confirmation because it may share cruise capacity plus pickup constraints.
- Yacht capacity is unknown and must be manually confirmed before implementation.

## 9. Possible Future Data Model Changes

- Canonical product with provider aliases.
- Product variant linked to canonical product.
- Fixed-time schedule slot with effective date range.
- Slot capacity and remaining-capacity calculation from imported bookings.
- Optional season/effective-date table for future and historical schedule changes.
- Optional provider-specific alias mapping table.
- Later: transfer/pickup metadata, arrival-note metadata, private-group/yacht capacity model.

## 10. What TicketMirror Should Not Implement Yet

- Bookeo-like product editing screens.
- Bookeo visual design, language, icons, styling, or layout.
- Recurring appointment behavior.
- Full advanced people/pricing rules.
- Transfer pickup logic before confirming where pickup timing is configured.
- Yacht private booking logic before capacity and scheduling are confirmed.
- Historical season migration unless operations requires historical availability.
