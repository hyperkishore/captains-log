"""Main daemon orchestrator coordinating all tracking components."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from captains_log.core.config import Config, get_config
from captains_log.core.permissions import PermissionManager
from captains_log.storage.database import Database, init_database
from captains_log.trackers.app_monitor import AppInfo, AppMonitor
from captains_log.trackers.buffer import ActivityBuffer, ActivityEvent
from captains_log.trackers.idle_detector import IdleDetector
from captains_log.trackers.window_tracker import WindowTracker

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main daemon coordinator for Captain's Log.

    Manages the lifecycle of all tracking components and coordinates
    data flow from activity capture to database storage.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        self._running = False
        self._startup_time: datetime | None = None

        # Core components (initialized in start())
        self.db: Database | None = None
        self.permissions: PermissionManager | None = None
        self.app_monitor: AppMonitor | None = None
        self.window_tracker: WindowTracker | None = None
        self.idle_detector: IdleDetector | None = None
        self.buffer: ActivityBuffer | None = None

        # Background tasks
        self._tasks: list[asyncio.Task] = []

        # PID file for daemon management
        self._pid_file = self.config.data_dir / "daemon.pid"

    @property
    def is_running(self) -> bool:
        """Check if orchestrator is running."""
        return self._running

    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        if self._startup_time is None:
            return 0.0
        return (datetime.utcnow() - self._startup_time).total_seconds()

    async def start(self) -> None:
        """Start the daemon and all tracking components."""
        if self._running:
            logger.warning("Orchestrator already running")
            return

        logger.info("Starting Captain's Log daemon...")

        try:
            # Ensure directories exist
            self.config.ensure_directories()

            # Write PID file
            self._write_pid_file()

            # Initialize database
            self.db = await init_database(self.config.db_path)

            # Check permissions
            self.permissions = PermissionManager()
            self.permissions.check_and_request_permissions()

            # Initialize trackers
            self.idle_detector = IdleDetector(
                idle_threshold=self.config.tracking.idle_threshold_seconds,
            )

            self.window_tracker = WindowTracker()
            if not self.window_tracker.is_available:
                logger.warning("Window tracking unavailable - titles/URLs won't be captured")

            # Initialize buffer with database
            self.buffer = ActivityBuffer(
                db=self.db,
                flush_interval=self.config.tracking.buffer_flush_seconds,
            )

            # Initialize app monitor
            self.app_monitor = AppMonitor()
            self.app_monitor.set_debounce(self.config.tracking.debounce_ms)

            # Start components
            await self.buffer.start()
            self.app_monitor.start(self._on_app_change)

            self._running = True
            self._startup_time = datetime.utcnow()

            # Setup signal handlers
            self._setup_signal_handlers()

            logger.info("Captain's Log daemon started successfully")

        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the daemon and cleanup all resources."""
        if not self._running and self.db is None:
            return

        logger.info("Stopping Captain's Log daemon...")

        self._running = False

        # Stop app monitor
        if self.app_monitor:
            self.app_monitor.stop()
            self.app_monitor = None

        # Stop buffer (will flush remaining events)
        if self.buffer:
            await self.buffer.stop()
            self.buffer = None

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

        # Close database
        if self.db:
            await self.db.close()
            self.db = None

        # Remove PID file
        self._remove_pid_file()

        logger.info("Captain's Log daemon stopped")

    def _on_app_change(self, app_info: AppInfo) -> None:
        """Handle application change events.

        This is called by AppMonitor when the active application changes.
        """
        if not self._running or self.buffer is None:
            return

        try:
            # Get window title if accessibility is available
            window_title = None
            url = None
            is_fullscreen = False

            if self.window_tracker and self.window_tracker.is_available:
                # Try simple method first (faster)
                window_title = self.window_tracker.get_window_title_simple(app_info.pid)
                if window_title is None:
                    window_title = self.window_tracker.get_window_title(app_info.pid)

                # Extract URL for browsers
                url = self.window_tracker.extract_url_from_title(
                    app_info.bundle_id, window_title
                )

                # Special handling for Safari
                if app_info.bundle_id == "com.apple.Safari" and url is None:
                    url = self.window_tracker.get_safari_url(app_info.pid)

                # Check fullscreen
                is_fullscreen = self.window_tracker.is_fullscreen(app_info.pid)

            # Get idle state
            idle_state = None
            if self.idle_detector:
                idle_state = self.idle_detector.get_idle_state(app_info.bundle_id)

            # Create event
            event = ActivityEvent(
                timestamp=app_info.timestamp,
                app_name=app_info.app_name,
                bundle_id=app_info.bundle_id,
                window_title=window_title,
                url=url,
                idle_seconds=idle_state.total_idle_seconds if idle_state else 0.0,
                idle_status=idle_state.status.value if idle_state else "ACTIVE",
                is_fullscreen=is_fullscreen,
            )

            # Add to buffer
            self.buffer.add(event)

            logger.debug(
                f"Captured: {app_info.app_name} - {window_title or 'no title'} "
                f"(idle: {event.idle_status})"
            )

        except Exception as e:
            logger.error(f"Error processing app change: {e}")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_signal, sig)

    def _handle_signal(self, sig: signal.Signals) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {sig.name}, initiating shutdown...")
        asyncio.create_task(self.stop())

    def _write_pid_file(self) -> None:
        """Write PID file for daemon management."""
        self._pid_file.parent.mkdir(parents=True, exist_ok=True)
        self._pid_file.write_text(str(os.getpid()))
        logger.debug(f"PID file written: {self._pid_file}")

    def _remove_pid_file(self) -> None:
        """Remove PID file."""
        if self._pid_file.exists():
            self._pid_file.unlink()
            logger.debug("PID file removed")

    @classmethod
    def get_daemon_pid(cls, config: Config | None = None) -> int | None:
        """Get the PID of a running daemon from PID file."""
        config = config or get_config()
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

    @classmethod
    def is_daemon_running(cls, config: Config | None = None) -> bool:
        """Check if daemon is currently running."""
        return cls.get_daemon_pid(config) is not None

    async def get_health(self) -> dict:
        """Get health status of all components."""
        health = {
            "status": "running" if self._running else "stopped",
            "uptime_seconds": self.uptime_seconds,
            "pid": os.getpid(),
        }

        if self.db:
            try:
                health["database"] = {
                    "connected": True,
                    "size_mb": await self.db.get_size_mb(),
                    "integrity_ok": await self.db.check_integrity(),
                }
            except Exception as e:
                health["database"] = {"connected": False, "error": str(e)}

        if self.buffer:
            health["buffer"] = {
                "pending_events": self.buffer.pending_count,
                "is_running": self.buffer.is_running,
            }

        if self.permissions:
            health["permissions"] = {
                "accessibility": self.permissions.has_accessibility,
                "screen_recording": self.permissions.has_screen_recording,
            }

        if self.app_monitor:
            health["app_monitor"] = {
                "is_running": self.app_monitor.is_running,
                "last_app": self.app_monitor.last_app.app_name if self.app_monitor.last_app else None,
            }

        if self.window_tracker:
            health["window_tracker"] = {
                "available": self.window_tracker.is_available,
            }

        return health


# Global orchestrator instance
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


async def run_daemon() -> None:
    """Run the daemon until stopped."""
    orchestrator = get_orchestrator()

    try:
        await orchestrator.start()

        # Keep running until stopped
        while orchestrator.is_running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await orchestrator.stop()
