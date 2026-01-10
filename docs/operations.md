# Operations

## Service Management

### Start/Stop Services

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart specific service
docker compose restart leaknote
docker compose restart dendrite

# View status
docker compose ps
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f leaknote
docker compose logs -f dendrite
docker compose logs -f postgres

# Last 100 lines
docker compose logs --tail 100 leaknote
```

## Cron Jobs

### Installation

```bash
crontab -e
```

Add entries from `crontab.example`:

```bash
# Daily digest at 6:00 AM
0 6 * * * /path/to/leaknote/cron/daily_digest.sh

# Weekly review Sunday at 4:00 PM
0 16 * * 0 /path/to/leaknote/cron/weekly_review.sh

# Weekly maintenance Sunday at 11:00 PM
0 23 * * 0 /path/to/leaknote/cron/maintenance.sh

# Daily backup at 2:00 AM
0 2 * * * /path/to/leaknote/cron/backup.sh

# Health check every 5 minutes
*/5 * * * * /path/to/leaknote/cron/health_check.sh >> /path/to/leaknote/logs/health.log 2>&1
```

### Manual Execution

```bash
# Test daily digest
docker exec leaknote-bot python scripts/daily_digest.py

# Test weekly review
docker exec leaknote-bot python scripts/weekly_review.py

# Test maintenance
docker exec leaknote-bot python scripts/maintenance.py

# Test health check
docker exec leaknote-bot python scripts/health_check.py
```

### Log Locations

```
logs/
├── daily_digest.log
├── weekly_review.log
├── maintenance.log
├── backup.log
└── health.log
```

## Backup & Restore

### Automatic Backups

The `cron/backup.sh` script runs daily at 02:00 and:

1. Backs up Leaknote database
2. Backs up Dendrite database
3. Compresses with gzip
4. Retains 30 days of backups

Backups are stored in `data/backups/`.

### Manual Backup

```bash
./cron/backup.sh
ls -la data/backups/
```

### Restore Leaknote Database

```bash
# Stop the bot first
docker compose stop leaknote

# Restore
gunzip -c data/backups/leaknote_20260110_020000.sql.gz | \
    docker exec -i leaknote-db psql -U leaknote -d leaknote

# Restart
docker compose start leaknote
```

### Restore Dendrite Database

```bash
# Stop Dendrite first
docker compose stop dendrite

# Restore
gunzip -c data/backups/dendrite_20260110_020000.sql.gz | \
    docker exec -i leaknote-db psql -U dendrite -d dendrite

# Restart
docker compose start dendrite
```

### Full Disaster Recovery

1. Fresh server with Docker installed
2. Clone the repository
3. Copy `.env` from backup
4. Copy `dendrite/config/` from backup (contains signing key!)
5. Run `docker compose up -d postgres` (start only postgres)
6. Restore both databases
7. Run `docker compose up -d` (start remaining services)

## Maintenance Tasks

### Weekly Maintenance Script

Runs automatically Sunday at 23:00:

- Cleans up old pending clarifications (>7 days)
- Archives completed admin tasks (>30 days)
- Runs VACUUM ANALYZE on all tables
- Generates statistics report

### Manual Database Maintenance

```bash
# Connect to database
docker exec -it leaknote-db psql -U leaknote -d leaknote

# Check table sizes
SELECT 
    relname as table,
    pg_size_pretty(pg_total_relation_size(relid)) as size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;

# Vacuum specific table
VACUUM ANALYZE projects;

# Reindex
REINDEX TABLE inbox_log;
```

### Cleanup Old Data

```sql
-- Delete old inbox log entries (keep 90 days)
DELETE FROM inbox_log WHERE created_at < NOW() - INTERVAL '90 days';

-- Delete completed admin tasks older than 60 days
DELETE FROM admin WHERE status = 'done' AND updated_at < NOW() - INTERVAL '60 days';

