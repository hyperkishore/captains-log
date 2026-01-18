"""Controller that coordinates Pomodoro timer, goal tracker, and widget display."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from captains_log.focus.pomodoro import PomodoroTimer, PomodoroConfig, TimerPhase
from captains_log.focus.goal_tracker import GoalTracker, FocusGoal, FocusSession
from captains_log.focus.activity_matcher import MatchCriteria
from captains_log.widget.focus_widget import FocusWidget, WidgetState, WidgetMode

logger = logging.getLogger(__name__)

# Status file for Swift widget to read
STATUS_FILE = Path.home() / "Library" / "Application Support" / "CaptainsLog" / "focus_status.json"


class WidgetController:
    """Coordinates Pomodoro timer, goal tracking, and widget display.

    This is the main interface for the focus mode feature.

    Usage:
        controller = WidgetController(db)

        # Start focus mode with a goal
        await controller.start_focus(
            goal_name="Deep work on captains-log",
            target_minutes=120,
            match_criteria=MatchCriteria(apps=["VS Code", "Terminal"])
        )

        # Process activity events
        await controller.on_activity_changed(activity_dict)

        # Stop focus mode
        await controller.stop_focus()
    """

    def __init__(self, db=None, config=None):
        """Initialize the widget controller.

        Args:
            db: Database instance for persistence
            config: FocusConfig instance
        """
        self.db = db
        self._config = config

        # Components
        self._timer: PomodoroTimer | None = None
        self._tracker: GoalTracker | None = None
        self._widget: FocusWidget | None = None

        # State
        self._active = False
        self._current_app = ""
        self._current_activity: dict[str, Any] = {}
        self._streak_days = 0

        # For main thread widget updates
        self._pending_state: WidgetState | None = None

    async def start_focus(
        self,
        goal_name: str,
        target_minutes: int = 120,
        estimated_sessions: int = 4,
        match_criteria: MatchCriteria | None = None,
        goal_type: str = "app_based",
        tracking_mode: str = "passive",
        show_widget: bool = True,
    ) -> FocusSession:
        """Start a focus session with the given goal.

        Args:
            goal_name: Name for the goal
            target_minutes: Target minutes to achieve
            estimated_sessions: Estimated Pomodoro sessions to complete the task
            match_criteria: Criteria for matching activities
            goal_type: Type of goal (app_based, project_based, etc.)
            tracking_mode: "passive" (always track) or "strict" (timer only)
            show_widget: Whether to show the floating widget

        Returns:
            The created FocusSession
        """
        if self._active:
            logger.warning("Focus session already active, stopping first")
            await self.stop_focus()

        # Initialize tracker
        if self.db:
            self._tracker = GoalTracker(self.db)
        else:
            self._tracker = GoalTracker()

        # Try to find existing goal by name first
        from captains_log.focus.goal_tracker import GoalType
        goal = None

        if self.db:
            existing_goals = await self._tracker.list_goals(active_only=True)
            for g in existing_goals:
                if g.name.lower() == goal_name.lower():
                    goal = g
                    logger.info(f"Reusing existing goal: {goal.name} (ID: {goal.id})")
                    break

        # Create new goal if not found
        if goal is None:
            goal = FocusGoal(
                name=goal_name,
                goal_type=GoalType(goal_type),
                target_minutes=target_minutes,
                estimated_sessions=estimated_sessions,
                match_criteria=match_criteria or MatchCriteria(),
            )

            if self.db:
                goal = await self._tracker.create_goal(goal)
                logger.info(f"Created new goal: {goal.name} (ID: {goal.id})")

        # Get streak info
        if self.db and goal.id:
            streak_info = await self._tracker.get_streak(goal.id)
            self._streak_days = streak_info.get("current_streak", 0)

        # Set tracking mode
        self._tracker.set_tracking_mode(tracking_mode)

        # Set up tracker callbacks
        self._tracker.on_progress_update = self._on_progress_update
        self._tracker.on_goal_achieved = self._on_goal_achieved
        self._tracker.on_off_goal = self._on_off_goal

        # Start tracking
        session = await self._tracker.set_active_goal(goal)

        # Create timer
        timer_config = PomodoroConfig()
        if self._config:
            timer_config.work_minutes = self._config.work_minutes
            timer_config.short_break_minutes = self._config.short_break_minutes
            timer_config.long_break_minutes = self._config.long_break_minutes
            timer_config.pomodoros_until_long_break = self._config.pomodoros_until_long_break
            timer_config.auto_start_breaks = self._config.auto_start_breaks
            timer_config.auto_start_work = self._config.auto_start_work

        self._timer = PomodoroTimer(timer_config)
        self._timer.on_tick = self._on_timer_tick
        self._timer.on_phase_complete = self._on_phase_complete
        self._timer.on_pomodoro_complete = self._on_pomodoro_complete

        # Create widget
        if show_widget:
            position = self._config.widget_position if self._config else "top-right"
            self._widget = FocusWidget(position=position)
            self._setup_widget_callbacks()
            self._widget.show()

        self._active = True

        # Initial widget update
        self._update_widget()

        logger.info(f"Focus session started: {goal_name} ({target_minutes} min)")
        return session

    async def stop_focus(self) -> FocusSession | None:
        """Stop the current focus session.

        Returns:
            The completed FocusSession, or None if not active
        """
        if not self._active:
            return None

        session = None

        # Stop timer
        if self._timer:
            await self._timer.pause()
            self._timer = None

        # Save and stop tracking
        if self._tracker:
            session = self._tracker.current_session
            # Explicitly save session before clearing
            if self.db and session:
                await self._tracker._save_session()
            await self._tracker.clear_active_goal()
            self._tracker = None

        # Hide widget
        if self._widget:
            self._widget.close()
            self._widget = None

        self._active = False
        self.clear_status_file()
        logger.info("Focus session stopped")

        return session

    async def pause_timer(self) -> None:
        """Pause the Pomodoro timer."""
        if self._timer:
            await self._timer.pause()
            if self._tracker:
                self._tracker.set_timer_running(False)
            self._update_widget()

    async def resume_timer(self) -> None:
        """Resume the Pomodoro timer."""
        if self._timer:
            await self._timer.start()
            if self._tracker:
                self._tracker.set_timer_running(True)
            self._update_widget()

    async def skip_timer(self) -> None:
        """Skip to the next timer phase."""
        if self._timer:
            await self._timer.skip()
            self._update_widget()

    async def reset_timer(self) -> None:
        """Reset the current timer phase."""
        if self._timer:
            await self._timer.reset()
            self._update_widget()

    async def on_activity_changed(self, activity: dict[str, Any]) -> None:
        """Process an activity change event from the orchestrator.

        Args:
            activity: Activity dict with app_name, bundle_id, work_project, etc.
        """
        self._current_activity = activity
        self._current_app = activity.get("app_name", "")

        if self._tracker:
            await self._tracker.on_activity(activity)

        self._update_widget()

    def _setup_widget_callbacks(self) -> None:
        """Set up callbacks from widget button clicks."""
        if not self._widget:
            return

        def on_pause():
            asyncio.create_task(self._toggle_pause())

        def on_skip():
            asyncio.create_task(self.skip_timer())

        def on_reset():
            asyncio.create_task(self.reset_timer())

        self._widget.set_callback("pause", on_pause)
        self._widget.set_callback("skip", on_skip)
        self._widget.set_callback("reset", on_reset)

    async def _toggle_pause(self) -> None:
        """Toggle between paused and running."""
        if self._timer:
            if self._timer.state.is_running:
                await self.pause_timer()
            else:
                await self.resume_timer()

    def _on_timer_tick(self, timer_state) -> None:
        """Handle timer tick event."""
        # Track time automatically when timer is running (for CLI mode without orchestrator)
        # Only during work phase, add 1 second (1/60 minute) to focus time
        if (timer_state.is_running and
            timer_state.phase == TimerPhase.WORK and
            self._tracker and
            self._tracker.current_session):
            # Add 1 second of focus time (converted to minutes)
            self._tracker.current_session.total_focus_minutes += 1 / 60

            # Save to database every 10 seconds
            elapsed = timer_state.total_work_seconds
            if elapsed > 0 and elapsed % 10 == 0 and self.db:
                # Schedule async save (don't block the tick)
                asyncio.create_task(self._save_session_async())

        self._update_widget()

    async def _save_session_async(self) -> None:
        """Save session to database asynchronously."""
        if self._tracker:
            try:
                await self._tracker._save_session()
            except Exception as e:
                logger.error(f"Failed to save session: {e}")

    async def _on_phase_complete(self, phase: TimerPhase) -> None:
        """Handle timer phase completion."""
        if phase == TimerPhase.WORK and self._tracker:
            # Record completed Pomodoro
            await self._tracker.add_pomodoro()
        elif phase in (TimerPhase.SHORT_BREAK, TimerPhase.LONG_BREAK) and self._tracker:
            # Record break time
            if phase == TimerPhase.SHORT_BREAK:
                await self._tracker.add_break_time(5)
            else:
                await self._tracker.add_break_time(15)

        self._update_widget()

    async def _on_pomodoro_complete(self, count: int) -> None:
        """Handle Pomodoro completion."""
        logger.info(f"Pomodoro #{count} complete!")
        # Could add notification here

    async def _on_progress_update(self, session: FocusSession) -> None:
        """Handle goal progress update."""
        self._update_widget()

    async def _on_goal_achieved(self, goal: FocusGoal, session: FocusSession) -> None:
        """Handle goal achievement."""
        logger.info(f"Goal achieved: {goal.name}")
        self._update_widget()
        # Could add celebration notification here

    async def _on_off_goal(self, activity: dict, reason: str) -> None:
        """Handle switching to off-goal activity."""
        if self._config and not self._config.gentle_nudges:
            return
        logger.debug(f"Off-goal activity: {activity.get('app_name')} - {reason}")
        self._update_widget()

    def _update_widget(self) -> None:
        """Update the widget with current state."""
        # Always write status file for Swift widget (even when PyObjC widget disabled)
        self.write_status_file()

        if not self._widget:
            return

        # Build state from components
        state = WidgetState()

        # Timer state
        if self._timer:
            ts = self._timer.state
            state.timer_running = ts.is_running
            state.timer_phase = ts.phase.value
            state.time_remaining = ts.time_remaining_display
            state.pomodoros_today = ts.pomodoros_completed

        # Goal/session state
        if self._tracker and self._tracker.current_session:
            session = self._tracker.current_session
            goal = self._tracker.active_goal

            if goal:
                state.goal_name = goal.name
            state.goal_progress_percent = session.progress_percent
            state.goal_progress_text = session.format_progress()
            state.goal_completed = session.completed

            state.is_on_goal = self._tracker.is_on_goal
            if not state.is_on_goal and self._current_activity:
                state.off_goal_reason = self._current_activity.get("app_name", "")

        # Activity state
        state.current_app = self._current_app

        # Streak
        state.streak_days = self._streak_days

        # Update widget
        self._widget.update(state)

    # Properties
    @property
    def is_active(self) -> bool:
        """Whether a focus session is currently active."""
        return self._active

    @property
    def current_session(self) -> FocusSession | None:
        """Get the current focus session."""
        if self._tracker:
            return self._tracker.current_session
        return None

    @property
    def timer_state(self):
        """Get the current timer state."""
        if self._timer:
            return self._timer.state
        return None

    def get_status(self) -> dict:
        """Get a status summary of the current focus session."""
        status = {
            "active": self._active,
            "current_app": self._current_app,
        }

        if self._timer:
            status["timer"] = self._timer.get_summary()

        if self._tracker and self._tracker.current_session:
            session = self._tracker.current_session
            status["session"] = {
                "goal_name": self._tracker.active_goal.name if self._tracker.active_goal else "",
                "progress_percent": round(session.progress_percent, 1),
                "progress_text": session.format_progress(),
                "completed": session.completed,
                "pomodoros": session.pomodoro_count,
                "is_on_goal": self._tracker.is_on_goal,
            }

        status["streak_days"] = self._streak_days

        return status

    def write_status_file(self) -> None:
        """Write status to JSON file for Swift widget to read."""
        try:
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Build flat status dict for Swift widget
            status = {
                "active": self._active,
                "current_app": self._current_app,
                "streak_days": self._streak_days,
                "goal_name": "",
                "target_minutes": 0,
                "focus_minutes": 0.0,
                "pomodoro_count": 0,
                "estimated_sessions": 4,
                "daily_focus_minutes": 0.0,
                "completed": False,
                "is_on_goal": True,
                "timer_phase": "work",
                "time_remaining": "25:00",
                "timer_running": False,
            }

            if self._timer:
                ts = self._timer.state
                status["timer_phase"] = ts.phase.value
                status["time_remaining"] = ts.time_remaining_display
                status["timer_running"] = ts.is_running

            if self._tracker and self._tracker.current_session:
                session = self._tracker.current_session
                if self._tracker.active_goal:
                    status["goal_name"] = self._tracker.active_goal.name
                    status["target_minutes"] = self._tracker.active_goal.target_minutes
                    # Get estimated sessions from goal (default 4)
                    status["estimated_sessions"] = getattr(
                        self._tracker.active_goal, 'estimated_sessions', 4
                    ) or 4
                status["focus_minutes"] = round(session.total_focus_minutes, 1)
                status["pomodoro_count"] = session.pomodoro_count
                status["completed"] = session.completed
                status["is_on_goal"] = self._tracker.is_on_goal
                # Daily focus is sum of today's session minutes
                status["daily_focus_minutes"] = round(session.total_focus_minutes, 1)

            STATUS_FILE.write_text(json.dumps(status, indent=2))
        except Exception as e:
            logger.error(f"Failed to write status file: {e}")

    def clear_status_file(self) -> None:
        """Clear the status file when session stops."""
        try:
            status = {"active": False}
            STATUS_FILE.write_text(json.dumps(status, indent=2))
        except Exception as e:
            logger.error(f"Failed to clear status file: {e}")
