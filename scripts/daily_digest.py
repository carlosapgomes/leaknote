#!/usr/bin/env python3
"""
Daily digest cron job.
Run at 06:00 daily.

Usage:
    python scripts/daily_digest.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from telegram import Bot
from config import Config
from digest import generate_daily_digest, format_digest_date
from db import close_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def send_digest(bot: Bot, chat_id: int, content: str):
    """Send the daily digest to the owner."""
    date_str = format_digest_date()
    full_message = f"☀️ **Daily Digest - {date_str}**\n\n{content}"

    await bot.send_message(
        chat_id=chat_id,
        text=full_message,
    )


async def main():
    logger.info("Starting daily digest generation...")

    if not Config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    if not Config.TELEGRAM_OWNER_ID:
        logger.error("TELEGRAM_OWNER_ID not set")
        sys.exit(1)

    bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)

    try:
        logger.info("Generating daily digest...")
        digest_content = await generate_daily_digest()
        logger.info(f"Digest generated ({len(digest_content)} chars)")

        await send_digest(bot, Config.TELEGRAM_OWNER_ID, digest_content)
        logger.info("Daily digest sent successfully")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
