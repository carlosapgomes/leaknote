# Docker Compose Deployment

Complete containerized deployment of the second brain system **including a self-hosted Dendrite Matrix server**.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         HOST                                     │
│                                                                  │
│   Cron Jobs ──────────────────────────────┐                     │
│   ├── daily_digest.sh                     │                     │
│   ├── weekly_review.sh                    │ docker exec         │
│   └── maintenance.sh                      ▼                     │
│                                    ┌─────────────┐              │
│                                    │  secondbrain │              │
│                                    │  container   │              │
│                                    └──────┬──────┘              │
│                                           │                      │
│   ┌───────────────────────────────────────┼──────────────────┐  │
│   │              Docker Network           │                   │  │
│   │                                       │                   │  │
│   │   ┌─────────────┐    ┌────────────┐  │                   │  │
│   │   │  postgres   │◄───│  dendrite  │◄─┘                   │  │
│   │   │             │    │  (Matrix)  │◄── Element client    │  │
│   │   └─────────────┘    └────────────┘   (port 8008)        │  │
│   │         │                  │                              │  │
│   │         ▼                  ▼                              │  │
│   │   ./data/postgres    ./dendrite/                         │  │
│   │                      ├── config/                         │  │
│   │                      ├── media/                          │  │
│   │                      └── jetstream/                      │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ./data/backups (host backup directory)                        │
│   ./logs (host log directory)                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## What's Included

| Service | Purpose | Port |
|---------|---------|------|
| **postgres** | Shared database for Dendrite + Second Brain | 5432 (internal) |
| **dendrite** | Matrix homeserver | 8008 (client API), 8448 (federation) |
| **secondbrain** | Bot that captures, classifies, surfaces | - |

## Directory Structure

```
second-brain/
├── docker-compose.yml
├── Dockerfile
├── .env                      # Environment variables
├── .env.example              # Template
├── init-db.sql               # Creates both databases
├── schema.sql                # Second Brain tables
├── setup.sh                  # One-time setup script
├── create-users.sh           # Create Matrix users
├── bot/
│   └── ... (Python code)
├── scripts/
│   └── ... (digest, review scripts)
├── cron/                     # Host cron scripts
│   └── ...
├── dendrite/                 # Dendrite data (created by setup.sh)
│   ├── config/
│   │   ├── dendrite.yaml
│   │   └── matrix_key.pem
│   ├── media/
│   ├── jetstream/
│   └── searchindex/
├── data/
│   ├── postgres/
│   └── backups/
└── logs/
```

## Quick Start

### Step 1: Clone and Configure

```bash
cd second-brain/docker
cp .env.example .env
# Edit .env with your settings (especially passwords and API keys)
```

### Step 2: Run Setup Script

```bash
chmod +x setup.sh create-users.sh
./setup.sh
```

This will:
- Create all necessary directories
- Generate Dendrite signing key
- Generate Dendrite configuration
- Update init-db.sql with your passwords

### Step 3: Start the Stack

```bash
docker compose up -d
```

Wait for all services to be healthy:

```bash
docker compose ps
```

### Step 4: Create Matrix Users

```bash
./create-users.sh
```

This creates:
- Bot user (e.g., `@secondbrain:localhost`)
- Your user (e.g., `@carlos:localhost`) as admin

### Step 5: Configure Matrix Room

