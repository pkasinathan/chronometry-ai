"""Chronometry CLI — unified command-line interface.

Usage:
    chrono <command>                     (after pip install chronometry-ai)
    python -m chronometry.cli <command>  (development)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timedelta
from importlib.resources import files as pkg_files
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from chronometry import CHRONOMETRY_HOME, __version__
from chronometry.common import bootstrap, load_config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
LOGS_DIR = CHRONOMETRY_HOME / "logs"
CONFIG_DIR = CHRONOMETRY_HOME / "config"

SERVICES = {
    "webserver": {
        "label": "user.chronometry.webserver",
        "plist": "user.chronometry.webserver.plist",
        "description": "Web dashboard (port 8051)",
        "module": "chronometry.web_server",
        "log": "webserver",
        "port": 8051,
    },
    "menubar": {
        "label": "user.chronometry.menubar",
        "plist": "user.chronometry.menubar.plist",
        "description": "macOS menu bar app",
        "module": "chronometry.menubar_app",
        "log": "menubar",
        "port": None,
    },
}

console = Console()

# ---------------------------------------------------------------------------
# Typer apps
# ---------------------------------------------------------------------------

app = typer.Typer(
    no_args_is_help=True,
    help="Chronometry — unified CLI for activity tracking services.",
)

service_app = typer.Typer(no_args_is_help=True, help="Manage launchd services.")
app.add_typer(service_app, name="service")

# ---------------------------------------------------------------------------
# Helpers — launchd
# ---------------------------------------------------------------------------


def _is_loaded(label: str) -> bool:
    r = subprocess.run(
        ["launchctl", "list"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return label in r.stdout


def _get_pid(label: str) -> int | None:
    r = subprocess.run(
        ["launchctl", "list", label],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        if '"PID"' in line or "PID" in line:
            m = re.search(r"(\d+)", line.split("=")[-1] if "=" in line else line)
            if m:
                val = int(m.group(1))
                return val if val > 0 else None
    return None


def _port_listening(port: int) -> bool:
    r = subprocess.run(
        ["lsof", "-i", f":{port}", "-n", "-P"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return "LISTEN" in r.stdout


def _plist_installed(name: str) -> bool:
    return (LAUNCH_AGENTS_DIR / SERVICES[name]["plist"]).exists()


def _ensure_dirs():
    bootstrap()


APP_BUNDLE_DIR = CHRONOMETRY_HOME / "Chronometry.app"

_APP_INFO_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Chronometry</string>
    <key>CFBundleDisplayName</key>
    <string>Chronometry</string>
    <key>CFBundleIdentifier</key>
    <string>user.chronometry.menubar</string>
    <key>CFBundleVersion</key>
    <string>{version}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>Chronometry</string>
    <key>LSBackgroundOnly</key>
    <true/>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
"""


def _build_app_bundle() -> Path:
    """Create a minimal Chronometry.app bundle so macOS Accessibility
    identifies the process as 'Chronometry' instead of 'Python'.

    Returns the path to the executable inside the bundle.
    """
    contents_dir = APP_BUNDLE_DIR / "Contents"
    macos_dir = contents_dir / "MacOS"
    macos_dir.mkdir(parents=True, exist_ok=True)

    info_plist = contents_dir / "Info.plist"
    info_plist.write_text(_APP_INFO_PLIST.format(version=__version__))

    executable = macos_dir / "Chronometry"
    src_python = Path(sys.executable).resolve()

    if executable.exists() or executable.is_symlink():
        executable.unlink()

    try:
        os.link(src_python, executable)
    except OSError:
        shutil.copy2(src_python, executable)

    executable.chmod(0o755)

    # The Python binary loads libpython via @executable_path/../lib/.
    # Symlink the original lib directory so the dylib is found.
    src_lib = src_python.parent.parent / "lib"
    bundle_lib = contents_dir / "lib"
    if bundle_lib.is_symlink() or bundle_lib.exists():
        bundle_lib.unlink() if bundle_lib.is_symlink() else shutil.rmtree(bundle_lib)
    if src_lib.is_dir():
        bundle_lib.symlink_to(src_lib)

    return executable


