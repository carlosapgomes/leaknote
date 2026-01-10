#!/bin/bash
# Database backup - runs daily at 02:00
# Backs up both Dendrite and Second Brain databases

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/data/backups"
LOG_FILE="$PROJECT_DIR/logs/backup.log"
DATE=$(date +%Y%m%d_%H%M%S)

# Ensure directories exist
mkdir -p "$BACKUP_DIR"
mkdir -p "$PROJECT_DIR/logs"

echo "========================================" >> "$LOG_FILE"
echo "Backup - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Check if postgres container is running
if ! docker ps --format '{{.Names}}' | grep -q '^secondbrain-db$'; then
    echo "ERROR: secondbrain-db container is not running" >> "$LOG_FILE"
    exit 1
fi

# Load environment variables
if [ -f "$PROJECT_DIR/.env" ]; then
    source "$PROJECT_DIR/.env"
else
    echo "ERROR: .env file not found" >> "$LOG_FILE"
    exit 1
fi

# Backup Second Brain database
SECONDBRAIN_BACKUP="secondbrain_$DATE.sql.gz"
echo "Backing up Second Brain database..." >> "$LOG_FILE"
docker exec secondbrain-db pg_dump -U secondbrain secondbrain | gzip > "$BACKUP_DIR/$SECONDBRAIN_BACKUP"

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_DIR/$SECONDBRAIN_BACKUP" | cut -f1)
    echo "✓ Second Brain backup: $SECONDBRAIN_BACKUP ($BACKUP_SIZE)" >> "$LOG_FILE"
else
    echo "ERROR: Second Brain backup failed" >> "$LOG_FILE"
fi

# Backup Dendrite database
DENDRITE_BACKUP="dendrite_$DATE.sql.gz"
echo "Backing up Dendrite database..." >> "$LOG_FILE"
docker exec secondbrain-db pg_dump -U dendrite dendrite | gzip > "$BACKUP_DIR/$DENDRITE_BACKUP"

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_DIR/$DENDRITE_BACKUP" | cut -f1)
    echo "✓ Dendrite backup: $DENDRITE_BACKUP ($BACKUP_SIZE)" >> "$LOG_FILE"
else
    echo "ERROR: Dendrite backup failed" >> "$LOG_FILE"
fi

# Keep only last 30 days of backups
DELETED=$(find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "Deleted $DELETED old backup(s)" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
