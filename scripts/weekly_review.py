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

from nio import AsyncClient, LoginResponse
from config import Config
from weekly_review import generate_weekly_review, format_review_date_range
from db import close_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def get_dm_room_id(client: AsyncClient, user_id: str) -> str:
    """Get or create a DM room with the specified user."""
    await client.sync(timeout=10000)

    for room_id, room in client.rooms.items():
        if len(room.users) == 2:
            if user_id in [u for u in room.users.keys()]:
                return room_id

    response = await client.room_create(
        is_direct=True,
        invite=[user_id],
    )
    return response.room_id


async def send_review(client: AsyncClient, room_id: str, content: str):
    """Send the weekly review to a room."""
    date_range = format_review_date_range()
    full_message = f"📊 **Weekly Review - {date_range}**\n\n{content}"

    await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content={
            "msgtype": "m.text",
            "body": full_message,
        },
    )


async def main():
    logger.info("Starting weekly review generation...")

    target_user = Config.DIGEST_TARGET_USER
    if not target_user:
        logger.error("DIGEST_TARGET_USER not set")
        sys.exit(1)

    client = AsyncClient(Config.MATRIX_HOMESERVER, Config.MATRIX_USER_ID)

    try:
        response = await client.login(Config.MATRIX_PASSWORD)
        if not isinstance(response, LoginResponse):
            logger.error(f"Login failed: {response}")
            sys.exit(1)

        logger.info("Logged in to Matrix")

        logger.info("Generating weekly review...")
        review_content = await generate_weekly_review()
        logger.info(f"Review generated ({len(review_content)} chars)")

        room_id = await get_dm_room_id(client, target_user)
        logger.info(f"DM room: {room_id}")

        await send_review(client, room_id, review_content)
        logger.info("Weekly review sent successfully")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        await client.close()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
