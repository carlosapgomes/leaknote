# Phase 4: Weekly Review

## Goal

Every Sunday at 16:00, the bot sends a DM with:
1. What happened this week (summary of activity)
2. Biggest open loops (stuck/waiting projects)
3. Three suggested actions for next week
4. One recurring theme the system noticed
5. Ideas captured this week
6. Decisions made this week

Constraint: Under 250 words.

## Step 1: Weekly Review Generator

Create `bot/weekly_review.py`:

```python
import httpx
from typing import Dict, Any, List
from datetime import datetime, timedelta
from config import Config
from queries import (
    get_active_projects,
    get_waiting_projects,
    get_blocked_projects,
    get_admin_due_soon,
    get_overdue_admin,
    get_people_with_followups,
    get_recent_decisions,
    get_recent_ideas,
    get_inbox_stats,
)


WEEKLY_REVIEW_PROMPT = """You are generating a weekly review for a personal knowledge management system.

Your job is to create a thoughtful but CONCISE week-in-review.

STRICT CONSTRAINTS:
- Maximum 250 words total
- Be analytical, not descriptive
- Identify patterns and themes
- Suggest specific actions

FORMAT:
## This Week
[2-3 sentence summary of activity and progress]

## Open Loops
[Top 2-3 stuck or waiting items that need attention]

## Next Week
[3 specific, actionable suggestions]

## Pattern Noticed
[One theme or pattern across this week's entries]

## Ideas Captured
[List of ideas from this week, if any]

## Decisions Made
[List of decisions from this week, if any]

If a section has nothing meaningful, omit it.
Be direct. No pleasantries.

DATA:
"""


async def generate_weekly_review() -> str:
    """Generate the weekly review content."""
    
    # Gather data
    active_projects = await get_active_projects(limit=20)
    waiting_projects = await get_waiting_projects()
    blocked_projects = await get_blocked_projects()
    overdue = await get_overdue_admin()
    due_soon = await get_admin_due_soon(days=7)
    people = await get_people_with_followups()
    decisions = await get_recent_decisions(days=7, limit=10)
    ideas = await get_recent_ideas(days=7, limit=10)
    stats = await get_inbox_stats(days=7)
    
    # Format data for LLM
    data_sections = []
    
    # Stats summary
    data_sections.append(
        f"INBOX STATS (last 7 days):\n"
        f"- Total captured: {stats['total']}\n"
        f"- Filed: {stats['filed']}\n"
        f"- Needed review: {stats['needs_review']}\n"
        f"- Fixed: {stats['fixed']}"
    )
    
    if active_projects:
        projects_text = "\n".join([
            f"- {p['name']}: {p['next_action'] or 'no next action'} (updated {p['updated_at'].strftime('%a')})"
            for p in active_projects[:10]
        ])
        data_sections.append(f"ACTIVE PROJECTS ({len(active_projects)} total):\n{projects_text}")
    
    if waiting_projects:
        waiting_text = "\n".join([
            f"- {p['name']}: waiting since {p['updated_at'].strftime('%b %d')}"
            for p in waiting_projects
        ])
        data_sections.append(f"WAITING ({len(waiting_projects)}):\n{waiting_text}")
    
    if blocked_projects:
        blocked_text = "\n".join([
            f"- {p['name']}: {p['notes'] or 'no notes'}"
            for p in blocked_projects
        ])
        data_sections.append(f"BLOCKED ({len(blocked_projects)}):\n{blocked_text}")
    
    if overdue:
        overdue_text = "\n".join([
            f"- {a['name']} (was due {a['due_date']})"
            for a in overdue
        ])
        data_sections.append(f"OVERDUE:\n{overdue_text}")
    
    if due_soon:
        due_text = "\n".join([
            f"- {a['name']} (due {a['due_date']})"
            for a in due_soon[:5]
        ])
        data_sections.append(f"DUE THIS WEEK:\n{due_text}")
    
    if people:
        people_text = "\n".join([
            f"- {p['name']}: {p['follow_ups']} (last: {p['last_touched'].strftime('%b %d') if p['last_touched'] else 'never'})"
            for p in people[:5]
        ])
        data_sections.append(f"PEOPLE TO FOLLOW UP:\n{people_text}")
    
    if ideas:
        ideas_text = "\n".join([
            f"- {i['title']}: {i['one_liner'] or ''}"
            for i in ideas
        ])
        data_sections.append(f"IDEAS THIS WEEK ({len(ideas)}):\n{ideas_text}")
    
    if decisions:
        decisions_text = "\n".join([
            f"- {d['title']}: {d['decision']}"
            for d in decisions
        ])
        data_sections.append(f"DECISIONS THIS WEEK ({len(decisions)}):\n{decisions_text}")
    
    if not any([active_projects, waiting_projects, blocked_projects, ideas, decisions]):
        return "📭 Quiet week. No significant activity captured."
    
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
                "max_tokens": 800,
                "messages": [
                    {"role": "user", "content": WEEKLY_REVIEW_PROMPT + data_text}
                ],
            },
        )
        response.raise_for_status()
        
        result = response.json()
        return result["content"][0]["text"]


def format_review_date_range() -> str:
    """Format the date range for the review header."""
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    return f"{week_ago.strftime('%b %d')} - {today.strftime('%b %d, %Y')}"
```

## Step 2: Weekly Review Script

Create `scripts/weekly_review.py`:

```python
#!/usr/bin/env python3
"""
Weekly review cron job.
Run at 16:00 on Sundays.

Usage:
    python scripts/weekly_review.py

Cron entry:
    0 16 * * 0 cd /path/to/second-brain && /path/to/venv/bin/python scripts/weekly_review.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from nio import AsyncClient, LoginResponse
from config import Config
from weekly_review import generate_weekly_review, format_review_date_range
from db import close_pool

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_dm_room_id(client: AsyncClient, user_id: str) -> str:
    """Get or create a DM room with the specified user."""
    
    await client.sync(timeout=10000)
    
    for room_id, room in client.rooms.items():
        if room.is_direct and len(room.users) == 2:
            if user_id in [u.user_id for u in room.users.values()]:
                return room_id
    
    response = await client.room_create(
        is_direct=True,
        invite=[user_id],
    )
    return response.room_id


async def send_review(client: AsyncClient, room_id: str, content: str):
    """Send the weekly review to a room."""
    
    date_range = format_review_date_range()
    full_message = f"📊 **Weekly Review - {date_range}**\n\n{content}"
    
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
    logger.info("Starting weekly review generation...")
    
    import os
    target_user = os.getenv("DIGEST_TARGET_USER")
    if not target_user:
        logger.error("DIGEST_TARGET_USER not set")
        sys.exit(1)
    
    client = AsyncClient(Config.MATRIX_HOMESERVER, Config.MATRIX_USER_ID)
    
    try:
        response = await client.login(Config.MATRIX_PASSWORD)
        if not isinstance(response, LoginResponse):
            logger.error(f"Login failed: {response}")
            sys.exit(1)
        
        logger.info("Logged in to Matrix")
        
        logger.info("Generating weekly review...")
        review_content = await generate_weekly_review()
        logger.info(f"Review generated ({len(review_content)} chars)")
        
        room_id = await get_dm_room_id(client, target_user)
        logger.info(f"DM room: {room_id}")
        
        await send_review(client, room_id, review_content)
        logger.info("Weekly review sent successfully")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        await client.close()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
```

## Step 3: Wrapper Script

Create `scripts/run_weekly_review.sh`:

```bash
#!/bin/bash
set -e

cd /path/to/second-brain
source venv/bin/activate
source .env

export DIGEST_TARGET_USER

python scripts/weekly_review.py >> /var/log/second-brain/weekly_review.log 2>&1
```

Make executable:

```bash
chmod +x scripts/run_weekly_review.sh
```

## Step 4: Cron Setup

```bash
crontab -e
```

Add:

```
# Second brain weekly review at 4:00 PM on Sundays
0 16 * * 0 /path/to/second-brain/scripts/run_weekly_review.sh
```

Full crontab should now look like:

```
# Second brain daily digest at 6:00 AM
0 6 * * * /path/to/second-brain/scripts/run_daily_digest.sh

# Second brain weekly review at 4:00 PM on Sundays
0 16 * * 0 /path/to/second-brain/scripts/run_weekly_review.sh
```

## Step 5: Test

### 5.1 Manual test

```bash
cd /path/to/second-brain
source venv/bin/activate
export DIGEST_TARGET_USER=@carlos:yourdomain.com
python scripts/weekly_review.py
```

### 5.2 Example Output

```
📊 Weekly Review - Jan 03 - Jan 10, 2026

## This Week
Captured 23 items. Focus was on papercage sandbox development 
and Dito EHR integration planning. Good progress on infrastructure,
less on documentation.

## Open Loops
- Papercage nftables rules: blocked on network topology decision
- EHR integration spec: waiting on Dr. Silva's response since Jan 5

## Next Week
- Unblock papercage: make network topology decision
- Follow up with Dr. Silva (it's been 5 days)
- Process 3 ideas in backlog - some have been sitting since Dec

## Pattern Noticed
Security and isolation concerns appear across multiple projects 
(papercage, agent sandbox, Dito). Consider dedicating a focused
session to consolidate security architecture.

## Ideas Captured
- Matrix reactions for triage
- Multi-agent cost routing
- Embedding-based howto search

## Decisions Made
- Using Postgres for second brain (queryability)
- Dedicated bot user for Matrix
```

## Phase 4 Checklist

- [ ] `weekly_review.py` generator created
- [ ] `scripts/weekly_review.py` cron script created
- [ ] Wrapper script with proper paths
- [ ] Cron job installed for Sunday 16:00
- [ ] Manual test successful
- [ ] Review arrives in Matrix DM
- [ ] All sections render correctly

## Comparison: Daily vs Weekly

| Aspect | Daily Digest | Weekly Review |
|--------|--------------|---------------|
| **Focus** | Actions for today | Patterns and planning |
| **Length** | <150 words | <250 words |
| **Timing** | 06:00 daily | 16:00 Sunday |
| **Sections** | Focus, Due, Follow-up | Summary, Loops, Next week, Patterns |
| **LLM model** | Claude | Claude |
| **Tone** | Tactical | Reflective |

## Customization Options

### Change review day/time

Edit crontab:
```
# Saturday at 10:00 AM instead
0 10 * * 6 /path/to/second-brain/scripts/run_weekly_review.sh
```

### Add monthly review

Create `scripts/monthly_review.py` with similar structure but:
- Query last 30 days
- Include project completion stats
- Track decision patterns over time
- Longer word limit (400 words)

Cron for first Sunday of month:
```
0 16 1-7 * 0 /path/to/second-brain/scripts/run_monthly_review.sh
```

### Adjust sections

Edit `WEEKLY_REVIEW_PROMPT` in `weekly_review.py` to:
- Add/remove sections
- Change analysis depth
- Modify tone
