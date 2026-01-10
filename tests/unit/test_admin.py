"""Unit tests for admin UI module."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Add paths - both bot and leaknote directories need to be in path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "bot"))
sys.path.insert(0, str(project_root / "leaknote"))

# Set admin environment variables before importing
os.environ["ADMIN_USERNAME"] = "test_admin"
os.environ["ADMIN_PASSWORD"] = "test_password"

from admin.app import app
from admin.dependencies import get_table_config, VALID_TABLES


@pytest.mark.unit
class TestAdminDependencies:
    """Tests for admin dependencies."""

    def test_get_table_config_valid_table(self):
        """Test getting config for a valid table."""
        config = get_table_config("people")
        assert config["display_name"] == "People"
        assert config["is_markdown"] is False
        assert len(config["fields"]) > 0

    def test_get_table_config_markdown_table(self):
        """Test getting config for a markdown table."""
        config = get_table_config("decisions")
        assert config["display_name"] == "Decisions"
        assert config["is_markdown"] is True

    def test_get_table_config_invalid_table(self):
        """Test getting config for an invalid table."""
        with pytest.raises(HTTPException) as exc_info:
            get_table_config("invalid_table")
        assert exc_info.value.status_code == 404

    def test_all_tables_have_configs(self):
        """Test that all valid tables have configurations."""
        for table in VALID_TABLES:
            config = get_table_config(table)
            assert config is not None
            assert "display_name" in config
            assert "fields" in config
            assert "list_columns" in config
            assert "is_markdown" in config


@pytest.mark.unit
class TestAdminAuth:
    """Tests for admin authentication."""

    def test_valid_credentials(self):
        """Test authentication with valid credentials."""
        from fastapi.security import HTTPBasicCredentials
        from admin.dependencies import get_current_admin

        credentials = HTTPBasicCredentials(username="test_admin", password="test_password")
        username = get_current_admin(credentials)
        assert username == "test_admin"

    def test_invalid_username(self):
        """Test authentication with invalid username."""
        from fastapi.security import HTTPBasicCredentials
        from admin.dependencies import get_current_admin

        credentials = HTTPBasicCredentials(username="wrong", password="test_password")
        with pytest.raises(HTTPException) as exc_info:
            get_current_admin(credentials)
        assert exc_info.value.status_code == 401

    def test_invalid_password(self):
        """Test authentication with invalid password."""
        from fastapi.security import HTTPBasicCredentials
        from admin.dependencies import get_current_admin

        credentials = HTTPBasicCredentials(username="test_admin", password="wrong")
        with pytest.raises(HTTPException) as exc_info:
            get_current_admin(credentials)
        assert exc_info.value.status_code == 401


@pytest.mark.unit
class TestAdminRoutes:
    """Tests for admin routes."""

    @pytest.fixture
    def client(self):
        """Create a test client with auth bypass."""
        # Override auth and DB dependencies for testing
        def override_auth():
            return "test_admin"

        async def override_pool():
            # Mock pool that doesn't connect
            pool = MagicMock()
            return pool

        from admin.dependencies import get_current_admin, get_db_pool
        from admin.app import app
        app.dependency_overrides[get_current_admin] = override_auth
        app.dependency_overrides[get_db_pool] = override_pool

        # Mock get_pool at module level to avoid lifespan connecting
        mock_pool_instance = MagicMock()
        mock_pool_instance.close = AsyncMock()

        with patch("admin.app.get_pool", return_value=AsyncMock(return_value=mock_pool_instance)()):
            with TestClient(app) as test_client:
                yield test_client

        app.dependency_overrides.clear()

    @pytest.fixture
    def mock_pool(self):
        """Mock database pool."""
        pool = MagicMock()
        conn = AsyncMock()

        # Mock async context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = conn
        mock_context.__aexit__.return_value = None

        pool.acquire = MagicMock(return_value=mock_context)
        return pool

    def test_root_redirect(self, client):
        """Test root redirects to dashboard."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert "/dashboard" in response.headers["location"]

    @pytest.mark.skip(reason="Requires complex async mocking - integration test would be better")
    def test_dashboard_page(self, client):
        """Test dashboard page renders."""
        # This test would require mocking all the async query functions
        # Better suited for integration tests with a test database
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "Dashboard" in response.text

    def test_table_list_page(self, client, mock_pool):
        """Test table list page renders."""
        with patch("bot.db.get_pool", return_value=mock_pool):
            async def mock_fetch(*args, **kwargs):
                return []

            mock_pool.acquire().__aenter__.return_value.fetch = mock_fetch
            mock_pool.acquire().__aenter__.return_value.fetchval = AsyncMock(return_value=0)

            response = client.get("/table/people")

            assert response.status_code == 200
            assert "People" in response.text

    def test_table_new_form(self, client):
        """Test new record form renders."""
        response = client.get("/table/people/new")
        assert response.status_code == 200
        assert "New" in response.text or "People" in response.text

    def test_bulk_delete_page(self, client):
        """Test bulk delete page renders."""
        response = client.get("/bulk-delete")
        assert response.status_code == 200
        assert "Bulk Delete" in response.text

    def test_invalid_table_404(self, client):
        """Test invalid table returns 404."""
        response = client.get("/table/invalid_table")
        assert response.status_code == 404


@pytest.mark.unit
class TestTableConfigs:
    """Tests for table configurations."""

    def test_people_table_config(self):
        """Test people table has correct fields."""
        config = get_table_config("people")
        field_names = [f["name"] for f in config["fields"]]
        assert "name" in field_names
        assert "context" in field_names
        assert "follow_ups" in field_names
        assert "last_touched" in field_names
        assert "tags" in field_names

    def test_projects_table_config(self):
        """Test projects table has correct fields."""
        config = get_table_config("projects")
        field_names = [f["name"] for f in config["fields"]]
        assert "name" in field_names
        assert "status" in field_names
        assert "next_action" in field_names
        assert "notes" in field_names

    def test_decisions_table_config(self):
        """Test decisions table has markdown fields."""
        config = get_table_config("decisions")
        assert config["is_markdown"] is True
        markdown_fields = [f for f in config["fields"] if f["type"] == "markdown"]
        assert len(markdown_fields) > 0

    def test_reference_tables_use_markdown(self):
        """Test all reference category tables use markdown."""
        for table in ["decisions", "howtos", "snippets"]:
            config = get_table_config(table)
            assert config["is_markdown"] is True, f"{table} should use markdown"

    def test_dynamic_tables_no_markdown(self):
        """Test dynamic category tables don't use markdown."""
        for table in ["people", "projects", "ideas", "admin"]:
            config = get_table_config(table)
            assert config["is_markdown"] is False, f"{table} should not use markdown"
