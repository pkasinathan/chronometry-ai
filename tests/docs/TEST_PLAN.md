# Chronometry - Comprehensive Test Plan

**Quality Assurance Test Plan for End-to-End Coverage**

## Executive Summary

This document defines comprehensive test cases for all Python modules in `src/*.py` to ensure the Chronometry system works correctly end-to-end. The test plan covers unit tests, integration tests, and end-to-end scenarios.

---

## 1. Module: `common.py` - Shared Utilities

### 1.1 Configuration Management

**Test Cases:**
- ✅ TC-COM-001: Load valid split configuration (user_config + system_config)
- ✅ TC-COM-002: Load legacy single config file
- ✅ TC-COM-003: Deep merge user config overrides system config
- ✅ TC-COM-004: Reject invalid YAML syntax
- ✅ TC-COM-005: Reject missing required sections (capture, annotation, timeline)
- ✅ TC-COM-006: Validate capture_interval_seconds > 0
- ✅ TC-COM-007: Validate batch_size >= 1
- ✅ TC-COM-008: Validate bucket_minutes >= 1
- ✅ TC-COM-009: Validate retention_days >= 0
- ✅ TC-COM-010: Validate monitor_index >= 0

**Edge Cases:**
- Config file not found → FileNotFoundError
- Invalid retention_days (negative) → ValueError
- Non-dictionary config → ValueError
- Missing root_dir → ValueError

### 1.2 Path Helpers

**Test Cases:**
- ✅ TC-COM-020: Generate daily directory path with date
- ✅ TC-COM-021: Generate daily directory path without date (uses current)
- ✅ TC-COM-022: Generate frame path with timestamp
- ✅ TC-COM-023: Convert PNG path to JSON path
- ✅ TC-COM-024: Create nested directories
- ✅ TC-COM-025: Convert relative path to absolute
- ✅ TC-COM-026: Handle already absolute paths

### 1.3 Monitor Configuration

**Test Cases:**
- ✅ TC-COM-030: Get monitor by valid index
- ✅ TC-COM-031: Get monitor with custom region
- TC-COM-032: Reject invalid monitor index
- TC-COM-033: Reject invalid region format (wrong length)
- TC-COM-034: Reject non-integer region values

### 1.4 Data Cleanup

**Test Cases:**
- ✅ TC-COM-040: Skip cleanup when retention_days = 0
- ✅ TC-COM-041: Delete frames older than retention_days
- ✅ TC-COM-042: Keep recent frames within retention period
- ✅ TC-COM-043: Delete old digest files
- ✅ TC-COM-044: Delete old token_usage files
- ✅ TC-COM-045: Delete old timeline HTML files
- TC-COM-046: Skip non-date directories (like "other_stuff")
- TC-COM-047: Safety check: reject root_dir outside project

### 1.5 Notification System

**Test Cases:**
- TC-COM-050: Show macOS notification via osascript
- TC-COM-051: Show notification with sound
- TC-COM-052: Handle notification failure gracefully
- TC-COM-053: Test all NotificationMessages constants

### 1.6 JSON Helpers

**Test Cases:**
- TC-COM-060: Save dict to JSON file
- TC-COM-061: Load JSON file to dict
- TC-COM-062: Handle invalid JSON gracefully

### 1.7 Date/Time Helpers

**Test Cases:**
- TC-COM-070: Format datetime as YYYY-MM-DD
- TC-COM-071: Format datetime as YYYYMMDD_HHMMSS
- TC-COM-072: Parse date string to datetime
- TC-COM-073: Parse timestamp string to datetime
- TC-COM-074: Handle invalid date formats

### 1.8 Calculation Helpers

**Test Cases:**
- TC-COM-080: Count unannotated frames in directory
- TC-COM-081: Calculate compensated sleep (with pre-notification)
- TC-COM-082: Calculate compensated sleep (without pre-notification)

---

## 2. Module: `capture.py` - Screen Capture

### 2.1 Screen Lock Detection

**Test Cases:**
- TC-CAP-001: Detect locked screen via ioreg
- TC-CAP-002: Detect screensaver running
- TC-CAP-003: Return False when screen is unlocked
- TC-CAP-004: Handle detection failure gracefully (fail-safe to unlocked)

### 2.2 Camera Detection

