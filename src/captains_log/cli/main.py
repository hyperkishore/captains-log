"""CLI commands for Captain's Log using Typer."""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import signal
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from captains_log import __version__
from captains_log.core.config import Config, get_config

# Note: Orchestrator imports are deferred to avoid loading PyObjC before fork()
# This is critical - macOS crashes if PyObjC is loaded before fork()
# We use these lightweight functions to check daemon status without PyObjC


def _get_daemon_pid(config: Config) -> int | None:
    """Get daemon PID without importing PyObjC modules."""
    pid_file = config.data_dir / "daemon.pid"
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
        # Check if process is actually running
        os.kill(pid, 0)
        return pid
    except (ValueError, OSError):
        # Process not running or invalid PID
        pid_file.unlink(missing_ok=True)
        return None


def _is_daemon_running(config: Config) -> bool:
    """Check if daemon is running without importing PyObjC modules."""
    return _get_daemon_pid(config) is not None

# Initialize Typer app
app = typer.Typer(
    name="captains-log",
    help="Personal activity tracking with AI-powered insights.",
    add_completion=False,
)

console = Console()


def setup_logging(log_level: str, log_file: Path | None = None) -> None:
    """Configure logging for the application."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        # Use RotatingFileHandler to prevent unbounded log growth
        # maxBytes=1MB, keep 5 backups (6MB max total)
        rotating_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1_048_576,
            backupCount=5,
        )
        handlers.append(rotating_handler)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )

    # Reduce noise from external libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


def format_uptime(seconds: float) -> str:
    """Format uptime in human-readable format."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.0f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h"
    else:
        days = seconds / 86400
        return f"{days:.1f}d"


@app.command()
def start(
    foreground: bool = typer.Option(
        False,
        "--foreground",
        "-f",
        help="Run in foreground instead of as daemon",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        "-l",
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    ),
) -> None:
    """Start the Captain's Log daemon."""
    config = get_config()

    # Check if already running (using lightweight check without PyObjC)
    if _is_daemon_running(config):
        pid = _get_daemon_pid(config)
        console.print(f"[yellow]Daemon already running (PID: {pid})[/yellow]")
        raise typer.Exit(1)

    # Setup logging
    log_file = config.log_dir / "daemon.log" if not foreground else None
    setup_logging(log_level, log_file)

    if foreground:
        console.print("[green]Starting Captain's Log in foreground...[/green]")
        console.print("Press Ctrl+C to stop\n")

        # Import PyObjC modules only when running in foreground (no fork)
        from captains_log.core.orchestrator import run_daemon

        try:
            asyncio.run(run_daemon())
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped[/yellow]")
    else:
        # Start daemon as background subprocess
        # NOTE: We use subprocess.Popen instead of fork() because PyObjC
        # frameworks (AppKit, Foundation, etc.) crash after fork() on macOS
        console.print("[green]Starting Captain's Log daemon...[/green]")

        import subprocess

        log_path = config.log_dir / "daemon.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Launch new Python process with --foreground flag
        # This avoids fork() issues with PyObjC
        with open(log_path, "a") as log_file:
            subprocess.Popen(
                [sys.executable, "-m", "captains_log", "start", "--foreground", "--log-level", log_level],
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,  # Detach from parent session
            )

        # Wait a moment then check if started
        import time
        time.sleep(1.5)

        if _is_daemon_running(config):
            daemon_pid = _get_daemon_pid(config)
            console.print(f"[green]Daemon started (PID: {daemon_pid})[/green]")
            console.print(f"Logs: {config.log_dir / 'daemon.log'}")
        else:
            console.print("[red]Failed to start daemon - check logs[/red]")
            raise typer.Exit(1)


@app.command()
def stop() -> None:
    """Stop the Captain's Log daemon."""
    config = get_config()

    pid = _get_daemon_pid(config)
    if pid is None:
        console.print("[yellow]Daemon is not running[/yellow]")
        return

    console.print(f"[yellow]Stopping daemon (PID: {pid})...[/yellow]")

    try:
        os.kill(pid, signal.SIGTERM)

        # Wait for graceful shutdown
        import time
        for _ in range(10):  # Wait up to 10 seconds
            time.sleep(1)
            if not _is_daemon_running(config):
                console.print("[green]Daemon stopped[/green]")
                return

        # Force kill if still running
        console.print("[yellow]Daemon not responding, forcing shutdown...[/yellow]")
        os.kill(pid, signal.SIGKILL)
        time.sleep(1)

        if _is_daemon_running(config):
            console.print("[red]Failed to stop daemon[/red]")
            raise typer.Exit(1)
        else:
            console.print("[green]Daemon stopped (forced)[/green]")

    except ProcessLookupError:
        console.print("[green]Daemon stopped[/green]")
        # Clean up stale PID file
        pid_file = config.data_dir / "daemon.pid"
        pid_file.unlink(missing_ok=True)


@app.command()
def status() -> None:
    """Show daemon status and basic information."""
    config = get_config()

    pid = _get_daemon_pid(config)

    if pid is None:
        console.print(Panel(
            "[red bold]STOPPED[/red bold]\n\nDaemon is not running.\nUse 'captains-log start' to begin tracking.",
            title="Captain's Log Status",
            border_style="red",
        ))
        return

    # Get basic process info
    try:
        import psutil
        proc = psutil.Process(pid)
        create_time = datetime.fromtimestamp(proc.create_time())
        uptime = datetime.now() - create_time
        memory_mb = proc.memory_info().rss / (1024 * 1024)
        cpu_percent = proc.cpu_percent(interval=0.5)
    except ImportError:
        uptime = timedelta(seconds=0)
        memory_mb = 0.0
        cpu_percent = 0.0
    except Exception:
        uptime = timedelta(seconds=0)
        memory_mb = 0.0
        cpu_percent = 0.0

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    table.add_row("Status", "[green bold]RUNNING[/green bold]")
    table.add_row("PID", str(pid))
    table.add_row("Uptime", format_uptime(uptime.total_seconds()))
    table.add_row("Memory", f"{memory_mb:.1f} MB")
    table.add_row("CPU", f"{cpu_percent:.1f}%")
    table.add_row("Database", str(config.db_path))
    table.add_row("Logs", str(config.log_dir / "daemon.log"))

    console.print(Panel(table, title="Captain's Log Status", border_style="green"))


@app.command()
def health() -> None:
    """Show detailed health status of all components."""
    config = get_config()

    pid = _get_daemon_pid(config)
    if pid is None:
        console.print("[red]Daemon is not running[/red]")
        console.print("Use 'captains-log start' to begin tracking.")
        raise typer.Exit(1)

    console.print("[yellow]Gathering health information...[/yellow]\n")

    # We need to query the database directly since the daemon is in a separate process
    async def get_health_info():
        from captains_log.core.permissions import PermissionManager
        from captains_log.storage.database import Database

        db = Database(config.db_path)
        await db.connect()

        try:
            # Database stats
            db_size = await db.get_size_mb()
            integrity_ok = await db.check_integrity()

            # Activity counts
            today = datetime.now().strftime("%Y-%m-%d")
            activity_today = await db.fetch_one(
                "SELECT COUNT(*) as count FROM activity_logs WHERE date(timestamp) = ?",
                (today,)
            )
            total_activities = await db.fetch_one(
                "SELECT COUNT(*) as count FROM activity_logs"
            )

            # Screenshot counts
            screenshots_today = await db.fetch_one(
                "SELECT COUNT(*) as count FROM screenshots WHERE date(timestamp) = ?",
                (today,)
            )

            # Last activity
            last_activity = await db.fetch_one(
                "SELECT app_name, timestamp FROM activity_logs ORDER BY timestamp DESC LIMIT 1"
            )

        finally:
            await db.close()

        # Permission status
        pm = PermissionManager()

        return {
            "db_size_mb": db_size,
            "db_integrity": integrity_ok,
            "activity_today": activity_today["count"] if activity_today else 0,
            "total_activities": total_activities["count"] if total_activities else 0,
            "screenshots_today": screenshots_today["count"] if screenshots_today else 0,
            "last_activity": last_activity,
            "has_accessibility": pm.has_accessibility,
            "has_screen_recording": pm.has_screen_recording,
        }

    try:
        info = asyncio.run(get_health_info())
    except Exception as e:
        console.print(f"[red]Error gathering health info: {e}[/red]")
        raise typer.Exit(1)

    # Process info
    try:
        import psutil
        proc = psutil.Process(pid)
        create_time = datetime.fromtimestamp(proc.create_time())
        uptime = datetime.now() - create_time
        memory_mb = proc.memory_info().rss / (1024 * 1024)
        cpu_percent = proc.cpu_percent(interval=0.5)
    except ImportError:
        uptime = timedelta(seconds=0)
        memory_mb = 0.0
        cpu_percent = 0.0
    except Exception:
        uptime = timedelta(seconds=0)
        memory_mb = 0.0
        cpu_percent = 0.0

    # Build health display
    console.print(Panel(
        f"[green bold]RUNNING[/green bold] (PID: {pid}, Uptime: {format_uptime(uptime.total_seconds())})",
        title="Daemon Status",
        border_style="green"
    ))

    # Process metrics
    table = Table(title="Process Metrics", show_header=True, header_style="bold cyan")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_column("Status")

    cpu_status = "[green]OK[/green]" if cpu_percent < 5 else "[yellow]High[/yellow]"
    mem_status = "[green]OK[/green]" if memory_mb < 100 else "[yellow]High[/yellow]"

    table.add_row("CPU Usage", f"{cpu_percent:.1f}%", cpu_status)
    table.add_row("Memory", f"{memory_mb:.1f} MB", mem_status)
    console.print(table)
    console.print()

    # Database health
    table = Table(title="Database", show_header=True, header_style="bold cyan")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_column("Status")

    integrity_status = "[green]OK[/green]" if info["db_integrity"] else "[red]CORRUPTED[/red]"
    table.add_row("Size", f"{info['db_size_mb']:.1f} MB", "[green]OK[/green]")
    table.add_row("Integrity", "Passed" if info["db_integrity"] else "FAILED", integrity_status)
    table.add_row("Activities (Today)", str(info["activity_today"]), "[green]OK[/green]")
    table.add_row("Activities (Total)", str(info["total_activities"]), "[green]OK[/green]")
    table.add_row("Screenshots (Today)", str(info["screenshots_today"]), "[green]OK[/green]")
    console.print(table)
    console.print()

    # Permissions
    table = Table(title="Permissions", show_header=True, header_style="bold cyan")
    table.add_column("Permission")
    table.add_column("Status")

    acc_status = "[green]Granted[/green]" if info["has_accessibility"] else "[red]Denied[/red]"
    scr_status = "[green]Granted[/green]" if info["has_screen_recording"] else "[yellow]Not Checked[/yellow]"

    table.add_row("Accessibility", acc_status)
    table.add_row("Screen Recording", scr_status)
    console.print(table)
    console.print()

    # Last activity
    if info["last_activity"]:
        last = info["last_activity"]
        last_time = datetime.fromisoformat(last["timestamp"])
        age = datetime.utcnow() - last_time
        age_str = format_uptime(age.total_seconds()) + " ago"
        console.print(f"[dim]Last Activity:[/dim] {last['app_name']} ({age_str})")


