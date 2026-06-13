# Bookeo-Inspired Feature Reference

These notes are a functional reference workspace for TicketMirror planning. Bookeo is used only as a source of operational workflow inspiration.

Do not copy Bookeo branding, exact visual design, text, icons, CSS, layout proportions, colors, or trade dress. TicketMirror implementations should use our own product language, data model, styling, and interaction details.

## Purpose

Use this directory to describe operational screens before implementing them:

- What the operator sees.
- What actions the operator can take.
- What data is shown.
- What filters, date controls, and toggles exist.
- What happens after clicking rows, buttons, tabs, or menu items.
- Acceptance criteria for TicketMirror behavior.

## Files

- `screen-template.md`: reusable template for documenting a screen.
- `workflows.md`: cross-screen operator workflows and expected outcomes.
- `feature-backlog.md`: candidate features to evaluate and prioritize.

## Reference Rules

- Describe behavior, not visual cloning.
- Prefer TicketMirror terms such as booking, provider, product, tour, activity, schedule, capacity, review queue, and audit event.
- Avoid provider or traveler personal data in examples.
- Keep examples anonymized and deterministic.
- Convert any observed third-party workflow into our own acceptance criteria before implementation.

## Implementation Gate

A feature reference is ready for implementation when it includes:

- User role and permission expectations.
- Data dependencies and source models.
- Empty, loading, success, error, and permission-denied states.
- Click behavior and navigation behavior.
- Audit or logging requirements.
- Acceptance criteria that can become tests.
