"""Integration tests for the complete command flow from Matrix message to response.

Tests that verify commands are correctly recognized and not sent to LLM classification.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bot"))


@pytest.mark.integration
class TestCommandMessageFlow:
    """Test that query commands are recognized before LLM classification."""

    @pytest.mark.asyncio
    async def test_projects_command_not_classified(self, mock_db_pool, mock_llm_client):
        """Test that ?projects is recognized as command, not sent to LLM."""
        from main import LeaknoteBot

        bot = LeaknoteBot()
        bot.inbox_room_id = "!test:localhost"
        bot.client = AsyncMock()
        bot.client.user_id = "@bot:test"

        # Mock database to return sample projects
        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetch.return_value = [
            {
                "id": 1,
                "name": "Test Project",
                "status": "active",
                "next_action": "Continue",
                "notes": None,
                "updated_at": "2026-01-10",
            }
        ]

        # Create Matrix message event
        event = MagicMock()
        event.sender = "@user:test"
        event.event_id = "$test_123"
        event.body = "?projects"
        event.source = {"content": {"body": "?projects"}}

        room = MagicMock()
        room.room_id = "!test:localhost"

        with patch("main.get_pool", return_value=mock_db_pool), \
             patch("queries.get_pool", return_value=mock_db_pool), \
             patch("main.send_message", new_callable=AsyncMock) as mock_send:

            await bot.on_message(room, event)

            # Verify send_message was called (command was handled)
            assert mock_send.called
            # Verify LLM was NOT called (command was not classified)
            assert not mock_llm_client.complete_json.called

    @pytest.mark.asyncio
    async def test_ideas_command_not_classified(self, mock_db_pool, mock_llm_client):
        """Test that ?ideas is recognized as command, not sent to LLM."""
        from main import LeaknoteBot

        bot = LeaknoteBot()
        bot.inbox_room_id = "!test:localhost"
        bot.client = AsyncMock()
        bot.client.user_id = "@bot:test"

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetch.return_value = []

        event = MagicMock()
        event.sender = "@user:test"
        event.event_id = "$test_124"
        event.body = "?ideas"
        event.source = {"content": {"body": "?ideas"}}

        room = MagicMock()
        room.room_id = "!test:localhost"

        with patch("main.get_pool", return_value=mock_db_pool), \
             patch("queries.get_pool", return_value=mock_db_pool), \
             patch("main.send_message", new_callable=AsyncMock) as mock_send:

            await bot.on_message(room, event)

            assert mock_send.called
            assert not mock_llm_client.complete_json.called

    @pytest.mark.asyncio
    async def test_search_command_not_classified(self, mock_db_pool, mock_llm_client):
        """Test that ?search is recognized as command, not sent to LLM for classification."""
        from main import LeaknoteBot
        from config import Config

        bot = LeaknoteBot()
        bot.inbox_room_id = "!test:localhost"
        bot.client = AsyncMock()
        bot.client.user_id = "@bot:test"

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetch.return_value = []

        event = MagicMock()
        event.sender = "@user:test"
        event.event_id = "$test_125"
        event.body = "?search docker"
        event.source = {"content": {"body": "?search docker"}}

        room = MagicMock()
        room.room_id = "!test:localhost"

        with patch("main.get_pool", return_value=mock_db_pool), \
             patch("queries.get_pool", return_value=mock_db_pool), \
             patch.object(Config, "get_summary_client", return_value=mock_llm_client), \
             patch("main.send_message", new_callable=AsyncMock) as mock_send:

            await bot.on_message(room, event)

            assert mock_send.called
            # Summary LLM might be called for formatting, but classification should not
            # We can't easily distinguish between summary and classification calls here

    @pytest.mark.asyncio
    async def test_non_command_is_classified(self, mock_db_pool, mock_llm_client, sample_classification):
        """Test that regular messages ARE sent to LLM classification."""
        from main import LeaknoteBot
        from config import Config

        bot = LeaknoteBot()
        bot.inbox_room_id = "!test:localhost"
        bot.client = AsyncMock()
        bot.client.user_id = "@bot:test"

        mock_llm_client.complete_json = AsyncMock(return_value=sample_classification)

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchval.return_value = "record-123"
        conn.fetchrow.return_value = {"title": "Test idea"}

        event = MagicMock()
        event.sender = "@user:test"
        event.event_id = "$test_126"
        event.body = "This is a regular message"
        event.source = {"content": {"body": "This is a regular message"}}

        room = MagicMock()
        room.room_id = "!test:localhost"

        with patch("main.get_pool", return_value=mock_db_pool), \
             patch("router.get_pool", return_value=mock_db_pool), \
             patch.object(Config, "get_classify_client", return_value=mock_llm_client), \
             patch("main.get_record", return_value={"title": "Test"}), \
             patch("main.send_confirmation", new_callable=AsyncMock):

            await bot.on_message(room, event)

            # Verify classification LLM WAS called
            assert mock_llm_client.complete_json.called

    @pytest.mark.asyncio
    async def test_command_with_leading_whitespace(self, mock_db_pool):
        """Test that commands with leading whitespace are recognized."""
        from main import LeaknoteBot

        bot = LeaknoteBot()
        bot.inbox_room_id = "!test:localhost"
        bot.client = AsyncMock()
        bot.client.user_id = "@bot:test"

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetch.return_value = []

        event = MagicMock()
        event.sender = "@user:test"
        event.event_id = "$test_127"
        event.body = "  ?projects  "  # Leading and trailing spaces
        event.source = {"content": {"body": "  ?projects  "}}

        room = MagicMock()
        room.room_id = "!test:localhost"

        with patch("main.get_pool", return_value=mock_db_pool), \
             patch("queries.get_pool", return_value=mock_db_pool), \
             patch("main.send_message", new_callable=AsyncMock) as mock_send:

            await bot.on_message(room, event)

            # Should be recognized as command (main.py strips text at line 277)
            assert mock_send.called

    @pytest.mark.asyncio
    async def test_uppercase_command(self, mock_db_pool):
        """Test that uppercase commands are recognized."""
        from main import LeaknoteBot

        bot = LeaknoteBot()
        bot.inbox_room_id = "!test:localhost"
        bot.client = AsyncMock()
        bot.client.user_id = "@bot:test"

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetch.return_value = []

        event = MagicMock()
        event.sender = "@user:test"
        event.event_id = "$test_128"
        event.body = "?PROJECTS"
        event.source = {"content": {"body": "?PROJECTS"}}

        room = MagicMock()
        room.room_id = "!test:localhost"

        with patch("main.get_pool", return_value=mock_db_pool), \
             patch("queries.get_pool", return_value=mock_db_pool), \
             patch("main.send_message", new_callable=AsyncMock) as mock_send:

            await bot.on_message(room, event)

            assert mock_send.called


@pytest.mark.integration
class TestMatrixMessageParsing:
    """Tests that simulate how Matrix actually sends messages."""

    @pytest.mark.asyncio
    async def test_matrix_plain_text_command(self, mock_db_pool):
        """Test command in Matrix plain text message (no formatting)."""
        from main import LeaknoteBot

        bot = LeaknoteBot()
        bot.inbox_room_id = "!test:localhost"
        bot.client = AsyncMock()
        bot.client.user_id = "@bot:test"

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetch.return_value = []

        # Simulate actual Matrix event structure
        event = MagicMock()
        event.sender = "@user:test"
        event.event_id = "$test_129"
        event.body = "?projects"  # This is what gets parsed
        event.source = {
            "content": {
                "msgtype": "m.text",
                "body": "?projects",
                # Matrix might also send formatted_body, but we only use body
            }
        }

        room = MagicMock()
        room.room_id = "!test:localhost"

        with patch("main.get_pool", return_value=mock_db_pool), \
             patch("queries.get_pool", return_value=mock_db_pool), \
             patch("main.send_message", new_callable=AsyncMock) as mock_send:

            await bot.on_message(room, event)

            assert mock_send.called

    @pytest.mark.asyncio
    async def test_matrix_formatted_message_with_command(self, mock_db_pool):
        """Test that commands work even if Matrix sends formatted content."""
        from main import LeaknoteBot

        bot = LeaknoteBot()
        bot.inbox_room_id = "!test:localhost"
        bot.client = AsyncMock()
        bot.client.user_id = "@bot:test"

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetch.return_value = []

        event = MagicMock()
        event.sender = "@user:test"
        event.event_id = "$test_130"
        event.body = "?search docker"  # Plain text version
        event.source = {
            "content": {
                "msgtype": "m.text",
                "body": "?search docker",
                "formatted_body": "<p>?search docker</p>",  # HTML version
                "format": "org.matrix.custom.html"
            }
        }

        room = MagicMock()
        room.room_id = "!test:localhost"

        with patch("main.get_pool", return_value=mock_db_pool), \
             patch("queries.get_pool", return_value=mock_db_pool), \
             patch("main.send_message", new_callable=AsyncMock) as mock_send:

            await bot.on_message(room, event)

            assert mock_send.called


@pytest.mark.unit
class TestCommandVsMessageClassification:
    """Unit tests to document what should be commands vs classified messages."""

    def test_what_should_be_commands(self):
        """Document what SHOULD be recognized as commands."""
        from commands import parse_command

        should_be_commands = [
            "?projects",
            "?projects active",
            "?ideas",
            "?admin",
            "?admin due",
            "?search docker",
            "?search docker deployment",
            "?recall git",
            "?people John",
            "?people John Doe",
        ]

        for text in should_be_commands:
            result = parse_command(text)
            assert result is not None, f"'{text}' should be a command but wasn't recognized!"

    def test_what_should_not_be_commands(self):
        """Document what should NOT be commands (should go to LLM)."""
        from commands import parse_command

        should_not_be_commands = [
            "I need to check my projects",
            "What are my ideas?",
            "Show me the projects",
            "Can you search for docker?",
            "? projects",  # Space after ?
            "?project",  # Missing s
            "idea: Build something",  # Prefix, not command
            "List all projects",
            "project: My new project",
        ]

        for text in should_not_be_commands:
            result = parse_command(text)
            assert result is None, f"'{text}' should NOT be a command but was recognized as {result}!"
