# Chronometry Test Suite

**Comprehensive testing for the Chronometry work activity analyzer**

---

## Quick Start

### Run All Tests
```bash
# From project root
pytest tests/ -v
```

### Run with Coverage
```bash
pytest tests/ -v --cov=src --cov-report=html
open htmlcov/index.html
```

### Run Specific Test File
```bash
pytest tests/test_timeline.py -v
pytest tests/test_common.py -v
pytest tests/test_capture.py -v
```

---

## Test Files

### ✅ Implemented

| File | Coverage | Lines | Status |
|------|----------|-------|--------|
| `test_common.py` | ~85% | 232 lines | ✅ Good |
| `test_capture.py` | ~40% | 292 lines | ⏳ Partial |
| `test_annotate.py` | ~30% | 137 lines | ⏳ Partial |
| `test_timeline.py` | **NEW** | **500+ lines** | ✅ **Complete** |

### ❌ TODO (High Priority)

- [ ] `test_digest.py` - AI digest generation
- [ ] `test_token_usage.py` - Token tracking
- [ ] `test_web_server.py` - Web API endpoints
- [ ] `test_menubar_app.py` - Menu bar app

### ❌ TODO (Integration)

- [ ] `integration/test_capture_to_annotate.py`
- [ ] `integration/test_annotate_to_timeline.py`
- [ ] `integration/test_timeline_to_digest.py`
- [ ] `integration/test_full_workflow.py`

---

## Test Coverage Summary

### Current Status
```
Overall Coverage: ~25%

✅ common.py         85% (Good)
⏳ capture.py        40% (Needs work)
⏳ annotate.py       30% (Needs work)
🆕 timeline.py       70% (NEW - Good)
❌ digest.py         0% (Critical gap)
❌ token_usage.py    0% (Critical gap)
❌ web_server.py     0% (High priority)
❌ menubar_app.py    0% (Medium priority)
```

### Target: 80%+ Overall Coverage

---

## Test Categories

### Unit Tests
**Location:** `tests/test_*.py`  
**Purpose:** Test individual functions and methods  
**Coverage:** ~25% current, target 80%

**Examples:**
- Configuration loading and validation
- Path helpers and date formatting
- Activity categorization
- Statistics calculation

### Integration Tests
**Location:** `tests/integration/`  
**Purpose:** Test module interactions  
**Coverage:** 0% current, target 70%

**Examples:**
- Capture → Annotation flow
- Annotation → Timeline flow
- Timeline → Digest flow
- Full workflow end-to-end

### E2E Tests
**Location:** `tests/e2e/`  
**Purpose:** Test complete user scenarios  
**Coverage:** 0% current, target 50%

**Examples:**
- Full day workflow
- Privacy protection scenarios
- Configuration changes
- Error recovery

---

## Test Structure

### Standard Test File Template

```python
"""Tests for <module_name>.py"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

from chronometry.<module_name> import <functions>


class Test<ClassName>:
    """Tests for <ClassName> functionality."""
    
    @pytest.fixture
    def sample_data(self):
        """Provide test data."""
        return {...}
    
    def test_basic_functionality(self, sample_data):
        """Test basic functionality."""
        result = function(sample_data)
        assert result == expected
    
    def test_error_handling(self):
        """Test error cases."""
        with pytest.raises(ValueError):
            function(invalid_input)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Fixtures

### Configuration Fixtures

Defined in `conftest.py`:

- **`sample_config`** — Returns a dict with full config including `model_name: "qwen3-vl:8b"`, annotation/digest backends, capture settings, timeline, notifications, and categories. Uses `tmp_path` for `root_dir`.
- **`isolate_chronometry_home`** (autouse) — Redirects `CHRONOMETRY_HOME` to `tmp_path/.chronometry` so tests never touch the real `~/.chronometry` directory.

The project uses a two-file config system:
- `system_config.yaml` — Defaults shipped with the package (not user-edited)
- `user_config.yaml` — User overrides merged on top of system defaults

### Sample Data Fixtures

Located in `fixtures/`:
- `sample_images/` - Test PNG files
- `sample_annotations/` - Test JSON files
- `sample_timelines/` - Test HTML files

---

## Mocking Patterns

### Mock Vision API (annotation backend)
```python
@patch('src.llm_backends.call_ollama_vision')
def test_vision(mock_vision):
    mock_vision.return_value = {'summary': 'test', 'sources': []}
    # Test code
