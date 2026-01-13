"""Message routing logic."""

import asyncio
import logging
from typing import Tuple, Optional

from classifier import classify_thought, parse_reference
from bot.db import insert_record, insert_inbox_log
from bot.config import Config

logger = logging.getLogger(__name__)


# Map categories to table names
CATEGORY_TABLE_MAP = {
    "people": "people",
    "projects": "projects",
    "ideas": "ideas",
    "admin": "admin",
    "decisions": "decisions",
    "howtos": "howtos",
    "snippets": "snippets",
}

# Display names for user-facing messages
CATEGORY_DISPLAY = {
    "people": "person",
    "projects": "project",
    "ideas": "idea",
    "admin": "admin",
    "decisions": "decision",
    "howtos": "howto",
    "snippets": "snippet",
}


async def route_message(
    text: str,
    telegram_message_id: str,
    telegram_chat_id: str,
) -> Tuple[Optional[str], Optional[str], Optional[float], str]:
    """
    Route a message to the appropriate table.

    Returns: (category, record_id, confidence, status)
    - status: 'filed' | 'needs_review'
    """

    # Check for reference prefix first
    ref_result = parse_reference(text)

    if ref_result:
        # Reference with prefix - store directly
        category = ref_result["category"]
        table = CATEGORY_TABLE_MAP[category]
        extracted = ref_result["extracted"]

        record_id = await insert_record(table, extracted)

        await insert_inbox_log(
            raw_text=text,
            destination=category,
            record_id=record_id,
            confidence=1.0,  # Prefix = explicit intent = full confidence
            status="filed",
            telegram_message_id=telegram_message_id,
            telegram_chat_id=telegram_chat_id,
        )

        # Enhance with memory layer (run in background)
        asyncio.create_task(
            _enhance_with_memory(
                text=text,
                category=category,
                record_id=record_id,
                extracted=extracted,
            )
        )

        return category, record_id, 1.0, "filed"

    # No prefix - classify with LLM
    try:
        classification = await classify_thought(text)
    except Exception as e:
        # LLM failed - log for review
        logger.error(f"Classification failed for text '{text[:50]}...': {e}")
        await insert_inbox_log(
            raw_text=text,
            destination=None,
            record_id=None,
            confidence=None,
            status="needs_review",
            telegram_message_id=telegram_message_id,
            telegram_chat_id=telegram_chat_id,
        )
        return None, None, None, "needs_review"

    category = classification.get("category")
    confidence = classification.get("confidence", 0.0)
    extracted = classification.get("extracted", {})
    tags = classification.get("tags", [])

    logger.info(f"Classification: category={category}, confidence={confidence}, threshold={Config.get_threshold(category) if category else Config.CONFIDENCE_THRESHOLD}")

    # Add tags to extracted data
    if tags:
        extracted["tags"] = tags

    # Get threshold for this category
    threshold = Config.get_threshold(category) if category else Config.CONFIDENCE_THRESHOLD

    # Check confidence threshold
    if confidence < threshold:
        await insert_inbox_log(
            raw_text=text,
            destination=category,
            record_id=None,
            confidence=confidence,
            status="needs_review",
            telegram_message_id=telegram_message_id,
            telegram_chat_id=telegram_chat_id,
        )
        return category, None, confidence, "needs_review"

    # Confidence OK - store the record
    table = CATEGORY_TABLE_MAP.get(category)
    if not table:
        # Unknown category from LLM
        await insert_inbox_log(
            raw_text=text,
            destination=None,
            record_id=None,
            confidence=confidence,
            status="needs_review",
            telegram_message_id=telegram_message_id,
            telegram_chat_id=telegram_chat_id,
        )
        return None, None, confidence, "needs_review"

    record_id = await insert_record(table, extracted)

    await insert_inbox_log(
        raw_text=text,
        destination=category,
        record_id=record_id,
        confidence=confidence,
        status="filed",
        telegram_message_id=telegram_message_id,
        telegram_chat_id=telegram_chat_id,
    )

    # Enhance with memory layer (run in background)
    asyncio.create_task(
        _enhance_with_memory(
            text=text,
            category=category,
            record_id=record_id,
            extracted=extracted,
        )
    )

    return category, record_id, confidence, "filed"


async def _enhance_with_memory(
    text: str,
    category: str,
    record_id: str,
    extracted: dict,
):
    """Background task to add memory layer processing."""
    try:
        from memory.graph import get_brain

        brain = get_brain()
        await brain.process_note(
            input_note=text,
            category=category,
            note_id=record_id,
            extracted_fields=extracted,
        )
        logger.info(f"Memory enhancement completed for note {record_id}")
    except Exception as e:
        logger.error(f"Memory enhancement failed for note {record_id}: {e}")
