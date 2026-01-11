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
    echo "   - Set your Telegram bot token (from @BotFather)"
    echo "   - Set your Telegram user ID (from @userinfobot)"
    echo "   - Add your LLM API keys"
    echo ""
    read -p "Press Enter after editing .env, or Ctrl+C to abort..."
fi

# Create directories
echo ""
echo "Creating directories..."
mkdir -p data/postgres
mkdir -p data/backups
mkdir -p logs

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Start the stack:"
echo "   docker compose up -d"
echo ""
echo "2. Wait for services to be healthy:"
echo "   docker compose ps"
echo ""
echo "3. Send /start to your Telegram bot to test"
echo ""
echo "4. Install cron jobs from crontab.example"
echo ""
