# Deployment

Production deployment uses Docker Compose with these services:

- `web`: Django served by Gunicorn.
- `poller`: continuous Gmail polling with `python manage.py poll_gmail --loop --interval 60`.
- `postgres`: PostgreSQL 16 with a persistent volume.
- `caddy`: public HTTP/HTTPS reverse proxy.

Persistent volumes:

- `postgres_data`: application database.
- `static_data`: collected static files.
- `media_data`: uploaded or generated media.
- `caddy_data` and `caddy_config`: TLS state and Caddy config.

## Environment

Start from `.env.prod.example` and fill in production values on the server.

Required values:

- `DJANGO_SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `DOMAIN`
- `ACME_EMAIL`

Gmail polling values:

- `GMAIL_MAILBOX`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`

Use a read-only Gmail OAuth grant for the poller. Do not commit real secrets or real provider email samples.

## Deploy

```bash
cp .env.prod.example .env.prod
chmod +x deployment/*.sh
deployment/deploy.sh
```

The deploy script builds images, starts PostgreSQL, applies migrations, collects static files, creates the initial admin if configured, and starts `web`, `poller`, and `caddy`.

Useful manual commands:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d postgres
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm web python manage.py migrate --noinput
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d web poller caddy
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f web poller caddy
```

## Gmail Operations

Run one catch-up cycle manually:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm web python manage.py poll_gmail
```

Retry raw emails that were stored but not parsed:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm web python manage.py process_pending_emails
```

Run a bounded deploy-safe repair:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm web python manage.py repair_parsed_booking_display_fields --quiet --limit 500
```

## Backups

Use the scripts under `deployment/` for PostgreSQL backups and restores. Restores restart `web`, `poller`, and `caddy` after loading the dump.

## Network

Only Caddy should publish ports `80` and `443`. Keep PostgreSQL unexposed outside the private Compose network except for deliberate local development.
