# Product Inspection: Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR

## Inspection Metadata
- Inspected date: 2026-06-13
- Inspected by: Codex
- Bookeo navigation path: Settings > Tours and activities > Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR
- Product matched exactly? yes
- If not exact, closest visible product name:
- Notes about ambiguity: None.

## General Tab

### Name
- Visible product name: Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR
- Internal/display name notes: Internal nickname observed as `VIATOR 2H`.

### Display Settings
The product is customer-bookable, integration/API booking is enabled, package-only booking is not enabled, no waiver was selected, a thumbnail is present, and no video URL was visible. Treat the product code as an external reference only, not a TicketMirror identifier.

## Scheduling Tab

### Current Schedule
- Schedule name: Current active seasonal schedule.
- Active date range: Saturday, 4 April 2026 to Friday, 31 July 2026.
- Days of week: Monday through Sunday.
- Time slots: 11:00, 14:00, 19:00.
- Duration: 2 hours where the timing controls were visible.
- Capacity or availability references: 250 seats per listed time slot.
- Exceptions / blocked periods: Availability section used a blocked-period model; no blocked periods were listed.
- Transfer or pickup timing if visible: No transfer or pickup timing was visible in the inspected schedule area.
- Other visible schedule rules: Minimum advance booking was 10 minutes, maximum advance booking was 12 months, too-late bookings are hidden, customer recurring bookings were enabled for exactly 2 appointments, staff recurring bookings were disabled, private-tour and virtual-roster behavior were disabled.

### Current Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Schedule tab | Weekly grid with seven days and three fixed slots per day. | Generate fixed-time inventory for each visible day/time pair. |
| Current schedule grid | Each slot showed a start time and seat count. | Slot capacity should be stored per departure, not only per product. |
| Timing and booking rules area | Duration, booking-window rules, recurrence controls, and availability mode were visible. | TicketMirror needs duration, min/max booking window, and blocked-period support later. |
| Slot edit affordances observed, not opened | Slot edit controls appeared to be edit actions. They were not opened to avoid changing Bookeo data. | Mutation UI is out of scope for this documentation-only task. |

### Other Schedule
- Schedule name: SUMMER season 2027; WINTER season; AUTMUN season; summer season; WINTER season; Default season.
- Active date range: 1/4/2027 onward; 1/10/2026 to 31/3/2027; 1/8/2026 to 30/9/2026; 1/4/2026 to 3/4/2026; 1/10/2025 to 31/3/2026; 19/5/2024 to 30/9/2025.
- Days of week: Not expanded from historical/future schedule rows.
- Time slots: Not expanded from historical/future schedule rows.
- Duration: Use current schedule duration unless a future TicketMirror import proves otherwise.
- Capacity or availability references: Other schedule rows did not expose capacity without entering edit flows.
- Exceptions / blocked periods: None visible in the other-schedule table.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: Other schedule rows define seasonal date boundaries.

### Other Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Other schedule table | Seasonal rows with start, end, and schedule names. | TicketMirror should model product schedule seasons as effective date ranges. |
| Season row edit affordances observed, not opened | Rows appeared tied to schedule-edit behavior. They were not opened to avoid modifying Bookeo data. | Future admin UI should distinguish read-only inspection from edit mode. |

## People Tab

### Number Of People Per Booking
- Minimum people per booking: 1 where the full control set was visible.
- Maximum people per booking: 20 where the full control set was visible.
- Capacity/availability implications: Party size should consume seats from the 250-seat slot capacity.
- Any group/private booking behavior visible: Private-tour behavior was not enabled.
- TicketMirror capacity note: Capacity should be live remaining seats per slot after imported bookings are counted.

## TicketMirror Mapping Draft

### Suggested Canonical Product
- Suggested canonical product name: Bosphorus Cruise
- Suggested variant name: 2-hour Viator alias
- Suggested slot type:
  - fixed_time

### Suggested Capacity Model
- Capacity per slot: 250
- Capacity source: Visible seat count on each current schedule time slot.
- Needs manual confirmation? no
- Notes: Confirm whether all seasonal rows keep the same 250-seat rule.

### Suggested Provider Alias
- Provider: Viator
- Raw provider product name: Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR
- Transfer variant? no
- GYG/Viator/direct variant? yes
- Notes: Likely an alias of the 2-hour Bosphorus cruise canonical product.

## Open Questions
- Question 1: Do all listed seasonal schedules use the same 11:00, 14:00, and 19:00 departures?
- Question 2: Should recurring-booking support be ignored until TicketMirror has native recurring booking requirements?
