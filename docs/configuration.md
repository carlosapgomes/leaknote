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

# Dendrite database credentials (used by init-db.sh at runtime)
DENDRITE_DB_PASSWORD=your-dendrite-db-password
```

### Matrix / Dendrite

```bash
# Your Matrix domain (used in user IDs like @user:domain)
MATRIX_SERVER_NAME=localhost

# Bot user credentials
MATRIX_USER_ID=@leaknote:localhost
MATRIX_PASSWORD=bot-password

# Inbox room alias
MATRIX_INBOX_ROOM=#leaknote-inbox:localhost

# Your user ID (receives digests)
DIGEST_TARGET_USER=@carlos:localhost
```

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

## Dendrite Configuration

After running `setup.sh`, Dendrite config is at `dendrite/config/dendrite.yaml`.

The config is generated from `dendrite/config/dendrite.yaml.template` using values from `.env`:

- `MATRIX_SERVER_NAME` - Your Matrix domain
- `DENDRITE_DB_PASSWORD` - Database password (from .env)
- `DENDRITE_REGISTRATION_SECRET` - Registration secret (auto-generated if not set)

**Security note:** The template file is safe to commit to git. The generated `dendrite.yaml` contains sensitive data and is excluded by `.gitignore`.

Key settings:

```yaml
global:
  server_name: localhost  # Must match MATRIX_SERVER_NAME
  database:
    connection_string: postgres://dendrite:password@postgres/dendrite?sslmode=disable

client_api:
  registration_disabled: true  # Set false to allow Element registration
  registration_shared_secret: "auto-generated-or-set-in-env"
```

## Network Configuration

### Docker Internal Network

| Service | Internal Hostname | Port |
|---------|-------------------|------|
| PostgreSQL | `postgres` | 5432 |
| Dendrite | `dendrite` | 8008, 8448 |
| Leaknote | `leaknote` | - |

### External Access

| Port | Service | Purpose |
|------|---------|---------|
| 8008 | Dendrite | Matrix client API |
| 8448 | Dendrite | Federation (optional) |

### Local Network Access

1. Update `MATRIX_SERVER_NAME` to your server's IP
2. Update `dendrite/config/dendrite.yaml` server_name
3. Connect Element to `http://YOUR_IP:8008`
