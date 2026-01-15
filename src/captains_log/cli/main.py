"""CLI commands for Captain's Log using Typer."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from captains_log import __version__
from captains_log.core.config import Config, get_config
from captains_log.core.orchestrator import Orchestrator, get_orchestrator, run_daemon

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
        handlers.append(logging.FileHandler(log_file))

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

    # Check if already running
    if Orchestrator.is_daemon_running(config):
        pid = Orchestrator.get_daemon_pid(config)
        console.print(f"[yellow]Daemon already running (PID: {pid})[/yellow]")
        raise typer.Exit(1)

    # Setup logging
    log_file = config.log_dir / "daemon.log" if not foreground else None
    setup_logging(log_level, log_file)

    if foreground:
        console.print("[green]Starting Captain's Log in foreground...[/green]")
        console.print("Press Ctrl+C to stop\n")

        try:
            asyncio.run(run_daemon())
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped[/yellow]")
    else:
        # Fork to background
        console.print("[green]Starting Captain's Log daemon...[/green]")

        # Double fork to daemonize
        pid = os.fork()
        if pid > 0:
            # Parent process - wait a moment then check if started
            import time
            time.sleep(1)

            if Orchestrator.is_daemon_running(config):
                daemon_pid = Orchestrator.get_daemon_pid(config)
                console.print(f"[green]Daemon started (PID: {daemon_pid})[/green]")
                console.print(f"Logs: {config.log_dir / 'daemon.log'}")
            else:
                console.print("[red]Failed to start daemon - check logs[/red]")
                raise typer.Exit(1)
            return

        # Child process - become session leader
        os.setsid()

        # Second fork
        pid = os.fork()
        if pid > 0:
            sys.exit(0)

        # Grandchild - actual daemon
        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()

        with open("/dev/null", "r") as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())

        log_path = config.log_dir / "daemon.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "a") as log:
            os.dup2(log.fileno(), sys.stdout.fileno())
            os.dup2(log.fileno(), sys.stderr.fileno())

        # Change working directory
        os.chdir("/")

        # Run daemon
        asyncio.run(run_daemon())


@app.command()
def stop() -> None:
    """Stop the Captain's Log daemon."""
    config = get_config()

    pid = Orchestrator.get_daemon_pid(config)
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
            if not Orchestrator.is_daemon_running(config):
                console.print("[green]Daemon stopped[/green]")
                return

        # Force kill if still running
        console.print("[yellow]Daemon not responding, forcing shutdown...[/yellow]")
        os.kill(pid, signal.SIGKILL)
        time.sleep(1)

        if Orchestrator.is_daemon_running(config):
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

    pid = Orchestrator.get_daemon_pid(config)

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

    pid = Orchestrator.get_daemon_pid(config)
    if pid is None:
        console.print("[red]Daemon is not running[/red]")
        console.print("Use 'captains-log start' to begin tracking.")
        raise typer.Exit(1)

    console.print("[yellow]Gathering health information...[/yellow]\n")

    # We need to query the database directly since the daemon is in a separate process
    async def get_health_info():
        from captains_log.storage.database import Database
        from captains_log.core.permissions import PermissionManager

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

    console.print(f"[green]Starting Captain's Log Dashboard...[/green]")
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
    from captains_log.cli.install import install as do_install, is_installed, is_loaded

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
    from captains_log.cli.install import uninstall as do_uninstall, is_installed

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


@app.callback()
def main_callback() -> None:
    """Captain's Log - Personal activity tracking with AI-powered insights."""
    pass


if __name__ == "__main__":
    app()
