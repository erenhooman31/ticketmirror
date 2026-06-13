# Product Inspection: 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR

## Inspection Metadata
- Inspected date: 2026-06-13
- Inspected by: Codex
- Bookeo navigation path: Settings > Tours and activities > 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR
- Product matched exactly? yes
- If not exact, closest visible product name:
- Notes about ambiguity: Name overlaps with other 2-hour Bosphorus provider aliases.

## General Tab

### Name
- Visible product name: 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR
- Internal/display name notes: Internal nickname observed as `NEW VIATOR 2H V2`.

### Display Settings
The product is customer-bookable, integration/API booking is enabled, package-only booking is not enabled, no waiver was selected, a thumbnail is present, and no video URL was visible.

## Scheduling Tab

### Current Schedule
- Schedule name: Current active seasonal schedule.
- Active date range: Wednesday, 1 April 2026 to Friday, 31 July 2026.
- Days of week: Monday through Sunday.
- Time slots: 11:00, 14:00, 19:00.
- Duration: 2 hours where the timing controls were visible.
- Capacity or availability references: 250 seats per listed time slot.
- Exceptions / blocked periods: Blocked-period mode was visible; no blocked periods were listed.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: Minimum advance booking was 10 minutes, maximum advance booking was 12 months, too-late bookings are hidden, customer recurring bookings were enabled for exactly 2 appointments, staff recurring bookings were disabled, private-tour and virtual-roster behavior were disabled.

### Current Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Schedule tab | Weekly seven-day grid with three fixed departures. | Model this as fixed daily departures. |
| Current schedule grid | Start time and 250-seat capacity were visible on each slot. | Imported bookings should decrement per-slot capacity. |
| Timing and booking rules area | Duration, booking windows, recurrence, and availability controls. | Establish defaults for TicketMirror product schedule settings. |
| Slot edit affordances observed, not opened | Edit controls were visible but not opened to avoid changing Bookeo. | Editing behavior is not part of this documentation task. |

### Other Schedule
- Schedule name: autumon season; WINTER season; autumon season; winter season; Default season.
- Active date range: 1/4/2027 onward; 1/10/2026 to 31/3/2027; 1/8/2026 to 30/9/2026; 1/10/2025 to 31/3/2026; 19/5/2024 to 30/9/2025.
- Days of week: Not expanded from seasonal rows.
- Time slots: Not expanded from seasonal rows.
- Duration: Use current 2-hour model pending confirmation.
- Capacity or availability references: Not visible in the other-schedule table.
- Exceptions / blocked periods: None visible.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: Seasonal rows define future and past effective ranges.

### Other Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Other schedule table | Seasonal date ranges and names. | Requires effective-date schedule records. |
| Season row edit affordances observed, not opened | Season rows were not opened because they appeared to be edit flows. | Avoid copying Bookeo edit behavior; implement TicketMirror read/edit separately later. |

## People Tab

### Number Of People Per Booking
- Minimum people per booking: 1 where the full control set was visible.
- Maximum people per booking: 20 where the full control set was visible.
- Capacity/availability implications: Party size consumes seats from the 250-seat slot.
- Any group/private booking behavior visible: Private-tour behavior was not enabled.
- TicketMirror capacity note: Use imported booking passenger counts to compute remaining capacity.

## TicketMirror Mapping Draft

### Suggested Canonical Product
- Suggested canonical product name: Bosphorus Cruise
- Suggested variant name: 2-hour Viator alias V2
- Suggested slot type:
  - fixed_time

### Suggested Capacity Model
- Capacity per slot: 250
- Capacity source: Visible current schedule slot capacity.
- Needs manual confirmation? no
- Notes: Seasonal capacity should be confirmed before automated import.

### Suggested Provider Alias
- Provider: Viator
- Raw provider product name: 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR
- Transfer variant? no
- GYG/Viator/direct variant? yes
- Notes: Likely same canonical cruise as the first product, with a different provider alias or listing version.

## Open Questions
- Question 1: Is this product replacing or coexisting with the first Viator 2-hour alias?
- Question 2: Are the misspelled seasonal names intentional aliases that should be normalized in TicketMirror?
