"""Unit tests for classifier module."""

import pytest
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bot"))

from classifier import parse_reference


@pytest.mark.unit
class TestParseReference:
    """Tests for parse_reference function."""

    def test_parse_idea_prefix(self):
        """Test parsing idea: prefix."""
        text = "idea: Build automated test suite"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "ideas"
        assert "title" in result["extracted"]
        assert "Build automated test suite" in result["extracted"]["title"]
        assert "elaboration" in result["extracted"]

    def test_parse_person_prefix(self):
        """Test parsing person: prefix."""
        text = "person: John Doe - software engineer at Acme Corp"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "people"
        assert "name" in result["extracted"]
        assert "John Doe" in result["extracted"]["name"]
        assert "context" in result["extracted"]

    def test_parse_project_prefix(self):
        """Test parsing project: prefix."""
        text = "project: Automated testing - implement pytest suite"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "projects"
        assert "name" in result["extracted"]
        assert result["extracted"]["status"] == "active"
        assert "next_action" in result["extracted"]

    def test_parse_admin_prefix(self):
        """Test parsing admin: prefix."""
        text = "admin: File taxes by April 15"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "admin"
        assert "name" in result["extracted"]
        assert result["extracted"]["due_date"] is None
        assert "notes" in result["extracted"]

    def test_parse_decision_prefix_with_rationale(self):
        """Test parsing decision: prefix with 'because' rationale."""
        text = "decision: Use pytest for testing because it has great async support"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "decisions"
        assert "title" in result["extracted"]
        assert "Use pytest for testing" in result["extracted"]["decision"]
        assert "great async support" in result["extracted"]["rationale"]

    def test_parse_decision_prefix_without_rationale(self):
        """Test parsing decision: prefix without rationale."""
        text = "decision: Use PostgreSQL for database"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "decisions"
        assert "title" in result["extracted"]
        assert "PostgreSQL" in result["extracted"]["decision"]
        assert result["extracted"]["rationale"] is None

    def test_parse_howto_prefix_with_separator(self):
        """Test parsing howto: prefix with arrow separator."""
        text = "howto: Deploy to production → docker build && docker push"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "howtos"
        assert "title" in result["extracted"]
        assert "Deploy to production" == result["extracted"]["title"]
        assert "docker build" in result["extracted"]["content"]

    def test_parse_howto_prefix_with_dash_separator(self):
        """Test parsing howto: prefix with dash separator."""
        text = "howto: Run tests - pytest tests/"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "howtos"
        assert "Run tests" == result["extracted"]["title"]
        assert "pytest tests/" in result["extracted"]["content"]

    def test_parse_snippet_prefix_with_separator(self):
        """Test parsing snippet: prefix with separator."""
        text = "snippet: Git force push → git push --force-with-lease"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "snippets"
        assert "Git force push" == result["extracted"]["title"]
        assert "git push --force-with-lease" in result["extracted"]["content"]

    def test_parse_no_prefix(self):
        """Test that text without prefix returns None."""
        text = "This is just a regular message"
        result = parse_reference(text)

        assert result is None

    def test_parse_case_insensitive(self):
        """Test that prefixes are case insensitive."""
        text = "IDEA: Test case insensitivity"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "ideas"

    def test_parse_with_extra_whitespace(self):
        """Test parsing with extra whitespace after colon."""
        text = "project:    Test whitespace handling"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "projects"
        assert "Test whitespace handling" in result["extracted"]["name"]

    def test_parse_multiline_content(self):
        """Test parsing content with newlines."""
        text = "idea: Multi-line idea\nLine 2\nLine 3"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "ideas"
        assert "Multi-line idea" in result["extracted"]["title"]
        assert "\n" in result["extracted"]["elaboration"]

    def test_parse_empty_content_after_prefix(self):
        """Test parsing with minimal content after prefix."""
        text = "idea: x"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "ideas"
        assert result["extracted"]["title"] == "x"

    def test_parse_snippet_without_separator(self):
        """Test parsing snippet without separator uses full content."""
        text = "snippet: docker ps"
        result = parse_reference(text)

        assert result is not None
        assert result["category"] == "snippets"
        assert result["extracted"]["title"] == "docker ps"
        assert result["extracted"]["content"] == "docker ps"
