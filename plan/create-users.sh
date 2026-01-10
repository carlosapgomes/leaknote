#!/bin/bash
# Create Matrix users in Dendrite
# Run this after the stack is up and healthy

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment
source .env

echo "========================================"
echo "Create Matrix Users"
echo "========================================"
echo ""

# Check if Dendrite is running
if ! docker ps --format '{{.Names}}' | grep -q '^dendrite-matrix$'; then
    echo "ERROR: Dendrite container is not running"
    echo "Start the stack first: docker compose up -d"
    exit 1
fi

# Wait for Dendrite to be ready
echo "Checking Dendrite health..."
sleep 2

# Create bot user
echo ""
echo "Creating bot user: ${MATRIX_USER_ID:-@secondbrain:localhost}"
read -s -p "Enter password for bot user: " BOT_PASSWORD
echo ""

# Extract username from full Matrix ID (@user:server -> user)
BOT_USERNAME=$(echo "${MATRIX_USER_ID:-@secondbrain:localhost}" | sed 's/@\([^:]*\):.*/\1/')

docker exec -it dendrite-matrix /usr/bin/create-account \
    -config /etc/dendrite/dendrite.yaml \
    -username "$BOT_USERNAME" \
    -password "$BOT_PASSWORD"

echo "✓ Bot user created"

# Create your personal user
echo ""
echo "Creating your user: ${DIGEST_TARGET_USER:-@carlos:localhost}"
read -s -p "Enter password for your user: " USER_PASSWORD
echo ""

# Extract username
YOUR_USERNAME=$(echo "${DIGEST_TARGET_USER:-@carlos:localhost}" | sed 's/@\([^:]*\):.*/\1/')

docker exec -it dendrite-matrix /usr/bin/create-account \
    -config /etc/dendrite/dendrite.yaml \
    -username "$YOUR_USERNAME" \
    -password "$USER_PASSWORD" \
    -admin  # Make yourself an admin

echo "✓ Your user created (as admin)"

echo ""
echo "========================================"
echo "Users Created!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Update .env with the bot password you just set:"
echo "   MATRIX_PASSWORD=$BOT_PASSWORD"
echo ""
echo "2. Connect to your Matrix server with Element:"
echo "   - Homeserver: http://localhost:8008 (or your server's address)"
echo "   - Log in with your user credentials"
echo ""
echo "3. Create a room called 'sb-inbox' (or your preferred name)"
echo ""
echo "4. Invite the bot user to the room"
echo ""
echo "5. Update .env with the room alias:"
echo "   MATRIX_INBOX_ROOM=#sb-inbox:${MATRIX_SERVER_NAME:-localhost}"
echo ""
echo "6. Restart the bot to pick up the new config:"
echo "   docker compose restart secondbrain"
echo ""
