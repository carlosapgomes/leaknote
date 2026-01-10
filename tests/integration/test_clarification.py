"""Integration tests for clarification workflow."""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bot"))


@pytest.mark.integration
class TestClarificationWorkflow:
    """Integration tests for the clarification workflow."""

    @pytest.mark.asyncio
    async def test_clarification_reply_with_category_prefix(
        self, mock_db_pool, mock_llm_client, sample_pending_clarification
    ):
        """Test replying to clarification with category prefix."""
        from main import LeaknoteBot
        from config import Config

        # Setup
        bot = LeaknoteBot()
        bot.inbox_room_id = "!test:localhost"

        # Mock pending clarification exists
        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchrow.return_value = sample_pending_clarification
        conn.fetchval.return_value = "new-record-123"
        conn.execute.return_value = "DELETE 1"

        # Mock Matrix client
        bot.client = AsyncMock()
        bot.client.user_id = "@bot:test"
        bot.client.send_message = AsyncMock()

        # Create mock event
        event = MagicMock()
        event.sender = "@user:test"
        event.event_id = "$reply_event_123"
        event.body = "> <@bot:test> Can you clarify?\n\nidea"
        event.source = {
            "content": {
                "body": "> <@bot:test> Can you clarify?\n\nidea",
                "m.relates_to": {
                    "m.in_reply_to": {
                        "event_id": "$clarification_event_123"
                    }
                }
            }
        }

        room = MagicMock()
        room.room_id = "!test:localhost"

        with patch("main.get_pool", return_value=mock_db_pool), \
             patch("router.get_pool", return_value=mock_db_pool), \
             patch.object(Config, "get_classify_client", return_value=mock_llm_client), \
             patch("main.get_pending_by_reply_to", return_value=sample_pending_clarification), \
             patch("main.delete_pending_clarification", return_value=True):

            reply_to_id = "$clarification_event_123"
            await bot.handle_reply(room, event, reply_to_id)

            # Verify bot sent a confirmation
            assert bot.client.send_message.called or bot.client.room_send.called

    @pytest.mark.asyncio
    async def test_clarification_reply_with_skip(
        self, mock_db_pool, sample_pending_clarification
    ):
        """Test replying to clarification with 'skip'."""
        from main import LeaknoteBot

        bot = LeaknoteBot()
        bot.inbox_room_id = "!test:localhost"

        # Mock database
        conn = await mock_db_pool.acquire().__aenter__()
        conn.execute.return_value = "DELETE 1"

        # Mock Matrix client
        bot.client = AsyncMock()
        bot.client.user_id = "@bot:test"
        bot.client.send_message = AsyncMock()

        # Create mock event for skip
        event = MagicMock()
        event.sender = "@user:test"
        event.event_id = "$reply_event_124"
        event.body = "> <@bot:test> Can you clarify?\n\nskip"
        event.source = {
            "content": {
                "body": "> <@bot:test> Can you clarify?\n\nskip",
                "m.relates_to": {
                    "m.in_reply_to": {
                        "event_id": "$clarification_event_123"
                    }
                }
            }
        }

        room = MagicMock()
        room.room_id = "!test:localhost"

        with patch("main.get_pool", return_value=mock_db_pool), \
             patch("main.get_pending_by_reply_to", return_value=sample_pending_clarification), \
             patch("main.delete_pending_clarification", return_value=True):

            reply_to_id = "$clarification_event_123"
            await bot.handle_reply(room, event, reply_to_id)

            # Verify bot sent a skip confirmation
            assert bot.client.send_message.called or bot.client.room_send.called

    @pytest.mark.asyncio
    async def test_clarification_reply_with_new_text(
        self, mock_db_pool, mock_llm_client, sample_pending_clarification, sample_classification
    ):
        """Test replying to clarification with completely new text."""
        from main import LeaknoteBot
        from config import Config

        bot = LeaknoteBot()
        bot.inbox_room_id = "!test:localhost"

        # Mock database
        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchrow.return_value = sample_pending_clarification
        conn.fetchval.return_value = "new-record-123"
        conn.execute.return_value = "DELETE 1"

        # Mock Matrix client
        bot.client = AsyncMock()
        bot.client.user_id = "@bot:test"
        bot.client.send_message = AsyncMock()

        # Mock LLM to return successful classification
        mock_llm_client.complete_json = AsyncMock(return_value=sample_classification)

        # Create mock event with new text
        event = MagicMock()
        event.sender = "@user:test"
        event.event_id = "$reply_event_125"
        event.body = "> <@bot:test> Can you clarify?\n\nThis is a better description of my idea"
        event.source = {
            "content": {
                "body": "> <@bot:test> Can you clarify?\n\nThis is a better description of my idea",
                "m.relates_to": {
                    "m.in_reply_to": {
                        "event_id": "$clarification_event_123"
                    }
                }
            }
        }

        room = MagicMock()
        room.room_id = "!test:localhost"

        with patch("main.get_pool", return_value=mock_db_pool), \
             patch("router.get_pool", return_value=mock_db_pool), \
             patch.object(Config, "get_classify_client", return_value=mock_llm_client), \
             patch("main.get_pending_by_reply_to", return_value=sample_pending_clarification), \
             patch("main.delete_pending_clarification", return_value=True), \
             patch("main.get_record", return_value={"title": "Test idea"}):

            reply_to_id = "$clarification_event_123"
            await bot.handle_reply(room, event, reply_to_id)

            # Verify bot sent a response
            assert bot.client.send_message.called or bot.client.room_send.called

    @pytest.mark.asyncio
    async def test_extract_reply_text_removes_quotes(self):
        """Test that extract_reply_text removes quoted content."""
        from main import LeaknoteBot

        bot = LeaknoteBot()

        # Create mock event with quoted reply
        event = MagicMock()
        event.body = "> <@user:test> Original message\n> Line 2\n\nNew reply text"

        extracted = bot.extract_reply_text(event)

        assert extracted == "New reply text"
        assert "> <@user:test>" not in extracted
        assert "Original message" not in extracted

    @pytest.mark.asyncio
    async def test_extract_reply_text_multiline_reply(self):
        """Test extracting multi-line reply text."""
        from main import LeaknoteBot

        bot = LeaknoteBot()

        event = MagicMock()
        event.body = "> <@user:test> Original\n\nLine 1\nLine 2\nLine 3"

        extracted = bot.extract_reply_text(event)

        assert "Line 1" in extracted
        assert "Line 2" in extracted
        assert "Line 3" in extracted
        assert "> <@user:test>" not in extracted

    @pytest.mark.asyncio
    async def test_clarification_created_for_low_confidence(
        self, mock_db_pool, mock_llm_client
    ):
        """Test that clarification is created when confidence is low."""
        from router import route_message
        from config import Config

        # Mock low-confidence classification
        low_confidence = {
            "category": "ideas",
            "confidence": 0.3,
            "extracted": {
                "title": "Unclear",
                "one_liner": "Not sure",
                "elaboration": "Ambiguous message",
            },
            "tags": [],
        }
        mock_llm_client.complete_json = AsyncMock(return_value=low_confidence)

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchval.return_value = "inbox-log-123"

        with patch("router.get_pool", return_value=mock_db_pool), \
             patch.object(Config, "get_classify_client", return_value=mock_llm_client):

            category, record_id, confidence, status = await route_message(
                text="unclear message",
                matrix_event_id="$test_event_200",
                matrix_room_id="!test:localhost",
            )

            assert status == "needs_review"
            assert confidence == 0.3
            assert record_id is None

    @pytest.mark.asyncio
    async def test_clarification_not_created_for_high_confidence(
        self, mock_db_pool, mock_llm_client, sample_classification
    ):
        """Test that clarification is NOT created when confidence is high."""
        from router import route_message
        from config import Config

        mock_llm_client.complete_json = AsyncMock(return_value=sample_classification)

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchval.return_value = "record-123"

        with patch("router.get_pool", return_value=mock_db_pool), \
             patch.object(Config, "get_classify_client", return_value=mock_llm_client):

            category, record_id, confidence, status = await route_message(
                text="clear idea message",
                matrix_event_id="$test_event_201",
                matrix_room_id="!test:localhost",
            )

            assert status == "filed"
            assert confidence == 0.8
            assert record_id is not None

    @pytest.mark.asyncio
    async def test_get_original_event_id_follows_thread(self, mock_db_pool):
        """Test that get_original_event_id follows reply thread."""
        from main import LeaknoteBot

        bot = LeaknoteBot()
        bot.client = AsyncMock()
        bot.client.user_id = "@bot:test"

        # Mock inbox log lookup
        inbox_log = {
            "id": 1,
            "matrix_event_id": "$original_user_message",
        }
        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchrow.return_value = inbox_log

        # Mock room_get_event to return bot's message that replies to user's message
        bot_message_event = MagicMock()
        bot_message_event.source = {
            "sender": "@bot:test",
            "content": {
                "m.relates_to": {
                    "m.in_reply_to": {
                        "event_id": "$original_user_message"
                    }
                }
            }
        }
        bot_message_event.event = bot_message_event

        response = MagicMock()
        response.event = bot_message_event
        bot.client.room_get_event = AsyncMock(return_value=response)

        with patch("main.get_inbox_log_by_event") as mock_get_inbox:
            # First call returns None (not the original), second call returns the log
            mock_get_inbox.side_effect = [None, inbox_log]

            result = await bot.get_original_event_id("$bot_confirmation_message", "!test:localhost")

            assert result == "$original_user_message"