@app.command()
def logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """View daemon logs."""
    config = get_config()
    log_file = config.log_dir / "daemon.log"

    if not log_file.exists():
        console.print("[yellow]No log file found. Start the daemon first.[/yellow]")
        raise typer.Exit(1)

    if follow:
        # Use tail -f
        import subprocess
        try:
            subprocess.run(["tail", "-f", str(log_file)])
        except KeyboardInterrupt:
            pass
    else:
        # Read last N lines
        with open(log_file) as f:
            all_lines = f.readlines()
            for line in all_lines[-lines:]:
                console.print(line.rstrip())


@app.command()
def config_show() -> None:
    """Show current configuration."""
    config = get_config()

    table = Table(title="Captain's Log Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Setting")
    table.add_column("Value")

    # Paths
    table.add_row("[bold]Paths[/bold]", "")
    table.add_row("  Data Directory", str(config.data_dir))
    table.add_row("  Log Directory", str(config.log_dir))
    table.add_row("  Config Directory", str(config.config_dir))
    table.add_row("  Database", str(config.db_path))

    # Tracking
    table.add_row("[bold]Tracking[/bold]", "")
    table.add_row("  Buffer Flush", f"{config.tracking.buffer_flush_seconds}s")
    table.add_row("  Idle Threshold", f"{config.tracking.idle_threshold_seconds}s")
    table.add_row("  Debounce", f"{config.tracking.debounce_ms}ms")

    # Screenshots
    table.add_row("[bold]Screenshots[/bold]", "")
    table.add_row("  Enabled", str(config.screenshots.enabled))
    table.add_row("  Interval", f"{config.screenshots.interval_minutes} min")
    table.add_row("  Quality", f"{config.screenshots.quality}%")
    table.add_row("  Retention", f"{config.screenshots.retention_days} days")

    # Summarization
    table.add_row("[bold]Summarization[/bold]", "")
    table.add_row("  Enabled", str(config.summarization.enabled))
    table.add_row("  Model", config.summarization.model)
    table.add_row("  Batch API", str(config.summarization.use_batch_api))
    table.add_row("  API Key", "***" if config.claude_api_key else "[yellow]Not Set[/yellow]")

    # Web
    table.add_row("[bold]Web Dashboard[/bold]", "")
    table.add_row("  Enabled", str(config.web.enabled))
    table.add_row("  URL", f"http://{config.web.host}:{config.web.port}")

    console.print(table)


