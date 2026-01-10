#!/bin/bash
# Daily digest - runs at 06:00

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/daily_digest.log"

mkdir -p "$PROJECT_DIR/logs"

echo "========================================" >> "$LOG_FILE"
echo "Daily Digest - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

if ! docker ps --format '{{.Names}}' | grep -q '^leaknote-bot$'; then
    echo "ERROR: leaknote-bot container is not running" >> "$LOG_FILE"
    exit 1
fi

docker exec leaknote-bot python scripts/daily_digest.py >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "ERROR: Daily digest failed with exit code $EXIT_CODE" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
exit $EXIT_CODE
