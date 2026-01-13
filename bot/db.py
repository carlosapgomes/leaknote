"""Database operations using asyncpg."""

import asyncpg
from typing import Optional, Dict, Any, List
from datetime import date, datetime
from bot.config import Config

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

    # Convert date strings to date objects
    converted_data = {}
    for key, value in data.items():
        if key in ("due_date", "last_touched") and isinstance(value, str):
            # Parse ISO date string to date object
            try:
                converted_data[key] = datetime.fromisoformat(value).date()
            except (ValueError, AttributeError):
                # If parsing fails, skip this field
                continue
        else:
            converted_data[key] = value

    columns = ", ".join(converted_data.keys())
    placeholders = ", ".join(f"${i+1}" for i in range(len(converted_data)))
    values = list(converted_data.values())

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


async def record_exists(table: str, record_id: str) -> bool:
    """Check if a record exists by ID."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.fetchval(
            f"SELECT 1 FROM {table} WHERE id = $1", record_id
        )
        return result is not None


# =============================================================================
# Inbox Log Operations
# =============================================================================


async def insert_inbox_log(
    raw_text: str,
    destination: Optional[str],
    record_id: Optional[str],
    confidence: Optional[float],
    status: str,
    telegram_message_id: str,
    telegram_chat_id: str,
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
            "telegram_message_id": telegram_message_id,
            "telegram_chat_id": telegram_chat_id,
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


async def get_inbox_log_by_event(telegram_message_id: str) -> Optional[Dict[str, Any]]:
    """Get inbox log by Telegram message ID."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM inbox_log WHERE telegram_message_id = $1", telegram_message_id
        )
        return dict(row) if row else None


# =============================================================================
# Pending Clarifications
# =============================================================================


async def insert_pending_clarification(
    inbox_log_id: str,
    telegram_message_id: str,
    telegram_chat_id: str,
    suggested_category: Optional[str],
) -> str:
    """Create a pending clarification entry."""
    return await insert_record(
        "pending_clarifications",
        {
            "inbox_log_id": inbox_log_id,
            "telegram_message_id": telegram_message_id,
            "telegram_chat_id": telegram_chat_id,
            "suggested_category": suggested_category,
        },
    )


async def get_pending_by_reply_to(original_message_id: str) -> Optional[Dict[str, Any]]:
    """Get pending clarification by the original message it's replying to."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT pc.*, il.raw_text
            FROM pending_clarifications pc
            JOIN inbox_log il ON pc.inbox_log_id = il.id
            WHERE pc.telegram_message_id = $1
            """,
            original_message_id,
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
