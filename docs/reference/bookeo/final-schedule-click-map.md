# Bookeo Final Schedule Click Map

Inspection date: 2026-06-14
Inspector: Subagent B - Bookeo Schedule Inspector
Path used: Bookeo > Settings > Tours and activities

Scope was limited to schedule/time areas for:

- Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR
- 1 Hours Bosphorus Tour GYG
- GYG 2 Hours Bosphorus Tour SL-(2-3)
- gyg yacht

No TicketMirror app code was edited. No destructive or externally mutating Bookeo action was submitted. Save, Delete, Ok, Copy, Copy schedule, and Delete old actions were inspected visually or by dialog contents only; Cancel was used to leave edit dialogs/pages.

## Safety Notes

- The in-app browser was available but failed to attach a new webview twice. The connected Chrome Browser profile was used instead and already had an authenticated Bookeo session.
- Existing rows, plus buttons, dropdowns, date fields, time fields, seats fields, and modal/page Cancel buttons were clicked.
- Save/Delete/Ok/Copy submit buttons were not clicked.
- Existing seasonal schedule edit pages were exited with Cancel.
- New/add dialogs were exited with Cancel.

## Fixed-Tour Common Behavior

The three fixed-tour products use the same Schedule tab structure:

- Current schedule
- Other schedules
- Duration

### Current Schedule

Visible layout:

- A section header states the active schedule effective date range.
- A seven-column weekly grid is shown from Monday through Sunday.
- Each weekday header has a plus icon with tooltip/meaning `Add a tour`.
- Each time row is clickable and has tooltip/meaning `Edit`.
- Below the grid are `Copy...` and `Change seats for all times`.

Click behavior:

- Clicking an existing time row opens an `Edit tour` modal.
- Clicking a weekday plus opens an `Edit new tour` modal.
- Clicking `Copy...` opens a `Copy to other days` modal.
- Clicking `Change seats for all times` opens a `Seats` modal.

Existing time row modal:

- Title: `Edit tour`
- Fields:
  - `Day`: read-only text, for example `Monday`
  - `Start`: native select containing only the selected current time for the clicked row
  - `Seats`: text input with the current seat count, normally `250`
- Buttons:
  - `Save`: present, not clicked
  - `Cancel`: clicked; closes modal without submitting
  - `Delete`: present, not clicked

Add-tour plus modal:

- Title: `Edit new tour`
- Fields:
  - `Day`: read-only text for the selected weekday
  - `Start`: native select, default `9:00`
  - `Seats`: native select with `1` through `20` and `Other...`, default `10`
- Buttons:
  - `Save`: present, not clicked
  - `Cancel`: clicked; closes modal without submitting
  - `Delete`: present, not clicked

Copy modal:

- Title/text: `Copy to other days`
- Fields:
  - `From`: weekday native select, defaulting to `Monday` in the inspected flow
  - `To`: weekday checkboxes for Monday through Sunday
- Buttons:
  - `Copy`: present, not clicked
  - `Cancel`: clicked; closes modal without submitting

Bulk seats modal:

- Title/text: `Seats`
- Text: `You can change the number of seats available for all times in the schedule, in one go`
- Field:
  - `Seats`: native select with `1` through `20` and `Other...`, default `10`
- Buttons:
  - `Save`: present, not clicked
  - `Cancel`: clicked; closes modal without submitting

### Other Schedules

Visible layout:

- A table with columns `Start`, `End`, and `Name`.
- A `New/change schedule` button below the table.

Existing row click behavior:

- Clicking an Other schedules row navigates to a full schedule-edit page, not a modal.
- The edit page contains:
  - `Name` text input
  - `Start date` native selects for day, month, and year
  - `End date` informational text or an effective end date implied by the adjacent schedule range
  - a weekly schedule grid with the same plus/time-row behavior as Current schedule
  - `Copy...`
  - `Change seats for all times`
  - `Copy schedule`
  - right-side `Save`, `Cancel`, and `Delete`
