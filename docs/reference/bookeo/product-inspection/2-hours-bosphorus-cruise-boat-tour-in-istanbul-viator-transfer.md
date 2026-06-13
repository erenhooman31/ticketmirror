# Product Inspection: 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER

## Inspection Metadata
- Inspected date: 2026-06-13
- Inspected by: Codex
- Bookeo navigation path: Settings > Tours and activities > 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER
- Product matched exactly? yes
- If not exact, closest visible product name:
- Notes about ambiguity: Appears to be a transfer-enabled alias of the 2-hour Bosphorus cruise.

## General Tab

### Name
- Visible product name: 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER
- Internal/display name notes: Internal nickname observed as `NEW VIATOR 2H TRANSFER`.

### Display Settings
The product is customer-bookable, integration/API booking is enabled, package-only booking is not enabled, no waiver was selected, a thumbnail is present, and no video URL was visible.

## Scheduling Tab

### Current Schedule
- Schedule name: Current schedule.
- Active date range: Visible range was not captured from the read-only grid in this pass.
- Days of week: Monday through Sunday were shown in the weekly grid.
- Time slots: 11:00, 14:00, 19:00.
- Duration: Expected 2-hour cruise model; confirm in Bookeo before migration.
- Capacity or availability references: 250 seats per listed time slot.
- Exceptions / blocked periods: No blocked periods visible in the inspected schedule grid.
- Transfer or pickup timing if visible: The product name indicates transfer, but no pickup offset or transfer timing was visible in the inspected schedule area.
- Other visible schedule rules: Same default schedule-rule controls were visible as the 2-hour products when the schedule editor controls were available.

### Current Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Schedule tab | Weekly grid with 11:00, 14:00, and 19:00 departures. | Transfer variant should reuse the same slot catalog unless pickup timing is added separately. |
| Current schedule grid | Slots showed 250 seats. | Capacity can be shared structurally with non-transfer 2-hour cruise variants. |
| Slot edit affordances observed, not opened | Edit controls were visible but not opened. | Do not infer pickup rules from product name alone. |

### Other Schedule
- Schedule name: WINTER season; Default season.
- Active date range: 1/10/2025 to 31/3/2026; 19/5/2024 to 30/9/2025.
- Days of week: Not expanded from other-schedule rows.
- Time slots: Not expanded from other-schedule rows.
- Duration: Confirm manually.
- Capacity or availability references: Not visible in the other-schedule table.
- Exceptions / blocked periods: None visible.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: Fewer seasonal rows were visible than the non-transfer Viator products.

### Other Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Other schedule table | Two historical seasonal rows. | TicketMirror should support missing future seasonal rows per alias. |
| Season row edit affordances observed, not opened | No safe read-only expansion was used. | Confirm transfer-specific seasonality manually before implementation. |

## People Tab

### Number Of People Per Booking
- Minimum people per booking: 1 where the full control set was visible.
- Maximum people per booking: 20 where the full control set was visible.
- Capacity/availability implications: Party size consumes from the 250-seat slot capacity.
- Any group/private booking behavior visible: Private-tour behavior was not enabled.
- TicketMirror capacity note: Transfer logistics may need a separate pickup-capacity model later; do not build it yet.

## TicketMirror Mapping Draft

### Suggested Canonical Product
- Suggested canonical product name: Bosphorus Cruise
- Suggested variant name: 2-hour Viator transfer
- Suggested slot type:
  - fixed_time

### Suggested Capacity Model
- Capacity per slot: 250
- Capacity source: Visible current schedule slot capacity.
- Needs manual confirmation? yes
- Notes: Confirm transfer pickup timing and whether transfer bookings share the same cruise capacity.

### Suggested Provider Alias
- Provider: Viator
- Raw provider product name: 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER
- Transfer variant? yes
- GYG/Viator/direct variant? yes
- Notes: Treat as a variant, not a separate canonical product, unless operations confirms separate inventory.

## Open Questions
- Question 1: Does transfer inventory share the same boat capacity as non-transfer bookings?
- Question 2: Where is pickup timing configured if not on the inspected schedule screen?
