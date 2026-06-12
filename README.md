# ticketmirror

Internal Django platform for mirroring OTA booking emails from a dedicated Gmail inbox.

ticketmirror is not the source of truth. It stores raw provider emails first, parses stable provider booking references, upserts mirrored bookings by `provider + reference`, and keeps internal operational data separate from provider payloads.

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

## Environment Variables

Required production values:

- `DJANGO_SECRET_KEY`: Django secret key.
- `DJANGO_DEBUG`: `false` outside local development.
- `DJANGO_ALLOWED_HOSTS`: Comma-separated hostnames.
- `DATABASE_URL`: PostgreSQL connection URL.
- `REDIS_URL`: Redis URL used by the application.
- `CELERY_BROKER_URL`: Celery broker URL.
- `CELERY_RESULT_BACKEND`: Celery result backend URL.

Gmail integration placeholders:

- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_INBOX_LABEL`

Do not commit real Gmail credentials or provider secrets.

## Booking Model Notes

- Raw emails are stored in `ingestion.RawEmail` before parsing.
- Existing bookings are matched by provider and provider reference.
- Provider payload data is stored separately from active internal fields.
- Manual edits should use `bookings.services.apply_manual_override()` so audit events are created.
- Upserts create `BookingEvent` records instead of silently overwriting operationally important data.
- Capacity reporting counts confirmed active bookings separately from pending bookings.

## CSV Exports

The reports app contains a placeholder CSV export for bookings:

```bash
/reports/bookings.csv
```
