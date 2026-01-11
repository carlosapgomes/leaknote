"""Leaknote Bot - Main entry point (Telegram version)."""

import asyncio
import logging
import sys
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)

from bot.config import Config
from router import route_message, CATEGORY_DISPLAY
from bot.db import (
    close_pool,
    get_record,
    insert_pending_clarification,
    get_pending_by_reply_to,
    delete_pending_clarification,
    get_inbox_log_by_event,
    insert_inbox_log,
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
    """Telegram bot for Leaknote."""

    def __init__(self):
        self.application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    def _get_help_text(self) -> str:
        """Get the help text for commands."""
        return (
            "Leaknote bot is running.\n\n"
            "Send messages here or in the inbox channel to capture thoughts.\n"
            "Available commands:\n"
            "• ?recall <query> - Search decisions, howtos, snippets\n"
            "• ?search <query> - Search all categories\n"
            "• ?people <query> - Search people\n"
            "• ?projects [status] - List projects\n"
            "• ?ideas - List recent ideas\n"
            "• ?admin [due] - List admin tasks\n"
            "• fix: <category> - Reclassify a message (reply to it)"
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        # Security check - only owner can use /start
        if update.effective_user.id != Config.TELEGRAM_OWNER_ID:
            logger.warning(f"Unauthorized /start attempt from user {update.effective_user.id}")
            return

        await update.message.reply_text(self._get_help_text())

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        # Security check - only owner can use /help
        if update.effective_user.id != Config.TELEGRAM_OWNER_ID:
            logger.warning(f"Unauthorized /help attempt from user {update.effective_user.id}")
            return

        await update.message.reply_text(self._get_help_text())

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all text messages."""
        # Security check - only allow messages from the owner
        # Works with both DMs and channels (as long as owner sends them)
        if update.effective_user.id != Config.TELEGRAM_OWNER_ID:
            logger.warning(f"Unauthorized message from user {update.effective_user.id} in chat {update.effective_chat.id}")
            return

        message = update.message
        text = message.text

        if not text:
            return

        logger.info(f"Message from {update.effective_user.id} in chat {update.effective_chat.id} (msg_id {message.message_id}): {text[:50]}...")

        # Check if this is a reply to a bot message (clarification or fix)
        if message.reply_to_message and message.reply_to_message.from_user.is_bot:
            await self.handle_reply(update, context)
            return

        # Check for query commands
        command_result = parse_command(text)
        if command_result:
            await self.handle_query_command(update, context, command_result)
            return

        # Check for fix command
        fix_result = parse_fix_command(text)
        if fix_result:
            await self.handle_fix_command(update, context, fix_result)
            return

        # Regular capture flow
        await self.handle_capture(update, context)

    async def handle_capture(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process a capture message through classification."""
        text = update.message.text
        message_id = update.message.message_id
        chat_id = update.effective_chat.id

        # Route the message
        category, record_id, confidence, status = await route_message(
            text,
            str(message_id),
            str(chat_id),
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
                context.bot,
                chat_id,
                message_id,
                CATEGORY_DISPLAY.get(category, category),
                confidence,
                extracted_name,
            )

        elif status == "needs_review":
            # Low confidence or error - ask for clarification
            logger.info(f"Checking for inbox_log with telegram_message_id: {message_id}")
            log_entry = await get_inbox_log_by_event(str(message_id))
            logger.info(f"Found log_entry: {log_entry}")

            clarification_message_id = await send_clarification_request(
                context.bot,
                chat_id,
                message_id,
                category,
                confidence,
            )
            logger.info(f"Sent clarification request with message_id: {clarification_message_id}")

            # Store pending clarification
            if log_entry:
                logger.info(f"Creating pending clarification for inbox_log_id: {log_entry['id']}")
                await insert_pending_clarification(
                    inbox_log_id=str(log_entry["id"]),
                    telegram_message_id=str(clarification_message_id),
                    telegram_chat_id=str(chat_id),
                    suggested_category=category,
                )
                logger.info(f"Pending clarification created successfully")
            else:
                logger.warning(f"No log_entry found, cannot create pending clarification!")

    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle reply to clarification request or fix command."""
        text = update.message.text
        reply_to_message_id = update.message.reply_to_message.message_id
        chat_id = update.effective_chat.id
        message_id = update.message.message_id

        logger.info(f"Reply text: '{text}'")

        # Check if it's a fix command
        fix_category = parse_fix_command(text)
        if fix_category:
            # Find the original user message
            # The user replied to the bot's confirmation, which itself is a reply to the original message
            original_message_id = update.message.reply_to_message.reply_to_message.message_id if update.message.reply_to_message.reply_to_message else None

            if not original_message_id:
                # Fallback: try to find inbox_log by the clarification message
                log_entry = await get_inbox_log_by_event(str(reply_to_message_id))
                if log_entry:
                    original_message_id = log_entry.get("telegram_message_id")

            if not original_message_id:
                await send_error(
                    context.bot,
                    chat_id,
                    message_id,
                    "Couldn't find the original message to fix. Please reply directly to your message or the bot's confirmation.",
                )
                return

            logger.info(f"Fix command: original message {original_message_id}, changing to {fix_category}")

            success, msg, old_category, extracted_name = await handle_fix(
                str(original_message_id), fix_category
            )

            if success:
                await send_fix_confirmation(
                    context.bot,
                    chat_id,
                    message_id,
                    old_category,
                    CATEGORY_DISPLAY.get(fix_category, fix_category),
                    extracted_name,
                )
            else:
                await send_error(context.bot, chat_id, message_id, msg)
            return

        # Check if it's a clarification response
        pending = await get_pending_by_reply_to(str(reply_to_message_id))
        if pending:
            # User is clarifying a previous uncertain message
            if text.lower() == "skip":
                await delete_pending_clarification(str(pending["id"]))
                await send_message(
                    context.bot,
                    chat_id,
                    "👍 Skipped",
                    message_id,
                )
                return

            # Try to parse as a category (with or without colon)
            original_text = pending["raw_text"]
            text_lower = text.lower().strip()

            # Check if user typed a category label (case insensitive, with or without colon)
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

            # Get the original message_id from pending clarification
            original_log = await get_inbox_log_by_event(pending.get("telegram_message_id"))
            original_message_id = original_log.get("telegram_message_id") if original_log else str(message_id)

            category, record_id, confidence, status = await route_message(
                new_text,
                original_message_id,
                str(chat_id),
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
                    context.bot,
                    chat_id,
                    message_id,
                    CATEGORY_DISPLAY.get(category, category),
                    confidence or 1.0,
                    extracted_name,
                )
            else:
                await send_error(
                    context.bot,
                    chat_id,
                    message_id,
                    "Still couldn't classify. Try using a prefix like `decision: your text`",
                )

    async def handle_query_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, command_result):
        """Handle ?recall, ?search, etc."""
        command, arg = command_result
        logger.info(f"Command: {command}, arg: {arg}")

        try:
            response = await handle_command(command, arg)
            logger.info(f"Command response: {response[:100]}...")
        except Exception as e:
            logger.error(f"Command error: {e}")
            response = f"Error: {str(e)}"

        # Telegram has 4096 char limit per message - split if needed
        await self.send_long_message(update.effective_chat.id, response, context.bot)

    async def send_long_message(self, chat_id: int, text: str, bot):
        """Send long message, splitting if needed."""
        MAX_LENGTH = 4096
        if len(text) <= MAX_LENGTH:
            await bot.send_message(chat_id, text)
        else:
            # Split at newlines near the limit
            chunks = []
            current_chunk = ""
            for line in text.split('\n'):
                if len(current_chunk) + len(line) + 1 > MAX_LENGTH:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    current_chunk += '\n' + line if current_chunk else line
            if current_chunk:
                chunks.append(current_chunk)

            for chunk in chunks:
                await bot.send_message(chat_id, chunk)

    async def handle_fix_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, fix_result):
        """Handle fix: command (not as a reply)."""
        # This handles "fix: category" when NOT replying to a message
        # We need to find the most recent message from this user
        await send_error(
            context.bot,
            update.effective_chat.id,
            update.message.message_id,
            "Please reply to the message you want to fix with `fix: <category>`",
        )

    async def run(self):
        """Start the bot."""
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Start polling
        logger.info("Starting Telegram bot...")
        async with self.application:
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

            # Keep running until interrupted
            try:
                import signal
                stop_event = asyncio.Event()

                def signal_handler(signum, frame):
                    stop_event.set()

                signal.signal(signal.SIGINT, signal_handler)
                signal.signal(signal.SIGTERM, signal_handler)

                await stop_event.wait()
            finally:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()


async def main():
    """Main entry point."""
    # Validate config
    missing = Config.validate()
    if missing:
        logger.error(f"Missing configuration: {', '.join(missing)}")
        sys.exit(1)

    # Start bot
    bot = LeaknoteBot()
    try:
        await bot.run()
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
