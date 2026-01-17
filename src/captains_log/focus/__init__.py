"""Focus tracking module with Pomodoro timer and goal-based activity tracking."""

from captains_log.focus.pomodoro import PomodoroTimer, PomodoroState, TimerPhase, PomodoroConfig
from captains_log.focus.activity_matcher import ActivityMatcher, MatchCriteria, GOAL_TEMPLATES
from captains_log.focus.goal_tracker import GoalTracker, FocusGoal, FocusSession, GoalType

__all__ = [
    "PomodoroTimer",
    "PomodoroState",
    "TimerPhase",
    "PomodoroConfig",
    "ActivityMatcher",
    "MatchCriteria",
    "GOAL_TEMPLATES",
    "GoalTracker",
    "FocusGoal",
    "FocusSession",
    "GoalType",
]