@app.command()
def dashboard(
    host: str = typer.Option(None, "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(None, "--port", "-p", help="Port to bind to"),
) -> None:
    """Launch the web dashboard."""
    config = get_config()

    # Use config values if not overridden
    host = host or config.web.host
    port = port or config.web.port

    console.print("[green]Starting Captain's Log Dashboard...[/green]")
    console.print(f"Open [blue]http://{host}:{port}[/blue] in your browser")
    console.print("Press Ctrl+C to stop\n")

    try:
        import uvicorn
        uvicorn.run(
            "captains_log.web.app:create_app",
            host=host,
            port=port,
            factory=True,
            log_level="info",
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped[/yellow]")


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"Captain's Log v{__version__}")


@app.command()
def install() -> None:
    """Install as launchd service for auto-start on login."""
    from captains_log.cli.install import install as do_install
    from captains_log.cli.install import is_installed, is_loaded

    if is_installed():
        console.print("[yellow]Service already installed[/yellow]")
        if not is_loaded():
            console.print("Run 'captains-log start' to start it")
        return

    console.print("[yellow]Installing launchd service...[/yellow]")

    success, message = do_install()

    if success:
        console.print(f"[green]{message}[/green]")
        console.print("\nCaptain's Log will now start automatically on login.")
        console.print("Use 'captains-log status' to check the service status.")
    else:
        console.print(f"[red]{message}[/red]")
        raise typer.Exit(1)


@app.command()
def uninstall() -> None:
    """Uninstall the launchd service."""
    from captains_log.cli.install import is_installed
    from captains_log.cli.install import uninstall as do_uninstall

    if not is_installed():
        console.print("[yellow]Service not installed[/yellow]")
        return

    console.print("[yellow]Uninstalling launchd service...[/yellow]")

    success, message = do_uninstall()

    if success:
        console.print(f"[green]{message}[/green]")
        console.print("\nCaptain's Log will no longer start automatically.")
    else:
        console.print(f"[red]{message}[/red]")
        raise typer.Exit(1)


@app.command(name="install-status")
def install_status() -> None:
    """Show launchd service installation status."""
    from captains_log.cli.install import get_status

    status = get_status()

    table = Table(title="launchd Service Status", show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    installed = status["installed"]
    loaded = status["loaded"]

    table.add_row("Installed", "[green]Yes[/green]" if installed else "[red]No[/red]")
    table.add_row("Loaded", "[green]Yes[/green]" if loaded else "[red]No[/red]")

    if status.get("plist_path"):
        table.add_row("Plist Path", status["plist_path"])

    if status.get("pid"):
        table.add_row("PID", str(status["pid"]))

    if status.get("exit_status") is not None:
        exit_status = status["exit_status"]
        status_text = "[green]Running[/green]" if exit_status == 0 else f"[red]Exit: {exit_status}[/red]"
        table.add_row("Status", status_text)

    console.print(table)

    if not installed:
        console.print("\n[dim]Run 'captains-log install' to enable auto-start on login.[/dim]")


@app.command()
def summaries(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of summaries to show"),
    hours: int = typer.Option(24, "--hours", help="Show summaries from last N hours"),
) -> None:
    """Show recent AI-generated summaries."""
    config = get_config()

    async def get_summaries():

        from captains_log.storage.database import Database

        db = Database(config.db_path)
        await db.connect()

        try:
            since = datetime.utcnow() - timedelta(hours=hours)

            summaries = await db.fetch_all(
                """
                SELECT
                    period_start, period_end, primary_app, activity_type,
                    focus_score, context, context_switches, tags,
                    tokens_input, tokens_output
                FROM summaries
                WHERE period_start >= ?
                ORDER BY period_start DESC
                LIMIT ?
                """,
                (since.isoformat(), limit),
            )

            # Get queue stats
            queue_stats = await db.fetch_one(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM summary_queue
                """
            )

            return summaries, queue_stats

        finally:
            await db.close()

    try:
        summaries, queue_stats = asyncio.run(get_summaries())
    except Exception as e:
        console.print(f"[red]Error fetching summaries: {e}[/red]")
        raise typer.Exit(1)

    # Queue stats
    console.print(Panel(
        f"Pending: {queue_stats['pending'] or 0} | "
        f"Completed: {queue_stats['completed'] or 0} | "
        f"Failed: {queue_stats['failed'] or 0}",
        title="Summary Queue",
        border_style="blue"
    ))
    console.print()

    if not summaries:
        console.print(f"[yellow]No summaries found in the last {hours} hours[/yellow]")
        console.print("[dim]Summaries are generated automatically every 5 minutes when the daemon is running.[/dim]")
        return

    # Display summaries
    for s in summaries:
        try:
            start = datetime.fromisoformat(s["period_start"].replace("Z", ""))
            end = datetime.fromisoformat(s["period_end"].replace("Z", ""))
        except (ValueError, TypeError):
            continue

        # Focus score color
        focus = s.get("focus_score", 0)
        if focus >= 8:
            focus_color = "green"
        elif focus >= 5:
            focus_color = "yellow"
        else:
            focus_color = "red"

        # Activity type emoji
        activity_emojis = {
            "coding": "💻",
            "writing": "📝",
            "communication": "💬",
            "browsing": "🌐",
            "meetings": "📞",
            "design": "🎨",
            "admin": "📋",
            "entertainment": "🎮",
            "learning": "📚",
            "breaks": "☕",
        }
        activity_type = s.get("activity_type", "unknown")
        emoji = activity_emojis.get(activity_type, "❓")

        # Tags
        tags = s.get("tags", "[]")
        if isinstance(tags, str):
            try:
                tags = eval(tags) if tags else []
            except Exception:
                tags = []

        tag_str = " ".join(f"[dim]#{t}[/dim]" for t in tags[:3]) if tags else ""

        console.print(
            f"[bold]{start.strftime('%H:%M')} - {end.strftime('%H:%M')}[/bold] "
            f"{emoji} {s.get('primary_app', 'Unknown')} "
            f"[{focus_color}]Focus: {focus}/10[/{focus_color}] "
            f"[dim]({s.get('context_switches', 0)} switches)[/dim]"
        )
        if s.get("context"):
            console.print(f"  [dim]{s['context'][:100]}...[/dim]" if len(s.get("context", "")) > 100 else f"  [dim]{s['context']}[/dim]")
        if tag_str:
            console.print(f"  {tag_str}")
        console.print()


@app.command(name="summaries-backfill")
def summaries_backfill(
    hours: int = typer.Option(24, "--hours", help="Backfill summaries for last N hours"),
    limit: int = typer.Option(100, "--limit", help="Maximum summaries to generate"),
) -> None:
    """Generate summaries for periods that are missing."""
    config = get_config()

    # Check for API key
    api_key = config.claude_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]No API key configured.[/red]")
        console.print("Set ANTHROPIC_API_KEY or CAPTAINS_LOG_CLAUDE_API_KEY environment variable.")
        raise typer.Exit(1)

    async def do_backfill():
        from captains_log.ai.batch_processor import BatchProcessor
        from captains_log.storage.database import Database
        from captains_log.summarizers.five_minute import FiveMinuteSummarizer
        from captains_log.summarizers.focus_calculator import FocusCalculator

        db = Database(config.db_path)
        await db.connect()

        try:
            batch_processor = BatchProcessor(
                db=db,
                use_batch_api=config.summarization.use_batch_api,
            )

            summarizer = FiveMinuteSummarizer(
                db=db,
                batch_processor=batch_processor,
                focus_calculator=FocusCalculator(),
                screenshots_dir=config.screenshots_dir,
            )

            since = datetime.utcnow() - timedelta(hours=hours)
            queued = await summarizer.backfill_summaries(since=since, limit=limit)

            return queued

        finally:
            await db.close()

    console.print(f"[yellow]Backfilling summaries for last {hours} hours...[/yellow]")

    try:
        queued = asyncio.run(do_backfill())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if queued > 0:
        console.print(f"[green]Queued {queued} summaries for processing.[/green]")
        if config.summarization.use_batch_api:
            console.print(f"[dim]Summaries will be processed in the next batch (every {config.summarization.batch_interval_hours} hours).[/dim]")
        else:
            console.print("[dim]Summaries will be processed in real-time.[/dim]")
    else:
        console.print("[yellow]No missing summaries found.[/yellow]")


@app.command(name="summaries-process")
def summaries_process(
    limit: int = typer.Option(50, "--limit", help="Maximum summaries to process"),
) -> None:
    """Process pending summaries in the queue (requires API key)."""
    config = get_config()

    # Check for API key
    api_key = config.claude_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]No API key configured.[/red]")
        console.print("Set ANTHROPIC_API_KEY or CAPTAINS_LOG_CLAUDE_API_KEY environment variable.")
        raise typer.Exit(1)

    async def do_process():
        from captains_log.ai.batch_processor import BatchProcessor
        from captains_log.storage.database import Database

        db = Database(config.db_path)
        await db.connect()

        try:
            batch_processor = BatchProcessor(
                db=db,
                use_batch_api=False,  # Process immediately
            )

            processed = await batch_processor.process_queue(limit=limit)
            usage = batch_processor.claude_client.get_usage_stats()

            return processed, usage

        finally:
            await db.close()

    console.print(f"[yellow]Processing pending summaries (limit: {limit})...[/yellow]")

    try:
        processed, usage = asyncio.run(do_process())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Processed {processed} summaries.[/green]")
    console.print(f"[dim]Tokens used: {usage['total_input_tokens']} in, {usage['total_output_tokens']} out[/dim]")
    console.print(f"[dim]Estimated cost: ${usage['estimated_cost_usd']:.4f}[/dim]")


@app.command()
def focus(
    goal: str = typer.Option(
        None,
        "--goal",
        "-g",
        help="Goal name (e.g., 'Deep work on captains-log')",
    ),
    target: int = typer.Option(
        120,
        "--target",
        "-t",
        help="Target minutes for the goal",
    ),
    sessions: int = typer.Option(
        4,
        "--sessions",
        "-s",
        help="Estimated Pomodoro sessions to complete the task",
    ),
    apps: str = typer.Option(
        None,
        "--apps",
        "-a",
        help="Comma-separated list of apps to track (e.g., 'VS Code,Terminal')",
    ),
    project: str = typer.Option(
        None,
        "--project",
        "-p",
        help="Project name to track",
    ),
    mode: str = typer.Option(
        "passive",
        "--mode",
        "-m",
        help="Tracking mode: 'passive' (always track) or 'strict' (timer only)",
    ),
    no_widget: bool = typer.Option(
        False,
        "--no-widget",
        help="Run without floating widget",
    ),
) -> None:
    """Start a focus session with Pomodoro timer and goal tracking.

    Examples:
        captains-log focus -g "Deep work" -t 120 -a "VS Code,Terminal" --sessions 4
        captains-log focus -g "Writing docs" -p "captains-log" -s 2
        captains-log focus  # Interactive mode
    """
    config = get_config()

    # Interactive mode if no goal specified
    if not goal:
        from rich.prompt import Prompt, IntPrompt

        console.print("[bold]Focus Mode Setup[/bold]\n")

        goal = Prompt.ask("Goal name", default="Deep work")
        target = IntPrompt.ask("Target minutes", default=120)
        sessions = IntPrompt.ask("Estimated sessions", default=4)

        app_input = Prompt.ask("Apps to track (comma-separated)", default="VS Code,Terminal")
        apps = app_input if app_input else None

        project = Prompt.ask("Project name (optional)", default="")
        if not project:
            project = None

    console.print(f"\n[green]Starting focus session:[/green] {goal}")
    console.print(f"  Target: {target} minutes ({sessions} sessions)")
    if apps:
        console.print(f"  Apps: {apps}")
    if project:
        console.print(f"  Project: {project}")
    console.print(f"  Mode: {mode}")
    console.print(f"  Widget: {'disabled' if no_widget else 'enabled'}\n")

    async def run_focus():
        from captains_log.focus.activity_matcher import MatchCriteria
        from captains_log.storage.database import Database
        from captains_log.widget.widget_controller import WidgetController

        db = Database(config.db_path)
        await db.connect()

        try:
            # Build match criteria
            criteria = MatchCriteria()
            if apps:
                criteria.apps = [a.strip() for a in apps.split(",")]
            if project:
                criteria.projects = [project]

            # Create controller
            controller = WidgetController(db=db, config=config.focus)

            # Start focus session
            session = await controller.start_focus(
                goal_name=goal,
                target_minutes=target,
                estimated_sessions=sessions,
                match_criteria=criteria,
                tracking_mode=mode,
                show_widget=not no_widget,
            )

            console.print("[green]Focus session started![/green]")
            console.print("Press Ctrl+C to stop\n")

            # Start the timer
            await controller.resume_timer()

            # Run until stopped
            try:
                from Foundation import NSDate, NSRunLoop

                while controller.is_active:
                    # Process macOS events
                    NSRunLoop.currentRunLoop().runUntilDate_(
                        NSDate.dateWithTimeIntervalSinceNow_(0.5)
                    )
                    await asyncio.sleep(0.1)

                    # Check for control commands
                    ctrl = read_focus_control()
                    if ctrl:
                        action = ctrl.get("action")
                        if action == "pause":
                            await controller.pause_timer()
                        elif action == "resume":
                            await controller.resume_timer()
                        elif action == "skip":
                            await controller.skip_timer()
                        elif action == "stop":
                            break

                    # Show status periodically
                    if controller.timer_state:
                        status = controller.get_status()
                        timer_info = status.get("timer", {})
                        session_info = status.get("session", {})

                        # Simple status line (overwrite)
                        sys.stdout.write(
                            f"\r🍅 {timer_info.get('time_remaining', '--:--')} | "
                            f"Progress: {session_info.get('progress_text', '--')} "
                            f"({session_info.get('progress_percent', 0):.0f}%)    "
                        )
                        sys.stdout.flush()

            except ImportError:
                # No PyObjC RunLoop, just use asyncio
                while controller.is_active:
                    # Check for control commands
                    ctrl = read_focus_control()
                    if ctrl:
                        action = ctrl.get("action")
                        if action == "pause":
                            await controller.pause_timer()
                        elif action == "resume":
                            await controller.resume_timer()
                        elif action == "skip":
                            await controller.skip_timer()
                        elif action == "stop":
                            break
                    await asyncio.sleep(1)

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Stopping focus session...[/yellow]")
        finally:
            if controller.is_active:
                session = await controller.stop_focus()
                if session:
                    console.print(f"\n[bold]Session Summary:[/bold]")
                    console.print(f"  Total focus time: {session.format_progress()}")
                    console.print(f"  Pomodoros completed: {session.pomodoro_count}")
                    console.print(f"  Goal completed: {'Yes' if session.completed else 'No'}")
            await db.close()

    try:
        asyncio.run(run_focus())
    except KeyboardInterrupt:
        pass


@app.command(name="focus-status")
def focus_status() -> None:
    """Show current focus session status."""
    config = get_config()

    async def get_focus_status():
        from captains_log.storage.database import Database
        from datetime import date

        db = Database(config.db_path)
        await db.connect()

        try:
            today = date.today().isoformat()

            # Get today's sessions
            sessions = await db.fetch_all(
                """SELECT fs.*, fg.name as goal_name, fg.target_minutes
                   FROM focus_sessions fs
                   JOIN focus_goals fg ON fs.goal_id = fg.id
                   WHERE fs.date = ?
                   ORDER BY fs.created_at DESC""",
                (today,)
            )

            # Get active goals
            goals = await db.fetch_all(
                "SELECT * FROM focus_goals WHERE is_active = 1 ORDER BY created_at DESC"
            )

            return sessions, goals

        finally:
            await db.close()

    try:
        sessions, goals = asyncio.run(get_focus_status())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print(Panel("[bold]Focus Mode Status[/bold]", border_style="blue"))

    # Today's sessions
    if sessions:
        table = Table(title="Today's Sessions", show_header=True, header_style="bold cyan")
        table.add_column("Goal")
        table.add_column("Progress")
        table.add_column("Pomodoros")
        table.add_column("Status")

        for s in sessions:
            progress = f"{s['total_focus_minutes']:.0f}m / {s['target_minutes']}m"
            pct = (s['total_focus_minutes'] / s['target_minutes'] * 100) if s['target_minutes'] > 0 else 0
            progress += f" ({pct:.0f}%)"

            status = "[green]Complete[/green]" if s['completed'] else "[yellow]In Progress[/yellow]"

            table.add_row(
                s['goal_name'],
                progress,
                f"🍅 {s['pomodoro_count']}",
                status
            )

        console.print(table)
    else:
        console.print("[dim]No focus sessions today[/dim]")

    console.print()

    # Active goals
    if goals:
        console.print("[bold]Active Goals:[/bold]")
        for g in goals[:5]:
            console.print(f"  • {g['name']} ({g['target_minutes']} min)")
    else:
        console.print("[dim]No active goals[/dim]")

    console.print("\n[dim]Use 'captains-log focus -g \"Goal name\"' to start a focus session[/dim]")


@app.command(name="focus-goals")
def focus_goals(
    create: str = typer.Option(None, "--create", "-c", help="Create a new goal"),
    target: int = typer.Option(120, "--target", "-t", help="Target minutes for new goal"),
    apps: str = typer.Option(None, "--apps", "-a", help="Apps to track for new goal"),
    delete: int = typer.Option(None, "--delete", "-d", help="Delete goal by ID"),
) -> None:
    """Manage focus goals."""
    config = get_config()

    async def manage_goals():
        from captains_log.storage.database import Database
        from captains_log.focus.goal_tracker import GoalTracker, FocusGoal, GoalType
        from captains_log.focus.activity_matcher import MatchCriteria
        import json

        db = Database(config.db_path)
        await db.connect()

        try:
            tracker = GoalTracker(db)

            if create:
                # Create new goal
                criteria = MatchCriteria()
                if apps:
                    criteria.apps = [a.strip() for a in apps.split(",")]

                goal = FocusGoal(
                    name=create,
                    goal_type=GoalType.APP_BASED,
                    target_minutes=target,
                    match_criteria=criteria,
                )
                goal = await tracker.create_goal(goal)
                console.print(f"[green]Created goal #{goal.id}: {goal.name}[/green]")
                return

            if delete:
                # Delete goal
                await tracker.delete_goal(delete)
                console.print(f"[yellow]Deleted goal #{delete}[/yellow]")
                return

            # List goals
            goals = await tracker.list_goals(active_only=False)

            if not goals:
                console.print("[dim]No goals found. Create one with --create[/dim]")
                return

            table = Table(title="Focus Goals", show_header=True, header_style="bold cyan")
            table.add_column("ID")
            table.add_column("Name")
            table.add_column("Target")
            table.add_column("Apps")
            table.add_column("Status")

            for g in goals:
                apps_str = ", ".join(g.match_criteria.apps[:3]) if g.match_criteria.apps else "-"
                if g.match_criteria.apps and len(g.match_criteria.apps) > 3:
                    apps_str += f" +{len(g.match_criteria.apps) - 3}"

                status = "[green]Active[/green]" if g.is_active else "[dim]Inactive[/dim]"

                table.add_row(
                    str(g.id),
                    g.name,
                    f"{g.target_minutes}m",
                    apps_str,
                    status
                )

            console.print(table)

        finally:
            await db.close()

    try:
        asyncio.run(manage_goals())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# Control file for focus session commands
FOCUS_CONTROL_FILE = Path.home() / "Library" / "Application Support" / "CaptainsLog" / "focus_control.json"


def write_focus_control(action: str) -> None:
    """Write a control command for the running focus session."""
    import json
    FOCUS_CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)
    FOCUS_CONTROL_FILE.write_text(json.dumps({"action": action, "timestamp": datetime.now().isoformat()}))


def read_focus_control() -> dict | None:
    """Read and clear the control command."""
    import json
    if not FOCUS_CONTROL_FILE.exists():
        return None
    try:
        data = json.loads(FOCUS_CONTROL_FILE.read_text())
        FOCUS_CONTROL_FILE.unlink()  # Clear after reading
        return data
    except Exception:
        return None


@app.command(name="focus-timer")
def focus_timer(
    action: str = typer.Argument(..., help="Action: pause, resume, skip"),
) -> None:
    """Control the focus timer (pause, resume, skip)."""
    if action not in ("pause", "resume", "skip", "start"):
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Valid actions: pause, resume, skip")
        raise typer.Exit(1)

    # Map 'start' to 'resume' for consistency
    if action == "start":
        action = "resume"

    write_focus_control(action)
    console.print(f"[green]Sent {action} command[/green]")


@app.command(name="focus-stop")
def focus_stop() -> None:
    """Stop the current focus session."""
    write_focus_control("stop")
    console.print("[yellow]Stopping focus session...[/yellow]")


# =============================================================================
# Time Optimization Commands
# =============================================================================


@app.command(name="optimize")
def optimize_status() -> None:
    """Show current time optimization metrics and status."""
    config = get_config()

    async def get_metrics():
        from captains_log.storage.database import Database
        from captains_log.optimization.deal_classifier import DEALClassifier
        from captains_log.optimization.interrupt_detector import InterruptDetector
        from captains_log.optimization.context_switch_analyzer import ContextSwitchAnalyzer
        from captains_log.optimization.meeting_fragmentation import MeetingFragmentationAnalyzer
        import json

        db = Database(config.db_path)
        await db.connect()

        try:
            today = datetime.utcnow()

            # Get DEAL metrics
            deal_classifier = DEALClassifier(db=db)
            deal_metrics = await deal_classifier.get_daily_metrics(today)

            # Get interrupt metrics
            interrupt_detector = InterruptDetector(db=db)
            interrupt_metrics = await interrupt_detector.get_daily_metrics(today)

            # Get context switch metrics
            switch_analyzer = ContextSwitchAnalyzer(db=db)
            switch_metrics = await switch_analyzer.get_daily_metrics(today)

            # Get fragmentation metrics
            frag_analyzer = MeetingFragmentationAnalyzer(db=db)
            frag_metrics = await frag_analyzer.analyze_day(today)

            # Read optimization status file if exists
            status_file = config.data_dir / "optimization_status.json"
            status_data = {}
            if status_file.exists():
                try:
                    status_data = json.loads(status_file.read_text())
                except Exception:
                    pass

            return {
                "deal": deal_metrics,
                "interrupts": interrupt_metrics,
                "switches": switch_metrics,
                "fragmentation": frag_metrics,
                "status": status_data,
            }

        finally:
            await db.close()

    try:
        metrics = asyncio.run(get_metrics())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Status color indicator
    status_color = metrics["status"].get("status_color", "green")
    color_emoji = {"green": "🟢", "amber": "🟡", "red": "🔴"}.get(status_color, "⚪")

    console.print(Panel(
        f"{color_emoji} Time Optimization Status: [bold]{status_color.upper()}[/bold]",
        title="Captain's Log Optimization",
        border_style=status_color
    ))
    console.print()

    # DEAL breakdown
    deal = metrics["deal"]
    table = Table(title="Time Distribution (DEAL Framework)", show_header=True, header_style="bold cyan")
    table.add_column("Category")
    table.add_column("Time")
    table.add_column("Percent")
    table.add_column("Description")

    total = deal.total_minutes or 1  # Avoid division by zero

    table.add_row(
        "[green]Leverage[/green]",
        f"{deal.leverage_minutes:.0f}m",
        f"{deal.leverage_minutes/total*100:.0f}%",
        "High-value work to protect"
    )
    table.add_row(
        "[blue]Delegate[/blue]",
        f"{deal.delegate_minutes:.0f}m",
        f"{deal.delegate_minutes/total*100:.0f}%",
        "Admin tasks others could do"
    )
    table.add_row(
        "[red]Eliminate[/red]",
        f"{deal.eliminate_minutes:.0f}m",
        f"{deal.eliminate_minutes/total*100:.0f}%",
        "Distractions to reduce"
    )
    table.add_row(
        "[yellow]Automate[/yellow]",
        f"{deal.automate_minutes:.0f}m",
        f"{deal.automate_minutes/total*100:.0f}%",
        "Repetitive patterns to batch"
    )

    console.print(table)
    console.print()

    # Key Metrics
    table = Table(title="Today's Key Metrics", show_header=True, header_style="bold cyan")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_column("Status")

    # Interrupts
    interrupts = metrics["interrupts"]
    interrupt_status = "[green]Good[/green]" if interrupts.total_interrupts < 15 else (
        "[yellow]High[/yellow]" if interrupts.total_interrupts < 30 else "[red]Very High[/red]"
    )
    table.add_row(
        "Interrupts",
        str(interrupts.total_interrupts),
        interrupt_status
    )

    # Context switches
    switches = metrics["switches"]
    switch_status = "[green]Good[/green]" if switches.total_switches < 30 else (
        "[yellow]High[/yellow]" if switches.total_switches < 60 else "[red]Very High[/red]"
    )
    table.add_row(
        "Context Switches",
        str(switches.total_switches),
        switch_status
    )
    table.add_row(
        "  Est. Cost",
        f"{switches.estimated_total_cost_minutes:.0f}m",
        "[dim]Refocus time lost[/dim]"
    )

    # Fragmentation
    frag = metrics["fragmentation"]
    frag_status = "[green]Good[/green]" if frag.swiss_cheese_score < 0.3 else (
        "[yellow]Fragmented[/yellow]" if frag.swiss_cheese_score < 0.6 else "[red]Swiss Cheese[/red]"
    )
    table.add_row(
        "Swiss Cheese Score",
        f"{frag.swiss_cheese_score:.2f}",
        frag_status
    )
    table.add_row(
        "  Meetings",
        str(frag.total_meetings),
        f"[dim]{frag.meeting_hours:.1f}h[/dim]"
    )
    table.add_row(
        "  Largest Focus Block",
        f"{frag.largest_focus_block_minutes:.0f}m",
        "[dim]Usable time[/dim]"
    )

    console.print(table)
    console.print()

    # Potential savings
    savings = deal.potential_savings_minutes
    console.print(f"[bold]Potential Time Savings:[/bold] {savings:.0f} minutes/day")
    console.print(f"[dim]Target: 20% (~96 min/day for 8h workday)[/dim]")


@app.command(name="optimize-briefing")
def optimize_briefing(
    yesterday: bool = typer.Option(False, "--yesterday", "-y", help="Show yesterday's briefing"),
) -> None:
    """Show the daily optimization briefing."""
    config = get_config()

    async def get_briefing():
        from captains_log.storage.database import Database
        from captains_log.optimization.daily_briefing import DailyBriefingGenerator

        db = Database(config.db_path)
        await db.connect()

        try:
            generator = DailyBriefingGenerator(db=db)

            target_date = datetime.utcnow()
            if yesterday:
                target_date = target_date - timedelta(days=1)

            # Try to get existing briefing
            briefing = await generator.get_briefing(target_date)

            # Generate if not found
            if not briefing:
                briefing = await generator.generate_briefing(target_date)

            return briefing

        finally:
            await db.close()

    try:
        briefing = asyncio.run(get_briefing())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if not briefing:
        console.print("[yellow]No briefing available[/yellow]")
        return

    # Display briefing
    console.print(Panel(
        f"[bold]{briefing.greeting}[/bold]",
        border_style="blue"
    ))
    console.print()

    # Yesterday's wins
    if briefing.wins:
        console.print("[bold green]Yesterday's Wins[/bold green]")
        for win in briefing.wins:
            improvement = f" (+{win.improvement_percent:.0f}%)" if win.improvement_percent else ""
            console.print(f"  ✓ {win.message}{improvement}")
        console.print()

    # Yesterday's summary
    console.print("[bold]Yesterday's Summary[/bold]")
    console.print(f"  • Deep work: {briefing.yesterday_deep_work_hours:.1f} hours")
    console.print(f"  • Interrupts: {briefing.yesterday_interrupts}")
    console.print(f"  • Context switches: {briefing.yesterday_context_switches}")
    console.print(f"  • Meetings: {briefing.yesterday_meeting_hours:.1f} hours")
    console.print()

    # Today's focus
    if briefing.focus_suggestions:
        console.print("[bold cyan]Today's Focus[/bold cyan]")
        for suggestion in briefing.focus_suggestions:
            console.print(f"  → {suggestion}")
        console.print()

    # Quick wins
    if briefing.quick_wins:
        console.print("[bold yellow]Quick Wins[/bold yellow]")
        for qw in briefing.quick_wins:
            priority_color = {"high": "red", "medium": "yellow", "low": "dim"}.get(qw.priority, "white")
            console.print(f"  [{priority_color}]●[/{priority_color}] {qw.action}")
            console.print(f"    [dim]→ {qw.estimated_benefit}[/dim]")
        console.print()

    # Week context
    if briefing.week_progress:
        console.print(f"[dim italic]{briefing.week_progress}[/dim italic]")


@app.command(name="optimize-report")
def optimize_report(
    weeks_ago: int = typer.Option(0, "--weeks-ago", "-w", help="Generate report for N weeks ago"),
) -> None:
    """Generate comprehensive weekly optimization report."""
    config = get_config()

    async def get_report():
        from captains_log.storage.database import Database
        from captains_log.optimization.weekly_report import WeeklyReportGenerator

        db = Database(config.db_path)
        await db.connect()

        try:
            generator = WeeklyReportGenerator(
                db=db,
                target_savings_percent=config.optimization.target_savings_percent
            )

            week_start = None
            if weeks_ago > 0:
                today = datetime.utcnow()
                week_start = today - timedelta(days=today.weekday() + 7 * weeks_ago)

            # Try to get existing report
            report = await generator.get_report(week_start)

            # Generate if not found
            if not report:
                report = await generator.generate_report(week_start)

            return report

        finally:
            await db.close()

    console.print("[yellow]Generating weekly optimization report...[/yellow]\n")

    try:
        report = asyncio.run(get_report())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if not report:
        console.print("[yellow]No report available[/yellow]")
        return

    # Print the text report
    console.print(report.to_text())


@app.command(name="optimize-profile")
def optimize_profile(
    role: str = typer.Option(None, "--role", "-r", help="Your role (e.g., 'Software Engineer', 'Manager')"),
    department: str = typer.Option(None, "--dept", "-d", help="Your department"),
    hourly_rate: float = typer.Option(None, "--rate", help="Hourly rate for ROI calculations"),
    work_hours: int = typer.Option(None, "--hours", "-h", help="Work hours per week"),
    savings_goal: float = typer.Option(None, "--goal", "-g", help="Time savings goal (0.0-1.0, e.g., 0.20 for 20%)"),
) -> None:
    """Manage your time optimization profile."""
    config = get_config()

    async def manage_profile():
        from captains_log.storage.database import Database
        from captains_log.optimization.schemas import UserProfile
        import json

        db = Database(config.db_path)
        await db.connect()

        try:
            # Try to get existing profile
            existing = await db.fetch_one(
                "SELECT * FROM user_profile ORDER BY id DESC LIMIT 1"
            )

            # If updating
            if any([role, department, hourly_rate, work_hours, savings_goal]):
                profile_data = {}
                if existing:
                    profile_data = {
                        "role": existing.get("role"),
                        "department": existing.get("department"),
                        "hourly_rate": existing.get("hourly_rate", 0),
                        "work_hours_per_week": existing.get("work_hours_per_week", 40),
                        "time_savings_goal": existing.get("time_savings_goal", 0.20),
                    }

                # Update with new values
                if role:
                    profile_data["role"] = role
                if department:
                    profile_data["department"] = department
                if hourly_rate is not None:
                    profile_data["hourly_rate"] = hourly_rate
                if work_hours is not None:
                    profile_data["work_hours_per_week"] = work_hours
                if savings_goal is not None:
                    profile_data["time_savings_goal"] = savings_goal

                # Save profile
                profile_data["updated_at"] = datetime.utcnow().isoformat()
                if not existing:
                    profile_data["created_at"] = datetime.utcnow().isoformat()
                    await db.insert("user_profile", profile_data)
                else:
                    await db.execute(
                        """UPDATE user_profile SET
                           role = ?, department = ?, hourly_rate = ?,
                           work_hours_per_week = ?, time_savings_goal = ?, updated_at = ?
                           WHERE id = ?""",
                        (
                            profile_data.get("role"),
                            profile_data.get("department"),
                            profile_data.get("hourly_rate"),
                            profile_data.get("work_hours_per_week"),
                            profile_data.get("time_savings_goal"),
                            profile_data["updated_at"],
                            existing["id"]
                        )
                    )

                console.print("[green]Profile updated![/green]")
                return profile_data
            else:
                # Just return existing
                if existing:
                    return dict(existing)
                return None

        finally:
            await db.close()

    try:
        profile = asyncio.run(manage_profile())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if not profile:
        console.print("[dim]No profile configured. Set one up:[/dim]")
        console.print('captains-log optimize-profile --role "Software Engineer" --dept "Engineering" --rate 75 --hours 40 --goal 0.20')
        return

    # Display profile
    table = Table(title="Time Optimization Profile", show_header=False, box=None)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("Role", profile.get("role") or "[dim]Not set[/dim]")
    table.add_row("Department", profile.get("department") or "[dim]Not set[/dim]")

    rate = profile.get("hourly_rate")
    table.add_row("Hourly Rate", f"${rate:.2f}" if rate else "[dim]Not set[/dim]")

    hours = profile.get("work_hours_per_week", 40)
    table.add_row("Work Hours/Week", str(hours))

    goal = profile.get("time_savings_goal", 0.20)
    table.add_row("Savings Goal", f"{goal*100:.0f}%")

    # Calculate target hours
    target_hours = hours * goal
    table.add_row("Target Savings", f"{target_hours:.1f}h/week")

    console.print(table)


@app.command(name="goals")
def goals_cmd(
    add: str = typer.Option(None, "--add", "-a", help="Add a new goal"),
    hours: float = typer.Option(40.0, "--hours", "-h", help="Estimated hours for goal"),
    deadline: str = typer.Option(None, "--deadline", "-d", help="Deadline (YYYY-MM-DD)"),
    delete: int = typer.Option(None, "--delete", help="Delete goal by ID"),
    list_all: bool = typer.Option(False, "--all", help="Show all goals including completed"),
) -> None:
    """Manage productivity goals (quarterly/half-year objectives)."""
    config = get_config()

    async def manage():
        from captains_log.focus.productivity_goals import (
            ProductivityGoalsManager,
            ProductivityGoal,
        )
        from captains_log.storage.database import Database
        from datetime import date

        db = Database(config.db_path)
        await db.connect()

        try:
            manager = ProductivityGoalsManager(db)

            if add:
                deadline_date = None
                if deadline:
                    try:
                        deadline_date = date.fromisoformat(deadline)
                    except ValueError:
                        console.print(f"[red]Invalid date format: {deadline}. Use YYYY-MM-DD[/red]")
                        return

                goal = ProductivityGoal(
                    name=add,
                    estimated_hours=hours,
                    deadline=deadline_date,
                )
                goal = await manager.create_goal(goal)
                console.print(f"[green]Created goal #{goal.id}: {goal.name}[/green]")
                console.print(f"  Estimated: {hours}h | Deadline: {deadline or 'None'}")
                return

            if delete:
                await manager.delete_goal(delete)
                console.print(f"[yellow]Deleted goal #{delete}[/yellow]")
                return

            # List goals
            goals = await manager.list_goals(active_only=not list_all, limit=10)

            if not goals:
                console.print("[dim]No goals found. Create one with --add[/dim]")
                console.print('[dim]Example: captains-log goals --add "Q1 Project" --hours 80 --deadline 2025-03-31[/dim]')
                return

            table = Table(title="Productivity Goals", show_header=True, header_style="bold cyan")
            table.add_column("ID")
            table.add_column("Goal")
            table.add_column("Est.")
            table.add_column("Progress")
            table.add_column("Daily Target")
            table.add_column("Deadline")

            for g in goals:
                progress = f"{g.progress_percent:.0f}%"
                daily = f"{g.daily_target_minutes:.0f}m"
                deadline_str = g.deadline.isoformat() if g.deadline else "-"

                # Color code by status
                today_status = g.get_today_status()
                if today_status.value == "green":
                    status_color = "green"
                elif today_status.value == "amber":
                    status_color = "yellow"
                elif today_status.value == "red":
                    status_color = "red"
                else:
                    status_color = "dim"

                table.add_row(
                    str(g.id),
                    g.name,
                    f"{g.estimated_hours:.0f}h",
                    f"[{status_color}]{progress}[/{status_color}]",
                    daily,
                    deadline_str
                )

            console.print(table)

        finally:
            await db.close()

    try:
        asyncio.run(manage())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command(name="tasks")
def tasks_cmd(
    goal_id: int = typer.Option(None, "--goal", "-g", help="Goal ID to list/add tasks for"),
    add: str = typer.Option(None, "--add", "-a", help="Add a new task"),
    minutes: int = typer.Option(30, "--minutes", "-m", help="Estimated minutes for task"),
    complete: int = typer.Option(None, "--complete", "-c", help="Complete task by ID"),
    delete: int = typer.Option(None, "--delete", help="Delete task by ID"),
) -> None:
    """Manage tasks within productivity goals."""
    config = get_config()

    async def manage():
        from captains_log.focus.productivity_goals import (
            ProductivityGoalsManager,
            GoalTask,
        )
        from captains_log.storage.database import Database

        db = Database(config.db_path)
        await db.connect()

        try:
            manager = ProductivityGoalsManager(db)

            if add:
                if not goal_id:
                    console.print("[red]Please specify --goal ID when adding a task[/red]")
                    return

                task = GoalTask(
                    goal_id=goal_id,
                    name=add,
                    estimated_minutes=minutes,
                )
                task = await manager.create_task(task)
                console.print(f"[green]Created task #{task.id}: {task.name} ({minutes}m)[/green]")
                return

            if complete:
                await manager.complete_task(complete)
                console.print(f"[green]Completed task #{complete}[/green]")
                return

            if delete:
                await manager.delete_task(delete)
                console.print(f"[yellow]Deleted task #{delete}[/yellow]")
                return

            # List tasks
            goals = await manager.list_goals(active_only=True, limit=5)

            if not goals:
                console.print("[dim]No goals found. Create one first with: captains-log goals --add[/dim]")
                return

            for g in goals:
                if goal_id and g.id != goal_id:
                    continue

                console.print(f"\n[bold]{g.name}[/bold] ({g.estimated_hours:.0f}h)")

                tasks = g.tasks
                if not tasks:
                    console.print("  [dim]No tasks. Add with: captains-log tasks --goal {g.id} --add \"Task name\"[/dim]")
                    continue

                for t in tasks:
                    status = "[green]✓[/green]" if t.is_completed else "○"
                    console.print(f"  {status} #{t.id} {t.name} ({t.estimated_minutes}m)")
                    for sub in t.subtasks:
                        sub_status = "[green]✓[/green]" if sub.is_completed else "○"
                        console.print(f"    {sub_status} #{sub.id} {sub.name} ({sub.estimated_minutes}m)")

        finally:
            await db.close()

    try:
        asyncio.run(manage())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command(name="goals-status")
def goals_status_cmd() -> None:
    """Show productivity goals status as JSON (for menu bar widget)."""
    config = get_config()

    async def get_status():
        from captains_log.focus.productivity_goals import ProductivityGoalsManager
        from captains_log.storage.database import Database

        db = Database(config.db_path)
        await db.connect()

        try:
            manager = ProductivityGoalsManager(db)
            return await manager.get_goals_status_json()
        finally:
            await db.close()

    try:
        json_str = asyncio.run(get_status())
        console.print(json_str)
    except Exception as e:
        console.print(f'{{"error": "{e}"}}')
        raise typer.Exit(1)


@app.command(name="settings")
def settings_cmd(
    pomodoro: int = typer.Option(None, "--pomodoro", "-p", help="Default pomodoro duration in minutes"),
    target_mode: str = typer.Option(None, "--target-mode", "-t", help="Target mode: fixed or rolling"),
) -> None:
    """Manage app settings."""
    config = get_config()

    async def manage():
        from captains_log.focus.productivity_goals import ProductivityGoalsManager, TargetMode
        from captains_log.storage.database import Database

        db = Database(config.db_path)
        await db.connect()

        try:
            manager = ProductivityGoalsManager(db)

            if pomodoro is not None:
                await manager.set_setting("default_pomodoro_minutes", str(pomodoro))
                console.print(f"[green]Set default pomodoro to {pomodoro} minutes[/green]")

            if target_mode is not None:
                if target_mode not in ("fixed", "rolling"):
                    console.print("[red]Invalid target mode. Use 'fixed' or 'rolling'[/red]")
                    return
                await manager.set_setting("target_mode", target_mode)
                console.print(f"[green]Set target mode to {target_mode}[/green]")

            # Show current settings
            pom = await manager.get_default_pomodoro_minutes()
            mode = await manager.get_target_mode()

            table = Table(title="App Settings", show_header=True, header_style="bold cyan")
            table.add_column("Setting")
            table.add_column("Value")

            table.add_row("Default Pomodoro", f"{pom} minutes")
            table.add_row("Target Mode", mode.value)

            console.print(table)

        finally:
            await db.close()

    try:
        asyncio.run(manage())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def today() -> None:
    """Show today's activity summary — quick glanceable view."""
    config = get_config()

    async def get_today():
        from captains_log.storage.database import Database
        from captains_log.summarizers.duration_calculator import (
            _format_duration,
            get_app_durations,
            get_category_durations,
            get_focus_hours,
            get_most_focused_hour,
            get_total_active_hours,
        )

        db = Database(config.db_path)
        await db.connect()

        try:
            today_str = datetime.now().strftime("%Y-%m-%d")

            active_hours = await get_total_active_hours(db, today_str)
            focus_hrs = await get_focus_hours(db, today_str)
            app_durs = await get_app_durations(db, today_str)
            cat_durs = await get_category_durations(db, today_str)
            focused_hour = await get_most_focused_hour(db, today_str)

            return {
                "date": today_str,
                "active_hours": active_hours,
                "focus_hours": focus_hrs,
                "app_durations": app_durs,
                "category_durations": cat_durs,
                "most_focused_hour": focused_hour,
                "fmt": _format_duration,
            }
        finally:
            await db.close()

    try:
        data = asyncio.run(get_today())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if data["active_hours"] < 0.02:  # less than ~1 minute
        console.print(Panel(
            "[yellow]No activity recorded today.[/yellow]\n\n"
            "Is the daemon running? Check: captains-log status",
            title="Today",
            border_style="yellow",
        ))
        return

    fmt = data["fmt"]
    lines = []
    lines.append(f"  Date: {data['date']}")
    lines.append(
        f"  Active: {fmt(data['active_hours'] * 60)}    "
        f"Focus: {fmt(data['focus_hours'] * 60)}"
    )
    lines.append("")

    # App duration breakdown
    app_durs = data["app_durations"]
    if app_durs:
        lines.append("  Apps:")
        max_name = max(len(n) for n in app_durs)
        max_mins = max(app_durs.values()) if app_durs else 1
        for name, mins in list(app_durs.items())[:10]:
            bar_len = int(mins / max_mins * 20) if max_mins > 0 else 0
            bar = "\u2588" * bar_len
            lines.append(f"    {name:<{max_name}}  {fmt(mins):>7}  {bar}")
        lines.append("")

    # Category breakdown
    cat_durs = data["category_durations"]
    if cat_durs:
        lines.append("  Categories:")
        for cat, mins in cat_durs.items():
            lines.append(f"    {cat:<16} {fmt(mins):>7}")
        lines.append("")

    # Most focused hour
    if data["most_focused_hour"]:
        lines.append(f"  Most focused hour: {data['most_focused_hour']}")

    console.print(Panel(
        "\n".join(lines),
        title=f"Today \u2014 {data['date']}",
        border_style="green",
    ))


@app.command()
def digest(
    date: str = typer.Option(
        None, "--date", "-d",
        help="Date to generate digest for (YYYY-MM-DD, default: today)",
    ),
    notify: bool = typer.Option(
        False, "--notify", "-n",
        help="Send as macOS notification",
    ),
) -> None:
    """Generate and display the daily digest."""
    config = get_config()

    async def get_digest():
        from captains_log.notifications.daily_digest import DailyDigestGenerator
        from captains_log.storage.database import Database

        db = Database(config.db_path)
        await db.connect()

        try:
            target = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
            generator = DailyDigestGenerator(db)
            return await generator.generate(target)
        finally:
            await db.close()

    try:
        d = asyncio.run(get_digest())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        d.to_rich_text(),
        title=f"Daily Digest — {d.date}",
        border_style="blue",
    ))

    if notify:
        from captains_log.notifications.notifier import send_notification

        send_notification(
            title=d.notification_title,
            body=d.notification_body,
            subtitle=d.notification_subtitle,
            sound="Pop",
        )
        console.print("[green]Notification sent[/green]")


@app.command()
def week() -> None:
    """Show this week vs last week comparison."""
    config = get_config()

    async def get_week_data():
        from captains_log.storage.database import Database
        from captains_log.summarizers.duration_calculator import (
            get_app_durations,
            get_category_durations,
            get_focus_hours,
            get_total_active_hours,
        )

        db = Database(config.db_path)
        await db.connect()

        try:
            now = datetime.now()

            # This week: Monday to today
            days_since_monday = now.weekday()
            this_monday = now - timedelta(days=days_since_monday)
            last_monday = this_monday - timedelta(days=7)

            # Compute each day this week
            this_week_days = []
            for i in range(days_since_monday + 1):
                day = this_monday + timedelta(days=i)
                ds = day.strftime("%Y-%m-%d")
                active = await get_total_active_hours(db, ds)
                focus = await get_focus_hours(db, ds)
                apps = await get_app_durations(db, ds)
                cats = await get_category_durations(db, ds)
                this_week_days.append({
                    "date": ds,
                    "active_hours": active,
                    "focus_hours": focus,
                    "app_durations": apps,
                    "category_durations": cats,
                })

            # Compute each day last week
            last_week_days = []
            for i in range(7):
                day = last_monday + timedelta(days=i)
                ds = day.strftime("%Y-%m-%d")
                active = await get_total_active_hours(db, ds)
                focus = await get_focus_hours(db, ds)
                last_week_days.append({
                    "date": ds,
                    "active_hours": active,
                    "focus_hours": focus,
                })

            return this_week_days, last_week_days, days_since_monday
        finally:
            await db.close()

    try:
        this_week, last_week, days_done = asyncio.run(get_week_data())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    from captains_log.summarizers.duration_calculator import _format_duration

    fmt = _format_duration

    this_active_hrs = sum(d["active_hours"] for d in this_week)
    last_active_hrs = sum(d["active_hours"] for d in last_week)
    this_focus_hrs = sum(d["focus_hours"] for d in this_week)
    last_focus_hrs = sum(d["focus_hours"] for d in last_week)

    lines = []
    lines.append(
        f"  This week:  {fmt(this_active_hrs * 60)} active, "
        f"{fmt(this_focus_hrs * 60)} focus  ({days_done + 1} days)"
    )
    lines.append(
        f"  Last week:  {fmt(last_active_hrs * 60)} active, "
        f"{fmt(last_focus_hrs * 60)} focus  (7 days)"
    )

    if last_active_hrs > 0 and days_done > 0:
        projected = (this_active_hrs / (days_done + 1)) * 7
        diff = ((projected - last_active_hrs) / last_active_hrs) * 100
        direction = "up" if diff > 0 else "down"
        color = "green" if diff > 0 else "red"
        lines.append(f"  Trend:      [{color}]{abs(diff):.0f}% {direction}[/{color}] (projected)")
    lines.append("")

    # Per-day breakdown with active + focus hours
    lines.append("  Day-by-day:                Active   Focus")
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i, d in enumerate(this_week):
        bar_len = int(d["active_hours"] * 2) if d["active_hours"] > 0 else 0
        bar = "\u2588" * min(bar_len, 16)
        lines.append(
            f"    {day_names[i]}  {fmt(d['active_hours'] * 60):>7}  "
            f"{fmt(d['focus_hours'] * 60):>7}  {bar}"
        )

    # Top apps across the week (by duration)
    app_totals: dict[str, float] = {}
    for d in this_week:
        for app_name, mins in d["app_durations"].items():
            app_totals[app_name] = app_totals.get(app_name, 0) + mins

    if app_totals:
        lines.append("")
        lines.append("  Top apps this week:")
        sorted_apps = sorted(app_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        for name, mins in sorted_apps:
            lines.append(f"    {name:<20} {fmt(mins)}")

    # Category breakdown for the week
    cat_totals: dict[str, float] = {}
    for d in this_week:
        for cat, mins in d["category_durations"].items():
            cat_totals[cat] = cat_totals.get(cat, 0) + mins

    if cat_totals:
        lines.append("")
        lines.append("  Categories this week:")
        sorted_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
        for cat, mins in sorted_cats:
            lines.append(f"    {cat:<16} {fmt(mins)}")

    console.print(Panel(
        "\n".join(lines),
        title="Week Summary",
        border_style="blue",
    ))


@app.command()
def insights(
    days: int = typer.Option(14, "--days", "-d", help="Days of history to analyze"),
) -> None:
    """Show detected focus patterns from your activity history."""
    config = get_config()

    async def get_insights():
        from captains_log.insights.pattern_detector import PatternDetector

        detector = PatternDetector(str(config.db_path))
        return await detector.get_all_insights(days=days)

    console.print(f"[dim]Analyzing {days} days of activity...[/dim]\n")

    try:
        patterns = asyncio.run(get_insights())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Filter out patterns with no meaningful data
    has_data = False

    for pattern in patterns:
        if pattern.pattern_type == "peak_hours":
            peak_hours = pattern.data.get("peak_hours", [])
            if peak_hours:
                has_data = True
                lines = []
                lines.append("[bold cyan]Peak Hours[/bold cyan]")
                for ph in peak_hours:
                    lines.append(
                        f"  {ph['label']}  "
                        f"[green]{ph['avg_focus_minutes']:.0f}m[/green] focused, "
                        f"[dim]{ph['avg_switches']:.0f} switches/hr[/dim]"
                    )
                console.print(Panel("\n".join(lines), border_style="cyan"))
            else:
                console.print(Panel(
                    "[dim]Not enough data to detect peak hours.[/dim]",
                    title="Peak Hours",
                    border_style="dim",
                ))

        elif pattern.pattern_type == "context_switch_spike":
            spike_hours = pattern.data.get("spike_hours", [])
            daily_avg = pattern.data.get("daily_avg_switches", 0)
            if spike_hours:
                has_data = True
                lines = []
                lines.append("[bold yellow]Context Switch Spikes[/bold yellow]")
                lines.append(f"  [dim]Daily avg: {daily_avg:.0f} switches[/dim]")
                for sh in spike_hours[:5]:
                    lines.append(
                        f"  {sh['label']}  "
                        f"[red]{sh['avg_switches']:.0f}[/red] switches/hr"
                    )
                console.print(Panel("\n".join(lines), border_style="yellow"))
            else:
                console.print(Panel(
                    f"[dim]No significant context switch spikes detected.\n"
                    f"Daily avg: {daily_avg:.0f} switches[/dim]",
                    title="Context Switches",
                    border_style="dim",
                ))

        elif pattern.pattern_type == "weekly_rhythm":
            day_averages = pattern.data.get("day_averages", [])
            most = pattern.data.get("most_productive")
            least = pattern.data.get("least_productive")
            if day_averages:
                has_data = True
                lines = []
                lines.append("[bold blue]Weekly Rhythm[/bold blue]")
                if most:
                    lines.append(
                        f"  Best:  [green]{most['day']}[/green] "
                        f"({most['avg_hours']:.1f}h avg)"
                    )
                if least:
                    lines.append(
                        f"  Worst: [red]{least['day']}[/red] "
                        f"({least['avg_hours']:.1f}h avg)"
                    )
                lines.append("")
                # Bar chart of days
                max_hrs = max(d["avg_hours"] for d in day_averages) if day_averages else 1
                for d in sorted(day_averages, key=lambda x: x["dow"]):
                    bar_len = int(d["avg_hours"] / max_hrs * 16) if max_hrs > 0 else 0
                    bar = "\u2588" * bar_len
                    lines.append(f"  {d['day_short']}  {d['avg_hours']:>5.1f}h  {bar}")
                console.print(Panel("\n".join(lines), border_style="blue"))
            else:
                console.print(Panel(
                    "[dim]Not enough data to detect weekly rhythm.[/dim]",
                    title="Weekly Rhythm",
                    border_style="dim",
                ))

    if not has_data:
        console.print(
            "\n[yellow]No patterns detected yet. "
            "Keep the daemon running for a few days to accumulate data.[/yellow]"
        )


@app.command(name="weekly")
def weekly_cmd(
    week_offset: int = typer.Option(0, "--offset", "-o", help="Weeks ago (0=current)"),
) -> None:
    """Show comprehensive weekly digest with trends."""
    config = get_config()

    async def get_weekly():
        from captains_log.notifications.weekly_digest import WeeklyDigestGenerator
        from captains_log.storage.database import Database

        db = Database(config.db_path)
        await db.connect()

        try:
            generator = WeeklyDigestGenerator(db)
            ref_date = date.today() - timedelta(weeks=week_offset)
            return await generator.generate(week_of=ref_date)
        finally:
            await db.close()

    try:
        digest = asyncio.run(get_weekly())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    from captains_log.summarizers.duration_calculator import _format_duration

    fmt = _format_duration

    # ── Header with totals and trends ──────────────────────────────────── #
    active_trend = digest.active_trend_percent
    focus_trend = digest.focus_trend_percent

    def _trend_str(pct: float) -> str:
        if abs(pct) < 0.5:
            return "[dim]--[/dim]"
        color = "green" if pct > 0 else "red"
        arrow = "+" if pct > 0 else ""
        return f"[{color}]{arrow}{pct:.0f}%[/{color}]"

    header_lines = []
    header_lines.append(
        f"  Active: {fmt(digest.total_active_hours * 60):>7}  "
        f"({_trend_str(active_trend)} vs prev week)"
    )
    header_lines.append(
        f"  Focus:  {fmt(digest.focus_hours * 60):>7}  "
        f"({_trend_str(focus_trend)} vs prev week)"
    )
    header_lines.append(
        f"  Prev:   {fmt(digest.prev_week_active_hours * 60):>7} active, "
        f"{fmt(digest.prev_week_focus_hours * 60)} focus"
    )

    if digest.most_productive_day:
        header_lines.append(
            f"  Best day: [green]{digest.most_productive_day}[/green]    "
            f"Worst: [red]{digest.least_productive_day}[/red]"
        )

    console.print(Panel(
        "\n".join(header_lines),
        title=f"Weekly Digest \u2014 {digest.week_start.isoformat()} to {digest.week_end.isoformat()}",
        border_style="blue",
    ))

    # ── Daily breakdown ───────────────────────────────────────────────── #
    table = Table(title="Daily Breakdown", show_header=True, header_style="bold cyan")
    table.add_column("Day", min_width=6)
    table.add_column("Date", min_width=10)
    table.add_column("Active", justify="right", min_width=7)
    table.add_column("Focus", justify="right", min_width=7)
    table.add_column("Chart", min_width=18)

    max_hrs = max((d["active_hours"] for d in digest.daily_breakdown), default=1) or 1

    for d in digest.daily_breakdown:
        bar_len = int(d["active_hours"] / max_hrs * 16) if max_hrs > 0 else 0
        focus_len = int(d["focus_hours"] / max_hrs * 16) if max_hrs > 0 else 0
        # Show focus as green blocks, remaining active as blue blocks
        bar = "[green]" + "\u2588" * focus_len + "[/green]"
        if bar_len > focus_len:
            bar += "[blue]" + "\u2588" * (bar_len - focus_len) + "[/blue]"

        table.add_row(
            d["day_name"][:3],
            d["date"],
            fmt(d["active_hours"] * 60),
            fmt(d["focus_hours"] * 60),
            bar,
        )

    console.print(table)
    console.print("[dim]  Chart: [green]\u2588[/green] focus  [blue]\u2588[/blue] other active[/dim]")
    console.print()

    # ── Top apps ──────────────────────────────────────────────────────── #
    if digest.top_apps:
        table = Table(title="Top Apps", show_header=True, header_style="bold cyan")
        table.add_column("App", min_width=20)
        table.add_column("Hours", justify="right", min_width=7)

        for app_info in digest.top_apps[:8]:
            table.add_row(app_info["app"], f"{app_info['hours']:.1f}h")

        console.print(table)
        console.print()

    # ── Categories ────────────────────────────────────────────────────── #
    if digest.category_hours:
        table = Table(title="Categories", show_header=True, header_style="bold cyan")
        table.add_column("Category", min_width=16)
        table.add_column("Hours", justify="right", min_width=7)

        for cat, hrs in digest.category_hours.items():
            table.add_row(cat, f"{hrs:.1f}h")

        console.print(table)
        console.print()

    # ── Narrative ─────────────────────────────────────────────────────── #
    if digest.narrative:
        console.print(Panel(
            f"[italic]{digest.narrative}[/italic]",
            title="Summary",
            border_style="dim",
        ))


@app.command()
def recall(
    query: str = typer.Argument(
        ...,
        help="Natural language query about your activity history",
    ),
) -> None:
    """Ask questions about your activity history using AI.

    Examples:
        captains-log recall "what did I work on last Thursday"
        captains-log recall "how much time in Slack this week"
        captains-log recall "my most productive day last week"
    """
    config = get_config()

    api_key = config.claude_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Recall requires an API key.[/red]")
        console.print("Set ANTHROPIC_API_KEY or CAPTAINS_LOG_CLAUDE_API_KEY.")
        raise typer.Exit(1)

    async def do_recall():
        from captains_log.storage.database import Database

        db = Database(config.db_path)
        await db.connect()

        try:
            # Gather context data for Claude
            context = await _build_recall_context(db, query)

            # Call Claude to answer the question
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)

            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=(
                    "You are Captain's Log, a personal activity tracker. "
                    "Answer questions about the user's digital activity history based on the data provided. "
                    "Be concise and specific. Use hours and minutes, not raw numbers. "
                    "If the data doesn't contain enough information, say so. "
                    "Format your response for a terminal (no markdown headers, keep it compact)."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": f"Question: {query}\n\nActivity data:\n{context}",
                    }
                ],
            )

            return message.content[0].text

        finally:
            await db.close()

    console.print(f"[dim]Searching your history...[/dim]\n")

    try:
        answer = asyncio.run(do_recall())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print(Panel(answer, title="Captain's Log", border_style="cyan"))


