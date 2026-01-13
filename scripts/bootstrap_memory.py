#!/usr/bin/env python3
"""
Bootstrap Mem0 with existing notes from PostgreSQL.

Usage:
    python scripts/bootstrap_memory.py
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from bot.config import Config
from bot.db import get_pool, close_pool
from memory.mem0_client import get_memory_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def bootstrap_category(table: str, category: str) -> Dict[str, int]:
    """
    Bootstrap all records from a category.

    Args:
        table: Database table name
        category: Category name for memory storage

    Returns:
        Dict with success and failure counts
    """
    pool = await get_pool()
    memory_client = get_memory_client()

    async with pool.acquire() as conn:
        rows = await conn.fetch(f"SELECT * FROM {table}")

        logger.info(f"Bootstrapping {len(rows)} records from {table}...")

        success_count = 0
        failure_count = 0

        for i, row in enumerate(rows, 1):
            record = dict(row)
            record_id = str(record["id"])

            # Build content from record fields
            content_parts = []
            for key, value in record.items():
                if key not in ["id", "created_at", "updated_at"] and value:
                    content_parts.append(f"{key}: {value}")

            content = " | ".join(content_parts)

            # Build metadata
            metadata = {
                "bootstrapped": True,
                "bootstrapped_at": datetime.now().isoformat(),
            }

            # Add to memory
            try:
                await memory_client.add_note_memory(
                    note_id=record_id,
                    category=category,
                    content=content,
                    metadata=metadata,
                )
                logger.info(f"[{i}/{len(rows)}] Added {category}/{record_id}")
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to add {category}/{record_id}: {e}")
                failure_count += 1

        logger.info(f"Completed bootstrapping {table}: {success_count} success, {failure_count} failed")
        return {"success": success_count, "failure": failure_count}


async def main():
    logger.info("Starting memory bootstrap...")

    # Validate database configuration
    if not Config.DATABASE_URL:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    # Validate memory configuration
    from memory.config import MemoryConfig
    missing = MemoryConfig.validate()
    if missing:
        logger.error(f"Missing memory configuration: {', '.join(missing)}")
        logger.error("Please set the following environment variables:")
        for var in missing:
            logger.error(f"  - {var}")
        sys.exit(1)

    # Categories to bootstrap
    categories = [
        ("people", "people"),
        ("projects", "projects"),
        ("ideas", "ideas"),
        ("admin", "admin"),
        ("decisions", "decisions"),
        ("howtos", "howtos"),
        ("snippets", "snippets"),
    ]

    total_success = 0
    total_failure = 0

    for table, category in categories:
        try:
            results = await bootstrap_category(table, category)
            total_success += results["success"]
            total_failure += results["failure"]
        except Exception as e:
            logger.error(f"Error bootstrapping {table}: {e}")

    logger.info("=" * 50)
    logger.info(f"Memory bootstrap complete!")
    logger.info(f"Total: {total_success} success, {total_failure} failed")
    logger.info("=" * 50)

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
