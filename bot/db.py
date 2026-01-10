"""Database operations using asyncpg."""

import asyncpg
from typing import Optional, Dict, Any, List
from config import Config

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Get or create the database connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(Config.DATABASE_URL)
    return _pool


async def close_pool():
    """Close the database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def check_health() -> bool:
    """Verify database connection is healthy."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False


# =============================================================================
# Generic CRUD Operations
# =============================================================================


async def insert_record(table: str, data: dict) -> str:
    """Insert a record and return its ID."""
    pool = await get_pool()

    columns = ", ".join(data.keys())
    placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
    values = list(data.values())

    query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"

    async with pool.acquire() as conn:
        record_id = await conn.fetchval(query, *values)
        return str(record_id)


async def update_record(table: str, record_id: str, data: dict) -> bool:
    """Update a record by ID."""
    pool = await get_pool()

    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
    values = [record_id] + list(data.values())

    query = f"UPDATE {table} SET {set_clause}, updated_at = NOW() WHERE id = $1"

    async with pool.acquire() as conn:
        result = await conn.execute(query, *values)
        return result == "UPDATE 1"


async def delete_record(table: str, record_id: str) -> bool:
    """Delete a record by ID."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(f"DELETE FROM {table} WHERE id = $1", record_id)
        return result == "DELETE 1"


async def get_record(table: str, record_id: str) -> Optional[Dict[str, Any]]:
    """Get a record by ID."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(f"SELECT * FROM {table} WHERE id = $1", record_id)
        return dict(row) if row else None


# =============================================================================
# Inbox Log Operations
# =============================================================================


async def insert_inbox_log(
    raw_text: str,
    destination: Optional[str],
    record_id: Optional[str],
    confidence: Optional[float],
    status: str,
    matrix_event_id: str,
    matrix_room_id: str,
) -> str:
    """Log an inbox entry."""
    return await insert_record(
        "inbox_log",
        {
            "raw_text": raw_text,
            "destination": destination,
            "record_id": record_id,
            "confidence": confidence,
            "status": status,
            "matrix_event_id": matrix_event_id,
            "matrix_room_id": matrix_room_id,
        },
    )


async def update_inbox_log(log_id: str, data: dict) -> bool:
    """Update an inbox log entry."""
    pool = await get_pool()

    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
    values = [log_id] + list(data.values())

    query = f"UPDATE inbox_log SET {set_clause} WHERE id = $1"

    async with pool.acquire() as conn:
        result = await conn.execute(query, *values)
        return result == "UPDATE 1"


async def get_inbox_log_by_event(matrix_event_id: str) -> Optional[Dict[str, Any]]:
    """Get inbox log by Matrix event ID."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM inbox_log WHERE matrix_event_id = $1", matrix_event_id
        )
        return dict(row) if row else None


# =============================================================================
# Pending Clarifications
# =============================================================================


async def insert_pending_clarification(
    inbox_log_id: str,
    matrix_event_id: str,
    matrix_room_id: str,
    suggested_category: Optional[str],
) -> str:
    """Create a pending clarification entry."""
    return await insert_record(
        "pending_clarifications",
        {
            "inbox_log_id": inbox_log_id,
            "matrix_event_id": matrix_event_id,
            "matrix_room_id": matrix_room_id,
            "suggested_category": suggested_category,
        },
    )


async def get_pending_by_reply_to(original_event_id: str) -> Optional[Dict[str, Any]]:
    """Get pending clarification by the original event it's replying to."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT pc.*, il.raw_text
            FROM pending_clarifications pc
            JOIN inbox_log il ON pc.inbox_log_id = il.id
            WHERE pc.matrix_event_id = $1
            """,
            original_event_id,
        )
        return dict(row) if row else None


async def delete_pending_clarification(clarification_id: str) -> bool:
    """Delete a pending clarification."""
    return await delete_record("pending_clarifications", clarification_id)


async def cleanup_old_pending(days: int = 7) -> int:
    """Delete pending clarifications older than N days."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            f"DELETE FROM pending_clarifications WHERE created_at < NOW() - INTERVAL '{days} days'"
        )
        return int(result.split()[-1])
