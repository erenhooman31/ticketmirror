# Product Inspection: GYG 2 Hours Bosphorus Tour SL-(2-3)

## Inspection Metadata
- Inspected date: 2026-06-13
- Inspected by: Codex
- Bookeo navigation path: Settings > Tours and activities > GYG 2 Hours Bosphorus Tour SL-(2-3)
- Product matched exactly? yes
- If not exact, closest visible product name:
- Notes about ambiguity: Looks like the GYG alias for the later two 2-hour departures.

## General Tab

### Name
- Visible product name: GYG 2 Hours Bosphorus Tour SL-(2-3)
- Internal/display name notes: Internal nickname observed as `GYG - 2 SAAT SL-(2-3)`.

### Display Settings
The product is customer-bookable, integration/API booking is enabled, package-only booking is not enabled, no waiver was selected, a thumbnail is present, and no video URL was visible.

## Scheduling Tab

### Current Schedule
- Schedule name: Current active seasonal schedule.
- Active date range: Wednesday, 1 April 2026 to Friday, 31 July 2026.
- Days of week: Monday through Sunday.
- Time slots: 14:00, 19:00.
- Duration: 2-hour product by product name; confirm timing control before migration.
- Capacity or availability references: 250 seats per listed time slot.
- Exceptions / blocked periods: No blocked periods visible.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: Customer recurring bookings were enabled for exactly 2 appointments; staff recurring bookings were disabled; too-late bookings are hidden.

### Current Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Schedule tab | Weekly grid with 14:00 and 19:00 departures. | Model as fixed afternoon/evening slots. |
| Current schedule grid | Each visible slot had 250 seats. | Capacity can share rules with other 2-hour cruise variants. |
| Slot edit affordances observed, not opened | Edit controls were visible but not opened. | Prevent accidental Bookeo changes. |

### Other Schedule
- Schedule name: winter season2; autumn season; winter season; winter season; Default season.
- Active date range: 1/10/2026 onward; 1/8/2026 to 30/9/2026; 4/2/2026 to 31/3/2026; 1/10/2025 to 3/2/2026; 19/5/2024 to 30/9/2025.
- Days of week: Not expanded from seasonal rows.
- Time slots: Not expanded from seasonal rows.
- Duration: Confirm manually.
- Capacity or availability references: Not visible in the other-schedule table.
- Exceptions / blocked periods: None visible.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: Multiple winter rows suggest seasonal changes split by effective date.

### Other Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Other schedule table | Five seasonal rows with split winter ranges. | TicketMirror needs season records that can overlap the same season label with different dates. |
| Season row edit affordances observed, not opened | Rows were not opened to avoid edit flows. | Confirm seasonal slot changes manually before import. |

## People Tab

### Number Of People Per Booking
- Minimum people per booking: 1 where the full control set was visible.
- Maximum people per booking: 20 where the full control set was visible.
- Capacity/availability implications: Party size consumes seats from 250-seat departures.
- Any group/private booking behavior visible: Private-tour behavior was not enabled.
- TicketMirror capacity note: Create two daily slot records, each with separate capacity.

## TicketMirror Mapping Draft

### Suggested Canonical Product
- Suggested canonical product name: Bosphorus Cruise
- Suggested variant name: 2-hour GYG SL-2-3
- Suggested slot type:
  - fixed_time

### Suggested Capacity Model
- Capacity per slot: 250
- Capacity source: Visible current schedule slot capacity.
- Needs manual confirmation? yes
- Notes: Confirm if SL-(2-3) maps to the 14:00 and 19:00 operational departures.

### Suggested Provider Alias
- Provider: GYG
- Raw provider product name: GYG 2 Hours Bosphorus Tour SL-(2-3)
- Transfer variant? no
- GYG/Viator/direct variant? yes
- Notes: GYG alias for the afternoon/evening 2-hour cruise.

## Open Questions
- Question 1: Should SL-1 and SL-(2-3) be variants or provider aliases on separate slots?
- Question 2: Do the future winter/autumn seasons change times or only effective dates?
