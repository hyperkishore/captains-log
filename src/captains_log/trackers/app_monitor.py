"""Event-based application monitoring using NSWorkspace notifications."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class AppInfo:
    """Information about an active application."""

    bundle_id: str
    app_name: str
    pid: int
    timestamp: datetime
    is_active: bool = True


class AppMonitor:
    """Application monitor using NSWorkspace notifications with polling fallback.

    Prefers event-based tracking via NSWorkspace notifications, but falls back
    to polling if events aren't being received (e.g., in launchd contexts).
    """

    def __init__(self):
        self._callback: Callable[[AppInfo], None] | None = None
        self._observer = None
        self._running = False
        self._last_app: AppInfo | None = None
        self._debounce_timer: threading.Timer | None = None
        self._debounce_ms = 500  # Ignore app focus < 500ms
        self._pending_app: AppInfo | None = None
        self._lock = threading.Lock()

        # Polling fallback
        self._polling_timer: threading.Timer | None = None
        self._polling_interval = 2.0  # Check every 2 seconds
        self._events_received = False  # Track if we get any events
        self._use_polling = False  # Fall back to polling if events fail

    def set_debounce(self, ms: int) -> None:
        """Set debounce time in milliseconds."""
        self._debounce_ms = ms

    def get_current_app(self) -> AppInfo | None:
        """Get the currently active application."""
        try:
            from AppKit import NSWorkspace

            workspace = NSWorkspace.sharedWorkspace()
            active = workspace.frontmostApplication()

            if active is None:
                return None

            return AppInfo(
                bundle_id=active.bundleIdentifier() or "unknown",
                app_name=active.localizedName() or "Unknown",
                pid=active.processIdentifier(),
                timestamp=datetime.utcnow(),
            )
        except Exception as e:
            logger.error(f"Error getting current app: {e}")
            return None

    def start(self, callback: Callable[[AppInfo], None]) -> None:
        """Start monitoring with a callback for app changes.

        The callback will be called whenever the active application changes.
        Uses NSWorkspace notifications with polling fallback.
        """
        if self._running:
            logger.warning("AppMonitor already running")
            return

        self._callback = callback
        self._running = True
        self._events_received = False

        try:
            from AppKit import NSWorkspace

            workspace = NSWorkspace.sharedWorkspace()
            nc = workspace.notificationCenter()

            # Register for app activation events
            self._observer = nc.addObserverForName_object_queue_usingBlock_(
                "NSWorkspaceDidActivateApplicationNotification",
                None,
                None,
                self._on_app_activated,
            )

            # Fire callback for current app
            current = self.get_current_app()
            if current:
                self._last_app = current
                if self._callback:
                    self._callback(current)

            # Start polling fallback timer - will check if events are received
            # and switch to polling mode if they're not
            self._start_polling_fallback()

            logger.info("AppMonitor started (event-based with polling fallback)")
        except Exception as e:
            logger.error(f"Failed to start AppMonitor: {e}")
            self._running = False
            raise

    def stop(self) -> None:
        """Stop monitoring."""
        if not self._running:
            return

        self._running = False

        # Cancel pending debounce timer
        with self._lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
                self._debounce_timer = None

            # Cancel polling timer
            if self._polling_timer:
                self._polling_timer.cancel()
                self._polling_timer = None

        # Remove observer
        if self._observer:
            try:
                from AppKit import NSWorkspace

                workspace = NSWorkspace.sharedWorkspace()
                nc = workspace.notificationCenter()
                nc.removeObserver_(self._observer)
            except Exception as e:
                logger.error(f"Error removing observer: {e}")

            self._observer = None

        logger.info("AppMonitor stopped")

    def _on_app_activated(self, notification) -> None:
        """Handle app activation notification."""
        if not self._running:
            return

        # Mark that we're receiving events - disable polling fallback
        if not self._events_received:
            self._events_received = True
            logger.info("NSWorkspace events are being received, disabling polling fallback")

        try:
            active_app = notification.userInfo()["NSWorkspaceApplicationKey"]

            app_info = AppInfo(
                bundle_id=active_app.bundleIdentifier() or "unknown",
                app_name=active_app.localizedName() or "Unknown",
                pid=active_app.processIdentifier(),
                timestamp=datetime.utcnow(),
            )

            # Debounce: Don't fire for very brief app focuses (e.g., CMD+TAB scrolling)
            self._schedule_emit(app_info)

        except Exception as e:
            logger.error(f"Error handling app activation: {e}")

    def _schedule_emit(self, app_info: AppInfo) -> None:
        """Schedule emitting an app change event with debouncing."""
        with self._lock:
            # Cancel pending timer
            if self._debounce_timer:
                self._debounce_timer.cancel()

            self._pending_app = app_info

            # Schedule new emit
            self._debounce_timer = threading.Timer(
                self._debounce_ms / 1000.0,
                self._emit_if_still_active,
            )
            self._debounce_timer.start()

    def _emit_if_still_active(self) -> None:
        """Emit the app change if the pending app is still active."""
        with self._lock:
            if not self._running or not self._pending_app:
                return

            pending = self._pending_app
            self._pending_app = None
            self._debounce_timer = None

        # Verify the app is still active
        current = self.get_current_app()
        if current and current.bundle_id == pending.bundle_id:
            # Don't emit if same as last app
            if self._last_app and self._last_app.bundle_id == pending.bundle_id:
                return

            self._last_app = pending
            if self._callback:
                self._callback(pending)
                logger.debug(f"App changed: {pending.app_name} ({pending.bundle_id})")

    @property
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running

    @property
    def last_app(self) -> AppInfo | None:
        """Get the last detected application."""
        return self._last_app

    def _start_polling_fallback(self) -> None:
        """Start polling fallback check.

        After 10 seconds, if no events have been received, switch to polling mode.
        """
        def check_and_maybe_poll():
            if not self._running:
                return

            if not self._events_received:
                # No events received after 10 seconds - enable polling
                logger.warning(
                    "No NSWorkspace events received after 10s - enabling polling fallback"
                )
                self._use_polling = True
                self._schedule_poll()
            else:
                logger.debug("NSWorkspace events working, no polling needed")

        # Check after 10 seconds
        self._polling_timer = threading.Timer(10.0, check_and_maybe_poll)
        self._polling_timer.start()

    def _schedule_poll(self) -> None:
        """Schedule the next poll."""
        if not self._running or not self._use_polling:
            return

        with self._lock:
            if self._polling_timer:
                self._polling_timer.cancel()

            self._polling_timer = threading.Timer(
                self._polling_interval,
                self._do_poll,
            )
            self._polling_timer.start()

    def _do_poll(self) -> None:
        """Poll for current app and emit if changed."""
        if not self._running:
            return

        try:
            current = self.get_current_app()
            if current:
                # Check if app changed
                if self._last_app is None or self._last_app.bundle_id != current.bundle_id:
                    logger.debug(f"Poll detected app change: {current.app_name}")
                    self._last_app = current
                    if self._callback:
                        self._callback(current)

        except Exception as e:
            logger.error(f"Error during poll: {e}")

        # Schedule next poll
        self._schedule_poll()
