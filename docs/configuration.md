# Configuration

## Environment Variables

All configuration is done through environment variables in `.env`.

### PostgreSQL

```bash
# Shared PostgreSQL admin
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-admin-password

# Leaknote database credentials (used by init-db.sh at runtime)
LEAKNOTE_DB_PASSWORD=your-leaknote-db-password
```

### Telegram

```bash
# Telegram bot token (from @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Your Telegram user ID (receives all messages and digests)
# Get this from @userinfobot
TELEGRAM_OWNER_ID=123456789
```

**Getting your Telegram configuration:**

1. Create a bot:
   - Message @BotFather on Telegram
   - Send `/newbot` and follow the prompts
   - Save the bot token provided

2. Get your user ID:
   - Message @userinfobot on Telegram
   - It will reply with your user ID

**Security note:** Only the owner ID can interact with the bot. All messages from other users are ignored.

## LLM Configuration

Leaknote uses three LLM clients with different roles:

| Client | Purpose | Characteristics |
|--------|---------|-----------------|
| **Classify** | Route incoming thoughts | Cheap, fast, runs frequently |
| **Summary** | Digests, reviews, retrieval | Quality matters, less frequent |
| **Memory** | Semantic memory operations | High-quality model for embeddings |

### Provider Types

All three clients support two provider types:

- `openai` - Works with any OpenAI-compatible API
- `anthropic` - Native Anthropic API

### Configuration Pattern

Each LLM has four settings:

```bash
{PREFIX}_PROVIDER=openai|anthropic
{PREFIX}_API_URL=https://...
{PREFIX}_API_KEY=your-api-key
{PREFIX}_MODEL=model-name
```

### Classification LLM

```bash
CLASSIFY_PROVIDER=openai
CLASSIFY_API_URL=https://api.z.ai/v1
CLASSIFY_API_KEY=your-key
CLASSIFY_MODEL=glm-4
```

### Summary LLM

```bash
SUMMARY_PROVIDER=openai
SUMMARY_API_URL=https://openrouter.ai/api/v1
SUMMARY_API_KEY=your-key
SUMMARY_MODEL=anthropic/claude-sonnet-4
```

## OpenAI-Compatible Endpoints

The `openai` provider works with many services:

| Service | API URL | Notes |
|---------|---------|-------|
| **OpenAI** | `https://api.openai.com/v1` | GPT-4o, GPT-4, etc. |
| **OpenRouter** | `https://openrouter.ai/api/v1` | Access to all models |
| **Ollama** | `http://localhost:11434/v1` | Local models, free |
| **vLLM** | `http://localhost:8000/v1` | Self-hosted inference |
| **LiteLLM** | `http://localhost:4000/v1` | Proxy to any provider |
| **Together AI** | `https://api.together.xyz/v1` | Fast open models |
| **Groq** | `https://api.groq.com/openai/v1` | Very fast inference |
| **Mistral** | `https://api.mistral.ai/v1` | Mistral models |
| **DeepSeek** | `https://api.deepseek.com/v1` | DeepSeek models |
| **Z.AI** | `https://api.z.ai/v1` | GLM-4 |

## Example Configurations

### Budget Setup (Local + OpenRouter)

```bash
# Classification: Local Ollama (free)
CLASSIFY_PROVIDER=openai
CLASSIFY_API_URL=http://localhost:11434/v1
CLASSIFY_API_KEY=ollama
CLASSIFY_MODEL=llama3

# Summary: OpenRouter (pay per use)
SUMMARY_PROVIDER=openai
SUMMARY_API_URL=https://openrouter.ai/api/v1
SUMMARY_API_KEY=your-openrouter-key
SUMMARY_MODEL=anthropic/claude-sonnet-4
```

### Speed Setup (Groq + Groq)

