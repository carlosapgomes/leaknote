"""Unit tests for fix_handler module."""

import pytest
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bot"))

from fix_handler import parse_fix_command


@pytest.mark.unit
class TestParseFixCommand:
    """Tests for parse_fix_command function."""

    def test_parse_fix_person(self):
        """Test parsing fix: person command."""
        assert parse_fix_command("fix: person") == "people"
        assert parse_fix_command("fix:person") == "people"
        assert parse_fix_command("FIX: PERSON") == "people"

    def test_parse_fix_people(self):
        """Test parsing fix: people command (plural form)."""
        assert parse_fix_command("fix: people") == "people"
        assert parse_fix_command("fix:people") == "people"

    def test_parse_fix_project(self):
        """Test parsing fix: project command."""
        assert parse_fix_command("fix: project") == "projects"
        assert parse_fix_command("fix:project") == "projects"
        assert parse_fix_command("FIX: PROJECT") == "projects"

    def test_parse_fix_projects(self):
        """Test parsing fix: projects command (plural form)."""
        assert parse_fix_command("fix: projects") == "projects"

    def test_parse_fix_idea(self):
        """Test parsing fix: idea command."""
        assert parse_fix_command("fix: idea") == "ideas"
        assert parse_fix_command("fix:idea") == "ideas"

    def test_parse_fix_ideas(self):
        """Test parsing fix: ideas command (plural form)."""
        assert parse_fix_command("fix: ideas") == "ideas"

    def test_parse_fix_admin(self):
        """Test parsing fix: admin command."""
        assert parse_fix_command("fix: admin") == "admin"
        assert parse_fix_command("fix:admin") == "admin"

    def test_parse_fix_decision(self):
        """Test parsing fix: decision command."""
        assert parse_fix_command("fix: decision") == "decisions"
        assert parse_fix_command("fix:decision") == "decisions"

    def test_parse_fix_decisions(self):
        """Test parsing fix: decisions command (plural form)."""
        assert parse_fix_command("fix: decisions") == "decisions"

    def test_parse_fix_howto(self):
        """Test parsing fix: howto command."""
        assert parse_fix_command("fix: howto") == "howtos"
        assert parse_fix_command("fix:howto") == "howtos"

    def test_parse_fix_howtos(self):
        """Test parsing fix: howtos command (plural form)."""
        assert parse_fix_command("fix: howtos") == "howtos"

    def test_parse_fix_snippet(self):
        """Test parsing fix: snippet command."""
        assert parse_fix_command("fix: snippet") == "snippets"
        assert parse_fix_command("fix:snippet") == "snippets"

    def test_parse_fix_snippets(self):
        """Test parsing fix: snippets command (plural form)."""
        assert parse_fix_command("fix: snippets") == "snippets"

    def test_parse_fix_with_extra_whitespace(self):
        """Test parsing with extra whitespace."""
        assert parse_fix_command("  fix:  project  ") == "projects"
        assert parse_fix_command("fix:   idea") == "ideas"

    def test_parse_fix_case_insensitive(self):
        """Test that parsing is case insensitive."""
        assert parse_fix_command("FIX: PERSON") == "people"
        assert parse_fix_command("Fix: Project") == "projects"
        assert parse_fix_command("fIx: IdEa") == "ideas"

    def test_parse_invalid_category(self):
        """Test that invalid category returns None."""
        assert parse_fix_command("fix: invalid") is None
        assert parse_fix_command("fix: xyz") is None
        assert parse_fix_command("fix: note") is None

    def test_parse_not_fix_command(self):
        """Test that non-fix commands return None."""
        assert parse_fix_command("idea: something") is None
        assert parse_fix_command("project: task") is None
        assert parse_fix_command("just some text") is None
        assert parse_fix_command("fixme: bug") is None

    def test_parse_empty_string(self):
        """Test that empty string returns None."""
        assert parse_fix_command("") is None
        assert parse_fix_command("   ") is None

    def test_parse_fix_without_category(self):
        """Test that 'fix:' without category returns None."""
        assert parse_fix_command("fix:") is None
        assert parse_fix_command("fix: ") is None
