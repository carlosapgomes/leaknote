"""Database queries for digests, reviews, and search."""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from bot.db import get_pool


# =============================================================================
# Project Queries
# =============================================================================


async def get_active_projects(limit: int = 10) -> List[Dict[str, Any]]:
    """Get active projects with next actions."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, status, next_action, notes, tags, updated_at
            FROM projects
            WHERE status = 'active'
            ORDER BY updated_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(row) for row in rows]


async def get_waiting_projects() -> List[Dict[str, Any]]:
    """Get projects in waiting status."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, status, next_action, notes, updated_at
            FROM projects
            WHERE status = 'waiting'
            ORDER BY updated_at DESC
            """
        )
        return [dict(row) for row in rows]


async def get_blocked_projects() -> List[Dict[str, Any]]:
    """Get blocked projects."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, status, next_action, notes, updated_at
            FROM projects
            WHERE status = 'blocked'
            ORDER BY updated_at DESC
            """
        )
        return [dict(row) for row in rows]


async def list_projects(status: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """List projects, optionally filtered by status."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                """
                SELECT id, name, status, next_action, notes, updated_at
                FROM projects
                WHERE status = $1
                ORDER BY updated_at DESC
                LIMIT $2
                """,
                status,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, name, status, next_action, notes, updated_at
                FROM projects
                ORDER BY
                    CASE status
                        WHEN 'active' THEN 1
                        WHEN 'waiting' THEN 2
                        WHEN 'blocked' THEN 3
                        WHEN 'someday' THEN 4
                        ELSE 5
                    END,
                    updated_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [dict(row) for row in rows]


# =============================================================================
# Admin Queries
# =============================================================================


async def get_admin_due_soon(days: int = 7) -> List[Dict[str, Any]]:
    """Get admin tasks due within N days."""
    pool = await get_pool()
    cutoff = datetime.now().date() + timedelta(days=days)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, due_date, status, notes
            FROM admin
            WHERE status = 'pending'
              AND due_date IS NOT NULL
              AND due_date <= $1
            ORDER BY due_date ASC
            """,
            cutoff,
        )
        return [dict(row) for row in rows]


async def get_overdue_admin() -> List[Dict[str, Any]]:
    """Get overdue admin tasks."""
    pool = await get_pool()
    today = datetime.now().date()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, due_date, status, notes
            FROM admin
            WHERE status = 'pending'
              AND due_date IS NOT NULL
              AND due_date < $1
            ORDER BY due_date ASC
            """,
            today,
        )
        return [dict(row) for row in rows]


async def list_admin(due_only: bool = False, limit: int = 20) -> List[Dict[str, Any]]:
    """List admin tasks."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        if due_only:
            rows = await conn.fetch(
                """
                SELECT id, name, due_date, status, notes
                FROM admin
                WHERE status = 'pending' AND due_date IS NOT NULL
                ORDER BY due_date ASC
                LIMIT $1
                """,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, name, due_date, status, notes
                FROM admin
                WHERE status = 'pending'
                ORDER BY
                    CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                    due_date ASC
                LIMIT $1
                """,
                limit,
            )
        return [dict(row) for row in rows]


# =============================================================================
# People Queries
# =============================================================================


async def get_people_with_followups() -> List[Dict[str, Any]]:
    """Get people who have follow-up notes."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, context, follow_ups, last_touched
            FROM people
            WHERE follow_ups IS NOT NULL
              AND follow_ups != ''
            ORDER BY last_touched DESC
            """
        )
        return [dict(row) for row in rows]


# =============================================================================
# Ideas Queries
# =============================================================================


async def get_recent_ideas(days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
    """Get ideas captured in the last N days."""
    pool = await get_pool()
    cutoff = datetime.now() - timedelta(days=days)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, one_liner, created_at
            FROM ideas
            WHERE created_at >= $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            cutoff,
            limit,
        )
        return [dict(row) for row in rows]


async def list_ideas(limit: int = 20) -> List[Dict[str, Any]]:
    """List recent ideas."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, one_liner, created_at
            FROM ideas
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(row) for row in rows]


