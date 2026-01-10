# Phase 3: Daily Digest

## Goal

Every morning at 06:00, the bot sends a DM with:
1. Top 3 actions for the day (from projects + admin)
2. People with upcoming follow-ups
3. One thing you might be stuck on
4. One recent decision (for awareness)

Constraint: Under 150 words to fit on a phone screen.

## Architecture

```
┌─────────────────────┐
│  Cron (06:00)       │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  daily_digest.py    │
│  - Query Postgres   │
│  - Send to Claude   │
│  - Format digest    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Matrix DM to user  │
└─────────────────────┘
```

## Step 1: Database Queries

Create `bot/queries.py`:

```python
from typing import List, Dict, Any
from datetime import datetime, timedelta
from db import get_pool


async def get_active_projects(limit: int = 10) -> List[Dict[str, Any]]:
    """Get active projects with next actions."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, status, next_action, notes, tags, updated_at
            FROM projects
            WHERE status = 'active'
            ORDER BY updated_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(row) for row in rows]


async def get_waiting_projects() -> List[Dict[str, Any]]:
    """Get projects in waiting status."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, status, next_action, notes, updated_at
            FROM projects
            WHERE status = 'waiting'
            ORDER BY updated_at DESC
            """
        )
        return [dict(row) for row in rows]


async def get_blocked_projects() -> List[Dict[str, Any]]:
    """Get blocked projects."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, status, next_action, notes, updated_at
            FROM projects
            WHERE status = 'blocked'
            ORDER BY updated_at DESC
            """
        )
        return [dict(row) for row in rows]


async def get_admin_due_soon(days: int = 7) -> List[Dict[str, Any]]:
    """Get admin tasks due within N days."""
    pool = await get_pool()
    cutoff = datetime.now().date() + timedelta(days=days)
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, due_date, status, notes
            FROM admin
            WHERE status = 'pending'
              AND due_date IS NOT NULL
              AND due_date <= $1
            ORDER BY due_date ASC
            """,
            cutoff
        )
        return [dict(row) for row in rows]


async def get_overdue_admin() -> List[Dict[str, Any]]:
    """Get overdue admin tasks."""
    pool = await get_pool()
    today = datetime.now().date()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, due_date, status, notes
            FROM admin
            WHERE status = 'pending'
              AND due_date IS NOT NULL
              AND due_date < $1
            ORDER BY due_date ASC
            """,
            today
        )
        return [dict(row) for row in rows]


async def get_people_with_followups() -> List[Dict[str, Any]]:
    """Get people who have follow-up notes."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, context, follow_ups, last_touched
            FROM people
            WHERE follow_ups IS NOT NULL
              AND follow_ups != ''
            ORDER BY last_touched DESC
            """
        )
        return [dict(row) for row in rows]


async def get_recent_decisions(days: int = 7, limit: int = 5) -> List[Dict[str, Any]]:
    """Get decisions made in the last N days."""
    pool = await get_pool()
    cutoff = datetime.now() - timedelta(days=days)
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, decision, rationale, created_at
            FROM decisions
            WHERE created_at >= $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            cutoff,
            limit
        )
        return [dict(row) for row in rows]


async def get_recent_ideas(days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
    """Get ideas captured in the last N days."""
    pool = await get_pool()
    cutoff = datetime.now() - timedelta(days=days)
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, one_liner, created_at
            FROM ideas
            WHERE created_at >= $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            cutoff,
            limit
        )
        return [dict(row) for row in rows]


async def get_inbox_stats(days: int = 7) -> Dict[str, int]:
    """Get inbox statistics for the last N days."""
    pool = await get_pool()
    cutoff = datetime.now() - timedelta(days=days)
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'filed') as filed,
                COUNT(*) FILTER (WHERE status = 'needs_review') as needs_review,
                COUNT(*) FILTER (WHERE status = 'fixed') as fixed
            FROM inbox_log
            WHERE created_at >= $1
            """,
            cutoff
        )
        return dict(row)
```

## Step 2: Digest Generator

Create `bot/digest.py`:

