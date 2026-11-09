#!/usr/bin/env bash
# Restores a dump produced by backup_db.sh into the "postgres" compose
# service. Destructive: wipes everything in the current database first.
# Run from the repo root. See docs/05-operacao-e-testes.md §5.
#
# Usage:
#   ./docker/scripts/restore_db.sh <dump_file.sql.gz> [-y]
set -euo pipefail

cd "$(dirname "$0")/../.."

DUMP_FILE="${1:?Uso: restore_db.sh <dump_file.sql.gz> [-y]}"
SKIP_CONFIRM="${2:-}"

if [ ! -f "$DUMP_FILE" ]; then
    echo "Arquivo não encontrado: $DUMP_FILE" >&2
    exit 1
fi

set -a
source .env
set +a

if [ "$SKIP_CONFIRM" != "-y" ]; then
    read -r -p "Isso apaga TODOS os dados atuais de '${POSTGRES_DB}' e restaura $DUMP_FILE. Continuar? [digite 'sim'] " CONFIRM
    if [ "$CONFIRM" != "sim" ]; then
        echo "Cancelado."
        exit 1
    fi
fi

docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

gunzip -c "$DUMP_FILE" | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

echo "Restore concluído a partir de $DUMP_FILE"
