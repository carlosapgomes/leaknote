# Test Refactoring Strategy for Telegram Migration

## Overview

During the Matrix → Telegram migration, several integration tests were skipped because they tested Matrix-specific architecture and patterns that no longer exist in the Telegram bot. This document provides strategic guidance for refactoring these tests.

## Skipped Tests

The following integration test files were marked with `@pytest.mark.skip`:

1. **`test_clarification.py`** - Tests clarification workflow and reply handling
2. **`test_fix_handler.py`** - Tests the `fix:` command functionality
3. **`test_command_flow.py`** - Tests command recognition and message flow
4. **`test_query_commands.py`** - Tests query command execution

## Architectural Changes

### Matrix Bot (Old)
```python
# Event-based architecture from matrix-nio
client = nio.AsyncClient(homeserver, user, password)
event.event_id = "$event_id"
event.room_id = "!room:server"
event.sender = "@user:server"
event.body = "message text"

# Room-based messaging
await client.room_send(room_id, content)
```

### Telegram Bot (New)
```python
# Update-based architecture from python-telegram-bot
update.effective_user.id = 123456789
update.message.message_id = 123
update.effective_chat.id = -1001234567890  # Channel or DM
update.message.text = "message text"

# Direct messaging with bot.send_message()
await bot.send_message(chat_id, text, reply_to_message_id=msg_id)
```

## Key Differences to Address

### 1. Message ID vs Event ID
- **Matrix**: Used string event IDs (`$event_id`)
- **Telegram**: Uses integer message IDs

### 2. Room vs Chat
- **Matrix**: Messages belong to rooms with `room_id`
- **Telegram**: Messages belong to chats with `chat_id` (negative for channels/groups)

### 3. Reply Structure
- **Matrix**: Replies use `m.relates_to.m.in_reply_to.event_id` in event source
- **Telegram**: Replies use `message.reply_to_message.message_id`

### 4. Client Methods
- **Matrix**: `client.room_send(room_id, content, reply_to_event_id)`
- **Telegram**: `bot.send_message(chat_id, text, reply_to_message_id)`

### 5. Message Structure
- **Matrix**: Event objects with nested `source` dictionary
- **Telegram**: Update objects with `message` attribute

## Refactoring Strategy

### Phase 1: Update Test Fixtures

**File**: `tests/conftest.py`

The fixtures have been updated, but verify these patterns:

```python
@pytest.fixture
def sample_telegram_update():
    """Sample Telegram Update object."""
    update = MagicMock()
    update.effective_user.id = 123456789
    update.message.message_id = 123
    update.effective_chat.id = -1001234567890  # Channel
    update.message.text = "test message"
    update.message.reply_to_message = None
    return update

@pytest.fixture
def sample_telegram_reply():
    """Sample Telegram reply update."""
    update = MagicMock()
    update.message.reply_to_message = MagicMock()
    update.message.reply_to_message.message_id = 122
    update.message.reply_to_message.from_user.is_bot = True
    return update
```

### Phase 2: Rewrite `test_clarification.py`

**Priority**: HIGH - Core user-facing workflow

**Changes Needed**:

1. **Remove Matrix-specific mocks**:
   ```python
   # OLD
   bot.client = AsyncMock()
   bot.client.room_send = AsyncMock()
   event = MagicMock()
   event.event_id = "$event_id"

   # NEW
   context.bot.send_message = AsyncMock()
   update.message.message_id = 123
   ```

2. **Update test methods** to match new bot structure:
   - `handle_reply()` is now in `LeaknoteBot` class
   - Takes `Update` and `Context` objects (not `room`, `event`)
   - Uses Telegram message IDs

3. **Test scenarios to cover**:
   - Low confidence → clarification request
   - Reply with category prefix (`idea:`, `decision:`, etc.)
   - Reply with `skip`
   - Reply with new text

**Example Pattern**:
```python
@pytest.mark.asyncio
async def test_clarification_reply_with_category(
    self, mock_db_pool, mock_llm_client
):
    """Test replying to clarification with category prefix."""
    from telegram import Update
    from bot.main import LeaknoteBot

    bot = LeaknoteBot()

    # Mock the update
    update = MagicMock(spec=Update)
    update.effective_user.id = 123456789
    update.message.message_id = 123
    update.message.text = "idea: clarified text"
    update.message.reply_to_message = MagicMock()
    update.message.reply_to_message.message_id = 456
    update.message.reply_to_message.from_user.is_bot = True

    # Mock context
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    # Mock database
    with patch("bot.db.get_pool", return_value=mock_db_pool):
        await bot.handle_reply(update, context)

    # Verify response
    assert context.bot.send_message.called
```

### Phase 3: Rewrite `test_fix_handler.py`

**Priority**: MEDIUM - Important feature but simpler flow

**Changes Needed**:

1. **Fix command parsing** works the same (tests may just need fixture updates)

2. **Update to test through main bot flow**:
   - `handle_fix_command()` method in `LeaknoteBot`
   - Uses `get_inbox_log_by_event(telegram_message_id)`
   - Calls `handle_fix()` from fix_handler module

3. **Test scenarios**:
   - Valid fix: `fix: project`
   - Invalid category: `fix: notacategory`
   - Message not found

### Phase 4: Rewrite `test_command_flow.py`

**Priority**: HIGH - Critical for command recognition

**Changes Needed**:

1. **Update to test main bot flow**:
   ```python
   # OLD: Direct Matrix event handling
   await bot.handle_message(room, event)

   # NEW: Telegram Update handling
   await bot.handle_message(update, context)
   ```

2. **Test scenarios**:
   - Commands recognized before LLM classification
   - `?projects`, `?ideas`, `?admin` etc.
   - Non-command messages go to LLM

3. **Mock strategy**:
   - Mock `parse_command()` to return command info
   - Mock `handle_command()` from commands module
   - Verify LLM classification is NOT called for commands

### Phase 5: Rewrite `test_query_commands.py`

**Priority**: LOW - Already covered partially by unit tests

**Changes Needed**:

1. **Test the actual query execution** through bot

2. **Test scenarios**:
   - `?recall query`
   - `?search query`
   - `?people query`
   - Results returned and formatted

## Mocking Strategy

### Mocking Telegram Updates

```python
from telegram import Update, Message, User, Chat

def create_mock_update(user_id=123456789, chat_id=-1001234567890, text="test"):
    """Create a mock Telegram Update."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = user_id
    update.message = MagicMock(spec=Message)
    update.message.message_id = 123
    update.message.text = text
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.id = chat_id
    return update
```

### Mocking Bot Context

```python
def create_mock_context():
    """Create a mock Telegram Context."""
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.bot.edit_message_text = AsyncMock()
    return context
```

### Mocking Reply Chains

```python
def create_mock_reply(original_msg_id=122, reply_text="fix: idea"):
    """Create a mock reply update."""
    update = create_mock_update()
    update.message.reply_to_message = MagicMock()
    update.message.reply_to_message.message_id = original_msg_id
    update.message.reply_to_message.from_user.is_bot = True
    update.message.text = reply_text
    return update
```

## Testing Patterns

### Pattern 1: Message Flow Test

```python
@pytest.mark.asyncio
async def test_message_to_classification_to_response(self):
    """Test complete flow: message → classify → respond."""
    from bot.main import LeaknoteBot

    bot = LeaknoteBot()
    update = create_mock_update(text="idea: test idea")
    context = create_mock_context()

    with patch("bot.router.route_message") as mock_route:
        mock_route.return_value = ("ideas", "id123", 1.0, "filed")

        await bot.handle_capture(update, context)

        # Verify confirmation sent
        context.bot.send_message.assert_called_once()
```

### Pattern 2: Database Interaction Test

```python
@pytest.mark.asyncio
async def test_clarification_creates_pending(self, mock_db_pool):
    """Test that low confidence creates pending clarification."""
    conn = await mock_db_pool.acquire().__aenter__()
    conn.fetchval.return_value = "log-id-123"

    from bot.router import route_message

    category, record_id, confidence, status = await route_message(
        text="unclear message",
        telegram_message_id="123",
        telegram_chat_id="-1001234567890"
    )

    assert status == "needs_review"
    assert record_id is None
```

## Priority Order

1. **FIRST**: `test_routing.py` ✅ (Already done - just parameter updates)
2. **SECOND**: `test_command_flow.py` - Commands are critical
3. **THIRD**: `test_clarification.py` - Core workflow
4. **FOURTH**: `test_fix_handler.py` - Important but simpler
5. **LAST**: `test_query_commands.py` - Less critical

## Common Pitfalls

### 1. Wrong Mock Type
```python
# WRONG - Using old Matrix mocks
event = MagicMock()
event.event_id = "$id"

# CORRECT - Using Telegram Update
update = MagicMock(spec=Update)
update.message.message_id = 123
```

### 2. Forgetting AsyncMock
```python
# WRONG
context.bot.send_message = MagicMock()

# CORRECT
context.bot.send_message = AsyncMock()
```

### 3. Not Specifying Mock Spec
```python
# WRONG - Too permissive
update = MagicMock()

# BETTER - More restrictive
update = MagicMock(spec=Update)
```

## Running Tests

### Run Updated Tests
```bash
# Unit tests (should pass)
docker compose run --rm leaknote pytest tests/unit/ -v

# Routing tests (should pass)
docker compose run --rm leaknote pytest tests/integration/test_routing.py -v

# All tests (skipped ones show as SKIPPED)
docker compose run --rm leaknote pytest tests/ -v
```

### Run Specific Test
```bash
docker compose run --rm leaknote pytest tests/integration/test_command_flow.py::TestCommandMessageFlow::test_projects_command_not_classified -v
```

## Success Criteria

A test is successfully refactored when:

1. ✅ Uses `Update` and `Context` objects (not Matrix events)
2. ✅ Mocks `telegram_message_id` and `telegram_chat_id`
3. ✅ Tests the actual bot methods from `bot/main.py`
4. ✅ Uses `AsyncMock` for async bot methods
5. ✅ Tests realistic Telegram scenarios
6. ✅ Passes with `pytest -v`
7. ✅ No longer has `@pytest.mark.skip` decorator

## Resources

- **python-telegram-bot docs**: https://docs.python-telegram-bot.org/
- **Current bot implementation**: `bot/main.py` - See `LeaknoteBot` class
- **Example Update structure**: Check telegram library's Update class
- **Existing working tests**: `tests/unit/test_classifier.py` - Good reference patterns

## Notes

- The unit tests in `tests/unit/` should still work as they test business logic
- Focus on integration tests that test the bot's message handling
- Keep tests simple and focused - don't over-mock
- Test behavior, not implementation details
- Consider adding E2E tests with a real test bot token for critical flows
