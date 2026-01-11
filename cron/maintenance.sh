#!/bin/bash
# Weekly maintenance - runs Sunday at 23:00

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/maintenance.log"

mkdir -p "$PROJECT_DIR/logs"

echo "========================================" >> "$LOG_FILE"
echo "Weekly Maintenance - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

if ! docker ps --format '{{.Names}}' | grep -q '^leaknote-bot$'; then
    echo "ERROR: leaknote-bot container is not running" >> "$LOG_FILE"
    exit 1
fi

docker exec leaknote-bot python scripts/maintenance.py >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "ERROR: Maintenance failed with exit code $EXIT_CODE" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
exit $EXIT_CODE