**Test Cases:**
- TC-CAP-010: Detect camera via system logs (com.apple.cmio)
- TC-CAP-011: Detect camera via ioreg (AppleCameraInterface)
- TC-CAP-012: Detect camera via Chrome CMIO usage
- TC-CAP-013: Detect FaceTime running
- TC-CAP-014: Return False when no camera active
- TC-CAP-015: Handle detection failure gracefully (fail-safe to not active)

### 2.3 Synthetic Annotations

**Test Cases:**
- TC-CAP-020: Create synthetic annotation when camera active
- TC-CAP-021: Create synthetic annotation when screen locked
- TC-CAP-022: Synthetic annotation includes timestamp, summary, reason
- TC-CAP-023: No PNG file created for synthetic annotation
- TC-CAP-024: Handle synthetic annotation creation failure

### 2.4 Single Frame Capture

**Test Cases:**
- ✅ TC-CAP-030: Capture screenshot successfully
- ✅ TC-CAP-031: Skip capture when screen locked
- ✅ TC-CAP-032: Skip capture when camera active
- TC-CAP-033: Create synthetic annotation on camera skip
- TC-CAP-034: Save screenshot to correct path (root_dir/frames/YYYY-MM-DD/YYYYMMDD_HHMMSS.png)
- TC-CAP-035: Show notification after successful capture
- TC-CAP-036: Show notification when capture skipped
- TC-CAP-037: Handle capture error gracefully

### 2.5 Region Capture

**Test Cases:**
- TC-CAP-040: Interactive region selection via macOS screencapture
- TC-CAP-041: User cancels region selection
- TC-CAP-042: Timeout after 60 seconds
- TC-CAP-043: Skip when screen locked
- TC-CAP-044: Skip when camera active
- TC-CAP-045: Save to correct timestamp path
- TC-CAP-046: Show notifications during process

### 2.6 Capture Iteration (Main Loop)

**Test Cases:**
- ✅ TC-CAP-050: Successful capture with all checks passing
- ✅ TC-CAP-051: Skip when screen locked
- ✅ TC-CAP-052: Skip when camera active
- ✅ TC-CAP-053: Create synthetic annotation on camera skip
- ✅ TC-CAP-054: Show pre-notification when enabled (not first capture)
- ✅ TC-CAP-055: Skip pre-notification on first capture
- TC-CAP-056: Sleep for pre_notify_seconds after notification
- TC-CAP-057: Additional 2-second sleep for notification disappear
- ✅ TC-CAP-058: Handle capture errors gracefully
- TC-CAP-059: Return correct status: 'captured', 'skipped_locked', 'skipped_camera', 'error'

### 2.7 Full Capture Loop

**Test Cases:**
- TC-CAP-060: Continuous capture at configured interval
- TC-CAP-061: Periodic cleanup every hour
- TC-CAP-062: Handle max consecutive errors (stop after 5)
- TC-CAP-063: Compensated sleep accounts for pre-notification
- TC-CAP-064: Track capture statistics (count, skipped, etc.)
- TC-CAP-065: Handle KeyboardInterrupt gracefully
- TC-CAP-066: Show final notification with count

---

## 3. Module: `annotate.py` - AI Annotation

### 3.1 Image Encoding

**Test Cases:**
- ✅ TC-ANN-001: Encode PNG to base64 string
- TC-ANN-002: Handle missing image file
- TC-ANN-003: Handle corrupted image file

### 3.2 Vision API

**Test Cases:**
- ✅ TC-ANN-010: Validate API URL (https/http only)
- ✅ TC-ANN-011: Reject invalid URL schemes (ftp, file, etc.)
- ✅ TC-ANN-012: Reject missing network location
- TC-ANN-013: Call Vision API with images
- TC-ANN-014: Parse successful JSON response
- ✅ TC-ANN-015: Handle invalid JSON response
- ✅ TC-ANN-016: Handle command failure (returncode != 0)
- TC-ANN-017: Handle timeout (30 seconds default)
- TC-ANN-018: Validate response structure (summary, sources)
- TC-ANN-019: Default missing 'summary' field to empty string
- TC-ANN-020: Default missing 'sources' field to empty list

### 3.3 Retry Logic

