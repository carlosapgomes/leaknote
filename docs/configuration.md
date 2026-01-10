# Configuration

## Environment Variables

All configuration is done through environment variables in `.env`.

### PostgreSQL

```bash
# Shared PostgreSQL admin
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-admin-password

# Leaknote database credentials
LEAKNOTE_DB_PASSWORD=your-leaknote-db-password

# Dendrite database credentials  
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

### LLM APIs

```bash
# GLM-4 (for classification - cheap, fast)
GLM_API_URL=https://api.z.ai/v1/chat/completions
GLM_API_KEY=your-glm-key
GLM_MODEL=glm-4

# Claude (for summaries and retrieval - quality matters)
CLAUDE_API_URL=https://api.anthropic.com/v1/messages
CLAUDE_API_KEY=your-claude-key
CLAUDE_MODEL=claude-sonnet-4-20250514
```

### Bot Settings

```bash
# Classification confidence threshold (0.0-1.0)
# Below this, bot asks for clarification
CONFIDENCE_THRESHOLD=0.6
```

## Dendrite Configuration

After running `setup.sh`, the Dendrite configuration is at `dendrite/config/dendrite.yaml`.

### Key Settings

```yaml
global:
  # Must match MATRIX_SERVER_NAME
  server_name: localhost
  
  # Database connection (password must match DENDRITE_DB_PASSWORD)
  database:
    connection_string: postgres://dendrite:your-password@postgres/dendrite?sslmode=disable

client_api:
  # Set to false to allow user registration via Element
  # Set to true to only allow creation via create-users.sh
  registration_disabled: true
```

### Federation (Optional)

If you want to federate with other Matrix servers:

1. Set `server_name` to your public domain
2. Configure port 8448 forwarding
3. Set up SSL certificates
4. Configure DNS SRV records

For local-only use, leave federation disabled.

## LLM Model Selection

### Classification (GLM-4)

Classification needs to be fast and cheap since it runs on every capture. Recommended models:

| Model | Speed | Cost | Accuracy |
|-------|-------|------|----------|
| GLM-4 (Z.AI) | Fast | Very low | Good |
| GPT-3.5-turbo | Fast | Low | Good |
| Claude Haiku | Fast | Low | Very good |
| Local (Llama 3) | Varies | Free | Moderate |

### Summaries (Claude)

Digests and retrieval benefit from higher quality. Recommended:

| Model | Quality | Cost |
|-------|---------|------|
| Claude Sonnet | Excellent | Moderate |
| Claude Opus | Best | Higher |
| GPT-4o | Excellent | Moderate |

## Confidence Threshold Tuning

The default threshold is 0.6. Adjust based on your experience:

### Check Your Stats

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

### Tuning Guidelines

| Observation | Action |
|-------------|--------|
| Fix rate > 15% | Increase threshold to 0.7 |
| Clarification rate > 30% | Decrease threshold to 0.5 |
| Target | <10% fix rate, <20% clarification rate |

### Per-Category Thresholds (Advanced)

If one category has more errors, you can set per-category thresholds in `bot/config.py`:

```python
CONFIDENCE_THRESHOLDS = {
    "people": 0.7,      # Higher - misclassifying people is annoying
    "projects": 0.6,
    "ideas": 0.5,       # Lower - ideas are low-stakes
    "admin": 0.65,
}
```

## Database Schema

The database schema is defined in `schema.sql`. Key tables:

### Dynamic Categories

```sql
people (id, name, context, follow_ups, last_touched, tags, created_at, updated_at)
projects (id, name, status, next_action, notes, tags, created_at, updated_at)
ideas (id, title, one_liner, elaboration, tags, created_at, updated_at)
admin (id, name, due_date, status, notes, tags, created_at, updated_at)
```

### Reference Categories

```sql
decisions (id, title, decision, rationale, context, tags, created_at)
howtos (id, title, content, tags, created_at, updated_at)
snippets (id, title, content, tags, created_at, updated_at)
```

### System Tables

```sql
inbox_log (id, raw_text, destination, record_id, confidence, status, matrix_event_id, matrix_room_id, created_at)
pending_clarifications (id, inbox_log_id, matrix_event_id, matrix_room_id, suggested_category, created_at)
```

## Network Configuration

### Docker Internal Network

Services communicate via Docker network:

| Service | Internal Hostname | Port |
|---------|-------------------|------|
| PostgreSQL | `postgres` | 5432 |
| Dendrite | `dendrite` | 8008, 8448 |
| Leaknote | `leaknote` | - |

### External Access

| Port | Service | Purpose |
|------|---------|---------|
| 8008 | Dendrite | Matrix client API (Element connects here) |
| 8448 | Dendrite | Matrix federation (optional) |

### Exposing to Local Network

To access from other devices:

1. Update `MATRIX_SERVER_NAME` to your server's IP
2. Update `dendrite/config/dendrite.yaml` server_name
3. Connect Element to `http://YOUR_IP:8008`

### Public Access (Reverse Proxy)

For public access, put a reverse proxy in front:

```nginx
server {
    listen 443 ssl http2;
    server_name matrix.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8008;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
