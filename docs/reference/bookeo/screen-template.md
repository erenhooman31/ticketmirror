# Screen Reference Template

Use this template to document a Bookeo-inspired idea in TicketMirror terms before writing application code.

## Screen Name

TicketMirror name:

Reference area:

Status: proposed / accepted / deferred / rejected

## Purpose

Describe the operator or admin job this screen supports in one or two sentences.

## Roles

- Admin:
- Operator:
- Viewer:
- Unauthenticated:

## Entry Points

- Primary navigation:
- Related screens:
- Direct URL pattern:
- Non-JavaScript fallback:

## What The Operator Sees

- Primary sections:
- Row or card types:
- Counts and summaries:
- Status indicators:
- Empty state:
- Error state:
- Permission-denied state:

## Data Shown

| Field | Source | Notes |
| --- | --- | --- |
| Example | `Model.field` or service | Include masking, formatting, or calculation rules. |

## Filters And Controls

| Control | Values | Default | Behavior |
| --- | --- | --- | --- |
| Example filter | All / active | All | Narrows rows without changing capacity math. |

## Actions

| Action | Role | Result | Audit |
| --- | --- | --- | --- |
| Click row | Viewer+ | Opens detail view or modal. | No mutation. |
| Save change | Operator/Admin | Persists allowed fields. | Records old/new values. |

## Click Behavior

- Row click:
- Primary command:
- Secondary command:
- Date navigation:
- Filter change:
- Tab switch:
- Modal close:
- Back/cancel:

## Data Safety

- Personal data displayed:
- Personal data masked:
- Raw provider data exposed:
- Export/download behavior:
- External transmission risk:

## Permissions

- Unauthenticated:
- Viewer:
- Operator:
- Admin:

## Audit And Logging

- Audit event required:
- Old/new values stored:
- System event recorded:
- Log masking:
- Parser/raw-email safety:

## Acceptance Criteria

- Given a permitted user opens the screen, when data exists, then the expected rows and counts are visible.
- Given matching filters are applied, when the result set changes, then counts and capacity calculations remain correct.
- Given a viewer opens the screen, then mutation controls are hidden or disabled.
- Given an operator performs an allowed mutation, then the change is saved and an audit event records old and new values.
- Given no matching records exist, then the screen shows an empty state without errors.
- Given a service error occurs, then the screen shows a recoverable error and does not partially mutate data.

## Open Questions

- Question:
- Assumption:
- Decision needed:
