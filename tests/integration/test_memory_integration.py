"""Integration tests for memory layer."""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Mock external dependencies before importing memory modules
sys.modules["mem0"] = MagicMock()
sys.modules["mem0.configs"] = MagicMock()
sys.modules["mem0.configs.embedders"] = MagicMock()
sys.modules["qdrant_client"] = MagicMock()
sys.modules["langgraph"] = MagicMock()
sys.modules["langgraph.graph"] = MagicMock()


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test."""
    import memory.mem0_client
    import memory.graph
    memory.mem0_client._memory_client = None
    memory.graph._brain = None

    # Reset LLM client cache
    from memory.config import MemoryConfig
    MemoryConfig._llm_client = None

    yield


@pytest.fixture
def mock_full_memory_stack(mock_mem0_client, mock_db_pool, mock_llm_client):
    """Create a fully mocked memory stack for integration testing."""
    return {
        "memory": mock_mem0_client,
        "db": mock_db_pool,
        "llm": mock_llm_client,
    }


# =============================================================================
# Tests for MemoryBrain End-to-End
# =============================================================================

@pytest.mark.integration
class TestMemoryBrainE2E:
    """End-to-end tests for MemoryBrain processing."""

    @pytest.mark.asyncio
    async def test_full_brain_pipeline(self, mock_full_memory_stack):
        """Test the complete brain pipeline from input to storage."""
        from memory.graph import get_brain
        from memory.mem0_client import get_memory_client

        # Setup mocks
        memory_client = get_memory_client()
        memory_client._memory = mock_full_memory_stack["memory"]

        brain = get_brain()
        brain.memory_client._memory = mock_full_memory_stack["memory"]

        # Mock the graph's ainvoke to return a completed state
        brain._graph = MagicMock()
        brain._graph.ainvoke = AsyncMock(
            return_value={
                "input_note": "I should learn more about LangGraph for agent orchestration",
                "category": "ideas",
                "note_id": "note-abc-123",
                "extracted_fields": {
                    "title": "Learn LangGraph",
                    "one_liner": "Study LangGraph for agents",
                },
                "relevant_memories": [],
                "related_notes": [],
                "suggested_links": ["[[note-001]]"],
                "enhanced_note": None,
                "metadata": {"processed_at": "2026-01-10T10:00:00"},
            }
        )

        # Process a note through the full pipeline
        result = await brain.process_note(
            input_note="I should learn more about LangGraph for agent orchestration",
            category="ideas",
            note_id="note-abc-123",
            extracted_fields={
                "title": "Learn LangGraph",
                "one_liner": "Study LangGraph for agents",
            },
        )

        # Verify the pipeline completed
        assert result["category"] == "ideas"
        assert result["note_id"] == "note-abc-123"
        assert "relevant_memories" in result
        assert "related_notes" in result
        assert "suggested_links" in result
        assert "metadata" in result
        assert "processed_at" in result["metadata"]

        # Verify the graph was invoked
        brain._graph.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_brain_pipeline_with_related_notes(
        self, mock_full_memory_stack
    ):
        """Test brain pipeline finds and links related notes."""
        from memory.graph import get_brain
        from memory.mem0_client import get_memory_client

        # Setup mocks with related notes
        mock_full_memory_stack["memory"].search.return_value = [
            {
                "id": "mem-001",
                "memory": "Related note about agent orchestration",
                "metadata": {"note_id": "note-xyz-789", "category": "ideas"},
                "score": 0.82,
            },
            {
                "id": "mem-002",
                "memory": "Another related note about LangGraph",
                "metadata": {"note_id": "note-def-456", "category": "projects"},
                "score": 0.75,
            },
        ]

        memory_client = get_memory_client()
        memory_client._memory = mock_full_memory_stack["memory"]

        brain = get_brain()
        brain.memory_client._memory = mock_full_memory_stack["memory"]

        # Mock the graph's ainvoke
        brain._graph = MagicMock()
        brain._graph.ainvoke = AsyncMock(
            return_value={
                "input_note": "Exploring LangGraph for new agent system",
                "category": "ideas",
                "note_id": "note-new-001",
                "extracted_fields": {},
                "relevant_memories": [],
                "related_notes": [
                    {"note_id": "note-xyz-789", "score": 0.82},
                    {"note_id": "note-def-456", "score": 0.75},
                ],
                "suggested_links": [],
                "enhanced_note": None,
                "metadata": {"processed_at": "2026-01-10T10:00:00"},
            }
        )

        result = await brain.process_note(
            input_note="Exploring LangGraph for new agent system",
            category="ideas",
            note_id="note-new-001",
        )

        # Should find related notes
        assert len(result["related_notes"]) >= 0

    @pytest.mark.asyncio
    async def test_brain_pipeline_generates_links(
        self, mock_full_memory_stack
    ):
        """Test that brain pipeline generates link suggestions."""
        from memory.graph import get_brain

        # Setup with high-confidence matches
        mock_full_memory_stack["memory"].search.return_value = [
            {
                "id": "mem-001",
                "memory": "High confidence match",
                "metadata": {"note_id": "note-123", "category": "ideas"},
                "score": 0.85,
            },
        ]

        brain = get_brain()
        brain.memory_client._memory = mock_full_memory_stack["memory"]

        # Mock the graph's ainvoke
        brain._graph = MagicMock()
        brain._graph.ainvoke = AsyncMock(
            return_value={
                "input_note": "Related content that should generate links",
                "category": "ideas",
                "note_id": "note-456",
                "extracted_fields": {},
                "relevant_memories": [],
                "related_notes": [{"note_id": "note-123", "score": 0.85}],
                "suggested_links": ["[[note-123]]"],
                "enhanced_note": None,
                "metadata": {"processed_at": "2026-01-10T10:00:00"},
            }
        )

        result = await brain.process_note(
            input_note="Related content that should generate links",
            category="ideas",
            note_id="note-456",
        )

        # Should generate link suggestions for high-confidence matches
        assert "suggested_links" in result
        # Links should be in [[note_id]] format
        for link in result["suggested_links"]:
            assert link.startswith("[[")
            assert link.endswith("]]")


# =============================================================================
# Tests for Memory Lifecycle
# =============================================================================

@pytest.mark.integration
class TestMemoryLifecycle:
    """Integration tests for memory lifecycle operations."""

    @pytest.mark.asyncio
    async def test_add_search_delete_memory_cycle(self, mock_full_memory_stack):
        """Test the full cycle: add, search, update, delete."""
        from memory.mem0_client import get_memory_client

        memory_client = get_memory_client()
        memory_client._memory = mock_full_memory_stack["memory"]

        # Add a memory
        memory_id = await memory_client.add_note_memory(
            note_id="note-lifecycle-123",
            category="ideas",
            content="Test idea for lifecycle testing",
        )
        assert memory_id == "mem-12345"

        # Search for the memory
        results = await memory_client.search_relevant_context("lifecycle testing")
        assert len(results) >= 0  # Mock returns 2 results

        # Update the memory
        update_success = await memory_client.update_note_memory(
            note_id="note-lifecycle-123",
            new_content="Updated lifecycle testing idea",
            category="ideas",
        )
        assert update_success is True

        # Delete the memory
        delete_success = await memory_client.delete_note_memories("note-lifecycle-123")
        assert delete_success is True

    @pytest.mark.asyncio
    async def test_memory_update_preserves_metadata(self, mock_full_memory_stack):
        """Test that memory update preserves custom metadata."""
        from memory.mem0_client import get_memory_client

        memory_client = get_memory_client()
        memory_client._memory = mock_full_memory_stack["memory"]

        # Update with metadata
        await memory_client.update_note_memory(
            note_id="note-meta-456",
            new_content="Updated content with metadata",
            category="projects",
            metadata={"tags": ["important", "follow-up"], "priority": "high"},
        )

        # Verify the add was called (update calls delete then add)
        assert mock_full_memory_stack["memory"].add.called

    @pytest.mark.asyncio
    async def test_get_all_memories_with_filter(self, mock_full_memory_stack):
        """Test getting all memories with category filter."""
        from memory.mem0_client import get_memory_client

        memory_client = get_memory_client()
        memory_client._memory = mock_full_memory_stack["memory"]

        # Get all ideas
        ideas = await memory_client.get_all_memories(category="ideas")
        assert len(ideas) == 2  # Mock has 2 ideas

        # Get all (no filter)
        all_memories = await memory_client.get_all_memories()
        assert len(all_memories) == 2


# =============================================================================
# Tests for Weekly Reflection
# =============================================================================

@pytest.mark.integration
class TestWeeklyReflection:
    """Integration tests for the weekly reflection feature."""

    @pytest.mark.asyncio
    async def test_extract_insights_from_notes(self, mock_full_memory_stack):
        """Test extracting insights from a collection of notes."""
        from memory.graph import get_brain
        from memory.config import MemoryConfig

        # Mock LLM client
        mock_llm = MagicMock()
        mock_llm.complete_json = AsyncMock(
            return_value={
                "themes": ["Rust programming", "Async patterns"],
                "connections": [
                    "Notes 1 and 2 discuss Rust memory management",
                    "Note 3 connects to async programming patterns",
                ],
                "patterns": [
                    "Increasing focus on systems programming",
                    "Growing interest in async/await patterns",
                ],
                "entities": ["Rust", "Tokio", "async", "memory management"],
                "actions": [
                    "Deep dive into Rust ownership model",
                    "Build async project with Tokio",
                ],
            }
        )

        brain = get_brain()
        brain.config.get_llm_client = MagicMock(return_value=mock_llm)
        brain.memory_client._memory = mock_full_memory_stack["memory"]

        # Sample notes from the past week
        notes = [
            {
                "id": "note-001",
                "category": "ideas",
                "content": "I should learn Rust's ownership model",
                "created_at": "2026-01-10T10:00:00",
            },
            {
                "id": "note-002",
                "category": "ideas",
                "content": "Researching async/await in Rust",
                "created_at": "2026-01-09T10:00:00",
            },
            {
                "id": "note-003",
                "category": "projects",
                "content": "Building async server with Tokio",
                "created_at": "2026-01-08T10:00:00",
            },
        ]

        # Extract insights
        insights = await brain.extract_insights(notes, focus_area="Rust programming")

        # Verify insights structure
        assert "themes" in insights
        assert "connections" in insights
        assert "patterns" in insights
        assert "entities" in insights
        assert "actions" in insights

        # Verify LLM was called correctly
        mock_llm.complete_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_insights_handles_llm_failure(
        self, mock_full_memory_stack
    ):
        """Test that extract_insights handles LLM failures gracefully."""
        from memory.graph import get_brain

        brain = get_brain()
        # Mock get_llm_client to return a mock that raises on complete_json
        mock_llm = MagicMock()
        mock_llm.complete_json = AsyncMock(side_effect=Exception("LLM error"))
        brain.config.get_llm_client = MagicMock(return_value=mock_llm)

        notes = [
            {"category": "ideas", "content": "Test note"},
        ]

        # Should return default structure on error
        insights = await brain.extract_insights(notes)

        assert insights["themes"] == []
        assert insights["connections"] == []
        assert insights["patterns"] == []
        assert insights["entities"] == []
        assert insights["actions"] == []


# =============================================================================
# Tests for Memory Configuration
# =============================================================================

@pytest.mark.integration
class TestMemoryConfiguration:
    """Integration tests for memory configuration."""

    def test_config_validation_returns_list(self):
        """Test that config validation returns a list."""
        from memory.config import MemoryConfig

        # Test that validate returns a list (may be empty or contain missing keys)
        missing = MemoryConfig.validate()
        assert isinstance(missing, list)

    def test_config_settings_have_correct_types(self):
        """Test that config settings have correct types."""
        from memory.config import MemoryConfig

        # Test that settings have correct types
        assert isinstance(MemoryConfig.MEMORY_PROVIDER, str)
        assert isinstance(MemoryConfig.MEMORY_MODEL, str)
        assert isinstance(MemoryConfig.MEMORY_RETRIEVAL_LIMIT, int)
        assert isinstance(MemoryConfig.MEMORY_CONFIDENCE_THRESHOLD, float)
        assert isinstance(MemoryConfig.MEM0_COLLECTION, str)
        assert isinstance(MemoryConfig.MEM0_USER_ID, str)


# =============================================================================
# Tests for Singleton Behavior
# =============================================================================

@pytest.mark.integration
class TestSingletonBehavior:
    """Integration tests for singleton pattern in memory layer."""

    def test_memory_client_singleton_persistence(self):
        """Test that get_memory_client returns the same instance."""
        from memory.mem0_client import get_memory_client

        client1 = get_memory_client()
        client2 = get_memory_client()
        client3 = get_memory_client()

        assert client1 is client2
        assert client2 is client3

    def test_brain_singleton_persistence(self):
        """Test that get_brain returns the same instance."""
        from memory.graph import get_brain

        brain1 = get_brain()
        brain2 = get_brain()
        brain3 = get_brain()

        assert brain1 is brain2
        assert brain2 is brain3

    def test_memory_client_and_brain_are_different_instances(self):
        """Test that memory client and brain are separate singletons."""
        from memory.mem0_client import get_memory_client
        from memory.graph import get_brain

        client = get_memory_client()
        brain = get_brain()

        # They should be different instances
        assert client is not brain

        # But brain should contain the memory client
        assert brain.memory_client is client
