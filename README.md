# Leaknote

A self-hosted "second brain" that captures your thoughts via Matrix, classifies them with LLMs, and surfaces relevant information through daily digests and on-demand retrieval.

## Features

- **Frictionless capture**: One Matrix channel, one message per thought
- **AI classification**: Automatically routes to people, projects, ideas, admin
- **Reference storage**: Explicit prefixes for decisions, howtos, snippets
- **Daily digest**: Morning briefing with top actions (06:00)
- **Weekly review**: Sunday summary with patterns and suggestions (16:00)
- **On-demand retrieval**: `?recall`, `?search`, `?projects` commands
- **Trust mechanisms**: Confirmations, fix commands, audit log

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Matrix (Dendrite)                                              │
│  ├── #leaknote-inbox (capture)                                  │
│  └── DM (digests, confirmations)                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Leaknote Bot (Python)                                          │
│  ├── Classifier (GLM-4 for routing)                             │
│  ├── Router (prefix detection + confidence check)               │
│  └── Surfacer (Claude for summaries)                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PostgreSQL                                                     │
│  ├── people, projects, ideas, admin (dynamic)                   │
│  ├── decisions, howtos, snippets (reference)                    │
│  └── inbox_log (audit trail)                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start (Docker)

### Prerequisites

- Docker and Docker Compose
- API keys for GLM-4 (or similar) and Claude

### 1. Clone and configure

```bash
git clone <repo-url> leaknote
cd leaknote

cp .env.example .env
# Edit .env with your passwords and API keys
```

### 2. Run setup

```bash
chmod +x setup.sh create-users.sh
./setup.sh
```

This generates Dendrite keys, configuration, and initializes the database scripts.

### 3. Start the stack

```bash
docker compose up -d
docker compose ps  # Wait for all services to be healthy
```

### 4. Create Matrix users

```bash
./create-users.sh
```

Creates the bot user and your personal user.

### 5. Configure Matrix room

1. Connect to Matrix with Element: `http://localhost:8008`
2. Log in with your credentials
3. Create a private room named `leaknote-inbox`
4. Invite the bot user
5. Restart the bot: `docker compose restart leaknote`

### 6. Install cron jobs

```bash
crontab -e
# Add entries from crontab.example
```

### 7. Test it

Send a message to `#leaknote-inbox`:

```
Met João at conference, works on EHR integration
```

Bot should reply with a confirmation.

## Usage

### Capture (Dynamic Categories)

Just type naturally - the AI classifies automatically:

```
Met João at conference, works on EHR integration
→ Classified as: people

Need to review nftables rules this week  
→ Classified as: projects

Could use Matrix reactions for quick triage
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
?search <query>     Search all categories
?people <query>     Search people
?projects [status]  List projects (optionally filter by active/waiting/blocked)
?ideas              List recent ideas
?admin [due]        List admin tasks (optionally only those with due dates)
```

### Fix Mistakes

Reply to any bot confirmation with:

```
fix: people
fix: project
fix: idea
```

## Configuration

See [docs/configuration.md](docs/configuration.md) for:

- Environment variables reference
- Dendrite configuration
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
│   ├── router.py           # Message routing
│   ├── responder.py        # Matrix responses
│   ├── commands.py         # Query commands
│   ├── queries.py          # Database queries
│   ├── digest.py           # Daily digest
│   └── weekly_review.py    # Weekly review
├── scripts/                # Cron scripts
│   ├── daily_digest.py
│   ├── weekly_review.py
│   ├── maintenance.py
│   └── health_check.py
├── prompts/                # LLM prompts
│   ├── classify.md
│   ├── daily.md
│   ├── weekly.md
│   └── retrieval.md
├── docs/                   # Documentation
│   ├── architecture.md
│   ├── configuration.md
│   └── operations.md
├── docker-compose.yml
├── Dockerfile
├── schema.sql
├── requirements.txt
├── setup.sh
├── create-users.sh
└── crontab.example
```

## License

MIT
