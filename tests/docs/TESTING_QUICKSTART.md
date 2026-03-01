# Testing Quick Start Guide

**Quick reference for implementing and running tests in Chronometry**

## Current Test Coverage

### ✅ Fully Tested (>80%)
- `common.py` - Utilities, config loading, path helpers, cleanup

### ⏳ Partially Tested (30-50%)
- `capture.py` - Basic capture iteration tests exist
- `annotate.py` - API validation tests exist

### ❌ Not Tested (0%)
- `timeline.py` - No tests
- `digest.py` - No tests
- `token_usage.py` - No tests
- `web_server.py` - No tests
- `menubar_app.py` - No tests

---

## Quick Test Commands

### Run All Tests
```bash
pytest tests/ -v
```

### Run with Coverage
```bash
pytest tests/ -v --cov=src --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Run Specific Module Tests
```bash
pytest tests/test_common.py -v
pytest tests/test_capture.py -v
pytest tests/test_annotate.py -v
```

### Run with Markers
```bash
pytest -m unit         # Unit tests only
pytest -m integration  # Integration tests only
pytest -m slow         # Slow tests only
```

---

## Test File Structure

```
tests/
├── __init__.py
├── fixtures/
│   ├── config_test.yaml           # Test configuration
│   ├── sample_images/             # Sample PNG files
│   └── sample_annotations/        # Sample JSON files
├── test_common.py                 # ✅ Common utilities
├── test_capture.py                # ⏳ Capture module
├── test_annotate.py               # ⏳ Annotation module
├── test_timeline.py               # ❌ TODO: Timeline module
├── test_digest.py                 # ❌ TODO: Digest module
├── test_token_usage.py            # ❌ TODO: Token tracking
├── test_web_server.py             # ❌ TODO: Web API
└── integration/
    ├── test_capture_to_annotate.py    # ❌ TODO
    ├── test_annotate_to_timeline.py   # ❌ TODO
    └── test_full_workflow.py          # ❌ TODO
```

---

## Priority 1: Critical Path Tests (MUST HAVE)

### 1. Timeline Module (`test_timeline.py`)
**Why:** Core visualization feature - currently untested!

```python
# Key tests needed:
- Batch deduplication
- Activity categorization
- Activity grouping
- Statistics calculation
- HTML generation
```

**Estimated effort:** 4-6 hours

### 2. Digest Module (`test_digest.py`)
**Why:** AI-powered feature - API calls need testing!

```python
# Key tests needed:
- LLM API calls (mocked)
- Category summary generation
- Overall summary generation
- Caching mechanism
- Token tracking integration
```

**Estimated effort:** 3-4 hours

### 3. Token Usage Module (`test_token_usage.py`)
**Why:** Critical for cost tracking!

```python
# Key tests needed:
- Token logging
- File locking (race conditions)
- Daily usage retrieval
- Usage summary
```

**Estimated effort:** 2-3 hours

---

## Priority 2: Important Features (SHOULD HAVE)

### 4. Web Server Module (`test_web_server.py`)
**Why:** API endpoints need validation!

```python
# Key tests needed:
- All GET endpoints
- Configuration update (PUT)
- Export functionality (CSV/JSON)
- WebSocket events
- Error handling
```

**Estimated effort:** 5-7 hours

### 5. Enhanced Capture Tests
**Why:** Fill gaps in existing coverage!

```python
# Missing tests:
- Region capture (interactive)
- Full capture loop
- Statistics tracking
- Error recovery
```

**Estimated effort:** 2-3 hours

### 6. Enhanced Annotation Tests
**Why:** Fill gaps in batch processing!

```python
# Missing tests:
- Batch processing
- Cross-midnight handling
- Retry logic
- Yesterday folder check
```

**Estimated effort:** 2-3 hours

---

## Priority 3: Integration & E2E (NICE TO HAVE)

### 7. Integration Tests
```python
# tests/integration/test_capture_to_annotate.py
def test_captured_frame_gets_annotated():
    """Capture a frame, then annotate it"""
    pass

