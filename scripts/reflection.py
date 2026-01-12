#!/usr/bin/env python3
"""
Weekly semantic reflection cron job.
Run at Sunday 17:00 (after weekly review).

Analyzes recent notes using the memory layer (Mem0 + LangGraph)
for pattern detection and insight generation.

Usage:
    python scripts/reflection.py
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from telegram import Bot
from config import Config
from db import get_pool, close_pool, insert_record
from memory.graph import get_brain
from memory.config import MemoryConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def get_weekly_notes():
    """Get all notes from the past week for semantic analysis."""
    pool = await get_pool()
    cutoff = datetime.now() - timedelta(days=7)

    notes = []

    async with pool.acquire() as conn:
        # Query main categories that people actively file to
        for table in ["people", "projects", "ideas", "admin"]:
            rows = await conn.fetch(
                f"""
                SELECT * FROM {table}
                WHERE created_at >= $1
                ORDER BY created_at DESC
                """,
                cutoff,
            )
            for row in rows:
                r = dict(row)
                r["category"] = table
                # Build a content representation for LLM
                content_parts = []
                for key, value in r.items():
                    if key not in ["id", "created_at", "updated_at", "category"] and value:
                        content_parts.append(f"{key}: {value}")
                r["content"] = " | ".join(content_parts)
                notes.append(r)

    logger.info(f"Found {len(notes)} notes from the past week")
    return notes


async def generate_reflection(notes):
    """Generate weekly semantic reflection using LangGraph brain."""
    brain = get_brain()

    logger.info("Generating semantic insights using memory layer...")
    insights = await brain.extract_insights(notes)

    return insights


async def save_reflection_to_db(insights: dict) -> str:
    """Save the reflection as an idea in the database."""
    title = f"Weekly Reflection - {datetime.now().strftime('%Y-%m-%d')}"

    # Format insights as elaboration
    elaboration_parts = []
    for section, items in insights.items():
        if items:
            # Handle both list and non-list items
            if isinstance(items, list):
                items_str = "\n".join(f"- {i}" for i in items if i)
            else:
                items_str = str(items)
            elaboration_parts.append(f"**{section.title()}**\n{items_str}")

    elaboration = "\n\n".join(elaboration_parts)

    # Create a one-liner summary
    theme_count = len(insights.get("themes", []))
    pattern_count = len(insights.get("patterns", []))
    connection_count = len(insights.get("connections", []))
    one_liner = (
        f"Semantic reflection on the past week's notes "
        f"({theme_count} themes, {pattern_count} patterns, {connection_count} connections)"
    )

    record_id = await insert_record(
        "ideas",
        {
            "title": title,
            "one_liner": one_liner,
            "elaboration": elaboration,
        },
    )

    return record_id


async def send_reflection_to_telegram(bot: Bot, chat_id: int, insights: dict, note_id: str):
    """Send the reflection via Telegram."""
    lines = [
        "🧠 **Weekly Semantic Reflection**",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "_Using the memory layer to find patterns and insights..._",
        "",
    ]

    # Display insights by section
    for section, items in insights.items():
        if items:
            lines.append(f"**{section.title()}**")
            # Handle both list and non-list items
            if isinstance(items, list):
                for item in items[:5]:  # Limit to 5 per section
                    if item:
                        lines.append(f"• {item}")
            else:
                lines.append(f"• {items}")
            lines.append("")

    lines.append(f"💾 Saved as idea: [[{note_id}]]")

    message = "\n".join(lines)

    # Handle long messages - Telegram limit is 4096
    if len(message) > 4000:
        message = message[:3970] + "\n... (truncated)"

    await bot.send_message(chat_id=chat_id, text=message)


async def main():
    logger.info("Starting weekly semantic reflection...")

    if not Config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    if not Config.TELEGRAM_OWNER_ID:
        logger.error("TELEGRAM_OWNER_ID not set")
        sys.exit(1)

    # Validate memory config
    missing = MemoryConfig.validate()
    if missing:
        logger.error(f"Missing memory configuration: {', '.join(missing)}")
        logger.error("Semantic reflection requires memory layer to be configured")
        sys.exit(1)

    bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)

    try:
        # Get weekly notes
        notes = await get_weekly_notes()

        if not notes:
            logger.info("No notes from the past week to reflect on")
            return

        # Generate insights using memory layer
        logger.info("Generating semantic insights...")
        insights = await generate_reflection(notes)
        logger.info(f"Insights generated: {list(insights.keys())}")

        # Check if we have meaningful insights
        has_content = any(
            bool(insights.get(k))
            for k in ["themes", "connections", "patterns", "entities", "actions"]
        )

        if not has_content:
            logger.info("No meaningful insights found this week")
            return

        # Save to database
        note_id = await save_reflection_to_db(insights)
        logger.info(f"Reflection saved as idea {note_id}")

        # Send via Telegram
        await send_reflection_to_telegram(bot, Config.TELEGRAM_OWNER_ID, insights, note_id)
        logger.info("Weekly semantic reflection sent successfully")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
