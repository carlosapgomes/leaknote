# Leaknote Bot Testing Status (2026-01-10)

## ✅ Working

### Core Functionality
- Bot logs into Dendrite Matrix server successfully
- Bot joins `#leaknote-inbox:localhost` (unencrypted room)
- **GPT-4o-mini API integration** (fixed from pt-4o-mini typo)
- **LLM classification with correct schema** (ideas uses `elaboration`, not `notes`)
- Database storage working for all tables
- **Auto-filing high-confidence messages** (>0.6 threshold)
- **Reference prefixes work** for all categories (person:, project:, idea:, admin:, decision:, howto:, snippet:)
- **Comprehensive debug logging** for troubleshooting
- Classification prompt fixed and working (copied directly to container)

### ✅ Fix Command Workflow (FULLY WORKING)
**Status**: Tested and working for all 7 categories

User can reply with `fix:<new-category>` to correct misclassification:
- ✅ **Thread following** - Works when replying to bot's confirmation OR original message
- ✅ **All categories supported**: people, projects, ideas, admin, decisions, howtos, snippets
- ✅ **Correct schema mapping** - Each category uses its proper table schema
- ✅ **Old record deleted** - Message is removed from original table
- ✅ **New record created** - Message is added to target table
- ✅ **inbox_log updated** - destination and record_id are updated
- ✅ **Bot confirmation** - User gets feedback message

**Code Changes** (bot/main.py):
- Added `get_original_event_id()` - Follows reply thread to find original user message
- Added `extract_reply_text()` - Extracts new text from reply, excluding quoted content
- Updated `handle_reply()` - Uses new methods for proper thread handling

**Code Changes** (bot/fix_handler.py):
- Changed from LLM re-classification to prefix-based extraction
- Uses `parse_reference()` with category prefix for correct schema mapping
- Preserves tags from original classification when possible

**Test Commands**:
```bash
# Send a message
uv run matrix-commander --message "need to buy groceries" --room "!9vdNDYik1zgOyFmQ:localhost"

# Wait for filing, then reply to bot's confirmation:
fix: project

# Or reply to your original message:
fix: idea
```

### ✅ Query Commands (FULLY WORKING)
**Status**: All query commands tested and working

| Command | Description | Status |
|---------|-------------|--------|
| `?projects [status]` | List projects by status (active, waiting, blocked, someday, done) | ✅ Working |
| `?ideas` | List all ideas with dates | ✅ Working |
| `?admin [due]` | List admin tasks (optionally only due items) | ✅ Working |
| `?search <term>` | Search all categories with LLM summarization | ✅ Working |
| `?recall <term>` | Search reference categories (howtos, snippets, decisions) | ✅ Working |
| `?people <name>` | Search people | ✅ Working |

**Example Test**:
```bash
# Test projects query
uv run matrix-commander --message "?projects" --room "!9vdNDYik1zgOyFmQ:localhost"

# Test search query
uv run matrix-commander --message "?search docker" --room "!9vdNDYik1zgOyFmQ:localhost"
```

## ⚠️ Needs Testing

### 1. Clarification Workflow (Low Confidence Messages)
**Status**: Code exists but needs end-to-end testing

Note: With "Always choose ONE category. Never refuse." in the prompt, clarification may rarely trigger.

When classification confidence < threshold (0.5-0.6):
- ✅ Bot sends clarification request message (code exists)
- ✅ pending_clarifications row is created (code exists)
- ❓ **User reply to clarification message** - NEEDS TESTING

**Test Case**:
```bash
# 1. Send ambiguous message (should trigger clarification)
uv run matrix-commander --message "xyz" --room "!9vdNDYik1zgOyFmQ:localhost"

# 2. Wait for clarification request from bot
# Check logs:
docker logs leaknote-bot --tail 50 | grep -E "(Creating|Pending|Sent clarification)"

# 3. Check pending_clarifications table
docker exec leaknote-db psql -U leaknote -d leaknote -c "SELECT pc.*, il.raw_text FROM pending_clarifications pc JOIN inbox_log il ON pc.inbox_log_id = il.id;"

# 4. Reply to the clarification message (using matrix-commander)
# Get the clarification event_id from the query above, then:
uv run matrix-commander --message "idea" --room "!9vdNDYik1zgOyFmQ:localhost" --reply-to "$CLARIFICATION_EVENT_ID"

# 5. Verify the message was filed
docker logs leaknote-bot --tail 50 | grep -E "(handle_reply|Filed|elaboration)"

# 6. Verify pending_clarifications was deleted
docker exec leaknote-db psql -U leaknote -d leaknote -c "SELECT COUNT(*) FROM pending_clarifications;"
```

**Expected behavior**:
- Bot should file the message to the ideas table
- pending_clarifications row should be deleted
- inbox_log status should be "filed"
- Bot should confirm to the user

## Recent Fixes (2026-01-10)

### Today's Fixes (Session: Fix Command & Query Testing)

1. **Fix command thread following** (bot/main.py)
   - Added `get_original_event_id()` - Follows reply thread to find original user message
   - Added `extract_reply_text()` - Extracts new text from reply, excluding quoted content
   - Users can now reply to bot's confirmation (intuitive!) OR their original message

2. **Fix command schema mapping** (bot/fix_handler.py)
   - Changed from LLM re-classification to prefix-based extraction
   - Uses `parse_reference()` with category prefix for correct schema mapping
   - Now works for all 7 categories: people, projects, ideas, admin, decisions, howtos, snippets
   - Fixed issue where fix:project would fail with "column due_date does not exist"

3. **Query commands debug logging** (bot/main.py)
   - Added try/except with error logging for command handling
   - Added response logging to verify query outputs

### Earlier Fixes

### Critical Bug Fixes
1. **Model typo fixed** (.env:52): `pt-4o-mini` → `gpt-4o-mini`
   - Was causing 404 errors: "model does not exist"

2. **Classification prompt schema fixed** (prompts/classify.md)
   - Added proper JSON examples for each category (people, projects, ideas, admin)
   - Fixed ideas schema: now uses `elaboration` instead of `notes`
   - Was causing: "column 'notes' of relation 'ideas' does not exist"
   - **Note**: Had to copy file directly to container: `docker cp prompts/classify.md leaknote-bot:/app/prompts/classify.md`

3. **Added debug logging** (bot/main.py:238, bot/router.py)
   - Reply detection: shows `reply_to_id` and event structure
   - Pending clarification creation: logs when rows are created
   - Classification failures: logs errors with context

### Previously Fixed
4. **Reply handler** (bot/main.py:144-168) - accepts category labels without colons
5. **parse_reference() expanded** (bot/classifier.py:50-169) - handles all prefixes
6. **Temperature set to 1.0** for classification (bot/classifier.py:42)

## Current Configuration
- **Classification model**: gpt-4o-mini
- **Temperature**: 1.0
- **Confidence threshold**: 0.6 (ideas), 0.5-0.6 (other categories)
- **Room**: #leaknote-inbox:localhost (unencrypted)

## Test Commands
```bash
# Clear test data
docker exec leaknote-db psql -U leaknote -d leaknote -c "DELETE FROM pending_clarifications; DELETE FROM inbox_log WHERE status = 'needs_review';"

# Copy updated files to container (workaround for Docker build cache)
docker cp /home/carlos/projects/leaknote/bot/main.py leaknote-bot:/app/bot/main.py
docker cp /home/carlos/projects/leaknote/bot/fix_handler.py leaknote-bot:/app/bot/fix_handler.py
docker compose restart leaknote

# Check logs
docker logs leaknote-bot --tail 50

# Check tables
docker exec leaknote-db psql -U leaknote -d leaknote -c "SELECT * FROM projects;"
docker exec leaknote-db psql -U leaknote -d leaknote -c "SELECT * FROM ideas;"
docker exec leaknote-db psql -U leaknote -d leaknote -c "SELECT * FROM inbox_log ORDER BY created_at DESC LIMIT 5;"

# Send test messages with matrix-commander
uv run matrix-commander --message "test message" --room "!9vdNDYik1zgOyFmQ:localhost"
uv run matrix-commander --message "howto: Deploy → Build and push" --room "!9vdNDYik1zgOyFmQ:localhost"
uv run matrix-commander --message "?projects" --room "!9vdNDYik1zgOyFmQ:localhost"
```

## Known Issues
1. **Docker build cache**: When updating bot files, the COPY command may use cache
   - **Workaround**: Copy files directly to container: `docker cp bot/*.py leaknote-bot:/app/bot/`
   - Then restart: `docker compose restart leaknote`

2. **Low confidence messages**: GPT-4o-mini tends to give high confidence (0.5-0.8) even to ambiguous messages
   - Messages like "xyz" get 0.5 confidence
   - May need to adjust threshold or prompt to trigger clarification workflow more often

3. **Manual testing is slow**: Too many moving parts for manual testing
   - **Need**: Automated tests for bot functionality
   - Suggestion: Integration tests that use a test Matrix room

## Next Steps
1. ✅ Test fix command workflow - DONE (all 7 categories working)
2. ✅ Test query commands - DONE (all 6 commands working)
3. ⚠️ Test clarification reply workflow (may rarely trigger with current prompt)
4. ❓ Create automated tests - NEEDED
   - Unit tests for classification, routing, fix handling
   - Integration tests for Matrix message handling
   - End-to-end tests for complete workflows