# tests/integration/test_annotate_to_timeline.py
def test_annotations_appear_in_timeline():
    """Annotate frames, then generate timeline"""
    pass

# tests/integration/test_full_workflow.py
def test_capture_annotate_timeline_digest():
    """Full end-to-end workflow"""
    pass
```

**Estimated effort:** 6-8 hours

---

## Test Template

Use this template for new test files:

```python
"""Tests for <module_name>.py"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

from chronometry.<module_name> import <functions>

from <module_name> import <functions_to_test>


class Test<ClassName>:
    """Tests for <ClassName> functionality."""
    
    @pytest.fixture
    def sample_data(self):
        """Provide sample test data."""
        return {...}
    
    def test_basic_functionality(self, sample_data):
        """Test basic functionality works."""
        result = function_under_test(sample_data)
        assert result == expected_value
    
    def test_error_handling(self):
        """Test error handling."""
        with pytest.raises(ValueError):
            function_under_test(invalid_input)
    
    @patch('module_name.external_dependency')
    def test_with_mocks(self, mock_dependency):
        """Test with mocked dependencies."""
        mock_dependency.return_value = Mock(...)
        result = function_under_test()
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Common Mocking Patterns

### Mock Vision API Call
```python
@patch('src.llm_backends.call_ollama_vision')
def test_vision_api(mock_vision):
    mock_vision.return_value = {'summary': 'test summary', 'sources': []}
    # Your test code here
```

### Mock Text API Call
```python
@patch('src.digest.call_text_api')
def test_text_api(mock_text):
    mock_text.return_value = {
        'content': 'test', 'tokens': 100,
        'prompt_tokens': 60, 'completion_tokens': 40
    }
    # Your test code here
```

### Mock File System
```python
def test_with_temp_dir(tmp_path):
    """Use pytest's tmp_path fixture for temporary directories."""
    test_file = tmp_path / "test.json"
    test_file.write_text('{"test": true}')
    # Your test code here
```

### Mock Screenshot Capture
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
    
    # Your test code here
```

---

## Test Data Fixtures

### Create Test Config
```python
@pytest.fixture
def test_config(tmp_path):
    """Provide test configuration."""
    return {
        'root_dir': str(tmp_path / 'data'),
        'capture': {
            'capture_interval_seconds': 900,
            'monitor_index': 1,
            'retention_days': 30
        },
        'annotation': {
            'api_url': 'https://test.example.com/api',
            'prompt': 'Test prompt',
            'batch_size': 4,
            'timeout_sec': 30
        },
        'timeline': {
            'bucket_minutes': 15,
            'gap_minutes': 5
        },
        'digest': {
            'enabled': True,
            'interval_seconds': 3600,
            'model': 'gpt-4o',
            'temperature': 0.7
        }
    }
```

### Create Test Frames
```python
@pytest.fixture
def sample_frames(tmp_path):
    """Create sample frame files."""
    frames_dir = tmp_path / 'frames' / '2025-11-01'
    frames_dir.mkdir(parents=True)
    
    # Create 3 test frames
    for i in range(3):
        png_file = frames_dir / f'20251101_10{i:02d}00.png'
        json_file = frames_dir / f'20251101_10{i:02d}00.json'
        
        # Minimal PNG (1x1 pixel)
        png_file.write_bytes(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        
        # JSON annotation
        json_file.write_text(f'{{"timestamp": "20251101_10{i:02d}00", "summary": "Test activity", "image_file": "20251101_10{i:02d}00.png"}}')
    
    return frames_dir
```

---

## Test Coverage Goals

| Module | Current | Target | Status |
|--------|---------|--------|--------|
| common.py | 85% | 90% | ✅ Good |
| capture.py | 40% | 80% | ⚠️ Needs work |
| annotate.py | 30% | 80% | ⚠️ Needs work |
| timeline.py | 0% | 80% | ❌ Critical |
| digest.py | 0% | 80% | ❌ Critical |
| token_usage.py | 0% | 80% | ❌ Critical |
| web_server.py | 0% | 70% | ⚠️ Medium |
| menubar_app.py | 0% | 50% | ⏳ Low priority |
| **Overall** | **25%** | **80%** | **⚠️ Action needed** |

