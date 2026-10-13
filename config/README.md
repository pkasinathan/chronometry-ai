# Chronometry Configuration Guide

> **Note:** The files in this `config/` directory are **examples** for reference.
> The authoritative defaults shipped with the package live in
> `src/chronometry/defaults/`. When you run `chrono init`, those defaults
> are copied to `~/.chronometry/config/`.

## Overview

Chronometry uses a **two-file configuration system** stored in `~/.chronometry/config/`:

- **`system_config.yaml`** — Contains ALL default settings (the single source of truth)
- **`user_config.yaml`** — Your overrides only (starts empty; any key you add here wins)

On first run (`chrono init`), both files are copied from the package defaults.

This design ensures:
- One place to look for every default value
- User overrides are explicit and easy to diff
- `chrono init --force` cleanly resets without losing track of what you changed

---

## How Configuration Works

### 1. Loading Priority

The system loads both config files and merges them:

1. Loads `system_config.yaml` (all defaults)
2. Loads `user_config.yaml` (your overrides — may be empty)
3. Deep-merges them (user values take precedence)

If either file is missing, `chrono init` runs automatically to create defaults.

### 2. Merging Behavior

System config provides every default. User config overrides only what you set:

```yaml
# system_config.yaml (has all defaults)
capture:
  capture_interval_seconds: 900
  monitor_index: 1
  region: null

# user_config.yaml (only your overrides)
capture:
  capture_interval_seconds: 600  # Override: capture every 10 min

# Result (merged):
capture:
  capture_interval_seconds: 600  # From user
  monitor_index: 1               # From system
  region: null                   # From system
```

### 3. Validation

All configs are validated on load:
- Type checking (int, float, string, bool, list)
- Range validation (positive numbers, non-negative, etc.)
- Required field checking
- Helpful error messages if invalid

---

## Configuration Sections

All of these live in `system_config.yaml` as defaults. Override any value by adding it to `user_config.yaml`.

### Capture
```yaml
capture:
  capture_interval_seconds: 900  # How often to capture (15 min default)
  monitor_index: 1               # Which monitor (0=all, 1=primary, 2=secondary)
  retention_days: 1095           # Days to keep screenshots (3 years)
  region: null                   # Custom region [x,y,w,h] or null
  startup_delay_seconds: 5       # Delay before first capture
  screen_check_timeout: 2        # Timeout for lock detection
```

### Annotation
```yaml
annotation:
  annotation_mode: manual        # "manual" or "auto"
  screenshot_analysis_batch_size: 1
  inference_image_max_edge: 1280
  inference_image_quality: 80
  timeout_sec: 30
  screenshot_analysis_prompt: |  # VLM prompt with {metadata_block} and {recent_context} placeholders
    ...
  rewrite_screenshot_analysis_format_summary: true
  rewrite_screenshot_analysis_prompt: |
    ...
  local_model:
    provider: "ollama"           # "ollama" or "openai_compatible"
    base_url: "http://localhost:11434"
    model_name: "qwen3-vl:8b"    # Primary vision model
    fallback_model_name: "qwen2.5vl:7b"  # Fallback if primary fails
    timeout_sec: 300
    max_retries: 3
```

### Digest
```yaml
digest:
  enabled: true
  model: "qwen3.5:4b"            # Legacy/display key (text model)
  temperature: 0.7
  interval_seconds: 3600
  max_tokens_default: 500
  max_tokens_category: 200
  max_tokens_overall: 300
  system_prompt: "..."
  digest_category_prompt: |      # Template with {category}, {activity_descriptions}
    ...
  digest_overall_prompt: |       # Template with {total_activities}, {focus_percentage}, {top_categories}, {sample_activities}
    ...
  local_model:
    provider: "ollama"
    base_url: "http://localhost:11434"
    model_name: "qwen3.5:4b"     # Authoritative key used for digest + post-format text calls
    timeout_sec: 300
```

### Server, Timeline, Notifications, etc.
```yaml
server:
  host: "127.0.0.1"
  port: 8051

timeline:
  bucket_minutes: 30
  gap_minutes: 5
  exclude_keywords: []

notifications:
  enabled: true
  notify_before_capture: true
  pre_capture_warning_seconds: 5
  pre_capture_sound: false
```

---

## Editing Configuration

### Via Web UI (Recommended)

1. Open dashboard: http://localhost:8051/
2. Click **Settings** tab
3. Modify values
4. Click **Save Changes** (overrides are written to `user_config.yaml`, backup created automatically)
5. Restart services for changes to take effect

### Via File Editor

1. Add your overrides to `~/.chronometry/config/user_config.yaml`
2. Save the file
3. Restart services: `chrono service restart`

### Reset to Defaults

- **From the UI**: Click **Reset to Defaults** in the Settings tab (creates backup first)
- **From the CLI**: `chrono init --force` (creates backup first)

Both methods back up existing configs to `~/.chronometry/config/backup/` before overwriting.

---

## Troubleshooting

### "No configuration files found" Error

**Fix**: Run `chrono init` to create default configuration files.

### Settings Don't Save in UI

**Fix**:
1. Check browser console for validation errors
2. Ensure `~/.chronometry/config/user_config.yaml` is writable:
   ```bash
   chmod 644 ~/.chronometry/config/user_config.yaml
   ```

### Services Won't Start After Config Change

**Fix**:
1. Check logs: `chrono logs`
2. Validate YAML syntax:
   ```bash
   python -c "import yaml; yaml.safe_load(open('$HOME/.chronometry/config/user_config.yaml'))"
   ```
3. Reset to defaults: `chrono init --force`

### Changes Don't Take Effect

**Fix**:
```bash
chrono service restart
```

---

## Quick Reference

### Capture Interval Examples

| Seconds | Minutes | Use Case |
|---------|---------|----------|
| 300 | 5 min | High frequency (detailed tracking) |
| 600 | 10 min | Medium frequency (balanced) |
| 900 | 15 min | Default (good balance) |
| 1800 | 30 min | Low frequency (light tracking) |

### Retention Days Examples

| Days | Duration | Use Case |
|------|----------|----------|
| 30 | 1 month | Monthly analysis |
| 365 | 1 year | Annual tracking |
| 1095 | 3 years | Default (long-term analysis) |

---

## Support

- **Documentation**: README.md, QUICK_START.md
- **Logs**: `~/.chronometry/logs/` directory
- **Validation**: `chrono validate`
- **Full merged config**: `chrono config`
- **Runtime health snapshot**: `http://localhost:8051/api/system-health`
