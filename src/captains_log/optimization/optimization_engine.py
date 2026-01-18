"""Optimization Engine - Main coordinator for time optimization features.

This module coordinates all optimization components:
- Interrupt detection
- Context switch analysis
- DEAL classification
- Nudge system
- Status file output for menu bar integration
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from captains_log.core.config import OptimizationConfig
from captains_log.optimization.interrupt_detector import (
    ActivityEvent,
    InterruptDetector,
)
from captains_log.optimization.context_switch_analyzer import ContextSwitchAnalyzer
from captains_log.optimization.schemas import (
    Nudge,
    NudgeType,
    OptimizationStatus,
)

logger = logging.getLogger(__name__)


class OptimizationEngine:
    """Main coordinator for time optimization features."""

    def __init__(
        self,
        db: Any,
        config: OptimizationConfig,
        data_dir: Path | None = None,
    ):
        """Initialize the optimization engine.

        Args:
            db: Database instance
            config: Optimization configuration
            data_dir: Data directory for status files
        """
        self.db = db
        self.config = config
        self.data_dir = data_dir or Path.home() / "Library/Application Support/CaptainsLog"

        # Initialize analyzers
        self.interrupt_detector = InterruptDetector(db=db)
        self.context_switch_analyzer = ContextSwitchAnalyzer(db=db)

        # State tracking
        self._running = False
        self._last_nudge_time: datetime | None = None
        self._status = OptimizationStatus()

        # Background task for periodic updates
        self._update_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the optimization engine."""
        if self._running:
            return

        self._running = True
        logger.info("Optimization engine started")

        # Start periodic status updates
        if self.config.write_status_file:
            self._update_task = asyncio.create_task(self._periodic_status_update())

    async def stop(self) -> None:
        """Stop the optimization engine."""
        self._running = False

        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        # Write final status
        await self._write_status_file()

        logger.info("Optimization engine stopped")

    async def on_activity(
        self,
        timestamp: datetime,
        app_name: str,
        bundle_id: str | None = None,
        window_title: str | None = None,
        work_category: str | None = None,
    ) -> None:
        """Process an activity event.

        This is called by the orchestrator on each app change.

        Args:
            timestamp: When the activity occurred
            app_name: Name of the active application
            bundle_id: Bundle ID of the application
            window_title: Current window title
            work_category: Category of work (if known)
        """
        if not self.config.enabled:
            return

        # Create activity event
        event = ActivityEvent(
            timestamp=timestamp,
            app_name=app_name,
            bundle_id=bundle_id,
            window_title=window_title,
            work_category=work_category,
        )

        # Process through interrupt detector
        interrupt = self.interrupt_detector.on_activity(event)
        if interrupt:
            await self.interrupt_detector.save_interrupt(interrupt)
            self._status.interrupt_count_today += 1

            # Check for nudge
            if self.config.enable_nudges:
                await self._check_interrupt_nudge()

        # Process through context switch analyzer
        switch = self.context_switch_analyzer.on_app_change(
            timestamp=timestamp,
            new_app=app_name,
        )
        if switch:
            await self.context_switch_analyzer.save_switch(switch)
            self._status.context_switch_cost_minutes += switch.estimated_cost_minutes

        # Update deep work tracking
        if self.context_switch_analyzer.is_in_deep_work():
            duration = self.context_switch_analyzer.get_current_focus_duration()
            self._status.daily_deep_work_hours = duration / 60.0

        # Update status color based on current state
        self._update_status_color()

    async def _check_interrupt_nudge(self) -> None:
        """Check if we should nudge about interrupt frequency."""
        # Respect cooldown
        if self._last_nudge_time:
            elapsed = (datetime.utcnow() - self._last_nudge_time).total_seconds()
            cooldown_seconds = self.config.nudge_cooldown_minutes * 60
            if elapsed < cooldown_seconds:
                return

        # Check interrupt frequency
        should_nudge, message = await self.interrupt_detector.should_nudge_interrupt_frequency(
            threshold_per_hour=self.config.interrupt_nudge_threshold
        )

        if should_nudge and message:
            nudge = Nudge(
                nudge_type=NudgeType.INTERRUPT_FREQUENCY,
                message=message,
                suggestion="Consider batching your communication checks.",
                urgency="gentle",
            )

            # Save nudge
            await self.db.insert("nudge_history", nudge.to_db_dict())

            # Update status with latest nudge
            self._status.latest_nudge = {
                "type": nudge.nudge_type.value,
                "message": nudge.message,
                "timestamp": datetime.utcnow().isoformat(),
            }

            self._last_nudge_time = datetime.utcnow()
            logger.info(f"Nudge generated: {message}")

    def _update_status_color(self) -> None:
        """Update the status color based on current metrics."""
        # Green: On track for deep work goal
        # Amber: Slightly off track or high interrupts
        # Red: Significant issues

        deep_work_hours = self._status.daily_deep_work_hours
        ideal_hours = self.config.ideal_deep_work_hours

        # Calculate expected progress (assuming 8-hour workday)
        now = datetime.now()
        work_start = now.replace(hour=9, minute=0, second=0)
        if now < work_start:
            expected_progress = 0.0
        else:
            hours_elapsed = min(8, (now - work_start).total_seconds() / 3600)
            expected_progress = (hours_elapsed / 8) * ideal_hours

        # Compare actual to expected
        if deep_work_hours >= expected_progress * 0.8:
            self._status.status_color = "green"
        elif deep_work_hours >= expected_progress * 0.5:
            self._status.status_color = "amber"
        else:
            self._status.status_color = "red"

        # Override to amber/red for high interrupt count
        if self._status.interrupt_count_today > 30:
            self._status.status_color = "red"
        elif self._status.interrupt_count_today > 15:
            if self._status.status_color == "green":
                self._status.status_color = "amber"

    async def _write_status_file(self) -> None:
        """Write optimization status to JSON file for menu bar integration."""
        if not self.config.write_status_file:
            return

        status_file = self.data_dir / "optimization_status.json"

        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)

            with open(status_file, "w") as f:
                json.dump(self._status.to_dict(), f, indent=2)

            logger.debug(f"Wrote optimization status to {status_file}")
        except Exception as e:
            logger.warning(f"Failed to write optimization status: {e}")

    async def _periodic_status_update(self) -> None:
        """Periodically update the status file."""
        while self._running:
            try:
                await self._write_status_file()
                await asyncio.sleep(5)  # Update every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in periodic status update: {e}")
                await asyncio.sleep(30)  # Back off on error

    async def get_daily_summary(self, target_date: datetime | None = None) -> dict[str, Any]:
        """Get optimization summary for a specific day.

        Args:
            target_date: The date to get summary for (defaults to today)

        Returns:
            Dictionary with optimization metrics
        """
        target_date = target_date or datetime.utcnow()

        # Get interrupt metrics
        interrupt_metrics = await self.interrupt_detector.get_daily_metrics(target_date)

        # Get context switch metrics
        switch_metrics = await self.context_switch_analyzer.get_daily_metrics(target_date)

        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "interrupts": interrupt_metrics.to_dict(),
            "context_switches": switch_metrics.to_dict(),
            "deep_work_hours": self._status.daily_deep_work_hours,
            "status_color": self._status.status_color,
        }

    async def reset_daily_metrics(self) -> None:
        """Reset daily metrics (called at midnight or new day)."""
        self._status = OptimizationStatus()
        logger.info("Daily optimization metrics reset")