- Date dropdowns were clicked and inspected.
- `Save`, `Delete`, and `Copy schedule` were not clicked.
- `Cancel` was clicked to return to the main Schedule tab.

New/change schedule behavior:

- Opens a `Copy schedule` modal.
- Field:
  - source schedule native select, listing existing seasons and `Start with an empty schedule`
- Buttons:
  - `Ok`: present, not clicked
  - `Cancel`: clicked; closes modal without submitting

### Duration

Visible layout:

- Section title: `Duration`
- Help text: `Specify the duration of this tour.`
- Field group: `* Duration:`
- Controls:
  - days native select: `0`, `1`, `2`, `3`, `4`, `5`, `6`, `7`, `Other...`
  - hours native select: `0` through `24`
  - minutes native select: `00`, `05`, `10`, `15`, `20`, `25`, `30`, `35`, `40`, `45`, `50`, `55`

Click behavior:

- Clicking each duration field opens the native dropdown.
- There is no modal for Duration.
- The page-level `Save` and `Cancel` buttons remain visible on the right; neither was used for Duration because no value was changed.

## Product: Bosphorus Cruise Tour In Istanbul For 2 Hours VIATOR

### Current Schedule

Effective range:

- Saturday, 4 April 2026 to Friday, 31 July 2026

Weekly rows:

| Day | Times |
| --- | --- |
| Monday | 11:00 (250 seats), 14:00 (250 seats), 19:00 (250 seats) |
| Tuesday | 11:00 (250 seats), 14:00 (250 seats), 19:00 (250 seats) |
| Wednesday | 11:00 (250 seats), 14:00 (250 seats), 19:00 (250 seats) |
| Thursday | 11:00 (250 seats), 14:00 (250 seats), 19:00 (250 seats) |
| Friday | 11:00 (250 seats), 14:00 (250 seats), 19:00 (250 seats) |
| Saturday | 11:00 (250 seats), 14:00 (250 seats), 19:00 (250 seats) |
| Sunday | 11:00 (250 seats), 14:00 (250 seats), 19:00 (250 seats) |

Clicked:

- Monday `11:00 (250 seats)` row/time.
- Existing-time modal `Start` dropdown and `Seats` textbox.
- Existing-time modal `Cancel`.
- Monday plus button.
- Add-tour modal `Start` dropdown and `Seats` dropdown.
- Add-tour modal `Cancel`.
- `Copy...`, then copy modal `From` dropdown and destination weekday checkboxes, then `Cancel`.
- `Change seats for all times`, then seats dropdown, then `Cancel`.

Skipped:

- Existing-time modal `Save` and `Delete`.
- Add-tour modal `Save` and `Delete`.
- Copy modal `Copy`.
- Bulk seats modal `Save`.

### Other Schedules

Rows:

| Start | End | Name |
| --- | --- | --- |
| 1/4/2027 | blank | SUMMER season 2027 |
| 1/10/2026 | 31/3/2027 | WINTER season |
| 1/8/2026 | 30/9/2026 | AUTMUN season |
| 1/4/2026 | 3/4/2026 | summer season |
| 1/10/2025 | 31/3/2026 | WINTER season |
| 19/5/2024 | 30/9/2025 | Default season |

Clicked:

- First existing row, `1/4/2027 SUMMER season 2027`.
- Edit page `Name` field.
- Edit page start-date day, month, and year dropdowns.
- Edit page `Cancel`.
- `New/change schedule`.
- Copy-schedule source dropdown.
- Copy-schedule modal `Cancel`.

Skipped:

- Edit page `Save`, `Delete`, `Copy...`, `Change seats for all times`, and `Copy schedule`.
- Copy-schedule modal `Ok`.

### Duration

Selected value:

- `0` days, `2` hours, `00` minutes

Clicked:

- days dropdown
- hours dropdown
- minutes dropdown

Skipped:

- page-level `Save`
- page-level `Cancel`

