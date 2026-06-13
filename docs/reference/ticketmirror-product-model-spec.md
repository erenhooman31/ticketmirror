# TicketMirror Product, Schedule, And Capacity Model Spec

Source scope: `docs/reference/bookeo/product-inspection/*`, `docs/reference/bookeo/feature-backlog.md`, and `docs/reference/bookeo/workflows.md`.

This specification translates the inspected Bookeo configuration into TicketMirror-owned concepts. TicketMirror must not copy Bookeo branding, wording, visual design, icons, CSS, layout, or trade dress.

## Purpose

TicketMirror needs one canonical operational model for products, variants, provider aliases, schedules, slots, and capacity. The model must support operator workflows for dashboard capacity, calendar capacity investigation, slot detail, and admin-only product/schedule setup.

The Bookeo products should be treated as historical source records and provider-facing aliases, not as the primary TicketMirror product structure.

## A. Canonical Product Model

Canonical products represent real business products sold through one or more providers. They are the unit operators understand operationally.

| Canonical product | Category | Duration model | Slot behavior | Capacity pattern |
| --- | --- | --- | --- | --- |
| Bosphorus Cruise | Cruise | Variant-defined: 1 hour or 2 hours | Fixed-time departures | Usually 250 seats per slot |
| Istanbul Old City and Bosphorus Tour | Land and cruise tour | Half-day until confirmed | Fixed morning departure | 50 seats per slot |
| Istanbul Two Continents Tour | Land and cruise tour | Full-day until confirmed | Fixed morning departure | 50 seats per slot |
| Yacht Experience | Yacht/private experience | Unknown; manual confirmation required | Private-group or open-time candidate | Unknown |

### Canonical Product Fields

- `name`: operator-facing product name.
- `category`: cruise, land_and_cruise_tour, yacht_experience, or future category.
- `active_state`: active, inactive, or archived.
- `duration_model`: fixed_minutes, half_day, full_day, private_group_unknown, or manual_confirmation_required.
- `default_duration_minutes`: required for fixed-minute products once confirmed.
- `slot_behavior`: fixed_time, half_day, full_day, open_time, or private_group.
- `operational_notes`: internal notes such as pickup uncertainty, shared-capacity caveats, or source-listing meaning.
- `admin_only`: product and schedule configuration must be admin-only.

### Canonical Product Rules

- Operators consume canonical products and slots; they do not edit setup.
- Provider-specific naming must not create duplicate canonical products when the operational product is the same.
- Historical Bookeo product names should be retained as aliases for matching imports and audit, not as primary product names.
- Inactive products remain available for historical bookings and audit trails.

## B. Variant Model

Variants represent operationally meaningful differences under a canonical product: duration, transfer inclusion, departure group, or special product mode.

| Canonical product | Variant | Slot type | Provider mapping rules | Alias mapping rules |
| --- | --- | --- | --- | --- |
| Bosphorus Cruise | 2-hour standard cruise | fixed_time | Viator and GYG aliases can map here when no transfer is present. | Match 2-hour Bosphorus cruise names, including Viator V1/V2 names and GYG SL group names. |
| Bosphorus Cruise | 2-hour transfer cruise | fixed_time | Viator transfer product maps here. | Match explicit `TRANSFER` source names only until pickup rules are confirmed. |
| Bosphorus Cruise | 2-hour GYG SL-1 departure group | fixed_time | GYG product with SL-1 nickname maps to the 11:00 departure group. | Treat `SL-1` as a departure-group alias, not a canonical product. |
| Bosphorus Cruise | 2-hour GYG SL-(2-3) departure group | fixed_time | GYG product with SL-(2-3) name maps to 14:00 and 19:00 departure groups. | Treat `SL-(2-3)` as a departure-group alias, not a canonical product. |
| Bosphorus Cruise | 1-hour cruise | fixed_time | Viator and GYG one-hour products map here. | Match one-hour Bosphorus names across providers. |
| Istanbul Old City and Bosphorus Tour | Provider alias variant | half_day | Viator and GYG aliases map here unless operations confirms separate inventory. | Time difference between 8:30 and 8:15 must be preserved as a schedule difference or pickup/start-time caveat. |
| Istanbul Two Continents Tour | Provider alias variant | full_day | Viator and GYG aliases map here unless operations confirms separate inventory. | Both visible aliases use 8:15 current time. |
| Yacht Experience | GYG yacht | private_group | GYG yacht maps here. | Do not merge with Bosphorus Cruise based on provider alone. |

### Variant Fields

- `canonical_product_id`
- `variant_name`
- `slot_type`
- `duration_minutes` where fixed.
- `is_transfer_variant`
- `is_private_group_candidate`
- `default_capacity`
- `needs_manual_confirmation`
- `source_notes`

### Provider Alias Fields

