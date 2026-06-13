# Product Inspection: Istanbul Two Continents Tour By Bus And Bosphorus Cruise

## Inspection Metadata
- Inspected date: 2026-06-13
- Inspected by: Codex
- Bookeo navigation path: Settings > Tours and activities > Istanbul Two Continents Tour By Bus And Bosphorus Cruise
- Product matched exactly? yes
- If not exact, closest visible product name:
- Notes about ambiguity: Likely a separate land-and-cruise product, not a Bosphorus cruise alias.

## General Tab

### Name
- Visible product name: Istanbul Two Continents Tour By Bus And Bosphorus Cruise
- Internal/display name notes: Internal nickname observed as `VIATOR-TWO CONTINENTS`.

### Display Settings
The product is customer-bookable, integration/API booking is enabled, package-only booking is not enabled, no waiver was selected, a thumbnail is present, and no video URL was visible.

## Scheduling Tab

### Current Schedule
- Schedule name: Current schedule.
- Active date range: Visible range was not captured from the grid in this pass.
- Days of week: Weekly grid was visible.
- Time slots: 8:15.
- Duration: Not confirmed from timing controls; likely half-day or full-day tour and requires manual confirmation.
- Capacity or availability references: 50 seats per listed time slot.
- Exceptions / blocked periods: No blocked periods visible.
- Transfer or pickup timing if visible: None visible in the inspected schedule area.
- Other visible schedule rules: Recurring customer bookings were enabled for exactly 2 appointments; staff recurring bookings were disabled; too-late bookings are hidden.

### Current Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Schedule tab | One 8:15 departure. | Model as a fixed start time with tour-duration metadata. |
| Current schedule grid | 50-seat capacity. | Land-tour capacity differs from boat-only capacity. |
| Slot edit affordances observed, not opened | Edit controls were visible but not opened. | Avoid editing Bookeo while confirming duration later. |

### Other Schedule
- Schedule name: Default season.
- Active date range: 19/5/2024 to 30/5/2026.
- Days of week: Not expanded from the other-schedule row.
- Time slots: Not expanded from the other-schedule row.
- Duration: Confirm manually.
- Capacity or availability references: Not visible in the other-schedule table.
- Exceptions / blocked periods: None visible.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: One long default season row was visible.

### Other Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Other schedule table | One effective date range. | Simple schedule season support is enough initially. |
| Season row edit affordances observed, not opened | No safe read-only expansion was used. | Confirm if future seasons exist outside visible rows. |

## People Tab

### Number Of People Per Booking
- Minimum people per booking: 1 where the full control set was visible.
- Maximum people per booking: 20 where the full control set was visible.
- Capacity/availability implications: Party size consumes seats from the 50-seat departure.
- Any group/private booking behavior visible: Private-tour behavior was not enabled.
- TicketMirror capacity note: Configure 50-seat capacity separately from cruise-only products.

## TicketMirror Mapping Draft

### Suggested Canonical Product
- Suggested canonical product name: Istanbul Two Continents Tour
- Suggested variant name: Viator alias
- Suggested slot type:
  - full_day

### Suggested Capacity Model
- Capacity per slot: 50
- Capacity source: Visible current schedule slot capacity.
- Needs manual confirmation? yes
- Notes: Confirm duration and whether the GYG alias shares capacity.

### Suggested Provider Alias
- Provider: Viator
- Raw provider product name: Istanbul Two Continents Tour By Bus And Bosphorus Cruise
- Transfer variant? no
- GYG/Viator/direct variant? yes
- Notes: Separate canonical product from Old City and cruise-only products.

## Open Questions
- Question 1: Is this full-day or half-day in operations?
- Question 2: Does it share transport/boat capacity with other tours?