# =============================================================================
# Decisions Queries
# =============================================================================


async def get_recent_decisions(days: int = 7, limit: int = 5) -> List[Dict[str, Any]]:
    """Get decisions made in the last N days."""
    pool = await get_pool()
    cutoff = datetime.now() - timedelta(days=days)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, decision, rationale, created_at
            FROM decisions
            WHERE created_at >= $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            cutoff,
            limit,
        )
        return [dict(row) for row in rows]


# =============================================================================
# Inbox Stats
# =============================================================================


async def get_inbox_stats(days: int = 7) -> Dict[str, int]:
    """Get inbox statistics for the last N days."""
    pool = await get_pool()
    cutoff = datetime.now() - timedelta(days=days)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'filed') as filed,
                COUNT(*) FILTER (WHERE status = 'needs_review') as needs_review,
                COUNT(*) FILTER (WHERE status = 'fixed') as fixed
            FROM inbox_log
            WHERE created_at >= $1
            """,
            cutoff,
        )
        return dict(row)


# =============================================================================
# Full-Text Search
# =============================================================================


async def search_full_text(
    query: str,
    tables: List[str],
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Full-text search across specified tables.
    Returns results with table name and relevance score.
    """
    pool = await get_pool()

    table_configs = {
        "people": {
            "search_columns": "name || ' ' || COALESCE(context, '') || ' ' || COALESCE(follow_ups, '')",
            "display_columns": "id, name, context, follow_ups, last_touched",
        },
        "projects": {
            "search_columns": "name || ' ' || COALESCE(next_action, '') || ' ' || COALESCE(notes, '')",
            "display_columns": "id, name, status, next_action, notes, updated_at",
        },
        "ideas": {
            "search_columns": "title || ' ' || COALESCE(one_liner, '') || ' ' || COALESCE(elaboration, '')",
            "display_columns": "id, title, one_liner, elaboration, created_at",
        },
        "admin": {
            "search_columns": "name || ' ' || COALESCE(notes, '')",
            "display_columns": "id, name, due_date, status, notes, created_at",
        },
        "decisions": {
            "search_columns": "title || ' ' || decision || ' ' || COALESCE(rationale, '') || ' ' || COALESCE(context, '')",
            "display_columns": "id, title, decision, rationale, context, created_at",
        },
        "howtos": {
            "search_columns": "title || ' ' || content",
            "display_columns": "id, title, content, created_at",
        },
        "snippets": {
            "search_columns": "title || ' ' || content",
            "display_columns": "id, title, content, created_at",
        },
    }

    results = []

    async with pool.acquire() as conn:
        for table in tables:
            if table not in table_configs:
                continue

            config = table_configs[table]

            sql = f"""
                SELECT
                    '{table}' as source_table,
                    {config['display_columns']},
                    ts_rank(
                        to_tsvector('english', {config['search_columns']}),
                        plainto_tsquery('english', $1)
                    ) as rank
                FROM {table}
                WHERE to_tsvector('english', {config['search_columns']})
                      @@ plainto_tsquery('english', $1)
                ORDER BY rank DESC
                LIMIT $2
            """

            rows = await conn.fetch(sql, query, limit)
            results.extend([dict(row) for row in rows])

    # Sort all results by rank
    results.sort(key=lambda x: x.get("rank", 0), reverse=True)

    return results[:limit]


async def search_references(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search only reference categories (decisions, howtos, snippets)."""
    return await search_full_text(
        query=query,
        tables=["decisions", "howtos", "snippets"],
        limit=limit,
    )


async def search_all(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search all categories."""
    return await search_full_text(
        query=query,
        tables=[
            "people",
            "projects",
            "ideas",
            "admin",
            "decisions",
            "howtos",
            "snippets",
        ],
        limit=limit,
    )


async def search_people(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search people only."""
    return await search_full_text(
        query=query,
        tables=["people"],
        limit=limit,
    )
