"""Integration tests for fix command workflow."""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bot"))


@pytest.mark.integration
class TestFixCommandWorkflow:
    """Integration tests for the complete fix command workflow."""

    @pytest.mark.asyncio
    async def test_fix_idea_to_project(self, mock_db_pool, mock_llm_client):
        """Test fixing a message from idea to project."""
        from fix_handler import handle_fix
        from config import Config

        # Mock inbox log entry
        inbox_log = {
            "id": 1,
            "raw_text": "Build automated tests",
            "destination": "ideas",
            "record_id": "old-record-123",
            "confidence": 0.8,
            "status": "filed",
        }

        # Mock get_inbox_log_by_event to return the log
        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchrow.return_value = inbox_log

        # Mock insert to return new ID
        conn.fetchval.return_value = "new-record-456"

        # Mock delete
        conn.execute.return_value = "DELETE 1"

        with patch("db.get_pool", return_value=mock_db_pool), patch.object(
            Config, "get_classify_client", return_value=mock_llm_client
        ):
            success, msg, old_category, extracted_name = await handle_fix(
                original_event_id="$test_event_123",
                new_category="projects",
            )

            assert success is True
            assert msg == "Fixed"
            assert old_category == "idea"
            assert "Build automated tests" in extracted_name

    @pytest.mark.asyncio
    async def test_fix_project_to_idea(self, mock_db_pool, mock_llm_client):
        """Test fixing a message from project to idea."""
        from fix_handler import handle_fix
        from config import Config

        # Mock inbox log entry
        inbox_log = {
            "id": 1,
            "raw_text": "Random thought about testing",
            "destination": "projects",
            "record_id": "old-record-123",
            "confidence": 0.7,
            "status": "filed",
        }

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchrow.return_value = inbox_log
        conn.fetchval.return_value = "new-record-456"
        conn.execute.return_value = "DELETE 1"

        with patch("db.get_pool", return_value=mock_db_pool), patch.object(
            Config, "get_classify_client", return_value=mock_llm_client
        ):
            success, msg, old_category, extracted_name = await handle_fix(
                original_event_id="$test_event_124",
                new_category="ideas",
            )

            assert success is True
            assert old_category == "project"

    @pytest.mark.asyncio
    async def test_fix_to_decision_category(self, mock_db_pool):
        """Test fixing a message to decision (reference category)."""
        from fix_handler import handle_fix

        inbox_log = {
            "id": 1,
            "raw_text": "Use pytest for testing",
            "destination": "ideas",
            "record_id": "old-record-123",
            "confidence": 0.8,
            "status": "filed",
        }

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchrow.return_value = inbox_log
        conn.fetchval.return_value = "new-record-456"
        conn.execute.return_value = "DELETE 1"

        with patch("db.get_pool", return_value=mock_db_pool):
            success, msg, old_category, extracted_name = await handle_fix(
                original_event_id="$test_event_125",
                new_category="decisions",
            )

            assert success is True
            assert old_category == "idea"

    @pytest.mark.asyncio
    async def test_fix_to_howto_category(self, mock_db_pool):
        """Test fixing a message to howto (reference category)."""
        from fix_handler import handle_fix

        inbox_log = {
            "id": 1,
            "raw_text": "Deploy using docker",
            "destination": "projects",
            "record_id": "old-record-123",
            "confidence": 0.7,
            "status": "filed",
        }

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchrow.return_value = inbox_log
        conn.fetchval.return_value = "new-record-456"
        conn.execute.return_value = "DELETE 1"

        with patch("db.get_pool", return_value=mock_db_pool):
            success, msg, old_category, extracted_name = await handle_fix(
                original_event_id="$test_event_126",
                new_category="howtos",
            )

            assert success is True
            assert old_category == "project"

    @pytest.mark.asyncio
    async def test_fix_to_snippet_category(self, mock_db_pool):
        """Test fixing a message to snippet (reference category)."""
        from fix_handler import handle_fix

        inbox_log = {
            "id": 1,
            "raw_text": "docker ps -a",
            "destination": "admin",
            "record_id": "old-record-123",
            "confidence": 0.6,
            "status": "filed",
        }

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchrow.return_value = inbox_log
        conn.fetchval.return_value = "new-record-456"
        conn.execute.return_value = "DELETE 1"

        with patch("db.get_pool", return_value=mock_db_pool):
            success, msg, old_category, extracted_name = await handle_fix(
                original_event_id="$test_event_127",
                new_category="snippets",
            )

            assert success is True
            assert old_category == "admin"

    @pytest.mark.asyncio
    async def test_fix_same_category(self, mock_db_pool):
        """Test that fixing to same category fails gracefully."""
        from fix_handler import handle_fix

        inbox_log = {
            "id": 1,
            "raw_text": "Test message",
            "destination": "ideas",
            "record_id": "record-123",
            "confidence": 0.8,
            "status": "filed",
        }

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchrow.return_value = inbox_log

        with patch("db.get_pool", return_value=mock_db_pool):
            success, msg, old_category, extracted_name = await handle_fix(
                original_event_id="$test_event_128",
                new_category="ideas",
            )

            assert success is False
            assert "Already filed" in msg
            assert old_category is None

    @pytest.mark.asyncio
    async def test_fix_original_message_not_found(self, mock_db_pool):
        """Test that fix fails when original message not found."""
        from fix_handler import handle_fix

        # Mock no inbox log found
        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchrow.return_value = None

        with patch("db.get_pool", return_value=mock_db_pool):
            success, msg, old_category, extracted_name = await handle_fix(
                original_event_id="$nonexistent_event",
                new_category="projects",
            )

            assert success is False
            assert "Couldn't find" in msg
            assert old_category is None
            assert extracted_name is None

    @pytest.mark.asyncio
    async def test_fix_deletes_old_record(self, mock_db_pool, mock_llm_client):
        """Test that fix deletes the old record."""
        from fix_handler import handle_fix
        from config import Config

        inbox_log = {
            "id": 1,
            "raw_text": "Test message",
            "destination": "ideas",
            "record_id": "old-record-123",
            "confidence": 0.8,
            "status": "filed",
        }

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchrow.return_value = inbox_log
        conn.fetchval.return_value = "new-record-456"
        conn.execute.return_value = "DELETE 1"

        with patch("db.get_pool", return_value=mock_db_pool), patch.object(
            Config, "get_classify_client", return_value=mock_llm_client
        ):
            success, msg, old_category, extracted_name = await handle_fix(
                original_event_id="$test_event_129",
                new_category="projects",
            )

            # Verify delete was called
            # The execute method should be called at least once for delete
            assert conn.execute.called

    @pytest.mark.asyncio
    async def test_fix_updates_inbox_log(self, mock_db_pool, mock_llm_client):
        """Test that fix updates the inbox_log entry."""
        from fix_handler import handle_fix
        from config import Config

        inbox_log = {
            "id": 1,
            "raw_text": "Test message",
            "destination": "ideas",
            "record_id": "old-record-123",
            "confidence": 0.8,
            "status": "filed",
        }

        conn = await mock_db_pool.acquire().__aenter__()
        conn.fetchrow.return_value = inbox_log
        conn.fetchval.return_value = "new-record-456"
        conn.execute.return_value = "UPDATE 1"

        with patch("db.get_pool", return_value=mock_db_pool), patch.object(
            Config, "get_classify_client", return_value=mock_llm_client
        ):
            success, msg, old_category, extracted_name = await handle_fix(
                original_event_id="$test_event_130",
                new_category="projects",
            )

            assert success is True
            # Verify execute was called (for both delete and update)
            assert conn.execute.called
