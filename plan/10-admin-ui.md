# Admin UI Implementation Plan

## Overview
Add a lightweight web-based admin UI to Leaknote for managing records (cleanup, edits, etc.). The UI will be accessible via Tailscale VPN only, with no public exposure.

## Architecture Decision
**Chosen Approach:** FastAPI + Simple Jinja2 Templates

**Why:**
- FastAPI is async-native, matches existing `asyncio`/`asyncpg` stack
- Can reuse existing database connection logic from `bot/db.py`
- Minimal dependencies and code (~200-300 lines)
- Server-side rendering is sufficient for simple CRUD operations
- Runs alongside existing Matrix bot without interference

## Implementation Steps

### 1. Add Dependencies
**File:** `requirements.txt` or `pyproject.toml`

Add new dependencies:
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
jinja2>=3.1.2
python-multipart>=0.0.6  # for form data
markdown>=3.5.0          # for markdown rendering (server-side)
```

### 2. Create Admin Module Structure
**New files to create:**
```
leaknote/
├── admin/
│   ├── __init__.py
│   ├── app.py           # FastAPI app setup
│   ├── routes.py        # Admin routes
│   ├── templates/       # Jinja2 templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── table_list.html
│   │   ├── record_edit.html
│   │   └── bulk_delete.html
│   └── static/
│       ├── admin.css        # Simple styling
│       ├── js/
│       │   └── markdown.js  # Markdown editor initialization
│       └── vendor/          # CDN or bundled JS libraries
│       └── (EasyMDE via CDN)
```

### 3. Implement FastAPI Application
**File:** `leaknote/admin/app.py`

- Initialize FastAPI app
- Configure Jinja2 templates
- Add simple authentication (API key via header or basic auth)
- Include routes from `routes.py`
- Reuse database connection pool from `bot/db.py`

### 4. Create Admin Routes
**File:** `leaknote/admin/routes.py`

**Endpoints to implement:**

1. `GET /` - Dashboard (stats, quick links)
2. `GET /table/{table_name}` - List records with pagination
3. `GET /table/{table_name}/new` - Create new record form
4. `POST /table/{table_name}/new` - Create new record
5. `GET /table/{table_name}/{id}/edit` - Edit record form (with EasyMDE for reference categories)
6. `POST /table/{table_name}/{id}/edit` - Update record
7. `GET /table/{table_name}/{id}/view` - View rendered markdown (for reference categories)
8. `POST /table/{table_name}/{id}/delete` - Delete record
9. `GET /bulk-delete` - Bulk delete interface
10. `POST /bulk-delete` - Execute bulk delete by date range or criteria

**Tables to support:**
- people, projects, ideas, admin (dynamic categories)
- decisions, howtos, snippets (reference categories)
- pending_clarifications (system table)

### 5. Create HTML Templates
**Directory:** `leaknote/admin/templates/`

**Templates:**
- `base.html` - Layout with navigation
- `dashboard.html` - Overview stats
- `table_list.html` - Record listing with search/filter
- `record_edit.html` - Form for create/edit
- `bulk_delete.html` - Bulk operations interface

**Design approach:**
- Minimal, clean CSS (no Bootstrap needed)
- Responsive for mobile devices
- Simple form validation

### 5.1 Markdown Editing for Reference Categories
**For:** decisions, howtos, snippets tables

**Why EasyMDE:**
- Simple, lightweight markdown editor
- No framework dependencies (vanilla JS)
- Toolbar with common formatting options
- Live preview pane
- Easy to integrate via CDN

**Implementation:**

1. **Include EasyMDE in base template:**
   ```html
   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/easymde/dist/easymde.min.css">
   <script src="https://cdn.jsdelivr.net/npm/easymde/dist/easymde.min.js"></script>
   ```

2. **Conditional markdown editor in record_edit.html:**
   - Detect if editing a reference category table
   - Replace textarea with EasyMDE for `content` field
   - Use simple textarea for dynamic categories (people, projects, ideas, admin)

3. **Server-side markdown rendering:**
   - Use Python `markdown` library for rendering preview/readonly view
   - Add `GET /table/{table_name}/{id}/view` endpoint for rendered markdown
   - Enable syntax highlighting for code blocks (optional)

4. **Editor configuration:**
   ```javascript
   new EasyMDE({
       element: document.getElementById('content'),
       spellChecker: false,
       autosave: {
           enabled: true,
           uniqueId: 'leaknote-edit-{table}-{id}'
       },
       toolbar: ['bold', 'italic', 'heading', '|',
                 'code', 'quote', 'unordered-list', 'ordered-list', '|',
                 'link', 'image', 'table', '|',
                 'preview', 'side-by-side', 'fullscreen']
   })
   ```

**Template logic:**
```jinja2
{% if table_name in ['decisions', 'howtos', 'snippets'] %}
  <!-- EasyMDE editor for markdown content -->
  <textarea id="content" name="content">{{ record.content }}</textarea>
{% else %}
  <!-- Plain textarea for dynamic categories -->
  <textarea id="content" name="content">{{ record.content }}</textarea>
{% endif %}
```

### 6. Update Docker Configuration
**File:** `docker-compose.yml`

**Architecture:** Separate containers for bot and admin UI

**Why separate containers:**
- **Isolation:** Admin server issues don't affect the Matrix bot
- **Independent updates:** Restart/update admin without bot downtime
- **Resource control:** Can set memory/CPU limits independently
- **Cleaner separation:** Different responsibilities, different scaling needs

**Implementation:**

```yaml
services:
  # Existing Matrix bot service
  leaknote:
    build: .
    container_name: leaknote-bot
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://leaknote:${POSTGRES_PASSWORD}@db:5432/leaknote
      # ... existing bot env vars ...
    depends_on:
      - db
    networks:
      - leaknote-network

  # New Admin UI service
  leaknote-admin:
    build: .
    container_name: leaknote-admin
    restart: unless-stopped
    command: uvicorn leaknote.admin.app:app --host 0.0.0.0 --port ${ADMIN_PORT}
    environment:
      - DATABASE_URL=postgresql://leaknote:${POSTGRES_PASSWORD}@db:5432/leaknote
      - ADMIN_USERNAME=${ADMIN_USERNAME}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
    ports:
      - "${ADMIN_PORT}:${ADMIN_PORT}"  # Only accessible via Tailscale
    depends_on:
      - db
    networks:
      - leaknote-network
    env_file:
      - .env  # Load all variables from global .env file

  # Existing database service
  db:
    image: postgres:16-alpine
    # ... existing db config ...
    networks:
      - leaknote-network

