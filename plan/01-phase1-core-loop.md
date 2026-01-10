# Phase 1: Core Loop

## Goal

Build the minimal working pipeline: capture a message in Matrix → classify with LLM → store in PostgreSQL.

No confirmations, no digests, no retrieval yet. Just the core data flow.

## Prerequisites

- PostgreSQL installed and running
- Python 3.11+
- A Matrix homeserver (Dendrite or Synapse)
- A dedicated bot user on the Matrix server
- API access to GLM-4 (via Z.AI or direct) and Claude

## Step 1: Database Schema

### 1.1 Create the database

```bash
sudo -u postgres createuser secondbrain
sudo -u postgres createdb secondbrain -O secondbrain
sudo -u postgres psql -c "ALTER USER secondbrain WITH PASSWORD 'your-secure-password';"
```

### 1.2 Schema SQL

Create file: `schema.sql`

```sql
-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enum for project status
CREATE TYPE project_status AS ENUM ('active', 'waiting', 'blocked', 'someday', 'done');

-- Enum for admin status
CREATE TYPE admin_status AS ENUM ('pending', 'done');

-- Dynamic categories
CREATE TABLE people (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    context TEXT,
    follow_ups TEXT,
    last_touched TIMESTAMP DEFAULT NOW(),
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    status project_status DEFAULT 'active',
    next_action TEXT,
    notes TEXT,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ideas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    one_liner TEXT,
    elaboration TEXT,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE admin (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    due_date DATE,
    status admin_status DEFAULT 'pending',
    notes TEXT,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Reference categories
CREATE TABLE decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    decision TEXT NOT NULL,
    rationale TEXT,
    context TEXT,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE howtos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE snippets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Audit log
CREATE TABLE inbox_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    raw_text TEXT NOT NULL,
    destination TEXT,  -- 'people', 'projects', etc. or NULL if unclassified
    record_id UUID,    -- FK to the created record, NULL if needs_review
    confidence REAL,
    status TEXT DEFAULT 'filed',  -- 'filed', 'needs_review', 'fixed'
    matrix_event_id TEXT,
    matrix_room_id TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_admin_due_date ON admin(due_date);
CREATE INDEX idx_admin_status ON admin(status);
CREATE INDEX idx_inbox_log_status ON inbox_log(status);
CREATE INDEX idx_inbox_log_created ON inbox_log(created_at);

-- Full-text search indexes
CREATE INDEX idx_people_search ON people USING gin(to_tsvector('english', name || ' ' || COALESCE(context, '')));
CREATE INDEX idx_projects_search ON projects USING gin(to_tsvector('english', name || ' ' || COALESCE(notes, '')));
CREATE INDEX idx_ideas_search ON ideas USING gin(to_tsvector('english', title || ' ' || COALESCE(one_liner, '') || ' ' || COALESCE(elaboration, '')));
CREATE INDEX idx_decisions_search ON decisions USING gin(to_tsvector('english', title || ' ' || decision || ' ' || COALESCE(rationale, '')));
CREATE INDEX idx_howtos_search ON howtos USING gin(to_tsvector('english', title || ' ' || content));
CREATE INDEX idx_snippets_search ON snippets USING gin(to_tsvector('english', title || ' ' || content));
```

### 1.3 Apply schema

```bash
psql -U secondbrain -d secondbrain -f schema.sql
```

## Step 2: Project Structure

```
second-brain/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Entry point, Matrix client setup
│   ├── config.py            # Configuration loading
│   ├── db.py                # Database operations
│   ├── classifier.py        # LLM classification logic
│   ├── router.py            # Prefix detection + routing
│   └── handlers.py          # Message handlers
├── scripts/
│   ├── daily_digest.py      # Cron job (Phase 3)
│   └── weekly_review.py     # Cron job (Phase 4)
├── prompts/
│   ├── classify.txt         # Classification prompt
│   ├── daily.txt            # Daily digest prompt (Phase 3)
│   ├── weekly.txt           # Weekly review prompt (Phase 4)
│   └── retrieval.txt        # Retrieval prompt (Phase 5)
├── schema.sql
├── requirements.txt
├── .env.example
└── README.md
```

## Step 3: Dependencies

Create `requirements.txt`:

```
matrix-nio[e2e]==0.24.0
asyncpg==0.29.0
httpx==0.27.0
python-dotenv==1.0.1
```

Install:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 4: Configuration

Create `.env.example`:

```bash
# Matrix
MATRIX_HOMESERVER=https://matrix.yourdomain.com
MATRIX_USER_ID=@secondbrain:yourdomain.com
MATRIX_PASSWORD=your-bot-password
MATRIX_INBOX_ROOM=#sb-inbox:yourdomain.com

# Database
DATABASE_URL=postgresql://secondbrain:your-secure-password@localhost/secondbrain

# LLM APIs
GLM_API_URL=https://api.z.ai/v1/chat/completions
GLM_API_KEY=your-glm-key
GLM_MODEL=glm-4

CLAUDE_API_URL=https://api.anthropic.com/v1/messages
CLAUDE_API_KEY=your-claude-key
CLAUDE_MODEL=claude-sonnet-4-20250514

# Classification settings
CONFIDENCE_THRESHOLD=0.6
```

Copy to `.env` and fill in real values:

```bash
cp .env.example .env
```

## Step 5: Core Code

### 5.1 config.py

```python
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Matrix
    MATRIX_HOMESERVER = os.getenv("MATRIX_HOMESERVER")
    MATRIX_USER_ID = os.getenv("MATRIX_USER_ID")
    MATRIX_PASSWORD = os.getenv("MATRIX_PASSWORD")
    MATRIX_INBOX_ROOM = os.getenv("MATRIX_INBOX_ROOM")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")

    # LLM
    GLM_API_URL = os.getenv("GLM_API_URL")
    GLM_API_KEY = os.getenv("GLM_API_KEY")
    GLM_MODEL = os.getenv("GLM_MODEL", "glm-4")

    CLAUDE_API_URL = os.getenv("CLAUDE_API_URL")
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    # Settings
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
```

### 5.2 db.py

```python
import asyncpg
from typing import Optional
from config import Config

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(Config.DATABASE_URL)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def insert_record(table: str, data: dict) -> str:
    """Insert a record and return its ID."""
    pool = await get_pool()
    
    columns = ", ".join(data.keys())
    placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
    values = list(data.values())
    
    query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"
    
    async with pool.acquire() as conn:
        record_id = await conn.fetchval(query, *values)
        return str(record_id)


async def insert_inbox_log(
    raw_text: str,
    destination: Optional[str],
    record_id: Optional[str],
    confidence: Optional[float],
    status: str,
    matrix_event_id: str,
    matrix_room_id: str,
) -> str:
    """Log an inbox entry."""
    return await insert_record("inbox_log", {
        "raw_text": raw_text,
        "destination": destination,
        "record_id": record_id,
        "confidence": confidence,
        "status": status,
        "matrix_event_id": matrix_event_id,
        "matrix_room_id": matrix_room_id,
    })
```

### 5.3 classifier.py

