"""Unit tests for commands module."""

import pytest
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bot"))

from commands import parse_command


@pytest.mark.unit
class TestParseCommand:
    """Tests for parse_command function."""

    def test_parse_recall_command(self):
        """Test parsing ?recall command."""
        result = parse_command("?recall docker deployment")
        assert result is not None
        assert result[0] == "recall"
        assert result[1] == "docker deployment"

    def test_parse_recall_case_insensitive(self):
        """Test ?recall is case insensitive."""
        result = parse_command("?RECALL test")
        assert result is not None
        assert result[0] == "recall"

    def test_parse_search_command(self):
        """Test parsing ?search command."""
        result = parse_command("?search matrix bot")
        assert result is not None
        assert result[0] == "search"
        assert result[1] == "matrix bot"

    def test_parse_search_case_insensitive(self):
        """Test ?search is case insensitive."""
        result = parse_command("?SEARCH test")
        assert result is not None
        assert result[0] == "search"

    def test_parse_people_command(self):
        """Test parsing ?people command."""
        result = parse_command("?people John Doe")
        assert result is not None
        assert result[0] == "people"
        assert result[1] == "john doe"  # Normalized to lowercase

    def test_parse_projects_command_no_status(self):
        """Test parsing ?projects without status filter."""
        result = parse_command("?projects")
        assert result is not None
        assert result[0] == "projects"
        assert result[1] is None

    def test_parse_projects_command_with_active(self):
        """Test parsing ?projects active."""
        result = parse_command("?projects active")
        assert result is not None
        assert result[0] == "projects"
        assert result[1] == "active"

    def test_parse_projects_command_with_waiting(self):
        """Test parsing ?projects waiting."""
        result = parse_command("?projects waiting")
        assert result is not None
        assert result[0] == "projects"
        assert result[1] == "waiting"

    def test_parse_projects_command_with_blocked(self):
        """Test parsing ?projects blocked."""
        result = parse_command("?projects blocked")
        assert result is not None
        assert result[0] == "projects"
        assert result[1] == "blocked"

    def test_parse_projects_command_with_someday(self):
        """Test parsing ?projects someday."""
        result = parse_command("?projects someday")
        assert result is not None
        assert result[0] == "projects"
        assert result[1] == "someday"

    def test_parse_projects_command_with_done(self):
        """Test parsing ?projects done."""
        result = parse_command("?projects done")
        assert result is not None
        assert result[0] == "projects"
        assert result[1] == "done"

    def test_parse_ideas_command(self):
        """Test parsing ?ideas command."""
        result = parse_command("?ideas")
        assert result is not None
        assert result[0] == "ideas"
        assert result[1] is None

    def test_parse_admin_command_no_filter(self):
        """Test parsing ?admin without filter."""
        result = parse_command("?admin")
        assert result is not None
        assert result[0] == "admin"
        assert result[1] is None

    def test_parse_admin_command_with_due(self):
        """Test parsing ?admin due."""
        result = parse_command("?admin due")
        assert result is not None
        assert result[0] == "admin"
        assert result[1] == "due"

    def test_parse_not_command(self):
        """Test that non-command text returns None."""
        assert parse_command("This is not a command") is None
        assert parse_command("idea: something") is None
        assert parse_command("regular message") is None

    def test_parse_invalid_command(self):
        """Test that invalid command returns None."""
        assert parse_command("?invalid") is None
        assert parse_command("?xyz test") is None

    def test_parse_command_with_extra_whitespace(self):
        """Test parsing with extra whitespace."""
        result = parse_command("  ?search   test query  ")
        assert result is not None
        assert result[0] == "search"
        # Note: argument will have leading/trailing spaces stripped by the command itself

    def test_parse_empty_string(self):
        """Test that empty string returns None."""
        assert parse_command("") is None
        assert parse_command("   ") is None

    def test_parse_question_mark_only(self):
        """Test that lone question mark returns None."""
        assert parse_command("?") is None

    def test_parse_recall_with_multiword_query(self):
        """Test ?recall with multi-word search query."""
        result = parse_command("?recall how to deploy docker containers")
        assert result is not None
        assert result[0] == "recall"
        assert result[1] == "how to deploy docker containers"

    def test_parse_search_with_special_characters(self):
        """Test ?search with special characters in query."""
        result = parse_command("?search pytest-asyncio @decorator")
        assert result is not None
        assert result[0] == "search"
        assert result[1] == "pytest-asyncio @decorator"