- `provider`: GYG, Viator, direct, or future provider.
- `raw_provider_product_name`
- `raw_internal_display_name`
- `source_system`: Bookeo inspection or future importer.
- `canonical_product_id`
- `variant_id`
- `slot_group_hint`: optional values such as `SL-1`, `SL-(2-3)`, transfer, one-hour, or two-hour.
- `active_state`

## C. Scheduling Model

TicketMirror schedules are effective-date definitions that generate or resolve operational slots. A slot is the date, time, product variant, and capacity unit that operators see in dashboard and calendar workflows.

### Core Concepts

- `ScheduleSet`: all schedules for one variant or alias mapping.
- `ActiveSchedule`: the schedule whose effective date range applies to a target service date.
- `FutureSchedule`: a schedule with a start date after the current active schedule.
- `HistoricalSchedule`: a schedule with an end date before the inspected/current operating date.
- `AlternateSchedule`: a schedule with an effective date range that can become active for specific dates. This is the general abstraction for Bookeo "Other schedule" rows.
- `SlotTemplate`: weekday/time/capacity rule inside a schedule.
- `GeneratedSlot`: concrete date/time/capacity record or computed view for a service date.

### Current Schedule Mapping Rules

- Bookeo Current schedule maps to TicketMirror `ActiveSchedule` for the inspected effective date.
- The visible weekday/time grid maps to `SlotTemplate` rows.
- Slot time and capacity belong to the `SlotTemplate`, not only to the product.
- Duration and booking-window rules belong to the variant schedule settings unless operations chooses product-level defaults.
- Blocked-period mode maps to `ScheduleBlockRule`, even when no blocked periods are listed.

### Other Schedule Meaning

Bookeo Other schedule rows should map to `AlternateSchedule`, with status derived from dates:

- If `start_date` is in the future relative to the service date: `FutureSchedule`.
- If `end_date` is before the service date: `HistoricalSchedule`.
- If the date range includes the service date but is not selected as current due to source behavior: `AlternateSchedule` with a conflict flag.

TicketMirror should not use "Other schedule" as a product-level catch-all. It is a set of dated schedule alternatives.

### Multiple Schedule Interaction

- Each variant can have zero or more schedules.
- Each schedule has `effective_start_date` and optional `effective_end_date`.
- A generated slot for a date must be produced by exactly one active schedule per variant.
- If no schedule matches a date, the variant has no sellable/generated slot for that date unless a manual slot override exists.
- If multiple schedules match a date, TicketMirror must reject the configuration or use a deterministic precedence rule recorded in audit.

### Active Priority Rules

1. Manual blocked/closed slot override wins over all generated availability.
2. Manual slot override wins over generated schedule templates for that exact date/time.
3. Schedule with the most specific matching effective date range wins only if overlap is explicitly allowed by admin policy.
4. Otherwise, overlapping effective ranges are invalid and must be rejected before save.
5. Future schedules do not affect current slots until the service date falls inside their date range.
6. Historical schedules remain for audit/import reconciliation but do not generate future slots.

### Schedule Types From Inspection

- `fixed_time`: all inspected non-yacht products use fixed visible departures.
- `half_day`: Old City and Bosphorus is a half-day candidate, pending duration confirmation.
- `full_day`: Two Continents is a full-day candidate, pending duration confirmation.
- `private_group`: yacht is a candidate only; capacity and timing were not visible.

## D. Capacity Model

TicketMirror capacity must support the dashboard, calendar, and slot detail workflows. Capacity is operational: it answers how many seats are available for a product/time/date after bookings are imported and classified.

### Where Capacity Lives

- Primary capacity lives on the `SlotTemplate` or generated `Slot`, because inspected Bookeo schedules showed capacity beside each time slot.
- Product-level capacity can be a default copied into new slot templates, but it is not the source of truth once a slot exists.
- People-tab minimum and maximum people per booking are booking-party constraints, not total slot capacity.

### People Tab Mapping

- `minimum_people_per_booking` maps from the People tab minimum party size where visible.
- `maximum_people_per_booking` maps from the People tab maximum party size where visible.
- For most inspected products, the docs recorded minimum 1 and maximum 20 where the full control set was visible.
- These values validate booking party size but do not define total available seats.
- Yacht People tab capacity was not visible and must not be inferred.

### Real-Time Capacity Calculation

For each generated slot:

```text
effective_capacity = slot.capacity
active_booked_pax = sum(participant_count for bookings in confirmed or operationally active statuses)
pending_pax = sum(participant_count for bookings in pending or manual-review statuses when policy reserves capacity)
canceled_pax = ignored for active capacity
remaining_capacity = effective_capacity - active_booked_pax - reserved_pending_pax
```

Manual-review bookings need a policy decision:

