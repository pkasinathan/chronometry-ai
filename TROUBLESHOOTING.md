# Troubleshooting

## `pip: command not found`

### Symptoms

- Running `pip install chronometry-ai` returns `pip: command not found` or `zsh: command not found: pip`

### Cause

Modern macOS (Homebrew Python 3.12+) and many Linux distributions no longer provide a bare `pip` command. Only `pip3` or `python3 -m pip` is available.

### Fix

Use `pip3` instead:

```bash
pip3 install chronometry-ai
```

Or use `python3 -m pip`:

```bash
python3 -m pip install chronometry-ai
```

---

## Python 3.10+ not installed

### Symptoms

- `python3 --version` shows a version below 3.10, or `python3: command not found`
- Installing chronometry fails with a Python version error

### Fix

Install Python 3.10+ via Homebrew (recommended on macOS):

```bash
brew install python@3.10
```

After installation, it's available as `python3.10` and `pip3.10`. Create a virtual environment:

```bash
python3.10 -m venv ~/.chronometry-venv
source ~/.chronometry-venv/bin/activate
pip install chronometry-ai
```

Alternatively, use **pyenv** to manage multiple Python versions:

```bash
brew install pyenv
pyenv install 3.10
pyenv global 3.10
pip install chronometry-ai
```

Or use **uv** (fastest):

```bash
uv python install 3.10
uv pip install chronometry-ai
```

---

## Cmd+Shift+6 hotkey not working

### Symptoms

- Pressing Cmd+Shift+6 does nothing (no region capture UI appears)
- The menu bar app is running (you can see the timer icon) but the hotkey is unresponsive
- The log at `~/.chronometry/logs/menubar.error.log` shows:
  `CGEventTapCreate failed — grant Accessibility permission`

### Cause

The Cmd+Shift+6 hotkey requires **macOS Accessibility permission**. On first install, macOS prompts you to grant it. If you dismissed the prompt or the permission wasn't toggled on, the hotkey won't work.

Common triggers:

- First-time installation (Accessibility prompt was dismissed or denied)
- Upgrading Python or recreating the virtual environment (binary path changes, run `chrono service install` to rebuild the app bundle)
- macOS updates that reset privacy permissions

### Fix

#### Step 1: Grant Accessibility permission

1. Open **System Settings** → **Privacy & Security** → **Accessibility**
2. Find **Chronometry** in the list and toggle it **ON**
3. If Chronometry is not in the list, add it manually:
   - Click **+** (unlock with your password if needed)
   - Navigate to `~/.chronometry/Chronometry.app` and add it (press **Cmd+Shift+G** in the file dialog to type the path)

The hotkey will work immediately after toggling the permission on — no restart needed.

#### Step 2: Verify

Check the log to confirm the hotkey registered successfully:

```bash
tail -5 ~/.chronometry/logs/menubar.error.log
```

You should see:

```
Global hotkey registered: Cmd+Shift+6 for Region Capture (CGEventTap)
```

If you instead see `CGEventTapCreate failed`, the Accessibility permission is still not granted. Repeat Step 1 and make sure the toggle is on.

#### After Python upgrade

If you upgrade Python or recreate the virtual environment, run:

```bash
chrono service install
```

This rebuilds the `Chronometry.app` bundle with the new Python binary. You may need to re-grant Accessibility permission in System Settings (remove the old entry and toggle the new one on).
