# Codex Completion Report

## Features Implemented

- Added `create_internal_booking()` for dashboard/direct internal bookings.
- Enforced transactional capacity checks for internal bookings.
- Rejected operator overcapacity booking attempts.
- Allowed admin overcapacity booking only when an explicit override reason is supplied.
- Added `capacity_overbooked` review queue issue type.
- Added capacity-overbooked review warnings and audit events for OTA/provider ingested bookings without rejecting the provider booking.
- Replaced dashboard direct booking creation with the capacity-safe service.
- Added admin-only overcapacity override fields to the dashboard new-booking modal.
- Added duplicate active slot validation for overlapping days in Settings / Tours.
- Added bulk-capacity warning when lowering seats leaves upcoming slots overbooked.
- Added `/settings/ingestion/` with Gmail configuration presence, sync state, raw email status counts, and role-protected actions.
- Added CSV exports for overcapacity, unmapped provider products, and parser failures.
- Updated README links and report export documentation.

## Tests Added

- Internal booking under capacity creates a manual booking event.
- Operator overcapacity booking is rejected.
- Admin overcapacity override requires a reason and creates a review item.
- Cancelled and no-show bookings are excluded from direct booking capacity checks.
- OTA/provider overcapacity creates a `capacity_overbooked` review warning and event.
- Ingestion settings page is viewable by viewers, rejects viewer mutation, and lets operators process pending email.
- Duplicate schedule slots are rejected in Settings / Tours.
- New report CSV endpoints return expected operational data.

## Verification

- `python manage.py check`: passed.
- `python manage.py makemigrations --check --dry-run`: passed, no changes detected.
- `python -m pytest`: passed, 145 tests.
- `black --check .`: passed.
- `ruff check .`: passed.

Docker verification was not feasible in this environment because the `docker`
command is not installed or not on `PATH`.

## Known Limitations

- Docker Compose baseline and smoke runs could not be executed locally here.
- `makemigrations --check --dry-run` emitted a warning while checking migration
  history because `.env` points at the Compose database host `postgres`, which is
  unavailable without Docker. The command still completed with no model drift.
- Gmail sync and watch actions require real Gmail OAuth/Pub/Sub environment
  values in deployment; the settings page intentionally shows only whether
  secret-bearing values are configured.
- E2E browser smoke tests were not added because the current server-rendered
  coverage already exercises the requested workflows without adding a flaky
  browser dependency.

## Deployment Notes

- Apply migrations before deployment:

  ```bash
  python manage.py migrate
  ```

- Confirm production Gmail environment variables are present before using
  `/settings/ingestion/` actions:

  ```bash
  GMAIL_MAILBOX
  GMAIL_CLIENT_ID
  GMAIL_CLIENT_SECRET
  GMAIL_REFRESH_TOKEN
  GMAIL_PUBSUB_TOPIC
  GMAIL_WEBHOOK_AUDIENCE
  GOOGLE_CLOUD_PROJECT
  ```

- Continue to run ingestion actions from Settings with internal roles only:
  viewers are read-only, operators can process pending raw emails, and admins can
  sync recent Gmail or renew the Gmail watch.
