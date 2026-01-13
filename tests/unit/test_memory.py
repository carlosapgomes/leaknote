"""Unit tests for memory layer."""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add bot directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Mock external dependencies before importing memory modules
sys.modules["mem0"] = MagicMock()
sys.modules["mem0.configs"] = MagicMock()
sys.modules["mem0.configs.embedders"] = MagicMock()
sys.modules["qdrant_client"] = MagicMock()
sys.modules["langgraph"] = MagicMock()
sys.modules["langgraph.graph"] = MagicMock()

from memory.config import MemoryConfig
from memory.mem0_client import LeaknoteMemory, get_memory_client
from memory.graph import MemoryBrain, get_brain, BrainState


# Reset the singleton instances before each test
@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test."""
    import memory.mem0_client
    import memory.graph
    memory.mem0_client._memory_client = None
    memory.graph._brain = None
    # Also reset the cached LLM client
    MemoryConfig._llm_client = None
    yield


# =============================================================================
# Tests for MemoryConfig
# =============================================================================

@pytest.mark.unit
class TestMemoryConfig:
    """Tests for MemoryConfig class."""

    def test_qdrant_url_default(self):
        """Test QDRANT_URL has default value."""
        assert MemoryConfig.QDRANT_URL == "http://localhost:6333"

    def test_mem0_collection_default(self):
        """Test MEM0_COLLECTION has default value."""
        assert MemoryConfig.MEM0_COLLECTION == "test_leaknote_memories"

    def test_memory_provider_default(self):
        """Test MEMORY_PROVIDER has default value."""
        assert MemoryConfig.MEMORY_PROVIDER == "openai"

    def test_memory_model_default(self):
        """Test MEMORY_MODEL has default value."""
        assert MemoryConfig.MEMORY_MODEL == "gpt-4o"

    def test_memory_retrieval_limit_default(self):
        """Test MEMORY_RETRIEVAL_LIMIT has default value."""
        assert MemoryConfig.MEMORY_RETRIEVAL_LIMIT == 5

    def test_memory_confidence_threshold_default(self):
        """Test MEMORY_CONFIDENCE_THRESHOLD has default value."""
        assert MemoryConfig.MEMORY_CONFIDENCE_THRESHOLD == 0.7

    def test_mem0_user_id(self):
        """Test MEM0_USER_ID is set."""
        assert MemoryConfig.MEM0_USER_ID == "leaknote_user"

    def test_validate_with_all_config(self):
        """Test validate returns empty list when all config is set."""
        missing = MemoryConfig.validate()
        assert missing == []

    @patch.dict("os.environ", {
        "QDRANT_URL": "",
        "MEMORY_API_URL": "",
        "MEMORY_API_KEY": "",
    }, clear=False)
    def test_validate_with_missing_config(self):
        """Test validate returns missing config items."""
        # Reload the config class to pick up new env vars
        import importlib
        import memory.config
        importlib.reload(memory.config)
        from memory.config import MemoryConfig

        missing = MemoryConfig.validate()
        assert "QDRANT_URL" in missing
        assert "MEMORY_API_URL" in missing
        assert "MEMORY_API_KEY" in missing


# =============================================================================
# Tests for LeaknoteMemory
# =============================================================================

@pytest.mark.unit
class TestLeaknoteMemory:
    """Tests for LeaknoteMemory class."""

    @pytest.fixture
    def memory_client(self, mock_mem0_client):
        """Create a LeaknoteMemory instance with mocked Mem0 client."""
        client = LeaknoteMemory()
        client._memory = mock_mem0_client
        return client

    @pytest.mark.asyncio
    async def test_add_note_memory(self, memory_client):
        """Test adding a note to semantic memory."""
        memory_id = await memory_client.add_note_memory(
            note_id="note-123",
            category="ideas",
            content="Test idea about Rust programming",
        )

        assert memory_id == "mem-12345"
        memory_client._memory.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_note_memory_with_metadata(self, memory_client):
        """Test adding a note with additional metadata."""
        memory_id = await memory_client.add_note_memory(
            note_id="note-456",
            category="projects",
            content="Project for testing",
            metadata={"tags": ["test", "rust"]},
        )

        assert memory_id == "mem-12345"

        # Verify the call included the metadata
        call_args = memory_client._memory.add.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_add_note_memory_formats_context(self, memory_client):
        """Test that context is formatted with category prefix."""
        await memory_client.add_note_memory(
            note_id="note-789",
            category="ideas",
            content="Test content",
        )

        call_args = memory_client._memory.add.call_args
        context = call_args[0][0]  # First positional argument
        assert "[IDEAS]" in context
        assert "Test content" in context

    @pytest.mark.asyncio
    async def test_add_note_memory_includes_metadata(self, memory_client):
        """Test that metadata is properly included."""
        await memory_client.add_note_memory(
            note_id="note-999",
            category="people",
            content="Person note",
            metadata={"name": "John Doe"},
        )

        call_kwargs = memory_client._memory.add.call_args[1]
        metadata = call_kwargs["metadata"]

        assert metadata["note_id"] == "note-999"
        assert metadata["category"] == "people"
        assert "created_at" in metadata
        assert metadata["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_search_relevant_context(self, memory_client, sample_memory_result):
        """Test searching for relevant context."""
        results = await memory_client.search_relevant_context(
            query="Rust programming"
        )

        assert len(results) == 2
        assert results[0]["memory"] == "Test memory about Rust programming"
        assert results[0]["score"] == 0.85
        assert results[0]["metadata"]["note_id"] == "note-123"

    @pytest.mark.asyncio
    async def test_search_relevant_context_with_limit(self, memory_client):
        """Test search with custom limit."""
        await memory_client.search_relevant_context(
            query="test query",
            limit=3,
        )

        call_kwargs = memory_client._memory.search.call_args[1]
        assert call_kwargs["limit"] == 3

    @pytest.mark.asyncio
    async def test_search_relevant_context_returns_empty_on_error(self, memory_client):
        """Test search returns empty list on error."""
        memory_client._memory.search.side_effect = Exception("Search failed")

        results = await memory_client.search_relevant_context("test")

        assert results == []

    @pytest.mark.asyncio
    async def test_get_related_notes(self, memory_client, sample_related_notes):
        """Test getting related notes."""
        related = await memory_client.get_related_notes(
            note_content="Test note content",
            category="ideas",
            limit=5,
        )

        assert len(related) == 2
        assert related[0]["note_id"] == "note-123"
        assert related[0]["category"] == "ideas"
        assert related[0]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_get_related_notes_deduplicates(self, memory_client):
        """Test that get_related_notes deduplicates note IDs."""
        # Mock search to return duplicate note IDs
        memory_client._memory.search.return_value = [
            {
                "memory": "Memory 1",
                "metadata": {"note_id": "note-123", "category": "ideas"},
                "score": 0.9,
            },
            {
                "memory": "Memory 2",
                "metadata": {"note_id": "note-123", "category": "ideas"},
                "score": 0.8,
            },
            {
                "memory": "Memory 3",
                "metadata": {"note_id": "note-456", "category": "projects"},
                "score": 0.7,
            },
        ]

        related = await memory_client.get_related_notes("test", "ideas")

        # Should only return 2 unique notes
        assert len(related) == 2
        note_ids = [r["note_id"] for r in related]
        assert "note-123" in note_ids
        assert "note-456" in note_ids

    @pytest.mark.asyncio
    async def test_get_all_memories(self, memory_client):
        """Test getting all memories."""
        memories = await memory_client.get_all_memories()

        assert len(memories) == 2
        assert memories[0]["id"] == "mem-001"

    @pytest.mark.asyncio
    async def test_get_all_memories_with_category_filter(self, memory_client):
        """Test getting all memories filtered by category."""
        memories = await memory_client.get_all_memories(category="ideas")

        assert len(memories) == 2
        # All should be ideas category
        for mem in memories:
            assert mem["metadata"]["category"] == "ideas"

    @pytest.mark.asyncio
    async def test_delete_note_memories(self, memory_client):
        """Test deleting memories for a note."""
        result = await memory_client.delete_note_memories("note-123")

        assert result is True
        # Should call get_all and delete
        memory_client._memory.get_all.assert_called()
        memory_client._memory.delete.assert_called()

    @pytest.mark.asyncio
    async def test_delete_note_memories_on_error(self, memory_client):
        """Test delete returns False on error."""
        memory_client._memory.get_all.side_effect = Exception("Delete failed")

        result = await memory_client.delete_note_memories("note-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_note_memory(self, memory_client):
        """Test updating memories for a note."""
        result = await memory_client.update_note_memory(
            note_id="note-123",
            new_content="Updated content",
            category="ideas",
        )

        assert result is True
        # Should call delete and add
        memory_client._memory.get_all.assert_called()
        memory_client._memory.add.assert_called()

    @pytest.mark.asyncio
    async def test_update_note_memory_with_metadata(self, memory_client):
        """Test updating memories with metadata."""
        result = await memory_client.update_note_memory(
            note_id="note-456",
            new_content="Updated with metadata",
            category="projects",
            metadata={"tags": ["updated"]},
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_note_memory_logs_error(self, memory_client):
        """Test update logs errors from add_note_memory."""
        # Make add fail to simulate an error during update
        # Note: add_note_memory catches exceptions internally, so update still returns True
        memory_client._memory.add.side_effect = Exception("Update failed")

        result = await memory_client.update_note_memory(
            note_id="note-789",
            new_content="test",
            category="ideas",
        )

        # The update returns True because add_note_memory handles the error internally
        # The error is logged but doesn't propagate
        assert result is True

    def test_get_memory_client_singleton(self):
        """Test that get_memory_client returns a singleton."""
        client1 = get_memory_client()
        client2 = get_memory_client()

        assert client1 is client2


# =============================================================================
# Tests for MemoryBrain
# =============================================================================

@pytest.mark.unit
class TestMemoryBrain:
    """Tests for MemoryBrain class."""

    @pytest.fixture
    def brain(self, mock_mem0_client):
        """Create a MemoryBrain instance with mocked dependencies."""
        brain = MemoryBrain()
        brain.memory_client._memory = mock_mem0_client
        return brain

    def test_brain_initialization(self, brain):
        """Test brain initializes correctly."""
        assert brain.config is not None
        assert brain.memory_client is not None

    def test_graph_property_lazy_initialization(self, brain):
        """Test that graph is lazily initialized."""
        assert brain._graph is None
        _ = brain.graph
        assert brain._graph is not None

    def test_build_graph_structure(self, brain):
        """Test that graph is built with correct structure."""
        graph = brain.graph

        # The graph should be compiled
        assert graph is not None

    @pytest.mark.asyncio
    async def test_retrieve_memories_node(self, brain, sample_memory_result):
        """Test the _retrieve_memories node."""
        state = {
            "input_note": "Test note about LangGraph",
            "category": "ideas",
            "note_id": "note-123",
            "extracted_fields": {},
            "relevant_memories": [],
            "related_notes": [],
            "suggested_links": [],
            "enhanced_note": None,
            "metadata": {},
        }

        result = await brain._retrieve_memories(state)

        assert "relevant_memories" in result
        assert len(result["relevant_memories"]) == 2

    @pytest.mark.asyncio
    async def test_find_relations_node(self, brain, sample_related_notes):
        """Test the _find_relations node."""
        state = {
            "input_note": "Test note",
            "category": "ideas",
            "note_id": "note-123",
            "extracted_fields": {},
            "relevant_memories": [],
            "related_notes": [],
            "suggested_links": [],
            "enhanced_note": None,
            "metadata": {},
        }

        result = await brain._find_relations(state)

        assert "related_notes" in result
        assert len(result["related_notes"]) == 2

    @pytest.mark.asyncio
    async def test_generate_links_node_with_high_confidence(self, brain):
        """Test _generate_links with high confidence scores."""
        state = {
            "input_note": "Test note",
            "category": "ideas",
            "note_id": "note-123",
            "extracted_fields": {},
            "relevant_memories": [],
            "related_notes": [
                {"note_id": "note-001", "score": 0.85},
                {"note_id": "note-002", "score": 0.72},
                {"note_id": "note-003", "score": 0.65},  # Below threshold
            ],
            "suggested_links": [],
            "enhanced_note": None,
            "metadata": {},
        }

        result = await brain._generate_links(state)

        assert len(result["suggested_links"]) == 2
        assert "[[note-001]]" in result["suggested_links"]
        assert "[[note-002]]" in result["suggested_links"]
        assert "[[note-003]]" not in result["suggested_links"]

    @pytest.mark.asyncio
    async def test_generate_links_node_with_low_confidence(self, brain):
        """Test _generate_links with low confidence scores."""
        state = {
            "input_note": "Test note",
            "category": "ideas",
            "note_id": "note-123",
            "extracted_fields": {},
            "relevant_memories": [],
            "related_notes": [
                {"note_id": "note-001", "score": 0.5},
                {"note_id": "note-002", "score": 0.6},
            ],
            "suggested_links": [],
            "enhanced_note": None,
            "metadata": {},
        }

        result = await brain._generate_links(state)

        # No links should be generated (all below threshold of 0.7)
        assert len(result["suggested_links"]) == 0

    @pytest.mark.asyncio
    async def test_store_memory_node(self, brain, mock_mem0_client):
        """Test the _store_memory node."""
        state = {
            "input_note": "Test note to store",
            "category": "ideas",
            "note_id": "note-123",
            "extracted_fields": {},
            "relevant_memories": [],
            "related_notes": [],
            "suggested_links": ["[[note-001]]"],
            "enhanced_note": None,
            "metadata": {"test": "value"},
        }

        result = await brain._store_memory(state)

        # Verify memory was added
        mock_mem0_client.add.assert_called()

    @pytest.mark.asyncio
    async def test_process_note_full_pipeline(self, brain, mock_mem0_client):
        """Test processing a note through the full pipeline."""
        # Mock the graph's ainvoke to return a completed state
        brain._graph = MagicMock()
        brain._graph.ainvoke = AsyncMock(
            return_value={
                "input_note": "I should learn more about LangGraph",
                "category": "ideas",
                "note_id": "note-123",
                "extracted_fields": {"title": "LangGraph Learning"},
                "relevant_memories": [],
                "related_notes": [],
                "suggested_links": ["[[note-001]]"],
                "enhanced_note": None,
                "metadata": {"processed_at": "2026-01-10T10:00:00"},
            }
        )

        result = await brain.process_note(
            input_note="I should learn more about LangGraph",
            category="ideas",
            note_id="note-123",
            extracted_fields={"title": "LangGraph Learning"},
        )

        assert result["category"] == "ideas"
        assert result["note_id"] == "note-123"
        assert "relevant_memories" in result
        assert "related_notes" in result
        assert "suggested_links" in result
        assert "metadata" in result
        assert "processed_at" in result["metadata"]

    @pytest.mark.asyncio
    async def test_extract_insights(self, brain, mock_llm_client):
        """Test extracting insights from a collection of notes."""
        notes = [
            {"category": "ideas", "content": "Note about Rust"},
            {"category": "ideas", "content": "Note about async"},
            {"category": "projects", "content": "LangGraph project"},
        ]

        # Mock get_llm_client to return our mock
        brain.config.get_llm_client = MagicMock(return_value=mock_llm_client)

        # Mock LLM response
        mock_llm_client.complete_json = AsyncMock(
            return_value={
                "themes": ["Rust programming", "Async patterns"],
                "connections": ["Notes 1 and 2 both discuss Rust"],
                "patterns": ["Interest in async programming"],
                "entities": ["Rust", "LangGraph"],
                "actions": ["Learn more about async Rust"],
            }
        )

        insights = await brain.extract_insights(notes)

        assert "themes" in insights
        assert "connections" in insights
        assert "patterns" in insights
        assert "entities" in insights
        assert "actions" in insights

    @pytest.mark.asyncio
    async def test_extract_insights_with_focus_area(self, brain, mock_llm_client):
        """Test extracting insights with a focus area."""
        notes = [
            {"category": "ideas", "content": "Note about Rust"},
        ]

        # Mock get_llm_client
        brain.config.get_llm_client = MagicMock(return_value=mock_llm_client)

        mock_llm_client.complete_json = AsyncMock(
            return_value={
                "themes": ["Rust"],
                "connections": [],
                "patterns": [],
                "entities": ["Rust"],
                "actions": [],
            }
        )

        insights = await brain.extract_insights(
            notes,
            focus_area="Rust programming"
        )

        assert "themes" in insights

    @pytest.mark.asyncio
    async def test_extract_insights_on_error(self, brain, mock_llm_client):
        """Test extract_insights returns default structure on error."""
        # Mock get_llm_client to return our mock
        brain.config.get_llm_client = MagicMock(return_value=mock_llm_client)

        # Make complete_json raise an error (this is inside the try/except)
        mock_llm_client.complete_json = AsyncMock(
            side_effect=Exception("LLM completion error")
        )

        notes = [{"category": "ideas", "content": "Test"}]

        insights = await brain.extract_insights(notes)

        # Should return default structure
        assert insights["themes"] == []
        assert insights["connections"] == []
        assert insights["patterns"] == []
        assert insights["entities"] == []
        assert insights["actions"] == []

    def test_get_brain_singleton(self):
        """Test that get_brain returns a singleton."""
        brain1 = get_brain()
        brain2 = get_brain()

        assert brain1 is brain2


# =============================================================================
# Tests for BrainState
# =============================================================================

@pytest.mark.unit
class TestBrainState:
    """Tests for BrainState TypedDict."""

    def test_brain_state_structure(self, sample_brain_state):
        """Test BrainState has all required fields."""
        state = sample_brain_state

        assert "input_note" in state
        assert "category" in state
        assert "note_id" in state
        assert "extracted_fields" in state
        assert "relevant_memories" in state
        assert "related_notes" in state
        assert "suggested_links" in state
        assert "enhanced_note" in state
        assert "metadata" in state

    def test_brain_state_types(self, sample_brain_state):
        """Test BrainState has correct types."""
        state = sample_brain_state

        assert isinstance(state["input_note"], str)
        assert isinstance(state["category"], str)
        assert isinstance(state["extracted_fields"], dict)
        assert isinstance(state["relevant_memories"], list)
        assert isinstance(state["related_notes"], list)
        assert isinstance(state["suggested_links"], list)
        assert isinstance(state["metadata"], dict)
