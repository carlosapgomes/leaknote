# Leaknote

A self-hosted "second brain" that captures your thoughts via Telegram, classifies them with LLMs, and surfaces relevant information through daily digests, semantic search, and on-demand retrieval.

## Features

- **Frictionless capture**: Direct messages to Telegram bot
- **AI classification**: Automatically routes to people, projects, ideas, admin
- **Reference storage**: Explicit prefixes for decisions, howtos, snippets
- **Daily digest**: Morning briefing with top actions (06:00)
- **Weekly review**: Sunday summary with patterns and suggestions (16:00)
- **Semantic memory**: Long-term memory layer using Mem0 + Qdrant + LangGraph
- **Smart linking**: Automatic link suggestions based on semantic similarity
- **On-demand retrieval**: `?recall`, `?search`, `?projects`, `?semsearch` commands
- **Web admin UI**: Browser-based management for records (Tailscale-only access)
- **Trust mechanisms**: Confirmations, fix commands, audit log

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Telegram Bot API                                               │
│  └── Direct Messages (capture, digests, confirmations)          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Leaknote Bot (Python)                                          │
│  ├── Classifier (LLM for routing)                               │
│  ├── Router (prefix detection + confidence check)               │
│  ├── Surfacer (LLM for summaries)                               │
│  └── Memory Layer (semantic search + smart linking)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
┌───────────────────────────┐   ┌─────────────────────────────────┐
│  PostgreSQL (Source)       │   │  Memory Layer (Semantic)        │
│  ├── people, projects      │   │  ├── Mem0 (memory management)  │
│  ├── ideas, admin          │   │  ├── Qdrant (vector DB)        │
│  ├── decisions, howtos     │   │  └── LangGraph (orchestration) │
│  ├── snippets              │   │  - Smart linking                │
│  └── inbox_log (audit)     │   │  - Semantic search              │
└───────────────────────────┘   └─────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────────┐
│  Admin UI (FastAPI) - Tailscale Only                            │
│  ├── CRUD operations for all tables                             │
│  ├── Markdown editor (EasyMDE)                                  │
│  └── Bulk delete and cleanup                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start (Docker)

### Prerequisites

- Docker and Docker Compose
- LLM API keys (for classification, summaries, and memory operations)
- Telegram Bot Token (from @BotFather)
- Your Telegram User ID

### Memory Layer Requirements

The memory layer (Mem0 + Qdrant) requires:

- **OpenAI API key** for embeddings (see "Why Two API Keys?" below)
- **Memory LLM** for orchestration (can use any provider)
- ~500MB RAM for Qdrant vector database
- ~1GB disk space for vector storage (grows with your notes)

**Why Two API Keys?**

The memory layer requires **two separate API keys** for different purposes:

| Key | Purpose | Model | Can Use Alternative Providers? |
|-----|---------|-------|-------------------------------|
| `OPENAI_API_KEY` | Embeddings (text → vectors) | `text-embedding-3-small` | **No** - Must use OpenAI |
| `MEMORY_API_KEY` | LLM orchestration (reasoning) | `gpt-4o` or any model | **Yes** - Any provider |

**Why OpenAI for embeddings?**
- High-quality embeddings are critical for semantic search accuracy
- OpenAI's `text-embedding-3-small` provides the best quality/cost ratio (1536 dimensions)
- Embeddings are cached after generation, so API usage is minimal
- Your local machine only stores and searches the vectors (~500MB RAM)

**Memory LLM flexibility:**
- The `MEMORY_API_KEY` can use OpenAI, OpenRouter, Groq, or any OpenAI-compatible provider
- This allows you to test different models for the orchestration "brain" without breaking embeddings
- You can even use local models (Ollama) for the LLM while keeping OpenAI for embeddings

### 1. Create a Telegram Bot

1. Message @BotFather on Telegram
2. Use `/newbot` command and follow the prompts
3. Save the bot token
4. Get your Telegram user ID (message @userinfobot)

### 2. Clone and setup

```bash
git clone <repo-url> leaknote
cd leaknote

# Run setup script (creates .env and directories)
chmod +x setup.sh
./setup.sh

# Edit .env with your:
# - Database passwords
# - LLM API keys (CLASSIFY_*, SUMMARY_*, MEMORY_*)
# - Telegram bot token
# - Telegram owner ID (your user ID)
# - Admin UI credentials
```

### 3. Start the stack

```bash
docker compose up -d
docker compose ps  # Wait for all services to be healthy
```

Services started:
- `postgres` - PostgreSQL database
- `qdrant` - Vector database for memory layer
- `leaknote` - Main bot application

### 4. Bootstrap existing notes (optional)

If you have existing notes in PostgreSQL, bootstrap them into the memory layer:

```bash
# From inside the container
docker exec -it leaknote python scripts/bootstrap_memory.py
```

This will:
- Export all notes from PostgreSQL
- Generate embeddings via OpenAI API
- Store vectors in Qdrant for semantic search

### 5. Install cron jobs

```bash
crontab -e
# Add entries from crontab.example:
# - Daily digest (06:00)
# - Weekly reflection (Sunday 16:00)
# - Health checks
```

### 6. Test it

Send a direct message to your bot on Telegram:

```
Met João at conference, works on EHR integration
```

Bot should reply with a confirmation and the note will be added to semantic memory.

## Usage

### Capture (Dynamic Categories)

