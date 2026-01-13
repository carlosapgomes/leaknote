#!/usr/bin/env python3
"""Cleanup orphaned memories from Qdrant.

Scans all memories in Qdrant and deletes those whose associated notes
no longer exist in PostgreSQL.

Usage:
    python scripts/cleanup_orphaned_memories.py [--dry-run]
"""

import asyncio
import logging
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from bot.db import get_pool, close_pool, get_record
from memory.mem0_client import get_memory_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def check_note_exists(table: str, note_id: str) -> bool:
    """Check if a note still exists in the database."""
    try:
        record = await get_record(table, note_id)
        return record is not None
    except Exception:
        return False


async def find_orphaned_memories():
    """Scan all memories and identify orphans."""
    memory_client = get_memory_client()

    logger.info("Fetching all memories from Qdrant...")
    all_memories = await memory_client.get_all_memories()
    logger.info(f"Found {len(all_memories)} total memories")

    orphans = []

    for mem in all_memories:
        metadata = mem.get("metadata", {})
        note_id = metadata.get("note_id")
        category = metadata.get("category")

        if not note_id or not category:
            continue

        exists = await check_note_exists(category, note_id)

        if not exists:
            orphans.append({
                "memory_id": mem.get("id"),
                "memory": mem.get("memory"),
                "note_id": note_id,
                "category": category,
            })

    return orphans


async def delete_orphaned_memories(orphans):
    """Delete orphaned memories from Qdrant."""
    memory_client = get_memory_client()
    deleted_count = 0

    for orphan in orphans:
        try:
            memory_client.memory.delete(memory_id=orphan["memory_id"])
            logger.info(f"Deleted memory {orphan['memory_id']} (note: {orphan['category']}/{orphan['note_id']})")
            deleted_count += 1
        except Exception as e:
            logger.error(f"Failed to delete memory {orphan['memory_id']}: {e}")

    return deleted_count


async def main():
    parser = argparse.ArgumentParser(description="Cleanup orphaned memories from Qdrant")
    parser.add_argument("--dry-run", action="store_true", help="Scan and report but don't delete")
    args = parser.parse_args()

    logger.info("Starting orphaned memory cleanup...")

    if args.dry_run:
        logger.info("DRY RUN MODE - No deletions will be performed")

    try:
        orphans = await find_orphaned_memories()

        if not orphans:
            logger.info("✓ No orphaned memories found!")
            await close_pool()
            return

        # Group by category
        by_category = {}
        for orphan in orphans:
            category = orphan["category"]
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(orphan)

        logger.info("=" * 60)
        logger.info(f"Found {len(orphans)} orphaned memories:")
        logger.info("=" * 60)

        for category, items in sorted(by_category.items()):
            logger.info(f"\n{category.upper()}: {len(items)} orphans")
            for item in items[:5]:
                logger.info(f"  - Note {item['note_id']}: {item['memory'][:60]}...")
            if len(items) > 5:
                logger.info(f"  ... and {len(items) - 5} more")

        logger.info("=" * 60)

        if args.dry_run:
            logger.info("Dry run complete. No deletions performed.")
            await close_pool()
            return

        print("\nDelete these orphaned memories? (yes/no): ", end="")
        confirmation = input().strip().lower()

        if confirmation not in ["yes", "y"]:
            logger.info("Cancelled. No deletions performed.")
            await close_pool()
            return

        logger.info("Deleting orphaned memories...")
        deleted_count = await delete_orphaned_memories(orphans)

        logger.info("=" * 60)
        logger.info(f"Cleanup complete! Deleted {deleted_count}/{len(orphans)} orphaned memories")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
