"""Main daemon orchestrator coordinating all tracking components."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from typing import TYPE_CHECKING

from captains_log.ai.batch_processor import BatchProcessor
from captains_log.core.config import Config, get_config
from captains_log.optimization.optimization_engine import OptimizationEngine
from captains_log.sync.cloud_sync import CloudSync
from captains_log.core.permissions import PermissionManager
from captains_log.storage.database import Database, init_database
from captains_log.storage.screenshot_manager import ScreenshotManager
from captains_log.summarizers.five_minute import FiveMinuteSummarizer
from captains_log.summarizers.focus_calculator import FocusCalculator
from captains_log.trackers.app_monitor import AppInfo, AppMonitor
from captains_log.trackers.buffer import ActivityBuffer, ActivityEvent
from captains_log.trackers.idle_detector import IdleDetector
from captains_log.trackers.input_monitor import InputMonitor, InputStats
from captains_log.trackers.screenshot_capture import ScreenshotCapture, ScreenshotInfo
from captains_log.trackers.window_tracker import WindowTracker
from captains_log.trackers.work_context import WorkContext, WorkContextExtractor

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
        self.work_context_extractor: WorkContextExtractor | None = None
        self.input_monitor: InputMonitor | None = None
        self.screenshot_capture: ScreenshotCapture | None = None
        self.screenshot_manager: ScreenshotManager | None = None

        # AI summarization components
        self.batch_processor: BatchProcessor | None = None
        self.summarizer: FiveMinuteSummarizer | None = None
        self.focus_calculator: FocusCalculator | None = None

        # Time optimization engine
        self.optimization_engine: OptimizationEngine | None = None

        # Cloud sync
        self.cloud_sync: CloudSync | None = None

        # Current input stats (accumulated between app switches)
        self._current_input_stats: InputStats | None = None

        # Background tasks
        self._tasks: list[asyncio.Task] = []

        # Queue for pending screenshot saves (for app-change captures)
        self._pending_screenshots: list[ScreenshotInfo] = []
        self._last_app_change_screenshot: datetime | None = None
        self._min_screenshot_interval = 5.0  # Minimum 5 seconds between app-change screenshots

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
            # Detect if we're running in daemon mode (stdout not a terminal)
            daemon_mode = not sys.stdout.isatty()
            self.permissions = PermissionManager(daemon_mode=daemon_mode)
            if not self.permissions.has_accessibility:
                logger.warning("Accessibility permission not granted - window titles unavailable")
            if not self.permissions.has_screen_recording:
                logger.info("Screen Recording permission not granted - screenshots will be unavailable")

            # Initialize trackers
            self.idle_detector = IdleDetector(
                idle_threshold=self.config.tracking.idle_threshold_seconds,
            )

            self.window_tracker = WindowTracker(daemon_mode=daemon_mode)
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

            # Initialize work context extractor
            self.work_context_extractor = WorkContextExtractor()

            # Initialize input monitor (keyboard/mouse tracking)
            # This is optional - daemon continues without it if it fails
            try:
                self.input_monitor = InputMonitor()
                if self.input_monitor.is_available:
                    started = self.input_monitor.start(self._on_input_stats)
                    if started:
                        logger.info("Input monitoring started (keyboard/mouse tracking enabled)")
                    else:
                        logger.warning("Input monitor failed to start - engagement metrics disabled")
                        self.input_monitor = None
                else:
                    logger.warning("Input monitoring unavailable - engagement metrics disabled")
                    self.input_monitor = None
            except Exception as e:
                logger.warning(f"Failed to initialize input monitor: {e} - engagement metrics disabled")
                self.input_monitor = None

            # Initialize screenshot capture (optional - daemon continues without it)
            if self.config.screenshots.enabled:
                if self.permissions.has_screen_recording:
                    try:
                        # Initialize screenshot manager
                        self.screenshot_manager = ScreenshotManager(
                            db=self.db,
                            screenshots_dir=self.config.screenshots_dir,
                        )

                        # Initialize screenshot capture
                        self.screenshot_capture = ScreenshotCapture(
                            screenshots_dir=self.config.screenshots_dir,
                            interval_minutes=self.config.screenshots.interval_minutes,
                            quality=self.config.screenshots.quality,
                            max_width=self.config.screenshots.max_width,
                            retention_days=self.config.screenshots.retention_days,
                            excluded_apps=self.config.screenshots.excluded_apps,
                        )

                        # Wire up current app callback for filtering excluded apps
                        self.screenshot_capture.set_current_app_callback(
                            lambda: self.app_monitor.last_app.bundle_id
                            if self.app_monitor and self.app_monitor.last_app
                            else None
                        )

                        # Start screenshot capture with database save callback
                        started = await self.screenshot_capture.start(
                            on_capture=self._on_screenshot_captured
                        )

                        if started:
                            logger.info(
                                f"Screenshot capture started (every {self.config.screenshots.interval_minutes} min)"
                            )
                        else:
                            logger.warning("Screenshot capture failed to start")
                            self.screenshot_capture = None
                            self.screenshot_manager = None

                    except Exception as e:
                        logger.warning(f"Failed to initialize screenshot capture: {e}")
                        self.screenshot_capture = None
                        self.screenshot_manager = None
                else:
                    logger.info(
                        "Screenshot capture disabled - Screen Recording permission not granted"
                    )

            # Start components
            await self.buffer.start()
            self.app_monitor.start(self._on_app_change)

            self._running = True
            self._startup_time = datetime.utcnow()

            # Setup signal handlers
            self._setup_signal_handlers()

            # Start periodic cleanup task for screenshots
            if self.screenshot_manager:
                cleanup_task = asyncio.create_task(self._periodic_screenshot_cleanup())
                self._tasks.append(cleanup_task)
                logger.info("Screenshot cleanup task started (runs every hour)")

                # Start task to process pending screenshots from app changes
                pending_task = asyncio.create_task(self._process_pending_screenshots())
                self._tasks.append(pending_task)
                logger.info("Screenshot save task started")

            # Initialize AI summarization (optional - daemon continues without it)
            if self.config.summarization.enabled:
                try:
                    # Check for API key
                    api_key = self.config.claude_api_key or os.environ.get("ANTHROPIC_API_KEY")
                    if api_key:
                        # Initialize focus calculator
                        self.focus_calculator = FocusCalculator()

                        # Initialize batch processor
                        self.batch_processor = BatchProcessor(
                            db=self.db,
                            use_batch_api=self.config.summarization.use_batch_api,
                            batch_interval_hours=self.config.summarization.batch_interval_hours,
                        )
                        await self.batch_processor.start()

                        # Initialize 5-minute summarizer
                        self.summarizer = FiveMinuteSummarizer(
                            db=self.db,
                            batch_processor=self.batch_processor,
                            focus_calculator=self.focus_calculator,
                            interval_minutes=5,
                            screenshots_dir=self.config.screenshots_dir,
                        )
                        await self.summarizer.start()

                        mode = "batch" if self.config.summarization.use_batch_api else "realtime"
                        logger.info(f"AI summarization started ({mode} mode)")
                    else:
                        logger.warning(
                            "AI summarization disabled - no API key configured. "
                            "Set ANTHROPIC_API_KEY or CAPTAINS_LOG_CLAUDE_API_KEY"
                        )
                except Exception as e:
                    logger.warning(f"Failed to initialize AI summarization: {e}")
                    self.batch_processor = None
                    self.summarizer = None

            # Initialize cloud sync (optional)
            if self.config.sync.enabled:
                try:
                    self.cloud_sync = CloudSync(self.config)
                    await self.cloud_sync.start()
                    logger.info(f"Cloud sync started (device: {self.config.device_id[:8]}...)")
                except Exception as e:
                    logger.warning(f"Failed to initialize cloud sync: {e}")
                    self.cloud_sync = None

            # Initialize time optimization engine (optional)
            if self.config.optimization.enabled:
                try:
                    self.optimization_engine = OptimizationEngine(
                        db=self.db,
                        config=self.config.optimization,
                        data_dir=self.config.data_dir,
                    )
                    await self.optimization_engine.start()
                    logger.info(
                        f"Time optimization started (goal: {self.config.optimization.target_savings_percent}% savings)"
                    )
                except Exception as e:
                    logger.warning(f"Failed to initialize optimization engine: {e}")
                    self.optimization_engine = None

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

        # Stop optimization engine
        if self.optimization_engine:
            await self.optimization_engine.stop()
            self.optimization_engine = None

        # Stop cloud sync
        if self.cloud_sync:
            await self.cloud_sync.stop()
            self.cloud_sync = None

        # Stop AI summarization
        if self.summarizer:
            await self.summarizer.stop()
            self.summarizer = None

        if self.batch_processor:
            await self.batch_processor.stop()
            self.batch_processor = None

        self.focus_calculator = None

        # Stop screenshot capture
        if self.screenshot_capture:
            await self.screenshot_capture.stop()
            self.screenshot_capture = None
            self.screenshot_manager = None

        # Stop input monitor
        if self.input_monitor:
            self.input_monitor.stop()
            self.input_monitor = None

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

                # Extract URL for browsers (use AppleScript for Chrome/Arc, Accessibility for Safari)
                url = self.window_tracker.get_browser_url(app_info.bundle_id, app_info.pid)

                # Fallback to title parsing if AppleScript fails
                if url is None:
                    url = self.window_tracker.extract_url_from_title(
                        app_info.bundle_id, window_title
                    )

                # Check fullscreen
                is_fullscreen = self.window_tracker.is_fullscreen(app_info.pid)

            # Get idle state
            idle_state = None
            if self.idle_detector:
                idle_state = self.idle_detector.get_idle_state(app_info.bundle_id)

            # Extract work context from URL and window title
            work_context: WorkContext | None = None
            if self.work_context_extractor:
                work_context = self.work_context_extractor.extract(
                    url=url,
                    window_title=window_title,
                    app_name=app_info.app_name
                )

            # Get input stats (accumulated since last app change)
            input_stats = self._get_and_reset_input_stats()

            # Create event with work context and input stats
            event = ActivityEvent(
                timestamp=app_info.timestamp,
                app_name=app_info.app_name,
                bundle_id=app_info.bundle_id,
                window_title=window_title,
                url=url,
                idle_seconds=idle_state.total_idle_seconds if idle_state else 0.0,
                idle_status=idle_state.status.value if idle_state else "ACTIVE",
                is_fullscreen=is_fullscreen,
                # Work context
                work_category=work_context.category if work_context else None,
                work_service=work_context.service if work_context else None,
                work_project=work_context.project if work_context else None,
                work_document=work_context.document if work_context else None,
                work_meeting=work_context.meeting if work_context else None,
                work_channel=work_context.channel if work_context else None,
                work_issue_id=work_context.issue_id if work_context else None,
                work_organization=work_context.organization if work_context else None,
                # Input stats
                keystrokes=input_stats.keystrokes if input_stats else 0,
                mouse_clicks=input_stats.total_clicks if input_stats else 0,
                scroll_events=input_stats.scroll_events if input_stats else 0,
                engagement_score=input_stats.engagement_score if input_stats else 0.0,
            )

            # Add to buffer
            self.buffer.add(event)

            # Feed to optimization engine for interrupt/context switch analysis
            if self.optimization_engine:
                try:
                    asyncio.create_task(
                        self.optimization_engine.on_activity(
                            timestamp=app_info.timestamp,
                            app_name=app_info.app_name,
                            bundle_id=app_info.bundle_id,
                            window_title=window_title,
                            work_category=work_context.category if work_context else None,
                        )
                    )
                except Exception as e:
                    logger.debug(f"Optimization tracking error: {e}")

            # Log with work context info
            context_info = ""
            if work_context and work_context.summary:
                context_info = f" [{work_context.summary}]"

            engagement_info = ""
            if input_stats and input_stats.keystrokes > 0:
                engagement_info = f" (keys: {input_stats.keystrokes}, clicks: {input_stats.total_clicks})"

            logger.debug(
                f"Captured: {app_info.app_name} - {window_title or 'no title'}"
                f"{context_info}{engagement_info} (idle: {event.idle_status})"
            )

            # Capture screenshot on app change if enabled
            if (
                self.config.screenshots.capture_on_app_change
                and self.screenshot_capture
                and self.screenshot_capture.is_running
            ):
                # Debounce: skip if we took a screenshot too recently
                now = datetime.utcnow()
                should_capture = True
                if self._last_app_change_screenshot:
                    elapsed = (now - self._last_app_change_screenshot).total_seconds()
                    if elapsed < self._min_screenshot_interval:
                        should_capture = False
                        logger.debug(f"Skipping app-change screenshot (debounce: {elapsed:.1f}s)")

                if should_capture:
                    # Capture synchronously (CoreGraphics is sync)
                    try:
                        info = self.screenshot_capture.capture_sync()
                        if info:
                            # Queue for async DB save
                            self._pending_screenshots.append(info)
                            self._last_app_change_screenshot = now
                            logger.debug(f"App-change screenshot queued: {info.file_path.name}")
                    except Exception as e:
                        logger.error(f"App-change screenshot failed: {e}")

        except Exception as e:
            logger.error(f"Error processing app change: {e}")

    def _on_input_stats(self, stats: InputStats) -> None:
        """Callback for periodic input stats updates."""
        # Store the latest stats - they'll be used on the next app change
        self._current_input_stats = stats

    async def _on_screenshot_captured(self, info: ScreenshotInfo) -> None:
        """Handle captured screenshot - save metadata to database."""
        if self.screenshot_manager:
            try:
                await self.screenshot_manager.save_screenshot(info)
                logger.debug(f"Screenshot saved: {info.file_path.name}")
            except Exception as e:
                logger.error(f"Failed to save screenshot metadata: {e}")

    async def _process_pending_screenshots(self) -> None:
        """Periodically save pending screenshots to database."""
        while self._running:
            try:
                await asyncio.sleep(1)  # Check every second

                if not self._running or not self.screenshot_manager:
                    break

                # Process all pending screenshots
                while self._pending_screenshots:
                    info = self._pending_screenshots.pop(0)
                    try:
                        await self.screenshot_manager.save_screenshot(info)
                        logger.debug(f"Saved app-change screenshot: {info.file_path.name}")
                    except Exception as e:
                        logger.error(f"Failed to save screenshot: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing pending screenshots: {e}")

    async def _periodic_screenshot_cleanup(self) -> None:
        """Periodically clean up expired screenshots."""
        cleanup_interval = 3600  # 1 hour

        while self._running:
            try:
                await asyncio.sleep(cleanup_interval)

                if not self._running or not self.screenshot_manager:
                    break

                # Run cleanup
                files_deleted, records_updated = await self.screenshot_manager.cleanup_expired()

                if files_deleted > 0 or records_updated > 0:
                    logger.info(
                        f"Screenshot cleanup: {files_deleted} files deleted, "
                        f"{records_updated} records updated"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in screenshot cleanup: {e}")

    def _get_and_reset_input_stats(self) -> InputStats | None:
        """Get current input stats and reset for next period."""
        if self.input_monitor and self.input_monitor.is_running:
            return self.input_monitor.get_current_stats()
        return self._current_input_stats

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

        if self.input_monitor:
            health["input_monitor"] = {
                "available": self.input_monitor.is_available,
                "is_running": self.input_monitor.is_running,
            }

        health["work_context_extractor"] = {
            "available": self.work_context_extractor is not None,
        }

        # Screenshot capture status
        if self.screenshot_capture:
            health["screenshot_capture"] = {
                "available": self.screenshot_capture.is_available,
                "is_running": self.screenshot_capture.is_running,
                "interval_minutes": self.config.screenshots.interval_minutes,
            }

        # Screenshot storage stats
        if self.screenshot_manager:
            try:
                stats = await self.screenshot_manager.get_storage_stats()
                health["screenshots"] = stats
            except Exception as e:
                health["screenshots"] = {"error": str(e)}

        # AI summarization status
        if self.summarizer:
            try:
                summarizer_stats = await self.summarizer.get_stats()
                health["summarizer"] = summarizer_stats
            except Exception as e:
                health["summarizer"] = {"error": str(e)}

        if self.batch_processor:
            try:
                queue_stats = await self.batch_processor.get_queue_stats()
                health["summary_queue"] = queue_stats
            except Exception as e:
                health["summary_queue"] = {"error": str(e)}

        # Cloud sync status
        if self.cloud_sync:
            health["cloud_sync"] = self.cloud_sync.status

        # Time optimization status
        if self.optimization_engine:
            try:
                summary = await self.optimization_engine.get_daily_summary()
                health["optimization"] = {
                    "enabled": True,
                    "status_color": summary.get("status_color", "unknown"),
                    "interrupts_today": summary.get("interrupts", {}).get("total_interrupts", 0),
                    "deep_work_hours": summary.get("deep_work_hours", 0),
                }
            except Exception as e:
                health["optimization"] = {"enabled": True, "error": str(e)}
        else:
            health["optimization"] = {"enabled": False}

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

        # Run the CFRunLoop to receive NSWorkspace notifications
        # This is required because NSWorkspace notifications are delivered via the RunLoop
        try:
            from Foundation import NSDate, NSRunLoop

            logger.info("Starting CFRunLoop for event processing...")

            # Run the run loop in small increments so we can check if we should stop
            while orchestrator.is_running:
                # Run the RunLoop for a short interval to process pending events
                NSRunLoop.currentRunLoop().runUntilDate_(
                    NSDate.dateWithTimeIntervalSinceNow_(0.5)
                )
                # Give asyncio a chance to run
                await asyncio.sleep(0.1)

        except ImportError:
            logger.warning("PyObjC RunLoop not available, falling back to asyncio only")
            # Fallback: just use asyncio sleep (events won't be received)
            while orchestrator.is_running:
                await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await orchestrator.stop()
