"""Matrix message response helpers."""

from typing import Optional
from nio import AsyncClient


async def send_confirmation(
    client: AsyncClient,
    room_id: str,
    reply_to_event_id: str,
    category: str,
    confidence: float,
    extracted_name: str,
) -> str:
    """Send a confirmation message as a thread reply."""

    confidence_pct = int(confidence * 100)

    content = {
        "msgtype": "m.text",
        "body": (
            f"✓ Filed as {category}: \"{extracted_name}\"\n"
            f"Confidence: {confidence_pct}%\n"
            f"Reply `fix: <category>` if wrong"
        ),
        "m.relates_to": {"m.in_reply_to": {"event_id": reply_to_event_id}},
    }

    response = await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content=content,
    )

    return response.event_id


async def send_clarification_request(
    client: AsyncClient,
    room_id: str,
    reply_to_event_id: str,
    suggested_category: Optional[str],
    confidence: Optional[float],
) -> str:
    """Ask for clarification when confidence is low."""

    if suggested_category and confidence:
        confidence_pct = int(confidence * 100)
        body = (
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
        body = (
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

    content = {
        "msgtype": "m.text",
        "body": body,
        "m.relates_to": {"m.in_reply_to": {"event_id": reply_to_event_id}},
    }

    response = await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content=content,
    )

    return response.event_id


async def send_fix_confirmation(
    client: AsyncClient,
    room_id: str,
    reply_to_event_id: str,
    old_category: str,
    new_category: str,
    extracted_name: str,
) -> str:
    """Confirm a fix was applied."""

    content = {
        "msgtype": "m.text",
        "body": (
            f"✓ Fixed: moved from {old_category} → {new_category}\n"
            f"Entry: \"{extracted_name}\""
        ),
        "m.relates_to": {"m.in_reply_to": {"event_id": reply_to_event_id}},
    }

    response = await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content=content,
    )

    return response.event_id


async def send_error(
    client: AsyncClient,
    room_id: str,
    reply_to_event_id: str,
    message: str,
) -> str:
    """Send an error message."""

    content = {
        "msgtype": "m.text",
        "body": f"⚠️ {message}",
        "m.relates_to": {"m.in_reply_to": {"event_id": reply_to_event_id}},
    }

    response = await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content=content,
    )

    return response.event_id


async def send_message(
    client: AsyncClient,
    room_id: str,
    body: str,
    reply_to_event_id: Optional[str] = None,
) -> str:
    """Send a generic message, optionally as a reply."""

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"send_message: Sending message of length {len(body)} chars")
    logger.info(f"send_message: First 200 chars: {body[:200]}")
    logger.info(f"send_message: Last 200 chars: {body[-200:]}")

    content = {
        "msgtype": "m.text",
        "body": body,
    }

    if reply_to_event_id:
        content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to_event_id}}

    response = await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content=content,
    )

    logger.info(f"send_message: Message sent successfully, event_id={response.event_id}")

    return response.event_id
