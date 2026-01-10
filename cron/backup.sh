#!/bin/bash
# Database backup - runs daily at 02:00

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/data/backups"
LOG_FILE="$PROJECT_DIR/logs/backup.log"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"
mkdir -p "$PROJECT_DIR/logs"

echo "========================================" >> "$LOG_FILE"
echo "Backup - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

if ! docker ps --format '{{.Names}}' | grep -q '^leaknote-db$'; then
    echo "ERROR: leaknote-db container is not running" >> "$LOG_FILE"
    exit 1
fi

# Backup Leaknote database
LEAKNOTE_BACKUP="leaknote_$DATE.sql.gz"
echo "Backing up Leaknote database..." >> "$LOG_FILE"
docker exec leaknote-db pg_dump -U leaknote leaknote | gzip > "$BACKUP_DIR/$LEAKNOTE_BACKUP"

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_DIR/$LEAKNOTE_BACKUP" | cut -f1)
    echo "✓ Leaknote backup: $LEAKNOTE_BACKUP ($BACKUP_SIZE)" >> "$LOG_FILE"
else
    echo "ERROR: Leaknote backup failed" >> "$LOG_FILE"
fi

# Backup Dendrite database
DENDRITE_BACKUP="dendrite_$DATE.sql.gz"
echo "Backing up Dendrite database..." >> "$LOG_FILE"
docker exec leaknote-db pg_dump -U dendrite dendrite | gzip > "$BACKUP_DIR/$DENDRITE_BACKUP"

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_DIR/$DENDRITE_BACKUP" | cut -f1)
    echo "✓ Dendrite backup: $DENDRITE_BACKUP ($BACKUP_SIZE)" >> "$LOG_FILE"
else
    echo "ERROR: Dendrite backup failed" >> "$LOG_FILE"
fi

# Keep only last 30 days
DELETED=$(find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "Deleted $DELETED old backup(s)" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