def _install_plist(name: str):
    info = SERVICES[name]
    defaults = pkg_files("chronometry") / "defaults"
    template_path = defaults / info["plist"]

    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    content = template_path.read_text()

    if name == "menubar":
        app_python = _build_app_bundle()
        content = content.replace("{{PYTHON_PATH}}", str(app_python))
        # The bundled binary loses venv context; build PYTHONPATH from
        # venv site-packages + any .pth entries (editable installs).
        import site as _site

        site_pkgs = Path(_site.getsitepackages()[0])
        paths = [str(site_pkgs)]
        for pth in site_pkgs.glob("*.pth"):
            for line in pth.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and Path(line).is_dir():
                    paths.append(line)
        pythonpath_val = ":".join(paths)
        pythonpath_entry = (
            f"        <key>PYTHONPATH</key>\n"
            f"        <string>{pythonpath_val}</string>\n"
            f"    "
        )
        content = content.replace(
            "    </dict>\n\n    <key>ProcessType</key>",
            pythonpath_entry + "</dict>\n\n    <key>ProcessType</key>",
        )
    else:
        content = content.replace("{{PYTHON_PATH}}", sys.executable)

    content = content.replace("{{CHRONOMETRY_HOME}}", str(CHRONOMETRY_HOME))
    dest = LAUNCH_AGENTS_DIR / info["plist"]
    dest.write_text(content)


# ---------------------------------------------------------------------------
# Helpers — Ollama
# ---------------------------------------------------------------------------


def _check_ollama() -> str | None:
    """Return status string for Ollama, or None if not relevant."""
    cfg_path = CONFIG_DIR / "user_config.yaml"
    if not cfg_path.exists():
        return None
    try:
        import yaml

        cfg = yaml.safe_load(cfg_path.read_text()) or {}
    except Exception:
        return None
    is_local = cfg.get("annotation", {}).get("backend") == "local" or cfg.get("digest", {}).get("backend") == "local"
    if not is_local:
        return None

    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        return "[red]not installed[/red]"
    try:
        import requests

        r = requests.get("http://localhost:11434", timeout=2)
        if r.status_code == 200:
            return "[green]running[/green]"
    except Exception:
        pass
    return "[red]not running[/red] (start with: ollama serve)"


# ---------------------------------------------------------------------------
# Service sub-commands
# ---------------------------------------------------------------------------


@service_app.command("list")
def service_list():
    """List available services and their status."""
    table = Table(title="Chronometry Services", header_style="bold cyan")
    table.add_column("Service", style="bold")
    table.add_column("Description")
    table.add_column("Status")
    table.add_column("PID")

    for name, info in SERVICES.items():
        if _is_loaded(info["label"]):
            pid = _get_pid(info["label"])
            status = "[green]running[/green]"
            pid_str = str(pid) if pid else "–"
            if info["port"] and not _port_listening(info["port"]):
                status = "[yellow]loaded (port not ready)[/yellow]"
        else:
            status = "[red]stopped[/red]"
            pid_str = "–"
        table.add_row(name, info["description"], status, pid_str)

    console.print(table)

    ollama = _check_ollama()
    if ollama:
        console.print(f"\n  Ollama: {ollama}")


@service_app.command()
def install(
    service: str | None = typer.Argument(None, help="Service name (omit for all)"),
):
    """Install services into macOS launchd (start at login)."""
    names = [service] if service else list(SERVICES)
    _ensure_dirs()

    for name in names:
        if name not in SERVICES:
            console.print(f"[bold red]Unknown service:[/bold red] {name}")
            raise typer.Exit(1)
        _install_plist(name)
        info = SERVICES[name]
        plist_path = LAUNCH_AGENTS_DIR / info["plist"]
        if _is_loaded(info["label"]):
            console.print(f"[yellow]{name}: already loaded[/yellow]")
        else:
            subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True)
            time.sleep(1)
            if _is_loaded(info["label"]):
                console.print(f"[green]✓ {name}: installed and started[/green]")
            else:
                console.print(f"[red]✗ {name}: failed to start (check logs)[/red]")

    console.print("\n  Dashboard: [cyan]http://localhost:8051[/cyan]")
    console.print(f"  Logs:      {LOGS_DIR}")