1. Connect to your Matrix server with Element:
   - Homeserver URL: `http://localhost:8008` (or your server's address)
   - Log in with your user credentials

2. Create a private room named `sb-inbox`

3. Invite the bot user to the room

4. Update `.env` with the room alias if needed

5. Restart the bot:
   ```bash
   docker compose restart secondbrain
   ```

### Step 6: Install Cron Jobs

```bash
crontab -e
# Add entries from crontab.example
```

## Detailed Configuration

### Environment Variables

Create `.env` from `.env.example`:

```bash
# ===================
# PostgreSQL (shared)
# ===================
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres-admin-password-change-me

# Second Brain DB credentials
SECONDBRAIN_DB_PASSWORD=secondbrain-password-change-me

# Dendrite DB credentials
DENDRITE_DB_PASSWORD=dendrite-password-change-me

# ===================
# Dendrite Matrix Server
# ===================
# Your Matrix domain
MATRIX_SERVER_NAME=localhost

# ===================
# Matrix Bot Configuration  
# ===================
MATRIX_USER_ID=@secondbrain:localhost
MATRIX_PASSWORD=bot-password-here
MATRIX_INBOX_ROOM=#sb-inbox:localhost

# Your user (where digests are sent)
DIGEST_TARGET_USER=@carlos:localhost

# ===================
# LLM APIs
# ===================
GLM_API_URL=https://api.z.ai/v1/chat/completions
GLM_API_KEY=your-glm-key
GLM_MODEL=glm-4

CLAUDE_API_URL=https://api.anthropic.com/v1/messages
CLAUDE_API_KEY=your-claude-key
CLAUDE_MODEL=claude-sonnet-4-20250514

# ===================
# Settings
# ===================
CONFIDENCE_THRESHOLD=0.6
```

### Dendrite Configuration

After running `setup.sh`, review `dendrite/config/dendrite.yaml`:

Key settings to check:

```yaml
global:
  server_name: localhost  # Your Matrix domain
  
  database:
    connection_string: postgres://dendrite:YOUR_PASSWORD@postgres/dendrite?sslmode=disable

client_api:
  # Set to false if you want to allow user registration via Element
  registration_disabled: true
```

### Database Initialization

The `init-db.sql` script creates both databases:

```sql
-- Dendrite database
CREATE USER dendrite WITH PASSWORD 'your-dendrite-password';
CREATE DATABASE dendrite OWNER dendrite;

-- Second Brain database
CREATE USER secondbrain WITH PASSWORD 'your-secondbrain-password';
CREATE DATABASE secondbrain OWNER secondbrain;
```

**Important**: The passwords in `init-db.sql` must match:
- Dendrite: password in `dendrite.yaml` connection string
- Second Brain: `SECONDBRAIN_DB_PASSWORD` in `.env`

The `setup.sh` script handles this automatically.

## Management Commands

### Service Control

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart specific service
docker compose restart secondbrain
docker compose restart dendrite

# View logs
docker compose logs -f secondbrain
docker compose logs -f dendrite
docker compose logs -f postgres
```

### Matrix Administration

```bash
# Create a new user
docker exec -it dendrite-matrix /usr/bin/create-account \
    -config /etc/dendrite/dendrite.yaml \
    -username newuser \
    -password "password"

# Create an admin user
docker exec -it dendrite-matrix /usr/bin/create-account \
    -config /etc/dendrite/dendrite.yaml \
    -username admin \
    -password "password" \
    -admin
```

### Database Access

```bash
# Connect to Second Brain database
docker exec -it secondbrain-db psql -U secondbrain -d secondbrain

# Connect to Dendrite database
docker exec -it secondbrain-db psql -U dendrite -d dendrite

# Run a query
docker exec secondbrain-db psql -U secondbrain -d secondbrain \
    -c "SELECT * FROM inbox_log ORDER BY created_at DESC LIMIT 10;"
```

### Execute Bot Scripts

```bash
# Run daily digest
docker exec secondbrain-bot python scripts/daily_digest.py

# Run weekly review
docker exec secondbrain-bot python scripts/weekly_review.py

# Health check
docker exec secondbrain-bot python scripts/health_check.py
```

## Cron Jobs

Host scripts that execute inside containers:

```bash
# Daily digest at 6:00 AM
0 6 * * * /path/to/second-brain/cron/daily_digest.sh

# Weekly review Sunday at 4:00 PM
0 16 * * 0 /path/to/second-brain/cron/weekly_review.sh

# Weekly maintenance Sunday at 11:00 PM
0 23 * * 0 /path/to/second-brain/cron/maintenance.sh

# Daily backup at 2:00 AM
0 2 * * * /path/to/second-brain/cron/backup.sh

# Health check every 5 minutes
*/5 * * * * /path/to/second-brain/cron/health_check.sh >> /path/to/logs/health.log 2>&1
```

## Backup & Restore

### Backup

The `cron/backup.sh` script backs up both databases:

```bash
# Manual backup
./cron/backup.sh

# Backups are stored in data/backups/
ls -la data/backups/
```

### Restore

```bash
# Restore Second Brain database
gunzip -c data/backups/secondbrain_20260110.sql.gz | \
    docker exec -i secondbrain-db psql -U secondbrain -d secondbrain

# Restore Dendrite database (if needed)
gunzip -c data/backups/dendrite_20260110.sql.gz | \
    docker exec -i secondbrain-db psql -U dendrite -d dendrite
```

## Exposing to the Network

### Local Network Access

By default, Dendrite is accessible at `localhost:8008`. To access from other devices on your network:

1. Find your server's IP (e.g., `192.168.1.100`)
2. Update `.env`:
   ```
   MATRIX_SERVER_NAME=192.168.1.100
   ```
3. Regenerate Dendrite config or edit `dendrite/config/dendrite.yaml`
4. Restart: `docker compose restart dendrite`
5. Connect Element to `http://192.168.1.100:8008`

### Public Access (with Reverse Proxy)

For public access, you'll need:
1. A domain name
2. A reverse proxy (nginx, Caddy, Traefik)
3. SSL certificates

Example nginx configuration:

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

# Federation (optional)
server {
    listen 8448 ssl http2;
    server_name matrix.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8448;
        proxy_set_header Host $host;
    }
}
```

## Troubleshooting

### Dendrite won't start

```bash
# Check logs
docker compose logs dendrite

