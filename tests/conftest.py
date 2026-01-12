"""Pytest configuration and fixtures."""

import asyncio
import os
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock
import pytest


# Set test environment variables for Telegram
os.environ["TELEGRAM_BOT_TOKEN"] = "test_token_12345"
os.environ["TELEGRAM_OWNER_ID"] = "123456789"
os.environ["TELEGRAM_INBOX_CHAT_ID"] = "-1001234567890"  # Optional
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["CLASSIFY_API_URL"] = "http://test/v1"
os.environ["CLASSIFY_API_KEY"] = "test"
os.environ["CLASSIFY_MODEL"] = "gpt-4o-mini"
os.environ["SUMMARY_API_URL"] = "http://test/v1"
os.environ["SUMMARY_API_KEY"] = "test"
os.environ["SUMMARY_MODEL"] = "claude-sonnet-4"

# Memory layer environment variables
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["MEMORY_PROVIDER"] = "openai"
os.environ["MEMORY_API_URL"] = "http://test/v1"
os.environ["MEMORY_API_KEY"] = "test"
os.environ["MEMORY_MODEL"] = "gpt-4o"
os.environ["MEM0_COLLECTION"] = "test_leaknote_memories"
os.environ["MEMORY_RETRIEVAL_LIMIT"] = "5"
os.environ["MEMORY_CONFIDENCE_THRESHOLD"] = "0.7"


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing classification."""
    client = AsyncMock()

    # Create AsyncMocks for complete and complete_json methods
    client.complete_json = AsyncMock(
        return_value={
            "category": "ideas",
            "confidence": 0.8,
            "extracted": {
                "title": "Test idea",
                "one_liner": "A test idea",
                "elaboration": "This is a test idea",
            },
            "tags": ["test"],
        }
    )
    client.complete = AsyncMock(return_value=MagicMock(content="Test response"))
    return client


@pytest.fixture
def mock_db_pool():
    """Mock database pool for testing."""
    pool = MagicMock()
    conn = AsyncMock()

    # Properly mock async context manager
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    pool.acquire = MagicMock(return_value=mock_context)

    # Default mock behaviors
    conn.fetchval = AsyncMock(return_value="test-id-123")
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value="INSERT 1")

    return pool


@pytest.fixture
def sample_classification():
    """Sample classification result for testing."""
    return {
        "category": "ideas",
        "confidence": 0.8,
        "extracted": {
            "title": "Test idea",
            "one_liner": "A test idea",
            "elaboration": "This is a test idea for testing",
        },
        "tags": ["test", "automation"],
    }


@pytest.fixture
def sample_project_classification():
    """Sample project classification result."""
    return {
        "category": "projects",
        "confidence": 0.9,
        "extracted": {
            "name": "Test project",
            "status": "active",
            "next_action": "Write tests",
            "notes": "Project for testing",
        },
        "tags": ["testing"],
    }


@pytest.fixture
def sample_inbox_log():
    """Sample inbox log entry."""
    return {
        "id": 1,
        "raw_text": "This is a test message",
        "destination": "ideas",
        "record_id": "test-record-123",
        "confidence": 0.8,
        "status": "filed",
        "telegram_message_id": "123",
        "telegram_chat_id": "-1001234567890",
        "created_at": "2026-01-10T10:00:00",
    }


@pytest.fixture
def sample_pending_clarification():
    """Sample pending clarification entry."""
    return {
        "id": 1,
        "inbox_log_id": 1,
        "telegram_message_id": "456",
        "telegram_chat_id": "-1001234567890",
        "suggested_category": "ideas",
        "raw_text": "ambiguous message",
        "created_at": "2026-01-10T10:00:00",
    }


@pytest.fixture
def sample_telegram_message():
    """Sample Telegram message update."""
    update = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.username = "testuser"
    update.message.message_id = 123
    update.message.chat_id = -1001234567890
    update.message.text = "test message"
    update.message.reply_to_message = None
    return update


@pytest.fixture
def sample_telegram_dm():
    """Sample Telegram DM update (private chat)."""
    update = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.username = "testuser"
    update.message.message_id = 456
    update.message.chat_id = 123456789  # DM chat ID equals user ID
    update.message.text = "decision: This is a test decision"
    update.message.reply_to_message = None
    return update


@pytest.fixture
def mock_mem0_client():
    """Mock Mem0 Memory client for testing."""
    memory = MagicMock()

    # Mock add method to return a memory ID
    memory.add = MagicMock(return_value="mem-12345")

    # Mock search method to return relevant memories
    memory.search = MagicMock(return_value=[
        {
            "id": "mem-001",
            "memory": "Test memory about Rust programming",
            "metadata": {
                "note_id": "note-123",
                "category": "ideas",
                "created_at": "2026-01-10T10:00:00",
            },
            "score": 0.85,
        },
        {
            "id": "mem-002",
            "memory": "Related memory about async programming",
            "metadata": {
                "note_id": "note-456",
                "category": "ideas",
                "created_at": "2026-01-09T10:00:00",
            },
            "score": 0.72,
        },
    ])

    # Mock get_all method
    memory.get_all = MagicMock(return_value=[
        {
            "id": "mem-001",
            "memory": "Test memory about Rust programming",
            "metadata": {
                "note_id": "note-123",
                "category": "ideas",
                "created_at": "2026-01-10T10:00:00",
            },
        },
        {
            "id": "mem-002",
            "memory": "Related memory about async programming",
            "metadata": {
                "note_id": "note-456",
                "category": "ideas",
                "created_at": "2026-01-09T10:00:00",
            },
        },
    ])

    # Mock delete method
    memory.delete = MagicMock(return_value=True)

    return memory


@pytest.fixture
def sample_memory_result():
    """Sample memory search result for testing."""
    return [
        {
            "memory": "User is researching Rust memory management",
            "metadata": {
                "note_id": "note-123",
                "category": "ideas",
                "created_at": "2026-01-10T10:00:00",
            },
            "score": 0.85,
        },
        {
            "memory": "LangGraph is used for agent orchestration",
            "metadata": {
                "note_id": "note-456",
                "category": "projects",
                "created_at": "2026-01-09T10:00:00",
            },
            "score": 0.72,
        },
    ]


@pytest.fixture
def sample_related_notes():
    """Sample related notes result for testing."""
    return [
        {
            "note_id": "note-123",
            "category": "ideas",
            "memory": "User is researching Rust memory management",
            "score": 0.85,
        },
        {
            "note_id": "note-456",
            "category": "projects",
            "memory": "LangGraph is used for agent orchestration",
            "score": 0.72,
        },
    ]


@pytest.fixture
def sample_brain_state():
    """Sample BrainState for testing."""
    return {
        "input_note": "Test note about LangGraph integration",
        "category": "ideas",
        "note_id": "note-789",
        "extracted_fields": {
            "title": "LangGraph Integration",
            "one_liner": "Integrate LangGraph for memory processing",
        },
        "relevant_memories": [],
        "related_notes": [],
        "suggested_links": [],
        "enhanced_note": None,
        "metadata": {"processed_at": "2026-01-10T10:00:00"},
    }
