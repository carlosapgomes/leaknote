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

# Generate Dendrite config from template
if [ ! -f dendrite/config/dendrite.yaml ]; then
    echo ""
    echo "Generating Dendrite configuration from template..."

    SERVER_NAME="${MATRIX_SERVER_NAME:-localhost}"
    DB_PASSWORD="${DENDRITE_DB_PASSWORD:-dendrite}"
    REGISTRATION_SECRET="${DENDRITE_REGISTRATION_SECRET:-$(openssl rand -hex 32)}"

    # Copy template and replace placeholders
    sed "s/MATRIX_SERVER_NAME_PLACEHOLDER/${SERVER_NAME}/g" \
        dendrite/config/dendrite.yaml.template | \
    sed "s/DENDRITE_DB_PASSWORD_PLACEHOLDER/${DB_PASSWORD}/g" | \
    sed "s/REGISTRATION_SHARED_SECRET_PLACEHOLDER/${REGISTRATION_SECRET}/g" \
        > dendrite/config/dendrite.yaml

    echo "✓ Dendrite config generated"
else
    echo "✓ Dendrite config already exists"
fi

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