# Common issues:
# - Database connection failed (check password in dendrite.yaml)
# - Missing matrix_key.pem (run setup.sh)
# - Config syntax error (validate YAML)
```

### Bot can't connect to Matrix

```bash
# Check if Dendrite is healthy
curl http://localhost:8008/_matrix/client/versions

# Check bot logs
docker compose logs secondbrain

# Common issues:
# - Wrong homeserver URL (should be http://dendrite:8008 inside Docker)
# - User doesn't exist (run create-users.sh)
# - Wrong password in .env
```

### Can't create rooms or users

```bash
# Check Dendrite logs for errors
docker compose logs dendrite | grep -i error

# Verify database connection
docker exec secondbrain-db psql -U dendrite -d dendrite -c "SELECT 1"
```

### Bot not receiving messages

1. Verify bot is in the room (check room members in Element)
2. Check room alias matches `MATRIX_INBOX_ROOM` in `.env`
3. Check bot logs for sync errors

## Production Checklist

- [ ] All passwords are strong and unique
- [ ] `.env` has `chmod 600`
- [ ] Dendrite `server_name` is set correctly
- [ ] Database passwords match between `.env`, `init-db.sql`, and `dendrite.yaml`
- [ ] Bot user created and password in `.env`
- [ ] Inbox room created and bot invited
- [ ] Cron jobs installed
- [ ] Backups configured and tested
- [ ] Health check alerts configured (optional)
- [ ] Reverse proxy configured (if public access needed)

## Step 1: Dockerfile

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash secondbrain

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=secondbrain:secondbrain bot/ ./bot/
COPY --chown=secondbrain:secondbrain scripts/ ./scripts/
COPY --chown=secondbrain:secondbrain schema.sql .

# Make scripts executable
RUN chmod +x scripts/*.py scripts/*.sh 2>/dev/null || true

# Switch to non-root user
USER secondbrain

# Default command: run the bot
CMD ["python", "bot/main.py"]
```

## Step 2: Requirements

Create `requirements.txt`:

```
matrix-nio[e2e]==0.24.0
asyncpg==0.29.0
httpx==0.27.0
python-dotenv==1.0.1
```

