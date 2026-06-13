#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 path/to/backup.dump" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.prod}"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.prod.yml}"
BACKUP_FILE="$1"

if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "Backup file not found: ${BACKUP_FILE}" >&2
  exit 2
fi
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi
export TICKETMIRROR_ENV_FILE="${ENV_FILE}"

read -r -p "Restore ${BACKUP_FILE} into production database? Type RESTORE: " confirm
if [[ "${confirm}" != "RESTORE" ]]; then
  echo "Restore cancelled."
  exit 1
fi

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d postgres
cat "${BACKUP_FILE}" | docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" exec -T postgres \
  pg_restore -U "${POSTGRES_USER:-ticketmirror}" -d "${POSTGRES_DB:-ticketmirror}" \
  --clean --if-exists --no-owner --no-acl

echo "Restore complete. Restarting application services."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d web worker beat caddy
