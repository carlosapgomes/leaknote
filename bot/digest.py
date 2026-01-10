"""Daily digest generation."""

import httpx
from datetime import datetime
from pathlib import Path

from config import Config
from queries import (
    get_active_projects,
    get_blocked_projects,
    get_admin_due_soon,
    get_overdue_admin,
    get_people_with_followups,
    get_recent_decisions,
)


# Load prompt
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_file = PROMPTS_DIR / f"{name}.md"
    if prompt_file.exists():
        return prompt_file.read_text()
    raise FileNotFoundError(f"Prompt file not found: {prompt_file}")


DAILY_DIGEST_PROMPT = load_prompt("daily")


async def generate_daily_digest() -> str:
    """Generate the daily digest content."""

    # Gather data
    active_projects = await get_active_projects(limit=10)
    blocked_projects = await get_blocked_projects()
    overdue = await get_overdue_admin()
    due_soon = await get_admin_due_soon(days=3)
    people = await get_people_with_followups()
    decisions = await get_recent_decisions(days=7, limit=1)

    # Format data for LLM
    data_sections = []

    if active_projects:
        projects_text = "\n".join(
            [
                f"- {p['name']}: {p['next_action'] or 'no next action'}"
                for p in active_projects[:5]
            ]
        )
        data_sections.append(f"ACTIVE PROJECTS:\n{projects_text}")

    if blocked_projects:
        blocked_text = "\n".join(
            [f"- {p['name']}: {p['notes'] or 'no notes'}" for p in blocked_projects[:3]]
        )
        data_sections.append(f"BLOCKED:\n{blocked_text}")

    if overdue:
        overdue_text = "\n".join(
            [f"- {a['name']} (due {a['due_date']})" for a in overdue[:3]]
        )
        data_sections.append(f"OVERDUE:\n{overdue_text}")

    if due_soon:
        due_text = "\n".join(
            [f"- {a['name']} (due {a['due_date']})" for a in due_soon[:5]]
        )
        data_sections.append(f"DUE SOON:\n{due_text}")

    if people:
        people_text = "\n".join(
            [f"- {p['name']}: {p['follow_ups']}" for p in people[:3]]
        )
        data_sections.append(f"PEOPLE TO FOLLOW UP:\n{people_text}")

    if decisions:
        d = decisions[0]
        data_sections.append(f"RECENT DECISION:\n- {d['title']}: {d['decision']}")

    if not data_sections:
        return "📭 Nothing urgent today. Inbox is clear."

    data_text = "\n\n".join(data_sections)

    # Call Claude for summarization
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            Config.CLAUDE_API_URL,
            headers={
                "x-api-key": Config.CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": Config.CLAUDE_MODEL,
                "max_tokens": 500,
                "messages": [
                    {"role": "user", "content": DAILY_DIGEST_PROMPT + data_text}
                ],
            },
        )
        response.raise_for_status()

        result = response.json()
        return result["content"][0]["text"]


def format_digest_date() -> str:
    """Format today's date for the digest header."""
    return datetime.now().strftime("%A, %B %d")
