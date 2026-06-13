# ticketmirror

Internal Django platform for mirroring OTA booking emails from a dedicated Gmail inbox.

ticketmirror is not the source of truth. It stores raw provider emails first, parses stable provider booking references, upserts mirrored bookings by `provider + provider_booking_reference`, and keeps internal operational data separate from provider payloads.

## Stack

- Python 3.12
- Django 5.x
- PostgreSQL
- Redis
- Celery
- Server-rendered Django templates
- pytest, ruff, black

## Local Setup

1. Create an environment file:

   ```bash
   cp .env.example .env
   ```

2. Build and start services:

   ```bash
   docker compose up --build
   ```

3. Run migrations:

   ```bash
   docker compose exec web python manage.py migrate
   ```

4. Create an admin user:

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

5. Open the app:

   - Dashboard: http://localhost:8000/
   - Admin: http://localhost:8000/admin/

## Useful Commands

Run Django checks:

```bash
docker compose exec web python manage.py check
```

Run tests:

```bash
docker compose exec web pytest
```

Run formatting and linting:

```bash
docker compose exec web black .
docker compose exec web ruff check .
```

Run the same checks directly in a local virtualenv:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest
black --check .
ruff check .
```

Seed canonical products, variants, capacity rules, and provider aliases:

```bash
python manage.py seed_products --file data/sample_products.yml
```

## Documentation

- [Agent guidance](AGENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Database](docs/DATABASE.md)
- [Ingestion](docs/INGESTION.md)
- [Parsers](docs/PARSERS.md)
- [Product seeds](docs/PRODUCT_SEEDS.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Final review](FINAL_REVIEW.md)

## Production Deployment

Production deployment uses `docker-compose.prod.yml` with Gunicorn, Celery
worker, Celery beat, PostgreSQL, Redis, and Caddy. Start from
`.env.prod.example`, fill in real values on the server, and follow
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

```bash
cp .env.prod.example .env.prod
chmod +x deployment/*.sh
deployment/deploy.sh
```

Do not commit `.env`, `.env.prod`, OAuth credentials, database passwords, or real
provider email samples.

## CI

GitHub Actions runs on pushes to `main` and `develop` and on pull requests. The
workflow installs Python dependencies, runs migrations and Django checks, runs
the test suite, and verifies Ruff and Black. Dependabot is configured for Python
dependencies and GitHub Actions.

## Environment Variables

Required production values:

- `DJANGO_SECRET_KEY`: Django secret key.
- `DJANGO_DEBUG`: `false` outside local development.
- `ALLOWED_HOSTS`: Comma-separated hostnames.
- `CSRF_TRUSTED_ORIGINS`: Comma-separated trusted origins for HTTPS deployments.
- `DATABASE_URL`: PostgreSQL connection URL.
- `REDIS_URL`: Redis URL used by the application.
- `CELERY_BROKER_URL`: Celery broker URL.
- `CELERY_RESULT_BACKEND`: Celery result backend URL.

Gmail integration placeholders:

- `GMAIL_MAILBOX`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_PUBSUB_TOPIC`
- `GMAIL_WEBHOOK_AUDIENCE`
- `GOOGLE_CLOUD_PROJECT`

Gmail ingestion commands:

```bash
python manage.py setup_gmail_watch
python manage.py renew_gmail_watch
python manage.py sync_recent_gmail --limit 100
python manage.py process_pending_emails
```

Do not commit real Gmail credentials or provider secrets.

## Booking Model Notes

- Raw emails are stored in `ingestion.RawEmail` before parsing.
- Existing bookings are matched by provider and provider booking reference.
- Provider payload data is stored separately from active internal fields.
- Manual edits should use `bookings.services.apply_manual_override()` so audit events are created.
- Upserts create `BookingEvent` records instead of silently overwriting operationally important data.
- Capacity reporting counts confirmed active bookings separately from pending bookings.

## CSV Exports

The reports app contains CSV exports for bookings, daily manifests, capacity,
and provider summaries:

```bash
/reports/bookings.csv
/reports/daily-manifest.csv
/reports/capacity-summary.csv
/reports/provider-summary.csv
```