## Product: 1 Hours Bosphorus Tour GYG

### Current Schedule

Effective range:

- Effective since Tuesday, 17 February 2026

Weekly rows:

| Day | Times |
| --- | --- |
| Monday | 17:00 (250 seats) |
| Tuesday | 17:00 (250 seats) |
| Wednesday | 17:00 (250 seats) |
| Thursday | 17:00 (250 seats) |
| Friday | 17:00 (250 seats) |
| Saturday | 17:00 (250 seats) |
| Sunday | 17:00 (250 seats) |

Clicked:

- Monday `17:00 (250 seats)` row/time.
- Existing-time modal `Start` dropdown and `Seats` textbox.
- Existing-time modal `Cancel`.
- Monday plus button.
- Add-tour modal `Start` dropdown and `Seats` dropdown.
- Add-tour modal `Cancel`.
- `Change seats for all times`, then seats dropdown, then `Cancel`.

Skipped:

- Existing-time modal `Save` and `Delete`.
- Add-tour modal `Save` and `Delete`.
- Bulk seats modal `Save`.

### Other Schedules

Rows:

- Header only: `Start`, `End`, `Name`
- No existing Other schedules rows were present.

Clicked:

- `New/change schedule`.
- Copy-schedule source dropdown.
- Copy-schedule modal `Cancel`.

Copy-schedule dropdown options:

- `Copy from winter season (17/2/2026 - ) (current schedule)`
- `Start with an empty schedule`

Skipped:

- Copy-schedule modal `Ok`.

### Duration

Selected value:

- `0` days, `1` hour, `00` minutes

Clicked:

- days dropdown
- hours dropdown
- minutes dropdown

Skipped:

- page-level `Save`
- page-level `Cancel`

## Product: GYG 2 Hours Bosphorus Tour SL-(2-3)

### Current Schedule

Effective range:

- Wednesday, 1 April 2026 to Friday, 31 July 2026

Weekly rows:

| Day | Times |
| --- | --- |
| Monday | 14:00 (250 seats), 19:00 (250 seats) |
| Tuesday | 14:00 (250 seats), 19:00 (250 seats) |
| Wednesday | 14:00 (250 seats), 19:00 (250 seats) |
| Thursday | 14:00 (250 seats), 19:00 (250 seats) |
| Friday | 14:00 (250 seats), 19:00 (250 seats) |
| Saturday | 14:00 (250 seats), 19:00 (250 seats) |
| Sunday | 14:00 (250 seats), 19:00 (250 seats) |

Clicked:

- Monday `14:00 (250 seats)` row/time.
- Existing-time modal `Start` dropdown and `Seats` textbox.
- Existing-time modal `Cancel`.
- Monday plus button.
- Add-tour modal `Start` dropdown and `Seats` dropdown.
- Add-tour modal `Cancel`.
- `Change seats for all times`, then seats dropdown, then `Cancel`.

Skipped:

- Existing-time modal `Save` and `Delete`.
- Add-tour modal `Save` and `Delete`.
- Bulk seats modal `Save`.

### Other Schedules

Rows:

| Start | End | Name |
| --- | --- | --- |
| 1/10/2026 | blank | winter season2 |
| 1/8/2026 | 30/9/2026 | autumn season |
| 4/2/2026 | 31/3/2026 | winter season |
| 1/10/2025 | 3/2/2026 | winter season |
| 19/5/2024 | 30/9/2025 | Default season |

Clicked:

- First existing row, `1/10/2026 winter season2`.
- Edit page `Name` field.
- Edit page start-date day, month, and year dropdowns.
- Edit page `Cancel`.
- `New/change schedule`.
- Copy-schedule source dropdown.
- Copy-schedule modal `Cancel`.

Copy-schedule dropdown options:

- `Copy from winter season2 (1/10/2026 - )`
- `Copy from autumn season (1/8/2026 - 30/9/2026 )`
- `Copy from summer season (1/4/2026 - 31/7/2026 ) (current schedule)`
- `Copy from winter season (4/2/2026 - 31/3/2026 )`
- `Copy from winter season (1/10/2025 - 3/2/2026 )`
- `Copy from Default season (19/5/2024 - 30/9/2025 )`
- `Start with an empty schedule`

Skipped:

- Edit page `Save`, `Delete`, `Copy...`, `Change seats for all times`, and `Copy schedule`.
- Copy-schedule modal `Ok`.

### Duration

Selected value:

- `0` days, `2` hours, `00` minutes

Clicked:

- days dropdown
- hours dropdown
- minutes dropdown

Skipped:

- page-level `Save`
- page-level `Cancel`

## Product: gyg yacht

This product does not use the fixed-tour Schedule tab labels. It opens `Time settings` and does not show sections named `Current schedule`, `Other schedules`, or `Duration`.

Nearest observed equivalents:

- `Base duration`
- `Available hours`
- `Special available time slots`

### Exact Section Availability

| Requested section | Present? | Observed replacement |
| --- | --- | --- |
| Current schedule | No | Available hours |
| Other schedules | No | Special available time slots |
| Duration | No | Base duration |

### Base Duration

Selected value:

- `1` hour, `00` minutes

Controls:

- hours native select: `0` through `24`, selected `1`
- minutes native select: `00`, `05`, `10`, `15`, `20`, `25`, `30`, `35`, `40`, `45`, `50`, `55`, selected `00`

Clicked:

- hours dropdown
- minutes dropdown

Skipped:

- page-level `Save`
- page-level `Cancel`

### Available Hours

Visible mode:

- `Use a specific schedule for this tour`

Weekly rows:

| Day | Interval |
| --- | --- |
| Monday | 8:00-24:00 |
| Tuesday | 8:00-24:00 |
| Wednesday | 8:00-24:00 |
| Thursday | 8:00-24:00 |
| Friday | 8:00-24:00 |
| Saturday | 8:00-24:00 |
| Sunday | 8:00-24:00 |

Existing interval click behavior:

- Clicking `8:00-24:00` opens an `Edit interval` modal.
- Fields:
  - `From`: native select, selected `8:00`
  - `To`: native select, selected `24:00`
- Buttons:
  - `Save`: present, not clicked
  - `Cancel`: clicked; closes modal without submitting
  - `Delete`: present, not clicked

Add interval click behavior:

- Clicking the weekday plus opens an `Edit interval` modal.
- Fields:
  - `From`: native select, default `9:00`
  - `To`: native select, default `18:00`
- Buttons:
  - `Save`: present, not clicked
  - `Cancel`: clicked; closes modal without submitting
  - `Delete`: present, not clicked

### Special Available Time Slots

Visible table:

- Columns: `From`, `To`, `Description`
- No rows were listed.
- Buttons: `New`, `Delete old`

New click behavior:

- Clicking `New` opens an `Edit interval` modal.
- Fields:
  - `From` date: day/month/year dropdowns, defaulted during inspection to `14 June 2026`
  - `From` time: native select, default `9:00`
  - `All day` checkbox
  - `To` date: day/month/year dropdowns, defaulted during inspection to `14 June 2026`
  - `To` time: native select, default `10:00`
  - `Repeat`: native select, default `do not repeat`
  - `Description`: text input, empty
- Buttons:
  - `Save`: present, not clicked
  - `Cancel`: clicked; closes modal without submitting
  - `Delete`: present, not clicked

Skipped:

- `Save`
- `Delete`
- `Delete old`

## Intentionally Skipped Destructive Submits

These controls were intentionally not submitted anywhere in Bookeo:

- modal `Save`
- page-level `Save`
- modal `Delete`
- page-level `Delete`
- `Delete old`
- copy modal `Copy`
- schedule modal `Ok`
- `Copy schedule`

Only Cancel/close actions were used to exit inspection surfaces.