- Conservative mode: reserve manual-review pax until resolved.
- Lenient mode: show them separately and do not reduce remaining capacity.

The workflows require manual-review indicators and mathematically correct capacity totals. The recommended default is conservative mode for overbooking prevention.

### Overbooking Prevention And Flagging

- A booking cannot be accepted into an active slot if `participant_count` exceeds `remaining_capacity`, unless an admin override exists.
- Provider-imported overcapacity should not be silently rejected. It should create a capacity-risk flag and remain visible for operators.
- Canceled bookings remain visible for audit but do not count toward active booked capacity.
- Blocked slots are different from full slots: blocked slots prevent new internal bookings regardless of remaining seats.
- Capacity changes must be audited when they affect future slots.

### Capacity Patterns

- Bosphorus Cruise fixed-time variants: 250 seats per visible slot.
- Old City and Bosphorus: 50 seats per visible slot.
- Two Continents: 50 seats per visible slot.
- Yacht: unknown; manual confirmation required before implementation.
- Transfer variant: visible cruise capacity is 250, but pickup capacity may require a later separate constraint.

## E. Scheduling Normalization Rules

### Concept Translation

| Bookeo concept | TicketMirror term | Notes |
| --- | --- | --- |
| Product/tour/activity | CanonicalProduct plus ProviderAlias | Raw source product names should map into canonical business products. |
| Display nickname | Internal alias/display note | Useful for matching provider or operational labels. |
| Current schedule | ActiveSchedule | Effective schedule for the inspected/current service range. |
| Other schedule | AlternateSchedule | Derive FutureSchedule or HistoricalSchedule by date. |
| Weekday grid | SlotTemplate set | Each weekday/time/capacity row becomes one or more slot templates. |
| Time slot seat count | Slot capacity | Primary capacity source. |
| Number of people per booking | Party-size constraint | Not total slot capacity. |
| Blocked/unavailable periods | ScheduleBlockRule | Needed even if inspected products had none listed. |
| Private tour/group behavior | PrivateGroupMode | Deferred unless yacht or private product is confirmed. |
| Arrival reminder | Operational arrival note | Defer customer-facing behavior. |

### Precedence Rules

- `ActiveSchedule` is selected by service date, not by current wall-clock date alone.
- `FutureSchedule` becomes active when its start date is reached and no higher-priority override applies.
- `HistoricalSchedule` is retained for audit and import matching but does not generate future availability.
- Admin schedule save must reject invalid date ranges.
- Admin schedule save must reject overlapping ranges unless a deterministic precedence rule is explicitly selected and audited.
- Duplicate weekday/time entries should be rejected or normalized deterministically before save.

### Recommended Abstraction Decision

Use `AlternateSchedule` as the stored abstraction for Bookeo "Other schedule" rows. Expose derived labels:

- Future schedule: alternate schedule whose start date is after the relevant service date.
- Historical schedule: alternate schedule whose end date is before the relevant service date.
- Active schedule: alternate or current schedule whose range contains the relevant service date.

This avoids separate incompatible tables for future and past schedules while preserving operator language.

## F. Edge Cases From The Inspected Products

### Duplicate Products With Different Names

- Two Viator 2-hour Bosphorus products appear to represent the same canonical product and same 11:00/14:00/19:00 slot pattern.
- The two one-hour Bosphorus products appear to differ by provider alias only.
- Old City and Two Continents each have Viator and GYG products that likely map to the same canonical products.

TicketMirror should resolve these by provider alias mapping, not duplicate canonical product records.

### Transfer Vs Non-Transfer

- The transfer product is a variant under Bosphorus Cruise, not a separate canonical product by default.
- Transfer pickup timing was not visible in the inspected scheduling area.
- Do not implement pickup capacity or pickup windows until confirmed.
- Transfer bookings may share the 250-seat cruise capacity but may later need an additional pickup constraint.

### SL-1 And SL-(2-3)

- `SL-1` is associated with the 11:00 GYG 2-hour departure.
- `SL-(2-3)` is associated with the 14:00 and 19:00 GYG 2-hour departures.
- These should be modeled as provider slot-group hints or alias rules, not canonical products.
- Operations must confirm whether `SL` means sales listing, sailing line, slot line, or another operational grouping.

### Yacht Special Case

- The yacht product used Time settings instead of the normal Schedule tab label.
- No fixed slots, slot capacity, or standard schedule rows were visible.
- It should be modeled as a separate Yacht Experience canonical product with private-group/open-time status unresolved.
- Do not infer yacht capacity, duration, or schedule behavior from cruise products.

### Multi-Product Similarity Groups

