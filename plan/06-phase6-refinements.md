# Phase 6: Refinements

## Goal

Polish the system for long-term reliability:
1. Confidence threshold tuning
2. Error handling improvements
3. Restart procedures
4. Maintenance tasks
5. Backup strategy

## 1. Confidence Threshold Tuning

### The Problem

The confidence threshold (default 0.6) determines when the system asks for clarification vs. auto-filing. Too high = constant interruptions. Too low = misclassifications.

### Tuning Process

1. **Collect data**: Run for 2 weeks, track clarification rate

```sql
-- Check how many items needed review vs. auto-filed
SELECT 
    DATE(created_at) as day,
    COUNT(*) FILTER (WHERE status = 'filed') as auto_filed,
    COUNT(*) FILTER (WHERE status = 'needs_review') as needed_review,
    COUNT(*) FILTER (WHERE status = 'fixed') as fixed,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE status = 'fixed') / 
        NULLIF(COUNT(*) FILTER (WHERE status = 'filed'), 0), 
        1
    ) as fix_rate_pct
FROM inbox_log
WHERE created_at > NOW() - INTERVAL '14 days'
GROUP BY DATE(created_at)
ORDER BY day;
```

2. **Analyze**: 
   - If fix_rate > 15%: threshold too low, increase to 0.7
   - If clarification rate > 30%: threshold too high, decrease to 0.5
   - Target: <10% fix rate, <20% clarification rate

3. **Adjust in `.env`**:

```bash
CONFIDENCE_THRESHOLD=0.65
```

### Per-Category Thresholds (Advanced)

If one category has more errors than others, use category-specific thresholds:

```python
# In config.py
CONFIDENCE_THRESHOLDS = {
    "people": 0.7,      # Higher - misclassifying people is annoying
    "projects": 0.6,
    "ideas": 0.5,       # Lower - ideas are low-stakes
    "admin": 0.65,
}
```

Update `router.py` to use per-category thresholds.

## 2. Error Handling

### LLM API Failures

Update `classifier.py` with retry logic:

```python
import asyncio
from typing import Optional

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


async def classify_thought_with_retry(text: str) -> Optional[dict]:
    """Classify with retry logic for transient failures."""
    
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            return await classify_thought(text)
        except httpx.TimeoutException as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                # Server error, retry
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            else:
                # Client error, don't retry
                raise
    
    # All retries failed
    raise last_error
```

### Database Connection Issues

Add connection pooling health checks to `db.py`:

```python
async def check_pool_health() -> bool:
    """Verify database connection is healthy."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False


async def reconnect_pool():
    """Force reconnection of database pool."""
    global _pool
    if _pool:
        await _pool.close()
    _pool = None
    await get_pool()
```

### Matrix Connection Recovery

Update `main.py` with automatic reconnection:

```python
async def run(self):
    await self.login()
    
    if Config.MATRIX_INBOX_ROOM.startswith("#"):
        self.inbox_room_id = await self.resolve_room_alias(Config.MATRIX_INBOX_ROOM)
    else:
        self.inbox_room_id = Config.MATRIX_INBOX_ROOM
    
    logger.info(f"Watching room: {self.inbox_room_id}")
    
    self.client.add_event_callback(self.on_message, RoomMessageText)
    
    # Reconnection loop
    while True:
        try:
            await self.client.sync_forever(timeout=30000)
        except Exception as e:
            logger.error(f"Sync error: {e}")
            logger.info("Reconnecting in 30 seconds...")
            await asyncio.sleep(30)
            try:
                await self.client.close()
            except:
                pass
            self.client = AsyncClient(Config.MATRIX_HOMESERVER, Config.MATRIX_USER_ID)
            await self.login()
```

## 3. Restart Procedures

### The "No Guilt" Restart

From the video: design for restart, not perfection.

Create `scripts/restart_brain.py`:

```python
#!/usr/bin/env python3
"""
Brain dump restart procedure.
Use when you've been away and want to catch up quickly.

Usage:
    python scripts/restart_brain.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from nio import AsyncClient, LoginResponse
from config import Config
from db import get_pool, close_pool

RESTART_MESSAGE = """🔄 **Second Brain Restart**

Welcome back! Here's a quick restart procedure:

**Don't catch up. Just restart.**

1. Do a 10-minute brain dump into this channel
2. One thought per message
3. Don't organize, just capture
4. The system will handle classification

**Quick prompts to jog your memory:**
• Any people you need to follow up with?
• Any projects that moved forward?
• Any decisions you made?
• Any tasks with deadlines?
• Any ideas worth capturing?

Take 10 minutes, dump everything, then move on.
Tomorrow's digest will have you back on track.

---
Type anything to start capturing.
"""


async def send_restart_prompt():
    """Send the restart prompt to the inbox channel."""
    import os
    
    client = AsyncClient(Config.MATRIX_HOMESERVER, Config.MATRIX_USER_ID)
    
    try:
        response = await client.login(Config.MATRIX_PASSWORD)
        if not isinstance(response, LoginResponse):
            print(f"Login failed: {response}")
            sys.exit(1)
        
        # Resolve room
        if Config.MATRIX_INBOX_ROOM.startswith("#"):
            response = await client.room_resolve_alias(Config.MATRIX_INBOX_ROOM)
            room_id = response.room_id
        else:
            room_id = Config.MATRIX_INBOX_ROOM
        
        # Send restart message
        await client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": RESTART_MESSAGE,
            },
        )
        
        print("Restart prompt sent!")
        
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(send_restart_prompt())
```

### Service Restart

Create systemd service file `/etc/systemd/user/second-brain.service`:

```ini
[Unit]
Description=Second Brain Matrix Bot
After=network.target postgresql.service

[Service]
Type=simple
WorkingDirectory=/path/to/second-brain
Environment=PATH=/path/to/second-brain/venv/bin
EnvironmentFile=/path/to/second-brain/.env
ExecStart=/path/to/second-brain/venv/bin/python bot/main.py
Restart=always
RestartSec=30

[Install]
WantedBy=default.target
```

Commands:

```bash
# Enable and start
systemctl --user enable second-brain
systemctl --user start second-brain

# Check status
systemctl --user status second-brain

# View logs
journalctl --user -u second-brain -f

# Restart after config change
systemctl --user restart second-brain
```

## 4. Maintenance Tasks

### Weekly Maintenance Script

Create `scripts/weekly_maintenance.py`:

```python
#!/usr/bin/env python3
"""
Weekly maintenance tasks.
Run via cron on Sunday night.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from db import get_pool, close_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def cleanup_old_pending(days: int = 7) -> int:
    """Delete pending clarifications older than N days."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM pending_clarifications 
            WHERE created_at < NOW() - INTERVAL '%s days'
            """,
            days
        )
        count = int(result.split()[-1])
        logger.info(f"Cleaned up {count} old pending clarifications")
        return count


async def archive_completed_admin(days: int = 30) -> int:
    """Mark old completed admin tasks as archived (optional)."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # If you want to delete instead of archive:
        result = await conn.execute(
            """
            DELETE FROM admin
            WHERE status = 'done'
              AND updated_at < NOW() - INTERVAL '%s days'
            """,
            days
        )
        count = int(result.split()[-1])
        logger.info(f"Archived {count} completed admin tasks")
        return count


async def vacuum_analyze():
    """Run VACUUM ANALYZE on all tables."""
    pool = await get_pool()
    
    tables = [
        "people", "projects", "ideas", "admin",
        "decisions", "howtos", "snippets",
        "inbox_log", "pending_clarifications"
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
        for table in ["people", "projects", "ideas", "admin", "decisions", "howtos", "snippets"]:
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
            week_ago
        )
    
    report = f"""
📊 **Second Brain Statistics**

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
        await cleanup_old_pending()
        await archive_completed_admin()
        await vacuum_analyze()
        
        report = await generate_stats_report()
        print(report)
        
        logger.info("Maintenance complete")
        
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
```

Cron entry:

```
# Weekly maintenance Sunday at 11:00 PM
0 23 * * 0 /path/to/second-brain/scripts/run_maintenance.sh
```