**Test Cases:**
- TC-ANN-030: Retry on failure (max 3 attempts)
- TC-ANN-031: Exponential backoff (1s, 2s, 4s)
- TC-ANN-032: Succeed on second attempt
- TC-ANN-033: Fail after max retries

### 3.4 Batch Processing

**Test Cases:**
- TC-ANN-040: Process batch of images
- TC-ANN-041: Save same summary to all frames in batch
- TC-ANN-042: Include batch_size in JSON metadata
- TC-ANN-043: Handle encode failure for individual images
- TC-ANN-044: Skip batch if no valid images
- TC-ANN-045: Handle API error gracefully

### 3.5 Frame Annotation

**Test Cases:**
- TC-ANN-050: Annotate all unannotated frames
- TC-ANN-051: Check yesterday's folder for cross-midnight frames
- TC-ANN-052: Process in batches of configured size
- TC-ANN-053: Annotate even if less than batch_size
- TC-ANN-054: Sort frames chronologically before processing
- TC-ANN-055: Return count of annotated frames
- TC-ANN-056: Handle no frames found
- TC-ANN-057: Handle all frames already annotated

---

## 4. Module: `timeline.py` - Timeline Generation

### 4.1 Batch Deduplication

**Test Cases:**
- TC-TIM-001: Group annotations with same summary (batch_size > 1)
- TC-TIM-002: Track all frames in batch
- TC-TIM-003: Single annotations (batch_size=1) kept as-is
- TC-TIM-004: Sort deduplicated results chronologically
- TC-TIM-005: Handle empty annotations list

### 4.2 Load Annotations

**Test Cases:**
- TC-TIM-010: Load all JSON files from daily directory
- TC-TIM-011: Parse timestamp from filename
- TC-TIM-012: Load corresponding PNG as base64
- TC-TIM-013: Handle missing PNG file gracefully
- TC-TIM-014: Deduplicate batch annotations
- TC-TIM-015: Skip corrupted JSON files
- TC-TIM-016: Sort annotations by datetime

### 4.3 Activity Categorization

**Test Cases:**
- TC-TIM-020: Categorize as 'Code' (coding, IDE, terminal, git)
- TC-TIM-021: Categorize as 'Meeting' (zoom, teams, call)
- TC-TIM-022: Categorize as 'Documentation' (writing, notes, readme)
- TC-TIM-023: Categorize as 'Email' (gmail, inbox)
- TC-TIM-024: Categorize as 'Browsing' (chrome, web)
- TC-TIM-025: Categorize as 'Video' (youtube, watching)
- TC-TIM-026: Categorize as 'Social' (twitter, facebook)
- TC-TIM-027: Categorize as 'Learning' (tutorial, course)
- TC-TIM-028: Categorize as 'Design' (figma, photoshop)
- TC-TIM-029: Default to 'Work' for uncategorized
- TC-TIM-030: Return correct icon and color

### 4.4 Activity Grouping

**Test Cases:**
- TC-TIM-040: Group annotations into continuous activities
- TC-TIM-041: Use gap_minutes from config
- TC-TIM-042: Extend activity if same category within gap
- TC-TIM-043: Start new activity if different category
- TC-TIM-044: Start new activity if gap exceeded
- TC-TIM-045: Handle batch frames with multiple timestamps
- TC-TIM-046: Track all frames in activity
- TC-TIM-047: Combine summaries for extended activities

### 4.5 Statistics Calculation

**Test Cases:**
- TC-TIM-050: Calculate total_activities, total_time, focus_time, distraction_time
- TC-TIM-051: Calculate focus_percentage
- TC-TIM-052: Calculate distraction_percentage
- TC-TIM-053: Category breakdown (time per category)
- TC-TIM-054: Handle empty activities list
- TC-TIM-055: Classify focus categories (Code, Documentation, Work, Learning, Design)
- TC-TIM-056: Classify distraction categories (Video, Social, Browsing)

### 4.6 HTML Generation

**Test Cases:**
- TC-TIM-060: Generate complete HTML timeline
- TC-TIM-061: Include activity cards with icons, colors, summaries
- TC-TIM-062: Include detail panels with screenshots
- TC-TIM-063: Include filter buttons by category
- TC-TIM-064: Include stats overlay with focus percentage
- TC-TIM-065: Handle activities with no screenshots
- TC-TIM-066: JavaScript for interactivity (click, filter)

