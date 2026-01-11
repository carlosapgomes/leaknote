#!/usr/bin/env python3
"""
Weekly review cron job.
Run at 16:00 on Sundays.

Usage:
    python scripts/weekly_review.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from telegram import Bot
from config import Config
from weekly_review import generate_weekly_review, format_review_date_range
from db import close_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def send_review(bot: Bot, chat_id: int, content: str):
    """Send the weekly review to the owner."""
    date_range = format_review_date_range()
    full_message = f"📊 **Weekly Review - {date_range}**\n\n{content}"

    await bot.send_message(
        chat_id=chat_id,
        text=full_message,
    )


async def main():
    logger.info("Starting weekly review generation...")

    if not Config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    if not Config.TELEGRAM_OWNER_ID:
        logger.error("TELEGRAM_OWNER_ID not set")
        sys.exit(1)

    bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)

    try:
        logger.info("Generating weekly review...")
        review_content = await generate_weekly_review()
        logger.info(f"Review generated ({len(review_content)} chars)")

        await send_review(bot, Config.TELEGRAM_OWNER_ID, review_content)
        logger.info("Weekly review sent successfully")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
