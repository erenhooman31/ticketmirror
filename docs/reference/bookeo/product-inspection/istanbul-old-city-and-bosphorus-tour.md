# Product Inspection: Istanbul Old City And Bosphorus Tour

## Inspection Metadata
- Inspected date: 2026-06-13
- Inspected by: Codex
- Bookeo navigation path: Settings > Tours and activities > Istanbul Old City And Bosphorus Tour
- Product matched exactly? yes
- If not exact, closest visible product name:
- Notes about ambiguity: Likely separate from the cruise-only products.

## General Tab

### Name
- Visible product name: Istanbul Old City And Bosphorus Tour
- Internal/display name notes: Internal nickname observed as `VIATOR-OLD CITY`.

### Display Settings
The product is customer-bookable, integration/API booking is enabled, package-only booking is not enabled, no waiver was selected, a thumbnail is present, and no video URL was visible.

## Scheduling Tab

### Current Schedule
- Schedule name: Current schedule.
- Active date range: Visible range was not captured from the grid in this pass.
- Days of week: Weekly grid was visible.
- Time slots: 8:30.
- Duration: Not confirmed from the visible timing controls; likely half-day or full-day tour and requires manual confirmation.
- Capacity or availability references: 50 seats per listed time slot.
- Exceptions / blocked periods: No blocked periods visible.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: Recurring customer bookings were enabled for exactly 2 appointments; staff recurring bookings were disabled; too-late bookings are hidden.

### Current Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Schedule tab | One morning departure. | Model as fixed-time tour start. |
| Current schedule grid | 8:30 slot with 50 seats. | Capacity differs from cruise-only products. |
| Slot edit affordances observed, not opened | Edit controls were visible but not opened. | Duration needs manual confirmation outside mutation flows. |

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
| Other schedule table | One default seasonal range. | Supports a simple effective-date schedule. |
| Season row edit affordances observed, not opened | No safe read-only expansion was used. | Do not infer old-season slots without confirmation. |

## People Tab

### Number Of People Per Booking
- Minimum people per booking: 1 where the full control set was visible.
- Maximum people per booking: 20 where the full control set was visible.
- Capacity/availability implications: Party size consumes seats from the 50-seat departure.
- Any group/private booking behavior visible: Private-tour behavior was not enabled.
- TicketMirror capacity note: Capacity is smaller than cruise-only products and should be configured explicitly.

## TicketMirror Mapping Draft

### Suggested Canonical Product
- Suggested canonical product name: Istanbul Old City and Bosphorus Tour
- Suggested variant name: Viator alias
- Suggested slot type:
  - half_day

### Suggested Capacity Model
- Capacity per slot: 50
- Capacity source: Visible current schedule slot capacity.
- Needs manual confirmation? yes
- Notes: Confirm tour duration before deciding half-day versus full-day.

### Suggested Provider Alias
- Provider: Viator
- Raw provider product name: Istanbul Old City And Bosphorus Tour
- Transfer variant? no
- GYG/Viator/direct variant? yes
- Notes: Separate canonical product from cruise-only Bosphorus tours.

## Open Questions
- Question 1: Is this operationally half-day or full-day?
- Question 2: Does the GYG Old City product share the same inventory?
