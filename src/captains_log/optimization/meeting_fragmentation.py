"""Meeting Fragmentation Analysis.

Calculates the "Swiss Cheese Score" - how much meetings fragment
the workday into unusable small blocks.

Key concept: A day with 4 hours of meetings could have:
- Good: Two 2-hour blocks (morning meetings, afternoon free)
- Bad: Four 1-hour meetings scattered (Swiss cheese day)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from typing import Any

logger = logging.getLogger(__name__)


# Meeting detection patterns
MEETING_APPS = {
    "Zoom", "zoom.us", "Google Meet", "Microsoft Teams",
    "FaceTime", "Webex", "Skype", "Around", "Loom",
    "Discord",  # Voice channels
    "Slack",    # Huddles
}

MEETING_BUNDLE_IDS = {
    "us.zoom.xos",
    "com.apple.FaceTime",
    "com.microsoft.teams",
    "com.webex.meetingmanager",
    "com.skype.skype",
}

# Minimum duration to consider as a meeting (in minutes)
MIN_MEETING_DURATION = 5

# Work hours (configurable)
DEFAULT_WORK_START = time(9, 0)
DEFAULT_WORK_END = time(18, 0)


@dataclass
class TimeBlock:
    """A block of time in the schedule."""

    start: datetime
    end: datetime
    block_type: str  # "meeting", "deep_work", "fragmented", "usable"
    app_name: str | None = None
    duration_minutes: float = 0.0

    def __post_init__(self):
        if self.duration_minutes == 0.0:
            self.duration_minutes = (self.end - self.start).total_seconds() / 60.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "block_type": self.block_type,
            "app_name": self.app_name,
            "duration_minutes": self.duration_minutes,
        }


@dataclass
class FragmentationMetrics:
    """Metrics for meeting fragmentation analysis."""

    # Meeting stats
    total_meetings: int = 0
    total_meeting_minutes: float = 0.0
    avg_meeting_duration: float = 0.0
    back_to_back_meetings: int = 0

    # Fragmentation stats
    swiss_cheese_score: float = 0.0  # 0-1, higher = more fragmented
    usable_blocks: int = 0  # Gaps >= 30 min
    fragmented_blocks: int = 0  # Gaps 5-30 min
    tiny_gaps: int = 0  # Gaps < 5 min

    # Deep work impact
    largest_focus_block_minutes: float = 0.0
    total_usable_minutes: float = 0.0
    total_fragmented_minutes: float = 0.0

    # Time distribution
    meeting_hours: float = 0.0
    focus_hours: float = 0.0

    # Recommendations
    consolidation_possible: bool = False
    suggested_meeting_days: list[str] = field(default_factory=list)

    # Block details
    time_blocks: list[TimeBlock] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_meetings": self.total_meetings,
            "total_meeting_minutes": self.total_meeting_minutes,
            "avg_meeting_duration": self.avg_meeting_duration,
            "back_to_back_meetings": self.back_to_back_meetings,
            "swiss_cheese_score": self.swiss_cheese_score,
            "usable_blocks": self.usable_blocks,
            "fragmented_blocks": self.fragmented_blocks,
            "tiny_gaps": self.tiny_gaps,
            "largest_focus_block_minutes": self.largest_focus_block_minutes,
            "total_usable_minutes": self.total_usable_minutes,
            "total_fragmented_minutes": self.total_fragmented_minutes,
            "meeting_hours": self.meeting_hours,
            "focus_hours": self.focus_hours,
            "consolidation_possible": self.consolidation_possible,
            "suggested_meeting_days": self.suggested_meeting_days,
            "time_blocks": [b.to_dict() for b in self.time_blocks],
        }


@dataclass
class WeeklyFragmentationMetrics:
    """Weekly fragmentation summary."""

    days: dict[str, FragmentationMetrics] = field(default_factory=dict)
    avg_swiss_cheese_score: float = 0.0
    best_focus_day: str = ""
    worst_focus_day: str = ""
    total_meetings: int = 0
    total_meeting_hours: float = 0.0
    total_focus_hours: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "days": {k: v.to_dict() for k, v in self.days.items()},
            "avg_swiss_cheese_score": self.avg_swiss_cheese_score,
            "best_focus_day": self.best_focus_day,
            "worst_focus_day": self.worst_focus_day,
            "total_meetings": self.total_meetings,
            "total_meeting_hours": self.total_meeting_hours,
            "total_focus_hours": self.total_focus_hours,
        }


class MeetingFragmentationAnalyzer:
    """Analyzes how meetings fragment the workday."""

    def __init__(
        self,
        db: Any | None = None,
        work_start: time = DEFAULT_WORK_START,
        work_end: time = DEFAULT_WORK_END,
    ):
        """Initialize the fragmentation analyzer.

        Args:
            db: Database instance
            work_start: Start of work day
            work_end: End of work day
        """
        self.db = db
        self.work_start = work_start
        self.work_end = work_end

    def is_meeting_app(self, app_name: str, bundle_id: str | None = None) -> bool:
        """Check if an app is a meeting app."""
        if app_name in MEETING_APPS:
            return True
        if bundle_id and bundle_id in MEETING_BUNDLE_IDS:
            return True
        return False

    async def analyze_day(
        self,
        target_date: datetime | None = None,
    ) -> FragmentationMetrics:
        """Analyze meeting fragmentation for a specific day.

        Args:
            target_date: The date to analyze (defaults to today)

        Returns:
            FragmentationMetrics for the day
        """
        if not self.db:
            return FragmentationMetrics()

        target_date = target_date or datetime.utcnow()
        date_str = target_date.strftime("%Y-%m-%d")

        # Get all activities for the day
        rows = await self.db.fetch_all(
            """
            SELECT app_name, bundle_id, timestamp
            FROM activity_logs
            WHERE date(timestamp) = ?
            ORDER BY timestamp
            """,
            (date_str,),
        )

        if not rows:
            return FragmentationMetrics()

        # Detect meeting blocks
        meetings = self._detect_meeting_blocks(rows)

        # Analyze gaps between meetings
        metrics = self._analyze_fragmentation(meetings, target_date)

        return metrics

    def _detect_meeting_blocks(
        self,
        activity_rows: list[dict],
    ) -> list[TimeBlock]:
        """Detect meeting blocks from activity data.

        Consecutive meeting app usage is grouped into single meeting blocks.
        """
        meetings: list[TimeBlock] = []
        current_meeting: dict | None = None

        for i, row in enumerate(activity_rows):
            app_name = row.get("app_name", "")
            bundle_id = row.get("bundle_id")
            timestamp = datetime.fromisoformat(row["timestamp"])

            is_meeting = self.is_meeting_app(app_name, bundle_id)

            if is_meeting:
                if current_meeting is None:
                    # Start new meeting
                    current_meeting = {
                        "start": timestamp,
                        "end": timestamp,
                        "app_name": app_name,
                    }
                else:
                    # Extend current meeting
                    current_meeting["end"] = timestamp
            else:
                if current_meeting is not None:
                    # End current meeting
                    duration = (
                        current_meeting["end"] - current_meeting["start"]
                    ).total_seconds() / 60.0

                    # Only count if longer than minimum
                    if duration >= MIN_MEETING_DURATION:
                        meetings.append(TimeBlock(
                            start=current_meeting["start"],
                            end=current_meeting["end"],
                            block_type="meeting",
                            app_name=current_meeting["app_name"],
                        ))

                    current_meeting = None

        # Handle meeting that extends to end of data
        if current_meeting is not None:
            duration = (
                current_meeting["end"] - current_meeting["start"]
            ).total_seconds() / 60.0

            if duration >= MIN_MEETING_DURATION:
                meetings.append(TimeBlock(
                    start=current_meeting["start"],
                    end=current_meeting["end"],
                    block_type="meeting",
                    app_name=current_meeting["app_name"],
                ))

        return meetings

    def _analyze_fragmentation(
        self,
        meetings: list[TimeBlock],
        target_date: datetime,
    ) -> FragmentationMetrics:
        """Analyze fragmentation from meeting blocks."""
        metrics = FragmentationMetrics()

        if not meetings:
            # No meetings = no fragmentation
            work_hours = (
                datetime.combine(target_date.date(), self.work_end) -
                datetime.combine(target_date.date(), self.work_start)
            ).total_seconds() / 3600.0
            metrics.focus_hours = work_hours
            metrics.total_usable_minutes = work_hours * 60
            metrics.largest_focus_block_minutes = work_hours * 60
            return metrics

        # Calculate meeting stats
        metrics.total_meetings = len(meetings)
        total_meeting_minutes = sum(m.duration_minutes for m in meetings)
        metrics.total_meeting_minutes = total_meeting_minutes
        metrics.meeting_hours = total_meeting_minutes / 60.0

        if metrics.total_meetings > 0:
            metrics.avg_meeting_duration = (
                total_meeting_minutes / metrics.total_meetings
            )

        # Sort meetings by start time
        meetings = sorted(meetings, key=lambda m: m.start)

        # Analyze gaps between meetings
        gaps: list[TimeBlock] = []

        # Gap before first meeting (from work start)
        work_start_dt = datetime.combine(
            target_date.date(), self.work_start
        )
        if meetings[0].start > work_start_dt:
            gap_minutes = (meetings[0].start - work_start_dt).total_seconds() / 60.0
            gaps.append(TimeBlock(
                start=work_start_dt,
                end=meetings[0].start,
                block_type=self._classify_gap(gap_minutes),
            ))

        # Gaps between meetings
        for i in range(len(meetings) - 1):
            gap_start = meetings[i].end
            gap_end = meetings[i + 1].start
            gap_minutes = (gap_end - gap_start).total_seconds() / 60.0

            if gap_minutes > 0:
                gaps.append(TimeBlock(
                    start=gap_start,
                    end=gap_end,
                    block_type=self._classify_gap(gap_minutes),
                ))

            # Check for back-to-back (< 5 min gap)
            if gap_minutes < 5:
                metrics.back_to_back_meetings += 1

        # Gap after last meeting (until work end)
        work_end_dt = datetime.combine(
            target_date.date(), self.work_end
        )
        if meetings[-1].end < work_end_dt:
            gap_minutes = (work_end_dt - meetings[-1].end).total_seconds() / 60.0
            gaps.append(TimeBlock(
                start=meetings[-1].end,
                end=work_end_dt,
                block_type=self._classify_gap(gap_minutes),
            ))

        # Categorize gaps
        for gap in gaps:
            if gap.block_type == "usable":
                metrics.usable_blocks += 1
                metrics.total_usable_minutes += gap.duration_minutes
                if gap.duration_minutes > metrics.largest_focus_block_minutes:
                    metrics.largest_focus_block_minutes = gap.duration_minutes
            elif gap.block_type == "fragmented":
                metrics.fragmented_blocks += 1
                metrics.total_fragmented_minutes += gap.duration_minutes
            elif gap.block_type == "tiny":
                metrics.tiny_gaps += 1

        # Calculate Swiss Cheese Score
        # Score = fragmented_time / (fragmented_time + usable_time)
        # Higher score = more fragmented (bad)
        total_gap_time = metrics.total_usable_minutes + metrics.total_fragmented_minutes
        if total_gap_time > 0:
            metrics.swiss_cheese_score = (
                metrics.total_fragmented_minutes / total_gap_time
            )

        # Focus hours (usable blocks only)
        metrics.focus_hours = metrics.total_usable_minutes / 60.0

        # Store all blocks for visualization
        metrics.time_blocks = meetings + gaps

        # Check if consolidation is possible
        # If more than 2 meetings with fragmented gaps, consolidation helps
        if metrics.fragmented_blocks >= 2 and metrics.total_meetings >= 2:
            metrics.consolidation_possible = True

        return metrics

    def _classify_gap(self, gap_minutes: float) -> str:
        """Classify a gap between meetings.

        Args:
            gap_minutes: Duration of the gap

        Returns:
            "usable" (30+ min), "fragmented" (5-30 min), or "tiny" (< 5 min)
        """
        if gap_minutes >= 30:
            return "usable"
        elif gap_minutes >= 5:
            return "fragmented"
        else:
            return "tiny"

    async def analyze_week(
        self,
        week_start: datetime | None = None,
    ) -> WeeklyFragmentationMetrics:
        """Analyze meeting fragmentation for a week.

        Args:
            week_start: Start of the week (defaults to most recent Monday)

        Returns:
            WeeklyFragmentationMetrics with daily breakdowns
        """
        if not week_start:
            today = datetime.utcnow()
            # Go back to Monday
            week_start = today - timedelta(days=today.weekday())

        weekly = WeeklyFragmentationMetrics()
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

        best_score = 1.0
        worst_score = 0.0

        for i, day_name in enumerate(day_names):
            day_date = week_start + timedelta(days=i)
            metrics = await self.analyze_day(day_date)

            weekly.days[day_name] = metrics
            weekly.total_meetings += metrics.total_meetings
            weekly.total_meeting_hours += metrics.meeting_hours
            weekly.total_focus_hours += metrics.focus_hours

            # Track best/worst days
            if metrics.swiss_cheese_score < best_score:
                best_score = metrics.swiss_cheese_score
                weekly.best_focus_day = day_name
            if metrics.swiss_cheese_score > worst_score:
                worst_score = metrics.swiss_cheese_score
                weekly.worst_focus_day = day_name

        # Calculate average score
        if weekly.days:
            weekly.avg_swiss_cheese_score = sum(
                d.swiss_cheese_score for d in weekly.days.values()
            ) / len(weekly.days)

        return weekly

    def get_recommendations(
        self,
        metrics: FragmentationMetrics,
    ) -> list[str]:
        """Get recommendations based on fragmentation metrics.

        Args:
            metrics: The fragmentation metrics

        Returns:
            List of actionable recommendations
        """
        recommendations = []

        # High Swiss Cheese Score
        if metrics.swiss_cheese_score > 0.5:
            recommendations.append(
                f"Your day is highly fragmented (score: {metrics.swiss_cheese_score:.2f}). "
                "Consider consolidating meetings into blocks."
            )

        # Many back-to-back meetings
        if metrics.back_to_back_meetings >= 2:
            recommendations.append(
                f"You have {metrics.back_to_back_meetings} back-to-back meetings. "
                "Add buffer time between meetings for context switching."
            )

        # Small focus blocks
        if metrics.largest_focus_block_minutes < 60:
            recommendations.append(
                f"Your largest focus block is only {metrics.largest_focus_block_minutes:.0f} min. "
                "Aim for at least one 2-hour uninterrupted block."
            )

        # Too many meetings
        if metrics.meeting_hours > 4:
            recommendations.append(
                f"You spent {metrics.meeting_hours:.1f} hours in meetings. "
                "Consider declining optional meetings or suggesting async updates."
            )

        # Consolidation possible
        if metrics.consolidation_possible:
            recommendations.append(
                "Multiple short gaps could be consolidated. "
                "Try moving meetings closer together to create larger focus blocks."
            )

        return recommendations
