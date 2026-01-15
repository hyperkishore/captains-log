"""Focus score calculator for activity analysis."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# App categories for focus analysis
FOCUS_APPS = {
    # High focus: coding/development
    "com.microsoft.VSCode",
    "com.apple.dt.Xcode",
    "com.jetbrains.intellij",
    "com.jetbrains.pycharm",
    "com.sublimetext.4",
    "com.sublimetext.3",
    "dev.zed.Zed",
    "com.cursor.Cursor",
    "io.neovide.neovide",
    "com.googlecode.iterm2",
    "com.apple.Terminal",
    # High focus: writing
    "com.apple.iWork.Pages",
    "com.microsoft.Word",
    "com.ulysses.mac",
    "com.ia.writer",
    "com.google.Chrome",  # Could be docs
    "org.mozilla.firefox",
    "com.apple.Safari",
}

COMMUNICATION_APPS = {
    "com.tinyspeck.slackmacgap",
    "com.hnc.Discord",
    "com.apple.MobileSMS",
    "com.apple.mail",
    "com.readdle.smartemail-Mac",
    "us.zoom.xos",
    "com.microsoft.teams",
}

ENTERTAINMENT_APPS = {
    "com.spotify.client",
    "com.apple.Music",
    "tv.plex.player",
    "com.apple.TV",
    "com.twitter.twitter-mac",
    "com.facebook.Facebook",
}


@dataclass
class FocusMetrics:
    """Detailed focus metrics for a time period."""

    focus_score: int  # 1-10
    context_switches: int
    primary_app: str
    primary_app_percentage: float
    unique_apps: int
    total_events: int
    idle_percentage: float
    engagement_score: float
    focus_category: str  # "deep_work", "moderate", "fragmented", "distracted"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "focus_score": self.focus_score,
            "context_switches": self.context_switches,
            "primary_app": self.primary_app,
            "primary_app_percentage": self.primary_app_percentage,
            "unique_apps": self.unique_apps,
            "total_events": self.total_events,
            "idle_percentage": self.idle_percentage,
            "engagement_score": self.engagement_score,
            "focus_category": self.focus_category,
        }


class FocusCalculator:
    """Calculate focus scores from activity data.

    Focus Score Guidelines:
    - 10: Single-task deep work, no switches, sustained engagement
    - 8-9: Primarily focused with minimal, relevant switches
    - 6-7: Moderate focus with some context switching
    - 4-5: Fragmented attention, frequent switches between unrelated apps
    - 1-3: Highly distracted, rapid switching, no clear focus
    """

    def __init__(
        self,
        focus_apps: set[str] | None = None,
        communication_apps: set[str] | None = None,
        entertainment_apps: set[str] | None = None,
    ):
        """Initialize focus calculator.

        Args:
            focus_apps: Bundle IDs considered "focus" apps.
            communication_apps: Bundle IDs considered communication apps.
            entertainment_apps: Bundle IDs considered entertainment apps.
        """
        self.focus_apps = focus_apps or FOCUS_APPS
        self.communication_apps = communication_apps or COMMUNICATION_APPS
        self.entertainment_apps = entertainment_apps or ENTERTAINMENT_APPS

    def calculate(self, activity_data: list[dict[str, Any]]) -> FocusMetrics:
        """Calculate focus metrics from activity data.

        Args:
            activity_data: List of activity events.

        Returns:
            FocusMetrics with detailed analysis.
        """
        if not activity_data:
            return FocusMetrics(
                focus_score=5,
                context_switches=0,
                primary_app="Unknown",
                primary_app_percentage=0.0,
                unique_apps=0,
                total_events=0,
                idle_percentage=0.0,
                engagement_score=0.0,
                focus_category="unknown",
            )

        # Count apps
        apps = [e.get("app_name", "Unknown") for e in activity_data]
        bundle_ids = [e.get("bundle_id", "") for e in activity_data]
        app_counts = Counter(apps)

        # Primary app
        primary_app, primary_count = app_counts.most_common(1)[0]
        primary_percentage = primary_count / len(activity_data) * 100

        # Unique apps
        unique_apps = len(app_counts)

        # Context switches
        context_switches = self._count_context_switches(activity_data)

        # Idle percentage
        idle_events = sum(
            1 for e in activity_data
            if e.get("idle_status") in ("AWAY", "IDLE_BUT_PRESENT")
        )
        idle_percentage = idle_events / len(activity_data) * 100

        # Engagement score (based on input activity)
        engagement_score = self._calculate_engagement(activity_data)

        # Calculate focus score
        focus_score = self._calculate_focus_score(
            activity_data=activity_data,
            bundle_ids=bundle_ids,
            context_switches=context_switches,
            primary_percentage=primary_percentage,
            idle_percentage=idle_percentage,
            engagement_score=engagement_score,
        )

        # Categorize focus level
        focus_category = self._categorize_focus(focus_score, context_switches)

        return FocusMetrics(
            focus_score=focus_score,
            context_switches=context_switches,
            primary_app=primary_app,
            primary_app_percentage=primary_percentage,
            unique_apps=unique_apps,
            total_events=len(activity_data),
            idle_percentage=idle_percentage,
            engagement_score=engagement_score,
            focus_category=focus_category,
        )

    def _count_context_switches(self, activity_data: list[dict]) -> int:
        """Count context switches (app changes)."""
        if len(activity_data) < 2:
            return 0

        switches = 0
        prev_bundle = activity_data[0].get("bundle_id")

        for event in activity_data[1:]:
            curr_bundle = event.get("bundle_id")
            if curr_bundle and curr_bundle != prev_bundle:
                switches += 1
                prev_bundle = curr_bundle

        return switches

    def _calculate_engagement(self, activity_data: list[dict]) -> float:
        """Calculate engagement score from input activity."""
        total_keystrokes = sum(e.get("keystrokes", 0) for e in activity_data)
        total_clicks = sum(e.get("mouse_clicks", 0) for e in activity_data)
        total_scrolls = sum(e.get("scroll_events", 0) for e in activity_data)

        # Weight: keystrokes are more engaging than clicks/scrolls
        engagement = (total_keystrokes * 1.0 + total_clicks * 0.5 + total_scrolls * 0.2)

        # Normalize to 0-100 scale
        # Assume ~100 keystrokes per 5 min is average engagement
        normalized = min(100, engagement / len(activity_data) * 10 if activity_data else 0)

        return round(normalized, 1)

    def _calculate_focus_score(
        self,
        activity_data: list[dict],
        bundle_ids: list[str],
        context_switches: int,
        primary_percentage: float,
        idle_percentage: float,
        engagement_score: float,
    ) -> int:
        """Calculate the final focus score (1-10)."""
        score = 10.0

        # Factor 1: Context switches (biggest impact)
        # 0 switches = no deduction, 10+ = -4 points
        switch_penalty = min(4.0, context_switches * 0.4)
        score -= switch_penalty

        # Factor 2: App diversity
        # Single app = no deduction, many apps = up to -2 points
        unique_count = len(set(bundle_ids))
        if unique_count > 5:
            score -= 2.0
        elif unique_count > 3:
            score -= 1.0

        # Factor 3: Primary app concentration
        # >80% in one app = bonus, <40% = penalty
        if primary_percentage > 80:
            score += 0.5
        elif primary_percentage < 40:
            score -= 1.0

        # Factor 4: Idle time
        # Low idle = focused, high idle = away/distracted
        if idle_percentage > 50:
            score -= 2.0
        elif idle_percentage > 30:
            score -= 1.0

        # Factor 5: App type analysis
        # Entertainment apps reduce score
        entertainment_time = sum(
            1 for b in bundle_ids
            if any(b.startswith(e.replace("*", "")) for e in self.entertainment_apps)
        )
        entertainment_pct = entertainment_time / len(bundle_ids) * 100 if bundle_ids else 0

        if entertainment_pct > 30:
            score -= 1.5
        elif entertainment_pct > 15:
            score -= 0.5

        # Factor 6: Communication time
        # Some communication is necessary, but too much = distraction
        comm_time = sum(
            1 for b in bundle_ids
            if b in self.communication_apps
        )
        comm_pct = comm_time / len(bundle_ids) * 100 if bundle_ids else 0

        if comm_pct > 60:
            score -= 1.5
        elif comm_pct > 40:
            score -= 0.5

        # Factor 7: Engagement bonus
        # High engagement = more focused work
        if engagement_score > 50:
            score += 0.5

        # Clamp to 1-10
        return max(1, min(10, round(score)))

    def _categorize_focus(self, focus_score: int, context_switches: int) -> str:
        """Categorize focus level."""
        if focus_score >= 8:
            return "deep_work"
        elif focus_score >= 6:
            return "moderate"
        elif focus_score >= 4:
            return "fragmented"
        else:
            return "distracted"

    def calculate_period_focus(
        self,
        activity_data: list[dict[str, Any]],
        period_minutes: int = 5,
    ) -> list[FocusMetrics]:
        """Calculate focus for each period in a longer time range.

        Args:
            activity_data: All activity events.
            period_minutes: Period length in minutes.

        Returns:
            List of FocusMetrics for each period.
        """
        if not activity_data:
            return []

        # Sort by timestamp
        sorted_data = sorted(
            activity_data,
            key=lambda e: e.get("timestamp", ""),
        )

        # Group into periods
        periods: list[list[dict]] = []
        current_period: list[dict] = []

        period_start = None
        period_delta = timedelta(minutes=period_minutes)

        for event in sorted_data:
            timestamp_str = event.get("timestamp", "")
            if not timestamp_str:
                continue

            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                continue

            if period_start is None:
                period_start = timestamp
                current_period = [event]
            elif timestamp - period_start < period_delta:
                current_period.append(event)
            else:
                # Save current period and start new one
                if current_period:
                    periods.append(current_period)
                period_start = timestamp
                current_period = [event]

        # Don't forget the last period
        if current_period:
            periods.append(current_period)

        # Calculate focus for each period
        return [self.calculate(period) for period in periods]

    def get_daily_focus_summary(
        self, metrics_list: list[FocusMetrics]
    ) -> dict[str, Any]:
        """Summarize focus metrics for a day.

        Args:
            metrics_list: List of FocusMetrics from the day.

        Returns:
            Summary statistics.
        """
        if not metrics_list:
            return {
                "average_focus": 0,
                "total_context_switches": 0,
                "deep_work_periods": 0,
                "fragmented_periods": 0,
                "best_focus_score": 0,
                "worst_focus_score": 0,
            }

        focus_scores = [m.focus_score for m in metrics_list]
        switches = [m.context_switches for m in metrics_list]
        categories = Counter(m.focus_category for m in metrics_list)

        return {
            "average_focus": round(sum(focus_scores) / len(focus_scores), 1),
            "total_context_switches": sum(switches),
            "deep_work_periods": categories.get("deep_work", 0),
            "moderate_periods": categories.get("moderate", 0),
            "fragmented_periods": categories.get("fragmented", 0),
            "distracted_periods": categories.get("distracted", 0),
            "best_focus_score": max(focus_scores),
            "worst_focus_score": min(focus_scores),
            "total_periods": len(metrics_list),
        }
