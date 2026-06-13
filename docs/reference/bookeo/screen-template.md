# Screen Reference Template

Use this template when documenting a Bookeo-inspired screen before implementing it in TicketMirror.

## Screen Name

Short TicketMirror name for the screen.

## Purpose

One or two sentences explaining the operational job this screen supports.

## User Roles

- Admin:
- Operator:
- Viewer:
- Unauthenticated:

## Entry Points

- Navigation path:
- Direct URL pattern:
- Related screens:

## What The Operator Sees

Describe the visible sections in TicketMirror terms.

- Section:
- Primary rows/cards:
- Secondary details:
- Empty state:
- Error state:

## Data Shown

List fields and their source models or services.

| Field | Source | Notes |
| --- | --- | --- |
| Example field | `Model.field` | Example note |

## Filters And Controls

List controls and query/state behavior.

| Control | Values | Default | Behavior |
| --- | --- | --- | --- |
| Example filter | All / active | All | Narrows rows |

## Actions

Describe what the user can do.

| Action | Role | Result |
| --- | --- | --- |
| Click row | Viewer+ | Opens detail or modal |
| Save changes | Operator/Admin | Persists change and records audit event |

## Click Behavior

Document exactly what happens after clicking:

- Row click:
- Primary button:
- Secondary button:
- Tab switch:
- Modal close:
- Back/cancel:

## Permissions

Define access and mutation rules.

- Unauthenticated:
- Viewer:
- Operator:
- Admin:

## Audit And Logging

- Audit event required:
- Old/new values stored:
- Log masking requirements:
- Parser/raw-email safety requirements:

## Acceptance Criteria

- Given/when/then criteria suitable for tests.
- Include positive, permission, empty, and error cases.

Example:

- Given an operator opens the screen, when they click a booking row, then an in-page booking dialog opens without losing the current dashboard state.
- Given a viewer opens the same dialog, then editable controls are read-only and save actions are unavailable.

## Open Questions

- Question:
- Assumption:
- Decision needed:
