"""Integration tests for message routing."""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bot"))


@pytest.mark.integration
class TestMessageRouting:
    """Integration tests for the complete message routing workflow."""

    @pytest.mark.asyncio
    async def test_route_message_with_idea_prefix(self, mock_db_pool):
        """Test routing a message with idea: prefix."""
        from router import route_message

        with patch("db.get_pool", return_value=mock_db_pool):
            category, record_id, confidence, status = await route_message(
                text="idea: Build automated test suite",
                telegram_message_id="$test_event_123",
                telegram_chat_id="!test:localhost",
            )

            assert category == "ideas"
            assert record_id == "test-id-123"
            assert confidence == 1.0
            assert status == "filed"

            # Verify insert_record was called
            conn = await mock_db_pool.acquire().__aenter__()
            assert conn.fetchval.called

    @pytest.mark.asyncio
    async def test_route_message_with_project_prefix(self, mock_db_pool):
        """Test routing a message with project: prefix."""
        from router import route_message

        with patch("db.get_pool", return_value=mock_db_pool):
            category, record_id, confidence, status = await route_message(
                text="project: Test automation framework",
                telegram_message_id="$test_event_124",
                telegram_chat_id="!test:localhost",
            )

            assert category == "projects"
            assert record_id == "test-id-123"
            assert confidence == 1.0
            assert status == "filed"

    @pytest.mark.asyncio
    async def test_route_message_with_person_prefix(self, mock_db_pool):
        """Test routing a message with person: prefix."""
        from router import route_message

        with patch("db.get_pool", return_value=mock_db_pool):
            category, record_id, confidence, status = await route_message(
                text="person: John Doe - engineer at Acme",
                telegram_message_id="$test_event_125",
                telegram_chat_id="!test:localhost",
            )

            assert category == "people"
            assert record_id == "test-id-123"
            assert confidence == 1.0
            assert status == "filed"

    @pytest.mark.asyncio
    async def test_route_message_with_howto_prefix(self, mock_db_pool):
        """Test routing a message with howto: prefix."""
        from router import route_message

        with patch("db.get_pool", return_value=mock_db_pool):
            category, record_id, confidence, status = await route_message(
                text="howto: Deploy → docker build && docker push",
                telegram_message_id="$test_event_126",
                telegram_chat_id="!test:localhost",
            )

            assert category == "howtos"
            assert record_id == "test-id-123"
            assert confidence == 1.0
            assert status == "filed"

    @pytest.mark.asyncio
    async def test_route_message_with_snippet_prefix(self, mock_db_pool):
        """Test routing a message with snippet: prefix."""
        from router import route_message

        with patch("db.get_pool", return_value=mock_db_pool):
            category, record_id, confidence, status = await route_message(
                text="snippet: Git rebase → git rebase -i HEAD~3",
                telegram_message_id="$test_event_127",
                telegram_chat_id="!test:localhost",
            )

            assert category == "snippets"
            assert record_id == "test-id-123"
            assert confidence == 1.0
            assert status == "filed"

    @pytest.mark.asyncio
    async def test_route_message_with_decision_prefix(self, mock_db_pool):
        """Test routing a message with decision: prefix."""
        from router import route_message

        with patch("db.get_pool", return_value=mock_db_pool):
            category, record_id, confidence, status = await route_message(
                text="decision: Use pytest because it has great async support",
                telegram_message_id="$test_event_128",
                telegram_chat_id="!test:localhost",
            )

            assert category == "decisions"
            assert record_id == "test-id-123"
            assert confidence == 1.0
            assert status == "filed"

    @pytest.mark.asyncio
    async def test_route_message_with_admin_prefix(self, mock_db_pool):
        """Test routing a message with admin: prefix."""
        from router import route_message

        with patch("db.get_pool", return_value=mock_db_pool):
            category, record_id, confidence, status = await route_message(
                text="admin: File taxes by April 15",
                telegram_message_id="$test_event_129",
                telegram_chat_id="!test:localhost",
            )

            assert category == "admin"
            assert record_id == "test-id-123"
            assert confidence == 1.0
            assert status == "filed"

    @pytest.mark.asyncio
    async def test_route_message_with_llm_classification_high_confidence(
        self, mock_db_pool, mock_llm_client, sample_classification
    ):
        """Test routing with LLM classification (high confidence)."""
        from router import route_message
        from config import Config

        # Mock high-confidence classification
        mock_llm_client.complete_json = AsyncMock(return_value=sample_classification)

        with patch("db.get_pool", return_value=mock_db_pool), patch.object(
            Config, "get_classify_client", return_value=mock_llm_client
        ):
            category, record_id, confidence, status = await route_message(
                text="I should build automated tests",
                telegram_message_id="$test_event_130",
                telegram_chat_id="!test:localhost",
            )

            assert category == "ideas"
            assert record_id == "test-id-123"
            assert confidence == 0.8
            assert status == "filed"

    @pytest.mark.asyncio
    async def test_route_message_with_llm_classification_low_confidence(
        self, mock_db_pool, mock_llm_client
    ):
        """Test routing with LLM classification (low confidence - needs review)."""
        from router import route_message
        from config import Config

        # Mock low-confidence classification
        low_confidence_result = {
            "category": "ideas",
            "confidence": 0.3,  # Below threshold
            "extracted": {
                "title": "Ambiguous message",
                "one_liner": "Not sure what this is",
                "elaboration": "xyz",
            },
            "tags": [],
        }
        mock_llm_client.complete_json = AsyncMock(return_value=low_confidence_result)

        with patch("db.get_pool", return_value=mock_db_pool), patch.object(
            Config, "get_classify_client", return_value=mock_llm_client
        ):
            category, record_id, confidence, status = await route_message(
                text="xyz",
                telegram_message_id="$test_event_131",
                telegram_chat_id="!test:localhost",
            )

            assert category == "ideas"
            assert record_id is None
            assert confidence == 0.3
            assert status == "needs_review"

    @pytest.mark.asyncio
    async def test_route_message_llm_failure(self, mock_db_pool, mock_llm_client):
        """Test routing when LLM classification fails."""
        from router import route_message
        from config import Config

        # Mock LLM failure
        mock_llm_client.complete_json = AsyncMock(
            side_effect=Exception("API error")
        )

        with patch("db.get_pool", return_value=mock_db_pool), patch.object(
            Config, "get_classify_client", return_value=mock_llm_client
        ):
            category, record_id, confidence, status = await route_message(
                text="Test message",
                telegram_message_id="$test_event_132",
                telegram_chat_id="!test:localhost",
            )

            assert category is None
            assert record_id is None
            assert confidence is None
            assert status == "needs_review"

    @pytest.mark.asyncio
    async def test_route_message_unknown_category_from_llm(
        self, mock_db_pool, mock_llm_client
    ):
        """Test routing when LLM returns unknown category."""
        from router import route_message
        from config import Config

        # Mock unknown category
        unknown_category_result = {
            "category": "unknown_category",
            "confidence": 0.9,
            "extracted": {},
            "tags": [],
        }
        mock_llm_client.complete_json = AsyncMock(return_value=unknown_category_result)

        with patch("db.get_pool", return_value=mock_db_pool), patch.object(
            Config, "get_classify_client", return_value=mock_llm_client
        ):
            category, record_id, confidence, status = await route_message(
                text="Test message",
                telegram_message_id="$test_event_133",
                telegram_chat_id="!test:localhost",
            )

            assert category is None
            assert record_id is None
            assert confidence == 0.9
            assert status == "needs_review"
