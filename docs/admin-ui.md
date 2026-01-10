# Admin UI

## Overview

The Leaknote Admin UI is a web-based interface for managing all records stored in the database. It provides a convenient way to create, read, update, and delete records without using Matrix commands.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (via Tailscale)                                   │
│  └── http://<tailscale-ip>:8000                           │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI Application (leaknote-admin container)            │
│  ├── HTTP Basic Auth                                       │
│  ├── Jinja2 Templates                                      │
│  └── EasyMDE Markdown Editor                               │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL Database                                       │
│  └── Shared with Matrix bot                                │
└─────────────────────────────────────────────────────────────┘
```

## Access

### URL

```
http://<tailscale-ip>:8000
```

The admin UI is only accessible through Tailscale VPN for security.

### Authentication

HTTP Basic Auth is used for authentication:

```bash
# Default credentials (set in .env)
Username: admin
Password: your-secure-password
```

To change credentials, edit `.env`:

```bash
ADMIN_USERNAME=your-username
ADMIN_PASSWORD=your-secure-password
```

Then restart the admin container:

```bash
docker compose restart leaknote-admin
```

## Features

### Dashboard

The dashboard provides an overview of your Leaknote data:

- **Record Counts**: Total records per table
- **Inbox Stats**: 7-day capture statistics
- **Active Projects**: Projects with next actions
- **Admin Tasks**: Due soon and overdue items
- **People with Follow-ups**: Contacts needing attention
- **Recent Ideas**: Ideas captured in the last 7 days

### Table Management

Each table has a dedicated management interface:

#### Tables Available

| Table | Type | Description |
|-------|------|-------------|
| **people** | Dynamic | Person tracking with context and follow-ups |
| **projects** | Dynamic | Project management with status tracking |
| **ideas** | Dynamic | Idea capture and elaboration |
| **admin** | Dynamic | Administrative tasks with due dates |
| **decisions** | Reference | Decision log with rationale |
| **howtos** | Reference | How-to documentation (markdown) |
| **snippets** | Reference | Code snippets (markdown) |
| **pending_clarifications** | System | Messages awaiting clarification |

#### Operations

For each table you can:

- **List**: View all records with pagination
- **Search**: Full-text search across table contents
- **Create**: Add new records with form validation
- **Edit**: Update existing records
- **View**: Render markdown preview (reference tables)
- **Delete**: Remove records

### Markdown Editor

Reference category tables (decisions, howtos, snippets) use the EasyMDE markdown editor:

**Features:**
- Live preview
- Side-by-side editing
- Toolbar with formatting options:
  - Bold, italic, headings
  - Code blocks
  - Quotes
  - Lists (ordered/unordered)
  - Links and images
  - Tables
  - Fullscreen mode
- Auto-save to browser storage

**Supported Markdown:**

```markdown
# Heading 1
## Heading 2
**bold** and *italic*
`code` and ```code blocks```
- unordered lists
1. ordered lists
> quotes

[links](url)
![images](url)

| tables | are |
|--------|-----|
| supported | too |
```

### Bulk Operations

The bulk delete interface allows you to:

1. Select a table
2. Specify a date range (in days)
3. Delete all records older than the threshold

**Use cases:**
- Clean up old test data
- Remove completed admin tasks
- Archive old ideas

## Configuration

### Environment Variables

Add to `.env`:

```bash
# Admin UI credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me-secure-password
```

### Docker Compose

The admin UI runs in a separate container:

```yaml
leaknote-admin:
  build: .
  container_name: leaknote-admin
  restart: unless-stopped
  command: uvicorn leaknote.admin.app:app --host 0.0.0.0 --port 8000
  environment:
    - DATABASE_URL=postgresql://leaknote:${LEAKNOTE_DB_PASSWORD}@postgres:5432/leaknote
    - ADMIN_USERNAME=${ADMIN_USERNAME}
    - ADMIN_PASSWORD=${ADMIN_PASSWORD}
  ports:
    - "8000:8000"
  depends_on:
    - postgres
  networks:
    - leaknote-net
