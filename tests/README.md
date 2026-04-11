# Testing Documentation

## Overview

This directory contains the test suite for the Infortic Scraper project. Tests are organized into unit tests (fast, isolated) and integration tests (slower, with real dependencies).

## Test Structure

```
tests/
├── unit/                    # Fast, isolated unit tests
│   ├── test_validator.py    # Data validation tests
│   ├── test_normalizer.py   # Data normalization tests
│   ├── test_helpers.py      # Helper function tests
│   ├── test_duplicate_detector.py  # Duplicate detection tests
│   └── test_config.py       # Configuration tests
├── integration/             # Slower tests with real dependencies
│   ├── test_extraction_pipeline.py  # Extraction pipeline tests
│   ├── test_database_operations.py  # Database operation tests
│   └── test_complete_pipeline.py    # End-to-end tests
├── fixtures/                # Test data
│   ├── sample_captions.json
│   └── sample_extracted.json
└── conftest.py              # Shared fixtures and configuration
```

## Running Tests

### Prerequisites

Install testing dependencies:
```bash
pip install -r requirements.txt
```

### All Tests

Run the complete test suite:
```bash
pytest
```

### Unit Tests Only (Fast)

Run only fast, isolated unit tests:
```bash
pytest tests/unit/ -m unit
```

### Integration Tests Only

Run tests with real dependencies (requires DATABASE_URL and GEMINI_API_KEY):
```bash
pytest tests/integration/ -m integration
```

### Specific Test File

Run a specific test file:
```bash
pytest tests/unit/test_validator.py -v
```

### With Coverage Report

Generate coverage report:
```bash
pytest --cov=src --cov-report=html
```

View coverage report:
```bash
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
```

### Quick Test (No Coverage)

Run tests without coverage calculation (faster):
```bash
pytest --no-cov
```

## Test Markers

Tests are marked with pytest markers for selective execution:

- `@pytest.mark.unit` - Fast, isolated unit tests
- `@pytest.mark.integration` - Tests with real dependencies
- `@pytest.mark.slow` - Tests that take >5 seconds

Run tests by marker:
```bash
pytest -m unit          # Only unit tests
pytest -m integration   # Only integration tests
pytest -m "not slow"    # Skip slow tests
```

## Writing Tests

### Test Naming Convention

- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

### Example Unit Test

```python
import pytest

@pytest.mark.unit
def test_validator_accepts_valid_data(sample_extracted_data):
    """Test that validator accepts valid opportunity data"""
    from database.validator import DataValidator
    
    is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
    
    assert is_valid is True
    assert len(errors) == 0
```

### Example Integration Test

```python
import pytest

@pytest.mark.integration
def test_database_connection():
    """Test database connection (requires DATABASE_URL)"""
    from database.client import DatabaseClient
    from extraction.utils.config import Config
    
    if not Config.DATABASE_URL:
        pytest.skip("DATABASE_URL not set")
    
    db = DatabaseClient(Config.DATABASE_URL)
    db.connect()
    
    result = db.execute_query("SELECT 1")
    assert result is not None
    
    db.close()
```

### Using Fixtures

Fixtures are defined in `conftest.py` and can be used in any test:

```python
def test_with_fixture(sample_extracted_data):
    """Fixture is automatically injected"""
    assert sample_extracted_data["post_id"] == "TEST_POST_123"
```

### Mocking External Dependencies

Use `pytest-mock` for mocking:

```python
def test_with_mock(mocker):
    """Mock external API call"""
    mock_api = mocker.patch('module.api_call')
    mock_api.return_value = {"status": "success"}
    
    result = function_that_calls_api()
    assert result["status"] == "success"
```

## Test Principles

