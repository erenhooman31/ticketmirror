# AGENTS.md

Guidance for all future Codex work in this repository.

## Project Purpose

ticketmirror is an internal booking and ticket management dashboard. It mirrors bookings received by email from OTA providers such as GetYourGuide, Viator, Tiqets, Tripster, Sputnik8, Klook, and similar providers.

This is not a customer-facing booking engine. The OTA/provider systems remain the source of truth. ticketmirror stores incoming Gmail messages, parses stable provider booking references, and gives internal operations staff a date, activity, schedule-slot, and capacity view of mirrored reservations.

Do not build public customer pages. Do not build payment processing. Do not add checkout, payment links, carts, or customer booking flows.

## Tech Stack

- Python 3.12
- Django 5.x
- PostgreSQL
- Gmail polling management command
- Docker Compose
- Server-rendered Django templates
- Django admin for emergency/developer console access only
- Bootstrap or simple CSS
- pytest
- ruff and black
- django-environ for environment variables

Do not use React, Next.js, or a separate frontend app unless explicitly requested later.

## App Layout

- `config/`: Django settings, URL configuration, ASGI/WSGI.
- `apps/accounts/`: user profile and role model for admin, operator, viewer.
- `apps/bookings/`: providers, tours/activities, schedules, schedule slots, people rules, provider aliases, bookings, audit events, manual overrides, review queue.
- `apps/ingestion/`: raw email storage, Gmail scaffolding, parser registry, provider parser modules, booking upsert services.
- `apps/reports/`: CSV export and reporting endpoints.
- `apps/core/`: dashboard, base views, shared templates.
- `tests/`: project and app tests.
- `docs/`: architecture, database, ingestion, parser, and deployment notes.

## Run Locally

Use Docker Compose for the normal local environment:

```bash
cp .env.example .env
docker compose up --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Open:

- Home: http://localhost:8000/
- Calendar: http://localhost:8000/bookings/daily/
- Customers: http://localhost:8000/customers/
- Settings: http://localhost:8000/settings/

For local Python-only checks, a virtualenv is acceptable:

```bash
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py check
```

## Tests

Run tests before every commit:

```bash
docker compose exec web pytest
```

or locally:

```bash
.\.venv\Scripts\python -m pytest
```

Every new feature must include tests. Parser changes must include deterministic parser tests with representative email body samples.

## Lint And Format

Run before every commit:

```bash
docker compose exec web black .
docker compose exec web ruff check .
```

or locally:

```bash
.\.venv\Scripts\python -m black .
.\.venv\Scripts\python -m ruff check .
```

Do not leave formatting-only churn mixed with unrelated behavior changes unless it is required by the task.

## Security Rules

- Never hardcode credentials, tokens, cookies, client secrets, Gmail credentials, database URLs, or provider secrets.
- Use environment variables and document new variables in `.env.example` and README/docs.
- Do not commit `.env`, real emails, real Gmail payloads, production database dumps, or customer/traveler personal data.
- Treat raw email bodies as sensitive operational data.
- Keep access internal. Do not add public customer views or unauthenticated operational data endpoints.
- Use Django permissions, login protection, and admin access patterns for MVP features.
- Prefer server-side validation for all forms and admin actions.

## Database Rules

- PostgreSQL is the application database. SQLite is only acceptable for local tests.
- Create migrations for every model change.
- Do not use traveler name as a unique identifier.
- Upsert bookings by underlying OTA identity first, then by `provider + provider_booking_reference`.
- Keep original provider values and internal active values separate.
- Store provider payloads and raw emails for traceability.
- Manual edits must create audit records.
- Provider updates must create booking events.
- Provider updates must not silently overwrite manual overrides.
- Capacity calculations should count confirmed active bookings and show pending separately.
- Activity setup uses `TourActivity`, `ActivitySchedule`, `ActivityScheduleSlot`, `ActivityPeopleRule`, and `ProviderAlias`.
- Capacity lives on `ActivityScheduleSlot`; people rules are setup defaults.
- Use transactions around booking upserts, manual edits, and ingestion state changes.

## Parser Rules

- Store raw Gmail emails before parsing.
- Parser code must be deterministic and tested.
- Provider parsers should extract stable booking/reference numbers, product names, date, time slot, guest details, party size, and status when available.
- Parser output should be normalized into ingestion DTOs before upsert.
- Unknown or ambiguous provider aliases should create review queue items instead of guessing.
- Do not rely on traveler name, email subject alone, or fuzzy person matching to identify bookings.
- AI extraction may only be added later as a fallback, not as the main parser.
- Parser behavior must be provider-specific and covered by fixture-based tests.

## UI Rules

- Use Django templates and Settings pages for normal internal workflows.
- Primary navigation is limited to Home, Calendar, Customers, Settings. Admin functionality is role-based inside Settings, not a separate Admin section.
- Keep Django admin unlinked from the product UI; use it only as an emergency/developer console when explicitly needed.
- Keep UI internal, operational, dense, and practical.
- Prioritize date, activity, schedule slot, capacity, booking status, review queue, and CSV export workflows.
- Do not build marketing pages, customer booking pages, checkout pages, or public landing pages.
- Use Bootstrap or simple CSS. Avoid adding a frontend build system unless explicitly requested.

## Git Commit Expectations

- Every completed task must run checks and commit changes.
- Run at minimum:

  ```bash
  python manage.py check
  pytest
  black --check .
  ruff check .
  ```

- Commit messages should be concise and describe the completed change.
- Keep commits focused. Do not mix unrelated refactors, formatting sweeps, or generated files with feature work unless necessary.
- Do not rewrite existing history unless explicitly requested.

## Definition Of Done

A task is done when:

- The implementation matches the internal booking mirror product purpose.
- Security and database rules above are respected.
- Models have migrations when needed.
- New behavior has tests.
- Django checks pass.
- Tests pass.
- Formatting and lint checks pass.
- README or docs are updated when setup, architecture, environment variables, or workflows change.
- Changes are committed with an appropriate message.
