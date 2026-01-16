"""Input monitoring for keyboard and mouse activity.

Tracks keystroke counts, mouse clicks, and scroll events to measure
engagement intensity without capturing actual keystrokes (for privacy).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import Quartz for event monitoring
try:
    import Quartz
    from Quartz import (
        CFMachPortCreateRunLoopSource,
        CFRunLoopAddSource,
        CFRunLoopGetCurrent,
        CFRunLoopStop,
        CGEventMaskBit,
        CGEventTapCreate,
        CGEventTapEnable,
        kCFRunLoopCommonModes,
        kCGEventKeyDown,
        kCGEventLeftMouseDown,
        kCGEventMouseMoved,
        kCGEventRightMouseDown,
        kCGEventScrollWheel,
        kCGEventTapOptionListenOnly,
        kCGHeadInsertEventTap,
        kCGHIDEventTap,
    )
    QUARTZ_AVAILABLE = True
except ImportError:
    QUARTZ_AVAILABLE = False
    logger.warning("Quartz not available - input monitoring disabled")


@dataclass
class InputStats:
    """Statistics for input activity over a time period."""

    # Time window
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime | None = None

    # Keystroke metrics
    keystrokes: int = 0
    keystrokes_per_minute: float = 0.0

    # Mouse metrics
    left_clicks: int = 0
    right_clicks: int = 0
    total_clicks: int = 0
    clicks_per_minute: float = 0.0

    # Scroll metrics
    scroll_events: int = 0
    scroll_up: int = 0
    scroll_down: int = 0

    # Mouse movement (coarse, not tracking position)
    mouse_moves: int = 0

    # Derived metrics
    engagement_score: float = 0.0  # 0-100 based on input intensity

    def calculate_rates(self) -> None:
        """Calculate per-minute rates based on period duration."""
        if self.period_end is None:
            self.period_end = datetime.utcnow()

        duration_minutes = (self.period_end - self.period_start).total_seconds() / 60
        if duration_minutes > 0:
            self.keystrokes_per_minute = self.keystrokes / duration_minutes
            self.clicks_per_minute = self.total_clicks / duration_minutes

            # Calculate engagement score (0-100)
            # Based on typical active typing: 40-80 WPM = 200-400 keystrokes/min
            # Active clicking: 5-20 clicks/min
            keystroke_score = min(100, (self.keystrokes_per_minute / 300) * 100)
            click_score = min(100, (self.clicks_per_minute / 15) * 100)
            scroll_score = min(50, (self.scroll_events / duration_minutes / 10) * 50)

            # Weighted combination
            self.engagement_score = (
                keystroke_score * 0.5 +
                click_score * 0.3 +
                scroll_score * 0.2
            )

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        self.calculate_rates()
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "keystrokes": self.keystrokes,
            "keystrokes_per_minute": round(self.keystrokes_per_minute, 1),
            "left_clicks": self.left_clicks,
            "right_clicks": self.right_clicks,
            "total_clicks": self.total_clicks,
            "clicks_per_minute": round(self.clicks_per_minute, 1),
            "scroll_events": self.scroll_events,
            "scroll_up": self.scroll_up,
            "scroll_down": self.scroll_down,
            "mouse_moves": self.mouse_moves,
            "engagement_score": round(self.engagement_score, 1),
        }


class InputMonitor:
    """Monitor keyboard and mouse input for engagement tracking.

    This tracks input counts and patterns WITHOUT capturing actual
    keystrokes or mouse positions for privacy.
    """

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._run_loop = None
        self._tap = None

        # Current stats being accumulated
        self._current_stats = InputStats()
        self._stats_lock = threading.Lock()

        # Callback for periodic stats
        self._on_stats_callback: Callable[[InputStats], None] | None = None
        self._stats_interval = 60  # Report stats every 60 seconds
        self._last_stats_time = time.time()

    @property
    def is_available(self) -> bool:
        """Check if input monitoring is available."""
        return QUARTZ_AVAILABLE

    @property
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running

    def start(self, on_stats: Callable[[InputStats], None] | None = None) -> bool:
        """Start monitoring input events.

        Args:
            on_stats: Optional callback called periodically with stats

        Returns:
            True if started successfully
        """
        if not QUARTZ_AVAILABLE:
            logger.warning("Cannot start input monitor - Quartz not available")
            return False

        if self._running:
            logger.warning("Input monitor already running")
            return True

        self._on_stats_callback = on_stats
        self._current_stats = InputStats()
        self._last_stats_time = time.time()

        # Start monitoring in background thread
        self._running = True
        self._thread = threading.Thread(target=self._run_monitor, daemon=True)
        self._thread.start()

        logger.info("Input monitor started")
        return True

    def stop(self) -> None:
        """Stop monitoring input events."""
        if not self._running:
            return

        self._running = False

        # Stop the run loop
        if self._run_loop:
            try:
                CFRunLoopStop(self._run_loop)
            except Exception as e:
                logger.debug(f"Error stopping run loop: {e}")

        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self._thread = None
        self._tap = None
        self._run_loop = None

        logger.info("Input monitor stopped")

    def get_current_stats(self) -> InputStats:
        """Get current accumulated stats and reset."""
        with self._stats_lock:
            stats = self._current_stats
            stats.period_end = datetime.utcnow()
            stats.calculate_rates()

            # Start new period
            self._current_stats = InputStats()

            return stats

    def _run_monitor(self) -> None:
        """Run the event tap in a background thread."""
        try:
            # Create event mask for events we want to monitor
            event_mask = (
                CGEventMaskBit(kCGEventKeyDown) |
                CGEventMaskBit(kCGEventLeftMouseDown) |
                CGEventMaskBit(kCGEventRightMouseDown) |
                CGEventMaskBit(kCGEventScrollWheel) |
                CGEventMaskBit(kCGEventMouseMoved)
            )

            # Create the event tap
            # kCGEventTapOptionListenOnly = we only observe, don't modify events
            self._tap = CGEventTapCreate(
                kCGHIDEventTap,
                kCGHeadInsertEventTap,
                kCGEventTapOptionListenOnly,
                event_mask,
                self._event_callback,
                None
            )

            if self._tap is None:
                logger.error(
                    "Failed to create event tap. "
                    "Accessibility permission may be required."
                )
                self._running = False
                return

            # Create run loop source
            run_loop_source = CFMachPortCreateRunLoopSource(None, self._tap, 0)

            # Get current run loop and add source
            self._run_loop = CFRunLoopGetCurrent()
            CFRunLoopAddSource(self._run_loop, run_loop_source, kCFRunLoopCommonModes)

            # Enable the tap
            CGEventTapEnable(self._tap, True)

            logger.debug("Event tap created and enabled")

            # Run the loop (blocks until stopped)
            while self._running:
                # Run loop for short intervals to check if we should stop
                Quartz.CFRunLoopRunInMode(
                    Quartz.kCFRunLoopDefaultMode,
                    0.5,  # Run for 0.5 seconds
                    False
                )

                # Check if we should report stats
                self._check_stats_interval()

        except Exception as e:
            logger.error(f"Error in input monitor: {e}")
            self._running = False

    def _event_callback(self, proxy, event_type, event, refcon):
        """Callback for each input event.

        This is called from the event tap for each monitored event.
        We only count events, never capture actual content.
        """
        try:
            with self._stats_lock:
                if event_type == kCGEventKeyDown:
                    self._current_stats.keystrokes += 1

                elif event_type == kCGEventLeftMouseDown:
                    self._current_stats.left_clicks += 1
                    self._current_stats.total_clicks += 1

                elif event_type == kCGEventRightMouseDown:
                    self._current_stats.right_clicks += 1
                    self._current_stats.total_clicks += 1

                elif event_type == kCGEventScrollWheel:
                    self._current_stats.scroll_events += 1
                    # Get scroll direction (positive = up, negative = down)
                    try:
                        delta = Quartz.CGEventGetIntegerValueField(
                            event,
                            Quartz.kCGScrollWheelEventDeltaAxis1
                        )
                        if delta > 0:
                            self._current_stats.scroll_up += 1
                        elif delta < 0:
                            self._current_stats.scroll_down += 1
                    except Exception:
                        pass

                elif event_type == kCGEventMouseMoved:
                    self._current_stats.mouse_moves += 1

        except Exception as e:
            logger.debug(f"Error in event callback: {e}")

        # Return the event unchanged (we're just observing)
        return event

    def _check_stats_interval(self) -> None:
        """Check if we should report stats."""
        now = time.time()
        if now - self._last_stats_time >= self._stats_interval:
            self._last_stats_time = now

            if self._on_stats_callback:
                stats = self.get_current_stats()
                try:
                    self._on_stats_callback(stats)
                except Exception as e:
                    logger.error(f"Error in stats callback: {e}")


# Singleton instance
_input_monitor: InputMonitor | None = None


def get_input_monitor() -> InputMonitor:
    """Get the global input monitor instance."""
    global _input_monitor
    if _input_monitor is None:
        _input_monitor = InputMonitor()
    return _input_monitor
