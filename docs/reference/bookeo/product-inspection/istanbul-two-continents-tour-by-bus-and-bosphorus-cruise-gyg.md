# Product Inspection: Istanbul Two Continents Tour By Bus And Bosphorus Cruise - GYG

## Inspection Metadata
- Inspected date: 2026-06-13
- Inspected by: Codex
- Bookeo navigation path: Settings > Tours and activities > Istanbul Two Continents Tour By Bus And Bosphorus Cruise - GYG
- Product matched exactly? yes
- If not exact, closest visible product name:
- Notes about ambiguity: Likely GYG alias of the Two Continents tour.

## General Tab

### Name
- Visible product name: Istanbul Two Continents Tour By Bus And Bosphorus Cruise - GYG
- Internal/display name notes: Internal nickname observed as `GYG - TWO CONTINENTS`.

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
| Schedule tab | One 8:15 departure. | Model as fixed-time tour start. |
| Current schedule grid | 50-seat slot. | Likely shares capacity with related Two Continents alias if operations confirms. |
| Slot edit affordances observed, not opened | Edit controls were visible but not opened. | Keep implementation read-only/import-first. |

### Other Schedule
- Schedule name: None visible in the other-schedule table.
- Active date range: None visible.
- Days of week: Not applicable.
- Time slots: Not applicable.
- Duration: Confirm manually.
- Capacity or availability references: Not visible.
- Exceptions / blocked periods: None visible.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: No other-schedule rows were captured.

### Other Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Other schedule table | No rows were captured for this product. | TicketMirror must allow products without alternate seasons. |
| Season row edit affordances observed, not opened | No season rows were available to inspect read-only. | No migration dependency unless hidden seasons exist. |

## People Tab

### Number Of People Per Booking
- Minimum people per booking: 1 where the full control set was visible.
- Maximum people per booking: 20 where the full control set was visible.
- Capacity/availability implications: Party size consumes seats from the 50-seat departure.
- Any group/private booking behavior visible: Private-tour behavior was not enabled.
- TicketMirror capacity note: Confirm whether this shares capacity with the Viator Two Continents product.

## TicketMirror Mapping Draft

### Suggested Canonical Product
- Suggested canonical product name: Istanbul Two Continents Tour
- Suggested variant name: GYG alias
- Suggested slot type:
  - full_day

### Suggested Capacity Model
- Capacity per slot: 50
- Capacity source: Visible current schedule slot capacity.
- Needs manual confirmation? yes
- Notes: Confirm shared capacity and duration.

### Suggested Provider Alias
- Provider: GYG
- Raw provider product name: Istanbul Two Continents Tour By Bus And Bosphorus Cruise - GYG
- Transfer variant? no
- GYG/Viator/direct variant? yes
- Notes: Alias candidate for the Two Continents canonical product.

## Open Questions
- Question 1: Are Viator and GYG Two Continents bookings pooled into one operational departure?
- Question 2: Should the absence of other schedules be treated as current-only configuration?