Just type naturally - the AI classifies automatically:

```
Met João at conference, works on EHR integration
→ Classified as: people

Need to review nftables rules this week
→ Classified as: projects

Idea for quick triage with keyboard shortcuts
→ Classified as: ideas

Renew domain by January 15
→ Classified as: admin
```

### Capture (Reference Categories)

Use explicit prefixes to store retrievable knowledge:

```
decision: Using Postgres over markdown because queryability and atomicity

howto: Restart papercage → systemctl --user restart papercage-sandbox

snippet: Firejail base → firejail --net=none --private-tmp --private-dev
```

### Query Commands

```
?recall <query>     Search decisions, howtos, snippets
?search <query>     Search all categories (PostgreSQL full-text)
?semsearch <query>  Semantic search using memory layer (finds related concepts)
?people <query>     Search people
?projects [status]  List projects (optionally filter by active/waiting/blocked)
?ideas              List recent ideas
?admin [due]        List admin tasks (optionally only those with due dates)
```

**Semantic Search vs Regular Search:**

| Command | Search Type | Best For |
|---------|-------------|----------|
| `?search` | Keyword matching | Finding exact words/phrases |
| `?semsearch` | Semantic similarity | Finding related concepts, themes, connections |

Example:
```
?search rust              # Finds notes containing "rust"
?semsearch programming    # Finds notes about coding, development, software, etc.
```

### Fix Mistakes

Reply to any bot confirmation with:

```
fix: people
fix: project
fix: idea
```

### Admin Web UI

The admin UI provides browser-based management for all records:

**Access (Tailscale only):**
```
http://<tailscale-ip>:8000
```

**Features:**
- **Dashboard**: Overview stats, quick links to tables
- **CRUD Operations**: Create, edit, view, and delete records
- **Markdown Editor**: EasyMDE editor for decisions, howtos, and snippets
- **Bulk Delete**: Delete records by date range
- **Search**: Full-text search across all tables
- **Mobile Responsive**: Works on phones and tablets

**Authentication:**
- HTTP Basic Auth (browser prompts for username/password)
- Credentials set in `.env`:
  ```bash
  ADMIN_USERNAME=admin
  ADMIN_PASSWORD=your-secure-password
  ```

**Tables available:**
- Dynamic: people, projects, ideas, admin
- Reference: decisions, howtos, snippets
- System: pending_clarifications (view only)

For detailed documentation, see [docs/admin-ui.md](docs/admin-ui.md).

## Testing

The project includes a comprehensive automated test suite:

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run only unit tests (fast)
pytest -m unit

# Run with coverage report
pytest --cov=bot --cov-report=html

# View coverage report
open htmlcov/index.html
```

See [tests/README.md](tests/README.md) for detailed testing documentation.

## Configuration

See [docs/configuration.md](docs/configuration.md) for:

- Environment variables reference
- Telegram bot configuration
- LLM model selection
- Confidence threshold tuning

## Operations

See [docs/operations.md](docs/operations.md) for:

- Cron job setup
- Backup and restore
- Maintenance tasks
- Troubleshooting

## Project Structure

```
leaknote/
├── bot/                    # Python application
│   ├── main.py             # Entry point
│   ├── config.py           # Configuration
│   ├── db.py               # Database operations
│   ├── classifier.py       # LLM classification
│   ├── router.py           # Message routing (with memory enhancement)
│   ├── responder.py        # Telegram responses
│   ├── commands.py         # Query commands (including semsearch)
│   ├── queries.py          # Database queries
│   ├── digest.py           # Daily digest
│   └── llm/                # LLM abstraction layer
│       ├── factory.py      # Client factory
│       ├── openai_adapter.py
│       └── anthropic_adapter.py
├── memory/                 # Semantic memory layer
│   ├── config.py           # Memory configuration
│   ├── mem0_client.py      # Mem0 wrapper for leaknote
│   └── graph.py            # LangGraph orchestration brain
├── admin/                  # Admin UI module
│   ├── app.py              # FastAPI application
│   ├── routes.py           # Admin routes
│   ├── dependencies.py     # Dependencies and table configs
│   ├── templates/          # Jinja2 templates
│   └── static/             # CSS, JS (EasyMDE)
├── tests/                  # Automated tests
│   ├── conftest.py         # Test fixtures
│   ├── unit/               # Unit tests (including memory/)
│   └── integration/        # Integration tests (including memory/)
├── scripts/                # Cron scripts
│   ├── bootstrap_memory.py # Migrate notes to Qdrant
│   ├── reflection.py       # Weekly semantic reflection
│   ├── daily_digest.py
│   └── health_check.py
├── cron/                   # Cron wrapper scripts
│   └── reflection.sh
├── prompts/                # LLM prompts
│   ├── classify.md
│   ├── daily.md
│   ├── weekly.md
│   ├── retrieval.md
│   └── memory.md           # Memory extraction prompt
├── docs/                   # Documentation
│   ├── architecture.md
│   ├── configuration.md
│   ├── operations.md
│   └── admin-ui.md         # Admin UI documentation
├── plans/                  # Implementation plans
│   └── long-memory-implementation.md
├── docker-compose.yml
├── Dockerfile
├── schema.sql
├── requirements.txt
├── requirements-dev.txt    # Testing dependencies
├── pytest.ini              # Pytest configuration
├── setup.sh                # Initial setup script
└── crontab.example
```

## License

MIT