```python
import httpx
import json
from typing import Optional
from config import Config

CLASSIFICATION_PROMPT = """You are a classifier for a personal knowledge management system.

Given a raw thought, classify it into ONE of these categories:
- people: Information about a person, relationship notes, follow-up reminders for someone
- projects: Active work items, tasks with multiple steps, ongoing efforts
- ideas: Insights, possibilities, things to explore later
- admin: Errands, single tasks with deadlines, administrative duties

Return ONLY valid JSON with this exact structure:
{
  "category": "people|projects|ideas|admin",
  "confidence": 0.0-1.0,
  "extracted": {
    // For people: {"name": "", "context": "", "follow_ups": ""}
    // For projects: {"name": "", "status": "active", "next_action": "", "notes": ""}
    // For ideas: {"title": "", "one_liner": "", "elaboration": ""}
    // For admin: {"name": "", "due_date": "YYYY-MM-DD or null", "notes": ""}
  },
  "tags": ["tag1", "tag2"]
}

Rules:
- Extract a clear, actionable next_action for projects (not vague intentions)
- For people, extract any mentioned follow-ups
- For admin, extract due dates if mentioned (interpret "next week", "by Friday", etc.)
- Tags should be 1-3 relevant keywords
- Confidence should reflect how certain you are about the category

Input thought:
"""


async def classify_thought(text: str) -> dict:
    """Classify a thought using GLM-4."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            Config.GLM_API_URL,
            headers={
                "Authorization": f"Bearer {Config.GLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": Config.GLM_MODEL,
                "messages": [
                    {"role": "user", "content": CLASSIFICATION_PROMPT + text}
                ],
                "temperature": 0.1,  # Low temperature for consistent classification
            },
        )
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # Parse JSON from response (handle potential markdown wrapping)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        
        return json.loads(content)


def parse_reference(text: str) -> Optional[dict]:
    """Check for reference prefixes and parse accordingly."""
    text_lower = text.lower().strip()
    
    if text_lower.startswith("decision:"):
        content = text[9:].strip()
        # Try to split on "because" for rationale
        if " because " in content.lower():
            parts = content.split(" because ", 1)
            return {
                "category": "decisions",
                "extracted": {
                    "title": parts[0].strip()[:100],  # First 100 chars as title
                    "decision": parts[0].strip(),
                    "rationale": parts[1].strip() if len(parts) > 1 else None,
                },
            }
        return {
            "category": "decisions",
            "extracted": {
                "title": content[:100],
                "decision": content,
                "rationale": None,
            },
        }
    
    elif text_lower.startswith("howto:"):
        content = text[6:].strip()
        # Split on → or - or : for title/content
        for sep in ["→", "->", " - ", ": "]:
            if sep in content:
                parts = content.split(sep, 1)
                return {
                    "category": "howtos",
                    "extracted": {
                        "title": parts[0].strip(),
                        "content": parts[1].strip() if len(parts) > 1 else content,
                    },
                }
        return {
            "category": "howtos",
            "extracted": {
                "title": content[:100],
                "content": content,
            },
        }
    
    elif text_lower.startswith("snippet:"):
        content = text[8:].strip()
        # Split on → or - for title/content
        for sep in ["→", "->", " - ", ": "]:
            if sep in content:
                parts = content.split(sep, 1)
                return {
                    "category": "snippets",
                    "extracted": {
                        "title": parts[0].strip(),
                        "content": parts[1].strip() if len(parts) > 1 else content,
                    },
                }
        return {
            "category": "snippets",
            "extracted": {
                "title": content[:100],
                "content": content,
            },
        }
    
    return None
```

### 5.4 router.py

```python
from typing import Tuple, Optional
from classifier import classify_thought, parse_reference
from db import insert_record, insert_inbox_log
from config import Config


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


async def route_message(
    text: str,
    matrix_event_id: str,
    matrix_room_id: str,
) -> Tuple[str, Optional[str], Optional[float], str]:
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
            matrix_event_id=matrix_event_id,
            matrix_room_id=matrix_room_id,
        )
        
        return category, record_id, 1.0, "filed"
    
    # No prefix - classify with LLM
    try:
        classification = await classify_thought(text)
    except Exception as e:
        # LLM failed - log for review
        await insert_inbox_log(
            raw_text=text,
            destination=None,
            record_id=None,
            confidence=None,
            status="needs_review",
            matrix_event_id=matrix_event_id,
            matrix_room_id=matrix_room_id,
        )
        return None, None, None, "needs_review"
    
    category = classification.get("category")
    confidence = classification.get("confidence", 0.0)
    extracted = classification.get("extracted", {})
    tags = classification.get("tags", [])
    
    # Add tags to extracted data
    if tags:
        extracted["tags"] = tags
    
    # Check confidence threshold
    if confidence < Config.CONFIDENCE_THRESHOLD:
        await insert_inbox_log(
            raw_text=text,
            destination=category,
            record_id=None,
            confidence=confidence,
            status="needs_review",
            matrix_event_id=matrix_event_id,
            matrix_room_id=matrix_room_id,
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
            matrix_event_id=matrix_event_id,
            matrix_room_id=matrix_room_id,
        )
        return None, None, confidence, "needs_review"
    
    record_id = await insert_record(table, extracted)
    
    await insert_inbox_log(
        raw_text=text,
        destination=category,
        record_id=record_id,
        confidence=confidence,
        status="filed",
        matrix_event_id=matrix_event_id,
        matrix_room_id=matrix_room_id,
    )
    
    return category, record_id, confidence, "filed"
```

### 5.5 main.py