```python
import httpx
from typing import Dict, Any, List
from datetime import datetime
from config import Config
from queries import (
    get_active_projects,
    get_blocked_projects,
    get_admin_due_soon,
    get_overdue_admin,
    get_people_with_followups,
    get_recent_decisions,
)

DAILY_DIGEST_PROMPT = """You are generating a daily digest for a personal knowledge management system.

Your job is to create a SHORT, ACTIONABLE morning briefing.

STRICT CONSTRAINTS:
- Maximum 150 words total
- No fluff, no greetings, no encouragement
- Focus on ACTIONS, not descriptions
- Use bullet points sparingly

FORMAT:
## Today's Focus
[Top 3 most important actions - be specific]

## Due Soon
[Any deadlines in next 3 days]

## Follow Up
[Any people to reach out to]

## Watch Out
[One stuck/blocked item if any]

## Recent Decision
[One recent decision as a reminder, if any]

If a section has nothing, omit it entirely.

DATA:
"""


async def generate_daily_digest() -> str:
    """Generate the daily digest content."""
    
    # Gather data
    active_projects = await get_active_projects(limit=10)
    blocked_projects = await get_blocked_projects()
    overdue = await get_overdue_admin()
    due_soon = await get_admin_due_soon(days=3)
    people = await get_people_with_followups()
    decisions = await get_recent_decisions(days=7, limit=1)
    
    # Format data for LLM
    data_sections = []
    
    if active_projects:
        projects_text = "\n".join([
            f"- {p['name']}: {p['next_action'] or 'no next action'}"
            for p in active_projects[:5]
        ])
        data_sections.append(f"ACTIVE PROJECTS:\n{projects_text}")
    
    if blocked_projects:
        blocked_text = "\n".join([
            f"- {p['name']}: {p['notes'] or 'no notes'}"
            for p in blocked_projects[:3]
        ])
        data_sections.append(f"BLOCKED:\n{blocked_text}")
    
    if overdue:
        overdue_text = "\n".join([
            f"- {a['name']} (due {a['due_date']})"
            for a in overdue[:3]
        ])
        data_sections.append(f"OVERDUE:\n{overdue_text}")
    
    if due_soon:
        due_text = "\n".join([
            f"- {a['name']} (due {a['due_date']})"
            for a in due_soon[:5]
        ])
        data_sections.append(f"DUE SOON:\n{due_text}")
    
    if people:
        people_text = "\n".join([
            f"- {p['name']}: {p['follow_ups']}"
            for p in people[:3]
        ])
        data_sections.append(f"PEOPLE TO FOLLOW UP:\n{people_text}")
    
    if decisions:
        d = decisions[0]
        data_sections.append(f"RECENT DECISION:\n- {d['title']}: {d['decision']}")
    
    if not data_sections:
        return "📭 Nothing urgent today. Inbox is clear."
    
    data_text = "\n\n".join(data_sections)
    
    # Call Claude for summarization
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            Config.CLAUDE_API_URL,
            headers={
                "x-api-key": Config.CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": Config.CLAUDE_MODEL,
                "max_tokens": 500,
                "messages": [
                    {"role": "user", "content": DAILY_DIGEST_PROMPT + data_text}
                ],
            },
        )
        response.raise_for_status()
        
        result = response.json()
        return result["content"][0]["text"]


def format_digest_date() -> str:
    """Format today's date for the digest header."""
    return datetime.now().strftime("%A, %B %d")
```

## Step 3: Daily Digest Script

Create `scripts/daily_digest.py`:

```python
#!/usr/bin/env python3
"""
Daily digest cron job.
Run at 06:00 daily.

Usage:
    python scripts/daily_digest.py

Cron entry:
    0 6 * * * cd /path/to/second-brain && /path/to/venv/bin/python scripts/daily_digest.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from nio import AsyncClient, LoginResponse
from config import Config
from digest import generate_daily_digest, format_digest_date
from db import close_pool

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_dm_room_id(client: AsyncClient, user_id: str) -> str:
    """Get or create a DM room with the specified user."""
    
    # First, sync to get room list
    await client.sync(timeout=10000)
    
    # Look for existing DM
    for room_id, room in client.rooms.items():
        if room.is_direct and len(room.users) == 2:
            if user_id in [u.user_id for u in room.users.values()]:
                return room_id
    
    # Create new DM room
    response = await client.room_create(
        is_direct=True,
        invite=[user_id],
    )
    return response.room_id


async def send_digest(client: AsyncClient, room_id: str, content: str):
    """Send the digest to a room."""
    
    date_header = format_digest_date()
    full_message = f"🌅 **Daily Digest - {date_header}**\n\n{content}"
    
    await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content={
            "msgtype": "m.text",
            "body": full_message,
            "format": "org.matrix.custom.html",
            "formatted_body": full_message.replace("\n", "<br>"),
        },
    )


async def main():
    logger.info("Starting daily digest generation...")
    
    # Get target user from environment or config
    import os
    target_user = os.getenv("DIGEST_TARGET_USER")
    if not target_user:
        logger.error("DIGEST_TARGET_USER not set")
        sys.exit(1)
    
    # Initialize Matrix client
    client = AsyncClient(Config.MATRIX_HOMESERVER, Config.MATRIX_USER_ID)
    
    try:
        # Login
        response = await client.login(Config.MATRIX_PASSWORD)
        if not isinstance(response, LoginResponse):
            logger.error(f"Login failed: {response}")
            sys.exit(1)
        
        logger.info("Logged in to Matrix")
        
        # Generate digest
        logger.info("Generating digest...")
        digest_content = await generate_daily_digest()
        logger.info(f"Digest generated ({len(digest_content)} chars)")
        
        # Get DM room
        room_id = await get_dm_room_id(client, target_user)
        logger.info(f"DM room: {room_id}")
        
        # Send digest
        await send_digest(client, room_id, digest_content)
        logger.info("Digest sent successfully")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        await client.close()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
```

## Step 4: Environment Configuration

Add to `.env`:

```bash
# Digest target (your Matrix user ID)
DIGEST_TARGET_USER=@carlos:yourdomain.com
```

## Step 5: Cron Setup

### 5.1 Create wrapper script

Create `scripts/run_daily_digest.sh`:

```bash
#!/bin/bash
set -e

cd /path/to/second-brain
source venv/bin/activate
source .env

export DIGEST_TARGET_USER

python scripts/daily_digest.py >> /var/log/second-brain/daily_digest.log 2>&1
```

Make executable:

```bash
chmod +x scripts/run_daily_digest.sh
```

### 5.2 Create log directory

```bash
sudo mkdir -p /var/log/second-brain
sudo chown $USER:$USER /var/log/second-brain
```

### 5.3 Add cron entry

```bash
crontab -e
```

Add:

```
# Second brain daily digest at 6:00 AM
0 6 * * * /path/to/second-brain/scripts/run_daily_digest.sh
```

## Step 6: Test

### 6.1 Manual test

```bash
cd /path/to/second-brain
source venv/bin/activate
export DIGEST_TARGET_USER=@carlos:yourdomain.com
python scripts/daily_digest.py
```

### 6.2 Verify in Matrix

Check your DMs for a message like:

```
🌅 Daily Digest - Friday, January 10

## Today's Focus
- Review papercage nftables rules
- Email Dr. Silva about EHR timeline
- Finish domain renewal for carloszan.com

## Due Soon
- Domain renewal (Jan 15)

## Follow Up
- Dr. Silva: confirm integration timeline

## Recent Decision
- Using Postgres for second brain (queryability + atomicity)
```

## Phase 3 Checklist

- [ ] `queries.py` with all data retrieval functions
- [ ] `digest.py` with Claude summarization
- [ ] `daily_digest.py` cron script
- [ ] `DIGEST_TARGET_USER` configured
- [ ] Cron job installed for 06:00
- [ ] Log file location created
- [ ] Manual test successful
- [ ] Digest arrives in Matrix DM

## Customization Options

### Change digest time

Edit crontab:
```
# 7:30 AM instead of 6:00 AM
30 7 * * * /path/to/second-brain/scripts/run_daily_digest.sh
```

### Change digest content

Edit the `DAILY_DIGEST_PROMPT` in `digest.py` to adjust:
- Sections included
- Word limit
- Tone/style

### Skip weekends

```
# Only weekdays
0 6 * * 1-5 /path/to/second-brain/scripts/run_daily_digest.sh
```
