# Telegram Migration Plan

## Overview

Migrate Leaknote from Matrix (Dendrite + matrix-nio) to Telegram Bot API. This migration removes the need for self-hosted Matrix infrastructure while maintaining all core functionality.

## Goals

1. **Remove Matrix dependencies**: Eliminate Dendrite server, matrix-nio library
2. **Migrate to Telegram**: Use python-telegram-bot library
3. **Maintain functionality**: Preserve all capture, classification, query, and digest features
4. **Security**: Bot responds only to owner, private group control
5. **Simplify deployment**: Remove Dendrite container and complexity

## Architecture Changes

### Before (Matrix)
```
┌─────────────────────────────────────────────────────────────┐
│  Dendrite (Matrix Server)                                    │
│    ├── Requires PostgreSQL database                          │
│    ├── Exposed ports 8008, 8448                              │
│    ├── Room management                                       │
│    └── User authentication                                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Leaknote Bot (matrix-nio)                                   │
│    ├── AsyncClient connection                                │
│    ├── Room event callbacks                                  │
│    ├── Event deduplication                                   │
│    └── Message threading/replies                             │
└─────────────────────────────────────────────────────────────┘
```

### After (Telegram)
```
┌─────────────────────────────────────────────────────────────┐
│  Telegram Cloud                                              │
│    ├── Message handling                                      │
│    ├── User authentication                                   │
│    ├── Group management                                      │
│    └── Built-in storage/queuing                              │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Leaknote Bot (python-telegram-bot)                          │
│    ├── Webhook or polling                                    │
│    ├── Update handlers                                       │
│    ├── Built-in command routing                              │
│    └── Reply keyboard support                                │
└─────────────────────────────────────────────────────────────┘
```

## Phase 1: Telegram Bot Setup

### 1.1 Create Bot with BotFather

**Instructions:**

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow prompts:
   - **Bot name**: `Leaknote` (or your preference)
   - **Bot username**: `<your_username>_leaknote_bot` (must end in `bot`)
4. **Save the API token** - you'll need this for `TELEGRAM_BOT_TOKEN`
5. **Important**: Keep this token secret - it's equivalent to the bot's password

Example session:
```
You: /newbot
BotFather: Alright, a new bot. How are we going to call it?
You: Leaknote
BotFather: Good. Now let's choose a username for your bot.
You: carlos_leaknote_bot
BotFather: Done! Congratulations on your new bot. You will find it at t.me/carlos_leaknote_bot
          Here is your token: 7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
```

### 1.2 Configure Bot Privacy and Security

**Get your Telegram User ID:**

1. Open chat with `@userinfobot`
2. Send any message
3. **Save your User ID** - you'll need this for `TELEGRAM_OWNER_ID`

**Configure bot privacy with BotFather:**

1. Send `/mybots` to BotFather
2. Select your bot
3. Go to **Bot Settings** → **Group Privacy**
4. **DISABLE** group privacy (allows bot to read all messages in groups)
5. Go to **Bot Settings** → **Inline Mode**
6. **DISABLE** inline mode (not needed)

**Why disable group privacy?**
- By default, bots only see messages that start with `/` or mention the bot
- Leaknote needs to capture all messages in the inbox channel
- Security is handled via owner ID check in code

### 1.3 Create Private Channel for Inbox

**Instructions:**

1. In Telegram, create a **New Channel** (not group)
2. Name it: `Leaknote Inbox`
3. Set to **Private**
4. Add your bot as **Administrator** with these permissions:
   - ✓ Post messages
   - ✓ Edit messages
   - ✓ Delete messages
   - ✓ All other permissions can be disabled

**Get Channel ID:**

Method 1 - Via Bot:
1. Forward any message from the channel to `@userinfobot`
2. It will show the channel ID (starts with `-100`)

Method 2 - Via Web:
1. Open channel in Telegram Web
2. URL will show channel ID: `https://web.telegram.org/z/#-1001234567890`
3. Channel ID is the number after `#` (including the minus)

**Save this as** `TELEGRAM_INBOX_CHAT_ID`

### 1.4 Security Configuration Summary

**Environment variables needed:**
```bash
TELEGRAM_BOT_TOKEN="7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
TELEGRAM_OWNER_ID="123456789"
TELEGRAM_INBOX_CHAT_ID="-1001234567890"
```

