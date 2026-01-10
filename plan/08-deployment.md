# Deployment Guide

Complete deployment instructions for the self-hosted second brain.

## Prerequisites

- Debian Bookworm (or similar Linux)
- PostgreSQL 15+
- Python 3.11+
- A Matrix homeserver (Dendrite recommended for single-user)
- API keys for GLM-4 and Claude

## 1. System Setup

### 1.1 Install Dependencies

```bash
# System packages
sudo apt update
sudo apt install -y postgresql python3 python3-venv python3-pip git

# Create user for the service (optional, can use your own user)
# sudo useradd -m -s /bin/bash secondbrain
```

### 1.2 PostgreSQL Setup

```bash
# Create database and user
sudo -u postgres psql <<EOF
CREATE USER secondbrain WITH PASSWORD 'your-secure-password-here';
CREATE DATABASE secondbrain OWNER secondbrain;
GRANT ALL PRIVILEGES ON DATABASE secondbrain TO secondbrain;
EOF

# Test connection
psql -U secondbrain -d secondbrain -c "SELECT 1"
```

### 1.3 Matrix Bot User

On your Dendrite/Synapse server, create a bot user:

```bash
# For Dendrite
./dendrite-monolith-server --config dendrite.yaml create-account -username secondbrain -password 'bot-password'

# Or via Matrix client - register normally
```

Create the inbox room:
1. Log in as bot user
2. Create private room named `sb-inbox`
3. Note the room alias (e.g., `#sb-inbox:yourdomain.com`)
4. Invite yourself to the room

## 2. Application Setup

### 2.1 Clone and Configure

```bash
# Clone (or create directory structure)
mkdir -p ~/second-brain
cd ~/second-brain

# Create structure
mkdir -p bot scripts prompts

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install matrix-nio[e2e] asyncpg httpx python-dotenv
```

### 2.2 Environment Configuration

Create `.env`:

```bash
# Matrix
MATRIX_HOMESERVER=https://matrix.yourdomain.com
MATRIX_USER_ID=@secondbrain:yourdomain.com
MATRIX_PASSWORD=bot-password-here
MATRIX_INBOX_ROOM=#sb-inbox:yourdomain.com

# Database
DATABASE_URL=postgresql://secondbrain:your-db-password@localhost/secondbrain

# LLM APIs
GLM_API_URL=https://api.z.ai/v1/chat/completions
GLM_API_KEY=your-glm-key
GLM_MODEL=glm-4

CLAUDE_API_URL=https://api.anthropic.com/v1/messages
CLAUDE_API_KEY=your-claude-key
CLAUDE_MODEL=claude-sonnet-4-20250514

# Settings
CONFIDENCE_THRESHOLD=0.6
DIGEST_TARGET_USER=@carlos:yourdomain.com
```

Secure the file:

```bash
chmod 600 .env
```

### 2.3 Database Schema

Create `schema.sql` (from Phase 1 documentation) and apply:

```bash
psql -U secondbrain -d secondbrain -f schema.sql
```

### 2.4 Copy Bot Code

Copy all Python files from the phase documentation into the `bot/` directory:
- `config.py`
- `db.py`
- `classifier.py`
- `router.py`
- `responder.py`
- `fix_handler.py`
- `commands.py`
- `queries.py`
- `digest.py`
- `weekly_review.py`
- `main.py`

Copy scripts into `scripts/`:
- `daily_digest.py`
- `weekly_review.py`
- `weekly_maintenance.py`
- `restart_brain.py`
- `health_check.py`
- `backup.sh`

## 3. Systemd Service

### 3.1 Create Service File

Create `~/.config/systemd/user/second-brain.service`:

```bash
mkdir -p ~/.config/systemd/user
```

```ini
[Unit]
Description=Second Brain Matrix Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/youruser/second-brain
EnvironmentFile=/home/youruser/second-brain/.env
ExecStart=/home/youruser/second-brain/venv/bin/python bot/main.py
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

### 3.2 Enable and Start

```bash
# Reload systemd
systemctl --user daemon-reload

# Enable on boot
systemctl --user enable second-brain

# Start now
systemctl --user start second-brain

# Check status
systemctl --user status second-brain

