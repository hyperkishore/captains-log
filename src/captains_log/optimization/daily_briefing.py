"""Daily Briefing Generator.

Generates morning briefings that help users start their day
with awareness of yesterday's patterns and today's focus.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from captains_log.optimization.schemas import DEALCategory
from captains_log.optimization.deal_classifier import DEALClassifier, DEALMetrics
from captains_log.optimization.interrupt_detector import InterruptDetector, InterruptMetrics
from captains_log.optimization.context_switch_analyzer import (
    ContextSwitchAnalyzer,
    ContextSwitchMetrics,
)
from captains_log.optimization.meeting_fragmentation import (
    MeetingFragmentationAnalyzer,
    FragmentationMetrics,
)

logger = logging.getLogger(__name__)


@dataclass
class DailyWin:
    """A positive achievement from yesterday."""

    category: str  # "deep_work", "focus", "interrupts", "meetings"
    message: str
    improvement_percent: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "message": self.message,
            "improvement_percent": self.improvement_percent,
        }


@dataclass
class QuickWin:
    """A quick action the user can take today."""

    action: str
    estimated_benefit: str
    priority: str  # "high", "medium", "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "estimated_benefit": self.estimated_benefit,
            "priority": self.priority,
        }


@dataclass
class DailyBriefing:
    """The complete daily briefing."""

    date: datetime
    greeting: str

    # Yesterday's summary
    yesterday_deep_work_hours: float = 0.0
    yesterday_interrupts: int = 0
    yesterday_context_switches: int = 0
    yesterday_meeting_hours: float = 0.0

    # Wins from yesterday
    wins: list[DailyWin] = field(default_factory=list)

    # Today's focus
    focus_suggestions: list[str] = field(default_factory=list)

    # Quick wins for today
    quick_wins: list[QuickWin] = field(default_factory=list)

    # Metrics summary
    deal_breakdown: dict[str, float] = field(default_factory=dict)

    # Week context
    week_progress: str = ""
    days_until_weekend: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "greeting": self.greeting,
            "yesterday_deep_work_hours": self.yesterday_deep_work_hours,
            "yesterday_interrupts": self.yesterday_interrupts,
            "yesterday_context_switches": self.yesterday_context_switches,
            "yesterday_meeting_hours": self.yesterday_meeting_hours,
            "wins": [w.to_dict() for w in self.wins],
            "focus_suggestions": self.focus_suggestions,
            "quick_wins": [q.to_dict() for q in self.quick_wins],
            "deal_breakdown": self.deal_breakdown,
            "week_progress": self.week_progress,
            "days_until_weekend": self.days_until_weekend,
        }

    def to_text(self) -> str:
        """Generate human-readable briefing text."""
        lines = [
            f"# {self.greeting}",
            "",
        ]

        # Yesterday's wins
        if self.wins:
            lines.append("## Yesterday's Wins")
            for win in self.wins:
                improvement = ""
                if win.improvement_percent:
                    improvement = f" (+{win.improvement_percent:.0f}%)"
                lines.append(f"- {win.message}{improvement}")
            lines.append("")

        # Yesterday's summary
        lines.append("## Yesterday's Summary")
        lines.append(f"- Deep work: {self.yesterday_deep_work_hours:.1f} hours")
        lines.append(f"- Interrupts: {self.yesterday_interrupts}")
        lines.append(f"- Context switches: {self.yesterday_context_switches}")
        lines.append(f"- Meetings: {self.yesterday_meeting_hours:.1f} hours")
        lines.append("")

        # DEAL breakdown
        if self.deal_breakdown:
            lines.append("## Time Distribution")
            for category, minutes in self.deal_breakdown.items():
                hours = minutes / 60.0
                lines.append(f"- {category.title()}: {hours:.1f}h")
            lines.append("")

        # Today's focus
        if self.focus_suggestions:
            lines.append("## Today's Focus")
            for suggestion in self.focus_suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")

        # Quick wins
        if self.quick_wins:
            lines.append("## Quick Wins")
            for qw in self.quick_wins:
                lines.append(f"- {qw.action}")
                lines.append(f"  → {qw.estimated_benefit}")
            lines.append("")

        # Week context
        if self.week_progress:
            lines.append(f"_{self.week_progress}_")

        return "\n".join(lines)


class DailyBriefingGenerator:
    """Generates personalized daily briefings."""

    def __init__(self, db: Any | None = None):
        """Initialize the briefing generator.

        Args:
            db: Database instance
        """
        self.db = db

        # Initialize analyzers
        self.deal_classifier = DEALClassifier(db=db)
        self.interrupt_detector = InterruptDetector(db=db)
        self.context_switch_analyzer = ContextSwitchAnalyzer(db=db)
        self.fragmentation_analyzer = MeetingFragmentationAnalyzer(db=db)

        # Historical averages for comparison
        self._avg_deep_work_hours: float = 2.0
        self._avg_interrupts: int = 20
        self._avg_context_switches: int = 50

    async def generate_briefing(
        self,
        target_date: datetime | None = None,
    ) -> DailyBriefing:
        """Generate the daily briefing.

        Args:
            target_date: The date for the briefing (defaults to today)

        Returns:
            DailyBriefing with all components
        """
        target_date = target_date or datetime.utcnow()
        yesterday = target_date - timedelta(days=1)

        # Generate greeting
        greeting = self._generate_greeting(target_date)

        briefing = DailyBriefing(
            date=target_date,
            greeting=greeting,
        )

        # Get yesterday's metrics
        if self.db:
            await self._populate_yesterday_metrics(briefing, yesterday)

        # Generate wins
        briefing.wins = self._generate_wins(briefing)

        # Generate focus suggestions
        briefing.focus_suggestions = self._generate_focus_suggestions(
            target_date, briefing
        )

        # Generate quick wins
        briefing.quick_wins = self._generate_quick_wins(briefing)

        # Week context
        briefing.days_until_weekend = (5 - target_date.weekday()) % 7
        if briefing.days_until_weekend == 0:
            briefing.days_until_weekend = 7  # Today is Saturday
        briefing.week_progress = self._generate_week_progress(
            target_date, briefing.days_until_weekend
        )

        # Save briefing to database
        await self._save_briefing(briefing)

        return briefing

    def _generate_greeting(self, date: datetime) -> str:
        """Generate a time-appropriate greeting."""
        hour = date.hour
        day_name = date.strftime("%A")

        if hour < 12:
            time_greeting = "Good morning"
        elif hour < 17:
            time_greeting = "Good afternoon"
        else:
            time_greeting = "Good evening"

        return f"{time_greeting}! Here's your {day_name} briefing."

    async def _populate_yesterday_metrics(
        self,
        briefing: DailyBriefing,
        yesterday: datetime,
    ) -> None:
        """Populate briefing with yesterday's metrics."""
        # DEAL classification
        deal_metrics = await self.deal_classifier.get_daily_metrics(yesterday)
        briefing.deal_breakdown = {
            "leverage": deal_metrics.leverage_minutes,
            "delegate": deal_metrics.delegate_minutes,
            "eliminate": deal_metrics.eliminate_minutes,
            "automate": deal_metrics.automate_minutes,
        }
        briefing.yesterday_deep_work_hours = deal_metrics.leverage_minutes / 60.0

        # Interrupts
        interrupt_metrics = await self.interrupt_detector.get_daily_metrics(yesterday)
        briefing.yesterday_interrupts = interrupt_metrics.total_interrupts

        # Context switches
        switch_metrics = await self.context_switch_analyzer.get_daily_metrics(yesterday)
        briefing.yesterday_context_switches = switch_metrics.total_switches

        # Meetings
        frag_metrics = await self.fragmentation_analyzer.analyze_day(yesterday)
        briefing.yesterday_meeting_hours = frag_metrics.meeting_hours

        # Update running averages (for comparison)
        await self._update_averages(yesterday)

    async def _update_averages(self, date: datetime) -> None:
        """Update running averages from historical data."""
        if not self.db:
            return

        # Get last 7 days of data for averages
        week_ago = date - timedelta(days=7)

        # This would query historical metrics
        # For now, use defaults - could be enhanced with actual historical queries
        pass

    def _generate_wins(self, briefing: DailyBriefing) -> list[DailyWin]:
        """Generate wins based on yesterday's performance."""
        wins = []

        # Deep work win
        if briefing.yesterday_deep_work_hours >= self._avg_deep_work_hours:
            improvement = (
                (briefing.yesterday_deep_work_hours - self._avg_deep_work_hours)
                / self._avg_deep_work_hours * 100
            ) if self._avg_deep_work_hours > 0 else 0

            wins.append(DailyWin(
                category="deep_work",
                message=f"{briefing.yesterday_deep_work_hours:.1f}h of deep work",
                improvement_percent=improvement if improvement > 0 else None,
            ))

        # Low interrupts win
        if briefing.yesterday_interrupts < self._avg_interrupts:
            improvement = (
                (self._avg_interrupts - briefing.yesterday_interrupts)
                / self._avg_interrupts * 100
            ) if self._avg_interrupts > 0 else 0

            wins.append(DailyWin(
                category="focus",
                message=f"Only {briefing.yesterday_interrupts} interrupts",
                improvement_percent=improvement if improvement > 0 else None,
            ))

        # Low meeting hours
        if briefing.yesterday_meeting_hours < 2:
            wins.append(DailyWin(
                category="meetings",
                message=f"Only {briefing.yesterday_meeting_hours:.1f}h in meetings",
            ))

        return wins

    def _generate_focus_suggestions(
        self,
        today: datetime,
        briefing: DailyBriefing,
    ) -> list[str]:
        """Generate focus suggestions for today."""
        suggestions = []
        hour = today.hour

        # Morning suggestions
        if hour < 12:
            suggestions.append("Protect your morning for deep work")

            if briefing.yesterday_interrupts > 15:
                suggestions.append(
                    "Consider checking Slack only at 10am, 1pm, and 4pm"
                )

        # Based on yesterday's patterns
        if briefing.yesterday_deep_work_hours < 2:
            suggestions.append(
                "Block 2 hours for uninterrupted work today"
            )

        if briefing.yesterday_meeting_hours > 4:
            suggestions.append(
                "Decline optional meetings - you need focus time"
            )

        # Day-specific suggestions
        day_name = today.strftime("%A")
        if day_name == "Monday":
            suggestions.append(
                "Set your week's priorities before diving into tasks"
            )
        elif day_name == "Friday":
            suggestions.append(
                "Use Friday afternoon for weekly review and planning"
            )

        return suggestions[:3]  # Limit to 3 suggestions

    def _generate_quick_wins(self, briefing: DailyBriefing) -> list[QuickWin]:
        """Generate quick wins based on patterns."""
        quick_wins = []

        # High interrupt count
        if briefing.yesterday_interrupts > 20:
            quick_wins.append(QuickWin(
                action="Batch your Slack/email checks to 3 times today",
                estimated_benefit=f"Save ~{briefing.yesterday_interrupts * 2} minutes",
                priority="high",
            ))

        # High eliminate time
        eliminate_mins = briefing.deal_breakdown.get("eliminate", 0)
        if eliminate_mins > 60:
            quick_wins.append(QuickWin(
                action="Limit social media/news to lunch break only",
                estimated_benefit=f"Reclaim {eliminate_mins:.0f} minutes",
                priority="high",
            ))

        # High context switch cost
        if briefing.yesterday_context_switches > 50:
            quick_wins.append(QuickWin(
                action="Work in 45-min focused blocks with 5-min breaks",
                estimated_benefit="Reduce context switch overhead by 30%",
                priority="medium",
            ))

        # Low deep work
        if briefing.yesterday_deep_work_hours < 2:
            quick_wins.append(QuickWin(
                action="Start your day with 90 minutes of deep work",
                estimated_benefit="Front-load high-value work",
                priority="high",
            ))

        return quick_wins[:3]  # Limit to 3

    def _generate_week_progress(
        self,
        today: datetime,
        days_until_weekend: int,
    ) -> str:
        """Generate week progress context."""
        day_name = today.strftime("%A")

        if day_name == "Monday":
            return "Fresh week ahead - set your intentions"
        elif day_name == "Friday":
            return "Last push of the week - finish strong"
        elif days_until_weekend == 1:
            return "Almost there - one more day until the weekend"
        elif days_until_weekend <= 3:
            return f"{days_until_weekend} days until the weekend"
        else:
            return f"Week in progress - {days_until_weekend} days until weekend"

    async def _save_briefing(self, briefing: DailyBriefing) -> int:
        """Save briefing to database."""
        if not self.db:
            return 0

        try:
            return await self.db.insert(
                "daily_briefings",
                {
                    "date": briefing.date.strftime("%Y-%m-%d"),
                    "content": json.dumps(briefing.to_dict()),
                    "created_at": datetime.utcnow().isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to save briefing: {e}")
            return 0

    async def get_briefing(
        self,
        date: datetime | None = None,
    ) -> DailyBriefing | None:
        """Get a saved briefing from the database.

        Args:
            date: The date to retrieve (defaults to today)

        Returns:
            DailyBriefing if found, None otherwise
        """
        if not self.db:
            return None

        date = date or datetime.utcnow()
        date_str = date.strftime("%Y-%m-%d")

        row = await self.db.fetch_one(
            "SELECT * FROM daily_briefings WHERE date = ?",
            (date_str,),
        )

        if not row:
            return None

        content = json.loads(row["content"])
        return DailyBriefing(
            date=datetime.fromisoformat(content["date"]),
            greeting=content["greeting"],
            yesterday_deep_work_hours=content.get("yesterday_deep_work_hours", 0),
            yesterday_interrupts=content.get("yesterday_interrupts", 0),
            yesterday_context_switches=content.get("yesterday_context_switches", 0),
            yesterday_meeting_hours=content.get("yesterday_meeting_hours", 0),
            wins=[DailyWin(**w) for w in content.get("wins", [])],
            focus_suggestions=content.get("focus_suggestions", []),
            quick_wins=[QuickWin(**q) for q in content.get("quick_wins", [])],
            deal_breakdown=content.get("deal_breakdown", {}),
            week_progress=content.get("week_progress", ""),
            days_until_weekend=content.get("days_until_weekend", 0),
        )

    async def mark_as_viewed(self, date: datetime | None = None) -> None:
        """Mark a briefing as viewed.

        Args:
            date: The date of the briefing to mark
        """
        if not self.db:
            return

        date = date or datetime.utcnow()
        date_str = date.strftime("%Y-%m-%d")

        await self.db.execute(
            "UPDATE daily_briefings SET viewed_at = ? WHERE date = ?",
            (datetime.utcnow().isoformat(), date_str),
        )
