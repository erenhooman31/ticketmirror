#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.prod}"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.prod.yml}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing env file: ${ENV_FILE}" >&2
  echo "Create it from .env.prod.example and fill in production values." >&2
  exit 2
fi

export TICKETMIRROR_ENV_FILE="${ENV_FILE}"
mkdir -p "${ROOT_DIR}/deployment/backups"

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" build
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d postgres redis
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" run --rm web python manage.py migrate --noinput
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" run --rm web python manage.py collectstatic --noinput
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" run --rm web python manage.py create_initial_admin
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d web worker beat caddy
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