@service_app.command()
def start(
    service: str | None = typer.Argument(None, help="Service name (omit for all)"),
):
    """Start services."""
    names = [service] if service else list(SERVICES)
    for name in names:
        if name not in SERVICES:
            console.print(f"[bold red]Unknown service:[/bold red] {name}")
            raise typer.Exit(1)
        info = SERVICES[name]
        plist_path = LAUNCH_AGENTS_DIR / info["plist"]
        if not plist_path.exists():
            console.print(f"[yellow]{name}: not installed, installing…[/yellow]")
            _ensure_dirs()
        _install_plist(name)
        if _is_loaded(info["label"]):
            console.print(f"[yellow]{name}: already running[/yellow]")
            continue
        subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True)
        time.sleep(1)
        if _is_loaded(info["label"]):
            console.print(f"[green]✓ {name}: started[/green]")
        else:
            console.print(f"[red]✗ {name}: failed to start[/red]")


@service_app.command()
def stop(
    service: str | None = typer.Argument(None, help="Service name (omit for all)"),
):
    """Stop services."""
    names = [service] if service else list(SERVICES)
    for name in names:
        if name not in SERVICES:
            console.print(f"[bold red]Unknown service:[/bold red] {name}")
            raise typer.Exit(1)
        info = SERVICES[name]
        plist_path = LAUNCH_AGENTS_DIR / info["plist"]
        if not _is_loaded(info["label"]):
            console.print(f"[yellow]{name}: not running[/yellow]")
            continue
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
        console.print(f"[green]✓ {name}: stopped[/green]")


@service_app.command()
def restart(
    service: str | None = typer.Argument(None, help="Service name (omit for all)"),
):
    """Restart services."""
    names = [service] if service else list(SERVICES)
    for name in names:
        info = SERVICES[name]
        plist_path = LAUNCH_AGENTS_DIR / info["plist"]
        if _is_loaded(info["label"]):
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            console.print(f"  {name}: stopped")
        time.sleep(1)
        _ensure_dirs()
        _install_plist(name)
        subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True)
        time.sleep(1)
        if _is_loaded(info["label"]):
            console.print(f"[green]✓ {name}: restarted[/green]")
        else:
            console.print(f"[red]✗ {name}: failed to start[/red]")


@service_app.command()
def uninstall(
    service: str | None = typer.Argument(None, help="Service name (omit for all)"),
):
    """Uninstall services from launchd."""
    names = [service] if service else list(SERVICES)
    for name in names:
        if name not in SERVICES:
            console.print(f"[bold red]Unknown service:[/bold red] {name}")
            raise typer.Exit(1)
        info = SERVICES[name]
        plist_path = LAUNCH_AGENTS_DIR / info["plist"]
        if _is_loaded(info["label"]):
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
        if plist_path.exists():
            plist_path.unlink()
            console.print(f"[green]✓ {name}: uninstalled[/green]")
        else:
            console.print(f"[yellow]{name}: not installed[/yellow]")
        if name == "menubar" and APP_BUNDLE_DIR.exists():
            shutil.rmtree(APP_BUNDLE_DIR)
            console.print("  Chronometry.app bundle removed")
    console.print(f"\n  Log files preserved in: {LOGS_DIR}")


# ---------------------------------------------------------------------------
# Top-level commands — status / logs (convenience shortcuts)
# ---------------------------------------------------------------------------


@app.command()
def status():
    """Show service status overview."""
    service_list()


@app.command()
def logs(
    service: str | None = typer.Argument(None, help="Service name (omit for all)"),
    lines: int = typer.Option(50, "-n", "--lines", help="Number of lines"),
    follow: bool = typer.Option(False, "-f", "--follow", help="Follow log output"),
    stdout: bool = typer.Option(False, "--stdout", help="Show stdout logs instead of application logs"),
):
    """View service logs."""
    if service and service not in SERVICES:
        console.print(f"[bold red]Unknown service:[/bold red] {service}")
        raise typer.Exit(1)

    names = [service] if service else list(SERVICES)
    suffix = ".log" if stdout else ".error.log"
    log_files = []
    for name in names:
        log_path = LOGS_DIR / f"{SERVICES[name]['log']}{suffix}"
        if log_path.exists():
            log_files.append(str(log_path))

    if not log_files:
        console.print("[yellow]No log files found. Services may not have run yet.[/yellow]")
        raise typer.Exit(0)

    cmd = ["tail"]
    if follow:
        cmd.append("-f")
    else:
        cmd.extend(["-n", str(lines)])
    cmd.extend(log_files)

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# Top-level commands — init
# ---------------------------------------------------------------------------


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configs with defaults"),
):
    """Initialize ~/.chronometry with default configuration."""
    bootstrap(force=force)
    console.print(f"[green]✓ Initialized {CHRONOMETRY_HOME}[/green]")
    console.print(f"  Config:  {CONFIG_DIR}")
    console.print(f"  Data:    {CHRONOMETRY_HOME / 'data'}")
    console.print(f"  Logs:    {LOGS_DIR}")
    if force:
        console.print("[yellow]  (default configs restored)[/yellow]")


