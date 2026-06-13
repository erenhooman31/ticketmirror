# Product Inspection: 2 Hours Bosphorus Tour SL-1

## Inspection Metadata
- Inspected date: 2026-06-13
- Inspected by: Codex
- Bookeo navigation path: Settings > Tours and activities > 2 Hours Bosphorus Tour SL-1
- Product matched exactly? yes
- If not exact, closest visible product name:
- Notes about ambiguity: Looks like a GYG/source-listing variant for a single 2-hour departure.

## General Tab

### Name
- Visible product name: 2 Hours Bosphorus Tour SL-1
- Internal/display name notes: Internal nickname observed as `GYG - 2 SAAT (SL-1)`.

### Display Settings
The product is customer-bookable, integration/API booking is enabled, package-only booking is not enabled, no waiver was selected, a thumbnail is present, and no video URL was visible.

## Scheduling Tab

### Current Schedule
- Schedule name: Current schedule.
- Active date range: Visible range was not captured from the grid in this pass.
- Days of week: Weekly grid was visible.
- Time slots: 11:00.
- Duration: 2-hour product by product name; confirm timing control before migration.
- Capacity or availability references: 250 seats per listed time slot.
- Exceptions / blocked periods: No blocked periods visible.
- Transfer or pickup timing if visible: Arrival reminder was enabled; no pickup/transfer timing was visible.
- Other visible schedule rules: Recurring customer bookings were enabled for exactly 2 appointments; staff recurring bookings were disabled; too-late bookings are hidden.

### Current Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Schedule tab | One fixed departure time was visible. | Model as a fixed-time variant with one departure. |
| Current schedule grid | 11:00 slot with 250 seats. | Capacity belongs to the slot. |
| Arrival timing area | Arrival reminder/offset behavior was enabled. | Later TicketMirror UX may need an arrival-note field, not pickup logistics. |
| Slot edit affordances observed, not opened | Edit controls were visible but not opened. | Do not implement Bookeo-style slot editing yet. |

### Other Schedule
- Schedule name: Default season.
- Active date range: 19/5/2024 to 30/9/2025.
- Days of week: Not expanded from the other-schedule row.
- Time slots: Not expanded from the other-schedule row.
- Duration: Confirm manually.
- Capacity or availability references: Not visible in the other-schedule table.
- Exceptions / blocked periods: None visible.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: One historical/default season row was visible.

### Other Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Other schedule table | One default season row. | Keep seasonal history optional per product. |
| Season row edit affordances observed, not opened | No safe read-only expansion was used. | Confirm old seasons only if migrating historical availability. |

## People Tab

### Number Of People Per Booking
- Minimum people per booking: 1 where the full control set was visible.
- Maximum people per booking: 20 where the full control set was visible.
- Capacity/availability implications: Party size consumes seats from the 250-seat departure.
- Any group/private booking behavior visible: Private-tour behavior was not enabled.
- TicketMirror capacity note: One 11:00 slot should expose remaining seats after imported bookings.

## TicketMirror Mapping Draft

### Suggested Canonical Product
- Suggested canonical product name: Bosphorus Cruise
- Suggested variant name: 2-hour GYG SL-1
- Suggested slot type:
  - fixed_time

### Suggested Capacity Model
- Capacity per slot: 250
- Capacity source: Visible current schedule slot capacity.
- Needs manual confirmation? yes
- Notes: Confirm whether SL-1 is a provider alias or an operational departure grouping.

### Suggested Provider Alias
- Provider: GYG
- Raw provider product name: 2 Hours Bosphorus Tour SL-1
- Transfer variant? no
- GYG/Viator/direct variant? yes
- Notes: Likely GYG alias for the 11:00 2-hour cruise.

## Open Questions
- Question 1: What does `SL-1` mean operationally?
- Question 2: Is the arrival reminder customer-facing or internal only?
