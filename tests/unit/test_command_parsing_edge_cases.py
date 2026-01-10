"""Comprehensive edge case tests for command parsing.

This test suite was created to investigate issues where some query commands
were being misclassified as regular messages instead of being recognized
as commands.
"""

import pytest
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bot"))

from commands import parse_command


@pytest.mark.unit
class TestCommandParsingEdgeCases:
    """Edge cases and potential failure modes for command parsing."""

    # Basic functionality (should all pass)

    def test_all_commands_basic_form(self):
        """Test that all commands work in basic form."""
        assert parse_command("?projects") == ("projects", None)
        assert parse_command("?ideas") == ("ideas", None)
        assert parse_command("?admin") == ("admin", None)
        assert parse_command("?recall test") == ("recall", "test")
        assert parse_command("?search test") == ("search", "test")
        assert parse_command("?people John") == ("people", "john")  # Normalized

    # Whitespace variations

    def test_leading_whitespace(self):
        """Commands with leading whitespace (should work - strip() is called)."""
        assert parse_command("  ?projects") == ("projects", None)
        assert parse_command("\t?ideas") == ("ideas", None)
        assert parse_command(" ?admin due") == ("admin", "due")

    def test_trailing_whitespace(self):
        """Commands with trailing whitespace (should work)."""
        assert parse_command("?projects  ") == ("projects", None)
        assert parse_command("?ideas\t") == ("ideas", None)
        assert parse_command("?admin due  ") == ("admin", "due")

    def test_extra_internal_whitespace(self):
        """Commands with extra internal whitespace."""
        # These should work - regex allows \s+
        assert parse_command("?admin    due") == ("admin", "due")
        assert parse_command("?projects    active") == ("projects", "active")
        assert parse_command("?search  multiple  spaces") == ("search", "multiple  spaces")

    # Case variations

    def test_uppercase_commands(self):
        """Commands in uppercase (should work - re.IGNORECASE)."""
        assert parse_command("?PROJECTS") == ("projects", None)
        assert parse_command("?IDEAS") == ("ideas", None)
        assert parse_command("?ADMIN DUE") == ("admin", "due")
        assert parse_command("?SEARCH test") == ("search", "test")

    def test_mixed_case_commands(self):
        """Commands in mixed case."""
        assert parse_command("?PrOjEcTs") == ("projects", None)
        assert parse_command("?IdEaS") == ("ideas", None)
        assert parse_command("?AdMiN DuE") == ("admin", "due")

    # Invalid formats that should NOT be recognized as commands

    def test_space_after_question_mark(self):
        """Space between ? and command should fail."""
        assert parse_command("? projects") is None
        assert parse_command("? ideas") is None
        assert parse_command("? admin") is None

    def test_missing_question_mark(self):
        """Commands without ? should fail."""
        assert parse_command("projects") is None
        assert parse_command("ideas") is None
        assert parse_command("admin") is None
        assert parse_command("search test") is None

    def test_typos_in_command_name(self):
        """Common typos should fail (not be recognized)."""
        assert parse_command("?project") is None  # Missing 's'
        assert parse_command("?idea") is None  # Missing 's'
        assert parse_command("?projet") is None  # Typo
        assert parse_command("?serach") is None  # Typo

    # Commands with arguments

    def test_projects_with_all_valid_statuses(self):
        """Test ?projects with all valid status arguments."""
        assert parse_command("?projects active") == ("projects", "active")
        assert parse_command("?projects waiting") == ("projects", "waiting")
        assert parse_command("?projects blocked") == ("projects", "blocked")
        assert parse_command("?projects someday") == ("projects", "someday")
        assert parse_command("?projects done") == ("projects", "done")

    def test_projects_with_invalid_status(self):
        """Test ?projects with invalid status (should fail)."""
        assert parse_command("?projects invalid") is None
        assert parse_command("?projects completed") is None  # Should be 'done'
        assert parse_command("?projects pending") is None

    def test_projects_with_case_variations(self):
        """Test ?projects status is case insensitive."""
        assert parse_command("?projects ACTIVE") == ("projects", "active")
        assert parse_command("?projects Waiting") == ("projects", "waiting")
        assert parse_command("?projects BLOCKED") == ("projects", "blocked")

    def test_admin_with_due_filter(self):
        """Test ?admin with due filter."""
        assert parse_command("?admin due") == ("admin", "due")
        assert parse_command("?admin DUE") == ("admin", "due")

    def test_admin_with_invalid_filter(self):
        """Test ?admin with invalid filter (should fail)."""
        assert parse_command("?admin pending") is None
        assert parse_command("?admin overdue") is None

    def test_search_with_various_queries(self):
        """Test ?search with different query types."""
        assert parse_command("?search docker") == ("search", "docker")
        assert parse_command("?search docker deployment") == ("search", "docker deployment")
        assert parse_command("?search how to deploy") == ("search", "how to deploy")
        assert parse_command("?search @user mentions") == ("search", "@user mentions")
        assert parse_command("?search #hashtags") == ("search", "#hashtags")

    def test_recall_with_various_queries(self):
        """Test ?recall with different query types."""
        assert parse_command("?recall git") == ("recall", "git")
        assert parse_command("?recall git workflow") == ("recall", "git workflow")
        assert parse_command("?recall how to restart") == ("recall", "how to restart")

    def test_people_with_various_names(self):
        """Test ?people with different name formats."""
        assert parse_command("?people John") == ("people", "john")  # Normalized
        assert parse_command("?people John Doe") == ("people", "john doe")  # Normalized
        assert parse_command("?people João") == ("people", "joão")  # Unicode normalized
        assert parse_command("?people @john") == ("people", "@john")  # With @ (lowercase)

    # Commands that require arguments but don't have them

    def test_search_without_query(self):
        """?search without query should fail."""
        assert parse_command("?search") is None
        assert parse_command("?search ") is None

    def test_recall_without_query(self):
        """?recall without query should fail."""
        assert parse_command("?recall") is None
        assert parse_command("?recall ") is None

    def test_people_without_name(self):
        """?people without name should fail."""
        assert parse_command("?people") is None
        assert parse_command("?people ") is None

    # Commands that don't accept arguments

    def test_ideas_with_argument_should_fail(self):
        """?ideas doesn't accept arguments."""
        assert parse_command("?ideas active") is None
        assert parse_command("?ideas recent") is None

    def test_projects_without_argument(self):
        """?projects without argument should work."""
        assert parse_command("?projects") == ("projects", None)

    def test_admin_without_argument(self):
        """?admin without argument should work."""
        assert parse_command("?admin") == ("admin", None)

    # Special characters and Unicode

    def test_unicode_in_search_query(self):
        """Test Unicode characters in search queries."""
        assert parse_command("?search café") == ("search", "café")  # Unicode preserved
        assert parse_command("?recall código") == ("recall", "código")  # Unicode preserved
        assert parse_command("?people João") == ("people", "joão")  # Normalized (Unicode lowercase)

    def test_special_characters_in_query(self):
        """Test special characters in queries."""
        assert parse_command("?search docker-compose") == ("search", "docker-compose")
        assert parse_command("?search file.txt") == ("search", "file.txt")
        assert parse_command("?recall git@github.com") == ("recall", "git@github.com")

    # Multiple question marks

    def test_multiple_question_marks(self):
        """Multiple question marks should fail."""
        assert parse_command("??projects") is None
        assert parse_command("???ideas") is None

    # Empty and whitespace-only

    def test_just_question_mark(self):
        """Just a question mark should fail."""
        assert parse_command("?") is None

    def test_question_mark_with_whitespace(self):
        """Question mark with only whitespace should fail."""
        assert parse_command("?   ") is None
        assert parse_command("?\t") is None

    # Commands in sentences (should NOT be recognized)

    def test_command_in_sentence(self):
        """Commands embedded in sentences should NOT be recognized."""
        assert parse_command("Can you ?search for this?") is None
        assert parse_command("I want to ?recall something") is None
        assert parse_command("What about ?projects status") is None

    def test_command_not_at_start(self):
        """Commands not at start of line should fail."""
        assert parse_command("Please ?projects") is None
        assert parse_command("Show me ?ideas") is None

    # Potential Matrix-specific issues

    def test_matrix_formatted_text(self):
        """Test that plain text commands work (Matrix sends plain and formatted)."""
        # Matrix might send both body (plain) and formatted_body (HTML)
        # We only parse body, so plain text should work
        assert parse_command("?projects") == ("projects", None)

    def test_commands_with_newlines(self):
        """Commands with newlines (multiline messages)."""
        # If Matrix sends a message with newline after command
        assert parse_command("?projects\n") == ("projects", None)
        assert parse_command("?ideas\nSome text after") is None  # Should fail - extra text

    # Regression tests for reported issues

    def test_reported_working_commands(self):
        """Commands that were reported as working in manual tests."""
        # From TESTING_STATUS.md lines 55-60
        assert parse_command("?projects") == ("projects", None)
        assert parse_command("?ideas") == ("ideas", None)
        assert parse_command("?admin") == ("admin", None)
        assert parse_command("?search docker") == ("search", "docker")
        assert parse_command("?recall git") is not None  # Should match recall
        assert parse_command("?people John") == ("people", "john")  # Normalized

    def test_exact_manual_test_cases(self):
        """Exact commands from TESTING_STATUS.md test section."""
        # Line 65: ?projects
        assert parse_command("?projects") == ("projects", None)
        # Line 68: ?search docker
        assert parse_command("?search docker") == ("search", "docker")


@pytest.mark.unit
class TestCommandParsingVsClassification:
    """Tests to ensure commands don't get sent to LLM classification."""

    def test_commands_should_not_need_classification(self):
        """All valid commands should be recognized, not sent to LLM."""
        # These should ALL return non-None (recognized as commands)
        commands = [
            "?projects",
            "?projects active",
            "?ideas",
            "?admin",
            "?admin due",
            "?search test",
            "?recall test",
            "?people John",
        ]

        for cmd in commands:
            result = parse_command(cmd)
            assert result is not None, f"Command '{cmd}' not recognized! Would be sent to LLM."

    def test_non_commands_return_none(self):
        """Non-commands should return None and be sent to LLM."""
        non_commands = [
            "This is a regular message",
            "idea: Build something",
            "project: My project",
            "What are my ?projects",  # Command in middle of text
            "? projects",  # Space after ?
        ]

        for text in non_commands:
            result = parse_command(text)
            assert result is None, f"Text '{text}' incorrectly recognized as command!"
