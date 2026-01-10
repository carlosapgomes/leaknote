#!/bin/bash
# Create Matrix users in Dendrite
# Run this after the stack is up and healthy

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source .env

echo "========================================"
echo "Create Matrix Users"
echo "========================================"
echo ""

# Check if Dendrite is running
if ! docker ps --format '{{.Names}}' | grep -q '^leaknote-dendrite$'; then
    echo "ERROR: Dendrite container is not running"
    echo "Start the stack first: docker compose up -d"
    exit 1
fi

sleep 2

# Create bot user
echo "Creating bot user: ${MATRIX_USER_ID:-@leaknote:localhost}"
read -s -p "Enter password for bot user: " BOT_PASSWORD
echo ""

BOT_USERNAME=$(echo "${MATRIX_USER_ID:-@leaknote:localhost}" | sed 's/@\([^:]*\):.*/\1/')

docker exec -it leaknote-dendrite /usr/bin/create-account \
    -config /etc/dendrite/dendrite.yaml \
    -username "$BOT_USERNAME" \
    -password "$BOT_PASSWORD"

echo "✓ Bot user created"

# Create your personal user
echo ""
echo "Creating your user: ${DIGEST_TARGET_USER:-@yourname:localhost}"
read -s -p "Enter password for your user: " USER_PASSWORD
echo ""

YOUR_USERNAME=$(echo "${DIGEST_TARGET_USER:-@yourname:localhost}" | sed 's/@\([^:]*\):.*/\1/')

docker exec -it leaknote-dendrite /usr/bin/create-account \
    -config /etc/dendrite/dendrite.yaml \
    -username "$YOUR_USERNAME" \
    -password "$USER_PASSWORD" \
    -admin

echo "✓ Your user created (as admin)"

echo ""
echo "========================================"
echo "Users Created!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Update .env with the bot password:"
echo "   MATRIX_PASSWORD=<password you entered>"
echo ""
echo "2. Connect to Matrix with Element:"
echo "   Homeserver: http://localhost:8008"
echo ""
echo "3. Create room 'leaknote-inbox' and invite bot"
echo ""
echo "4. Restart bot: docker compose restart leaknote"
echo ""
