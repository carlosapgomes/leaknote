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

Leaknote uses two LLM clients with different roles:

| Client | Purpose | Characteristics |
|--------|---------|-----------------|
| **Classify** | Route incoming thoughts | Cheap, fast, runs frequently |
| **Summary** | Digests, reviews, retrieval | Quality matters, less frequent |

### Provider Types

Both clients support two provider types:

- `openai` - Works with any OpenAI-compatible API
- `anthropic` - Native Anthropic API (for Claude-specific features)

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

# Summary: Native Claude API
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
