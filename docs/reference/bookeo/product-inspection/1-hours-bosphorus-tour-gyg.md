# Product Inspection: 1 Hours Bosphorus Tour GYG

## Inspection Metadata
- Inspected date: 2026-06-13
- Inspected by: Codex
- Bookeo navigation path: Settings > Tours and activities > 1 Hours Bosphorus Tour GYG
- Product matched exactly? yes
- If not exact, closest visible product name:
- Notes about ambiguity: One-hour Bosphorus cruise alias for GYG.

## General Tab

### Name
- Visible product name: 1 Hours Bosphorus Tour GYG
- Internal/display name notes: Internal nickname observed as `GYG - 1 Hours`.

### Display Settings
The product is customer-bookable, integration/API booking is enabled, package-only booking is not enabled, no waiver was selected, a thumbnail is present, and no video URL was visible.

## Scheduling Tab

### Current Schedule
- Schedule name: Current schedule.
- Active date range: Visible range was not captured from the grid in this pass.
- Days of week: Weekly grid was visible.
- Time slots: 17:00.
- Duration: 1-hour product by product name; confirm timing control before migration.
- Capacity or availability references: 250 seats per listed time slot.
- Exceptions / blocked periods: No blocked periods visible.
- Transfer or pickup timing if visible: Arrival reminder was enabled; no transfer timing was visible.
- Other visible schedule rules: Recurring customer bookings were enabled for exactly 2 appointments; staff recurring bookings were disabled; too-late bookings are hidden.

### Current Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Schedule tab | One 17:00 fixed departure. | Same slot pattern as the Viator one-hour alias. |
| Current schedule grid | 250 seats. | Provider aliases may share capacity if operations confirms. |
| Arrival timing area | Arrival reminder behavior was enabled. | Later operator note, not required for first implementation. |
| Slot edit affordances observed, not opened | Edit controls were visible but not opened. | No Bookeo edit behavior should be copied. |

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
| Other schedule table | No rows were captured. | Allow current-only product schedules. |
| Season row edit affordances observed, not opened | No season rows available. | No other-season implementation dependency observed. |

## People Tab

### Number Of People Per Booking
- Minimum people per booking: 1 where the full control set was visible.
- Maximum people per booking: 20 where the full control set was visible.
- Capacity/availability implications: Party size consumes from the 250-seat departure.
- Any group/private booking behavior visible: Private-tour behavior was not enabled.
- TicketMirror capacity note: If Viator and GYG one-hour products share inventory, provider aliases should decrement one capacity pool.

## TicketMirror Mapping Draft

### Suggested Canonical Product
- Suggested canonical product name: Bosphorus Cruise
- Suggested variant name: 1-hour GYG alias
- Suggested slot type:
  - fixed_time

### Suggested Capacity Model
- Capacity per slot: 250
- Capacity source: Visible current schedule slot capacity.
- Needs manual confirmation? yes
- Notes: Confirm shared capacity with the Viator one-hour alias.

### Suggested Provider Alias
- Provider: GYG
- Raw provider product name: 1 Hours Bosphorus Tour GYG
- Transfer variant? no
- GYG/Viator/direct variant? yes
- Notes: One-hour provider alias under the Bosphorus Cruise canonical product.

## Open Questions
- Question 1: Should the Viator and GYG one-hour aliases map to one variant with two provider aliases?
- Question 2: Are there hidden seasons not visible in the other-schedule table?
