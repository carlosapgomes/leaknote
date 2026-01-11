#!/bin/bash
# Health check - runs every 5 minutes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

UNHEALTHY=0

# Check containers
if ! docker ps --format '{{.Names}}' | grep -q '^leaknote-bot$'; then
    echo "$(date) UNHEALTHY: leaknote-bot container not running"
    UNHEALTHY=1
fi

if ! docker ps --format '{{.Names}}' | grep -q '^leaknote-db$'; then
    echo "$(date) UNHEALTHY: leaknote-db container not running"
    UNHEALTHY=1
fi

# Check postgres
if ! docker exec leaknote-db pg_isready -U postgres > /dev/null 2>&1; then
    echo "$(date) UNHEALTHY: PostgreSQL not ready"
    UNHEALTHY=1
fi

if [ $UNHEALTHY -eq 0 ]; then
    echo "$(date) HEALTHY"
    exit 0
else
    exit 1
fi