-- Delete old pending clarifications
DELETE FROM pending_clarifications WHERE created_at < NOW() - INTERVAL '7 days';
```

## Matrix Administration

### Create New User

```bash
docker exec -it dendrite-matrix /usr/bin/create-account \
    -config /etc/dendrite/dendrite.yaml \
    -username newuser \
    -password "secure-password"
```

### Create Admin User

```bash
docker exec -it dendrite-matrix /usr/bin/create-account \
    -config /etc/dendrite/dendrite.yaml \
    -username admin \
    -password "secure-password" \
    -admin
```

### Reset User Password

Currently requires direct database access or user self-service.

## Troubleshooting

### Bot Not Responding

1. Check if container is running:
   ```bash
   docker compose ps leaknote
   ```

2. Check logs for errors:
   ```bash
   docker compose logs --tail 50 leaknote
   ```

3. Verify Matrix connection:
   ```bash
   curl http://localhost:8008/_matrix/client/versions
   ```

4. Restart the bot:
   ```bash
   docker compose restart leaknote
   ```

### Digest Not Arriving

1. Check cron logs:
   ```bash
   tail -50 logs/daily_digest.log
   ```

2. Test manual execution:
   ```bash
   docker exec leaknote-bot python scripts/daily_digest.py
   ```

3. Verify `DIGEST_TARGET_USER` is correct in `.env`

4. Check if bot can DM your user (room must exist)

### Classification Errors

1. Check recent fix rate:
   ```sql
   SELECT status, COUNT(*) 
   FROM inbox_log 
   WHERE created_at > NOW() - INTERVAL '7 days'
   GROUP BY status;
   ```

2. Review specific misclassifications:
   ```sql
   SELECT raw_text, destination, confidence 
   FROM inbox_log 
   WHERE status = 'fixed'
   ORDER BY created_at DESC 
   LIMIT 20;
   ```

3. Adjust `CONFIDENCE_THRESHOLD` if needed

### Database Connection Issues

1. Check postgres is running:
   ```bash
   docker compose ps postgres
   ```

2. Test connection:
   ```bash
   docker exec leaknote-db psql -U leaknote -d leaknote -c "SELECT 1"
   ```

3. Check logs:
   ```bash
   docker compose logs postgres
   ```

### Dendrite Issues

1. Check container status:
   ```bash
   docker compose ps dendrite
   ```

2. Check logs:
   ```bash
   docker compose logs dendrite
   ```

3. Verify config:
   ```bash
   cat dendrite/config/dendrite.yaml | grep -A5 "database:"
   ```

4. Test client API:
   ```bash
   curl http://localhost:8008/_matrix/client/versions
   ```

### Out of Disk Space

1. Check disk usage:
   ```bash
   df -h
   du -sh data/*
   ```

2. Clean up old backups:
   ```bash
   find data/backups -name "*.sql.gz" -mtime +30 -delete
   ```

3. Vacuum database:
   ```bash
   docker exec leaknote-db psql -U postgres -c "VACUUM FULL"
   ```

4. Clean up Dendrite media (if large):
   ```bash
   du -sh dendrite/media/
   # Consider implementing media retention policy
   ```

## Restart Procedure

After being away from the system:

1. **Don't catch up** - just restart fresh
2. Do a 10-minute brain dump into the inbox
3. One thought per message, no organizing
4. The system will classify everything
5. Tomorrow's digest will get you back on track

```bash
# Optional: trigger a restart prompt
docker exec leaknote-bot python scripts/restart_prompt.py
```

## Monitoring

### Health Check Script

The `cron/health_check.sh` script checks:

- All containers running
- PostgreSQL responding
- Dendrite API responding
- Bot internal health

### Setting Up Alerts

Add email alerting to crontab:

```bash
*/5 * * * * /path/to/leaknote/cron/health_check.sh > /dev/null 2>&1 || echo "Leaknote unhealthy at $(date)" | mail -s "Leaknote Alert" you@example.com
```

### Metrics to Track

- Inbox volume (captures per day)
- Fix rate (% of items corrected)
- Clarification rate (% asked for help)
- Digest delivery success
- Database size growth
