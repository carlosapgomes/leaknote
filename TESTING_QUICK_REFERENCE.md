# Testing Quick Reference

## Current Status

✅ **Unit Tests**: 98/98 passing (100%)
⚠️ **Integration Tests**: 2/40 passing (async mocking needs fix)
✅ **Bugs**: 2 found and fixed
⚡ **Speed**: <0.2s execution time

---

## Run Tests

```bash
# All unit tests (recommended)
uv run pytest tests/unit/ -v

# Quick run (no output, just pass/fail)
uv run pytest tests/unit/ --no-cov -q

# Specific test file
uv run pytest tests/unit/test_commands.py -v

# Specific test function
uv run pytest tests/unit/test_commands.py::TestParseCommand::test_parse_projects_command_no_status -v

# Tests matching a pattern
uv run pytest -k "admin" -v

# Only unit tests (using marker)
uv run pytest -m unit -v
```

---

## Expected Output

```
======================== 98 passed, 2 skipped in 0.11s ========================
```

---

## What Was Fixed

### Bug #1: ?admin DUE
- Before: Showed all tasks ❌
- After: Shows only due tasks ✅

### Bug #2: ?projects ACTIVE
- Before: Returned empty ❌
- After: Shows active projects ✅

**Fix**: `bot/commands.py` line 62-63 (added `arg.lower()`)

---

## Test Files

**Unit Tests** (all passing):
- `test_classifier.py` - 15 tests
- `test_fix_handler.py` - 17 tests
- `test_commands.py` - 21 tests
- `test_command_parsing_edge_cases.py` - 36 tests
- `test_command_bugs.py` - 9 tests

**Integration Tests** (need async mock fix):
- `test_routing.py` - 11 tests
- `test_fix_handler.py` - 9 tests
- `test_query_commands.py` - 11 tests
- `test_command_flow.py` - 6 tests
- `test_clarification.py` - 3 tests

---

## Documentation

- **TESTING_IMPLEMENTATION_FINAL.md** - Complete summary (READ THIS FIRST)
- **BUGS_FIXED.md** - Bug fixes details
- **INTEGRATION_TESTS_TODO.md** - How to fix integration tests
- **tests/README.md** - Detailed testing guide

---

## Deploy

```bash
# Copy fixed file to container
docker cp bot/commands.py leaknote-bot:/app/bot/commands.py
docker compose restart leaknote

# Test in Matrix
?admin DUE
?projects ACTIVE
```

---

## Add to CI/CD

```bash
# Pre-commit hook
echo "uv run pytest tests/unit/ --no-cov -q" > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

---

## Key Metrics

- 138 total tests created
- 98 unit tests passing
- 2 bugs found and fixed
- 3 lines of code changed
- 8 documentation files created
- <0.2s test execution time