# ---------------------------------------------------------------------------
# Top-level commands — core operations
# ---------------------------------------------------------------------------


@app.command()
def annotate(
    date: str | None = typer.Option(None, "--date", "-d", help="Date (YYYY-MM-DD)"),
):
    """Run annotation on unannotated frames."""
    from chronometry.annotate import annotate_frames

    console.print("[cyan]Running annotation…[/cyan]")
    config = load_config()
    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            console.print(f"[bold red]Invalid date format:[/bold red] {date} (expected YYYY-MM-DD)")
            raise typer.Exit(1)
    try:
        count = annotate_frames(config, date=target_date)
        console.print(f"[green]✓ Annotation complete ({count} frames)[/green]")
    except Exception as e:
        console.print(f"[red]✗ Annotation failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def timeline():
    """Generate timeline visualization."""
    from chronometry.timeline import generate_timeline

    console.print("[cyan]Generating timeline…[/cyan]")
    config = load_config()
    try:
        generate_timeline(config)
        console.print("[green]✓ Timeline generated[/green]")
    except Exception as e:
        console.print(f"[red]✗ Timeline generation failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def digest(
    date: str | None = typer.Option(None, "--date", "-d", help="Date (YYYY-MM-DD)"),
    force: bool = typer.Option(False, "--force", "-f", help="Regenerate even if cached"),
):
    """Generate or show daily digest."""
    from chronometry.digest import generate_daily_digest, get_or_generate_digest

    config = load_config()
    if date:
        try:
            target = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            console.print(f"[bold red]Invalid date format:[/bold red] {date} (expected YYYY-MM-DD)")
            raise typer.Exit(1)
    else:
        target = datetime.now()

    console.print(f"[cyan]Loading digest for {target.strftime('%Y-%m-%d')}…[/cyan]")
    if force:
        result = generate_daily_digest(target, config)
    else:
        result = get_or_generate_digest(target, config)

    if result.get("error"):
        console.print(f"[yellow]{result['error']}[/yellow]")
        return

    summary = result.get("overall_summary", "")
    if summary:
        console.print(Panel(summary, title="Daily Digest", border_style="cyan"))

    categories = result.get("category_summaries", {})
    if categories:
        table = Table(title="Activity Breakdown", header_style="bold cyan")
        table.add_column("Category")
        table.add_column("Count", justify="right")
        table.add_column("Duration", justify="right")
        for cat, data in categories.items():
            icon = data.get("icon", "")
            count = str(data.get("count", 0))
            mins = data.get("duration_minutes", 0)
            dur = f"{mins // 60}h {mins % 60}m" if mins >= 60 else f"{mins}m"
            table.add_row(f"{icon} {cat}", count, dur)
        console.print(table)


@app.command()
def validate():
    """Run system validation checks."""
    from chronometry.validate import run_validation

    run_validation(console)


# ---------------------------------------------------------------------------
# Top-level commands — data operations
# ---------------------------------------------------------------------------


@app.command()
def stats():
    """Show overall statistics."""
    from chronometry.timeline import group_activities, load_annotations

    config = load_config()
    root_dir = config["root_dir"]
    frames_dir = Path(root_dir) / "frames"

    if not frames_dir.exists():
        console.print("[yellow]No data yet.[/yellow]")
        return

    total_frames = 0
    total_activities = 0
    days = 0

    for date_dir in sorted(frames_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        total_frames += len([f for f in date_dir.glob("*.json") if not f.stem.endswith("_meta")])
        annotations = load_annotations(date_dir)
        if annotations:
            activities = group_activities(annotations, config=config)
            total_activities += len(activities)
            days += 1

    table = Table(header_style="bold cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right", style="cyan")
    table.add_row("Days tracked", str(days))
    table.add_row("Frames captured", str(total_frames))
    table.add_row("Activities", str(total_activities))
    console.print(table)


@app.command()
def dates():
    """List dates with captured data."""
    config = load_config()
    frames_dir = Path(config["root_dir"]) / "frames"

    if not frames_dir.exists():
        console.print("[yellow]No data yet.[/yellow]")
        return

    table = Table(header_style="bold cyan")
    table.add_column("Date")
    table.add_column("Frames", justify="right")

    for date_dir in sorted(frames_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        n = len([f for f in date_dir.glob("*.json") if not f.stem.endswith("_meta")])
        pngs = len(list(date_dir.glob("*.png")))
        table.add_row(date_dir.name, f"{n} annotated / {pngs} captured")

    console.print(table)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search term"),
    days: int = typer.Option(7, "--days", "-d", help="Days to search"),
    category: str | None = typer.Option(None, "--category", "-c", help="Filter by category"),
):
    """Search activities across dates."""
    from chronometry.common import format_date, get_daily_dir
    from chronometry.timeline import group_activities, load_annotations

    config = load_config()
    results = []

    for i in range(days):
        dt = datetime.now() - timedelta(days=i)
        daily_dir = get_daily_dir(config["root_dir"], dt)
        if not daily_dir.exists():
            continue
        annotations = load_annotations(daily_dir)
        if not annotations:
            continue
        activities = group_activities(annotations, config=config)
        for act in activities:
            if query.lower() not in act["summary"].lower():
                continue
            if category and act["category"].lower() != category.lower():
                continue
            results.append((format_date(dt), act))

    if not results:
        console.print(f'[yellow]No results for "{query}"[/yellow]')
        return

    console.print(f"Found [bold]{len(results)}[/bold] result(s)\n")
    for date_str, act in results:
        icon = act.get("icon", "")
        cat = act["category"]
        dur = act.get(
            "duration_minutes",
            int((act["end_time"] - act["start_time"]).total_seconds() / 60) if "end_time" in act else 0,
        )
        start = act["start_time"].strftime("%H:%M") if hasattr(act["start_time"], "strftime") else ""
        console.print(f"  {icon} [bold]{cat}[/bold]  {date_str} {start}  ({dur}m)")
        summary_preview = act["summary"][:120].replace("\n", " ")
        console.print(f"    [dim]{summary_preview}[/dim]\n")


# ---------------------------------------------------------------------------
# Top-level commands — config
# ---------------------------------------------------------------------------


@app.command("config")
def config_show(
    validate_cfg: bool = typer.Option(False, "--validate", help="Validate configuration"),
):
    """Show or validate current configuration."""
    try:
        config = load_config()
    except Exception as e:
        console.print(f"[bold red]Config error:[/bold red] {e}")
        raise typer.Exit(1)

    if validate_cfg:
        console.print("[green]✓ Configuration is valid[/green]")
        console.print(f"  Root dir: {config.get('root_dir')}")
        console.print(f"  Annotation backend: {config.get('annotation', {}).get('backend')}")
        console.print(f"  Digest backend: {config.get('digest', {}).get('backend')}")
        return

    user_cfg = CONFIG_DIR / "user_config.yaml"
    if user_cfg.exists():
        console.print(Panel(user_cfg.read_text(), title="user_config.yaml", border_style="cyan"))
    else:
        console.print("[yellow]No user_config.yaml found[/yellow]")


# ---------------------------------------------------------------------------
# Top-level commands — utilities
# ---------------------------------------------------------------------------


@app.command("open")
def open_dashboard():
    """Open the dashboard in a browser."""
    url = "http://localhost:8051"
    console.print(f"Opening [cyan]{url}[/cyan]")
    webbrowser.open(url)


@app.command()
def version():
    """Show version information."""
    console.print(f"[bold cyan]Chronometry[/bold cyan] v{__version__}")
    console.print(f"  Home:     {CHRONOMETRY_HOME}")
    console.print(f"  Config:   {CONFIG_DIR}")
    console.print(f"  Python:   {sys.version.split()[0]}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app()


if __name__ == "__main__":
    main()
