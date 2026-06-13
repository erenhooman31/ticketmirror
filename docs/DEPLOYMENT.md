# Deployment

The MVP is deployable as a Dockerized Django application with PostgreSQL, Redis, and a Celery worker.

## Services

`docker-compose.yml` defines:

- `web`: Django development server for local use.
- `worker`: Celery worker.
- `postgres`: PostgreSQL 16.
- `redis`: Redis 7.

Production deployment should run Django through a production server such as Gunicorn, run Celery workers separately, and use managed PostgreSQL and Redis where appropriate.

## Environment

Start from `.env.example` and provide real values through environment variables. Required production settings include:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=false`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

Gmail integration variables must be provided only through the environment. Never commit real Gmail secrets.

- `GMAIL_MAILBOX`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_PUBSUB_TOPIC`
- `GMAIL_WEBHOOK_AUDIENCE`
- `GOOGLE_CLOUD_PROJECT`

After deployment, run `python manage.py setup_gmail_watch` once and schedule
`python manage.py renew_gmail_watch` before the Gmail watch expires. Also
schedule `daily_reconciliation_sync` through Celery beat or another scheduler so
recent Gmail messages are re-queued periodically.

## Release Steps

Typical release sequence:

1. Build the image.
2. Run tests and checks.
3. Apply database migrations.
4. Start or restart web and worker services.
5. Verify the dashboard, admin login, and worker health.

## Operational Notes

Back up PostgreSQL regularly. Raw emails can contain personal data and should be protected according to internal data retention policies.

Logging should avoid printing full raw email bodies or credentials. Future production settings should add structured logging, secure cookie settings, HTTPS enforcement, and monitored Celery queues.
