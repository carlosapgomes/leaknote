# Leaknote Bot Test Suite

This directory contains automated tests for the Leaknote bot. The tests are organized into unit tests and integration tests.

## Test Structure

```
tests/
├── conftest.py              # Pytest configuration and shared fixtures
├── unit/                    # Unit tests (fast, isolated)
│   ├── test_classifier.py   # Tests for parse_reference function
│   ├── test_fix_handler.py  # Tests for fix command parsing
│   └── test_commands.py     # Tests for query command parsing
└── integration/             # Integration tests (slower, with mocks)
    ├── test_routing.py         # Message routing workflow tests
    ├── test_fix_handler.py     # Fix command workflow tests
    ├── test_query_commands.py  # Query command handling tests
    └── test_clarification.py   # Clarification workflow tests
```

## Running Tests

### Prerequisites

Install development dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Or with uv:

```bash
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

Run only unit tests (fast):
```bash
pytest -m unit
```

Run only integration tests:
```bash
pytest -m integration
```

### Run Specific Test Files

```bash
pytest tests/unit/test_classifier.py
pytest tests/integration/test_routing.py
```

### Run Specific Test Functions

```bash
pytest tests/unit/test_classifier.py::TestParseReference::test_parse_idea_prefix
```

### Run with Coverage Report

```bash
pytest --cov=bot --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`.

### Run with Verbose Output

```bash
pytest -v
```

### Run Tests in Parallel (faster)

```bash
pip install pytest-xdist
pytest -n auto
```

## Test Markers

Tests are marked with pytest markers for easy filtering:

- `@pytest.mark.unit` - Unit tests (fast, no external dependencies)
- `@pytest.mark.integration` - Integration tests (require mocked services)
- `@pytest.mark.slow` - Tests that take a long time to run

## Test Coverage

Current test coverage includes:

### Unit Tests

1. **Classifier (`test_classifier.py`)**
   - ✅ All 7 category prefixes (idea, person, project, admin, decision, howto, snippet)
   - ✅ Case insensitivity
   - ✅ Whitespace handling
   - ✅ Separator variations (→, ->, -, :)
   - ✅ Multiline content
   - ✅ Edge cases (empty content, no prefix)

2. **Fix Handler (`test_fix_handler.py`)**
   - ✅ All 7 category fix commands
   - ✅ Singular and plural forms
   - ✅ Case insensitivity
   - ✅ Whitespace handling
   - ✅ Invalid categories
   - ✅ Edge cases

3. **Commands (`test_commands.py`)**
   - ✅ All 6 query commands (?recall, ?search, ?people, ?projects, ?ideas, ?admin)
   - ✅ Command arguments
   - ✅ Case insensitivity
   - ✅ Invalid commands
   - ✅ Edge cases

### Integration Tests

1. **Message Routing (`test_routing.py`)**
   - ✅ Routing with all 7 category prefixes
   - ✅ LLM classification (high and low confidence)
   - ✅ LLM failure handling
   - ✅ Unknown category handling
   - ✅ Database insertion
   - ✅ Inbox log creation

2. **Fix Command Workflow (`test_fix_handler.py`)**
   - ✅ Fixing between all category combinations
   - ✅ Deleting old records
   - ✅ Creating new records
   - ✅ Updating inbox log
   - ✅ Same category rejection
   - ✅ Original message not found
   - ✅ Reference category handling

3. **Query Commands (`test_query_commands.py`)**
   - ✅ All 6 query commands
   - ✅ Filtering (projects by status, admin by due)
   - ✅ Empty result handling
   - ✅ LLM summarization
   - ✅ Database queries

4. **Clarification Workflow (`test_clarification.py`)**
   - ✅ Reply with category prefix
   - ✅ Reply with "skip"
   - ✅ Reply with new text
   - ✅ Quote extraction from replies
   - ✅ Low confidence triggers clarification
   - ✅ High confidence skips clarification
   - ✅ Thread following (get_original_event_id)

## Fixtures

The test suite includes several reusable fixtures defined in `conftest.py`:

- `mock_llm_client` - Mocked LLM client for testing classification
- `mock_db_pool` - Mocked database connection pool
- `sample_classification` - Sample LLM classification result
- `sample_project_classification` - Sample project classification
- `sample_inbox_log` - Sample inbox log entry
- `sample_pending_clarification` - Sample pending clarification
- `sample_matrix_event` - Sample Matrix message event
- `sample_matrix_reply_event` - Sample Matrix reply event

## Writing New Tests

### Unit Test Example

```python
import pytest
from bot.classifier import parse_reference

@pytest.mark.unit
def test_my_new_feature():
    """Test description."""
    result = parse_reference("idea: test")
    assert result is not None
    assert result["category"] == "ideas"
```

### Integration Test Example

```python
import pytest
from unittest.mock import patch

@pytest.mark.integration
@pytest.mark.asyncio
async def test_my_workflow(mock_db_pool, mock_llm_client):
    """Test description."""
    from bot.router import route_message

    with patch("router.get_pool", return_value=mock_db_pool):
        category, record_id, confidence, status = await route_message(
            text="test message",
            matrix_event_id="$test",
            matrix_room_id="!test",
        )

        assert status == "filed"
```

## Continuous Integration

These tests are designed to run in CI/CD pipelines. They don't require:
- Real Matrix server
- Real database
- Real LLM API

All external dependencies are mocked using pytest fixtures.

## Known Limitations

1. **Database Integration**: Tests use mocked database connections. For true end-to-end testing, consider using a test PostgreSQL instance.

2. **Matrix Client**: Tests mock the Matrix client. Real Matrix integration testing would require a test Matrix server.

3. **LLM Responses**: Tests use fixed mock responses. Real LLM variability isn't tested.

## Future Improvements

- [ ] Add end-to-end tests with test database
- [ ] Add performance/load tests
- [ ] Add Matrix client integration tests with synapse/dendrite test server
- [ ] Add property-based testing with hypothesis
- [ ] Add mutation testing with mutpy