### 4.7 Timeline Generation

**Test Cases:**
- TC-TIM-070: Generate timeline for specific date
- TC-TIM-071: Save to output_dir/timeline_YYYY-MM-DD.html
- TC-TIM-072: Handle no data for date
- TC-TIM-073: Handle no annotations
- TC-TIM-074: Create output directory if missing

---

## 5. Module: `digest.py` - AI-Powered Digest

### 5.1 Text API

**Test Cases:**
- TC-DIG-001: Call Text API with prompt
- TC-DIG-002: Use configured model (gpt-4o)
- TC-DIG-003: Use configured temperature (0.7)
- TC-DIG-004: Use configured max_tokens
- TC-DIG-005: Parse JSON response
- TC-DIG-006: Extract token usage from response
- TC-DIG-007: Log token usage via TokenUsageTracker
- TC-DIG-008: Handle timeout (30 seconds)
- TC-DIG-009: Handle API error
- TC-DIG-010: Handle invalid JSON response

### 5.2 Category Summaries

**Test Cases:**
- TC-DIG-020: Group activities by category
- TC-DIG-021: Calculate duration per category
- TC-DIG-022: Generate AI summary for each category
- TC-DIG-023: Limit to first 10 activities per category
- TC-DIG-024: Truncate long summaries (200 chars)
- TC-DIG-025: Include count, duration, icon, color
- TC-DIG-026: Use max_tokens_category from config
- TC-DIG-027: Track total tokens used

### 5.3 Overall Summary

**Test Cases:**
- TC-DIG-030: Generate overall summary of the day
- TC-DIG-031: Include total activities, focus percentage
- TC-DIG-032: Include top 3 categories
- TC-DIG-033: Include sample activities (first 5)
- TC-DIG-034: Generate 3-4 sentence summary
- TC-DIG-035: Use max_tokens_overall from config
- TC-DIG-036: Return tokens used

### 5.4 Digest Generation

**Test Cases:**
- TC-DIG-040: Generate complete daily digest
- TC-DIG-041: Include overall_summary, category_summaries, stats
- TC-DIG-042: Cache to digests/digest_YYYY-MM-DD.json
- TC-DIG-043: Handle no data for date
- TC-DIG-044: Handle no annotations
- TC-DIG-045: Log total token usage

### 5.5 Digest Caching

**Test Cases:**
- TC-DIG-050: Load cached digest if available
- TC-DIG-051: Handle missing cache file
- TC-DIG-052: Handle corrupted cache file
- TC-DIG-053: Force regenerate if requested

---

## 6. Module: `token_usage.py` - Token Tracking

### 6.1 Token Logging

**Test Cases:**
- TC-TOK-001: Log token usage to daily file
- TC-TOK-002: Create daily file if not exists
- TC-TOK-003: Append to existing daily file
- TC-TOK-004: Include timestamp, api_type, tokens, prompt_tokens, completion_tokens
- TC-TOK-005: Include optional context
- TC-TOK-006: Update total_tokens sum
- TC-TOK-007: Skip logging when tokens = 0
- TC-TOK-008: Use file locking to prevent race conditions
- TC-TOK-009: Retry on lock failure (max 5 attempts)
- TC-TOK-010: Atomic write using temp file

### 6.2 Usage Retrieval

**Test Cases:**
- TC-TOK-020: Get daily usage for date
- TC-TOK-021: Aggregate by api_type
- TC-TOK-022: Return total_tokens, by_type, calls
- TC-TOK-023: Handle missing file (return empty)
- TC-TOK-024: Handle corrupted JSON

### 6.3 Usage Summary

**Test Cases:**
- TC-TOK-030: Get summary for last N days
- TC-TOK-031: Include total across all days
- TC-TOK-032: Sort daily entries by date
- TC-TOK-033: Skip days with no usage

---

## 7. Module: `web_server.py` - Web Dashboard

### 7.1 Configuration

**Test Cases:**
- TC-WEB-001: Initialize configuration on startup
- TC-WEB-002: Convert relative paths to absolute
- TC-WEB-003: Set Flask secret key from config
- TC-WEB-004: Handle config load failure

### 7.2 API Endpoints - Data