**Security enforcement in code:**
- Bot will check every message sender against `TELEGRAM_OWNER_ID`
- Only owner can send messages to inbox
- Only owner can add bot to groups
- Only owner can use query commands
- Bot will ignore all other users completely

## Phase 2: Code Migration Strategy

### 2.1 Files to Modify

| File | Matrix-Specific Code | Migration Action |
|------|---------------------|-----------------|
| `requirements.txt` | `matrix-nio[e2e]` | Replace with `python-telegram-bot>=20.0` |
| `bot/config.py` | Matrix config vars | Replace with Telegram vars |
| `bot/main.py` | `AsyncClient`, `RoomMessageText` | Rewrite with `Application`, `Update` |
| `bot/responder.py` | `send_message()`, Matrix API | Rewrite with Telegram `send_message()` |
| `docker-compose.yml` | `dendrite` service | Remove entirely |
| `.env` | Matrix vars | Replace with Telegram vars |

### 2.2 Files That Don't Change

These files have **no Matrix-specific code**:
- `bot/classifier.py` - Pure LLM logic
- `bot/commands.py` - Query parsing and formatting
- `bot/db.py` - Pure PostgreSQL
- `bot/queries.py` - Pure PostgreSQL
- `bot/router.py` - Message routing logic
- `bot/fix_handler.py` - Fix command parsing
- `bot/digest.py` - Digest generation
- `bot/weekly_review.py` - Weekly review generation
- `bot/llm/` - LLM client abstraction
- `schema.sql` - Database schema
- `prompts/` - LLM prompts

### 2.3 API Mapping: Matrix → Telegram

| Matrix Concept | Telegram Equivalent | Notes |
|---------------|---------------------|-------|
| `AsyncClient` | `Application` | Main bot class |
| `RoomMessageText` event | `Update.message` | Incoming message |
| `event.body` | `message.text` | Message content |
| `event.sender` | `message.from_user.id` | User identification |
| `event.event_id` | `message.message_id` | Message identifier |
| Room alias | Chat ID | Numeric identifier |
| `client.room_send()` | `bot.send_message()` | Send message |
| Reply to message | `reply_to_message_id` | Message threading |
| Room join | Bot added to chat | Automatic |
| Login/password | Bot token | Single token auth |

## Phase 3: Detailed Implementation Steps

### 3.1 Update Dependencies

**File: `requirements.txt`**

Remove:
```python
matrix-nio[e2e]==0.24.0
```

Add:
```python
python-telegram-bot==20.7
```

Keep all other dependencies unchanged.

### 3.2 Update Configuration

**File: `bot/config.py`**

Replace Matrix section:
```python
# OLD - Matrix
MATRIX_HOMESERVER = os.getenv("MATRIX_HOMESERVER", "http://dendrite:8008")
MATRIX_USER_ID = os.getenv("MATRIX_USER_ID")
MATRIX_PASSWORD = os.getenv("MATRIX_PASSWORD")
MATRIX_INBOX_ROOM = os.getenv("MATRIX_INBOX_ROOM")
```

With Telegram section:
```python
# NEW - Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_OWNER_ID = int(os.getenv("TELEGRAM_OWNER_ID", "0"))
TELEGRAM_INBOX_CHAT_ID = int(os.getenv("TELEGRAM_INBOX_CHAT_ID", "0"))
```

Update validation:
```python
@classmethod
def validate(cls) -> list[str]:
    """Validate required configuration. Returns list of missing vars."""
    required = [
        ("TELEGRAM_BOT_TOKEN", cls.TELEGRAM_BOT_TOKEN),
        ("TELEGRAM_OWNER_ID", cls.TELEGRAM_OWNER_ID),
        ("TELEGRAM_INBOX_CHAT_ID", cls.TELEGRAM_INBOX_CHAT_ID),
        ("DATABASE_URL", cls.DATABASE_URL),
        ("CLASSIFY_API_URL", cls.CLASSIFY_API_URL),
        ("CLASSIFY_API_KEY", cls.CLASSIFY_API_KEY),
        ("SUMMARY_API_URL", cls.SUMMARY_API_URL),
        ("SUMMARY_API_KEY", cls.SUMMARY_API_KEY),
        # Note: DIGEST_TARGET_USER removed - always send to owner
    ]
    return [name for name, value in required if not value]
```

