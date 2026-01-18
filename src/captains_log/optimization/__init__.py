"""Time Optimization Engine for Captain's Log.

This module provides time optimization features including:
- Interrupt detection and tracking
- Context switch cost calculation
- Meeting fragmentation analysis (Swiss cheese score)
- DEAL framework classification (Delegate, Eliminate, Automate, Leverage)
- Daily briefings and weekly reports
- Real-time nudges for behavior change
- Time savings tracking toward 20% goal
"""

from captains_log.optimization.schemas import (
    DEALCategory,
    InterruptType,
    InterruptEvent,
    ContextSwitch,
    DailyOptimizationMetrics,
    WeeklyOptimizationInsights,
    Nudge,
    NudgeType,
    Recommendation,
    UserProfile,
    SwitchType,
    OptimizationStatus,
)

from captains_log.optimization.deal_classifier import (
    DEALClassifier,
    DEALMetrics,
    ClassificationResult,
    ActivityPattern,
)

from captains_log.optimization.meeting_fragmentation import (
    MeetingFragmentationAnalyzer,
    FragmentationMetrics,
    WeeklyFragmentationMetrics,
    TimeBlock,
)

from captains_log.optimization.daily_briefing import (
    DailyBriefingGenerator,
    DailyBriefing,
    DailyWin,
    QuickWin,
)

from captains_log.optimization.weekly_report import (
    WeeklyReportGenerator,
    WeeklyReport,
    WeeklyTrend,
    WeeklyInsight,
    WeeklyRecommendation,
    TimeSavingsProgress,
)

from captains_log.optimization.nudge_system import (
    NudgeSystem,
    NudgeThresholds,
    NudgeState,
)

__all__ = [
    # Schemas
    "DEALCategory",
    "InterruptType",
    "InterruptEvent",
    "ContextSwitch",
    "DailyOptimizationMetrics",
    "WeeklyOptimizationInsights",
    "Nudge",
    "NudgeType",
    "Recommendation",
    "UserProfile",
    "SwitchType",
    "OptimizationStatus",
    # DEAL Classifier
    "DEALClassifier",
    "DEALMetrics",
    "ClassificationResult",
    "ActivityPattern",
    # Meeting Fragmentation
    "MeetingFragmentationAnalyzer",
    "FragmentationMetrics",
    "WeeklyFragmentationMetrics",
    "TimeBlock",
    # Daily Briefing
    "DailyBriefingGenerator",
    "DailyBriefing",
    "DailyWin",
    "QuickWin",
    # Weekly Report
    "WeeklyReportGenerator",
    "WeeklyReport",
    "WeeklyTrend",
    "WeeklyInsight",
    "WeeklyRecommendation",
    "TimeSavingsProgress",
    # Nudge System
    "NudgeSystem",
    "NudgeThresholds",
    "NudgeState",
]
