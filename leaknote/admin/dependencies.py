"""FastAPI dependencies for the admin UI."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import os
import asyncpg

from bot.db import get_pool

security = HTTPBasic()


async def get_db_pool() -> asyncpg.Pool:
    """Get the database connection pool."""
    return await get_pool()


def get_current_admin(
    credentials: HTTPBasicCredentials = Depends(security),
) -> str:
    """Verify HTTP Basic Auth credentials and return the username."""
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "")

    correct_username = secrets.compare_digest(credentials.username, admin_user)
    correct_password = secrets.compare_digest(credentials.password, admin_pass)

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# Table configurations for form rendering
TABLE_CONFIGS = {
    "people": {
        "display_name": "People",
        "fields": [
            {"name": "name", "label": "Name", "type": "text", "required": True},
            {"name": "context", "label": "Context", "type": "textarea"},
            {"name": "follow_ups", "label": "Follow Ups", "type": "textarea"},
            {"name": "last_touched", "label": "Last Touched", "type": "date"},
            {"name": "tags", "label": "Tags", "type": "tags"},
        ],
        "list_columns": ["name", "context", "last_touched", "updated_at"],
        "is_markdown": False,
    },
    "projects": {
        "display_name": "Projects",
        "fields": [
            {"name": "name", "label": "Name", "type": "text", "required": True},
            {"name": "status", "label": "Status", "type": "select", "options": ["active", "waiting", "blocked", "someday", "done"], "default": "active"},
            {"name": "next_action", "label": "Next Action", "type": "text"},
            {"name": "notes", "label": "Notes", "type": "textarea"},
            {"name": "tags", "label": "Tags", "type": "tags"},
        ],
        "list_columns": ["name", "status", "next_action", "updated_at"],
        "is_markdown": False,
    },
    "ideas": {
        "display_name": "Ideas",
        "fields": [
            {"name": "title", "label": "Title", "type": "text", "required": True},
            {"name": "one_liner", "label": "One Liner", "type": "text"},
            {"name": "elaboration", "label": "Elaboration", "type": "textarea"},
            {"name": "tags", "label": "Tags", "type": "tags"},
        ],
        "list_columns": ["title", "one_liner", "created_at", "updated_at"],
        "is_markdown": False,
    },
    "admin": {
        "display_name": "Admin",
        "fields": [
            {"name": "name", "label": "Name", "type": "text", "required": True},
            {"name": "due_date", "label": "Due Date", "type": "date"},
            {"name": "status", "label": "Status", "type": "select", "options": ["pending", "done"], "default": "pending"},
            {"name": "notes", "label": "Notes", "type": "textarea"},
            {"name": "tags", "label": "Tags", "type": "tags"},
        ],
        "list_columns": ["name", "due_date", "status", "updated_at"],
        "is_markdown": False,
    },
    "decisions": {
        "display_name": "Decisions",
        "fields": [
            {"name": "title", "label": "Title", "type": "text", "required": True},
            {"name": "decision", "label": "Decision", "type": "markdown", "required": True},
            {"name": "rationale", "label": "Rationale", "type": "markdown"},
            {"name": "context", "label": "Context", "type": "markdown"},
            {"name": "tags", "label": "Tags", "type": "tags"},
        ],
        "list_columns": ["title", "decision", "created_at"],
        "is_markdown": True,
    },
    "howtos": {
        "display_name": "How-Tos",
        "fields": [
            {"name": "title", "label": "Title", "type": "text", "required": True},
            {"name": "content", "label": "Content", "type": "markdown", "required": True},
            {"name": "tags", "label": "Tags", "type": "tags"},
        ],
        "list_columns": ["title", "created_at", "updated_at"],
        "is_markdown": True,
    },
    "snippets": {
        "display_name": "Snippets",
        "fields": [
            {"name": "title", "label": "Title", "type": "text", "required": True},
            {"name": "content", "label": "Content", "type": "markdown", "required": True},
            {"name": "tags", "label": "Tags", "type": "tags"},
        ],
        "list_columns": ["title", "created_at", "updated_at"],
        "is_markdown": True,
    },
    "pending_clarifications": {
        "display_name": "Pending Clarifications",
        "fields": [],
        "list_columns": ["telegram_message_id", "suggested_category", "created_at"],
        "is_markdown": False,
    },
}

VALID_TABLES = list(TABLE_CONFIGS.keys())


def get_table_config(table_name: str) -> dict:
    """Get configuration for a table."""
    if table_name not in TABLE_CONFIGS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table '{table_name}' not found",
        )
    return TABLE_CONFIGS[table_name]