1. **Test Real Scenarios** - Test actual use cases, not just happy paths
2. **Test Error Conditions** - Test what happens when things go wrong
3. **Test Edge Cases** - Test boundary conditions and unusual inputs
4. **Keep Tests Fast** - Unit tests should run in <1 second each
5. **Clear Test Names** - Test names should describe what they test
6. **One Assertion Focus** - Each test should focus on one behavior
7. **Arrange-Act-Assert** - Structure tests clearly:
   ```python
   def test_something():
       # Arrange - Set up test data
       data = {"key": "value"}
       
       # Act - Execute the code being tested
       result = function(data)
       
       # Assert - Verify the result
       assert result == expected
   ```

## Coverage Goals

- **Unit Tests:** 80%+ coverage of src/ directory
- **Integration Tests:** Critical paths covered
- **Overall:** 70%+ coverage (enforced by pytest.ini)

## CI/CD Integration

Tests run automatically in GitHub Actions:

- **On Push/PR:** Unit tests run on every push to main/develop
- **Before Daily Scrape:** Quick unit tests run before pipeline execution
- **On Release:** Full test suite including integration tests

See `.github/workflows/ci-test.yml` for CI configuration.

### CI Workflow

The CI workflow runs on:
- Push to `main` or `develop` branches
- Pull requests to `main`
- Manual trigger via workflow_dispatch

**Test Matrix:**
- Python 3.11
- Python 3.12

**Steps:**
1. Checkout code
2. Set up Python
3. Install dependencies
4. Install Tesseract OCR
5. Run linting (flake8)
6. Run unit tests
7. Run integration tests (without secrets)
8. Generate coverage report
9. Upload coverage to Codecov

### Daily Scrape Workflow

The daily scrape workflow includes a test step:
- Runs quick unit tests before pipeline execution
- Fails fast if tests fail (prevents bad code from running)
- Continues with pipeline if tests pass

### Setting Up CI

**Required Secrets:**
- `DATABASE_URL` - For integration tests (optional)
- `GEMINI_API_KEY` - For integration tests (optional)
- `INSTAGRAM_SESSION` - For scraper (required for daily scrape)

**Optional Configuration:**
- Enable Codecov for coverage reports
- Configure branch protection rules
- Set up status checks

### Viewing Test Results

**In GitHub Actions:**
1. Go to Actions tab
2. Select workflow run
3. View test results in job logs
4. Check test summary in workflow summary

**Coverage Reports:**
- Uploaded to Codecov automatically
- View at: https://codecov.io/gh/your-org/your-repo

## Troubleshooting

### Tests Fail with Import Errors

Make sure you're running tests from the project root:
```bash
cd infortic_scraper
pytest
```

### Integration Tests Fail

Integration tests require environment variables:
- `DATABASE_URL` - Neon PostgreSQL connection string
- `GEMINI_API_KEY` - Google Gemini API key

Set these in `config/.env` or skip integration tests:
```bash
pytest tests/unit/ -m unit
```

### Coverage Report Not Generated

Install coverage dependencies:
```bash
pip install pytest-cov
```

### Tests Run Slowly

Run only unit tests (fast):
```bash
pytest tests/unit/ -m unit --no-cov
```

## Best Practices

1. **Run Tests Before Committing**
   ```bash
   pytest tests/unit/ -m unit
   ```

2. **Check Coverage Regularly**
   ```bash
   pytest --cov=src --cov-report=term-missing
   ```

3. **Write Tests for Bug Fixes**
   - When fixing a bug, write a test that reproduces it first
   - Verify the test fails, then fix the bug
   - Verify the test passes after the fix

4. **Keep Tests Independent**
   - Tests should not depend on each other
   - Tests should not share state
   - Tests should be able to run in any order

5. **Use Descriptive Assertions**
   ```python
   # Good
   assert len(errors) == 0, f"Expected no errors, got: {errors}"
   
   # Better
   assert is_valid is True, f"Validation failed: {errors}"
   ```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Best Practices](https://docs.pytest.org/en/stable/goodpractices.html)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

## Questions?

If you have questions about testing, check:
1. This README
2. Existing test files for examples
3. `conftest.py` for available fixtures
4. Project documentation in `docs/`