```

### Mock Text API (digest backend)
```python
@patch('src.digest.call_text_api')
def test_text(mock_text):
    mock_text.return_value = {
        'content': 'test', 'tokens': 0,
        'prompt_tokens': 0, 'completion_tokens': 0
    }
    # Test code
```

### Mock File System
```python
def test_with_temp_files(tmp_path):
    """Use pytest's tmp_path fixture."""
    test_file = tmp_path / "test.json"
    test_file.write_text('{"test": true}')
    # Test code
```

### Mock Screenshots
```python
@patch('capture.Image')
@patch('capture.mss.mss')
def test_capture(mock_mss, mock_image):
    mock_screenshot = Mock()
    mock_screenshot.size = (1920, 1080)
    mock_screenshot.bgra = b'\x00' * (1920 * 1080 * 4)
    
    mock_sct = Mock()
    mock_sct.grab.return_value = mock_screenshot
    mock_mss.return_value.__enter__.return_value = mock_sct
    # Test code
```

---

## Test Markers

### Available Markers

```python
@pytest.mark.unit
def test_unit():
    """Unit test marker"""
    pass

@pytest.mark.integration
def test_integration():
    """Integration test marker"""
    pass

@pytest.mark.slow
def test_slow():
    """Slow test marker (> 1 second)"""
    pass

@pytest.mark.requires_api
def test_api():
    """Requires external API marker"""
    pass
```

### Run by Marker
```bash
pytest -m unit              # Unit tests only
pytest -m integration       # Integration tests only
pytest -m "not slow"        # Skip slow tests
pytest -m "unit or integration"  # Multiple markers
```

---

## Common Test Commands

### Basic Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific file
pytest tests/test_timeline.py -v

# Run specific test
pytest tests/test_timeline.py::TestCategorizeActivity::test_categorize_code -v

# Run with output
pytest tests/ -v -s  # -s shows print statements
```

### Coverage Testing
```bash
# Generate HTML report
pytest tests/ -v --cov=src --cov-report=html
open htmlcov/index.html

# Generate terminal report
pytest tests/ -v --cov=src --cov-report=term

# Generate XML report (for CI)
pytest tests/ -v --cov=src --cov-report=xml
```

### Debugging
```bash
# Stop on first failure
pytest tests/ -v -x

# Show local variables on failure
pytest tests/ -v -l

# Run last failed tests only
pytest tests/ -v --lf

# Run with pdb on failure
pytest tests/ -v --pdb
```

### Performance
```bash
# Show slowest 10 tests
pytest tests/ -v --durations=10

# Parallel execution (requires pytest-xdist)
pytest tests/ -v -n auto
```

---

## Best Practices

### 1. Test Naming
```python
# Good
def test_categorize_code_activity():
    """Test code activity categorization."""
    
# Bad
def test_1():
    """Test something."""
```

### 2. Arrange-Act-Assert Pattern
```python
def test_example():
    # Arrange - Setup test data
    data = {"key": "value"}
    
    # Act - Execute function
    result = process(data)
    
    # Assert - Verify result
    assert result == expected
```

### 3. One Assertion Per Test
```python
# Good
def test_category():
    category, icon, color = categorize_activity("coding")
    assert category == "Code"

def test_icon():
    category, icon, color = categorize_activity("coding")
    assert icon == "💻"

# Acceptable (related assertions)
def test_categorize_code():
    category, icon, color = categorize_activity("coding")
    assert category == "Code"
    assert icon == "💻"
    assert color == "#E50914"
```

