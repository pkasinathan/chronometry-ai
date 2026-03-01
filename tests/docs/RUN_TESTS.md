# How to Run Tests - Quick Guide

## Prerequisites

```bash
cd /path/to/chronometry

# Activate virtual environment
source venv/bin/activate

# Install test dependencies (if not already installed)
pip install -r requirements-dev.txt
```

---

## Run All Tests

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=src --cov-report=html

# Open coverage report in browser
open htmlcov/index.html
```

---

## Run Individual Test Files

```bash
# Test digest module (AI-powered digest generation)
pytest tests/test_digest.py -v

# Test token usage module (API token tracking)
pytest tests/test_token_usage.py -v

# Test capture module (screen capture, camera/lock detection)
pytest tests/test_capture.py -v

# Test annotate module (AI annotation, batch processing)
pytest tests/test_annotate.py -v

# Test timeline module (visualization, categorization)
pytest tests/test_timeline.py -v

# Test web server module (API endpoints)
pytest tests/test_web_server.py -v

# Test menu bar module (macOS app)
pytest tests/test_menubar_app.py -v

# Test common module (utilities)
pytest tests/test_common.py -v
```

---

## Run Specific Test Classes

```bash
# Run only Text API tests
pytest tests/test_digest.py::TestTextAPI -v

# Run only camera detection tests
pytest tests/test_capture.py::TestCameraDetection -v

# Run only batch processing tests
pytest tests/test_annotate.py::TestBatchProcessing -v
```

---

## Run Specific Test Functions

```bash
# Run single test
pytest tests/test_digest.py::TestTextAPI::test_successful_api_call -v

# Run with output
pytest tests/test_capture.py::TestCameraDetection::test_detect_camera_via_system_logs -v -s
```

---

## Coverage Analysis

```bash
# Generate HTML coverage report
pytest tests/ -v --cov=src --cov-report=html --cov-report=term

# View coverage summary in terminal
pytest tests/ -v --cov=src --cov-report=term-missing

# Generate XML report (for CI/CD)
pytest tests/ -v --cov=src --cov-report=xml
```

---

## Debugging Tests

```bash
# Stop on first failure
pytest tests/ -v -x

# Show local variables on failure
pytest tests/ -v -l

# Run last failed tests only
pytest tests/ -v --lf

# Run with debugger on failure
pytest tests/ -v --pdb

# Show print statements
pytest tests/ -v -s
```

---

## Expected Results

### Test Count by File

| Test File | Test Count | Expected Status |
|-----------|-----------|-----------------|
| test_common.py | 60+ | ✅ Most pass |
| test_capture.py | 40+ | ✅ Most pass |
| test_annotate.py | 30+ | ✅ Most pass |
| test_timeline.py | 35+ | ✅ Most pass |
| test_digest.py | 34 | ✅ Most pass |
| test_token_usage.py | 31 | ⚠️ Some may fail |
| test_web_server.py | 33 | ⚠️ Some may fail |
| test_menubar_app.py | 37 | ⚠️ Some may fail |
| **Total** | **~253** | **~80% pass rate** |

### Expected Coverage

| Module | Target | Likely Result |
|--------|--------|---------------|
| common.py | 90% | ✅ 88-92% |
| capture.py | 80% | ✅ 75-85% |
| annotate.py | 80% | ✅ 75-85% |
| timeline.py | 80% | ✅ 70-80% |
| digest.py | 80% | ✅ 75-85% |
| token_usage.py | 80% | ⚠️ 70-80% |
| web_server.py | 70% | ⚠️ 60-75% |
| menubar_app.py | 50% | ⚠️ 45-55% |
| **Overall** | **75%** | **~70-80%** |

---

## Common Issues & Solutions

### Issue: "No module named pytest"
```bash
pip install -r requirements-dev.txt
```

### Issue: "ModuleNotFoundError: No module named 'src'"
```bash
# Ensure the package is installed first: pip install -e .
# If tests still fail, try:
export PYTHONPATH="${PYTHONPATH}:${PWD}"
pytest tests/ -v
```

### Issue: Tests fail with import errors
```bash
# Make sure you're in project root
cd /path/to/chronometry

# Make sure venv is activated
source venv/bin/activate

# Verify Python version
python --version  # Should be 3.8+
```

### Issue: Coverage report not generated
```bash
# Install coverage plugin
pip install pytest-cov

# Re-run with coverage
pytest tests/ -v --cov=src --cov-report=html
```

---

## Interpreting Results

### When Tests Pass ✅
- Feature is working correctly
- Code matches expected behavior
- No bugs in that functionality

### When Tests Fail ❌
- **DO NOT modify the test** (unless test itself has a bug)
- **DO NOT modify src/** (per requirements)
- Document the failure
- Note expected vs actual behavior
- Create bug ticket for source code fix

### Coverage Gaps
- Check `htmlcov/index.html` for uncovered lines
- Consider if additional tests needed
- May need integration/E2E tests

---

## Test Summary by Priority

### Priority 1: Critical (Must Pass)
```bash
pytest tests/test_common.py -v          # Utilities
pytest tests/test_capture.py -v         # Core capture
pytest tests/test_annotate.py -v        # Core annotation
pytest tests/test_timeline.py -v        # Core timeline
```

### Priority 2: Important (Should Pass)
```bash
pytest tests/test_digest.py -v          # AI features
pytest tests/test_token_usage.py -v     # Tracking
pytest tests/test_web_server.py -v      # API
```

### Priority 3: Nice to Have
```bash
pytest tests/test_menubar_app.py -v     # UI layer
```

---

## Quick Smoke Test

```bash
# Run one test from each module to verify setup
pytest tests/test_common.py::TestLoadConfig::test_load_config_valid -v
pytest tests/test_capture.py::TestCaptureIteration::test_successful_capture -v
pytest tests/test_annotate.py::TestEncodeImageToBase64::test_encode_image -v
pytest tests/test_timeline.py::TestCategorizeActivity::test_categorize_code -v
pytest tests/test_digest.py::TestTextAPI::test_successful_api_call -v
pytest tests/test_token_usage.py::TestTokenUsageTrackerInit::test_init_creates_tracker -v
```

If all 6 pass, setup is correct!

---

## Performance

### Expected Test Execution Time
- Individual test file: 1-5 seconds
- All tests: 20-40 seconds
- With coverage: 30-60 seconds

### Optimization
```bash
# Run tests in parallel (requires pytest-xdist)
pip install pytest-xdist
pytest tests/ -v -n auto
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
      - run: pip install -r requirements.txt
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/ -v --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v2
```

---

## Documentation References

- **TEST_PLAN.md** - Comprehensive test plan (400+ test cases documented)
- **TESTING_QUICKSTART.md** - Quick start guide and templates
- **TESTING_SUMMARY.md** - Executive summary and risk analysis
- **TEST_IMPLEMENTATION_COMPLETE.md** - This implementation summary
- **tests/README.md** - Test suite documentation

---

**Ready to Run:** ✅ YES  
**Dependencies:** pytest, pytest-cov (in requirements-dev.txt)  
**Estimated Time:** 30-60 seconds for full suite  
**Expected Pass Rate:** ~80% (intentional - some tests may expose bugs)

---

## Contact & Support

If tests fail:
1. Review test output carefully
2. Check TEST_PLAN.md for expected behavior
3. Document the bug
4. DO NOT modify tests to make them pass
5. Plan source code fixes for next phase

**Remember:** Failing tests are valuable - they help find bugs! 🐛