```python
import asyncio
import logging
from nio import AsyncClient, MatrixRoom, RoomMessageText, LoginResponse

from config import Config
from router import route_message
from db import close_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecondBrainBot:
    def __init__(self):
        self.client = AsyncClient(Config.MATRIX_HOMESERVER, Config.MATRIX_USER_ID)
        self.inbox_room_id = None
    
    async def login(self):
        response = await self.client.login(Config.MATRIX_PASSWORD)
        if isinstance(response, LoginResponse):
            logger.info(f"Logged in as {Config.MATRIX_USER_ID}")
        else:
            logger.error(f"Login failed: {response}")
            raise Exception("Login failed")
    
    async def resolve_room_alias(self, alias: str) -> str:
        """Resolve a room alias to room ID."""
        response = await self.client.room_resolve_alias(alias)
        return response.room_id
    
    async def on_message(self, room: MatrixRoom, event: RoomMessageText):
        # Ignore our own messages
        if event.sender == self.client.user_id:
            return
        
        # Only process messages in the inbox room
        if room.room_id != self.inbox_room_id:
            return
        
        text = event.body.strip()
        if not text:
            return
        
        logger.info(f"Processing: {text[:50]}...")
        
        # Route the message
        category, record_id, confidence, status = await route_message(
            text=text,
            matrix_event_id=event.event_id,
            matrix_room_id=room.room_id,
        )
        
        # Log result (confirmations added in Phase 2)
        if status == "filed":
            logger.info(f"Filed to {category} (confidence: {confidence:.2f})")
        else:
            logger.info(f"Needs review (suggested: {category}, confidence: {confidence})")
    
    async def run(self):
        await self.login()
        
        # Resolve inbox room alias to ID
        if Config.MATRIX_INBOX_ROOM.startswith("#"):
            self.inbox_room_id = await self.resolve_room_alias(Config.MATRIX_INBOX_ROOM)
        else:
            self.inbox_room_id = Config.MATRIX_INBOX_ROOM
        
        logger.info(f"Watching room: {self.inbox_room_id}")
        
        # Register message callback
        self.client.add_event_callback(self.on_message, RoomMessageText)
        
        # Sync forever
        await self.client.sync_forever(timeout=30000)
    
    async def shutdown(self):
        await self.client.close()
        await close_pool()


async def main():
    bot = SecondBrainBot()
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

## Step 6: Test the Core Loop

### 6.1 Create the Matrix room

In Element/FluffyChat:
1. Create a new private room named `sb-inbox` (or your preferred name)
2. Invite your bot user
3. Accept the invite from the bot (or auto-accept in code)

### 6.2 Run the bot

```bash
source venv/bin/activate
python bot/main.py
```

### 6.3 Test messages

Send these to `#sb-inbox`:

```
Met João at conference, works on EHR integration at Hospital X

Need to review papercage nftables rules this week

Could use Matrix reactions for quick triage in the bot

Renew domain carloszan.com by January 15

decision: Using Postgres over markdown because queryability and atomic transactions

howto: Restart papercage → systemctl --user restart papercage-sandbox

snippet: Firejail base → firejail --net=none --private-tmp --private-dev
```

### 6.4 Verify storage

```bash
psql -U secondbrain -d secondbrain

-- Check each table
SELECT * FROM people;
SELECT * FROM projects;
SELECT * FROM ideas;
SELECT * FROM admin;
SELECT * FROM decisions;
SELECT * FROM howtos;
SELECT * FROM snippets;
SELECT * FROM inbox_log ORDER BY created_at DESC;
```

## Phase 1 Checklist

- [ ] PostgreSQL installed and schema applied
- [ ] Python environment set up with dependencies
- [ ] `.env` configured with real credentials
- [ ] Matrix bot user created and can log in
- [ ] `#sb-inbox` room created and bot invited
- [ ] Bot successfully processes test messages
- [ ] Records appear in correct tables
- [ ] inbox_log contains audit trail

## What's Missing (Added in Later Phases)

- **Phase 2**: Bot replies with confirmation, fix command works
- **Phase 3**: Daily digest at 6am
- **Phase 4**: Weekly review on Sunday
- **Phase 5**: `?recall` and `?search` commands
- **Phase 6**: Tuning, error handling, maintenance procedures
