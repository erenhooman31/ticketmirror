# Scheduling UI Gap Audit

Bookeo is used only as functional/operator workflow reference. TicketMirror must keep its own internal dashboard visual language and must not copy Bookeo branding, typography, colors, exact wording, icons, CSS, layout, or trade dress.

## Inspection Scope

Inspected Bookeo Scheduling/Time settings pages read-only for:

- `2 Hours Bosphorus Tour SL-1`
- `GYG 2 Hours Bosphorus Tour SL-(2-3)`
- `1 Hours Bosphorus Tour GYG`
- `gyg yacht`

Inspected local TicketMirror at `http://localhost:8000/settings/tours/4/?tab=scheduling` using the seeded `2 Hours Bosphorus Tour SL-1` activity.

## Bookeo Workflow Observations

- Fixed-departure products show a Current schedule first, with effective dates summarized above the weekly availability.
- Weekly availability is shown by weekday and time, with capacity next to each departure.
- Operators add/edit/remove times as availability entries, not as comma-delimited developer text.
- Other schedules are presented as alternate/future/seasonal date-range rows.
- One-off extra times and unavailable periods are separate from the weekly schedule.
- Empty Other schedules are still shown as a table/list area, not as raw fields.
- The yacht product uses available-hour intervals and special available time slots rather than fixed public departures, but the same operator principle applies: schedules are availability controls, not model fields.

## Current TicketMirror Gaps

Raw/developer-like elements currently visible:

- `Date from`, `Date to`
- `Days of week` as JSON
- `Priority`
- `Recurrence mode`
- `Slot lines`
- raw slot line values such as `11:00,250,120,fixed_time`
- generic `Exception type`
- duplicate labels such as `Date Date` and `Start time Start time`

Fields and concepts that should be hidden or renamed:

- Hide `schedule_kind`; use section titles `Current Schedule` and `Other Schedule`.
- Hide `priority/order`; use backend precedence only.
- Hide `recurrence_mode`; the UI can describe weekly repeating behavior without exposing the internal field.
- Replace `days_of_week` JSON with weekday checkboxes/chips under `Repeats on`.
- Replace `date_from/date_to` with `Applies from` and `Applies until`.
- Replace `slot_type` enum values with human slot type labels.
- Replace `exception_type` enum values with human special-date type labels.

Grouping changes needed:

- Keep exactly two main cards: Current Schedule and Other Schedule.
- Each schedule card should have a summary header with name, status, effective dates, repeat days, active slot count, capacity summary, and an edit/save action.
- Inside each card, group controls into Schedule details, Available times, and Special dates / Blocked dates.
- Other Schedule should include a short functional note that it is for alternate, future, or seasonal scheduling.

Controls that should replace raw fields:

- Weekday checkboxes/chips for repeating days.
- Date inputs for applies-from/until.
- Time inputs for slot and exception times.
- Number inputs for duration and capacity.
- Selects with human labels for slot type and special-date type.
- Tables or compact rows for existing time slots and exceptions.

## Target TicketMirror UI

Each schedule section should function as an operator setup panel:

- Summary header: schedule name, active/inactive badge, effective dates, repeat-days chips, active slot count, capacity summary.
- Schedule details: schedule name, status, applies from, applies until, repeats on, timezone, notes.
- Available times: rows with time, duration, type, capacity, status, and actions.
- Special dates / Blocked dates: rows with date, time, type, capacity impact, reason, status, and actions.
- Empty slots: `No time slots have been added to this schedule yet.`
- Empty exceptions: `No special dates or blocked dates have been added.`

## Screens To Change

- Settings > Tours & Activities > Activity detail > Scheduling tab.
- The shared schedule partial used by Current Schedule and Other Schedule.
- Scheduling forms and POST handlers behind that tab.

## Acceptance Criteria

- The Scheduling tab has exactly two main cards: Current Schedule and Other Schedule.
- Raw/internal labels are not visible: `schedule_kind`, `recurrence_mode`, `days_of_week`, `date_from`, `date_to`, `exception_type`, `slot_type`, `display_settings`.
- Human labels are visible: Current Schedule, Other Schedule, Effective dates, Repeats on, Available times, Capacity, Special dates, Blocked dates.
- Admin users see add/edit/remove or deactivate actions for schedules, slots, and exceptions.
- Operator/viewer users can view the scheduling data but cannot see mutation actions.
- Empty slot and exception states are friendly and operational.
- Validation errors appear next to the relevant fields inside the affected card.
- Existing schedule precedence, capacity calculations, blocked/removed/extra/override exception behavior, seed command, calendar rendering, ingestion alias mapping, and reports continue to pass tests.

## Manual Verification Notes

- Before changes, local TicketMirror exposed raw schedule details, JSON weekdays, raw slot lines, and generic exception forms.
- After changes, local TicketMirror shows `Current Schedule` and `Other Schedule` as the only two main cards on the Scheduling tab.
- Schedule details now use Schedule name, Schedule status, Applies from, Applies until, Repeats on, Timezone, and Notes.
- Available times render as operational rows with Time, Duration, Type, Capacity, Status, and admin-only Edit/Remove actions.
- Special dates / Blocked dates render separately with empty-state text when no rows exist.
- The local browser pass found no visible raw JSON weekday field, slot line textarea, priority/order control, or recurrence-mode control.
- Other Schedule carries the alternate/future/seasonal scheduling note; Current Schedule does not.
