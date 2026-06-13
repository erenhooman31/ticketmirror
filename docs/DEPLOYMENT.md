# Deployment

This guide describes a small private-server production deployment for
ticketmirror. The production stack is isolated in its own Docker Compose file,
env file, containers, database volume, Redis volume, and backups folder.

The examples assume the app will run at `tickets.example.com`. Replace that with
the real subdomain before deploying.

## Production Stack

`docker-compose.prod.yml` defines:

- `web`: Gunicorn running Django.
- `worker`: Celery worker for Gmail ingestion and parsing jobs.
- `beat`: Celery beat scheduler process.
- `postgres`: PostgreSQL 16 with persisted database data.
- `redis`: Redis 7 with append-only persistence.
- `caddy`: HTTPS reverse proxy, static file server, and media file server.

Persistent storage:

- `postgres_data`: PostgreSQL data.
- `redis_data`: Redis append-only data.
- `static_data`: `collectstatic` output shared between `web` and `caddy`.
- `media_data`: Django media files, if any are added later.
- `caddy_data` and `caddy_config`: Caddy certificates and runtime state.
- `deployment/backups`: PostgreSQL dump files created by backup scripts.

## Server Prerequisites

Install on the server:

- Docker Engine
- Docker Compose v2
- Git
- A firewall that allows inbound `80/tcp` and `443/tcp`

DNS:

1. Create an `A` or `AAAA` record for the app subdomain.
2. Point it at the server public IP.
3. Wait for DNS to resolve before starting Caddy, because HTTPS certificate
   issuance depends on the domain reaching this server.

## Production Env File

Copy the production example and edit real values on the server:

```bash
cp .env.prod.example .env.prod
chmod 600 .env.prod
```

Required production values:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=false`
- `ALLOWED_HOSTS=tickets.example.com`
- `CSRF_TRUSTED_ORIGINS=https://tickets.example.com`
- `DJANGO_SECURE_SSL_REDIRECT=true`
- `DJANGO_SESSION_COOKIE_SECURE=true`
- `DJANGO_CSRF_COOKIE_SECURE=true`
- `DOMAIN=tickets.example.com`
- `ACME_EMAIL`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

Optional bootstrap admin values:

- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_EMAIL`
- `DJANGO_SUPERUSER_PASSWORD`

If the bootstrap admin values are blank, `create_initial_admin` exits without
creating an account. Remove `DJANGO_SUPERUSER_PASSWORD` after the first deploy if
you do not need repeatable bootstrap behavior.

Gmail values are configured later and must remain environment-only:

- `GMAIL_MAILBOX`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_PUBSUB_TOPIC`
- `GMAIL_WEBHOOK_AUDIENCE`
- `GOOGLE_CLOUD_PROJECT`

Do not commit `.env.prod` or any real credential file.

## First Deploy

From the repository root on the server:

```bash
chmod +x deployment/*.sh
deployment/deploy.sh
```

The deploy script:

1. Builds the application image.
2. Starts PostgreSQL and Redis.
3. Runs migrations.
4. Runs `collectstatic`.
5. Runs `create_initial_admin`.
6. Starts `web`, `worker`, `beat`, and `caddy`.
7. Prints Compose service status.

To run the same steps manually:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d postgres redis
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm web python manage.py migrate --noinput
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm web python manage.py create_initial_admin
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d web worker beat caddy
```

## Static And Media Files

Django writes static files to `STATIC_ROOT=/app/staticfiles` during
`collectstatic`. The `static_data` Docker volume is mounted into both:

- `web` at `/app/staticfiles`
- `caddy` at `/srv/static`

Caddy serves `/static/*` directly from that volume.

`MEDIA_ROOT=/app/media` is mounted as `media_data`. Caddy serves `/media/*` with
`Content-Disposition: attachment` so any future uploaded files are not rendered
inline by default. The app currently does not require user-uploaded media.

## Healthchecks And Restarts

Production services use `restart: unless-stopped`.

Healthchecks are configured for:

- `web`: `GET /healthz/`
- `postgres`: `pg_isready`
- `redis`: `redis-cli ping`

`caddy` waits for the `web` healthcheck before starting.

## Operations

View service state:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

View logs:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f web worker beat caddy
```

Run Django commands:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm web python manage.py check
```

Run tests before deploying a new build:

```bash
python -m pytest
```

## Backups

Create a PostgreSQL custom-format dump:

```bash
deployment/backup_postgres.sh
```

Backups are written to `deployment/backups/ticketmirror_<timestamp>.dump`.
Copy these dumps off the server regularly. The local backups directory is a
convenience, not a complete backup strategy.

Restore a dump:

```bash
deployment/restore_postgres.sh deployment/backups/ticketmirror_YYYYMMDDTHHMMSSZ.dump
```

The restore script requires typing `RESTORE` before it writes to the production
database.

## systemd

An optional systemd unit is provided at `deployment/ticketmirror.service`.
Assuming the repository lives at `/opt/ticketmirror`:

```bash
sudo cp deployment/ticketmirror.service /etc/systemd/system/ticketmirror.service
sudo systemctl daemon-reload
sudo systemctl enable ticketmirror
sudo systemctl start ticketmirror
```

The systemd unit starts and stops the production Compose stack. Continue to use
`deployment/deploy.sh` for migrations and static collection during releases.

## Gmail Watch Setup

After Gmail credentials and Pub/Sub are configured:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm web python manage.py setup_gmail_watch
```

Renew the watch before expiration:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm web python manage.py renew_gmail_watch
```

Reconcile recent messages after an outage:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm web python manage.py sync_recent_gmail --limit 100
```

## Release Checklist

1. Pull or copy the new code into the isolated ticketmirror directory.
2. Confirm `.env.prod` is present and not tracked by Git.
3. Run tests locally or in CI.
4. Run `deployment/backup_postgres.sh`.
5. Run `deployment/deploy.sh`.
6. Check `docker compose --env-file .env.prod -f docker-compose.prod.yml ps`.
7. Open the app over HTTPS and confirm login, dashboard, reports, and admin.

## Security Notes

- Keep `DJANGO_DEBUG=false` in production.
- Keep `.env.prod` outside version control.
- Use a long random `DJANGO_SECRET_KEY`.
- Use strong database and admin passwords.
- Restrict SSH access to trusted operators.
- Keep PostgreSQL and Redis ports unexposed; only Caddy publishes `80` and `443`.
- Raw emails can contain personal data. Protect backups accordingly.
- Logs are written to stdout for container collection and should not include raw
  email bodies or full traveler contact details.
