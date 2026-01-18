"""Goal tracking for focus sessions with progress monitoring."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Any, Callable, Awaitable

from captains_log.focus.activity_matcher import ActivityMatcher, MatchCriteria

logger = logging.getLogger(__name__)


class GoalType(Enum):
    """Type of focus goal."""
    APP_BASED = "app_based"           # Track time in specific apps
    PROJECT_BASED = "project_based"   # Track time on specific project
    CATEGORY_BASED = "category_based" # Track time in category (Development, Writing, etc.)
    NO_DISTRACTION = "no_distraction" # Track time NOT in distraction apps


@dataclass
class FocusGoal:
    """A focus goal to track progress against.

    Example:
        goal = FocusGoal(
            id=1,
            name="Deep work on captains-log",
            goal_type=GoalType.PROJECT_BASED,
            target_minutes=120,
            estimated_sessions=4,
            match_criteria=MatchCriteria(
                apps=["VS Code", "Terminal"],
                projects=["captains-log"]
            )
        )
    """
    id: int | None = None
    name: str = ""
    goal_type: GoalType = GoalType.APP_BASED
    target_minutes: int = 120  # 2 hours default
    estimated_sessions: int = 4  # Number of pomodoro sessions to complete task
    match_criteria: MatchCriteria = field(default_factory=MatchCriteria)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> FocusGoal:
        """Create from database row."""
        criteria_json = row.get("match_criteria", "{}")
        if isinstance(criteria_json, str):
            criteria_dict = json.loads(criteria_json)
        else:
            criteria_dict = criteria_json or {}

        return cls(
            id=row.get("id"),
            name=row.get("name", ""),
            goal_type=GoalType(row.get("goal_type", "app_based")),
            target_minutes=row.get("target_minutes", 120),
            estimated_sessions=row.get("estimated_sessions", 4),
            match_criteria=MatchCriteria.from_dict(criteria_dict),
            is_active=bool(row.get("is_active", True)),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.now(),
        )

    def to_db_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "name": self.name,
            "goal_type": self.goal_type.value,
            "target_minutes": self.target_minutes,
            "estimated_sessions": self.estimated_sessions,
            "match_criteria": json.dumps(self.match_criteria.to_dict()),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class FocusSession:
    """A focus session tracking progress toward a goal.

    Tracks both Pomodoro-based and passive time accumulation.
    """
    id: int | None = None
    goal_id: int | None = None
    goal: FocusGoal | None = None
    date: date = field(default_factory=date.today)
    pomodoro_count: int = 0
    total_focus_minutes: float = 0.0
    total_break_minutes: float = 0.0
    off_goal_minutes: float = 0.0  # Time spent on non-goal activities
    completed: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def progress_percent(self) -> float:
        """Progress toward goal (0-100)."""
        if not self.goal:
            return 0.0
        target = self.goal.target_minutes
        if target <= 0:
            return 100.0
        return min(100.0, (self.total_focus_minutes / target) * 100)

    @property
    def remaining_minutes(self) -> float:
        """Minutes remaining to reach goal."""
        if not self.goal:
            return 0.0
        return max(0.0, self.goal.target_minutes - self.total_focus_minutes)

    @property
    def focus_ratio(self) -> float:
        """Ratio of focused time to total tracked time."""
        total = self.total_focus_minutes + self.off_goal_minutes
        if total <= 0:
            return 1.0
        return self.total_focus_minutes / total

    def format_progress(self) -> str:
        """Format progress as human-readable string."""
        hours = int(self.total_focus_minutes // 60)
        mins = int(self.total_focus_minutes % 60)

        if self.goal:
            target_hours = self.goal.target_minutes // 60
            target_mins = self.goal.target_minutes % 60

            if hours > 0:
                current = f"{hours}h {mins}m"
            else:
                current = f"{mins}m"

            if target_hours > 0:
                target = f"{target_hours}h {target_mins}m" if target_mins else f"{target_hours}h"
            else:
                target = f"{target_mins}m"

            return f"{current} / {target}"
        else:
            if hours > 0:
                return f"{hours}h {mins}m"
            return f"{mins}m"

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> FocusSession:
        """Create from database row."""
        return cls(
            id=row.get("id"),
            goal_id=row.get("goal_id"),
            date=date.fromisoformat(row["date"]) if row.get("date") else date.today(),
            pomodoro_count=row.get("pomodoro_count", 0),
            total_focus_minutes=row.get("total_focus_minutes", 0.0),
            total_break_minutes=row.get("total_break_minutes", 0.0),
            off_goal_minutes=row.get("off_goal_minutes", 0.0),
            completed=bool(row.get("completed", False)),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.now(),
        )

    def to_db_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "goal_id": self.goal_id,
            "date": self.date.isoformat(),
            "pomodoro_count": self.pomodoro_count,
            "total_focus_minutes": self.total_focus_minutes,
            "total_break_minutes": self.total_break_minutes,
            "off_goal_minutes": self.off_goal_minutes,
            "completed": self.completed,
            "created_at": self.created_at.isoformat(),
        }


class GoalTracker:
    """Tracks progress toward focus goals based on activity events.

    Usage:
        tracker = GoalTracker(db)

        # Set active goal
        goal = FocusGoal(name="Deep work", target_minutes=120, ...)
        await tracker.set_active_goal(goal)

        # Process activity events
        await tracker.on_activity(activity_dict)

        # Get current progress
        session = tracker.current_session
        print(f"Progress: {session.progress_percent}%")
    """

    def __init__(self, db=None):
        """Initialize the goal tracker.

        Args:
            db: Database instance for persistence (optional for in-memory only)
        """
        self.db = db
        self._matcher = ActivityMatcher()
        self._active_goal: FocusGoal | None = None
        self._current_session: FocusSession | None = None
        self._last_activity_time: datetime | None = None
        self._last_was_on_goal: bool = False
        self._tracking_mode: str = "passive"  # "passive" or "strict"
        self._is_timer_running: bool = False
        self._lock = asyncio.Lock()

        # Callbacks
        self.on_progress_update: Callable[[FocusSession], Awaitable[None] | None] | None = None
        self.on_goal_achieved: Callable[[FocusGoal, FocusSession], Awaitable[None] | None] | None = None
        self.on_off_goal: Callable[[dict, str], Awaitable[None] | None] | None = None  # activity, reason

    @property
    def active_goal(self) -> FocusGoal | None:
        """Get the currently active goal."""
        return self._active_goal

    @property
    def current_session(self) -> FocusSession | None:
        """Get the current tracking session."""
        return self._current_session

    @property
    def is_on_goal(self) -> bool:
        """Whether the last activity was on-goal."""
        return self._last_was_on_goal

    async def set_active_goal(self, goal: FocusGoal) -> FocusSession:
        """Set the active goal and create/resume a session for today.

        Args:
            goal: The goal to track

        Returns:
            The current or new FocusSession
        """
        async with self._lock:
            self._active_goal = goal

            # Check for existing session today
            if self.db and goal.id:
                today = date.today().isoformat()
                row = await self.db.fetch_one(
                    "SELECT * FROM focus_sessions WHERE goal_id = ? AND date = ?",
                    (goal.id, today)
                )
                if row:
                    self._current_session = FocusSession.from_db_row(row)
                    self._current_session.goal = goal
                    logger.info(f"Resumed existing session for goal: {goal.name}")
                    return self._current_session

            # Create new session
            self._current_session = FocusSession(
                goal_id=goal.id,
                goal=goal,
                date=date.today(),
            )

            # Persist to database
            if self.db:
                session_id = await self.db.insert("focus_sessions", self._current_session.to_db_dict())
                self._current_session.id = session_id

            logger.info(f"Started new session for goal: {goal.name}")
            return self._current_session

    async def clear_active_goal(self) -> None:
        """Clear the active goal (stop tracking)."""
        async with self._lock:
            if self._current_session and self.db:
                await self._save_session()

            self._active_goal = None
            self._current_session = None
            self._last_activity_time = None
            self._last_was_on_goal = False

    def set_tracking_mode(self, mode: str) -> None:
        """Set tracking mode.

        Args:
            mode: "passive" (always track) or "strict" (only when timer running)
        """
        if mode not in ("passive", "strict"):
            raise ValueError(f"Invalid tracking mode: {mode}")
        self._tracking_mode = mode

    def set_timer_running(self, is_running: bool) -> None:
        """Update timer state for strict mode tracking."""
        self._is_timer_running = is_running

    async def on_activity(self, activity: dict[str, Any]) -> None:
        """Process an activity event and update tracking.

        Called by the orchestrator when app focus changes.

        Args:
            activity: Activity dict with app_name, bundle_id, work_project, etc.
        """
        if not self._active_goal or not self._current_session:
            return

        # Check tracking mode
        if self._tracking_mode == "strict" and not self._is_timer_running:
            return

        async with self._lock:
            now = datetime.now()

            # Calculate time since last activity
            if self._last_activity_time:
                elapsed_seconds = (now - self._last_activity_time).total_seconds()
                # Cap at 5 minutes to handle gaps
                elapsed_minutes = min(elapsed_seconds / 60, 5.0)
            else:
                elapsed_minutes = 0.0

            # Check if activity matches goal
            result = self._matcher.matches(self._active_goal.match_criteria, activity)

            # Update session based on match
            if self._last_activity_time and elapsed_minutes > 0:
                if self._last_was_on_goal:
                    self._current_session.total_focus_minutes += elapsed_minutes
                else:
                    self._current_session.off_goal_minutes += elapsed_minutes

            # Update state
            self._last_activity_time = now
            was_on_goal = self._last_was_on_goal
            self._last_was_on_goal = result.matches

            # Check for goal completion
            if not self._current_session.completed and \
               self._current_session.total_focus_minutes >= self._active_goal.target_minutes:
                self._current_session.completed = True
                await self._fire_goal_achieved()

            # Persist periodically (every 30 seconds of change)
            if self.db:
                await self._save_session()

            # Fire callbacks
            if self.on_progress_update:
                try:
                    result_cb = self.on_progress_update(self._current_session)
                    if asyncio.iscoroutine(result_cb):
                        await result_cb
                except Exception as e:
                    logger.error(f"Error in on_progress_update callback: {e}")

            # Fire off-goal callback when switching away
            if was_on_goal and not result.matches and self.on_off_goal:
                try:
                    result_cb = self.on_off_goal(activity, result.reason)
                    if asyncio.iscoroutine(result_cb):
                        await result_cb
                except Exception as e:
                    logger.error(f"Error in on_off_goal callback: {e}")

    async def add_pomodoro(self) -> None:
        """Record a completed Pomodoro."""
        if self._current_session:
            async with self._lock:
                self._current_session.pomodoro_count += 1
                if self.db:
                    await self._save_session()

    async def add_break_time(self, minutes: float) -> None:
        """Record break time."""
        if self._current_session:
            async with self._lock:
                self._current_session.total_break_minutes += minutes
                if self.db:
                    await self._save_session()

    async def _save_session(self) -> None:
        """Save current session to database."""
        if not self.db or not self._current_session:
            return

        data = self._current_session.to_db_dict()

        if self._current_session.id:
            # Update existing
            sets = ", ".join(f"{k} = ?" for k in data.keys())
            await self.db.execute(
                f"UPDATE focus_sessions SET {sets} WHERE id = ?",
                (*data.values(), self._current_session.id)
            )
        else:
            # Insert new
            self._current_session.id = await self.db.insert("focus_sessions", data)

    async def _fire_goal_achieved(self) -> None:
        """Fire goal achieved callback."""
        if self.on_goal_achieved and self._active_goal and self._current_session:
            try:
                result = self.on_goal_achieved(self._active_goal, self._current_session)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in on_goal_achieved callback: {e}")

    # Goal CRUD operations
    async def create_goal(self, goal: FocusGoal) -> FocusGoal:
        """Create a new goal in the database."""
        if not self.db:
            raise RuntimeError("Database not configured")

        goal_id = await self.db.insert("focus_goals", goal.to_db_dict())
        goal.id = goal_id
        return goal

    async def get_goal(self, goal_id: int) -> FocusGoal | None:
        """Get a goal by ID."""
        if not self.db:
            return None

        row = await self.db.fetch_one(
            "SELECT * FROM focus_goals WHERE id = ?",
            (goal_id,)
        )
        if row:
            return FocusGoal.from_db_row(row)
        return None

    async def list_goals(self, active_only: bool = True) -> list[FocusGoal]:
        """List all goals."""
        if not self.db:
            return []

        if active_only:
            rows = await self.db.fetch_all(
                "SELECT * FROM focus_goals WHERE is_active = 1 ORDER BY created_at DESC"
            )
        else:
            rows = await self.db.fetch_all(
                "SELECT * FROM focus_goals ORDER BY created_at DESC"
            )

        return [FocusGoal.from_db_row(row) for row in rows]

    async def delete_goal(self, goal_id: int) -> None:
        """Soft delete a goal (mark inactive)."""
        if not self.db:
            return

        await self.db.execute(
            "UPDATE focus_goals SET is_active = 0 WHERE id = ?",
            (goal_id,)
        )

    # Session queries
    async def get_sessions_for_date(self, target_date: date) -> list[FocusSession]:
        """Get all sessions for a specific date."""
        if not self.db:
            return []

        rows = await self.db.fetch_all(
            "SELECT * FROM focus_sessions WHERE date = ? ORDER BY created_at",
            (target_date.isoformat(),)
        )

        sessions = []
        for row in rows:
            session = FocusSession.from_db_row(row)
            # Load associated goal
            if session.goal_id:
                session.goal = await self.get_goal(session.goal_id)
            sessions.append(session)

        return sessions

    async def get_streak(self, goal_id: int) -> dict:
        """Get streak information for a goal.

        Returns:
            dict with current_streak, longest_streak, last_completed_date
        """
        if not self.db:
            return {"current_streak": 0, "longest_streak": 0, "last_completed_date": None}

        # Get all completed sessions ordered by date
        rows = await self.db.fetch_all(
            """SELECT date FROM focus_sessions
               WHERE goal_id = ? AND completed = 1
               ORDER BY date DESC""",
            (goal_id,)
        )

        if not rows:
            return {"current_streak": 0, "longest_streak": 0, "last_completed_date": None}

        dates = [date.fromisoformat(row["date"]) for row in rows]

        # Calculate current streak
        current_streak = 0
        today = date.today()
        expected = today

        for d in dates:
            if d == expected or d == expected - timedelta(days=1):
                current_streak += 1
                expected = d - timedelta(days=1)
            else:
                break

        # Calculate longest streak
        longest_streak = 1
        current_run = 1

        for i in range(1, len(dates)):
            if dates[i] == dates[i-1] - timedelta(days=1):
                current_run += 1
                longest_streak = max(longest_streak, current_run)
            else:
                current_run = 1

        return {
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "last_completed_date": dates[0].isoformat() if dates else None,
        }