**Test Cases:**
- TC-WEB-010: GET /api/health returns status
- TC-WEB-011: GET /api/config returns user config
- TC-WEB-012: PUT /api/config updates user_config.yaml
- TC-WEB-013: GET /api/stats returns overall statistics
- TC-WEB-014: GET /api/timeline returns activities
- TC-WEB-015: GET /api/timeline/<date> returns date-specific activities
- TC-WEB-016: GET /api/digest returns today's digest
- TC-WEB-017: GET /api/digest/<date> returns date-specific digest
- TC-WEB-018: GET /api/digest?force=true regenerates digest
- TC-WEB-019: GET /api/search with query parameter
- TC-WEB-020: GET /api/search with category filter
- TC-WEB-021: GET /api/search with days parameter
- TC-WEB-022: GET /api/analytics with days parameter
- TC-WEB-023: GET /api/frames lists frames for date
- TC-WEB-024: GET /api/frames/<date>/<timestamp>/image returns PNG
- TC-WEB-025: GET /api/dates returns available dates

### 7.3 API Endpoints - Export

**Test Cases:**
- TC-WEB-030: GET /api/export/csv returns CSV file
- TC-WEB-031: GET /api/export/json returns JSON data
- TC-WEB-032: Export includes all activity details
- TC-WEB-033: Export handles missing data

### 7.4 WebSocket Events

**Test Cases:**
- TC-WEB-040: Handle client connect
- TC-WEB-041: Handle client disconnect
- TC-WEB-042: Handle subscribe_live
- TC-WEB-043: Broadcast new_frame event
- TC-WEB-044: Broadcast new_activity event

### 7.5 Error Handling

**Test Cases:**
- TC-WEB-050: Return 404 for missing data
- TC-WEB-051: Return 500 for server errors
- TC-WEB-052: Handle invalid date formats
- TC-WEB-053: Handle invalid query parameters

---

## 8. Module: `menubar_app.py` - Menu Bar App

### 8.1 Initialization

**Test Cases:**
- TC-MENU-001: Load configuration on startup
- TC-MENU-002: Show configuration error alert
- TC-MENU-003: Setup menu items
- TC-MENU-004: Setup global hotkey (Cmd+Shift+6)
- TC-MENU-005: Initialize state variables

### 8.2 Capture Control

**Test Cases:**
- TC-MENU-010: Start capture from menu
- TC-MENU-011: Stop capture from menu
- TC-MENU-012: Pause capture
- TC-MENU-013: Resume capture
- TC-MENU-014: Update menu state when running
- TC-MENU-015: Update menu state when paused
- TC-MENU-016: Update menu state when stopped

### 8.3 Manual Actions

**Test Cases:**
- TC-MENU-020: Capture now via menu
- TC-MENU-021: Capture now via hotkey (Cmd+Shift+6)
- TC-MENU-022: Region capture via hotkey
- TC-MENU-023: Run annotation manually
- TC-MENU-024: Generate timeline manually
- TC-MENU-025: Generate digest manually

### 8.4 Capture Loop

**Test Cases:**
- TC-MENU-030: Run capture loop in thread
- TC-MENU-031: Use shared capture_iteration function
- TC-MENU-032: Track statistics (count, skipped, etc.)
- TC-MENU-033: Handle max consecutive errors
- TC-MENU-034: Periodic cleanup
- TC-MENU-035: Respect pause state
- TC-MENU-036: Stop on stop_event

### 8.5 Annotation Loop

**Test Cases:**
- TC-MENU-040: Run annotation loop in thread
- TC-MENU-041: Calculate annotation interval from batch_size
- TC-MENU-042: Run annotation when batch_size reached
- TC-MENU-043: Run annotation when interval elapsed
- TC-MENU-044: Generate timeline every 5 minutes
- TC-MENU-045: Generate digest every hour
- TC-MENU-046: Respect pause state
- TC-MENU-047: Stop on stop_event

### 8.6 UI Actions

**Test Cases:**
- TC-MENU-050: Open dashboard in browser
- TC-MENU-051: Open timeline in browser
- TC-MENU-052: Open data folder in Finder
- TC-MENU-053: Show statistics alert
- TC-MENU-054: Quit app

---

## 9. End-to-End Integration Tests

### 9.1 Complete Workflow