```bash
# Classification: Groq (very fast)
CLASSIFY_PROVIDER=openai
CLASSIFY_API_URL=https://api.groq.com/openai/v1
CLASSIFY_API_KEY=your-groq-key
CLASSIFY_MODEL=llama-3.1-8b-instant

# Summary: Groq Llama 70B
SUMMARY_PROVIDER=openai
SUMMARY_API_URL=https://api.groq.com/openai/v1
SUMMARY_API_KEY=your-groq-key
SUMMARY_MODEL=llama-3.1-70b-versatile
```

### Quality Setup (Native Anthropic)

```bash
# Classification: Z.AI GLM-4
CLASSIFY_PROVIDER=openai
CLASSIFY_API_URL=https://api.z.ai/v1
CLASSIFY_API_KEY=your-zai-key
CLASSIFY_MODEL=glm-4

# Summary: Native Anthropic API
SUMMARY_PROVIDER=anthropic
SUMMARY_API_URL=https://api.anthropic.com/v1/messages
SUMMARY_API_KEY=your-anthropic-key
SUMMARY_MODEL=claude-sonnet-4-20250514
```

### All OpenRouter

```bash
# Both via OpenRouter
CLASSIFY_PROVIDER=openai
CLASSIFY_API_URL=https://openrouter.ai/api/v1
CLASSIFY_API_KEY=your-key
CLASSIFY_MODEL=meta-llama/llama-3-8b-instruct

SUMMARY_PROVIDER=openai
SUMMARY_API_URL=https://openrouter.ai/api/v1
SUMMARY_API_KEY=your-key
SUMMARY_MODEL=anthropic/claude-sonnet-4
```

### Fully Local (Ollama)

```bash
# Both local - completely free
CLASSIFY_PROVIDER=openai
CLASSIFY_API_URL=http://localhost:11434/v1
CLASSIFY_API_KEY=ollama
CLASSIFY_MODEL=llama3:8b

SUMMARY_PROVIDER=openai
SUMMARY_API_URL=http://localhost:11434/v1
SUMMARY_API_KEY=ollama
SUMMARY_MODEL=llama3:70b
```

### Memory Layer

The memory layer uses **two separate API keys** for different purposes:

```bash
# Embeddings: Converting text to vectors (REQUIRES OpenAI)
OPENAI_API_KEY=your-openai-api-key-for-embeddings

# Memory LLM: Orchestration and reasoning (can use any provider)
MEMORY_PROVIDER=openai
MEMORY_API_URL=https://api.openai.com/v1
MEMORY_API_KEY=your-openai-api-key-for-llm
MEMORY_MODEL=gpt-4o
```

**Why Two API Keys?**

| Key | Purpose | Model | Provider Options |
|-----|---------|-------|------------------|
| `OPENAI_API_KEY` | Embeddings (text → vectors) | `text-embedding-3-small` | **Must use OpenAI** |
| `MEMORY_API_KEY` | LLM orchestration (LangGraph) | Any model (e.g., `gpt-4o`) | **Any provider** |

**Embeddings (`OPENAI_API_KEY`):**
- Converts text into vector representations for semantic search
- OpenAI's `text-embedding-3-small` provides the best quality/cost ratio
- **Cannot use alternative providers** - the embedding model must be OpenAI's
- Embeddings are cached, so API calls are minimal after initial setup
- Your local machine only stores and searches vectors (~500MB RAM)

**Memory LLM (`MEMORY_API_KEY`):**
- Powers the LangGraph orchestration "brain"
- Handles reasoning, insights extraction, and memory processing
- **Can use any OpenAI-compatible provider** (OpenRouter, Groq, Ollama, etc.)
- Allows testing different models without breaking embeddings

**Example: Budget-Friendly Setup**

```bash
# Embeddings: OpenAI (required)
OPENAI_API_KEY=sk-your-openai-key

# Memory LLM: OpenRouter (more affordable)
MEMORY_PROVIDER=openai
MEMORY_API_URL=https://openrouter.ai/api/v1
MEMORY_API_KEY=your-openrouter-key
MEMORY_MODEL=meta-llama/llama-3-70b-instruct
```

