# Phase 5: On-Demand Retrieval

## Goal

Add query commands so you can retrieve information from your second brain:

```
?recall <query>     → searches decisions, howtos, snippets
?search <query>     → searches all categories
?people <query>     → searches people only
?projects [status]  → lists projects, optionally by status
?ideas              → lists recent ideas
?admin [due]        → lists admin tasks
```

## Architecture

```
User: ?recall papercage restart
           │
           ▼
┌─────────────────────────┐
│  Command Parser         │
│  - Detect ?command      │
│  - Extract query        │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Search Handler         │
│  - PostgreSQL FTS       │
│  - Filter by category   │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  LLM Summarizer         │
│  - Rank results         │
│  - Format response      │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│  Matrix Reply           │
└─────────────────────────┘
```

## Step 1: Search Queries

Add to `bot/queries.py`:

```python
from typing import List, Dict, Any, Optional
from db import get_pool


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
    
    # Build search query for each table
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
            "display_columns": "id, title, decision, rationale, created_at",
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
            
            # Use PostgreSQL full-text search with ranking
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
    results.sort(key=lambda x: x.get('rank', 0), reverse=True)
    
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
        tables=["people", "projects", "ideas", "admin", "decisions", "howtos", "snippets"],
        limit=limit,
    )


async def search_people(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search people only."""
    return await search_full_text(
        query=query,
        tables=["people"],
        limit=limit,
    )


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
                limit
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
                limit
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
            limit
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
                limit
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
                limit
            )
        return [dict(row) for row in rows]
```

## Step 2: Command Handler

Create `bot/commands.py`:

```python
import re
from typing import Optional, Tuple, List, Dict, Any
import httpx
from config import Config
from queries import (
    search_references,
    search_all,
    search_people,
    list_projects,
    list_ideas,
    list_admin,
)


# Command patterns
COMMAND_PATTERNS = {
    "recall": re.compile(r'^\?recall\s+(.+)$', re.IGNORECASE),
    "search": re.compile(r'^\?search\s+(.+)$', re.IGNORECASE),
    "people": re.compile(r'^\?people\s+(.+)$', re.IGNORECASE),
    "projects": re.compile(r'^\?projects(?:\s+(active|waiting|blocked|someday|done))?$', re.IGNORECASE),
    "ideas": re.compile(r'^\?ideas$', re.IGNORECASE),
    "admin": re.compile(r'^\?admin(?:\s+(due))?$', re.IGNORECASE),
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


RETRIEVAL_PROMPT = """You are formatting search results from a personal knowledge management system.

Given the search results below, create a CONCISE response that:
1. Directly answers the query if possible
2. Lists the most relevant results
3. Includes key details (content for howtos, rationale for decisions)

Keep response under 200 words. Use bullet points for multiple results.
If there's a clear answer (like a howto command), lead with that.

QUERY: {query}

RESULTS:
{results}

FORMAT YOUR RESPONSE:
"""


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
            results_text.append(f"[DECISION] {r['title']}\n{r['decision']}\nRationale: {r.get('rationale', 'none')}")
        elif source == "people":
            results_text.append(f"[PERSON] {r['name']}\nContext: {r.get('context', 'none')}\nFollow-ups: {r.get('follow_ups', 'none')}")
        elif source == "projects":
            results_text.append(f"[PROJECT] {r['name']} ({r['status']})\nNext: {r.get('next_action', 'none')}")
        elif source == "ideas":
            results_text.append(f"[IDEA] {r['title']}\n{r.get('one_liner', '')}")
        elif source == "admin":
            due = f" (due {r['due_date']})" if r.get('due_date') else ""
            results_text.append(f"[ADMIN] {r['name']}{due}")
    
    if not use_llm:
        # Simple formatting without LLM
        return f"🔍 Results for: {query}\n\n" + "\n\n".join(results_text)
    
    # Use Claude to format nicely
    prompt = RETRIEVAL_PROMPT.format(
        query=query,
        results="\n\n".join(results_text),
    )
    
    async with httpx.AsyncClient(timeout=30.0) as client:
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
                    {"role": "user", "content": prompt}
                ],
            },
        )
        response.raise_for_status()
        
        result = response.json()
        return result["content"][0]["text"]


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
        
        next_action = f" → {p['next_action']}" if p.get('next_action') else ""
        lines.append(f"• {p['name']}{next_action}")
    
    return "\n".join(lines)


def format_idea_list(ideas: List[Dict[str, Any]]) -> str:
    """Format a list of ideas."""
    if not ideas:
        return "💡 No ideas captured yet."
    
    lines = ["💡 **Ideas**\n"]
    
    for i in ideas:
        one_liner = f": {i['one_liner']}" if i.get('one_liner') else ""
        date = i['created_at'].strftime('%b %d')
        lines.append(f"• {i['title']}{one_liner} ({date})")
    
    return "\n".join(lines)


def format_admin_list(admin: List[Dict[str, Any]]) -> str:
    """Format a list of admin tasks."""
    if not admin:
        return "✅ No pending admin tasks."
    
    lines = ["📝 **Admin Tasks**\n"]
    
    for a in admin:
        due = f" (due {a['due_date']})" if a.get('due_date') else ""
        lines.append(f"• {a['name']}{due}")
    
    return "\n".join(lines)


async def handle_command(command: str, arg: Optional[str]) -> str:
    """
    Handle a command and return the response.
    """
    
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
```

