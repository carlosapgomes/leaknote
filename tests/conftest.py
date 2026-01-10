"""Pytest configuration and fixtures."""

import asyncio
import os
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock
import pytest


# Set test environment variables
os.environ["MATRIX_HOMESERVER"] = "http://test:8008"
os.environ["MATRIX_USER_ID"] = "@bot:test"
os.environ["MATRIX_PASSWORD"] = "test"
os.environ["MATRIX_INBOX_ROOM"] = "#test:localhost"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["CLASSIFY_API_URL"] = "http://test/v1"
os.environ["CLASSIFY_API_KEY"] = "test"
os.environ["CLASSIFY_MODEL"] = "gpt-4o-mini"
os.environ["SUMMARY_API_URL"] = "http://test/v1"
os.environ["SUMMARY_API_KEY"] = "test"
os.environ["SUMMARY_MODEL"] = "claude-sonnet-4"
os.environ["DIGEST_TARGET_USER"] = "@user:test"


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
        "matrix_event_id": "$test_event_123",
        "matrix_room_id": "!test:localhost",
        "created_at": "2026-01-10T10:00:00",
    }


@pytest.fixture
def sample_pending_clarification():
    """Sample pending clarification entry."""
    return {
        "id": 1,
        "inbox_log_id": 1,
        "matrix_event_id": "$clarification_event_123",
        "matrix_room_id": "!test:localhost",
        "suggested_category": "ideas",
        "raw_text": "ambiguous message",
        "created_at": "2026-01-10T10:00:00",
    }


@pytest.fixture
def sample_matrix_event():
    """Sample Matrix message event."""
    event = MagicMock()
    event.sender = "@user:test"
    event.event_id = "$test_event_123"
    event.body = "test message"
    event.source = {
        "content": {
            "body": "test message",
            "msgtype": "m.text",
        }
    }
    return event


@pytest.fixture
def sample_matrix_reply_event():
    """Sample Matrix reply event."""
    event = MagicMock()
    event.sender = "@user:test"
    event.event_id = "$reply_event_123"
    event.body = "> <@user:test> original message\n\nfix: project"
    event.source = {
        "content": {
            "body": "> <@user:test> original message\n\nfix: project",
            "msgtype": "m.text",
            "m.relates_to": {
                "m.in_reply_to": {
                    "event_id": "$test_event_123"
                }
            }
        }
    }
    return event