**Example: Local LLM with Cloud Embeddings**

```bash
# Embeddings: OpenAI (required, cloud-based)
OPENAI_API_KEY=sk-your-openai-key

# Memory LLM: Ollama (local, free)
MEMORY_PROVIDER=openai
MEMORY_API_URL=http://localhost:11434/v1
MEMORY_API_KEY=ollama
MEMORY_MODEL=llama3:70b
```

## Adding New Providers

The LLM abstraction is in `bot/llm/`:

```
bot/llm/
├── __init__.py         # LLMClient interface, LLMResponse type
├── factory.py          # create_client() factory
├── openai_adapter.py   # OpenAI-compatible adapter
└── anthropic_adapter.py # Native Anthropic adapter
```

To add a new provider:

1. Create `bot/llm/newprovider_adapter.py` implementing `LLMClient`
2. Add to `factory.py` `create_client()` function
3. Use `PROVIDER=newprovider` in config

## Bot Settings

```bash
# Classification confidence threshold (0.0-1.0)
# Below this, bot asks for clarification
CONFIDENCE_THRESHOLD=0.6

# Optional: Per-category thresholds
CONFIDENCE_THRESHOLD_PEOPLE=0.7
CONFIDENCE_THRESHOLD_PROJECTS=0.6
CONFIDENCE_THRESHOLD_IDEAS=0.5
CONFIDENCE_THRESHOLD_ADMIN=0.65
```

### Tuning Thresholds

Check your stats:

```sql
SELECT
    DATE(created_at) as day,
    COUNT(*) FILTER (WHERE status = 'filed') as auto_filed,
    COUNT(*) FILTER (WHERE status = 'needs_review') as needed_review,
    COUNT(*) FILTER (WHERE status = 'fixed') as fixed,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE status = 'fixed') /
        NULLIF(COUNT(*) FILTER (WHERE status = 'filed'), 0),
        1
    ) as fix_rate_pct
FROM inbox_log
WHERE created_at > NOW() - INTERVAL '14 days'
GROUP BY DATE(created_at)
ORDER BY day;
```

| Observation | Action |
|-------------|--------|
| Fix rate > 15% | Increase threshold |
| Clarification rate > 30% | Decrease threshold |
| Target | <10% fix, <20% clarification |

## Admin UI Configuration

```bash
# Admin UI authentication
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-admin-password
```

The admin UI is accessible on port 8000 and requires HTTP Basic Auth.

**Security note:** The admin UI should only be exposed through Tailscale or a similar secure network. Do not expose it directly to the internet.

## Memory Layer Configuration

The memory layer provides semantic search and smart linking using Mem0, Qdrant, and LangGraph.

### Qdrant (Vector Database)

```bash
# Qdrant connection URL
QDRANT_URL=http://qdrant:6333

# For local development (outside Docker), use:
# QDRANT_URL=http://localhost:6333
```

### Memory Settings

```bash
# Collection name in Qdrant
MEM0_COLLECTION=leaknote_memories

# Number of memories to retrieve for context
MEMORY_RETRIEVAL_LIMIT=5

# Minimum similarity score for memory matches (0.0-1.0)
MEMORY_CONFIDENCE_THRESHOLD=0.7
```

### Tuning Memory Settings

| Setting | Default | Effect |
|---------|---------|--------|
| `MEMORY_RETRIEVAL_LIMIT` | 5 | More context = slower, more noise |
| `MEMORY_CONFIDENCE_THRESHOLD` | 0.7 | Higher = fewer but better matches |

**Recommended adjustments:**
- Increase `MEMORY_RETRIEVAL_LIMIT` to 7-10 if you want more related notes
- Decrease `MEMORY_CONFIDENCE_THRESHOLD` to 0.6 if too few links are suggested
- Increase `MEMORY_CONFIDENCE_THRESHOLD` to 0.8 if too many irrelevant links appear
