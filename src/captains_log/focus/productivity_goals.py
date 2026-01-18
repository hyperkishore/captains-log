"""Productivity goals manager for quarterly/half-year objectives with daily tracking."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DailyStatus(str, Enum):
    """Daily progress status for a goal."""
    PENDING = "pending"  # Not started or no target today
    GREEN = "green"      # Hit daily target (100%+)
    AMBER = "amber"      # Partial progress (50-99%)
    RED = "red"          # Little/no progress (<50%)


class TargetMode(str, Enum):
    """How to calculate daily targets."""
    FIXED = "fixed"      # Total hours / days until deadline (recalculated daily)
    ROLLING = "rolling"  # Redistributes missed hours to remaining days


@dataclass
class GoalTask:
    """A task within a productivity goal (30-60 min chunks)."""
    id: int | None = None
    goal_id: int | None = None
    name: str = ""
    description: str = ""
    estimated_minutes: int = 30
    parent_task_id: int | None = None
    sort_order: int = 0
    is_completed: bool = False
    created_at: datetime | None = None
    completed_at: datetime | None = None

    # Not stored in DB, populated at runtime
    subtasks: list[GoalTask] = field(default_factory=list)


@dataclass
class DailyProgress:
    """Daily progress record for a goal."""
    id: int | None = None
    goal_id: int | None = None
    date: date | None = None
    focus_minutes: float = 0.0
    target_minutes: float = 0.0
    status: DailyStatus = DailyStatus.PENDING
    sessions_completed: int = 0

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.target_minutes <= 0:
            return 0.0
        return min(100.0, (self.focus_minutes / self.target_minutes) * 100)

    def calculate_status(self) -> DailyStatus:
        """Calculate status based on progress."""
        pct = self.progress_percent
        if pct >= 100:
            return DailyStatus.GREEN
        elif pct >= 50:
            return DailyStatus.AMBER
        elif pct > 0:
            return DailyStatus.RED
        return DailyStatus.PENDING


@dataclass
class ProductivityGoal:
    """A quarterly/half-year productivity goal."""
    id: int | None = None
    name: str = ""
    description: str = ""
    estimated_hours: float = 40.0
    deadline: date | None = None
    priority: int = 0  # Lower = higher priority
    color: str = "#3B82F6"  # Blue default
    is_active: bool = True
    is_completed: bool = False
    target_mode: TargetMode = TargetMode.FIXED
    created_at: datetime | None = None
    completed_at: datetime | None = None

    # Runtime fields (not stored in DB)
    tasks: list[GoalTask] = field(default_factory=list)
    recent_progress: list[DailyProgress] = field(default_factory=list)
    total_focus_minutes: float = 0.0

    @property
    def estimated_minutes(self) -> float:
        """Get estimated time in minutes."""
        return self.estimated_hours * 60

    @property
    def days_remaining(self) -> int:
        """Days until deadline."""
        if not self.deadline:
            return 90  # Default 90 days if no deadline
        delta = self.deadline - date.today()
        return max(1, delta.days)

    @property
    def daily_target_minutes(self) -> float:
        """Calculate daily target in minutes."""
        remaining_minutes = self.estimated_minutes - self.total_focus_minutes
        if remaining_minutes <= 0:
            return 0.0
        return remaining_minutes / self.days_remaining

    @property
    def progress_percent(self) -> float:
        """Overall progress percentage."""
        if self.estimated_minutes <= 0:
            return 0.0
        return min(100.0, (self.total_focus_minutes / self.estimated_minutes) * 100)

    def get_today_status(self) -> DailyStatus:
        """Get today's status from recent progress."""
        today = date.today()
        for prog in self.recent_progress:
            if prog.date == today:
                return prog.status
        return DailyStatus.PENDING