| Similarity group | Products | Recommended handling |
| --- | --- | --- |
| 2-hour Bosphorus standard | Two Viator 2-hour aliases, GYG SL-1, GYG SL-(2-3) | One canonical product, multiple variants/alias rules by provider and departure group. |
| 2-hour Bosphorus transfer | Viator transfer product | Variant under Bosphorus Cruise with transfer flag. |
| 1-hour Bosphorus | Viator one-hour, GYG one-hour | One variant under Bosphorus Cruise with provider aliases. |
| Old City and Bosphorus | Viator Old City, GYG Old City | One canonical product with provider aliases; time difference requires confirmation. |
| Two Continents | Viator Two Continents, GYG Two Continents | One canonical product with provider aliases. |
| Yacht | GYG yacht | Separate canonical product requiring manual confirmation. |

## Bookeo Product To TicketMirror Mapping

| Bookeo product | TicketMirror canonical product | Variant | Provider alias | Schedule type | Current slot times | Capacity | Capacity source | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR | Bosphorus Cruise | 2-hour standard cruise | Viator | fixed_time | 11:00, 14:00, 19:00 | 250 per slot | Current schedule slot count | Viator alias V1. |
| 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR | Bosphorus Cruise | 2-hour standard cruise | Viator | fixed_time | 11:00, 14:00, 19:00 | 250 per slot | Current schedule slot count | Viator alias V2. |
| 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER | Bosphorus Cruise | 2-hour transfer cruise | Viator | fixed_time | 11:00, 14:00, 19:00 | 250 per slot | Current schedule slot count | Transfer pickup timing not visible. |
| 2 Hours Bosphorus Tour SL-1 | Bosphorus Cruise | 2-hour GYG SL-1 departure group | GYG | fixed_time | 11:00 | 250 per slot | Current schedule slot count | SL-1 likely maps to first departure. |
| GYG 2 Hours Bosphorus Tour SL-(2-3) | Bosphorus Cruise | 2-hour GYG SL-(2-3) departure group | GYG | fixed_time | 14:00, 19:00 | 250 per slot | Current schedule slot count | SL-(2-3) likely maps to later departures. |
| Istanbul Old City And Bosphorus Tour | Istanbul Old City and Bosphorus Tour | Viator alias | Viator | half_day | 8:30 | 50 per slot | Current schedule slot count | Duration needs confirmation. |
| Istanbul Two Continents Tour By Bus And Bosphorus Cruise | Istanbul Two Continents Tour | Viator alias | Viator | full_day | 8:15 | 50 per slot | Current schedule slot count | Duration needs confirmation. |
| Istanbul Old City And Bosphorus Tour - GYG | Istanbul Old City and Bosphorus Tour | GYG alias | GYG | half_day | 8:15 | 50 per slot | Current schedule slot count | Time differs from Viator alias. |
| Istanbul Two Continents Tour By Bus And Bosphorus Cruise - GYG | Istanbul Two Continents Tour | GYG alias | GYG | full_day | 8:15 | 50 per slot | Current schedule slot count | Other schedules not captured. |
| 1 Hours Bosphorus Tour viator | Bosphorus Cruise | 1-hour cruise | Viator | fixed_time | 17:00 | 250 per slot | Current schedule slot count | One-hour variant. |
| 1 Hours Bosphorus Tour GYG | Bosphorus Cruise | 1-hour cruise | GYG | fixed_time | 17:00 | 250 per slot | Current schedule slot count | Likely shares one-hour inventory with Viator alias. |
| gyg yacht | Yacht Experience | GYG yacht | GYG | private_group candidate | No fixed slots visible | Unknown | Not visible | Separate special case; manual confirmation required. |

## Admin Workflow Implications

- Product and schedule setup belongs under Settings and must be role-gated to admins.
- Admins configure canonical products, aliases, active state, duration, schedule names, weekday slots, seasonal date ranges, and capacity.
- Operators view configured products in dashboard, calendar, and slot detail but do not modify setup.
- Schedule changes must be deterministic, validated, and audited.
- Product filters and booking search must narrow display without corrupting slot-wide capacity totals.

## Explicit Non-Goals

- Do not implement public booking, marketing, pricing seasons, waivers, reminders, or customer messaging from this spec.
- Do not implement Bookeo-style editing flows.
- Do not implement transfer pickup logic until operations confirms source and rules.
- Do not implement yacht capacity or private-group behavior until manually confirmed.
- Do not create Django models, migrations, routes, templates, or CSS from this document.

## Open Decisions Before Implementation

- Confirm whether all Bosphorus cruise aliases share one physical capacity pool per departure.
- Confirm whether transfer bookings consume only boat seats or also pickup capacity.
- Confirm whether Old City and Two Continents GYG/Viator aliases share inventory.
- Confirm whether Old City 8:15 versus 8:30 is a pickup offset, provider display difference, or separate departure.
- Confirm yacht duration, capacity, and scheduling mode.
- Decide whether manual-review bookings reserve capacity by default; recommended default is yes.