## 5. Backup Strategy

### Database Backup Script

Create `scripts/backup.sh`:

```bash
#!/bin/bash
set -e

BACKUP_DIR="/path/to/backups/second-brain"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/secondbrain_$DATE.sql.gz"

# Create backup directory if needed
mkdir -p "$BACKUP_DIR"

# Dump and compress
pg_dump -U secondbrain secondbrain | gzip > "$BACKUP_FILE"

# Keep only last 30 days of backups
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete

echo "Backup created: $BACKUP_FILE"
```

Cron entry:

```
# Daily backup at 2:00 AM
0 2 * * * /path/to/second-brain/scripts/backup.sh >> /var/log/second-brain/backup.log 2>&1
```

### Restore Procedure

```bash
# Restore from backup
gunzip -c /path/to/backups/secondbrain_20260110.sql.gz | psql -U secondbrain secondbrain
```

## 6. Monitoring

### Health Check Endpoint

Create `scripts/health_check.py`:

```python
#!/usr/bin/env python3
"""
Health check script for monitoring.
Returns exit code 0 if healthy, 1 if unhealthy.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from db import check_pool_health


async def main():
    # Check database
    if not await check_pool_health():
        print("UNHEALTHY: Database connection failed")
        sys.exit(1)
    
    # Could add more checks here:
    # - Matrix connection
    # - LLM API availability
    # - Disk space
    
    print("HEALTHY")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
```

### Simple Monitoring with Cron

```bash
# Health check every 5 minutes, alert if unhealthy
*/5 * * * * /path/to/second-brain/scripts/health_check.sh || echo "Second brain unhealthy" | mail -s "Alert" you@example.com
```

## Phase 6 Checklist

- [ ] Confidence threshold tuned based on data
- [ ] Retry logic for LLM API calls
- [ ] Database reconnection handling
- [ ] Matrix reconnection handling
- [ ] Systemd service configured
- [ ] Restart procedure documented
- [ ] Weekly maintenance script
- [ ] Backup script with retention
- [ ] Health check script
- [ ] All cron jobs installed

## Final Crontab

```bash
# Second brain cron jobs

# Daily digest at 6:00 AM
0 6 * * * /path/to/second-brain/scripts/run_daily_digest.sh

# Weekly review Sunday at 4:00 PM
0 16 * * 0 /path/to/second-brain/scripts/run_weekly_review.sh

# Weekly maintenance Sunday at 11:00 PM
0 23 * * 0 /path/to/second-brain/scripts/run_maintenance.sh

# Daily backup at 2:00 AM
0 2 * * * /path/to/second-brain/scripts/backup.sh >> /var/log/second-brain/backup.log 2>&1

# Health check every 5 minutes
*/5 * * * * /path/to/second-brain/scripts/health_check.sh || echo "Second brain unhealthy" | mail -s "Alert" you@example.com
```

## Operational Runbook

### Bot not responding

1. Check service: `systemctl --user status second-brain`
2. Check logs: `journalctl --user -u second-brain -n 50`
3. Restart: `systemctl --user restart second-brain`

### Digest not arriving

1. Check cron: `grep second-brain /var/log/syslog`
2. Check digest log: `tail /var/log/second-brain/daily_digest.log`
3. Manual test: `python scripts/daily_digest.py`

### Classification seems wrong

1. Check confidence threshold in `.env`
2. Review recent fixes: `SELECT * FROM inbox_log WHERE status = 'fixed' ORDER BY created_at DESC LIMIT 20;`
3. Adjust threshold if fix rate > 15%

### Database issues

1. Check connection: `psql -U secondbrain -d secondbrain -c "SELECT 1"`
2. Check disk space: `df -h`
3. Run vacuum: `psql -U secondbrain -d secondbrain -c "VACUUM ANALYZE"`

### Need to migrate/export data

```bash
# Full export
pg_dump -U secondbrain secondbrain > export.sql

# Export to CSV for analysis
psql -U secondbrain -d secondbrain -c "\copy projects TO 'projects.csv' CSV HEADER"
```
