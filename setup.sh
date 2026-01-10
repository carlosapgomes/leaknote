#!/bin/bash
# Leaknote Setup Script
# Run this once before starting the stack

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "Leaknote Setup"
echo "========================================"

# Check for .env
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env with your settings before continuing!"
    echo "   - Set secure passwords"
    echo "   - Set your MATRIX_SERVER_NAME"
    echo "   - Add your LLM API keys"
    echo ""
    read -p "Press Enter after editing .env, or Ctrl+C to abort..."
fi

source .env

# Create directories
echo ""
echo "Creating directories..."
mkdir -p data/postgres
mkdir -p data/backups
mkdir -p logs
mkdir -p dendrite/config
mkdir -p dendrite/media
mkdir -p dendrite/jetstream
mkdir -p dendrite/searchindex

# Generate Dendrite signing key
if [ ! -f dendrite/config/matrix_key.pem ]; then
    echo ""
    echo "Generating Dendrite signing key..."
    docker run --rm --entrypoint="/usr/bin/generate-keys" \
        -v "$(pwd)/dendrite/config:/mnt" \
        matrixdotorg/dendrite-monolith:latest \
        -private-key /mnt/matrix_key.pem
    echo "✓ Signing key generated"
else
    echo "✓ Signing key already exists"
fi

# Generate Dendrite config
if [ ! -f dendrite/config/dendrite.yaml ]; then
    echo ""
    echo "Generating Dendrite configuration..."

    SERVER_NAME="${MATRIX_SERVER_NAME:-localhost}"
    DB_PASSWORD="${DENDRITE_DB_PASSWORD:-dendrite}"

    docker run --rm --entrypoint="/bin/sh" \
        -v "$(pwd)/dendrite/config:/mnt" \
        matrixdotorg/dendrite-monolith:latest \
        -c "/usr/bin/generate-config \
            -dir /var/dendrite/ \
            -db postgres://dendrite:${DB_PASSWORD}@postgres/dendrite?sslmode=disable \
            -server ${SERVER_NAME} > /mnt/dendrite.yaml"

    echo "✓ Dendrite config generated"
else
    echo "✓ Dendrite config already exists"
fi

# Update init-db.sql with passwords
echo ""
echo "Updating database initialization script..."
LEAKNOTE_PW="${LEAKNOTE_DB_PASSWORD:-leaknote}"
DENDRITE_PW="${DENDRITE_DB_PASSWORD:-dendrite}"

sed -i "s/LEAKNOTE_PASSWORD_PLACEHOLDER/${LEAKNOTE_PW}/g" init-db.sql
sed -i "s/DENDRITE_PASSWORD_PLACEHOLDER/${DENDRITE_PW}/g" init-db.sql

echo "✓ Database init script updated"

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Review dendrite/config/dendrite.yaml if needed"
echo ""
echo "2. Start the stack:"
echo "   docker compose up -d"
echo ""
echo "3. Wait for services to be healthy:"
echo "   docker compose ps"
echo ""
echo "4. Create Matrix users:"
echo "   ./create-users.sh"
echo ""
echo "5. Create inbox room in Element and invite bot"
echo ""
echo "6. Install cron jobs from crontab.example"
echo ""