async def _build_recall_context(db: Any, query: str) -> str:
    """Build context data for the recall query.

    Fetches relevant activity data based on time references in the query.
    """
    from typing import Any

    now = datetime.now()
    query_lower = query.lower()

    # Determine date range from the query
    if "today" in query_lower:
        start = now.replace(hour=0, minute=0, second=0)
        end = now
    elif "yesterday" in query_lower:
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0)
        end = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59)
    elif "last week" in query_lower:
        days_since_monday = now.weekday()
        start = (now - timedelta(days=days_since_monday + 7)).replace(hour=0, minute=0, second=0)
        end = (now - timedelta(days=days_since_monday)).replace(hour=23, minute=59, second=59)
    elif "this week" in query_lower:
        days_since_monday = now.weekday()
        start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0)
        end = now
    elif "this month" in query_lower:
        start = now.replace(day=1, hour=0, minute=0, second=0)
        end = now
    elif any(day in query_lower for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
        # Find the most recent occurrence of the named day
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day_name in enumerate(day_names):
            if day_name in query_lower:
                target_weekday = i
                break
        days_back = (now.weekday() - target_weekday) % 7
        if days_back == 0 and "last" in query_lower:
            days_back = 7
        elif days_back == 0:
            days_back = 0  # today
        target = now - timedelta(days=days_back)
        start = target.replace(hour=0, minute=0, second=0)
        end = target.replace(hour=23, minute=59, second=59)
    else:
        # Default: last 7 days
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0)
        end = now

    # Fetch activity data
    rows = await db.fetch_all(
        """
        SELECT app_name, timestamp, window_title, idle_status
        FROM activity_logs
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp ASC
        """,
        (start.isoformat(), end.isoformat()),
    )

    if not rows:
        return f"No activity data found for the period {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}."

    # Build per-day app usage summary (compact for Claude)
    days: dict[str, dict[str, float]] = {}
    for i in range(len(rows)):
        row = rows[i]
        day = row["timestamp"][:10]
        app = row["app_name"]

        if day not in days:
            days[day] = {}

        if i < len(rows) - 1:
            t1 = datetime.fromisoformat(row["timestamp"])
            t2 = datetime.fromisoformat(rows[i + 1]["timestamp"])
            dur = min((t2 - t1).total_seconds() / 60.0, 30.0)
            days[day][app] = days[day].get(app, 0) + dur

    # Format as compact text
    context_parts = [f"Period: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"]
    for day, apps in sorted(days.items()):
        total = sum(apps.values())
        h, m = int(total // 60), int(total % 60)
        context_parts.append(f"\n{day} ({h}h {m}m total):")
        sorted_apps = sorted(apps.items(), key=lambda x: x[1], reverse=True)
        for app_name, mins in sorted_apps[:10]:
            context_parts.append(f"  {app_name}: {int(mins)}m")

    # Also fetch AI summaries for richer context
    summaries = await db.fetch_all(
        """
        SELECT period_start, context, activity_type
        FROM summaries
        WHERE period_start BETWEEN ? AND ?
        ORDER BY period_start ASC
        """,
        (start.isoformat(), end.isoformat()),
    )

    if summaries:
        context_parts.append("\nAI Summaries:")
        for s in summaries[:20]:  # Limit to avoid token overflow
            if s["context"]:
                time_str = s["period_start"][11:16] if len(s["period_start"]) > 11 else ""
                day_str = s["period_start"][:10]
                context_parts.append(f"  {day_str} {time_str}: {s['context'][:100]}")

    # Focus sessions
    focus_rows = await db.fetch_all(
        """
        SELECT fs.date, fg.name, fs.total_focus_minutes, fs.pomodoro_count
        FROM focus_sessions fs
        JOIN focus_goals fg ON fs.goal_id = fg.id
        WHERE fs.date BETWEEN ? AND ?
        ORDER BY fs.date
        """,
        (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")),
    )

    if focus_rows:
        context_parts.append("\nFocus Sessions:")
        for fr in focus_rows:
            context_parts.append(
                f"  {fr['date']}: {fr['name']} — {int(fr['total_focus_minutes'])}m, "
                f"{fr['pomodoro_count']} pomodoros"
            )

    return "\n".join(context_parts)


@app.callback()
def main_callback() -> None:
    """Captain's Log - Personal activity tracking with AI-powered insights."""
    pass


if __name__ == "__main__":
    app()
