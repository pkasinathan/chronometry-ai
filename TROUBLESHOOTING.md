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
- The log at `~/.chronometry/logs/menubar.error.log` may show:
  - `This process is not trusted! Input event monitoring will not be possible until it is added to accessibility clients.`
  - `CGEventTapCreate failed — grant Accessibility permission to the Python binary`

### Cause

The Cmd+Shift+6 hotkey requires **macOS Accessibility permission** for the Python binary that runs the menu bar app. This permission is tied to the **exact binary path** — if Python is upgraded, reinstalled, or the virtual environment is recreated, the path changes and the old permission no longer applies.

Common triggers:

- Upgrading Python (e.g. 3.10 → 3.14) via Homebrew or uv
- Recreating the virtual environment
- macOS updates that reset privacy permissions
- Installing chronometry on a new machine

### Fix

#### Step 1: Find the correct binary

Run this command to see the actual binary the menu bar process is using:

```bash
ps aux | grep "[c]hronometry.menubar"
```

The output shows the full binary path, for example:

```
/Users/you/workspace/chronometry/venv/bin/python3.10 -m chronometry.menubar_app
```

**Important:** On some Python versions (notably 3.14+), macOS silently substitutes a different framework binary at runtime. Check which binary is actually running:

```bash
# Get the PID
PID=$(launchctl list user.chronometry.menubar 2>/dev/null | grep '"PID"' | grep -o '[0-9]*')

# See the actual executable
ps -p "$PID" -o comm=
```

If the output shows something like `.../Python.app/Contents/MacOS/Python` instead of the venv path, that is the binary you need to grant permission to.

#### Step 2: Grant Accessibility permission

1. Open **System Settings** → **Privacy & Security** → **Accessibility**
2. Click **+** (unlock with your password if needed)
3. Navigate to the binary path from Step 1 and add it
   - Tip: press **Cmd+Shift+G** in the file dialog to type a path directly
   - For framework binaries deep in Homebrew, you can reveal them in Finder first:
     ```bash
     open -R "$(ps -p "$PID" -o comm=)"
     ```
4. Make sure the toggle next to the entry is **ON**
5. Remove any old/stale entries that show a **?** icon (those point to binaries that no longer exist)

#### Step 3: Restart the service

```bash
chrono service restart menubar
```

#### Step 4: Verify

Check the log to confirm the hotkey registered successfully:

```bash
tail -5 ~/.chronometry/logs/menubar.error.log
```

You should see:

```
Global hotkey registered: Cmd+Shift+6 for Region Capture (CGEventTap)
```

If you instead see `CGEventTapCreate failed`, the Accessibility permission is still not granted to the correct binary. Repeat Steps 1-3, paying close attention to the exact binary path.

#### Quick one-liner

To find and reveal the exact binary that needs Accessibility permission:

```bash
open -R "$(ps -p "$(launchctl list user.chronometry.menubar 2>/dev/null | awk '/PID/{gsub(/[^0-9]/,""); print}')" -o comm=)"
```

This opens Finder with the binary highlighted — drag it into the Accessibility list.
