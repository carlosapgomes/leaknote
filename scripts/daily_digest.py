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

from nio import AsyncClient, LoginResponse
from config import Config
from digest import generate_daily_digest, format_digest_date
from db import close_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def get_dm_room_id(client: AsyncClient, user_id: str) -> str:
    """Get or create a DM room with the specified user."""
    await client.sync(timeout=10000)

    # Look for existing DM
    for room_id, room in client.rooms.items():
        if len(room.users) == 2:
            if user_id in [u for u in room.users.keys()]:
                return room_id

    # Create new DM room
    response = await client.room_create(
        is_direct=True,
        invite=[user_id],
    )
    return response.room_id


async def send_digest(client: AsyncClient, room_id: str, content: str):
    """Send the daily digest to a room."""
    date_str = format_digest_date()
    full_message = f"☀️ **Daily Digest - {date_str}**\n\n{content}"

    await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content={
            "msgtype": "m.text",
            "body": full_message,
        },
    )


async def main():
    logger.info("Starting daily digest generation...")

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

        logger.info("Generating daily digest...")
        digest_content = await generate_daily_digest()
        logger.info(f"Digest generated ({len(digest_content)} chars)")

        room_id = await get_dm_room_id(client, target_user)
        logger.info(f"DM room: {room_id}")

        await send_digest(client, room_id, digest_content)
        logger.info("Daily digest sent successfully")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        await client.close()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
