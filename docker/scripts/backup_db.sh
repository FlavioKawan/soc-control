#!/usr/bin/env bash
# Dumps the Postgres database running in the "postgres" compose service into
# a gzipped, timestamped file under $BACKUP_DIR, then deletes dumps older
# than $RETENTION_DAYS. Run from the repo root (needs docker-compose.yml and
# .env alongside it). Schedule it in cron - see docs/05-operacao-e-testes.md §5.
#
# Usage:
#   ./docker/scripts/backup_db.sh [backup_dir] [retention_days]
set -euo pipefail

cd "$(dirname "$0")/../.."

BACKUP_DIR="${1:-./backups}"
RETENTION_DAYS="${2:-14}"

set -a
source .env
set +a

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
DUMP_FILE="$BACKUP_DIR/${POSTGRES_DB}-${TIMESTAMP}.sql.gz"

docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$DUMP_FILE"

echo "Backup salvo em $DUMP_FILE"

find "$BACKUP_DIR" -name "${POSTGRES_DB}-*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete
