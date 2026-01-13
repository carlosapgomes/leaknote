"""Admin UI routes for the Leaknote admin interface."""

import logging
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from markdown import markdown
import asyncpg

from bot.db import get_pool, insert_record, update_record, delete_record, get_record
from memory.mem0_client import get_memory_client

logger = logging.getLogger(__name__)
from bot.queries import (
    get_inbox_stats,
    get_active_projects,
    get_admin_due_soon,
    get_overdue_admin,
    get_people_with_followups,
    get_recent_ideas,
)
from leaknote.admin.dependencies import get_db_pool, get_table_config, VALID_TABLES

router = APIRouter()
templates = Jinja2Templates(directory="leaknote/admin/templates")


# =============================================================================
# Dashboard
# =============================================================================


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Dashboard with statistics and quick links."""
    stats = await get_inbox_stats(days=7)
    active_projects = await get_active_projects(limit=5)
    due_soon = await get_admin_due_soon(days=7)
    overdue = await get_overdue_admin()
    followups = await get_people_with_followups()
    recent_ideas = await get_recent_ideas(days=7, limit=5)

    # Get record counts per table
    counts = {}
    async with pool.acquire() as conn:
        for table in ["people", "projects", "ideas", "admin", "decisions", "howtos", "snippets"]:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            counts[table] = count

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "active_projects": active_projects,
            "due_soon": due_soon,
            "overdue": overdue,
            "followups": followups,
            "recent_ideas": recent_ideas,
            "counts": counts,
        },
    )


# =============================================================================
# Table Listing
# =============================================================================


@router.get("/table/{table_name}", response_class=HTMLResponse)
async def table_list(
    request: Request,
    table_name: str,
    pool: asyncpg.Pool = Depends(get_db_pool),
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
):
    """List records from a table with pagination."""
    config = get_table_config(table_name)

    offset = (page - 1) * per_page

    # Build query
    if search and table_name in ["people", "projects", "ideas", "admin", "decisions", "howtos", "snippets"]:
        # Use full-text search
        from bot.queries import search_full_text
        results = await search_full_text(search, [table_name], limit=per_page * 2)
        records = results[offset : offset + per_page]
        total = len(results)
    else:
        # Simple pagination
        async with pool.acquire() as conn:
            columns = config["list_columns"]
            query = f"SELECT * FROM {table_name} ORDER BY created_at DESC LIMIT $1 OFFSET $2"
            rows = await conn.fetch(query, per_page, offset)
            records = [dict(r) for r in rows]

            # Get total count
            count_query = f"SELECT COUNT(*) FROM {table_name}"
            total = await conn.fetchval(count_query)

    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse(
        "table_list.html",
        {
            "request": request,
            "table_name": table_name,
            "config": config,
            "records": records,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "search": search,
        },
    )


# =============================================================================
# Create Record
# =============================================================================


@router.get("/table/{table_name}/new", response_class=HTMLResponse)
async def record_new_form(
    request: Request,
    table_name: str,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Show form to create a new record."""
    config = get_table_config(table_name)

    return templates.TemplateResponse(
        "record_edit.html",
        {
            "request": request,
            "table_name": table_name,
            "config": config,
            "record": None,
        },
    )


