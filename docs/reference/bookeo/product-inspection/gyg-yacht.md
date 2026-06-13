# Product Inspection: gyg yacht

## Inspection Metadata
- Inspected date: 2026-06-13
- Inspected by: Codex
- Bookeo navigation path: Settings > Tours and activities > gyg yacht
- Product matched exactly? yes
- If not exact, closest visible product name:
- Notes about ambiguity: This product used a `Time settings` tab rather than the `Schedule` label used by the other products.

## General Tab

### Name
- Visible product name: gyg yacht
- Internal/display name notes: Internal nickname observed as `gyg yacht`.

### Display Settings
The product is customer-bookable, integration/API booking is enabled, package-only booking is not enabled, no waiver was selected, no thumbnail was visible, and no video URL was visible.

## Scheduling Tab

### Current Schedule
- Schedule name: Time settings / non-grid timing configuration.
- Active date range: No current weekly schedule grid was visible.
- Days of week: No weekday grid was visible.
- Time slots: No fixed time slots were visible.
- Duration: Not visible in the inspected timing tab.
- Capacity or availability references: No seat-count slot capacity was visible.
- Exceptions / blocked periods: None visible.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: Customer recurring bookings were not enabled; staff recurring bookings were disabled. Participant-detail controls were visible separately.

### Current Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Time settings tab | No weekly fixed-slot grid was visible. | This product may need private/open-time modeling rather than fixed departures. |
| Timing controls | No slot duration, min/max advance, or capacity controls were visible in the same way as the tour products. | Requires manual confirmation before implementation. |
| Edit affordances observed, not opened | No safe read-only schedule-row expansion was available. | Do not implement yacht scheduling from incomplete data. |

### Other Schedule
- Schedule name: None visible.
- Active date range: None visible.
- Days of week: Not applicable.
- Time slots: Not applicable.
- Duration: Not visible.
- Capacity or availability references: Not visible.
- Exceptions / blocked periods: None visible.
- Transfer or pickup timing if visible: None visible.
- Other visible schedule rules: No other-schedule rows were captured.

### Other Schedule Click-Through Notes
| Section clicked | What was visible | TicketMirror relevance |
| --- | --- | --- |
| Other schedule area | No other schedule rows were visible. | Yacht scheduling should stay out of the first fixed-slot implementation. |
| Season row edit affordances observed, not opened | No season rows available. | Requires manual product-owner clarification. |

## People Tab

### Number Of People Per Booking
- Minimum people per booking: Not visible in the captured People view.
- Maximum people per booking: Not visible in the captured People view.
- Capacity/availability implications: No slot capacity was visible; likely needs a private-group or manual capacity model.
- Any group/private booking behavior visible: No explicit private-group capacity was confirmed.
- TicketMirror capacity note: Do not infer yacht capacity from cruise products.

## TicketMirror Mapping Draft

### Suggested Canonical Product
- Suggested canonical product name: Yacht Experience
- Suggested variant name: GYG yacht
- Suggested slot type:
  - private_group

### Suggested Capacity Model
- Capacity per slot: Unknown
- Capacity source: Not visible in inspected timing view.
- Needs manual confirmation? yes
- Notes: Requires separate operator confirmation before TicketMirror implementation.

### Suggested Provider Alias
- Provider: GYG
- Raw provider product name: gyg yacht
- Transfer variant? no
- GYG/Viator/direct variant? yes
- Notes: Separate canonical product, not a Bosphorus cruise alias.

## Open Questions
- Question 1: Is yacht booked as private-group, open-time, or fixed-time inventory?
- Question 2: What is the yacht capacity and duration?
