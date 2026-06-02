#!/bin/bash
# MySQL backup script for AutoCode platform
# Usage: DB_HOST=localhost DB_USER=root DB_PASS=xxx ./backup-mysql.sh
# Recommended cron: 0 3 * * * /path/to/backup-mysql.sh

set -euo pipefail

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-/backups/mysql}"
DB_HOST="${DB_HOST:-localhost}"
DB_USER="${DB_USER:-root}"
DB_PASS="${DB_PASS:-}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

DATABASES=("mvp_codeops" "approval_db" "artifact_db" "event_db")

mkdir -p "$BACKUP_DIR"

for DB in "${DATABASES[@]}"; do
    BACKUP_FILE="${BACKUP_DIR}/${DB}_${DATE}.sql.gz"
    echo "[$(date -Iseconds)] Backing up ${DB} -> ${BACKUP_FILE}"

    mysqldump \
        -h "$DB_HOST" \
        -u "$DB_USER" \
        -p"$DB_PASS" \
        --single-transaction \
        --routines \
        --triggers \
        --events \
        "$DB" 2>/dev/null | gzip > "$BACKUP_FILE"

    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date -Iseconds)] ${DB} backup complete: ${SIZE}"
done

# Prune old backups
echo "[$(date -Iseconds)] Pruning backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +"$RETENTION_DAYS" -delete -print | while read -r f; do
    echo "  Deleted: $f"
done

echo "[$(date -Iseconds)] Backup run finished."