@router.post("/table/{table_name}/new")
async def record_create(
    table_name: str,
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Create a new record."""
    config = get_table_config(table_name)

    form_data = await request.form()
    data = {}

    for field in config["fields"]:
        value = form_data.get(field["name"])
        if value is not None and value != "":
            # Handle tags (comma-separated)
            if field["type"] == "tags":
                data[field["name"]] = [t.strip() for t in value.split(",") if t.strip()]
            else:
                data[field["name"]] = value

    try:
        record_id = await insert_record(table_name, data)
        return RedirectResponse(f"/table/{table_name}?msg=created", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Edit Record
# =============================================================================


@router.get("/table/{table_name}/{id}/edit", response_class=HTMLResponse)
async def record_edit_form(
    request: Request,
    table_name: str,
    id: str,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Show form to edit a record."""
    config = get_table_config(table_name)
    record = await get_record(table_name, id)

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    return templates.TemplateResponse(
        "record_edit.html",
        {
            "request": request,
            "table_name": table_name,
            "config": config,
            "record": record,
            "record_id": id,
        },
    )


@router.post("/table/{table_name}/{id}/edit")
async def record_update(
    table_name: str,
    id: str,
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Update a record."""
    config = get_table_config(table_name)

    form_data = await request.form()
    data = {}

    for field in config["fields"]:
        value = form_data.get(field["name"])
        if value is not None and value != "":
            # Handle tags (comma-separated)
            if field["type"] in ("tags", "select"):
                if field["type"] == "tags":
                    data[field["name"]] = [t.strip() for t in value.split(",") if t.strip()]
                else:
                    data[field["name"]] = value
            else:
                data[field["name"]] = value

    try:
        success = await update_record(table_name, id, data)
        if success:
            return RedirectResponse(f"/table/{table_name}?msg=updated", status_code=303)
        else:
            raise HTTPException(status_code=404, detail="Record not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# View Record (Rendered Markdown for Reference Categories)
# =============================================================================


@router.get("/table/{table_name}/{id}/view", response_class=HTMLResponse)
async def record_view(
    request: Request,
    table_name: str,
    id: str,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """View a record with rendered markdown."""
    config = get_table_config(table_name)
    record = await get_record(table_name, id)

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # Render markdown fields
    rendered = {}
    if config["is_markdown"]:
        for field in config["fields"]:
            if field["type"] == "markdown" and record.get(field["name"]):
                rendered[field["name"]] = markdown(record[field["name"]])

    return templates.TemplateResponse(
        "record_view.html",
        {
            "request": request,
            "table_name": table_name,
            "config": config,
            "record": record,
            "rendered": rendered,
        },
    )


# =============================================================================
# Delete Record
# =============================================================================


@router.get("/table/{table_name}/{id}/delete", response_class=HTMLResponse)
async def record_delete_confirm(
    table_name: str,
    id: str,
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Show confirmation page before deleting a record with memory count."""
    config = get_table_config(table_name)
    record = await get_record(table_name, id)

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # Count associated memories
    memory_count = 0
    try:
        memory_client = get_memory_client()
        all_memories = await memory_client.get_all_memories()
        for mem in all_memories:
            if mem.get("metadata", {}).get("note_id") == id:
                memory_count += 1
    except Exception as e:
        logger.warning(f"Could not fetch memory count for {table_name}/{id}: {e}")

    return templates.TemplateResponse(
        "confirm_delete.html",
        {
            "request": request,
            "table_name": table_name,
            "config": config,
            "record": record,
            "record_id": id,
            "memory_count": memory_count,
        },
    )


@router.post("/table/{table_name}/{id}/delete")
async def record_delete(
    table_name: str,
    id: str,
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Delete a record, optionally with its associated memories."""
    form_data = await request.form()
    delete_memories = form_data.get("delete_memories") == "1"

    # Delete memories if requested
    if delete_memories:
        try:
            memory_client = get_memory_client()
            await memory_client.delete_note_memories(id)
        except Exception as e:
            logger.error(f"Failed to delete memories for {table_name}/{id}: {e}")

    # Always delete from PostgreSQL
    success = await delete_record(table_name, id)

    if success:
        msg = "deleted_with_memories" if delete_memories else "deleted"
        return RedirectResponse(f"/table/{table_name}?msg={msg}", status_code=303)
    else:
        raise HTTPException(status_code=404, detail="Record not found")


# =============================================================================
# Bulk Delete
# =============================================================================


@router.get("/bulk-delete", response_class=HTMLResponse)
async def bulk_delete_form(
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Show bulk delete form."""
    return templates.TemplateResponse(
        "bulk_delete.html",
        {
            "request": request,
            "tables": VALID_TABLES,
        },
    )


@router.post("/bulk-delete")
async def bulk_delete_execute(
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Execute bulk delete by date range."""
    form_data = await request.form()
    table_name = form_data.get("table_name")
    days_str = form_data.get("days", "30")

    try:
        days = int(days_str)
    except ValueError:
        days = 30

    if table_name not in VALID_TABLES:
        raise HTTPException(status_code=400, detail="Invalid table")

    async with pool.acquire() as conn:
        result = await conn.execute(
            f"DELETE FROM {table_name} WHERE created_at < NOW() - INTERVAL '{days} days'"
        )
        deleted_count = int(result.split()[-1])

    return RedirectResponse(f"/bulk-delete?msg=deleted_{deleted_count}", status_code=303)
