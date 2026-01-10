# Phase 2: Trust Mechanisms

## Goal

Add the components that build trust in the system:
1. **Confirmations**: Bot replies with what it did
2. **Fix command**: One-step correction via `fix:` reply
3. **Clarification**: Ask user when confidence is low

## Why This Matters

From the video:
> "You don't abandon systems because they're imperfect. You abandon them because you stop trusting them."

Trust comes from:
- Seeing what the system did (confirmation)
- Being able to correct mistakes easily (fix command)
- The system asking instead of guessing wrong (clarification)

## Step 1: Update Database Schema

Add a table to track pending clarifications:

```sql
-- Add to schema.sql or run directly
CREATE TABLE pending_clarifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inbox_log_id UUID REFERENCES inbox_log(id),
    matrix_event_id TEXT NOT NULL,
    matrix_room_id TEXT NOT NULL,
    suggested_category TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Add index for cleanup
CREATE INDEX idx_pending_created ON pending_clarifications(created_at);
```

## Step 2: Enhanced Database Operations

Update `db.py`:

```python
import asyncpg
from typing import Optional, List, Dict, Any
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


async def update_record(table: str, record_id: str, data: dict) -> bool:
    """Update a record by ID."""
    pool = await get_pool()
    
    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
    values = [record_id] + list(data.values())
    
    query = f"UPDATE {table} SET {set_clause}, updated_at = NOW() WHERE id = $1"
    
    async with pool.acquire() as conn:
        result = await conn.execute(query, *values)
        return result == "UPDATE 1"


async def delete_record(table: str, record_id: str) -> bool:
    """Delete a record by ID."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        result = await conn.execute(f"DELETE FROM {table} WHERE id = $1", record_id)
        return result == "DELETE 1"


async def get_record(table: str, record_id: str) -> Optional[Dict[str, Any]]:
    """Get a record by ID."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(f"SELECT * FROM {table} WHERE id = $1", record_id)
        return dict(row) if row else None


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


async def update_inbox_log(log_id: str, data: dict) -> bool:
    """Update an inbox log entry."""
    pool = await get_pool()
    
    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
    values = [log_id] + list(data.values())
    
    query = f"UPDATE inbox_log SET {set_clause} WHERE id = $1"
    
    async with pool.acquire() as conn:
        result = await conn.execute(query, *values)
        return result == "UPDATE 1"


async def get_inbox_log_by_event(matrix_event_id: str) -> Optional[Dict[str, Any]]:
    """Get inbox log by Matrix event ID."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM inbox_log WHERE matrix_event_id = $1",
            matrix_event_id
        )
        return dict(row) if row else None


async def insert_pending_clarification(
    inbox_log_id: str,
    matrix_event_id: str,
    matrix_room_id: str,
    suggested_category: Optional[str],
) -> str:
    """Create a pending clarification entry."""
    return await insert_record("pending_clarifications", {
        "inbox_log_id": inbox_log_id,
        "matrix_event_id": matrix_event_id,
        "matrix_room_id": matrix_room_id,
        "suggested_category": suggested_category,
    })


async def get_pending_by_reply_to(original_event_id: str) -> Optional[Dict[str, Any]]:
    """Get pending clarification by the original event it's replying to."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT pc.*, il.raw_text "
            "FROM pending_clarifications pc "
            "JOIN inbox_log il ON pc.inbox_log_id = il.id "
            "WHERE pc.matrix_event_id = $1",
            original_event_id
        )
        return dict(row) if row else None


async def delete_pending_clarification(clarification_id: str) -> bool:
    """Delete a pending clarification."""
    return await delete_record("pending_clarifications", clarification_id)


async def cleanup_old_pending(days: int = 7) -> int:
    """Delete pending clarifications older than N days."""
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM pending_clarifications "
            "WHERE created_at < NOW() - INTERVAL '$1 days'",
            days
        )
        # Extract count from "DELETE N"
        return int(result.split()[-1])
```

## Step 3: Message Response Handler

Create `bot/responder.py`:

```python
from nio import AsyncClient, RoomMessageText


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
        "m.relates_to": {
            "m.in_reply_to": {
                "event_id": reply_to_event_id
            }
        }
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
        "m.relates_to": {
            "m.in_reply_to": {
                "event_id": reply_to_event_id
            }
        }
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
        "m.relates_to": {
            "m.in_reply_to": {
                "event_id": reply_to_event_id
            }
        }
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
        "m.relates_to": {
            "m.in_reply_to": {
                "event_id": reply_to_event_id
            }
        }
    }
    
    response = await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content=content,
    )
    
    return response.event_id
```

## Step 4: Fix Command Handler

Create `bot/fix_handler.py`:

```python
import re
from typing import Optional, Tuple
from db import (
    get_inbox_log_by_event,
    get_record,
    delete_record,
    insert_record,
    update_inbox_log,
)
from classifier import classify_thought

# Valid categories for fix command
VALID_CATEGORIES = {
    "person": "people",
    "people": "people",
    "project": "projects",
    "projects": "projects",
    "idea": "ideas",
    "ideas": "ideas",
    "admin": "admin",
    "decision": "decisions",
    "decisions": "decisions",
    "howto": "howtos",
    "howtos": "howtos",
    "snippet": "snippets",
    "snippets": "snippets",
}

# Table to category display name
CATEGORY_DISPLAY = {
    "people": "people",
    "projects": "project",
    "ideas": "idea",
    "admin": "admin",
    "decisions": "decision",
    "howtos": "howto",
    "snippets": "snippet",
}


def parse_fix_command(text: str) -> Optional[str]:
    """
    Parse a fix command from message text.
    Returns the target category or None if not a fix command.
    
    Formats:
    - fix: people
    - fix: person
    - fix:project
    """
    text = text.strip().lower()
    
    # Match "fix:" followed by category
    match = re.match(r'^fix:\s*(\w+)', text)
    if not match:
        return None
    
    category_input = match.group(1)
    return VALID_CATEGORIES.get(category_input)


async def handle_fix(
    original_event_id: str,
    new_category: str,
) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """
    Handle a fix command.
    
    Returns: (success, message, old_category, extracted_name)
    """
    
    # Get the original inbox log entry
    log_entry = await get_inbox_log_by_event(original_event_id)
    if not log_entry:
        return False, "Couldn't find the original message to fix", None, None
    
    old_category = log_entry["destination"]
    old_record_id = log_entry["record_id"]
    raw_text = log_entry["raw_text"]
    
    # If same category, nothing to do
    if old_category == new_category:
        return False, f"Already filed as {CATEGORY_DISPLAY.get(new_category, new_category)}", None, None
    
    # Delete old record if it exists
    if old_record_id and old_category:
        await delete_record(old_category, str(old_record_id))
    
    # Re-classify for the new category
    # For dynamic categories, use LLM
    # For reference categories, parse directly
    if new_category in ("decisions", "howtos", "snippets"):
        # Reference categories need the prefix
        # Add the prefix and re-parse
        prefix_map = {
            "decisions": "decision:",
            "howtos": "howto:",
            "snippets": "snippet:",
        }
        prefixed_text = f"{prefix_map[new_category]} {raw_text}"
        
        from classifier import parse_reference
        ref_result = parse_reference(prefixed_text)
        
        if ref_result:
            extracted = ref_result["extracted"]
            new_record_id = await insert_record(new_category, extracted)
            extracted_name = extracted.get("title") or extracted.get("name") or raw_text[:50]
        else:
            return False, "Couldn't parse as reference", None, None
    else:
        # Dynamic category - re-classify with LLM
        try:
            classification = await classify_thought(raw_text)
            extracted = classification.get("extracted", {})
            tags = classification.get("tags", [])
            if tags:
                extracted["tags"] = tags
            
            new_record_id = await insert_record(new_category, extracted)
            extracted_name = (
                extracted.get("name") or
                extracted.get("title") or
                raw_text[:50]
            )
        except Exception as e:
            return False, f"Classification failed: {str(e)}", None, None
    
    # Update inbox log
    await update_inbox_log(str(log_entry["id"]), {
        "destination": new_category,
        "record_id": new_record_id,
        "status": "fixed",
    })
    
    return True, "Fixed", old_category, extracted_name
```

## Step 5: Update Main Bot

Update `bot/main.py`:

```python
import asyncio
import logging
from nio import (
    AsyncClient,
    MatrixRoom,
    RoomMessageText,
    LoginResponse,
    RoomMemberEvent,
)

from config import Config
from router import route_message
from db import (
    close_pool,
    insert_pending_clarification,
    get_pending_by_reply_to,
    delete_pending_clarification,
    get_inbox_log_by_event,
)
from responder import (
    send_confirmation,
    send_clarification_request,
    send_fix_confirmation,
    send_error,
)
from fix_handler import parse_fix_command, handle_fix, CATEGORY_DISPLAY
from classifier import parse_reference, classify_thought

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
    
    def get_reply_to_event_id(self, event: RoomMessageText) -> Optional[str]:
        """Extract the event ID this message is replying to, if any."""
        relates_to = event.source.get("content", {}).get("m.relates_to", {})
        reply_to = relates_to.get("m.in_reply_to", {})
        return reply_to.get("event_id")
    
    async def handle_reply(self, room: MatrixRoom, event: RoomMessageText, reply_to_id: str):
        """Handle a reply to a previous message (fix command or clarification)."""
        text = event.body.strip()
        
        # Check if it's a fix command
        new_category = parse_fix_command(text)
        if new_category:
            # This is a fix command - find the original message
            # The reply_to_id might be our confirmation, so we need to trace back
            success, message, old_category, extracted_name = await handle_fix(
                original_event_id=reply_to_id,
                new_category=new_category,
            )
            
            if success:
                await send_fix_confirmation(
                    client=self.client,
                    room_id=room.room_id,
                    reply_to_event_id=event.event_id,
                    old_category=CATEGORY_DISPLAY.get(old_category, old_category),
                    new_category=CATEGORY_DISPLAY.get(new_category, new_category),
                    extracted_name=extracted_name,
                )
            else:
                await send_error(
                    client=self.client,
                    room_id=room.room_id,
                    reply_to_event_id=event.event_id,
                    message=message,
                )
            return
        
        # Check if this is a clarification response
        pending = await get_pending_by_reply_to(reply_to_id)
        if pending:
            await self.handle_clarification_response(room, event, pending)
            return
        
        # Check if it's "skip"
        if text.lower() == "skip":
            # Find the pending clarification
            pending = await get_pending_by_reply_to(reply_to_id)
            if pending:
                await delete_pending_clarification(str(pending["id"]))
                await self.client.room_send(
                    room_id=room.room_id,
                    message_type="m.room.message",
                    content={
                        "msgtype": "m.text",
                        "body": "✓ Skipped",
                        "m.relates_to": {
                            "m.in_reply_to": {"event_id": event.event_id}
                        }
                    }
                )
            return
    
    async def handle_clarification_response(
        self,
        room: MatrixRoom,
        event: RoomMessageText,
        pending: dict,
    ):
        """Handle a user's response to a clarification request."""
        text = event.body.strip()
        raw_text = pending["raw_text"]
        
        # Check for category prefix in response
        ref_result = parse_reference(text)
        if ref_result:
            # User provided a reference prefix
            category = ref_result["category"]
            extracted = ref_result["extracted"]
        else:
            # Check for dynamic category prefix
            category_prefixes = {
                "person:": "people",
                "people:": "people",
                "project:": "projects",
                "projects:": "projects",
                "idea:": "ideas",
                "ideas:": "ideas",
                "admin:": "admin",
            }
            
            text_lower = text.lower()
            category = None
            for prefix, cat in category_prefixes.items():
                if text_lower.startswith(prefix):
                    category = cat
                    break
            
            if not category:
                await send_error(
                    client=self.client,
                    room_id=room.room_id,
                    reply_to_event_id=event.event_id,
                    message="Didn't understand. Reply with a category prefix like `person:` or `project:`",
                )
                return
            
            # Re-classify with LLM for dynamic categories
            try:
                classification = await classify_thought(raw_text)
                extracted = classification.get("extracted", {})
                tags = classification.get("tags", [])
                if tags:
                    extracted["tags"] = tags
            except Exception:
                extracted = {"name": raw_text[:100], "notes": raw_text}
        
        # Store the record
        from db import insert_record, update_inbox_log
        from router import CATEGORY_TABLE_MAP
        
        table = CATEGORY_TABLE_MAP.get(category)
        record_id = await insert_record(table, extracted)
        
        # Update inbox log
        await update_inbox_log(str(pending["inbox_log_id"]), {
            "destination": category,
            "record_id": record_id,
            "status": "filed",
            "confidence": 1.0,  # User explicitly chose
        })
        
        # Delete pending clarification
        await delete_pending_clarification(str(pending["id"]))
        
        # Confirm
        extracted_name = extracted.get("name") or extracted.get("title") or raw_text[:50]
        await send_confirmation(
            client=self.client,
            room_id=room.room_id,
            reply_to_event_id=event.event_id,
            category=CATEGORY_DISPLAY.get(category, category),
            confidence=1.0,
            extracted_name=extracted_name,
        )
    
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
        
        # Check if this is a reply to another message
        reply_to_id = self.get_reply_to_event_id(event)
        if reply_to_id:
            await self.handle_reply(room, event, reply_to_id)
            return
        
        logger.info(f"Processing: {text[:50]}...")
        
        # Route the message
        category, record_id, confidence, status = await route_message(
            text=text,
            matrix_event_id=event.event_id,
            matrix_room_id=room.room_id,
        )
        
        if status == "filed":
            # Get extracted name for confirmation
            if record_id and category:
                from db import get_record
                from router import CATEGORY_TABLE_MAP
                record = await get_record(CATEGORY_TABLE_MAP[category], record_id)
                extracted_name = (
                    record.get("name") or
                    record.get("title") or
                    text[:50]
                ) if record else text[:50]
            else:
                extracted_name = text[:50]
            
            await send_confirmation(
                client=self.client,
                room_id=room.room_id,
                reply_to_event_id=event.event_id,
                category=CATEGORY_DISPLAY.get(category, category),
                confidence=confidence,
                extracted_name=extracted_name,
            )
            logger.info(f"Filed to {category} (confidence: {confidence:.2f})")
        
        else:  # needs_review
            # Get the inbox log ID for this event
            log_entry = await get_inbox_log_by_event(event.event_id)
            if log_entry:
                await insert_pending_clarification(
                    inbox_log_id=str(log_entry["id"]),
                    matrix_event_id=event.event_id,
                    matrix_room_id=room.room_id,
                    suggested_category=category,
                )
            
            await send_clarification_request(
                client=self.client,
                room_id=room.room_id,
                reply_to_event_id=event.event_id,
                suggested_category=category,
                confidence=confidence,
            )
            logger.info(f"Asked for clarification (suggested: {category}, confidence: {confidence})")
    
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

## Step 6: Test the Trust Mechanisms

### 6.1 Test confirmation

Send a clear message:

```
Meeting with Dr. Silva next week about EHR integration
```

Expected bot reply:
```
✓ Filed as people: "Dr. Silva"
Confidence: 85%
Reply `fix: <category>` if wrong
```

### 6.2 Test fix command

Reply to the bot's confirmation:

```
fix: project
```

Expected:
```
✓ Fixed: moved from people → project
Entry: "Meeting with Dr. Silva - EHR integration"
```

### 6.3 Test clarification

Send an ambiguous message:

```
EHR
```

Expected:
```
🤔 Not sure about this one.
Best guess: idea (45% confident)

Reply with one of:
• `person:` - if about a person
• `project:` - if it's a project
• `idea:` - if it's an idea
• `admin:` - if it's a task/errand
• `decision:` - to save as a decision
• `howto:` - to save as a how-to
• `snippet:` - to save as a snippet
• `skip` - to ignore
```

Reply with:
```
project:
```

Expected:
```
✓ Filed as project: "EHR"
Confidence: 100%
Reply `fix: <category>` if wrong
```

## Phase 2 Checklist

- [ ] `pending_clarifications` table created
- [ ] Bot sends confirmation after filing
- [ ] `fix:` command moves records correctly
- [ ] Low-confidence items trigger clarification request
- [ ] User can respond with category prefix
- [ ] `skip` command works
- [ ] All interactions logged in inbox_log

## Interaction Flow Summary

```
User sends message
        │
        ▼
  Has prefix? ─────Yes────▶ Store as reference
        │                         │
       No                         ▼
        │                   Confirm + offer fix
        ▼
  Classify with LLM
        │
        ▼
  Confidence ≥ 0.6? ──Yes──▶ Store + Confirm
        │                         │
       No                         ▼
        │                   Offer fix command
        ▼
  Ask for clarification
        │
        ▼
  User replies with prefix
        │
        ▼
  Store + Confirm
```