```

### Port Configuration

Default port is `8000`. To change:

1. Update `.env`:
   ```bash
   ADMIN_PORT=8080  # or your preferred port
   ```

2. Update `docker-compose.yml`:
   ```yaml
   ports:
     - "${ADMIN_PORT}:8000"
   ```

3. Recreate the container:
   ```bash
   docker compose up -d --force-recreate leaknote-admin
   ```

## Security

### Tailscale-Only Access

The admin UI is designed to be accessed only through Tailscale VPN:

1. **No public exposure**: Port 8000 should not be forwarded
2. **Tailscale IP**: Use the Tailscale-assigned IP address
3. **Secondary authentication**: HTTP Basic Auth provides additional protection

### Security Considerations

- **Timing-safe comparison**: Uses `secrets.compare_digest()` for password verification
- **Strong passwords**: Use a secure, randomly generated password
- **TLS**: Tailscale provides encryption, so no HTTPS needed
- **Separate container**: Admin UI issues don't affect the Matrix bot

## Operations

### Starting the Admin UI

```bash
# Start all services
docker compose up -d

# Start only admin UI
docker compose up -d leaknote-admin

# Check status
docker compose ps leaknote-admin
```

### Viewing Logs

```bash
# Follow logs
docker compose logs -f leaknote-admin

# Last 100 lines
docker compose logs --tail 100 leaknote-admin
```

### Restarting

```bash
docker compose restart leaknote-admin
```

### Stopping

```bash
# Stop admin UI
docker compose stop leaknote-admin

# Stop all services
docker compose down
```

## Mobile Access

The admin UI is mobile-responsive:

- Touch-friendly buttons (minimum 44x44px)
- Responsive tables with horizontal scroll
- Stacked layouts on small screens
- Dropdown navigation for mobile
- EasyMDE mobile adjustments

## Troubleshooting

### Can't Access Admin UI

1. **Check if container is running:**
   ```bash
   docker compose ps leaknote-admin
   ```

2. **Check logs for errors:**
   ```bash
   docker compose logs leaknote-admin
   ```

3. **Verify Tailscale connection:**
   ```bash
   tailscale status
   tailscale ip
   ```

4. **Test from server:**
   ```bash
   curl http://localhost:8000
   ```

### Authentication Fails

1. **Verify credentials in `.env`:**
   ```bash
   grep ADMIN_ .env
   ```

2. **Restart the container:**
   ```bash
   docker compose restart leaknote-admin
   ```

3. **Clear browser cache and try again**

### Database Errors

1. **Check database connection:**
   ```bash
   docker exec leaknote-db psql -U leaknote -d leaknote -c "SELECT 1"
   ```

2. **Verify DATABASE_URL in docker-compose.yml**

3. **Check admin container logs:**
   ```bash
   docker compose logs leaknote-admin | grep -i database
   ```

### Markdown Editor Not Loading

1. **Check browser console for JavaScript errors**

2. **Verify EasyMDE files exist:**
   ```bash
   ls -la leaknote/admin/static/js/easymde/
   ```

3. **Check static file mounting in container:**
   ```bash
   docker exec leaknote-admin ls -la /app/leaknote/admin/static/js/easymde/
   ```

## Development

### Local Development

To run the admin UI locally (without Docker):

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://leaknote:password@localhost:5432/leaknote"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="test"

# Run the server
uvicorn leaknote.admin.app:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests

```bash
# Run admin UI tests
pytest tests/unit/test_admin.py -v

# Run with coverage
pytest tests/unit/test_admin.py --cov=leaknote/admin --cov-report=html
```

### File Structure

```
leaknote/admin/
├── __init__.py
├── app.py                  # FastAPI application
├── routes.py               # Route handlers
├── dependencies.py         # Dependencies and table configs
├── templates/
│   ├── base.html           # Base layout
│   ├── dashboard.html      # Dashboard page
│   ├── table_list.html     # Record listing
│   ├── record_edit.html    # Create/edit form
│   ├── record_view.html    # Markdown preview
│   └── bulk_delete.html    # Bulk delete interface
└── static/
    ├── css/
    │   └── admin.css       # Custom styles
    └── js/
        └── easymde/        # Bundled EasyMDE files
```

## Future Enhancements

Potential improvements for the admin UI:

- [ ] Advanced filtering and sorting
- [ ] Export records as CSV/JSON
- [ ] Bulk edit operations
- [ ] File attachments for records
- [ ] Activity audit log viewer
- [ ] Dark mode support
- [ ] Record comparison/diff view
- [ ] Custom field management
