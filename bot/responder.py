"""Telegram message response helpers."""

from typing import Optional
from telegram import Bot


async def send_confirmation(
    bot: Bot,
    chat_id: int,
    reply_to_message_id: int,
    category: str,
    confidence: float,
    extracted_name: str,
) -> int:
    """Send a confirmation message as a reply."""
    confidence_pct = int(confidence * 100)

    text = (
        f"✓ Filed as {category}: \"{extracted_name}\"\n"
        f"Confidence: {confidence_pct}%\n"
        f"Reply `fix: <category>` if wrong"
    )

    message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
    )

    return message.message_id


async def send_clarification_request(
    bot: Bot,
    chat_id: int,
    reply_to_message_id: int,
    suggested_category: Optional[str],
    confidence: Optional[float],
) -> int:
    """Ask for clarification when confidence is low."""

    if suggested_category and confidence:
        confidence_pct = int(confidence * 100)
        text = (
            f"🤔 Not sure about this one.\n"
            f"Best guess: {suggested_category} ({confidence_pct}% confident)\n\n"
            f"Reply with one of:\n"
            f"• `person:` - if about a person\n"
            f"• `project:` - if it's a project\n"
            f"• `idea:` - if it's an idea\n"
            f"• `admin:` - if it's a task/errand\n"
            f"• `decision:` - to save as a decision\n"
            f"• `howto:` - to save as a how-to\n"
            f"• `snippet:` - to save as a snippet\n"
            f"• `skip` - to ignore"
        )
    else:
        text = (
            f"❓ I couldn't classify this.\n\n"
            f"Reply with one of:\n"
            f"• `person:` - if about a person\n"
            f"• `project:` - if it's a project\n"
            f"• `idea:` - if it's an idea\n"
            f"• `admin:` - if it's a task/errand\n"
            f"• `decision:` - to save as a decision\n"
            f"• `howto:` - to save as a how-to\n"
            f"• `snippet:` - to save as a snippet\n"
            f"• `skip` - to ignore"
        )

    message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
    )

    return message.message_id


async def send_fix_confirmation(
    bot: Bot,
    chat_id: int,
    reply_to_message_id: int,
    old_category: str,
    new_category: str,
    extracted_name: str,
) -> int:
    """Confirm a fix was applied."""

    text = (
        f"✓ Fixed: moved from {old_category} → {new_category}\n"
        f"Entry: \"{extracted_name}\""
    )

    message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
    )

    return message.message_id


async def send_error(
    bot: Bot,
    chat_id: int,
    reply_to_message_id: int,
    message: str,
) -> int:
    """Send an error message."""

    msg = await bot.send_message(
        chat_id=chat_id,
        text=f"⚠️ {message}",
        reply_to_message_id=reply_to_message_id,
    )

    return msg.message_id


async def send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_to_message_id: Optional[int] = None,
) -> int:
    """Send a generic message, optionally as a reply."""

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"send_message: Sending message of length {len(text)} chars")
    logger.info(f"send_message: First 200 chars: {text[:200]}")
    logger.info(f"send_message: Last 200 chars: {text[-200:]}")

    message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
    )

    logger.info(f"send_message: Message sent successfully, message_id={message.message_id}")

    return message.message_id
