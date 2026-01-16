"""Idle detection using CGEventSource for mouse and keyboard activity."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatch

logger = logging.getLogger(__name__)


class IdleStatus(str, Enum):
    """User idle status classification."""

    ACTIVE = "ACTIVE"
    IDLE_BUT_PRESENT = "IDLE_BUT_PRESENT"  # Brief idle, likely thinking
    WATCHING_MEDIA = "WATCHING_MEDIA"  # Long keyboard idle, occasional mouse
    READING = "READING"  # In a reading app with little input
    AWAY = "AWAY"  # Long idle on both inputs
    SLEEP = "SLEEP"  # System sleep
    LOCKED = "LOCKED"  # Screen locked


@dataclass
class IdleState:
    """Current idle state with timing details."""

    total_idle_seconds: float
    mouse_idle_seconds: float
    keyboard_idle_seconds: float
    status: IdleStatus


class IdleDetector:
    """Detects user idle state using CGEventSource.

    Uses CGEventSourceSecondsSinceLastEventType to track how long
    since the last mouse movement and keyboard input.
    """

    # Default thresholds (can be adjusted)
    IDLE_THRESHOLD = 60  # Seconds to consider "idle but present"
    AWAY_THRESHOLD = 300  # 5 minutes to consider "away"
    MEDIA_KEYBOARD_THRESHOLD = 300  # Keyboard idle ok if watching media
    MEDIA_MOUSE_THRESHOLD = 60  # But mouse should occasionally move

    # Apps where long idle is normal
    VIDEO_APPS = [
        "com.apple.QuickTimePlayerX",
        "org.videolan.vlc",
        "com.netflix.*",
        "tv.plex.player",
        "com.amazon.aiv.AIVApp",
        "us.zoom.xos",  # Zoom meetings
        "com.microsoft.teams",
        "com.slack.Slack",  # Slack huddles
    ]

    READING_APPS = [
        "com.apple.Preview",
        "com.apple.Safari",
        "com.google.Chrome",
        "org.mozilla.firefox",
        "com.readdle.PDFExpert*",
        "com.amazon.Kindle",
        "com.apple.iBooksX",
    ]

    def __init__(
        self,
        idle_threshold: int = IDLE_THRESHOLD,
        away_threshold: int = AWAY_THRESHOLD,
    ):
        self.idle_threshold = idle_threshold
        self.away_threshold = away_threshold

    def get_mouse_idle_seconds(self) -> float:
        """Get seconds since last mouse movement."""
        try:
            from Quartz import (
                CGEventSourceSecondsSinceLastEventType,
                kCGEventMouseMoved,
                kCGEventSourceStateCombinedSessionState,
            )

            return CGEventSourceSecondsSinceLastEventType(
                kCGEventSourceStateCombinedSessionState,
                kCGEventMouseMoved,
            )
        except Exception as e:
            logger.debug(f"Error getting mouse idle time: {e}")
            return 0.0

    def get_keyboard_idle_seconds(self) -> float:
        """Get seconds since last keyboard input."""
        try:
            from Quartz import (
                CGEventSourceSecondsSinceLastEventType,
                kCGEventKeyDown,
                kCGEventSourceStateCombinedSessionState,
            )

            return CGEventSourceSecondsSinceLastEventType(
                kCGEventSourceStateCombinedSessionState,
                kCGEventKeyDown,
            )
        except Exception as e:
            logger.debug(f"Error getting keyboard idle time: {e}")
            return 0.0

    def get_any_input_idle_seconds(self) -> float:
        """Get seconds since any user input (mouse or keyboard)."""
        mouse_idle = self.get_mouse_idle_seconds()
        keyboard_idle = self.get_keyboard_idle_seconds()
        return min(mouse_idle, keyboard_idle)

    def get_idle_state(self, active_bundle_id: str | None = None) -> IdleState:
        """Get current idle state with classification.

        Args:
            active_bundle_id: Currently active app's bundle ID for
                             context-aware classification

        Returns:
            IdleState with timing and status classification
        """
        mouse_idle = self.get_mouse_idle_seconds()
        keyboard_idle = self.get_keyboard_idle_seconds()
        total_idle = min(mouse_idle, keyboard_idle)

        status = self._classify(mouse_idle, keyboard_idle, active_bundle_id)

        return IdleState(
            total_idle_seconds=total_idle,
            mouse_idle_seconds=mouse_idle,
            keyboard_idle_seconds=keyboard_idle,
            status=status,
        )

    def _classify(
        self,
        mouse_idle: float,
        keyboard_idle: float,
        bundle_id: str | None = None,
    ) -> IdleStatus:
        """Classify idle status based on input timing and active app.

        Context-aware classification:
        - Video apps: Long keyboard idle is normal
        - Reading apps: Moderate keyboard idle is normal
        - Default: Standard thresholds
        """
        # Check if in a video/meeting app
        if bundle_id and self._matches_patterns(bundle_id, self.VIDEO_APPS):
            # Video: keyboard idle is fine, just check mouse occasionally moves
            if mouse_idle < self.MEDIA_MOUSE_THRESHOLD:
                return IdleStatus.WATCHING_MEDIA
            elif mouse_idle > self.away_threshold:
                return IdleStatus.AWAY
            else:
                return IdleStatus.WATCHING_MEDIA

        # Check if in a reading app
        if bundle_id and self._matches_patterns(bundle_id, self.READING_APPS):
            # Reading: some keyboard idle is normal
            reading_keyboard_threshold = 600  # 10 minutes
            if keyboard_idle < reading_keyboard_threshold and mouse_idle < 120:
                return IdleStatus.READING

        # Default classification
        if keyboard_idle > self.away_threshold and mouse_idle > self.away_threshold:
            return IdleStatus.AWAY

        if keyboard_idle > self.away_threshold and mouse_idle < self.MEDIA_MOUSE_THRESHOLD:
            # Long keyboard idle but mouse moving = likely watching something
            return IdleStatus.WATCHING_MEDIA

        if min(keyboard_idle, mouse_idle) > self.idle_threshold:
            return IdleStatus.IDLE_BUT_PRESENT

        return IdleStatus.ACTIVE

    def _matches_patterns(self, bundle_id: str, patterns: list[str]) -> bool:
        """Check if bundle ID matches any pattern."""
        return any(fnmatch(bundle_id, pattern) for pattern in patterns)

    def is_idle(self) -> bool:
        """Simple check if user is idle."""
        return self.get_any_input_idle_seconds() > self.idle_threshold

    def is_away(self) -> bool:
        """Check if user is away (extended idle)."""
        return self.get_any_input_idle_seconds() > self.away_threshold

    def get_detailed_timings(self) -> dict[str, float]:
        """Get idle time for various event types (for debugging)."""
        try:
            from Quartz import (
                CGEventSourceSecondsSinceLastEventType,
                kCGEventKeyDown,
                kCGEventLeftMouseDown,
                kCGEventMouseMoved,
                kCGEventRightMouseDown,
                kCGEventScrollWheel,
                kCGEventSourceStateCombinedSessionState,
            )

            return {
                "mouse_moved": CGEventSourceSecondsSinceLastEventType(
                    kCGEventSourceStateCombinedSessionState, kCGEventMouseMoved
                ),
                "left_click": CGEventSourceSecondsSinceLastEventType(
                    kCGEventSourceStateCombinedSessionState, kCGEventLeftMouseDown
                ),
                "right_click": CGEventSourceSecondsSinceLastEventType(
                    kCGEventSourceStateCombinedSessionState, kCGEventRightMouseDown
                ),
                "key_down": CGEventSourceSecondsSinceLastEventType(
                    kCGEventSourceStateCombinedSessionState, kCGEventKeyDown
                ),
                "scroll": CGEventSourceSecondsSinceLastEventType(
                    kCGEventSourceStateCombinedSessionState, kCGEventScrollWheel
                ),
            }
        except Exception as e:
            logger.error(f"Error getting detailed timings: {e}")
            return {}