networks:
  leaknote-network:
    driver: bridge
```

**Alternative (single container with supervisor):**
Could also run both processes in one container using supervisord, but this defeats the isolation benefit.

### 7. Add Configuration

#### 7.1 Update `.env` file
**File:** `.env` (root of project)

Add admin UI credentials to the existing global `.env` file:

```bash
# ===================
# Admin UI
# ===================
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me-secure-password
ADMIN_PORT=8000
```

**Update `.env.example` file to include these variables** (without actual values):

```bash
# ===================
# Admin UI
# ===================
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me-secure-password
ADMIN_PORT=8000
```

#### 7.2 Docker Compose Environment Variables
**File:** `docker-compose.yml`

Update the `leaknote-admin` service to use the `.env` variables:

```yaml
leaknote-admin:
  build: .
  container_name: leaknote-admin
  restart: unless-stopped
  command: uvicorn leaknote.admin.app:app --host 0.0.0.0 --port ${ADMIN_PORT}
  environment:
    - DATABASE_URL=postgresql://leaknote:${POSTGRES_PASSWORD}@db:5432/leaknote
    - ADMIN_USERNAME=${ADMIN_USERNAME}
    - ADMIN_PASSWORD=${ADMIN_PASSWORD}
  ports:
    - "${ADMIN_PORT}:${ADMIN_PORT}"  # Only accessible via Tailscale
  depends_on:
    - db
  networks:
    - leaknote-network
  env_file:
    - .env  # Load from global .env file
```

#### 7.3 Authentication Implementation
**File:** `leaknote/admin/app.py`

Use FastAPI's HTTP Basic Auth or simple form-based authentication:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

security = HTTPBasic()

def get_admin_auth(credentials: HTTPBasicCredentials = Depends(security)):
    admin_user = os.getenv("ADMIN_USERNAME")
    admin_pass = os.getenv("ADMIN_PASSWORD")

    correct_username = secrets.compare_digest(credentials.username, admin_user)
    correct_password = secrets.compare_digest(credentials.password, admin_pass)

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
```

**Alternative:** Form-based login with session cookies (better UX for browsers)

## Security Considerations

Since this is Tailscale-only access:
- **Primary security:** Tailscale network isolation
- **Secondary security:** HTTP Basic Auth (username/password from `.env`)
- Uses `secrets.compare_digest()` for timing-attack protection
- **No TLS required** within Tailscale (it provides encryption)
- Consider adding rate limiting for additional protection

## Critical Files to Modify

1. **New:** `leaknote/admin/app.py` - FastAPI application with authentication
2. **New:** `leaknote/admin/routes.py` - Route handlers with auth dependency
3. **New:** `leaknote/admin/templates/*` - HTML templates (base, dashboard, CRUD forms)
4. **New:** `leaknote/admin/static/admin.css` - Simple styling
5. **Modify:** `requirements.txt` or `pyproject.toml` - Add FastAPI, uvicorn, jinja2, markdown
6. **Modify:** `docker-compose.yml` - Add leaknote-admin service
7. **Modify:** `.env` - Add ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_PORT
8. **Modify:** `.env.example` - Add admin credentials template

## Database Operations to Reuse

From `bot/db.py`:
- Existing connection pool (`Database` class)
- CRUD methods: `get_all`, `get_by_id`, `create`, `update`, `delete`
- Already async, works with FastAPI seamlessly

## Verification Plan

1. **Start the admin UI:**
   ```bash
   docker-compose up
   # Or run locally: uvicorn leaknote.admin.app:app --reload
   ```

2. **Access via Tailscale:**
   - Open browser to `http://<tailscale-ip>:8000`
   - Verify API key authentication works

3. **Test CRUD operations:**
   - List records from each table
   - Create a new test record
   - Edit an existing record
   - Delete a record

4. **Test markdown editing (reference categories):**
   - Create a new "decision" with markdown formatting (headers, lists, code blocks)
   - Edit an existing "howto" using EasyMDE editor
   - Test live preview and side-by-side mode
   - View rendered markdown via `/view` endpoint
   - Verify syntax highlighting works (if implemented)

5. **Test bulk operations:**
   - Delete records older than X days
   - Verify deletion was successful

6. **Verify bot still works:**
   - Ensure Matrix bot continues functioning normally
   - Check that database transactions don't conflict

## Alternative Options Considered

1. **SQLAdmin** - Rejected due to SQLAlchemy requirement (adds complexity alongside asyncpg)
2. **Adminer/pgAdmin** - Rejected because external tools don't integrate with custom schema/LLM features
3. **CLI-only** - Rejected per user preference for web browser access
4. **Full custom dashboard** - Rejected as overkill for simple cleanup/editing needs
