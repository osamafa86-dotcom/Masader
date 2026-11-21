#!/bin/sh
# Verifies that a backup can actually be restored: restores it into a throwaway database, checks the
# schema version and row counts, then drops it. Run inside the backup container:
#   docker compose exec backup sh /restore-test.sh            (latest dump)
#   docker compose exec backup sh /restore-test.sh FILE.dump
set -eu
DUMP="${1:-$(ls -1t /backups/marsad-*.dump 2>/dev/null | head -1)}"
[ -n "$DUMP" ] && [ -f "$DUMP" ] || { echo "no dump found"; exit 1; }
HOST="${PGHOST:-db}"; USER="${PGUSER:-marsad}"; TMP="restore_check_$$"
echo "restoring $DUMP into $TMP"
createdb -h "$HOST" -U "$USER" "$TMP"
trap 'dropdb -h "$HOST" -U "$USER" --if-exists "$TMP"' EXIT
psql -q -h "$HOST" -U "$USER" -d "$TMP" -c "CREATE EXTENSION IF NOT EXISTS vector" >/dev/null
pg_restore -h "$HOST" -U "$USER" -d "$TMP" --no-owner "$DUMP"
q() { psql -At -h "$HOST" -U "$USER" -d "$TMP" -c "$1"; }
VERSION=$(q "select version_num from alembic_version")
DOCS=$(q "select count(*) from documents")
PUBLISHED=$(q "select count(*) from documents where stage = 'published'")
SOURCES=$(q "select count(*) from sources")
echo "schema $VERSION, $SOURCES sources, $DOCS documents ($PUBLISHED published)"
[ "$SOURCES" -gt 0 ] || { echo "FAILED: no sources in restored copy"; exit 1; }
echo "restore check passed"
