"""Nudge System for Real-time Optimization Insights.

Provides ambient awareness through:
1. Status color coding (green/amber/red) for menu bar
2. Real-time nudges based on detected patterns
3. optimization_status.json for external integrations

This module writes to optimization_status.json which can be read by:
- Menu bar apps (Swift/SwiftBar)
- Dashboard widgets
- CLI tools
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from captains_log.optimization.schemas import Nudge, NudgeType, OptimizationStatus

logger = logging.getLogger(__name__)


@dataclass
class NudgeThresholds:
    """Configurable thresholds for nudge triggers."""

    # Interrupt thresholds
    interrupts_per_30min_warning: int = 8
    interrupts_per_30min_critical: int = 15

    # Context switch thresholds
    switches_per_hour_warning: int = 20
    switches_per_hour_critical: int = 40

    # Deep work thresholds
    min_deep_work_block_minutes: int = 25

    # Distraction thresholds
    distraction_minutes_warning: int = 30
    distraction_minutes_critical: int = 60

    # Cooldown between nudges (minutes)
    nudge_cooldown_minutes: int = 30


@dataclass
class NudgeState:
    """Current state of the nudge system."""

    # Recent metrics (rolling window)
    recent_interrupts: int = 0
    recent_switches: int = 0
    recent_distraction_minutes: float = 0.0

    # Deep work tracking
    current_deep_work_minutes: float = 0.0
    daily_deep_work_minutes: float = 0.0

    # Status
    status_color: str = "green"  # green, amber, red
    last_nudge_time: datetime | None = None
    pending_nudges: list[Nudge] = field(default_factory=list)

    # Daily totals
    daily_interrupts: int = 0
    daily_context_switches: int = 0
    daily_distraction_minutes: float = 0.0


class NudgeSystem:
    """Real-time nudge system for optimization insights."""

    def __init__(
        self,
        db: Any | None = None,
        data_dir: Path | None = None,
        thresholds: NudgeThresholds | None = None,
    ):
        """Initialize the nudge system.

        Args:
            db: Database instance
            data_dir: Directory for status file output
            thresholds: Customizable nudge thresholds
        """
        self.db = db
        self.data_dir = data_dir or Path.home() / "Library/Application Support/CaptainsLog"
        self.thresholds = thresholds or NudgeThresholds()

        self._state = NudgeState()
        self._running = False
        self._status_update_task: asyncio.Task | None = None

    @property
    def status_file(self) -> Path:
        """Path to the optimization status JSON file."""
        return self.data_dir / "optimization_status.json"

    async def start(self) -> None:
        """Start the nudge system."""
        if self._running:
            return

        self._running = True
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Start periodic status file updates
        self._status_update_task = asyncio.create_task(
            self._periodic_status_update()
        )

        # Initial status write
        await self.write_status()

        logger.info("Nudge system started")

    async def stop(self) -> None:
        """Stop the nudge system."""
        self._running = False

        if self._status_update_task:
            self._status_update_task.cancel()
            try:
                await self._status_update_task
            except asyncio.CancelledError:
                pass

        # Final status write
        await self.write_status()

        logger.info("Nudge system stopped")

    async def on_interrupt(self, count: int = 1) -> Nudge | None:
        """Record an interrupt and check for nudge.

        Args:
            count: Number of interrupts to record

        Returns:
            Nudge if threshold exceeded, None otherwise
        """
        self._state.recent_interrupts += count
        self._state.daily_interrupts += count

        # Check thresholds
        if self._state.recent_interrupts >= self.thresholds.interrupts_per_30min_critical:
            self._state.status_color = "red"
            return self._create_nudge(
                NudgeType.INTERRUPT_FREQUENCY,
                f"High interrupt rate: {self._state.recent_interrupts} in 30 min",
                "Consider enabling Do Not Disturb mode",
                "important",
            )
        elif self._state.recent_interrupts >= self.thresholds.interrupts_per_30min_warning:
            self._state.status_color = "amber"
            return self._create_nudge(
                NudgeType.INTERRUPT_FREQUENCY,
                f"You've checked communication apps {self._state.recent_interrupts} times",
                "Consider batching your checks",
                "gentle",
            )

        return None

    async def on_context_switch(
        self,
        switch_cost_minutes: float = 0,
    ) -> Nudge | None:
        """Record a context switch and check for nudge.

        Args:
            switch_cost_minutes: Estimated cost of the switch

        Returns:
            Nudge if threshold exceeded, None otherwise
        """
        self._state.recent_switches += 1
        self._state.daily_context_switches += 1

        # Check thresholds
        if self._state.recent_switches >= self.thresholds.switches_per_hour_critical:
            self._state.status_color = "red"
            return self._create_nudge(
                NudgeType.CONTEXT_SWITCH_FREQUENCY,
                f"High context switching: {self._state.recent_switches} switches/hour",
                "Try working in focused 45-minute blocks",
                "important",
            )
        elif self._state.recent_switches >= self.thresholds.switches_per_hour_warning:
            self._state.status_color = "amber"
            return self._create_nudge(
                NudgeType.CONTEXT_SWITCH_FREQUENCY,
                f"Frequent context switching detected",
                "Focus on one task at a time",
                "gentle",
            )

        return None

    async def on_distraction(
        self,
        app_name: str,
        duration_minutes: float,
    ) -> Nudge | None:
        """Record time on a distraction app.

        Args:
            app_name: Name of the distraction app
            duration_minutes: Time spent

        Returns:
            Nudge if threshold exceeded, None otherwise
        """
        self._state.recent_distraction_minutes += duration_minutes
        self._state.daily_distraction_minutes += duration_minutes

        # Check thresholds
        if self._state.recent_distraction_minutes >= self.thresholds.distraction_minutes_critical:
            self._state.status_color = "red"
            return self._create_nudge(
                NudgeType.DISTRACTION_ALERT,
                f"Over 1 hour on distractions today",
                "Consider taking a break or refocusing",
                "important",
            )
        elif self._state.recent_distraction_minutes >= self.thresholds.distraction_minutes_warning:
            self._state.status_color = "amber"
            return self._create_nudge(
                NudgeType.DISTRACTION_ALERT,
                f"30+ minutes on {app_name}",
                "Time to get back to work?",
                "gentle",
            )

        return None

    async def on_deep_work_achieved(
        self,
        duration_minutes: float,
    ) -> Nudge | None:
        """Record deep work achievement.

        Args:
            duration_minutes: Duration of the focus session

        Returns:
            Nudge (positive) if milestone reached
        """
        self._state.current_deep_work_minutes = duration_minutes
        self._state.daily_deep_work_minutes = max(
            self._state.daily_deep_work_minutes,
            duration_minutes
        )

        # Positive nudge for deep work milestone
        if duration_minutes >= 25 and duration_minutes < 30:  # Just hit 25 min
            self._state.status_color = "green"
            return self._create_nudge(
                NudgeType.DEEP_WORK_MILESTONE,
                "25-minute focus block achieved!",
                "Keep going or take a 5-minute break",
                "positive",
            )
        elif duration_minutes >= 45 and duration_minutes < 50:  # Flow state
            self._state.status_color = "green"
            return self._create_nudge(
                NudgeType.DEEP_WORK_MILESTONE,
                "You're in flow state! 45 minutes of focus",
                "Excellent deep work - you're crushing it",
                "positive",
            )

        return None

    def _create_nudge(
        self,
        nudge_type: NudgeType,
        message: str,
        suggestion: str,
        urgency: str,
    ) -> Nudge | None:
        """Create a nudge if cooldown has passed.

        Args:
            nudge_type: Type of nudge
            message: Main message
            suggestion: Suggested action
            urgency: Urgency level

        Returns:
            Nudge if created, None if in cooldown
        """
        # Check cooldown
        if self._state.last_nudge_time:
            elapsed = (datetime.utcnow() - self._state.last_nudge_time).total_seconds()
            cooldown_seconds = self.thresholds.nudge_cooldown_minutes * 60
            if elapsed < cooldown_seconds:
                return None

        nudge = Nudge(
            nudge_type=nudge_type,
            message=message,
            suggestion=suggestion,
            urgency=urgency,
        )

        self._state.last_nudge_time = datetime.utcnow()
        self._state.pending_nudges.append(nudge)

        return nudge

    async def save_nudge(self, nudge: Nudge) -> int:
        """Save a nudge to the database.

        Args:
            nudge: The nudge to save

        Returns:
            ID of the saved record
        """
        if not self.db:
            return 0

        try:
            return await self.db.insert("nudge_history", nudge.to_db_dict())
        except Exception as e:
            logger.warning(f"Failed to save nudge: {e}")
            return 0

    async def acknowledge_nudge(self, nudge_id: int) -> None:
        """Mark a nudge as acknowledged.

        Args:
            nudge_id: ID of the nudge to acknowledge
        """
        if not self.db:
            return

        await self.db.execute(
            "UPDATE nudge_history SET acknowledged_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), nudge_id),
        )

    async def dismiss_nudge(self, nudge_id: int) -> None:
        """Mark a nudge as dismissed.

        Args:
            nudge_id: ID of the nudge to dismiss
        """
        if not self.db:
            return

        await self.db.execute(
            "UPDATE nudge_history SET dismissed_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), nudge_id),
        )

    def get_current_status(self) -> OptimizationStatus:
        """Get the current optimization status.

        Returns:
            OptimizationStatus for display
        """
        latest_nudge = None
        if self._state.pending_nudges:
            nudge = self._state.pending_nudges[-1]
            latest_nudge = {
                "type": nudge.nudge_type.value,
                "message": nudge.message,
                "timestamp": datetime.utcnow().isoformat(),
            }

        return OptimizationStatus(
            status_color=self._state.status_color,
            daily_deep_work_hours=self._state.daily_deep_work_minutes / 60.0,
            interrupt_count_today=self._state.daily_interrupts,
            context_switch_cost_minutes=self._state.daily_context_switches * 2.0,  # Est. 2 min per switch
            latest_nudge=latest_nudge,
        )

    async def write_status(self) -> None:
        """Write current status to optimization_status.json.

        This file is read by:
        - Menu bar apps for status color
        - Dashboard widgets
        - CLI tools
        """
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)

            status = self.get_current_status()
            status_dict = status.to_dict()

            # Add additional context
            status_dict["updated_at"] = datetime.utcnow().isoformat()
            status_dict["savings_progress"] = {
                "goal_percent": 20,
                "actual_percent": max(0, 20 - (self._state.daily_distraction_minutes / 480 * 20)),
            }

            with open(self.status_file, "w") as f:
                json.dump(status_dict, f, indent=2)

            logger.debug(f"Wrote optimization status to {self.status_file}")

        except Exception as e:
            logger.warning(f"Failed to write optimization status: {e}")

    async def _periodic_status_update(self) -> None:
        """Periodically update the status file and reset rolling windows."""
        while self._running:
            try:
                # Write current status
                await self.write_status()

                # Every 30 minutes, reset rolling window counters
                # (This is a simplified approach - could use actual time windows)
                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in periodic status update: {e}")
                await asyncio.sleep(60)

    async def reset_rolling_window(self) -> None:
        """Reset the rolling window counters (called every 30 min)."""
        self._state.recent_interrupts = 0
        self._state.recent_switches = 0
        self._state.recent_distraction_minutes = 0.0

        # Update status color based on current state
        await self._recalculate_status_color()

    async def _recalculate_status_color(self) -> None:
        """Recalculate status color based on current metrics."""
        # Green by default
        self._state.status_color = "green"

        # Check for warning conditions
        if self._state.daily_deep_work_minutes < 60:  # Less than 1 hour
            self._state.status_color = "amber"

        if self._state.daily_interrupts > 30:
            self._state.status_color = "amber"

        if self._state.daily_distraction_minutes > 60:
            self._state.status_color = "red"

    async def reset_daily(self) -> None:
        """Reset daily counters (called at midnight or new day)."""
        self._state.daily_interrupts = 0
        self._state.daily_context_switches = 0
        self._state.daily_distraction_minutes = 0.0
        self._state.daily_deep_work_minutes = 0.0
        self._state.pending_nudges = []
        self._state.status_color = "green"

        await self.write_status()
        logger.info("Daily nudge counters reset")

    async def get_recent_nudges(
        self,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Get recent nudges from the database.

        Args:
            hours: Look back period in hours

        Returns:
            List of nudge dictionaries
        """
        if not self.db:
            return []

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        rows = await self.db.fetch_all(
            """
            SELECT * FROM nudge_history
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 20
            """,
            (cutoff.isoformat(),),
        )

        return [dict(row) for row in rows]