**Test Cases:**
- TC-E2E-001: Full capture → annotation → timeline → digest flow
- TC-E2E-002: Multiple captures in same day
- TC-E2E-003: Batch annotation (4 frames together)
- TC-E2E-004: Cross-midnight captures
- TC-E2E-005: Camera active during capture
- TC-E2E-006: Screen locked during capture
- TC-E2E-007: Manual capture while automatic running
- TC-E2E-008: Pause and resume capture
- TC-E2E-009: Stop and restart capture

### 9.2 Data Consistency

**Test Cases:**
- TC-E2E-020: Frames and JSON files match 1:1
- TC-E2E-021: Synthetic annotations have no PNG
- TC-E2E-022: Batch annotations have same summary
- TC-E2E-023: Timeline deduplicates batches correctly
- TC-E2E-024: Digest uses correct activities
- TC-E2E-025: Token usage logged for all API calls

### 9.3 Configuration Changes

**Test Cases:**
- TC-E2E-030: Change capture_interval_seconds via UI
- TC-E2E-031: Change batch_size via UI
- TC-E2E-032: Change digest interval via UI
- TC-E2E-033: Enable/disable digest via UI
- TC-E2E-034: Config reload without restart

### 9.4 Data Cleanup

**Test Cases:**
- TC-E2E-040: Old frames deleted after retention_days
- TC-E2E-041: Old digests deleted after retention_days
- TC-E2E-042: Old token usage deleted after retention_days
- TC-E2E-043: Old timelines deleted after retention_days
- TC-E2E-044: Recent data preserved

### 9.5 Error Recovery

**Test Cases:**
- TC-E2E-050: Recover from API failures
- TC-E2E-051: Recover from disk full
- TC-E2E-052: Recover from network issues
- TC-E2E-053: Continue after capture errors
- TC-E2E-054: Continue after annotation errors

---

## 10. Performance Tests

### 10.1 Load Tests

**Test Cases:**
- TC-PERF-001: Handle 1000 frames in single day
- TC-PERF-002: Handle 100 days of data
- TC-PERF-003: Timeline generation with 500 activities
- TC-PERF-004: Search across 1000 activities
- TC-PERF-005: Dashboard load time < 2 seconds

### 10.2 Memory Tests

**Test Cases:**
- TC-PERF-010: Memory usage < 150MB during capture
- TC-PERF-011: No memory leaks over 24 hours
- TC-PERF-012: Handle large images (4K screenshots)

### 10.3 Disk Tests

**Test Cases:**
- TC-PERF-020: Disk usage ~1-2MB per hour
- TC-PERF-021: Cleanup reduces disk usage
- TC-PERF-022: Handle limited disk space gracefully

---

## 11. Security Tests

### 11.1 Path Validation

**Test Cases:**
- TC-SEC-001: Reject path traversal (../)
- TC-SEC-002: Reject absolute paths outside project
- TC-SEC-003: Sanitize user input in API calls
- TC-SEC-004: Validate API URLs (https/http only)

### 11.2 Privacy Tests

**Test Cases:**
- TC-SEC-010: No screenshots during camera active
- TC-SEC-011: No screenshots when screen locked
- TC-SEC-012: Synthetic annotations track time only
- TC-SEC-013: Data stored locally only
- TC-SEC-014: API calls use HTTPS

---

## 12. Platform-Specific Tests

### 12.1 macOS Tests

**Test Cases:**
- TC-MAC-001: Menu bar icon displays
- TC-MAC-002: Global hotkey works (Cmd+Shift+6)
- TC-MAC-003: Notifications show correctly
- TC-MAC-004: Screen lock detection works
- TC-MAC-005: Camera detection works
- TC-MAC-006: Region capture via screencapture works

### 12.2 Linux Tests (Terminal Mode)

**Test Cases:**
- TC-LIN-001: Capture works without menu bar
- TC-LIN-002: Screen lock detection (xscreensaver)
- TC-LIN-003: Camera detection (v4l2)

---

## 13. Test Automation Strategy

### 13.1 Unit Tests (pytest)
- Location: `tests/test_*.py`
- Coverage Target: 80%+
- Run: `pytest tests/ -v --cov=src`

### 13.2 Integration Tests
- Location: `tests/integration/`
- Mock external APIs (vision and text backends via llm_backends)
- Test data flows between modules

