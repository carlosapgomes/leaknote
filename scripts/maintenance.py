#!/usr/bin/env python3
"""
Weekly maintenance tasks.
Run via cron on Sunday night.

Usage:
    python scripts/maintenance.py
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from db import get_pool, close_pool, cleanup_old_pending

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def archive_completed_admin(days: int = 30) -> int:
    """Delete old completed admin tasks."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            f"""
            DELETE FROM admin
            WHERE status = 'done'
              AND updated_at < NOW() - INTERVAL '{days} days'
            """
        )
        count = int(result.split()[-1])
        logger.info(f"Archived {count} completed admin tasks")
        return count


async def vacuum_analyze():
    """Run VACUUM ANALYZE on all tables."""
    pool = await get_pool()

    tables = [
        "people",
        "projects",
        "ideas",
        "admin",
        "decisions",
        "howtos",
        "snippets",
        "inbox_log",
        "pending_clarifications",
    ]

    async with pool.acquire() as conn:
        for table in tables:
            await conn.execute(f"VACUUM ANALYZE {table}")
            logger.info(f"Vacuumed {table}")


async def generate_stats_report() -> str:
    """Generate a statistics report."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Total counts
        counts = {}
        for table in [
            "people",
            "projects",
            "ideas",
            "admin",
            "decisions",
            "howtos",
            "snippets",
        ]:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            counts[table] = count

        # This week's activity
        week_ago = datetime.now() - timedelta(days=7)
        week_stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'filed') as filed,
                COUNT(*) FILTER (WHERE status = 'needs_review') as reviewed,
                COUNT(*) FILTER (WHERE status = 'fixed') as fixed
            FROM inbox_log
            WHERE created_at >= $1
            """,
            week_ago,
        )

    report = f"""
📊 **Leaknote Statistics**

**Total Records:**
• People: {counts['people']}
• Projects: {counts['projects']}
• Ideas: {counts['ideas']}
• Admin: {counts['admin']}
• Decisions: {counts['decisions']}
• Howtos: {counts['howtos']}
• Snippets: {counts['snippets']}

**This Week:**
• Captured: {week_stats['total']}
• Auto-filed: {week_stats['filed']}
• Needed review: {week_stats['reviewed']}
• Fixed: {week_stats['fixed']}
"""

    return report


async def main():
    logger.info("Starting weekly maintenance...")

    try:
        # Cleanup old pending clarifications
        count = await cleanup_old_pending(days=7)
        logger.info(f"Cleaned up {count} old pending clarifications")

        # Archive completed admin
        await archive_completed_admin(days=30)

        # Vacuum all tables
        await vacuum_analyze()

        # Generate report
        report = await generate_stats_report()
        print(report)

        logger.info("Maintenance complete")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