### 4. Use Fixtures for Common Setup
```python
@pytest.fixture
def test_config():
    return {
        'root_dir': '/tmp/test',
        'capture': {...}
    }

def test_with_config(test_config):
    # Use test_config
    pass
```

### 5. Mock External Dependencies
```python
# Always mock external APIs, file system (when appropriate), time
@patch('module.external_api')
@patch('module.datetime')
def test_function(mock_datetime, mock_api):
    # Test with mocks
    pass
```

---

## Continuous Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: macos-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run tests
        run: |
          pytest tests/ -v --cov=src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          files: ./coverage.xml
```

---

## Troubleshooting

### "ModuleNotFoundError"
```bash
# Ensure the package is installed (pip install -e .)
pytest tests/ -v
```

### "No module named pytest"
```bash
# Install dev dependencies
pip install -r requirements-dev.txt
```

### "Mock not working"
```python
# Use correct patch path (where imported, not defined)
# BAD:  @patch('subprocess.run')
# GOOD: @patch('annotate.subprocess.run')
```

### Tests are slow
```bash
# Use markers to skip slow tests
pytest -m "not slow"

# Or parallelize
pytest -n auto  # Requires pytest-xdist
```

### Temp files not cleaned
```python
# Use pytest's tmp_path fixture
def test_something(tmp_path):
    # tmp_path is automatically cleaned
    pass
```

---

## Current Priorities

### 🔴 Critical (This Week)
1. Run new timeline tests: `pytest tests/test_timeline.py -v`
2. Implement digest tests (~3-4 hours)
3. Implement token usage tests (~2-3 hours)

### 🟡 High (Next Week)
1. Implement web server tests (~5-7 hours)
2. Enhance capture tests (~2-3 hours)
3. Enhance annotation tests (~2-3 hours)

### 🟢 Medium (Week 3)
1. Integration tests (~6-8 hours)
2. E2E tests (~4-6 hours)
3. Performance tests (~2-3 hours)

---

## Documentation

- **TEST_PLAN.md** - Comprehensive test plan with 400+ test cases
- **TESTING_QUICKSTART.md** - Quick reference and templates
- **TESTING_SUMMARY.md** - Executive summary and recommendations
- **This README** - Test suite overview

---

## Metrics

### Coverage Goals

| Phase | Target | Status |
|-------|--------|--------|
| Current | 25% | 🟡 Below target |
| MVP | 60% | ⚠️ Critical gaps |
| Production | 80% | 🔴 Action needed |
| Excellence | 90%+ | 🔴 Major work |

### Module Targets

| Module | Current | Target |
|--------|---------|--------|
| common.py | 85% | ✅ |
| capture.py | 40% | 80% |
| annotate.py | 30% | 80% |
| timeline.py | 70% | 80% |
| digest.py | 0% | 80% ⚠️ |
| token_usage.py | 0% | 80% ⚠️ |
| web_server.py | 0% | 70% |

---

## Quick Wins

These tests can be added quickly (< 30 min each):

1. ✅ Timeline categorization (see `test_timeline.py`)
2. Duration formatting (see `test_timeline.py`)
3. Batch deduplication (see `test_timeline.py`)
4. Token logging basics
5. Digest caching

---

## Resources

- **pytest docs:** https://docs.pytest.org/
- **unittest.mock:** https://docs.python.org/3/library/unittest.mock.html
- **coverage.py:** https://coverage.readthedocs.io/
- **pytest fixtures:** https://docs.pytest.org/en/stable/fixture.html

---

## Getting Help

1. Review test examples in existing test files
2. Check TESTING_QUICKSTART.md for templates
3. Review TEST_PLAN.md for detailed scenarios
4. Run `pytest tests/test_timeline.py -v` to see comprehensive example

---

**Status:** ⚠️ In Progress - 25% coverage, target 80%  
**Last Updated:** November 1, 2025  
**Maintainer:** QA Team