# View logs
journalctl --user -u second-brain -f
```

### 3.3 Enable Lingering (important!)

To keep user services running after logout:

```bash
sudo loginctl enable-linger $USER
```

## 4. Cron Jobs

### 4.1 Create Log Directory

```bash
sudo mkdir -p /var/log/second-brain
sudo chown $USER:$USER /var/log/second-brain
```

### 4.2 Create Wrapper Scripts

Create `scripts/run_daily_digest.sh`:

```bash
#!/bin/bash
set -e
cd /home/youruser/second-brain
source venv/bin/activate
source .env
export DIGEST_TARGET_USER
python scripts/daily_digest.py
```

Create `scripts/run_weekly_review.sh`:

```bash
#!/bin/bash
set -e
cd /home/youruser/second-brain
source venv/bin/activate
source .env
export DIGEST_TARGET_USER
python scripts/weekly_review.py
```

Create `scripts/run_maintenance.sh`:

```bash
#!/bin/bash
set -e
cd /home/youruser/second-brain
source venv/bin/activate
source .env
python scripts/weekly_maintenance.py
```

Make executable:

```bash
chmod +x scripts/*.sh
```

### 4.3 Install Crontab

```bash
crontab -e
```

Add:

```
# Second Brain Cron Jobs
# ----------------------

# Daily digest at 6:00 AM
0 6 * * * /home/youruser/second-brain/scripts/run_daily_digest.sh >> /var/log/second-brain/daily_digest.log 2>&1

# Weekly review Sunday at 4:00 PM
0 16 * * 0 /home/youruser/second-brain/scripts/run_weekly_review.sh >> /var/log/second-brain/weekly_review.log 2>&1

# Weekly maintenance Sunday at 11:00 PM
0 23 * * 0 /home/youruser/second-brain/scripts/run_maintenance.sh >> /var/log/second-brain/maintenance.log 2>&1

# Daily backup at 2:00 AM
0 2 * * * /home/youruser/second-brain/scripts/backup.sh >> /var/log/second-brain/backup.log 2>&1
```

## 5. Verification

### 5.1 Test Bot Connection

```bash
cd ~/second-brain
source venv/bin/activate
python bot/main.py
```

Should see:
```
INFO - Logged in as @secondbrain:yourdomain.com
INFO - Watching room: !roomid:yourdomain.com
```

### 5.2 Test Capture

Send a message to `#sb-inbox`:
```
Test message for second brain setup
```

Should see bot reply with confirmation.

### 5.3 Test Digest

```bash
source venv/bin/activate
export DIGEST_TARGET_USER=@carlos:yourdomain.com
python scripts/daily_digest.py
```

Check Matrix DMs for the digest.

### 5.4 Test Database

```bash
psql -U secondbrain -d secondbrain -c "SELECT * FROM inbox_log ORDER BY created_at DESC LIMIT 5;"
```

## 6. Directory Structure

Final structure should look like:

```
~/second-brain/
├── .env                          # Configuration (chmod 600)
├── schema.sql                    # Database schema
├── requirements.txt              # Python dependencies
├── venv/                         # Python virtual environment
├── bot/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── classifier.py
│   ├── router.py
│   ├── responder.py
│   ├── fix_handler.py
│   ├── commands.py
│   ├── queries.py
│   ├── digest.py
│   ├── weekly_review.py
│   └── main.py
├── scripts/
│   ├── daily_digest.py
│   ├── weekly_review.py
│   ├── weekly_maintenance.py
│   ├── restart_brain.py
│   ├── health_check.py
│   ├── backup.sh
│   ├── run_daily_digest.sh
│   ├── run_weekly_review.sh
│   └── run_maintenance.sh
└── prompts/                      # Optional, for prompt versioning
    ├── classify.txt
    ├── daily.txt
    └── weekly.txt
```

## 7. Backup Locations

```
/var/log/second-brain/           # Logs
├── daily_digest.log
├── weekly_review.log
├── maintenance.log
└── backup.log

/path/to/backups/second-brain/   # Database backups
└── secondbrain_YYYYMMDD_HHMMSS.sql.gz
```

## 8. Troubleshooting

### Bot won't start

```bash
# Check logs
journalctl --user -u second-brain -n 100

# Common issues:
# - Wrong Matrix credentials
# - Database not accessible
# - Missing .env variables
```

### Digest not arriving

```bash
# Check if cron ran
grep second-brain /var/log/syslog

# Check digest log
tail -50 /var/log/second-brain/daily_digest.log

# Test manually
python scripts/daily_digest.py
```

### Database connection issues

```bash
# Test connection
psql -U secondbrain -d secondbrain -c "SELECT 1"

# Check PostgreSQL is running
sudo systemctl status postgresql

# Check pg_hba.conf allows local connections
```

### Matrix room not found

```bash
# Verify room alias
# In Element, check room settings for the correct alias

# Make sure bot is in the room
# Invite bot if needed
```

## 9. Updates and Migrations

### Updating Code

```bash
# Stop service
systemctl --user stop second-brain

# Update code (git pull or manual copy)

# Restart
systemctl --user start second-brain
```

### Database Migrations

For schema changes, create migration files:

```bash
# Example: add new column
psql -U secondbrain -d secondbrain -c "ALTER TABLE projects ADD COLUMN priority INTEGER DEFAULT 0;"
```

### Updating Dependencies

```bash
source venv/bin/activate
pip install --upgrade matrix-nio asyncpg httpx
```

## 10. Security Checklist

- [ ] `.env` file has `chmod 600`
- [ ] Database password is strong and unique
- [ ] Matrix bot password is strong and unique
- [ ] API keys are not committed to git
- [ ] PostgreSQL only accepts local connections (check `pg_hba.conf`)
- [ ] Backups are stored securely
- [ ] Log files don't contain sensitive data
