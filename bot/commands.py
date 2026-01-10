"""Query command handling (?recall, ?search, etc.)."""

import re
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path

from config import Config
from queries import (
    search_references,
    search_all,
    search_people,
    list_projects,
    list_ideas,
    list_admin,
)


# Load retrieval prompt
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_file = PROMPTS_DIR / f"{name}.md"
    if prompt_file.exists():
        return prompt_file.read_text()
    raise FileNotFoundError(f"Prompt file not found: {prompt_file}")


RETRIEVAL_PROMPT = load_prompt("retrieval")


# Command patterns
COMMAND_PATTERNS = {
    "recall": re.compile(r"^\?recall\s+(.+)$", re.IGNORECASE),
    "search": re.compile(r"^\?search\s+(.+)$", re.IGNORECASE),
    "people": re.compile(r"^\?people\s+(.+)$", re.IGNORECASE),
    "projects": re.compile(
        r"^\?projects(?:\s+(active|waiting|blocked|someday|done))?$", re.IGNORECASE
    ),
    "ideas": re.compile(r"^\?ideas$", re.IGNORECASE),
    "admin": re.compile(r"^\?admin(?:\s+(due))?$", re.IGNORECASE),
}


def parse_command(text: str) -> Optional[Tuple[str, Optional[str]]]:
    """
    Parse a command from message text.
    Returns (command_name, argument) or None if not a command.
    """
    text = text.strip()

    if not text.startswith("?"):
        return None

    for cmd_name, pattern in COMMAND_PATTERNS.items():
        match = pattern.match(text)
        if match:
            arg = match.group(1) if match.lastindex else None
            return cmd_name, arg

    return None


async def format_search_results(
    query: str,
    results: List[Dict[str, Any]],
    use_llm: bool = True,
) -> str:
    """Format search results, optionally using LLM for summarization."""

    if not results:
        return f"🔍 No results found for: {query}"

    # Format results for LLM
    results_text = []
    for r in results[:5]:  # Top 5 results
        source = r.get("source_table", "unknown")

        if source == "howtos":
            results_text.append(f"[HOWTO] {r['title']}\n{r['content']}")
        elif source == "snippets":
            results_text.append(f"[SNIPPET] {r['title']}\n{r['content']}")
        elif source == "decisions":
            results_text.append(
                f"[DECISION] {r['title']}\n{r['decision']}\nRationale: {r.get('rationale', 'none')}"
            )
        elif source == "people":
            results_text.append(
                f"[PERSON] {r['name']}\nContext: {r.get('context', 'none')}\nFollow-ups: {r.get('follow_ups', 'none')}"
            )
        elif source == "projects":
            results_text.append(
                f"[PROJECT] {r['name']} ({r['status']})\nNext: {r.get('next_action', 'none')}"
            )
        elif source == "ideas":
            results_text.append(f"[IDEA] {r['title']}\n{r.get('one_liner', '')}")
        elif source == "admin":
            due = f" (due {r['due_date']})" if r.get("due_date") else ""
            results_text.append(f"[ADMIN] {r['name']}{due}")

    if not use_llm:
        return f"🔍 Results for: {query}\n\n" + "\n\n".join(results_text)

    # Use summary client to format nicely
    prompt = RETRIEVAL_PROMPT.format(
        query=query,
        results="\n\n".join(results_text),
    )

    try:
        client = Config.get_summary_client()

        response = await client.complete(
            prompt=prompt,
            temperature=0.5,
            max_tokens=500,
        )

        return response.content
    except Exception:
        # Fallback to simple formatting
        return f"🔍 Results for: {query}\n\n" + "\n\n".join(results_text)


def format_project_list(projects: List[Dict[str, Any]]) -> str:
    """Format a list of projects."""
    if not projects:
        return "📋 No projects found."

    lines = ["📋 **Projects**\n"]

    current_status = None
    for p in projects:
        status = p["status"]
        if status != current_status:
            current_status = status
            lines.append(f"\n**{status.upper()}**")

        next_action = f" → {p['next_action']}" if p.get("next_action") else ""
        lines.append(f"• {p['name']}{next_action}")

    return "\n".join(lines)


def format_idea_list(ideas: List[Dict[str, Any]]) -> str:
    """Format a list of ideas."""
    if not ideas:
        return "💡 No ideas captured yet."

    lines = ["💡 **Ideas**\n"]

    for i in ideas:
        one_liner = f": {i['one_liner']}" if i.get("one_liner") else ""
        date = i["created_at"].strftime("%b %d")
        lines.append(f"• {i['title']}{one_liner} ({date})")

    return "\n".join(lines)


def format_admin_list(admin: List[Dict[str, Any]]) -> str:
    """Format a list of admin tasks."""
    if not admin:
        return "✅ No pending admin tasks."

    lines = ["📝 **Admin Tasks**\n"]

    for a in admin:
        due = f" (due {a['due_date']})" if a.get("due_date") else ""
        lines.append(f"• {a['name']}{due}")

    return "\n".join(lines)


async def handle_command(command: str, arg: Optional[str]) -> str:
    """Handle a command and return the response."""

    if command == "recall":
        results = await search_references(arg)
        return await format_search_results(arg, results, use_llm=True)

    elif command == "search":
        results = await search_all(arg)
        return await format_search_results(arg, results, use_llm=True)

    elif command == "people":
        results = await search_people(arg)
        return await format_search_results(arg, results, use_llm=True)

    elif command == "projects":
        projects = await list_projects(status=arg)
        return format_project_list(projects)

    elif command == "ideas":
        ideas = await list_ideas()
        return format_idea_list(ideas)

    elif command == "admin":
        due_only = arg == "due"
        admin = await list_admin(due_only=due_only)
        return format_admin_list(admin)

    return "❓ Unknown command"