### 3.3 Rewrite Main Bot

**File: `bot/main.py`**

**High-level structure:**

```python
"""Leaknote Bot - Main entry point (Telegram version)."""

import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)

from bot.config import Config
from router import route_message, CATEGORY_DISPLAY
from bot.db import (
    close_pool,
    get_record,
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
    send_message,
)
from fix_handler import parse_fix_command, handle_fix
from commands import parse_command, handle_command

logger = logging.getLogger(__name__)


class LeaknoteBot:
    """Telegram bot for Leaknote."""

    def __init__(self):
        self.application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        # Security check
        if update.effective_user.id != Config.TELEGRAM_OWNER_ID:
            return  # Ignore unauthorized users

        await update.message.reply_text(
            "Leaknote bot is running.\n\n"
            "Send messages here or in the inbox channel to capture thoughts.\n"
            "Available commands:\n"
            "• ?recall <query> - Search decisions, howtos, snippets\n"
            "• ?search <query> - Search all categories\n"
            "• ?people <query> - Search people\n"
            "• ?projects [status] - List projects\n"
            "• ?ideas - List recent ideas\n"
            "• ?admin [due] - List admin tasks"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all text messages."""
        # Security check - CRITICAL
        if update.effective_user.id != Config.TELEGRAM_OWNER_ID:
            logger.warning(f"Unauthorized access attempt from user {update.effective_user.id}")
            return

        message = update.message
        text = message.text

        # Check if this is a reply to a bot message (clarification or fix)
        if message.reply_to_message and message.reply_to_message.from_user.is_bot:
            await self.handle_reply(update, context)
            return

        # Check for query commands
        command_result = parse_command(text)
        if command_result:
            await self.handle_query_command(update, context, command_result)
            return

        # Check for fix command
        fix_result = parse_fix_command(text)
        if fix_result:
            await self.handle_fix_command(update, context, fix_result)
            return

        # Regular capture flow
        await self.handle_capture(update, context)

    async def handle_capture(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process a capture message through classification."""
        text = update.message.text
        message_id = update.message.message_id
        chat_id = update.effective_chat.id

        # Route the message
        result = await route_message(text)

        # Store in inbox_log
        from bot.db import insert_inbox_log
        record_id = await insert_inbox_log(
            raw_text=text,
            destination=result.get("category"),
            record_id=result.get("record_id"),
            confidence=result.get("confidence"),
            telegram_message_id=str(message_id),
            telegram_chat_id=str(chat_id),
        )

        # Respond based on result
        if result.get("needs_clarification"):
            await send_clarification_request(
                context.bot,
                chat_id,
                message_id,
                result.get("category"),
                result.get("confidence"),
            )
        else:
            await send_confirmation(
                context.bot,
                chat_id,
                message_id,
                result["category"],
                result["confidence"],
                result.get("extracted_name", text[:50]),
            )

    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle reply to clarification request."""
        # Implementation similar to Matrix version
        # but using Telegram message IDs
        pass

    async def handle_query_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, command_result):
        """Handle ?recall, ?search, etc."""
        command, arg = command_result
        response = await handle_command(command, arg)

        # Telegram has 4096 char limit per message
        # Split if needed
        await self.send_long_message(update.effective_chat.id, response)

    async def send_long_message(self, chat_id: int, text: str):
        """Send long message, splitting if needed."""
        MAX_LENGTH = 4096
        if len(text) <= MAX_LENGTH:
            await self.application.bot.send_message(chat_id, text)
        else:
            # Split at newlines near the limit
            chunks = []
            current_chunk = ""
            for line in text.split('\n'):
                if len(current_chunk) + len(line) + 1 > MAX_LENGTH:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    current_chunk += '\n' + line if current_chunk else line
            if current_chunk:
                chunks.append(current_chunk)

            for chunk in chunks:
                await self.application.bot.send_message(chat_id, chunk)

    async def handle_fix_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, fix_result):
        """Handle fix: command."""
        # Implementation similar to Matrix version
        pass

    def run(self):
        """Start the bot."""
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Start polling
        logger.info("Starting Telegram bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


async def main():
    """Main entry point."""
    # Validate config
    missing = Config.validate()
    if missing:
        logger.error(f"Missing configuration: {', '.join(missing)}")
        return

    # Start bot
    bot = LeaknoteBot()
    bot.run()


if __name__ == "__main__":
    asyncio.run(main())
```

**Key differences from Matrix:**

1. **No login flow** - Just token authentication
2. **Security via user ID check** - Every handler checks owner ID
3. **Simpler message handling** - No event deduplication needed (Telegram handles this)
4. **Built-in command routing** - Telegram has native command handlers
5. **Message length handling** - 4096 char limit vs Matrix's 65KB
6. **No room resolution** - Chat IDs are numeric and stable

### 3.4 Rewrite Responder

**File: `bot/responder.py`**

Replace all functions to use Telegram API:

```python
"""Telegram message response helpers."""

from typing import Optional
from telegram import Bot


async def send_confirmation(
    bot: Bot,
    chat_id: int,
    reply_to_message_id: int,
    category: str,
    confidence: float,
    extracted_name: str,
) -> int:
    """Send a confirmation message as a reply."""
    confidence_pct = int(confidence * 100)

    text = (
        f"✓ Filed as {category}: \"{extracted_name}\"\n"
        f"Confidence: {confidence_pct}%\n"
        f"Reply `fix: <category>` if wrong"
    )

    message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
    )

    return message.message_id


async def send_clarification_request(
    bot: Bot,
    chat_id: int,
    reply_to_message_id: int,
    suggested_category: Optional[str],
    confidence: Optional[float],
) -> int:
    """Ask for clarification when confidence is low."""

    if suggested_category and confidence:
        confidence_pct = int(confidence * 100)
        text = (
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
        text = (
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

    message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
    )

    return message.message_id


async def send_fix_confirmation(
    bot: Bot,
    chat_id: int,
    reply_to_message_id: int,
    old_category: str,
    new_category: str,
    extracted_name: str,
) -> int:
    """Confirm a fix was applied."""

    text = (
        f"✓ Fixed: moved from {old_category} → {new_category}\n"
        f"Entry: \"{extracted_name}\""
    )

    message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
    )

    return message.message_id


async def send_error(
    bot: Bot,
    chat_id: int,
    reply_to_message_id: int,
    message: str,
) -> int:
    """Send an error message."""

    msg = await bot.send_message(
        chat_id=chat_id,
        text=f"⚠️ {message}",
        reply_to_message_id=reply_to_message_id,
    )

    return msg.message_id


async def send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_to_message_id: Optional[int] = None,
) -> int:
    """Send a generic message, optionally as a reply."""

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"send_message: Sending message of length {len(text)} chars")
    logger.info(f"send_message: First 200 chars: {text[:200]}")
    logger.info(f"send_message: Last 200 chars: {text[-200:]}")

    message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
    )

    logger.info(f"send_message: Message sent successfully, message_id={message.message_id}")

    return message.message_id
```

### 3.5 Update Database Schema

**File: `bot/db.py`**

Update `insert_inbox_log` to use Telegram identifiers:

```python
async def insert_inbox_log(
    raw_text: str,
    destination: str,
    record_id: Optional[UUID],
    confidence: float,
    telegram_message_id: str,
    telegram_chat_id: str,
) -> UUID:
    """Insert a new inbox log entry."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO inbox_log (
                raw_text, destination, record_id, confidence,
                telegram_message_id, telegram_chat_id
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            raw_text,
            destination,
            record_id,
            confidence,
            telegram_message_id,
            telegram_chat_id,
        )
        return row["id"]
```

**File: `schema.sql`**

Update inbox_log and pending_clarifications tables:

```sql
-- OLD columns to remove:
-- matrix_event_id TEXT NOT NULL
-- matrix_room_id TEXT NOT NULL

-- NEW columns to add:
ALTER TABLE inbox_log
  DROP COLUMN matrix_event_id,
  DROP COLUMN matrix_room_id,
  ADD COLUMN telegram_message_id TEXT NOT NULL,
  ADD COLUMN telegram_chat_id TEXT NOT NULL;

ALTER TABLE pending_clarifications
  DROP COLUMN matrix_event_id,
  DROP COLUMN matrix_room_id,
  ADD COLUMN telegram_message_id TEXT NOT NULL,
  ADD COLUMN telegram_chat_id TEXT NOT NULL;

-- Update index
DROP INDEX IF EXISTS idx_inbox_log_event_id;
CREATE INDEX idx_inbox_log_telegram_message ON inbox_log(telegram_message_id);

DROP INDEX IF EXISTS idx_pending_event_id;
CREATE INDEX idx_pending_telegram_message ON pending_clarifications(telegram_message_id);
```

