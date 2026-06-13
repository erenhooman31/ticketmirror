#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.prod}"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/deployment/backups}"

mkdir -p "${BACKUP_DIR}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi
export TICKETMIRROR_ENV_FILE="${ENV_FILE}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="${BACKUP_DIR}/ticketmirror_${timestamp}.dump"

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-ticketmirror}" -d "${POSTGRES_DB:-ticketmirror}" \
  --format=custom --no-owner --no-acl > "${backup_file}"

echo "Wrote ${backup_file}"
