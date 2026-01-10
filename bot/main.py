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
        """Resolve a room alias to room ID, joining if invited."""
        response = await self.client.room_resolve_alias(alias)
        if hasattr(response, "room_id"):
            return response.room_id

        # Room might not be resolvable yet - check if we have an invitation
        logger.info(f"Could not resolve {alias}, checking for invitations...")
        sync_response = await self.client.sync(timeout=3000)

        if hasattr(sync_response, "rooms") and hasattr(sync_response.rooms, "invite"):
            for room_id, invite_info in sync_response.rooms.invite.items():
                # Check if this invitation matches our desired room
                # Try joining the invitation
                logger.info(f"Found invitation to room {room_id}, joining...")
                join_response = await self.client.join(room_id)
                if hasattr(join_response, "room_id"):
                    logger.info(f"Successfully joined room {room_id}")
                    # Try resolving the alias again
                    response = await self.client.room_resolve_alias(alias)
                    if hasattr(response, "room_id"):
                        return response.room_id
                    # If still can't resolve, return the room_id we just joined
                    return room_id

        raise ValueError(
            f"Could not resolve room alias: {alias}\n"
            f"Make sure the room exists and the bot has been invited."
        )

    def get_reply_to_event_id(self, event: RoomMessageText) -> Optional[str]:
        """Extract the event ID this message is replying to, if any."""
        relates_to = getattr(event, "source", {}).get("content", {}).get("m.relates_to", {})
        in_reply_to = relates_to.get("m.in_reply_to", {})
        return in_reply_to.get("event_id")

    async def get_original_event_id(self, reply_to_id: str, room_id: str) -> Optional[str]:
        """
        Follow the reply thread to find the original user message.

        If reply_to_id is the bot's message (confirmation/clarification),
        follow its reply chain to find the original user message.

        Returns the event_id of the original user message, or None if not found.
        """
        # First, try to get inbox_log directly (original user message)
        log_entry = await get_inbox_log_by_event(reply_to_id)
        if log_entry:
            return reply_to_id

        # If not found, this might be a reply to the bot's message
        # Get the event to check if it's from the bot
        try:
            response = await self.client.room_get_event(room_id, reply_to_id)
            if response and response.event:
                sender = response.event.source.get("sender")
                # If this is the bot's message, follow the reply thread
                if sender == self.client.user_id:
                    relates_to = response.event.source.get("content", {}).get("m.relates_to", {})
                    in_reply_to = relates_to.get("m.in_reply_to", {})
                    original_id = in_reply_to.get("event_id")
                    if original_id:
                        # Verify this original_id has an inbox_log entry
                        log_entry = await get_inbox_log_by_event(original_id)
                        if log_entry:
                            return original_id
        except Exception as e:
            logger.warning(f"Failed to get event {reply_to_id}: {e}")

        return None

    def extract_reply_text(self, event: RoomMessageText) -> str:
        """
        Extract just the new text from a reply, excluding quoted content.

        Matrix replies include the original message in the body formatted as:
        > <@sender:server> original text

        We need to extract only the new text that comes after the quotes.
        """
        text = event.body
        lines = text.split("\n")

        # Find the first non-quote line (not starting with ">")
        new_text_lines = []
        found_non_quote = False
        for line in lines:
            if not line.strip().startswith(">"):
                found_non_quote = True
            if found_non_quote:
                new_text_lines.append(line)

        new_text = "\n".join(new_text_lines).strip()
        return new_text if new_text else text

    async def handle_reply(
        self,
        room: MatrixRoom,
        event: RoomMessageText,
        reply_to_id: str,
    ):
        """Handle a reply to a previous message."""
        # Extract just the new text, excluding quoted reply content
        text = self.extract_reply_text(event)
        logger.info(f"Extracted reply text: '{text}'")

        # Check if it's a fix command
        fix_category = parse_fix_command(text)
        if fix_category:
            # Follow the reply thread to find the original user message
            original_event_id = await self.get_original_event_id(reply_to_id, room.room_id)

            if not original_event_id:
                await send_error(
                    self.client,
                    room.room_id,
                    event.event_id,
                    "Couldn't find the original message to fix. Please reply directly to your message or the bot's confirmation.",
                )
                return

            logger.info(f"Fix command: replying to {original_event_id}, changing to {fix_category}")

            success, msg, old_category, extracted_name = await handle_fix(
                original_event_id, fix_category
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

            # Try to parse as a category (with or without colon)
            original_text = pending["raw_text"]
            text_lower = text.lower().strip()

            # Check if user typed a category label (case insensitive, with or without colon)
            # Note: "people" is NOT a valid category - only "person" is
            valid_categories = ["person", "project", "idea", "admin", "decision", "howto", "snippet"]

            matched_category = None
            for cat in valid_categories:
                if text_lower.startswith(f"{cat}:"):
                    # They used the full prefix with colon
                    matched_category = cat
                    break
                elif text_lower == cat:
                    # They just typed the category name
                    matched_category = cat
                    break

            if matched_category:
                # Prepend the category to the original message
                new_text = f"{matched_category}: {original_text}"
            else:
                # Not a recognized category - treat their reply as completely new input
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

            try:
                response = await handle_command(command, arg)
                logger.info(f"Command response: {response[:100]}...")
            except Exception as e:
                logger.error(f"Command error: {e}")
                response = f"Error: {str(e)}"

            await send_message(
                self.client,
                room.room_id,
                response,
                event.event_id,
            )
            return

        # Check if this is a reply to another message
        reply_to_id = self.get_reply_to_event_id(event)
        logger.info(f"Reply check: reply_to_id={reply_to_id}, event.source={event.source}")
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
            logger.info(f"Checking for inbox_log with event_id: {event.event_id}")
            log_entry = await get_inbox_log_by_event(event.event_id)
            logger.info(f"Found log_entry: {log_entry}")

            clarification_event_id = await send_clarification_request(
                self.client,
                room.room_id,
                event.event_id,
                category,
                confidence,
            )
            logger.info(f"Sent clarification request with event_id: {clarification_event_id}")

            # Store pending clarification
            # NOTE: matrix_event_id should be the clarification message event ID,
            # not the original message event ID, so users can reply to it
            if log_entry:
                logger.info(f"Creating pending clarification for inbox_log_id: {log_entry['id']}")
                await insert_pending_clarification(
                    inbox_log_id=str(log_entry["id"]),
                    matrix_event_id=clarification_event_id,
                    matrix_room_id=room.room_id,
                    suggested_category=category,
                )
                logger.info(f"Pending clarification created successfully")
            else:
                logger.warning(f"No log_entry found, cannot create pending clarification!")

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

        # Join the room if not already joined
        join_response = await self.client.join(self.inbox_room_id)
        if hasattr(join_response, "room_id"):
            logger.info(f"Joined room: {self.inbox_room_id}")
        else:
            logger.warning(f"Could not join room {self.inbox_room_id}: {join_response}")

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