### 3.6 Update Docker Compose

**File: `docker-compose.yml`**

Remove entire `dendrite` service:

```yaml
# DELETE THIS ENTIRE BLOCK
# ===================
# Dendrite Matrix Server
# ===================
# dendrite:
#   image: matrixdotorg/dendrite-monolith:latest
#   ...entire section...
```

Update `leaknote` service:

```yaml
leaknote:
  build:
    context: .
    dockerfile: Dockerfile
  container_name: leaknote-bot
  restart: unless-stopped
  depends_on:
    postgres:
      condition: service_healthy
    # REMOVE: dendrite dependency
  environment:
    PYTHONPATH: /app

    # Telegram (NEW)
    TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN required}
    TELEGRAM_OWNER_ID: ${TELEGRAM_OWNER_ID:?TELEGRAM_OWNER_ID required}
    TELEGRAM_INBOX_CHAT_ID: ${TELEGRAM_INBOX_CHAT_ID:?TELEGRAM_INBOX_CHAT_ID required}

    # Database
    DATABASE_URL: postgresql://leaknote:${LEAKNOTE_DB_PASSWORD:-leaknote}@postgres:5432/leaknote

    # Classification LLM (cheap, fast)
    CLASSIFY_PROVIDER: ${CLASSIFY_PROVIDER:-openai}
    CLASSIFY_API_URL: ${CLASSIFY_API_URL:?CLASSIFY_API_URL required}
    CLASSIFY_API_KEY: ${CLASSIFY_API_KEY:?CLASSIFY_API_KEY required}
    CLASSIFY_MODEL: ${CLASSIFY_MODEL:-glm-4}

    # Summary LLM (quality)
    SUMMARY_PROVIDER: ${SUMMARY_PROVIDER:-openai}
    SUMMARY_API_URL: ${SUMMARY_API_URL:?SUMMARY_API_URL required}
    SUMMARY_API_KEY: ${SUMMARY_API_KEY:?SUMMARY_API_KEY required}
    SUMMARY_MODEL: ${SUMMARY_MODEL:-anthropic/claude-sonnet-4}

    # Settings
    CONFIDENCE_THRESHOLD: ${CONFIDENCE_THRESHOLD:-0.6}
    # REMOVE: DIGEST_TARGET_USER (always send to owner)
  volumes:
    - ./logs:/app/logs
  networks:
    - leaknote-net
```

Update `postgres` service to remove Dendrite database:

```yaml
postgres:
  image: postgres:16-alpine
  container_name: leaknote-db
  restart: unless-stopped
  environment:
    POSTGRES_USER: ${POSTGRES_USER:-postgres}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}
    # Database passwords for init-db.sh
    LEAKNOTE_DB_PASSWORD: ${LEAKNOTE_DB_PASSWORD:?LEAKNOTE_DB_PASSWORD required}
    # REMOVE: DENDRITE_DB_PASSWORD
  volumes:
    - ./data/postgres:/var/lib/postgresql/data
    - ./init-db.sh:/docker-entrypoint-initdb.d/01-init-db.sh:ro
    - ./schema.sql:/docker-entrypoint-initdb.d/02-schema.sql:ro
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres"]
    interval: 10s
    timeout: 5s
    retries: 5
  networks:
    - leaknote-net
```

### 3.7 Update Environment Template

**File: `.env.example`**

```bash
# PostgreSQL
POSTGRES_PASSWORD=your_secure_postgres_password
LEAKNOTE_DB_PASSWORD=your_secure_leaknote_password

# Telegram Bot
TELEGRAM_BOT_TOKEN=7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
TELEGRAM_OWNER_ID=123456789
TELEGRAM_INBOX_CHAT_ID=-1001234567890

# LLM - Classification (fast, cheap)
CLASSIFY_PROVIDER=openai
CLASSIFY_API_URL=https://api.openai.com/v1
CLASSIFY_API_KEY=your_openai_api_key
CLASSIFY_MODEL=gpt-4o-mini

# LLM - Summary (quality)
SUMMARY_PROVIDER=openai
SUMMARY_API_URL=https://api.openai.com/v1
SUMMARY_API_KEY=your_openai_api_key
SUMMARY_MODEL=gpt-4o

# Settings
CONFIDENCE_THRESHOLD=0.6

# Admin UI
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_admin_password
```

### 3.8 Update Digest/Review Scripts

**Files: `bot/digest.py`, `bot/weekly_review.py`**

Replace Matrix DM sending with Telegram:

```python
# OLD
from bot.config import Config
from nio import AsyncClient

client = AsyncClient(Config.MATRIX_HOMESERVER, Config.MATRIX_USER_ID)
await client.login(Config.MATRIX_PASSWORD)
await client.room_send(
    room_id=user_room_id,
    message_type="m.room.message",
    content={"msgtype": "m.text", "body": digest_text},
)

# NEW
from telegram import Bot
from bot.config import Config

bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
await bot.send_message(
    chat_id=Config.TELEGRAM_OWNER_ID,
    text=digest_text,
)
```

## Phase 4: Testing Strategy

### 4.1 Unit Testing

Test individual components in isolation:

1. **Config validation**
   ```bash
   # Test with missing vars
   TELEGRAM_BOT_TOKEN="" python -c "from bot.config import Config; print(Config.validate())"
   ```

2. **Command parsing**
   ```bash
   python -c "from bot.commands import parse_command; print(parse_command('?recall git'))"
   ```

3. **Database operations**
   ```bash
   # Test inbox_log insert with Telegram IDs
   ```

### 4.2 Integration Testing

Test bot with Telegram:

1. **Start bot in dev mode**
   ```bash
   docker compose up -d postgres
   docker compose build leaknote
   docker compose run --rm leaknote python bot/main.py
   ```

2. **Test capture flow**
   - Send message to inbox channel
   - Verify classification
   - Check database entry
   - Test fix command
   - Test clarification flow

3. **Test query commands**
   - `?recall git`
   - `?search john`
   - `?projects active`
   - `?ideas`
   - `?admin due`

4. **Test security**
   - Create a second Telegram account
   - Try sending messages
   - Verify bot ignores them

5. **Test digest/review**
   ```bash
   docker compose run --rm leaknote python -m bot.digest
   docker compose run --rm leaknote python -m bot.weekly_review
   ```

### 4.3 Message Length Testing

Test long message handling:

```python
# Test with 10KB message
long_text = "x" * 10000
await bot.send_message(chat_id, long_text)
```

Verify it splits correctly at ~4000 chars.

## Phase 5: Deployment

### 5.1 Database Migration

**Create migration script:**

```sql
-- migration_to_telegram.sql
BEGIN;

-- Backup existing data
CREATE TABLE inbox_log_backup AS SELECT * FROM inbox_log;
CREATE TABLE pending_clarifications_backup AS SELECT * FROM pending_clarifications;

-- Add new columns (allow NULL temporarily)
ALTER TABLE inbox_log
  ADD COLUMN IF NOT EXISTS telegram_message_id TEXT,
  ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT;

ALTER TABLE pending_clarifications
  ADD COLUMN IF NOT EXISTS telegram_message_id TEXT,
  ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT;

-- Drop old columns
ALTER TABLE inbox_log
  DROP COLUMN IF EXISTS matrix_event_id,
  DROP COLUMN IF EXISTS matrix_room_id;

ALTER TABLE pending_clarifications
  DROP COLUMN IF EXISTS matrix_event_id,
  DROP COLUMN IF EXISTS matrix_room_id;

-- Make new columns NOT NULL after adding them
ALTER TABLE inbox_log
  ALTER COLUMN telegram_message_id SET NOT NULL,
  ALTER COLUMN telegram_chat_id SET NOT NULL;

ALTER TABLE pending_clarifications
  ALTER COLUMN telegram_message_id SET NOT NULL,
  ALTER COLUMN telegram_chat_id SET NOT NULL;

-- Update indexes
DROP INDEX IF EXISTS idx_inbox_log_event_id;
CREATE INDEX idx_inbox_log_telegram_message ON inbox_log(telegram_message_id);

DROP INDEX IF EXISTS idx_pending_event_id;
CREATE INDEX idx_pending_telegram_message ON pending_clarifications(telegram_message_id);

COMMIT;
```

**Run migration:**

```bash
# Stop services
docker compose down

# Run migration
docker compose up -d postgres
docker exec -i leaknote-db psql -U postgres -d leaknote < migration_to_telegram.sql

# Verify
docker exec leaknote-db psql -U postgres -d leaknote -c "\d inbox_log"
```

### 5.2 Update Environment

1. Update `.env` with Telegram credentials
2. Remove Matrix variables
3. Remove Dendrite password

### 5.3 Deploy

```bash
# Build and start
docker compose build --no-cache
docker compose up -d

# Verify logs
docker logs -f leaknote-bot

# Test capture
# Send message to Telegram inbox channel
```

### 5.4 Cleanup

After confirming everything works:

```bash
# Remove Dendrite data
rm -rf dendrite/

# Remove backup tables (after a few days)
docker exec leaknote-db psql -U postgres -d leaknote -c "
  DROP TABLE IF EXISTS inbox_log_backup;
  DROP TABLE IF EXISTS pending_clarifications_backup;
"
```

## Phase 6: Documentation Updates

Update these plan files:

1. **`00-overview.md`**
   - Replace Matrix architecture with Telegram
   - Update interface description

2. **`08-deployment.md`** or **`09-docker-deployment.md`**
   - Remove Dendrite setup
   - Add Telegram bot creation steps
   - Update environment variables

3. **`README.md`** (if exists)
   - Update setup instructions
   - Replace Matrix references

## Rollback Plan

If migration fails:

1. **Restore database**
   ```sql
   DROP TABLE inbox_log;
   DROP TABLE pending_clarifications;
   ALTER TABLE inbox_log_backup RENAME TO inbox_log;
   ALTER TABLE pending_clarifications_backup RENAME TO pending_clarifications;
   ```

2. **Restore code**
   ```bash
   git checkout main
   docker compose down
   docker compose up -d
   ```

3. **Keep both systems running**
   - Run Matrix and Telegram bots in parallel
   - Migrate gradually

## Success Criteria

Migration is complete when:

- ✓ Bot responds to Telegram messages in inbox channel
- ✓ Classification and storage works correctly
- ✓ Fix command works
- ✓ Clarification flow works
- ✓ All query commands work (?recall, ?search, etc.)
- ✓ Daily digest sends to Telegram
- ✓ Weekly review sends to Telegram
- ✓ Bot ignores unauthorized users
- ✓ Long messages split correctly
- ✓ No Matrix/Dendrite dependencies remain
- ✓ Docker compose starts with only 3 services (postgres, leaknote, admin)

## Maintenance Notes

**Telegram-specific considerations:**

1. **Bot token security**: Treat like a password, rotate if exposed
2. **Rate limits**: Telegram has rate limits (30 msgs/sec to same chat)
3. **Message format**: Telegram supports Markdown/HTML formatting
4. **File uploads**: Bot can send files up to 50MB
5. **Webhooks vs Polling**: Currently using polling (simpler), can switch to webhooks for production
6. **Bot commands**: Can register commands with BotFather for autocomplete

**Future enhancements:**

1. **Inline keyboards**: For interactive clarification (buttons instead of text)
2. **File attachments**: Support for images, documents in captures
3. **Voice messages**: Transcribe and capture voice memos
4. **Multiple users**: Extend to family/team (requires ACL)
5. **Webhook deployment**: More efficient than polling for production

## Timeline Estimate

- **Phase 1** (Bot Setup): 30 minutes
- **Phase 2-3** (Code Migration): 4-6 hours
- **Phase 4** (Testing): 2-3 hours
- **Phase 5** (Deployment): 1 hour
- **Phase 6** (Documentation): 1 hour

**Total: ~8-12 hours** of focused work

## References

- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [BotFather Commands](https://core.telegram.org/bots/features#botfather)
- [Telegram Bot Security Best Practices](https://core.telegram.org/bots/security)