---

## Implementation Roadmap

### Week 1: Critical Modules
- [ ] Day 1-2: `test_timeline.py` (4-6 hours)
- [ ] Day 3: `test_digest.py` (3-4 hours)
- [ ] Day 4: `test_token_usage.py` (2-3 hours)
- [ ] Day 5: Review & fix issues

### Week 2: Important Features
- [ ] Day 1-2: `test_web_server.py` (5-7 hours)
- [ ] Day 3: Enhanced `test_capture.py` (2-3 hours)
- [ ] Day 4: Enhanced `test_annotate.py` (2-3 hours)
- [ ] Day 5: Review & fix issues

### Week 3: Integration & Polish
- [ ] Day 1-2: Integration tests (6-8 hours)
- [ ] Day 3: End-to-end tests
- [ ] Day 4: Performance tests
- [ ] Day 5: Documentation & cleanup

---

## Running CI/CD Tests

### GitHub Actions Workflow
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
      - run: pip install -r requirements.txt
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/ -v --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v2
```

---

## Troubleshooting Tests

### Tests fail with "ModuleNotFoundError"
```bash
# Ensure the package is installed (pip install -e .)
pytest tests/ -v
```

### Mock not working
```python
# Use correct patch path (where it's imported, not where it's defined)
# BAD:  @patch('subprocess.run')
# GOOD: @patch('annotate.subprocess.run')
```

### Temp files not cleaned up
```python
# Use pytest's tmp_path fixture instead of manual cleanup
def test_something(tmp_path):
    test_file = tmp_path / "test.txt"
    # No cleanup needed - pytest handles it
```

### Tests are slow
```python
# Mark slow tests and skip them during development
@pytest.mark.slow
def test_large_dataset():
    pass

# Run only fast tests:
pytest tests/ -v -m "not slow"
```

---

## Quick Wins (Easy Tests to Add)

### 1. Timeline Categorization (15 minutes)
```python
def test_categorize_code_activity():
    summary = "Working on Python code in VSCode"
    category, icon, color = categorize_activity(summary)
    assert category == "Code"
    assert icon == "💻"
```

### 2. Token Logging (20 minutes)
```python
def test_log_tokens(tmp_path):
    tracker = TokenUsageTracker(str(tmp_path))
    tracker.log_tokens('digest', 100, 60, 40, 'Test context')
    
    # Verify file created
    log_file = tmp_path / 'token_usage' / f'{datetime.now().strftime("%Y-%m-%d")}.json'
    assert log_file.exists()
```

### 3. Digest Caching (15 minutes)
```python
def test_load_cached_digest(tmp_path):
    # Create fake cache
    cache_dir = tmp_path / 'digests'
    cache_dir.mkdir()
    cache_file = cache_dir / 'digest_2025-11-01.json'
    cache_file.write_text('{"date": "2025-11-01"}')
    
    # Load it
    config = {'root_dir': str(tmp_path)}
    digest = load_cached_digest(datetime(2025, 11, 1), config)
    assert digest['date'] == '2025-11-01'
```

---

## Resources

- **pytest Documentation:** https://docs.pytest.org/
- **Mocking Guide:** https://docs.python.org/3/library/unittest.mock.html
- **Coverage.py:** https://coverage.readthedocs.io/
- **Test Fixtures:** https://docs.pytest.org/en/stable/fixture.html

---

**Next Steps:**
1. Review TEST_PLAN.md for detailed test cases
2. Start with Priority 1 tests (timeline, digest, token_usage)
3. Run tests frequently during development
4. Aim for 80% coverage before release

**Goal:** Get from 25% to 80% coverage in 3 weeks 🚀

