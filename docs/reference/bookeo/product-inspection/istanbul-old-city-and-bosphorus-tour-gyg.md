# Product Inspection: Istanbul Old City And Bosphorus Tour - GYG

## Inspection Metadata
- Inspected date: 2026-06-13
- Inspected by: Codex
- Bookeo navigation path: Settings > Tours and activities > Istanbul Old City And Bosphorus Tour - GYG
- Product matched exactly? yes
- If not exact, closest visible product name:
- Notes about ambiguity: Likely GYG alias of the Old City and Bosphorus tour.

## General Tab

### Name
- Visible product name: Istanbul Old City And Bosphorus Tour - GYG
- Internal/display name notes: Internal nickname observed as `GYG - OLD CITY`.

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
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: Recurring customer bookings were enabled for exactly 2 appointments; staff recurring bookings were disabled; too-late bookings are hidden.

### Current Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Schedule tab | One 8:15 departure. | Model as fixed-time product variant. |
| Current schedule grid | 50 seats on the visible departure. | Capacity should likely align with the Viator Old City product if operations confirms shared inventory. |
| Slot edit affordances observed, not opened | Edit controls were visible but not opened. | Avoid Bookeo mutation flows. |

### Other Schedule
- Schedule name: Default season.
- Active date range: 19/5/2024 to 31/7/2025.
- Days of week: Not expanded from the other-schedule row.
- Time slots: Not expanded from the other-schedule row.
- Duration: Confirm manually.
- Capacity or availability references: Not visible in the other-schedule table.
- Exceptions / blocked periods: None visible.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: One default season row was visible.

### Other Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Other schedule table | One default season row. | Supports alias-specific season history. |
| Season row edit affordances observed, not opened | No safe read-only expansion was used. | Confirm whether GYG and Viator season ranges should normalize together. |

## People Tab

### Number Of People Per Booking
- Minimum people per booking: 1 where the full control set was visible.
- Maximum people per booking: 20 where the full control set was visible.
- Capacity/availability implications: Party size consumes seats from the 50-seat departure.
- Any group/private booking behavior visible: Private-tour behavior was not enabled.
- TicketMirror capacity note: If this shares inventory with the Viator alias, aggregate provider bookings into one capacity pool.

## TicketMirror Mapping Draft

### Suggested Canonical Product
- Suggested canonical product name: Istanbul Old City and Bosphorus Tour
- Suggested variant name: GYG alias
- Suggested slot type:
  - half_day

### Suggested Capacity Model
- Capacity per slot: 50
- Capacity source: Visible current schedule slot capacity.
- Needs manual confirmation? yes
- Notes: Confirm shared inventory with the Viator Old City product.

### Suggested Provider Alias
- Provider: GYG
- Raw provider product name: Istanbul Old City And Bosphorus Tour - GYG
- Transfer variant? no
- GYG/Viator/direct variant? yes
- Notes: Alias candidate, not separate canonical product.

## Open Questions
- Question 1: Why does this alias use 8:15 while the Viator Old City product uses 8:30?
- Question 2: Are those separate pickups or separate tour starts?
