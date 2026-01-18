"""Interrupt detection and tracking.

Detects when users do quick checks on communication apps (Slack, email, etc.)
and tracks the frequency and cost of these interruptions.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from captains_log.optimization.schemas import (
    InterruptEvent,
    InterruptType,
)

logger = logging.getLogger(__name__)


# Apps considered as communication/interrupt sources
COMMUNICATION_APPS = {
    "Slack",
    "Discord",
    "Mail",
    "Microsoft Outlook",
    "Spark",
    "Airmail",
    "Messages",
    "WhatsApp",
    "Telegram",
    "Signal",
    "Microsoft Teams",
    "Zoom",
    "Google Meet",
    "FaceTime",
    "Skype",
}

# Bundle IDs for communication apps
COMMUNICATION_BUNDLE_IDS = {
    "com.tinyspeck.slackmacgap",
    "com.hnc.Discord",
    "com.apple.mail",
    "com.microsoft.Outlook",
    "com.readdle.smartemail-Mac",
    "it.bloop.airmail2",
    "com.apple.MobileSMS",
    "net.whatsapp.WhatsApp",
    "org.telegram.Telegram-Swift",
    "org.whispersystems.signal-desktop",
    "com.microsoft.teams",
    "us.zoom.xos",
    "com.apple.FaceTime",
    "com.skype.skype",
}

# Deep work apps (for detecting interruption impact)
DEEP_WORK_APPS = {
    "Code",
    "Visual Studio Code",
    "Xcode",
    "IntelliJ IDEA",
    "PyCharm",
    "WebStorm",
    "Sublime Text",
    "Atom",
    "Cursor",
    "Terminal",
    "iTerm2",
    "Warp",
    "Ghostty",
}

DEEP_WORK_BUNDLE_IDS = {
    "com.microsoft.VSCode",
    "com.apple.dt.Xcode",
    "com.jetbrains.intellij",
    "com.jetbrains.pycharm",
    "com.jetbrains.WebStorm",
    "com.sublimetext.4",
    "com.github.atom",
    "com.todesktop.230313mzl4w4u92",  # Cursor
    "com.apple.Terminal",
    "com.googlecode.iterm2",
    "dev.warp.Warp-Stable",
    "com.mitchellh.ghostty",
}


@dataclass
class ActivityEvent:
    """Represents an app activity event."""

    timestamp: datetime
    app_name: str
    bundle_id: str | None = None
    window_title: str | None = None
    work_category: str | None = None


@dataclass
class InterruptMetrics:
    """Aggregated interrupt metrics for a time period."""

    total_interrupts: int = 0
    quick_check_count: int = 0
    short_response_count: int = 0
    active_communication_count: int = 0
    deep_communication_count: int = 0

    total_interrupt_seconds: float = 0.0
    avg_interrupt_duration_seconds: float = 0.0
    estimated_context_loss_minutes: float = 0.0

    interrupts_per_hour: float = 0.0
    peak_interrupt_hours: list[int] = field(default_factory=list)

    # By app breakdown
    interrupts_by_app: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_interrupts": self.total_interrupts,
            "quick_check_count": self.quick_check_count,
            "short_response_count": self.short_response_count,
            "active_communication_count": self.active_communication_count,
            "deep_communication_count": self.deep_communication_count,
            "total_interrupt_seconds": self.total_interrupt_seconds,
            "avg_interrupt_duration_seconds": self.avg_interrupt_duration_seconds,
            "estimated_context_loss_minutes": self.estimated_context_loss_minutes,
            "interrupts_per_hour": self.interrupts_per_hour,
            "peak_interrupt_hours": self.peak_interrupt_hours,
            "interrupts_by_app": self.interrupts_by_app,
        }


class InterruptDetector:
    """Detects and tracks interrupts from communication apps."""

    # Context loss estimates by interrupt type (in minutes)
    CONTEXT_LOSS_ESTIMATES = {
        InterruptType.QUICK_CHECK: 1.0,  # Quick glance, minimal loss
        InterruptType.SHORT_RESPONSE: 3.0,  # Reply, some refocus needed
        InterruptType.ACTIVE_COMMUNICATION: 5.0,  # Discussion, significant
        InterruptType.DEEP_COMMUNICATION: 0.0,  # Intentional, not an interrupt
    }

    def __init__(self, db: Any | None = None):
        """Initialize the interrupt detector.

        Args:
            db: Database instance for persistence (optional)
        """
        self.db = db

        # Track recent activity for interrupt detection
        self._recent_events: deque[ActivityEvent] = deque(maxlen=100)
        self._pending_interrupts: list[InterruptEvent] = []

        # Current state tracking
        self._current_app: str | None = None
        self._current_app_start: datetime | None = None
        self._previous_app: str | None = None
        self._previous_category: str | None = None

        # Deep work tracking (for context loss calculation)
        self._deep_work_start: datetime | None = None
        self._in_deep_work: bool = False

    def is_communication_app(self, app_name: str, bundle_id: str | None = None) -> bool:
        """Check if an app is a communication app."""
        if app_name in COMMUNICATION_APPS:
            return True
        if bundle_id and bundle_id in COMMUNICATION_BUNDLE_IDS:
            return True
        return False

    def is_deep_work_app(self, app_name: str, bundle_id: str | None = None) -> bool:
        """Check if an app is a deep work app."""
        if app_name in DEEP_WORK_APPS:
            return True
        if bundle_id and bundle_id in DEEP_WORK_BUNDLE_IDS:
            return True
        return False

    def on_activity(self, event: ActivityEvent) -> InterruptEvent | None:
        """Process an activity event and detect interrupts.

        Args:
            event: The activity event to process

        Returns:
            InterruptEvent if an interrupt was detected, None otherwise
        """
        self._recent_events.append(event)

        # Handle first event
        if self._current_app is None:
            self._current_app = event.app_name
            self._current_app_start = event.timestamp
            if self.is_deep_work_app(event.app_name, event.bundle_id):
                self._deep_work_start = event.timestamp
                self._in_deep_work = True
            return None

        # App changed - check for interrupt
        if event.app_name != self._current_app:
            interrupt = self._check_for_interrupt(event)

            # Update state
            self._previous_app = self._current_app
            self._previous_category = event.work_category
            self._current_app = event.app_name
            self._current_app_start = event.timestamp

            # Update deep work tracking
            if self.is_deep_work_app(event.app_name, event.bundle_id):
                if not self._in_deep_work:
                    self._deep_work_start = event.timestamp
                    self._in_deep_work = True
            else:
                self._in_deep_work = False
                self._deep_work_start = None

            return interrupt

        return None

    def _check_for_interrupt(self, new_event: ActivityEvent) -> InterruptEvent | None:
        """Check if switching to a communication app constitutes an interrupt.

        An interrupt is detected when:
        1. User was in a non-communication app
        2. User switches to a communication app
        3. The duration in the communication app is short (< 15 min)
        """
        if not self._current_app or not self._current_app_start:
            return None

        # Only track switches FROM non-communication TO communication apps
        was_in_communication = self.is_communication_app(
            self._current_app, None
        )

        if was_in_communication:
            # Just left a communication app - finalize any pending interrupt
            return self._finalize_interrupt(new_event)

        return None

    def _finalize_interrupt(self, next_event: ActivityEvent) -> InterruptEvent | None:
        """Finalize an interrupt event when leaving a communication app."""
        if not self._current_app_start or not self._previous_app:
            return None

        duration = (next_event.timestamp - self._current_app_start).total_seconds()

        # Only count as interrupt if it was a quick check (< 15 min)
        # Longer durations are intentional communication, not interrupts
        if duration >= 900:  # 15 minutes
            return None

        interrupt_type = InterruptEvent.classify_interrupt(duration)
        context_loss = self.CONTEXT_LOSS_ESTIMATES.get(interrupt_type, 1.0)

        # Increase context loss if interrupted deep work
        if self._in_deep_work and self._deep_work_start:
            deep_work_duration = (
                self._current_app_start - self._deep_work_start
            ).total_seconds() / 60.0
            # Higher cost for interrupting longer deep work sessions
            if deep_work_duration > 25:
                context_loss *= 2.0
            elif deep_work_duration > 10:
                context_loss *= 1.5

        interrupt = InterruptEvent(
            timestamp=self._current_app_start,
            interrupt_app=self._current_app or "",
            duration_seconds=duration,
            previous_app=self._previous_app or "",
            next_app=next_event.app_name,
            interrupt_type=interrupt_type,
            context_loss_estimate=context_loss,
            work_context_before=self._previous_category or "",
        )

        logger.debug(
            f"Interrupt detected: {interrupt.interrupt_app} for {duration:.1f}s "
            f"(type: {interrupt_type.value}, context loss: {context_loss:.1f} min)"
        )

        return interrupt

    async def save_interrupt(self, interrupt: InterruptEvent) -> int:
        """Save an interrupt event to the database.

        Args:
            interrupt: The interrupt event to save

        Returns:
            The ID of the saved record
        """
        if not self.db:
            logger.warning("No database configured for interrupt detector")
            return 0

        return await self.db.insert("interrupts", interrupt.to_db_dict())

    async def get_daily_metrics(self, target_date: datetime | None = None) -> InterruptMetrics:
        """Get interrupt metrics for a specific day.

        Args:
            target_date: The date to get metrics for (defaults to today)

        Returns:
            InterruptMetrics for the day
        """
        if not self.db:
            return InterruptMetrics()

        target_date = target_date or datetime.utcnow()
        date_str = target_date.strftime("%Y-%m-%d")

        # Query interrupts for the day
        rows = await self.db.fetch_all(
            """
            SELECT * FROM interrupts
            WHERE date(timestamp) = ?
            ORDER BY timestamp
            """,
            (date_str,),
        )

        metrics = InterruptMetrics()
        hourly_counts: dict[int, int] = {}

        for row in rows:
            metrics.total_interrupts += 1
            duration = row.get("duration_seconds", 0)
            metrics.total_interrupt_seconds += duration

            # Classify and count
            interrupt_type = InterruptType(row.get("interrupt_type", "quick_check"))
            if interrupt_type == InterruptType.QUICK_CHECK:
                metrics.quick_check_count += 1
            elif interrupt_type == InterruptType.SHORT_RESPONSE:
                metrics.short_response_count += 1
            elif interrupt_type == InterruptType.ACTIVE_COMMUNICATION:
                metrics.active_communication_count += 1
            else:
                metrics.deep_communication_count += 1

            # Context loss
            context_loss = row.get("context_loss_estimate", 0)
            metrics.estimated_context_loss_minutes += context_loss

            # By app
            app = row.get("interrupt_app", "Unknown")
            metrics.interrupts_by_app[app] = metrics.interrupts_by_app.get(app, 0) + 1

            # Hourly distribution
            ts = datetime.fromisoformat(row["timestamp"])
            hour = ts.hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1

        # Calculate averages
        if metrics.total_interrupts > 0:
            metrics.avg_interrupt_duration_seconds = (
                metrics.total_interrupt_seconds / metrics.total_interrupts
            )

        # Calculate interrupts per hour (assuming 8 work hours)
        metrics.interrupts_per_hour = metrics.total_interrupts / 8.0

        # Find peak hours (top 3)
        sorted_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)
        metrics.peak_interrupt_hours = [h for h, _ in sorted_hours[:3]]

        return metrics

    async def get_recent_interrupt_count(self, minutes: int = 30) -> int:
        """Get the number of interrupts in the last N minutes.

        Args:
            minutes: Time window in minutes

        Returns:
            Number of interrupts
        """
        if not self.db:
            return 0

        cutoff = datetime.utcnow() - timedelta(minutes=minutes)

        result = await self.db.fetch_one(
            """
            SELECT COUNT(*) as count FROM interrupts
            WHERE timestamp > ?
            """,
            (cutoff.isoformat(),),
        )

        return result["count"] if result else 0

    async def should_nudge_interrupt_frequency(
        self, threshold_per_hour: float = 4.0
    ) -> tuple[bool, str | None]:
        """Check if user should be nudged about interrupt frequency.

        Args:
            threshold_per_hour: Interrupts per hour threshold

        Returns:
            Tuple of (should_nudge, nudge_message)
        """
        count_30min = await self.get_recent_interrupt_count(30)
        interrupts_per_hour = count_30min * 2  # Extrapolate to hourly rate

        if interrupts_per_hour > threshold_per_hour:
            message = (
                f"You've checked communication apps {count_30min} times "
                f"in the last 30 minutes. Consider batching your checks."
            )
            return True, message

        return False, None
