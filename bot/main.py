"""Leaknote Bot - Main entry point."""

import asyncio
import logging
import sys
from typing import Optional

from nio import AsyncClient, MatrixRoom, RoomMessageText, LoginResponse

from config import Config
from router import route_message, CATEGORY_DISPLAY
from db import (
    close_pool,
    get_record,
    insert_pending_clarification,
    get_pending_by_reply_to,
    delete_pending_clarification,
    get_inbox_log_by_event,
)
from responder import (
    send_confirmation,
    send_clarification_request,
    send_fix_confirmation,
    send_error,
    send_message,
)
from fix_handler import parse_fix_command, handle_fix
from commands import parse_command, handle_command

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class LeaknoteBot:
    """Matrix bot for Leaknote."""

    def __init__(self):
        self.client = AsyncClient(Config.MATRIX_HOMESERVER, Config.MATRIX_USER_ID)
        self.inbox_room_id: Optional[str] = None

    async def login(self):
        """Log in to the Matrix server."""
        response = await self.client.login(Config.MATRIX_PASSWORD)
        if isinstance(response, LoginResponse):
            logger.info(f"Logged in as {Config.MATRIX_USER_ID}")
        else:
            logger.error(f"Login failed: {response}")
            sys.exit(1)

    async def resolve_room_alias(self, alias: str) -> str:
        """Resolve a room alias to room ID."""
        response = await self.client.room_resolve_alias(alias)
        if hasattr(response, "room_id"):
            return response.room_id
        raise ValueError(f"Could not resolve room alias: {alias}")

    def get_reply_to_event_id(self, event: RoomMessageText) -> Optional[str]:
        """Extract the event ID this message is replying to, if any."""
        relates_to = getattr(event, "source", {}).get("content", {}).get("m.relates_to", {})
        in_reply_to = relates_to.get("m.in_reply_to", {})
        return in_reply_to.get("event_id")

    async def handle_reply(
        self,
        room: MatrixRoom,
        event: RoomMessageText,
        reply_to_id: str,
    ):
        """Handle a reply to a previous message."""
        text = event.body.strip()

        # Check if it's a fix command
        fix_category = parse_fix_command(text)
        if fix_category:
            # Get the original message being fixed
            original_log = await get_inbox_log_by_event(reply_to_id)

            if not original_log:
                await send_error(
                    self.client,
                    room.room_id,
                    event.event_id,
                    "Couldn't find the original message. Reply directly to your message with `fix: <category>`",
                )
                return

            success, msg, old_category, extracted_name = await handle_fix(
                reply_to_id, fix_category
            )

            if success:
                await send_fix_confirmation(
                    self.client,
                    room.room_id,
                    event.event_id,
                    old_category,
                    CATEGORY_DISPLAY.get(fix_category, fix_category),
                    extracted_name,
                )
            else:
                await send_error(self.client, room.room_id, event.event_id, msg)
            return

        # Check if it's a clarification response
        pending = await get_pending_by_reply_to(reply_to_id)
        if pending:
            # User is clarifying a previous uncertain message
            if text.lower() == "skip":
                await delete_pending_clarification(str(pending["id"]))
                await send_message(
                    self.client,
                    room.room_id,
                    "👍 Skipped",
                    event.event_id,
                )
                return

            # Try to parse as a category prefix
            original_text = pending["raw_text"]

            # Check if user provided a prefix
            prefixes = ["person:", "project:", "idea:", "admin:", "decision:", "howto:", "snippet:"]
            matched_prefix = None
            for prefix in prefixes:
                if text.lower().startswith(prefix):
                    matched_prefix = prefix
                    break

            if matched_prefix:
                # User provided category - prepend to original and re-route
                new_text = f"{matched_prefix} {original_text}"
            else:
                # Just use what user typed as the new input
                new_text = text

            category, record_id, confidence, status = await route_message(
                new_text,
                event.event_id,
                room.room_id,
            )

            await delete_pending_clarification(str(pending["id"]))

            if status == "filed" and record_id:
                table = category
                record = await get_record(table, record_id)
                extracted_name = (
                    record.get("name") or record.get("title") or new_text[:50]
                    if record
                    else new_text[:50]
                )

                await send_confirmation(
                    self.client,
                    room.room_id,
                    event.event_id,
                    CATEGORY_DISPLAY.get(category, category),
                    confidence or 1.0,
                    extracted_name,
                )
            else:
                await send_error(
                    self.client,
                    room.room_id,
                    event.event_id,
                    "Still couldn't classify. Try using a prefix like `decision: your text`",
                )
            return

    async def on_message(self, room: MatrixRoom, event: RoomMessageText):
        """Handle incoming messages."""
        # Ignore our own messages
        if event.sender == self.client.user_id:
            return

        # Only process messages in the inbox room
        if room.room_id != self.inbox_room_id:
            return

        text = event.body.strip()
        if not text:
            return

        logger.info(f"Message from {event.sender}: {text[:50]}...")

        # Check for query commands first
        command_result = parse_command(text)
        if command_result:
            command, arg = command_result
            logger.info(f"Command: {command}, arg: {arg}")

            response = await handle_command(command, arg)

            await send_message(
                self.client,
                room.room_id,
                response,
                event.event_id,
            )
            return

        # Check if this is a reply to another message
        reply_to_id = self.get_reply_to_event_id(event)
        if reply_to_id:
            await self.handle_reply(room, event, reply_to_id)
            return

        # New message - route it
        category, record_id, confidence, status = await route_message(
            text,
            event.event_id,
            room.room_id,
        )

        if status == "filed" and record_id:
            # Successfully filed
            table = category
            record = await get_record(table, record_id)
            extracted_name = (
                record.get("name") or record.get("title") or text[:50]
                if record
                else text[:50]
            )

            await send_confirmation(
                self.client,
                room.room_id,
                event.event_id,
                CATEGORY_DISPLAY.get(category, category),
                confidence,
                extracted_name,
            )

        elif status == "needs_review":
            # Low confidence or error - ask for clarification
            log_entry = await get_inbox_log_by_event(event.event_id)

            clarification_event_id = await send_clarification_request(
                self.client,
                room.room_id,
                event.event_id,
                category,
                confidence,
            )

            # Store pending clarification
            if log_entry:
                await insert_pending_clarification(
                    inbox_log_id=str(log_entry["id"]),
                    matrix_event_id=event.event_id,
                    matrix_room_id=room.room_id,
                    suggested_category=category,
                )

    async def run(self):
        """Start the bot."""
        # Validate config
        missing = Config.validate()
        if missing:
            logger.error(f"Missing required configuration: {', '.join(missing)}")
            sys.exit(1)

        await self.login()

        # Resolve room alias to ID
        if Config.MATRIX_INBOX_ROOM.startswith("#"):
            self.inbox_room_id = await self.resolve_room_alias(Config.MATRIX_INBOX_ROOM)
        else:
            self.inbox_room_id = Config.MATRIX_INBOX_ROOM

        logger.info(f"Watching room: {self.inbox_room_id}")

        # Register event callback
        self.client.add_event_callback(self.on_message, RoomMessageText)

        # Sync loop with reconnection
        while True:
            try:
                await self.client.sync_forever(timeout=30000)
            except Exception as e:
                logger.error(f"Sync error: {e}")
                logger.info("Reconnecting in 30 seconds...")
                await asyncio.sleep(30)
                try:
                    await self.client.close()
                except Exception:
                    pass
                self.client = AsyncClient(Config.MATRIX_HOMESERVER, Config.MATRIX_USER_ID)
                await self.login()


async def main():
    """Main entry point."""
    bot = LeaknoteBot()
    try:
        await bot.run()
    finally:
        await bot.client.close()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