## Step 3: Integrate with Bot

Update `bot/main.py` to handle commands:

```python
# Add import at top
from commands import parse_command, handle_command

# In the on_message method, add command handling before regular processing:

async def on_message(self, room: MatrixRoom, event: RoomMessageText):
    # Ignore our own messages
    if event.sender == self.client.user_id:
        return
    
    # Only process messages in the inbox room
    if room.room_id != self.inbox_room_id:
        return
    
    text = event.body.strip()
    if not text:
        return
    
    # Check for commands first
    command_result = parse_command(text)
    if command_result:
        command, arg = command_result
        logger.info(f"Command: {command}, arg: {arg}")
        
        response = await handle_command(command, arg)
        
        await self.client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": response,
                "m.relates_to": {
                    "m.in_reply_to": {
                        "event_id": event.event_id
                    }
                }
            }
        )
        return
    
    # Check if this is a reply to another message
    reply_to_id = self.get_reply_to_event_id(event)
    if reply_to_id:
        await self.handle_reply(room, event, reply_to_id)
        return
    
    # ... rest of existing capture logic
```

## Step 4: Test Commands

### 4.1 Test ?recall

```
You: ?recall papercage restart

Bot: Found 1 howto:
     **Restart papercage**
     → systemctl --user restart papercage-sandbox
     
     Verify with: papercage status
```

### 4.2 Test ?search

```
You: ?search postgres

Bot: Found 3 results:

     **[DECISION]** Using Postgres for second brain
     Decision: Use PostgreSQL over markdown files
     Rationale: queryability, atomic transactions, better for automation
     
     **[PROJECT]** Database migration
     Status: active
     Next: Write schema migration script
     
     **[HOWTO]** Postgres backup
     → pg_dump secondbrain > backup.sql
```

### 4.3 Test ?projects

```
You: ?projects

Bot: 📋 **Projects**

     **ACTIVE**
     • Papercage sandbox → Review nftables rules
     • Dito EHR integration → Email Dr. Silva
     • Second brain setup → Test daily digest
     
     **WAITING**
     • Domain renewal → Waiting for registrar
     
     **BLOCKED**
     • API migration → Need production access
```

### 4.4 Test ?projects active

```
You: ?projects active

Bot: 📋 **Projects**

     **ACTIVE**
     • Papercage sandbox → Review nftables rules
     • Dito EHR integration → Email Dr. Silva
     • Second brain setup → Test daily digest
```

### 4.5 Test ?ideas

```
You: ?ideas

Bot: 💡 **Ideas**

     • Matrix reactions for triage (Jan 8)
     • Multi-agent cost routing: Use GLM-4 for simple tasks (Jan 7)
     • Embedding search for howtos (Jan 5)
```

### 4.6 Test ?admin

```
You: ?admin due

Bot: 📝 **Admin Tasks**

     • Renew domain carloszan.com (due 2026-01-15)
     • Pay electricity bill (due 2026-01-20)
```

## Phase 5 Checklist

- [ ] Search functions added to `queries.py`
- [ ] Command parser created in `commands.py`
- [ ] LLM-assisted result formatting
- [ ] Commands integrated into main bot
- [ ] `?recall` searches references
- [ ] `?search` searches all categories
- [ ] `?people` searches people
- [ ] `?projects` lists/filters projects
- [ ] `?ideas` lists ideas
- [ ] `?admin` lists admin tasks

## Command Reference

| Command | Description | Example |
|---------|-------------|---------|
| `?recall <query>` | Search decisions, howtos, snippets | `?recall docker network` |
| `?search <query>` | Search all categories | `?search papercage` |
| `?people <query>` | Search people | `?people Silva` |
| `?projects` | List all projects | `?projects` |
| `?projects <status>` | Filter by status | `?projects blocked` |
| `?ideas` | List recent ideas | `?ideas` |
| `?admin` | List pending tasks | `?admin` |
| `?admin due` | List tasks with due dates | `?admin due` |

## Future Enhancements

### Semantic search with embeddings

For more accurate retrieval, add embedding-based search:

1. Add `pgvector` extension to PostgreSQL
2. Generate embeddings for all entries using a local model or API
3. Store embeddings in a `_embedding` column
4. Use cosine similarity for search

This would make queries like `?recall how to isolate network` find the papercage howto even if it doesn't contain those exact words.

### Natural language queries

Instead of `?recall`, allow natural questions:
```
You: How do I restart the sandbox?

Bot: [detects this is a retrieval question]
     [searches howtos]
     [returns answer]
```

This requires classifying whether a message is a capture or a query.
