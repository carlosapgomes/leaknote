# Integration Tests - Async Mocking Fix TODO

## Problem

Integration tests fail with: `AttributeError: 'coroutine' object has no attribute '__aenter__'`

**Cause**: The `mock_db_pool` fixture doesn't properly handle async context managers.

## Current Status

- Unit tests: ✅ 98/98 passing
- Integration tests: ❌ 38/40 failing (async mocking issues)

## Fix Option 1: Proper Async Mocking

Update `tests/conftest.py`:

```python
@pytest.fixture
def mock_db_pool():
    """Mock database pool for testing."""
    pool = AsyncMock()
    conn = AsyncMock()
    
    # Properly mock async context manager
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    
    pool.acquire.return_value = mock_context
    
    # Default mock behaviors
    conn.fetchval = AsyncMock(return_value="test-id-123")
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value="INSERT 1")
    
    return pool
```

## Fix Option 2: Use Real Test Database (RECOMMENDED)

Better approach - use actual PostgreSQL or SQLite:

```python
import pytest
import asyncpg
import os

@pytest.fixture
async def test_db_pool():
    """Create a real test database pool."""
    # Use test database
    pool = await asyncpg.create_pool(
        "postgresql://test:test@localhost:5432/leaknote_test"
    )
    
    # Setup: Create tables
    async with pool.acquire() as conn:
        with open("schema.sql") as f:
            await conn.execute(f.read())
    
    yield pool
    
    # Teardown: Clean up
    async with pool.acquire() as conn:
        await conn.execute("DROP SCHEMA public CASCADE")
        await conn.execute("CREATE SCHEMA public")
    
    await pool.close()
```

## Files to Fix

1. `tests/conftest.py` - Update `mock_db_pool` fixture
2. All integration test files - May need minor updates

## Expected Result After Fix

```bash
$ uv run pytest tests/integration/ -v
======================== 40 passed in 2s ========================
```

## Priority

**Medium** - Not blocking deployment, unit tests provide good coverage.
