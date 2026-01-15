"""Event-based application monitoring using NSWorkspace notifications."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from AppKit import NSRunningApplication

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
    """Event-based application monitor using NSWorkspace notifications.

    This is much more efficient than polling - it only fires when
    the active application actually changes.
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
        """
        if self._running:
            logger.warning("AppMonitor already running")
            return

        self._callback = callback
        self._running = True

        try:
            import objc
            from AppKit import NSWorkspace
            from Foundation import NSNotificationCenter

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

            logger.info("AppMonitor started (event-based)")
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
