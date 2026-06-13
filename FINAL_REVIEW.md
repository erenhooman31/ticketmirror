# Final Review

## What Was Built

ticketmirror is an internal Django MVP for mirroring OTA booking emails from a
dedicated Gmail inbox into an operational booking dashboard.

Implemented areas:

- Server-rendered Django app with role-aware internal pages.
- PostgreSQL data model for providers, products, product variants, capacity
  rules, bookings, booking events, review queue items, raw emails, and Gmail
  sync state.
- Deterministic parser framework with provider parsers and fixture-backed tests.
- Gmail API ingestion scaffolding using environment-based OAuth placeholders,
  Pub/Sub webhook handling, Celery retries, Gmail history tracking, MIME body
  decoding, forwarded-email handling, and RawEmail normalization.
- Booking upsert service keyed by provider and provider booking reference.
- Manual override behavior that prevents provider updates from silently
  overwriting active operational fields.
- Audit events for email creates/updates, manual edits, status changes, product
  alias changes, and conflict detection.
- Review queue for parser failures, low confidence parses, missing references,
  unmapped products, and manual override conflicts.
- Capacity services and CSV exports for daily manifests, capacity summaries,
  provider summaries, and date-range booking exports.
- Dashboard, daily operations view, slot detail view, review queue, aliases
  page, raw email detail page, reports page, and global search.
- Admin polish with useful list displays, filters, search fields, read-only
  identity fields after creation, booking event inlines, alias inlines, and raw
  email body previews.
- Production Docker Compose stack with Gunicorn, Celery worker, Celery beat,
  PostgreSQL, Redis, and Caddy.
- Deployment scripts for migrations, static collection, initial admin creation,
  PostgreSQL backup, PostgreSQL restore, and optional systemd management.
- GitHub Actions CI and Dependabot configuration.

## How To Run Locally

1. Copy the development env file:

   ```bash
   cp .env.example .env
   ```

2. Start the development stack:

   ```bash
   docker compose up --build
   ```

3. Apply migrations:

   ```bash
   docker compose exec web python manage.py migrate
   ```

4. Seed defaults if desired:

   ```bash
   docker compose exec web python manage.py seed_defaults
   ```

5. Create a local admin user:

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

6. Open:

   - Dashboard: `http://localhost:8000/`
   - Admin: `http://localhost:8000/admin/`

Useful local checks:

```bash
python -m pytest
python manage.py check
python manage.py makemigrations --check --dry-run
ruff check .
black --check .
```

When running checks outside Docker, set `DATABASE_URL=sqlite:///:memory:` or run
inside Compose so Django does not try to resolve the Compose hostname
`postgres`.

## How To Deploy

Production deployment is documented in `docs/DEPLOYMENT.md`.

Short version:

1. Provision a small private server with Docker Engine and Docker Compose v2.
2. Point a subdomain such as `tickets.example.com` at the server.
3. Copy `.env.prod.example` to `.env.prod`.
4. Fill in real production values and keep `.env.prod` out of Git.
5. Run:

   ```bash
   chmod +x deployment/*.sh
   deployment/deploy.sh
   ```

6. Confirm:

   ```bash
   docker compose --env-file .env.prod -f docker-compose.prod.yml ps
   ```

7. Configure Gmail OAuth, Pub/Sub, and watch registration when credentials are
   available.

The production stack is isolated in `docker-compose.prod.yml` and uses separate
containers, volumes, env file, and backup directory.

## What Is Complete

- Core booking, provider, product, alias, capacity, review queue, raw email, and
  audit models.
- Parser registry and deterministic parser test coverage for anonymized fixture
  emails.
- Raw-email-first ingestion flow and duplicate protection by Gmail message ID.
- Gmail API client scaffolding and webhook/task flow with mocked test coverage.
- Booking creation/update logic and manual override conflict handling.
- Capacity calculations for fixed-time, full-day, half-day, and private-group
  variants.
- CSV exports for operations and reporting.
- Viewer/operator/admin permissions for internal views and mutation boundaries.
- Admin usability improvements for core models.
- Production Docker Compose and deployment docs.
- CI workflow for checks, migrations, tests, lint, and formatting.

## What Still Needs Real Credentials Or Configuration

- Real `DJANGO_SECRET_KEY`.
- Production domain in `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `DOMAIN`.
- Production PostgreSQL password and matching `DATABASE_URL`.
- Optional initial admin env values, or manual superuser creation.
- Gmail OAuth client ID, client secret, refresh token, mailbox, Pub/Sub topic,
  webhook verification/audience value, and Google Cloud project ID.
- Gmail Pub/Sub subscription configuration pointing at
  `/ingestion/gmail/webhook/`.
- Production backup retention and off-server backup copy process.

## Known Limitations

- Real Gmail OAuth credentials are not committed.
- Real provider email samples are not committed unless anonymized.
- Klook parser coverage may need refinement when real sample emails are added.
- PDF attachment parsing is not required because current email samples are plain
  text.
- Gmail webhook validation is intentionally minimal until the production
  verification method is finalized.
- Celery beat is present in production Compose, but periodic schedules should be
  explicitly configured for the final operating cadence.
- Capacity rules assume the current product/variant model and should be revisited
  if products gain complex overlapping inventory pools.
- Reports are CSV-first and server-rendered; there is no BI dashboard or charting
  layer.

## Next Recommended Improvements

- Add production Pub/Sub webhook signature or token verification once the final
  Google delivery path is configured.
- Add Celery beat schedule configuration for Gmail watch renewal, daily
  reconciliation, and pending raw email processing.
- Add structured logging and application metrics for ingestion failures,
  capacity warnings, and parser review volume.
- Add more anonymized real provider samples, especially for Klook and forwarded
  email variants.
- Add admin actions for bulk review item resolution and safe parser reprocessing.
- Add backup retention automation and encrypted off-server backup storage.
- Add end-to-end smoke tests against the Docker production Compose stack.

## Verification

Final verification completed:

- `black --check .`: passed.
- `ruff check .`: passed.
- `python manage.py check`: passed.
- `DATABASE_URL=sqlite:///:memory: python manage.py makemigrations --check --dry-run`:
  passed with no migration changes detected.
- `python -m pytest`: 53 tests passed.

No blocking issues were found in the final review.
