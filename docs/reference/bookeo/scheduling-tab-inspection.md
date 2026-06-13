# Bookeo Scheduling Tab Inspection

Bookeo is used only as functional inspiration. TicketMirror must not copy Bookeo branding, exact visual design, text, icons, CSS, or trade dress.

## Scope

The inspected Bookeo product set contains 12 products from `docs/reference/bookeo/product-inspection/*`. The Scheduling tab was inspected in detail on the matching product page for `2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER`, then cross-checked against the product-inspection summaries for the remaining products.

## Exact Product Matches

| # | Bookeo product | Current schedule pattern | Capacity pattern | Other schedule pattern |
|---|---|---|---|---|
| 1 | Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR | 11:00, 14:00, 19:00 | 250 per slot | Seasonal rows present |
| 2 | 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR | 11:00, 14:00, 19:00 | 250 per slot | Seasonal rows present |
| 3 | 2 Hours Bosphorus Cruise Boat Tour in Istanbul VIATOR TRANSFER | 11:00, 14:00, 19:00 | 250 per slot | Winter/default seasonal rows present |
| 4 | 2 Hours Bosphorus Tour SL-1 | 11:00 | 250 per slot | Default seasonal row present |
| 5 | GYG 2 Hours Bosphorus Tour SL-(2-3) | 14:00, 19:00 | 250 per slot | Multiple seasonal rows present |
| 6 | Istanbul Old City And Bosphorus Tour | 08:30 | 50 per slot | Default seasonal row present |
| 7 | Istanbul Two Continents And Bosphorus Tour | 08:15 | 50 per slot | Default seasonal row present |
| 8 | Istanbul Old City And Bosphorus Tour GYG | 08:15 | 50 per slot | Default seasonal row present |
| 9 | Two Continents And Bosphorus Tour GYG | 08:15 | 50 per slot | No other schedule rows visible |
| 10 | 1 Hours Bosphorus Tour viator | 17:00 | 250 per slot | No other schedule rows visible |
| 11 | 1 Hours Bosphorus Tour GYG | 17:00 | 250 per slot | No other schedule rows visible |
| 12 | gyg yacht | No fixed public slots visible | Manual/private capacity | No other schedule rows visible |

## Operator Sections Observed

### Current Schedule

The operator sees the active weekly schedule for the product. It shows effective date, weekdays, each configured departure time, and seats per time. Each weekday can have one or more slots. The deep-inspected transfer product showed 11:00, 14:00, and 19:00 on each weekday with 250 seats.

TicketMirror mapping:

- `ActivitySchedule.schedule_kind = current`
- `ActivitySchedule.active`
- `ActivitySchedule.date_from/date_to`
- `ActivitySchedule.days_of_week`
- `ActivitySchedule.timezone`
- `ActivityScheduleSlot.start_time/end_time/duration_minutes/slot_type/capacity`

### Other Schedule

The operator sees named alternate schedules with start and end dates. These represent seasonal or future schedule definitions. The inspected transfer product showed a winter season and a default season.

TicketMirror mapping:

- `ActivitySchedule.schedule_kind = other`
- `ActivitySchedule.name`
- `ActivitySchedule.date_from/date_to`
- `ActivitySchedule.priority`
- `ActivitySchedule.active`

### Additional One-Off Times

The operator can add a specific date, start time, and seats. This is not a recurring weekly schedule. It is an exception that creates availability for one date.

TicketMirror mapping:

- `ActivityScheduleException.exception_type = extra_slot`
- `ActivityScheduleException.date/start_time/end_time/capacity`

### Unavailable Periods

The operator can define periods where the product is unavailable or only available for selected periods. TicketMirror treats this as schedule exceptions instead of a separate product-level calendar.

TicketMirror mapping:

- `blocked` or `closed`: suppress matching normal availability
- `removed_slot`: suppress one matching time
- `override_capacity`: change seats for one matching time

## TicketMirror Behavior

Schedule selection for a service date follows these rules:

1. Only active schedules are considered.
2. The service date must be inside the schedule date range when a range exists.
3. The service weekday must be allowed by `days_of_week`; an empty list means every day.
4. The most specific date range wins.
5. If specificity ties, `current` wins over `other`.
6. If still tied, lower `priority` wins.
7. If still tied, stable database id order is used as the final deterministic tiebreak.

Exception precedence:

1. `blocked`, `closed`, and `removed_slot` remove generated slot availability.
2. `override_capacity` replaces the slot capacity for the date/time.
3. `extra_slot` adds a one-off availability row for the date/time.

## Acceptance Criteria

- Scheduling tab contains exactly two major sections: Current schedule and Other schedule.
- Each section supports active state, name, effective date range, weekdays, timezone, priority, recurrence mode, notes, slot definition, and exception management.
- Slot validation rejects duplicate times, negative capacity, invalid duration, invalid weekday values, and invalid date ranges.
- Exception validation rejects dates outside the schedule range and requires start time/capacity where needed.
- Calendar availability is generated from active schedules, selected precedence, slots, and exceptions.
- Confirmed and modified bookings consume capacity. Pending and manual-review bookings are visible but do not consume confirmed capacity. Cancelled, rejected, parse-failed, and duplicate-ignored bookings are excluded from capacity.
- Over-capacity slots are flagged by negative remaining capacity.