### 13.3 End-to-End Tests
- Location: `tests/e2e/`
- Use test configuration
- Temporary data directories
- Clean up after tests

### 13.4 Manual Tests
- UI/UX testing
- Visual inspection of timelines
- Digest quality review
- Performance testing

---

## 14. Test Fixtures and Mocks

### 14.1 Configuration Fixtures
```python
@pytest.fixture
def test_config():
    return {
        'root_dir': '/tmp/test_chronometry',
        'capture': {...},
        'annotation': {...},
        'timeline': {...},
        'digest': {...}
    }
```

### 14.2 Mock External APIs
```python
@patch('annotate.subprocess.run')
def test_api_call(mock_run):
    mock_run.return_value = Mock(
        returncode=0,
        stdout='{"summary": "test"}'
    )
```

### 14.3 Test Data
- Sample screenshots (small PNGs)
- Sample annotations (JSON)
- Sample timelines (HTML)
- Sample digests (JSON)

---

## 15. Test Coverage Report

### Current Coverage (✅ = Implemented, ⏳ = Partial, ❌ = Missing)

| Module | Unit Tests | Integration Tests | E2E Tests |
|--------|-----------|------------------|-----------|
| common.py | ✅ 85% | ✅ | ✅ |
| capture.py | ⏳ 40% | ⏳ | ⏳ |
| annotate.py | ⏳ 30% | ❌ | ❌ |
| timeline.py | ❌ 0% | ❌ | ❌ |
| digest.py | ❌ 0% | ❌ | ❌ |
| token_usage.py | ❌ 0% | ❌ | ❌ |
| web_server.py | ❌ 0% | ❌ | ❌ |
| menubar_app.py | ❌ 0% | ❌ | ❌ |

### Priority for Implementation

1. **High Priority** (Critical Path):
   - TC-CAP-* (capture.py) - Core functionality
   - TC-ANN-* (annotate.py) - Core functionality
   - TC-TIM-* (timeline.py) - Core functionality
   - TC-E2E-001 to TC-E2E-009 - Main workflows

2. **Medium Priority** (Important Features):
   - TC-DIG-* (digest.py) - AI features
   - TC-WEB-* (web_server.py) - API endpoints
   - TC-TOK-* (token_usage.py) - Tracking

3. **Low Priority** (Nice to Have):
   - TC-MENU-* (menubar_app.py) - UI tests
   - TC-PERF-* (performance.py) - Optimization
   - TC-SEC-* (security.py) - Hardening

---

## 16. Test Execution Plan

### Daily
```bash
pytest tests/test_common.py -v
pytest tests/test_capture.py -v
pytest tests/test_annotate.py -v
```

### Weekly
```bash
pytest tests/ -v --cov=src --cov-report=html
open htmlcov/index.html
```

### Pre-Release
```bash
pytest tests/ -v --cov=src --cov-report=html
pytest tests/integration/ -v
pytest tests/e2e/ -v
```

---

## 17. Success Criteria

### Minimum Acceptance
- ✅ All critical path tests passing
- ✅ 80%+ code coverage
- ✅ No P0/P1 bugs
- ✅ End-to-end workflow works

### Ideal
- ✅ All tests passing
- ✅ 90%+ code coverage
- ✅ Performance benchmarks met
- ✅ Security tests passing
- ✅ Cross-platform tested

---

## 18. Known Issues & Limitations

### Current Limitations
1. Camera detection may have false positives on some Chrome configurations
2. Screen lock detection may fail on some Linux distributions
3. Region capture only works on macOS
4. Menu bar app only works on macOS

### Future Improvements
1. Add Windows support
2. Add more robust camera detection
3. Add unit tests for web_server.py
4. Add integration tests for digest.py
5. Add performance benchmarks

---

## Appendix: Test Data Generation

### Generate Test Screenshots
```bash
python tests/utils/generate_test_images.py --count 100
```

### Generate Test Annotations
```bash
python tests/utils/generate_test_annotations.py --frames 100
```

### Generate Test Timeline
```bash
python tests/utils/generate_test_timeline.py --date 2025-11-01
```

---

**Document Version:** 1.0  
**Last Updated:** November 1, 2025  
**Author:** Quality Assurance Team  
**Status:** ✅ Ready for Implementation

