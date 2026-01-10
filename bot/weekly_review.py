"""Weekly review generation."""

from datetime import datetime, timedelta
from pathlib import Path

from config import Config
from queries import (
    get_active_projects,
    get_waiting_projects,
    get_blocked_projects,
    get_admin_due_soon,
    get_overdue_admin,
    get_people_with_followups,
    get_recent_decisions,
    get_recent_ideas,
    get_inbox_stats,
)


# Load prompt
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_file = PROMPTS_DIR / f"{name}.md"
    if prompt_file.exists():
        return prompt_file.read_text()
    raise FileNotFoundError(f"Prompt file not found: {prompt_file}")


WEEKLY_REVIEW_PROMPT = load_prompt("weekly")


async def generate_weekly_review() -> str:
    """Generate the weekly review content."""

    # Gather data
    active_projects = await get_active_projects(limit=20)
    waiting_projects = await get_waiting_projects()
    blocked_projects = await get_blocked_projects()
    overdue = await get_overdue_admin()
    due_soon = await get_admin_due_soon(days=7)
    people = await get_people_with_followups()
    decisions = await get_recent_decisions(days=7, limit=10)
    ideas = await get_recent_ideas(days=7, limit=10)
    stats = await get_inbox_stats(days=7)

    # Format data for LLM
    data_sections = []

    # Stats summary
    data_sections.append(
        f"INBOX STATS (last 7 days):\n"
        f"- Total captured: {stats['total']}\n"
        f"- Filed: {stats['filed']}\n"
        f"- Needed review: {stats['needs_review']}\n"
        f"- Fixed: {stats['fixed']}"
    )

    if active_projects:
        projects_text = "\n".join(
            [
                f"- {p['name']}: {p['next_action'] or 'no next action'} (updated {p['updated_at'].strftime('%a')})"
                for p in active_projects[:10]
            ]
        )
        data_sections.append(
            f"ACTIVE PROJECTS ({len(active_projects)} total):\n{projects_text}"
        )

    if waiting_projects:
        waiting_text = "\n".join(
            [
                f"- {p['name']}: waiting since {p['updated_at'].strftime('%b %d')}"
                for p in waiting_projects
            ]
        )
        data_sections.append(f"WAITING ({len(waiting_projects)}):\n{waiting_text}")

    if blocked_projects:
        blocked_text = "\n".join(
            [f"- {p['name']}: {p['notes'] or 'no notes'}" for p in blocked_projects]
        )
        data_sections.append(f"BLOCKED ({len(blocked_projects)}):\n{blocked_text}")

    if overdue:
        overdue_text = "\n".join(
            [f"- {a['name']} (was due {a['due_date']})" for a in overdue]
        )
        data_sections.append(f"OVERDUE:\n{overdue_text}")

    if due_soon:
        due_text = "\n".join(
            [f"- {a['name']} (due {a['due_date']})" for a in due_soon[:5]]
        )
        data_sections.append(f"DUE THIS WEEK:\n{due_text}")

    if people:
        people_text = "\n".join(
            [
                f"- {p['name']}: {p['follow_ups']} (last: {p['last_touched'].strftime('%b %d') if p['last_touched'] else 'never'})"
                for p in people[:5]
            ]
        )
        data_sections.append(f"PEOPLE TO FOLLOW UP:\n{people_text}")

    if ideas:
        ideas_text = "\n".join(
            [f"- {i['title']}: {i['one_liner'] or ''}" for i in ideas]
        )
        data_sections.append(f"IDEAS THIS WEEK ({len(ideas)}):\n{ideas_text}")

    if decisions:
        decisions_text = "\n".join(
            [f"- {d['title']}: {d['decision']}" for d in decisions]
        )
        data_sections.append(
            f"DECISIONS THIS WEEK ({len(decisions)}):\n{decisions_text}"
        )

    if not any(
        [active_projects, waiting_projects, blocked_projects, ideas, decisions]
    ):
        return "📭 Quiet week. No significant activity captured."

    data_text = "\n\n".join(data_sections)

    # Get summary client and generate review
    client = Config.get_summary_client()

    response = await client.complete(
        prompt=WEEKLY_REVIEW_PROMPT + data_text,
        temperature=0.7,
        max_tokens=800,
    )

    return response.content


def format_review_date_range() -> str:
    """Format the date range for the review header."""
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    return f"{week_ago.strftime('%b %d')} - {today.strftime('%b %d, %Y')}"