## Step 3: Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: secondbrain-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-secondbrain}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}
      POSTGRES_DB: ${POSTGRES_DB:-secondbrain}
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
      - ./schema.sql:/docker-entrypoint-initdb.d/schema.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-secondbrain} -d ${POSTGRES_DB:-secondbrain}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - secondbrain-net

  secondbrain:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: secondbrain-bot
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      # Matrix
      MATRIX_HOMESERVER: ${MATRIX_HOMESERVER:?MATRIX_HOMESERVER required}
      MATRIX_USER_ID: ${MATRIX_USER_ID:?MATRIX_USER_ID required}
      MATRIX_PASSWORD: ${MATRIX_PASSWORD:?MATRIX_PASSWORD required}
      MATRIX_INBOX_ROOM: ${MATRIX_INBOX_ROOM:?MATRIX_INBOX_ROOM required}
      
      # Database (internal Docker network)
      DATABASE_URL: postgresql://${POSTGRES_USER:-secondbrain}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-secondbrain}
      
      # LLM APIs
      GLM_API_URL: ${GLM_API_URL:?GLM_API_URL required}
      GLM_API_KEY: ${GLM_API_KEY:?GLM_API_KEY required}
      GLM_MODEL: ${GLM_MODEL:-glm-4}
      
      CLAUDE_API_URL: ${CLAUDE_API_URL:-https://api.anthropic.com/v1/messages}
      CLAUDE_API_KEY: ${CLAUDE_API_KEY:?CLAUDE_API_KEY required}
      CLAUDE_MODEL: ${CLAUDE_MODEL:-claude-sonnet-4-20250514}
      
      # Settings
      CONFIDENCE_THRESHOLD: ${CONFIDENCE_THRESHOLD:-0.6}
      DIGEST_TARGET_USER: ${DIGEST_TARGET_USER:?DIGEST_TARGET_USER required}
    volumes:
      # Mount logs directory
      - ./logs:/app/logs
    networks:
      - secondbrain-net

networks:
  secondbrain-net:
    driver: bridge
```

## Step 4: Environment File

Create `.env.example`:

```bash
# ===================
# PostgreSQL
# ===================
POSTGRES_USER=secondbrain
POSTGRES_PASSWORD=change-this-secure-password
POSTGRES_DB=secondbrain

# ===================
# Matrix
# ===================
MATRIX_HOMESERVER=https://matrix.yourdomain.com
MATRIX_USER_ID=@secondbrain:yourdomain.com
MATRIX_PASSWORD=bot-password-here
MATRIX_INBOX_ROOM=#sb-inbox:yourdomain.com

# ===================
# LLM APIs
# ===================
# GLM-4 (for classification)
GLM_API_URL=https://api.z.ai/v1/chat/completions
GLM_API_KEY=your-glm-key
GLM_MODEL=glm-4

# Claude (for summaries)
CLAUDE_API_URL=https://api.anthropic.com/v1/messages
CLAUDE_API_KEY=your-claude-key
CLAUDE_MODEL=claude-sonnet-4-20250514

# ===================
# Settings
# ===================
CONFIDENCE_THRESHOLD=0.6
DIGEST_TARGET_USER=@carlos:yourdomain.com
```

Copy and configure:

```bash
cp .env.example .env
chmod 600 .env
# Edit .env with your values
```

## Step 5: Entrypoint Script

Create `scripts/entrypoint.sh`:

```bash
#!/bin/bash
set -e

# Wait for database to be ready (backup check)
until pg_isready -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
  echo "Waiting for PostgreSQL..."
  sleep 2
done

echo "PostgreSQL is ready"

# Execute the command passed to the container
exec "$@"
```

Update Dockerfile to use entrypoint:

```dockerfile
# Add before CMD
COPY --chown=secondbrain:secondbrain scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

## Step 6: Host Cron Scripts

These scripts run on the **host** and execute commands inside the container.

Create `cron/daily_digest.sh`:

```bash
#!/bin/bash
# Daily digest - runs at 06:00
# Executes inside the secondbrain container

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/daily_digest.log"

echo "========================================" >> "$LOG_FILE"
echo "Daily Digest - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

docker exec secondbrain-bot python scripts/daily_digest.py >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "ERROR: Daily digest failed with exit code $EXIT_CODE" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
```

Create `cron/weekly_review.sh`:

```bash
#!/bin/bash
# Weekly review - runs Sunday at 16:00
# Executes inside the secondbrain container

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/weekly_review.log"

echo "========================================" >> "$LOG_FILE"
echo "Weekly Review - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

docker exec secondbrain-bot python scripts/weekly_review.py >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "ERROR: Weekly review failed with exit code $EXIT_CODE" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
```

Create `cron/maintenance.sh`:

```bash
#!/bin/bash
# Weekly maintenance - runs Sunday at 23:00
# Executes inside the secondbrain container

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/maintenance.log"

echo "========================================" >> "$LOG_FILE"
echo "Weekly Maintenance - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

docker exec secondbrain-bot python scripts/weekly_maintenance.py >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "ERROR: Maintenance failed with exit code $EXIT_CODE" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
```

Create `cron/backup.sh`:

```bash
#!/bin/bash
# Database backup - runs daily at 02:00
# Uses pg_dump from the postgres container

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/data/backups"
LOG_FILE="$PROJECT_DIR/logs/backup.log"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="secondbrain_$DATE.sql.gz"

# Create backup directory if needed
mkdir -p "$BACKUP_DIR"

echo "========================================" >> "$LOG_FILE"
echo "Backup - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Get database credentials from .env
source "$PROJECT_DIR/.env"

# Run pg_dump inside postgres container and compress
docker exec secondbrain-db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_DIR/$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "Backup created: $BACKUP_FILE" >> "$LOG_FILE"
    
    # Keep only last 30 days of backups
    find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete
    echo "Old backups cleaned up" >> "$LOG_FILE"
else
    echo "ERROR: Backup failed" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
```

Create `cron/health_check.sh`:

```bash
#!/bin/bash
# Health check - runs every 5 minutes
# Checks if containers are running and healthy

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check if bot container is running
if ! docker ps --format '{{.Names}}' | grep -q '^secondbrain-bot$'; then
    echo "UNHEALTHY: secondbrain-bot container not running"
    exit 1
fi

# Check if postgres container is running
if ! docker ps --format '{{.Names}}' | grep -q '^secondbrain-db$'; then
    echo "UNHEALTHY: secondbrain-db container not running"
    exit 1
fi

# Run health check inside bot container
docker exec secondbrain-bot python scripts/health_check.py

exit $?
```

Make all scripts executable:

```bash
chmod +x cron/*.sh
```

## Step 7: Create Directories

```bash
mkdir -p data/postgres data/backups logs
touch logs/.gitkeep data/.gitkeep

# Add to .gitignore
cat >> .gitignore << 'EOF'
.env
data/postgres/
data/backups/*.sql.gz
logs/*.log
__pycache__/
*.pyc
EOF
```

## Step 8: Deploy

### 8.1 Build and Start

```bash
# Build the image
docker compose build

# Start services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f secondbrain
```

### 8.2 Verify Database Schema

The schema is automatically applied on first start via the init script. Verify:

```bash
docker exec secondbrain-db psql -U secondbrain -d secondbrain -c "\dt"
```

Should show all tables: people, projects, ideas, admin, decisions, howtos, snippets, inbox_log, pending_clarifications.

### 8.3 Test the Bot

Send a test message to your `#sb-inbox` Matrix room. Check logs:

```bash
docker compose logs -f secondbrain
```

### 8.4 Install Host Cron Jobs

```bash
crontab -e
```

Add (adjust paths to your installation):

```
# Second Brain Cron Jobs (Docker)
# ================================

# Daily digest at 6:00 AM
0 6 * * * /path/to/second-brain/cron/daily_digest.sh

# Weekly review Sunday at 4:00 PM
0 16 * * 0 /path/to/second-brain/cron/weekly_review.sh

# Weekly maintenance Sunday at 11:00 PM
0 23 * * 0 /path/to/second-brain/cron/maintenance.sh

# Daily backup at 2:00 AM
0 2 * * * /path/to/second-brain/cron/backup.sh

# Health check every 5 minutes (optional)
*/5 * * * * /path/to/second-brain/cron/health_check.sh > /dev/null 2>&1 || echo "Second brain unhealthy" | mail -s "Alert" you@example.com
```

### 8.5 Test Cron Scripts Manually

```bash
# Test daily digest
./cron/daily_digest.sh
cat logs/daily_digest.log

# Test backup
./cron/backup.sh
ls -la data/backups/
```

## Step 9: Management Commands

### View Logs

```bash
# Bot logs (real-time)
docker compose logs -f secondbrain

# Cron job logs
tail -f logs/daily_digest.log
tail -f logs/weekly_review.log
tail -f logs/backup.log
```

### Restart Services

```bash
# Restart bot only
docker compose restart secondbrain

# Restart everything
docker compose restart

# Full rebuild
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Database Access

```bash
# Connect to database
docker exec -it secondbrain-db psql -U secondbrain -d secondbrain

# Run a query
docker exec secondbrain-db psql -U secondbrain -d secondbrain -c "SELECT * FROM inbox_log ORDER BY created_at DESC LIMIT 10;"
```

### Execute Scripts Manually

```bash
# Run daily digest
docker exec secondbrain-bot python scripts/daily_digest.py

# Run weekly review
docker exec secondbrain-bot python scripts/weekly_review.py

# Run maintenance
docker exec secondbrain-bot python scripts/weekly_maintenance.py

# Health check
docker exec secondbrain-bot python scripts/health_check.py
```

### Backup & Restore

```bash
# Manual backup
./cron/backup.sh

# Restore from backup
gunzip -c data/backups/secondbrain_20260110_020000.sql.gz | docker exec -i secondbrain-db psql -U secondbrain -d secondbrain
```

## Step 10: Updates

### Update Application Code

```bash
# Pull new code (if using git)
git pull

# Rebuild and restart
docker compose build
docker compose up -d
```

### Update Base Image

```bash
# Pull latest Python image
docker compose pull

# Rebuild
docker compose build --no-cache
docker compose up -d
```

### Database Migrations

```bash
# Run migration SQL inside container
docker exec -i secondbrain-db psql -U secondbrain -d secondbrain < migrations/001_add_column.sql

# Or interactively
docker exec -it secondbrain-db psql -U secondbrain -d secondbrain
# Then run your ALTER TABLE statements
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs secondbrain

# Common issues:
# - Database not ready (check postgres health)
# - Invalid environment variables
# - Network connectivity issues
```

### Database connection refused

```bash
# Check postgres is running
docker compose ps postgres

# Check postgres logs
docker compose logs postgres

# Verify network
docker network inspect second-brain_secondbrain-net
```

### Cron jobs not running

```bash
# Check cron service
systemctl status cron

# Check cron logs
grep CRON /var/log/syslog

# Test script manually
./cron/daily_digest.sh
```

### Permission issues

```bash
# Fix log directory permissions
chmod 755 logs/
touch logs/daily_digest.log logs/weekly_review.log logs/backup.log logs/maintenance.log
chmod 644 logs/*.log
```

## Production Checklist

- [ ] `.env` has strong, unique passwords
- [ ] `.env` has `chmod 600`
- [ ] All cron scripts are executable (`chmod +x`)
- [ ] Log directory exists and is writable
- [ ] Backup directory exists
- [ ] Cron jobs installed on host
- [ ] Health check alerts configured
- [ ] Docker set to restart on boot (`docker compose up -d` in `/etc/rc.local` or systemd)
- [ ] Tested manual execution of all cron scripts
- [ ] Tested database restore procedure

## Docker Compose Commands Reference

| Command | Description |
|---------|-------------|
| `docker compose up -d` | Start all services |
| `docker compose down` | Stop all services |
| `docker compose restart` | Restart all services |
| `docker compose logs -f` | Follow logs |
| `docker compose ps` | Show running containers |
| `docker compose build` | Rebuild images |
| `docker compose exec secondbrain bash` | Shell into bot container |
| `docker compose exec postgres psql -U secondbrain` | Database shell |