class ProductivityGoalsManager:
    """Manages productivity goals, tasks, and daily progress."""

    def __init__(self, db=None):
        self.db = db

    # ==================== Goals ====================

    async def create_goal(self, goal: ProductivityGoal) -> ProductivityGoal:
        """Create a new productivity goal."""
        if not self.db:
            raise RuntimeError("Database not connected")

        goal_id = await self.db.execute(
            """INSERT INTO productivity_goals
               (name, description, estimated_hours, deadline, priority, color,
                is_active, target_mode, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                goal.name,
                goal.description,
                goal.estimated_hours,
                goal.deadline.isoformat() if goal.deadline else None,
                goal.priority,
                goal.color,
                goal.is_active,
                goal.target_mode.value,
                datetime.now().isoformat(),
            ),
        )
        goal.id = goal_id
        goal.created_at = datetime.now()
        logger.info(f"Created goal: {goal.name} (ID: {goal_id})")
        return goal

    async def get_goal(self, goal_id: int) -> ProductivityGoal | None:
        """Get a goal by ID with tasks and recent progress."""
        if not self.db:
            return None

        row = await self.db.fetch_one(
            "SELECT * FROM productivity_goals WHERE id = ?", (goal_id,)
        )
        if not row:
            return None

        goal = self._row_to_goal(row)
        goal.tasks = await self.get_tasks(goal_id)
        goal.recent_progress = await self.get_recent_progress(goal_id, days=5)
        goal.total_focus_minutes = await self._get_total_focus_minutes(goal_id)
        return goal

    async def list_goals(
        self,
        active_only: bool = True,
        limit: int = 5
    ) -> list[ProductivityGoal]:
        """List goals ordered by priority."""
        if not self.db:
            return []

        query = """
            SELECT * FROM productivity_goals
            WHERE 1=1
        """
        params: list[Any] = []

        if active_only:
            query += " AND is_active = 1 AND is_completed = 0"

        query += " ORDER BY priority ASC, created_at DESC LIMIT ?"
        params.append(limit)

        rows = await self.db.fetch_all(query, tuple(params))
        goals = []

        for row in rows:
            goal = self._row_to_goal(row)
            goal.tasks = await self.get_tasks(goal.id)
            goal.recent_progress = await self.get_recent_progress(goal.id, days=5)
            goal.total_focus_minutes = await self._get_total_focus_minutes(goal.id)
            goals.append(goal)

        return goals

    async def update_goal(self, goal: ProductivityGoal) -> None:
        """Update a goal."""
        if not self.db or not goal.id:
            return

        await self.db.execute(
            """UPDATE productivity_goals SET
               name = ?, description = ?, estimated_hours = ?, deadline = ?,
               priority = ?, color = ?, is_active = ?, is_completed = ?,
               target_mode = ?, completed_at = ?
               WHERE id = ?""",
            (
                goal.name,
                goal.description,
                goal.estimated_hours,
                goal.deadline.isoformat() if goal.deadline else None,
                goal.priority,
                goal.color,
                goal.is_active,
                goal.is_completed,
                goal.target_mode.value,
                goal.completed_at.isoformat() if goal.completed_at else None,
                goal.id,
            ),
        )
        logger.info(f"Updated goal: {goal.name}")

    async def delete_goal(self, goal_id: int) -> None:
        """Delete a goal and its tasks/progress."""
        if not self.db:
            return

        await self.db.execute("DELETE FROM productivity_goals WHERE id = ?", (goal_id,))
        logger.info(f"Deleted goal ID: {goal_id}")

    # ==================== Tasks ====================

    async def create_task(self, task: GoalTask) -> GoalTask:
        """Create a new task."""
        if not self.db:
            raise RuntimeError("Database not connected")

        task_id = await self.db.execute(
            """INSERT INTO goal_tasks
               (goal_id, name, description, estimated_minutes, parent_task_id,
                sort_order, is_completed, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.goal_id,
                task.name,
                task.description,
                task.estimated_minutes,
                task.parent_task_id,
                task.sort_order,
                task.is_completed,
                datetime.now().isoformat(),
            ),
        )
        task.id = task_id
        task.created_at = datetime.now()
        logger.info(f"Created task: {task.name} (ID: {task_id})")
        return task

    async def get_tasks(
        self,
        goal_id: int,
        include_completed: bool = False
    ) -> list[GoalTask]:
        """Get tasks for a goal."""
        if not self.db:
            return []

        query = """
            SELECT * FROM goal_tasks
            WHERE goal_id = ? AND parent_task_id IS NULL
        """
        params: list[Any] = [goal_id]

        if not include_completed:
            query += " AND is_completed = 0"

        query += " ORDER BY sort_order ASC, created_at ASC"

        rows = await self.db.fetch_all(query, tuple(params))
        tasks = []

        for row in rows:
            task = self._row_to_task(row)
            # Load subtasks
            subtask_rows = await self.db.fetch_all(
                "SELECT * FROM goal_tasks WHERE parent_task_id = ? ORDER BY sort_order",
                (task.id,)
            )
            task.subtasks = [self._row_to_task(r) for r in subtask_rows]
            tasks.append(task)

        return tasks

    async def complete_task(self, task_id: int) -> None:
        """Mark a task as completed."""
        if not self.db:
            return

        await self.db.execute(
            """UPDATE goal_tasks SET is_completed = 1, completed_at = ? WHERE id = ?""",
            (datetime.now().isoformat(), task_id),
        )
        logger.info(f"Completed task ID: {task_id}")

    async def delete_task(self, task_id: int) -> None:
        """Delete a task."""
        if not self.db:
            return

        await self.db.execute("DELETE FROM goal_tasks WHERE id = ?", (task_id,))
        logger.info(f"Deleted task ID: {task_id}")

    # ==================== Progress ====================

    async def add_focus_time(
        self,
        goal_id: int,
        minutes: float,
        for_date: date | None = None
    ) -> DailyProgress:
        """Add focus time to a goal's daily progress."""
        if not self.db:
            raise RuntimeError("Database not connected")

        target_date = for_date or date.today()

        # Get or create daily progress
        progress = await self._get_or_create_daily_progress(goal_id, target_date)
        progress.focus_minutes += minutes
        progress.status = progress.calculate_status()

        # Update in database
        await self.db.execute(
            """UPDATE goal_daily_progress SET
               focus_minutes = ?, status = ?, updated_at = ?
               WHERE goal_id = ? AND date = ?""",
            (
                progress.focus_minutes,
                progress.status.value,
                datetime.now().isoformat(),
                goal_id,
                target_date.isoformat(),
            ),
        )

        logger.debug(f"Added {minutes}m to goal {goal_id} for {target_date}")
        return progress

    async def increment_sessions(self, goal_id: int, for_date: date | None = None) -> None:
        """Increment completed sessions for today."""
        if not self.db:
            return

        target_date = for_date or date.today()
        await self._get_or_create_daily_progress(goal_id, target_date)

        await self.db.execute(
            """UPDATE goal_daily_progress SET
               sessions_completed = sessions_completed + 1, updated_at = ?
               WHERE goal_id = ? AND date = ?""",
            (datetime.now().isoformat(), goal_id, target_date.isoformat()),
        )

    async def get_recent_progress(
        self,
        goal_id: int,
        days: int = 5
    ) -> list[DailyProgress]:
        """Get recent daily progress for a goal."""
        if not self.db:
            return []

        # Get last N days
        today = date.today()
        dates = [(today - timedelta(days=i)) for i in range(days)]

        result = []
        for d in reversed(dates):  # Oldest first
            row = await self.db.fetch_one(
                "SELECT * FROM goal_daily_progress WHERE goal_id = ? AND date = ?",
                (goal_id, d.isoformat()),
            )
            if row:
                result.append(self._row_to_progress(row))
            else:
                # Create empty progress for missing days
                goal = await self.db.fetch_one(
                    "SELECT estimated_hours, deadline, target_mode FROM productivity_goals WHERE id = ?",
                    (goal_id,)
                )
                if goal:
                    total_minutes = await self._get_total_focus_minutes(goal_id)
                    remaining = (goal["estimated_hours"] * 60) - total_minutes
                    days_left = 1
                    if goal["deadline"]:
                        deadline = date.fromisoformat(goal["deadline"])
                        days_left = max(1, (deadline - d).days)
                    target = max(0, remaining / days_left) if remaining > 0 else 0

                    result.append(DailyProgress(
                        goal_id=goal_id,
                        date=d,
                        focus_minutes=0,
                        target_minutes=target,
                        status=DailyStatus.PENDING if d >= today else DailyStatus.RED,
                    ))

        return result

    async def get_goals_status_json(self) -> str:
        """Get goals status as JSON for Swift widget."""
        goals = await self.list_goals(active_only=True, limit=5)

        # Get today's total focus time from all sessions
        today_total = await self._get_today_total_focus_minutes()

        goals_data = []
        for goal in goals:
            progress_data = []
            for prog in goal.recent_progress:
                progress_data.append({
                    "date": prog.date.isoformat() if prog.date else "",
                    "status": prog.status.value,
                    "progress_percent": round(prog.progress_percent, 1),
                })

            tasks_data = []
            for task in goal.tasks[:5]:  # Limit tasks
                tasks_data.append({
                    "id": task.id,
                    "name": task.name,
                    "estimated_minutes": task.estimated_minutes,
                })

            goals_data.append({
                "id": goal.id,
                "name": goal.name,
                "color": goal.color,
                "estimated_hours": goal.estimated_hours,
                "progress_percent": round(goal.progress_percent, 1),
                "daily_target_minutes": round(goal.daily_target_minutes, 1),
                "today_status": goal.get_today_status().value,
                "recent_progress": progress_data,
                "tasks": tasks_data,
            })

        return json.dumps({
            "goals": goals_data,
            "today_focus_minutes": round(today_total, 1),
        }, indent=2)

    async def _get_today_total_focus_minutes(self) -> float:
        """Get total focus minutes for today from all sessions."""
        if not self.db:
            return 0.0

        today = date.today().isoformat()
        row = await self.db.fetch_one(
            "SELECT COALESCE(SUM(total_focus_minutes), 0) as total FROM focus_sessions WHERE date = ?",
            (today,)
        )
        return float(row["total"]) if row else 0.0

    # ==================== Settings ====================

    async def get_setting(self, key: str, default: str = "") -> str:
        """Get an app setting."""
        if not self.db:
            return default

        row = await self.db.fetch_one(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        )
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        """Set an app setting."""
        if not self.db:
            return

        await self.db.execute(
            """INSERT INTO app_settings (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?""",
            (key, value, datetime.now().isoformat(), value, datetime.now().isoformat()),
        )

    async def get_default_pomodoro_minutes(self) -> int:
        """Get default pomodoro duration in minutes."""
        value = await self.get_setting("default_pomodoro_minutes", "25")
        return int(value)

    async def get_target_mode(self) -> TargetMode:
        """Get target calculation mode."""
        value = await self.get_setting("target_mode", "fixed")
        return TargetMode(value)

    # ==================== Private Helpers ====================

    async def _get_total_focus_minutes(self, goal_id: int) -> float:
        """Get total focus minutes for a goal across all days."""
        if not self.db:
            return 0.0

        row = await self.db.fetch_one(
            "SELECT COALESCE(SUM(focus_minutes), 0) as total FROM goal_daily_progress WHERE goal_id = ?",
            (goal_id,),
        )
        return float(row["total"]) if row else 0.0

    async def _get_or_create_daily_progress(
        self,
        goal_id: int,
        for_date: date
    ) -> DailyProgress:
        """Get or create daily progress record."""
        if not self.db:
            raise RuntimeError("Database not connected")

        row = await self.db.fetch_one(
            "SELECT * FROM goal_daily_progress WHERE goal_id = ? AND date = ?",
            (goal_id, for_date.isoformat()),
        )

        if row:
            return self._row_to_progress(row)

        # Calculate target for this day
        goal = await self.db.fetch_one(
            "SELECT estimated_hours, deadline FROM productivity_goals WHERE id = ?",
            (goal_id,),
        )

        target_minutes = 60.0  # Default 1 hour
        if goal:
            total_so_far = await self._get_total_focus_minutes(goal_id)
            remaining = (goal["estimated_hours"] * 60) - total_so_far

            days_left = 1
            if goal["deadline"]:
                deadline = date.fromisoformat(goal["deadline"])
                days_left = max(1, (deadline - for_date).days)

            target_minutes = max(0, remaining / days_left)

        # Create new progress record
        await self.db.execute(
            """INSERT INTO goal_daily_progress
               (goal_id, date, focus_minutes, target_minutes, status, created_at)
               VALUES (?, ?, 0, ?, 'pending', ?)""",
            (goal_id, for_date.isoformat(), target_minutes, datetime.now().isoformat()),
        )

        return DailyProgress(
            goal_id=goal_id,
            date=for_date,
            focus_minutes=0,
            target_minutes=target_minutes,
            status=DailyStatus.PENDING,
        )

    def _row_to_goal(self, row: dict) -> ProductivityGoal:
        """Convert database row to ProductivityGoal."""
        return ProductivityGoal(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            estimated_hours=float(row["estimated_hours"]),
            deadline=date.fromisoformat(row["deadline"]) if row.get("deadline") else None,
            priority=row.get("priority", 0),
            color=row.get("color", "#3B82F6"),
            is_active=bool(row.get("is_active", True)),
            is_completed=bool(row.get("is_completed", False)),
            target_mode=TargetMode(row.get("target_mode", "fixed")),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
        )

    def _row_to_task(self, row: dict) -> GoalTask:
        """Convert database row to GoalTask."""
        return GoalTask(
            id=row["id"],
            goal_id=row["goal_id"],
            name=row["name"],
            description=row.get("description", ""),
            estimated_minutes=row.get("estimated_minutes", 30),
            parent_task_id=row.get("parent_task_id"),
            sort_order=row.get("sort_order", 0),
            is_completed=bool(row.get("is_completed", False)),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
        )

    def _row_to_progress(self, row: dict) -> DailyProgress:
        """Convert database row to DailyProgress."""
        return DailyProgress(
            id=row["id"],
            goal_id=row["goal_id"],
            date=date.fromisoformat(row["date"]) if row.get("date") else None,
            focus_minutes=float(row.get("focus_minutes", 0)),
            target_minutes=float(row.get("target_minutes", 0)),
            status=DailyStatus(row.get("status", "pending")),
            sessions_completed=row.get("sessions_completed", 0),
        )
