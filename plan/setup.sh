#!/bin/bash
# Setup script for Second Brain with Dendrite
# Run this once before starting the stack

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "Second Brain + Dendrite Setup"
echo "========================================"

# Load environment variables
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
    
    # Use environment variable or default
    SERVER_NAME="${MATRIX_SERVER_NAME:-localhost}"
    DB_PASSWORD="${DENDRITE_DB_PASSWORD:-dendrite-password-change-me}"
    
    docker run --rm --entrypoint="/bin/sh" \
        -v "$(pwd)/dendrite/config:/mnt" \
        matrixdotorg/dendrite-monolith:latest \
        -c "/usr/bin/generate-config \
            -dir /var/dendrite/ \
            -db postgres://dendrite:${DB_PASSWORD}@postgres/dendrite?sslmode=disable \
            -server ${SERVER_NAME} > /mnt/dendrite.yaml"
    
    echo "✓ Dendrite config generated"
    echo ""
    echo "⚠️  Review dendrite/config/dendrite.yaml and adjust settings as needed"
    echo "   Key settings to check:"
    echo "   - global.server_name"
    echo "   - global.database.connection_string (password must match init-db.sql)"
    echo "   - client_api.registration_disabled (set to false to allow registration)"
else
    echo "✓ Dendrite config already exists"
fi

# Update init-db.sql with actual passwords
echo ""
echo "Updating database initialization script..."
SECONDBRAIN_PW="${SECONDBRAIN_DB_PASSWORD:-secondbrain-password-change-me}"
DENDRITE_PW="${DENDRITE_DB_PASSWORD:-dendrite-password-change-me}"

cat > init-db.sql << EOF
-- Initialize databases for Dendrite and Second Brain
-- This runs on first PostgreSQL startup

-- Create Dendrite database and user
CREATE USER dendrite WITH PASSWORD '${DENDRITE_PW}';
CREATE DATABASE dendrite OWNER dendrite;

-- Create Second Brain database and user  
CREATE USER secondbrain WITH PASSWORD '${SECONDBRAIN_PW}';
CREATE DATABASE secondbrain OWNER secondbrain;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE dendrite TO dendrite;
GRANT ALL PRIVILEGES ON DATABASE secondbrain TO secondbrain;

-- Connect to secondbrain database to create extensions
\c secondbrain
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOF

echo "✓ Database init script updated"

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Review and edit these files if needed:"
echo "   - .env (passwords, API keys)"
echo "   - dendrite/config/dendrite.yaml"
echo "   - init-db.sql (generated with your passwords)"
echo ""
echo "2. Start the stack:"
echo "   docker compose up -d"
echo ""
echo "3. Wait for services to be healthy:"
echo "   docker compose ps"
echo ""
echo "4. Create Matrix users (run create-users.sh or manually):"
echo "   ./create-users.sh"
echo ""
echo "5. Create the inbox room and invite the bot"
echo ""
echo "6. Install cron jobs from crontab.example"
echo ""
