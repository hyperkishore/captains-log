"""Weekly Report Generator.

Generates comprehensive weekly reports with trends, insights,
and actionable recommendations based on time optimization data.
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
    WeeklyFragmentationMetrics,
)

logger = logging.getLogger(__name__)


@dataclass
class WeeklyTrend:
    """Trend data comparing this week to previous."""

    metric_name: str
    current_value: float
    previous_value: float
    change_percent: float
    is_improvement: bool
    unit: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "previous_value": self.previous_value,
            "change_percent": self.change_percent,
            "is_improvement": self.is_improvement,
            "unit": self.unit,
        }


@dataclass
class WeeklyInsight:
    """An insight derived from weekly data."""

    category: str  # "pattern", "opportunity", "achievement", "warning"
    title: str
    description: str
    impact: str  # "high", "medium", "low"
    data_points: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "impact": self.impact,
            "data_points": self.data_points,
        }


@dataclass
class WeeklyRecommendation:
    """A recommendation for the upcoming week."""

    title: str
    action: str
    estimated_impact: str
    priority: int  # 1-3, 1 = highest
    category: str  # "eliminate", "automate", "delegate", "protect"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "action": self.action,
            "estimated_impact": self.estimated_impact,
            "priority": self.priority,
            "category": self.category,
        }


@dataclass
class TimeSavingsProgress:
    """Progress toward time savings goal."""

    goal_percent: float  # Target (e.g., 20%)
    baseline_hours: float  # Baseline hours per week
    current_hours: float  # Current tracked hours
    eliminated_hours: float  # Time eliminated
    automated_hours: float  # Time saved through automation/batching
    total_saved_percent: float  # Actual savings percentage
    on_track: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_percent": self.goal_percent,
            "baseline_hours": self.baseline_hours,
            "current_hours": self.current_hours,
            "eliminated_hours": self.eliminated_hours,
            "automated_hours": self.automated_hours,
            "total_saved_percent": self.total_saved_percent,
            "on_track": self.on_track,
        }


@dataclass
class WeeklyReport:
    """Complete weekly optimization report."""

    week_start: datetime
    week_end: datetime
    generated_at: datetime

    # Summary stats
    total_tracked_hours: float = 0.0
    total_meetings: int = 0
    total_interrupts: int = 0
    total_context_switches: int = 0

    # Time distribution (DEAL)
    leverage_hours: float = 0.0
    delegate_hours: float = 0.0
    eliminate_hours: float = 0.0
    automate_hours: float = 0.0

    # Daily breakdown
    daily_stats: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Trends vs last week
    trends: list[WeeklyTrend] = field(default_factory=list)

    # Insights
    insights: list[WeeklyInsight] = field(default_factory=list)

    # Recommendations
    recommendations: list[WeeklyRecommendation] = field(default_factory=list)

    # Time savings progress
    savings_progress: TimeSavingsProgress | None = None

    # Meeting fragmentation
    avg_swiss_cheese_score: float = 0.0
    best_focus_day: str = ""
    worst_focus_day: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "total_tracked_hours": self.total_tracked_hours,
            "total_meetings": self.total_meetings,
            "total_interrupts": self.total_interrupts,
            "total_context_switches": self.total_context_switches,
            "leverage_hours": self.leverage_hours,
            "delegate_hours": self.delegate_hours,
            "eliminate_hours": self.eliminate_hours,
            "automate_hours": self.automate_hours,
            "daily_stats": self.daily_stats,
            "trends": [t.to_dict() for t in self.trends],
            "insights": [i.to_dict() for i in self.insights],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "savings_progress": self.savings_progress.to_dict() if self.savings_progress else None,
            "avg_swiss_cheese_score": self.avg_swiss_cheese_score,
            "best_focus_day": self.best_focus_day,
            "worst_focus_day": self.worst_focus_day,
        }

    def to_text(self) -> str:
        """Generate human-readable report."""
        lines = [
            "=" * 60,
            "WEEKLY TIME OPTIMIZATION REPORT",
            f"Week of {self.week_start.strftime('%B %d')} - {self.week_end.strftime('%B %d, %Y')}",
            "=" * 60,
            "",
        ]

        # Time Distribution
        lines.append("## Time Distribution")
        lines.append(f"- Leverage (high-value): {self.leverage_hours:.1f}h ({self._percent(self.leverage_hours)}%)")
        lines.append(f"- Delegate (admin): {self.delegate_hours:.1f}h ({self._percent(self.delegate_hours)}%)")
        lines.append(f"- Eliminate (distractions): {self.eliminate_hours:.1f}h ({self._percent(self.eliminate_hours)}%)")
        lines.append(f"- Automate (repetitive): {self.automate_hours:.1f}h ({self._percent(self.automate_hours)}%)")
        lines.append("")

        # Key Stats
        lines.append("## Key Stats")
        lines.append(f"- Total tracked: {self.total_tracked_hours:.1f} hours")
        lines.append(f"- Meetings: {self.total_meetings}")
        lines.append(f"- Interrupts: {self.total_interrupts}")
        lines.append(f"- Context switches: {self.total_context_switches}")
        lines.append("")

        # Trends
        if self.trends:
            lines.append("## vs. Last Week")
            for trend in self.trends:
                direction = "+" if trend.change_percent > 0 else ""
                status = "✓" if trend.is_improvement else "✗"
                lines.append(
                    f"{status} {trend.metric_name}: {direction}{trend.change_percent:.0f}%"
                )
            lines.append("")

        # Time Savings Progress
        if self.savings_progress:
            lines.append("## Time Savings Progress")
            lines.append(f"Goal: {self.savings_progress.goal_percent}%")
            lines.append(f"Actual: {self.savings_progress.total_saved_percent:.1f}%")
            status = "On track! 🎯" if self.savings_progress.on_track else "Needs attention"
            lines.append(f"Status: {status}")
            lines.append("")

        # Focus Quality
        lines.append("## Focus Quality")
        lines.append(f"- Swiss cheese score: {self.avg_swiss_cheese_score:.2f}")
        lines.append(f"- Best focus day: {self.best_focus_day}")
        lines.append(f"- Worst focus day: {self.worst_focus_day}")
        lines.append("")

        # Insights
        if self.insights:
            lines.append("## Key Insights")
            for insight in self.insights:
                emoji = {"pattern": "📊", "opportunity": "💡", "achievement": "🏆", "warning": "⚠️"}
                lines.append(f"{emoji.get(insight.category, '•')} {insight.title}")
                lines.append(f"   {insight.description}")
            lines.append("")

        # Recommendations
        if self.recommendations:
            lines.append("## Top Recommendations")
            for i, rec in enumerate(self.recommendations[:3], 1):
                lines.append(f"{i}. {rec.title}")
                lines.append(f"   → {rec.action}")
                lines.append(f"   Est. impact: {rec.estimated_impact}")
            lines.append("")

        return "\n".join(lines)

    def _percent(self, hours: float) -> int:
        """Calculate percentage of total hours."""
        if self.total_tracked_hours == 0:
            return 0
        return int((hours / self.total_tracked_hours) * 100)


class WeeklyReportGenerator:
    """Generates comprehensive weekly reports."""

    def __init__(
        self,
        db: Any | None = None,
        target_savings_percent: float = 20.0,
    ):
        """Initialize the report generator.

        Args:
            db: Database instance
            target_savings_percent: Target time savings (default 20%)
        """
        self.db = db
        self.target_savings_percent = target_savings_percent

        # Initialize analyzers
        self.deal_classifier = DEALClassifier(db=db)
        self.interrupt_detector = InterruptDetector(db=db)
        self.context_switch_analyzer = ContextSwitchAnalyzer(db=db)
        self.fragmentation_analyzer = MeetingFragmentationAnalyzer(db=db)

    async def generate_report(
        self,
        week_start: datetime | None = None,
    ) -> WeeklyReport:
        """Generate a weekly report.

        Args:
            week_start: Start of the week (defaults to most recent Monday)

        Returns:
            Complete WeeklyReport
        """
        if not week_start:
            today = datetime.utcnow()
            # Go back to Monday
            week_start = today - timedelta(days=today.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        week_end = week_start + timedelta(days=6)

        report = WeeklyReport(
            week_start=week_start,
            week_end=week_end,
            generated_at=datetime.utcnow(),
        )

        if self.db:
            # Gather daily metrics
            await self._gather_daily_metrics(report, week_start)

            # Calculate trends
            previous_week_start = week_start - timedelta(days=7)
            report.trends = await self._calculate_trends(
                week_start, previous_week_start
            )

            # Analyze fragmentation
            frag_metrics = await self.fragmentation_analyzer.analyze_week(week_start)
            report.avg_swiss_cheese_score = frag_metrics.avg_swiss_cheese_score
            report.best_focus_day = frag_metrics.best_focus_day
            report.worst_focus_day = frag_metrics.worst_focus_day
            report.total_meetings = frag_metrics.total_meetings

        # Generate insights
        report.insights = self._generate_insights(report)

        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        # Calculate savings progress
        report.savings_progress = self._calculate_savings_progress(report)

        # Save report
        await self._save_report(report)

        return report

    async def _gather_daily_metrics(
        self,
        report: WeeklyReport,
        week_start: datetime,
    ) -> None:
        """Gather metrics for each day of the week."""
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

        for i, day_name in enumerate(day_names):
            day_date = week_start + timedelta(days=i)

            # Get DEAL metrics
            deal_metrics = await self.deal_classifier.get_daily_metrics(day_date)

            # Get interrupt metrics
            interrupt_metrics = await self.interrupt_detector.get_daily_metrics(day_date)

            # Get switch metrics
            switch_metrics = await self.context_switch_analyzer.get_daily_metrics(day_date)

            # Store daily stats
            report.daily_stats[day_name] = {
                "leverage_minutes": deal_metrics.leverage_minutes,
                "delegate_minutes": deal_metrics.delegate_minutes,
                "eliminate_minutes": deal_metrics.eliminate_minutes,
                "automate_minutes": deal_metrics.automate_minutes,
                "interrupts": interrupt_metrics.total_interrupts,
                "context_switches": switch_metrics.total_switches,
            }

            # Aggregate to weekly totals
            report.leverage_hours += deal_metrics.leverage_minutes / 60.0
            report.delegate_hours += deal_metrics.delegate_minutes / 60.0
            report.eliminate_hours += deal_metrics.eliminate_minutes / 60.0
            report.automate_hours += deal_metrics.automate_minutes / 60.0
            report.total_interrupts += interrupt_metrics.total_interrupts
            report.total_context_switches += switch_metrics.total_switches

        report.total_tracked_hours = (
            report.leverage_hours + report.delegate_hours +
            report.eliminate_hours + report.automate_hours
        )

    async def _calculate_trends(
        self,
        current_week: datetime,
        previous_week: datetime,
    ) -> list[WeeklyTrend]:
        """Calculate trends comparing two weeks."""
        trends = []

        # Get metrics for both weeks
        current_leverage = 0.0
        current_interrupts = 0
        previous_leverage = 0.0
        previous_interrupts = 0

        for i in range(5):  # Mon-Fri
            # Current week
            day = current_week + timedelta(days=i)
            deal = await self.deal_classifier.get_daily_metrics(day)
            interrupt = await self.interrupt_detector.get_daily_metrics(day)
            current_leverage += deal.leverage_minutes / 60.0
            current_interrupts += interrupt.total_interrupts

            # Previous week
            prev_day = previous_week + timedelta(days=i)
            prev_deal = await self.deal_classifier.get_daily_metrics(prev_day)
            prev_interrupt = await self.interrupt_detector.get_daily_metrics(prev_day)
            previous_leverage += prev_deal.leverage_minutes / 60.0
            previous_interrupts += prev_interrupt.total_interrupts

        # Deep work trend
        if previous_leverage > 0:
            change = ((current_leverage - previous_leverage) / previous_leverage) * 100
            trends.append(WeeklyTrend(
                metric_name="Deep work hours",
                current_value=current_leverage,
                previous_value=previous_leverage,
                change_percent=change,
                is_improvement=change > 0,
                unit="hours",
            ))

        # Interrupts trend
        if previous_interrupts > 0:
            change = ((current_interrupts - previous_interrupts) / previous_interrupts) * 100
            trends.append(WeeklyTrend(
                metric_name="Interrupts",
                current_value=current_interrupts,
                previous_value=previous_interrupts,
                change_percent=change,
                is_improvement=change < 0,  # Fewer is better
                unit="count",
            ))

        return trends

    def _generate_insights(self, report: WeeklyReport) -> list[WeeklyInsight]:
        """Generate insights from report data."""
        insights = []

        # High leverage ratio insight
        if report.total_tracked_hours > 0:
            leverage_ratio = report.leverage_hours / report.total_tracked_hours
            if leverage_ratio >= 0.5:
                insights.append(WeeklyInsight(
                    category="achievement",
                    title="Strong Focus Week",
                    description=f"You spent {leverage_ratio*100:.0f}% of your time on high-value work",
                    impact="high",
                    data_points=[f"{report.leverage_hours:.1f} hours of deep work"],
                ))
            elif leverage_ratio < 0.3:
                insights.append(WeeklyInsight(
                    category="warning",
                    title="Low Deep Work Time",
                    description=f"Only {leverage_ratio*100:.0f}% of time was on high-value work",
                    impact="high",
                    data_points=[
                        f"Target: 50%+",
                        f"Actual: {report.leverage_hours:.1f}h",
                    ],
                ))

        # High elimination time
        if report.eliminate_hours > 5:
            insights.append(WeeklyInsight(
                category="opportunity",
                title="Reclaim Distraction Time",
                description=f"You spent {report.eliminate_hours:.1f}h on distractions this week",
                impact="high",
                data_points=[
                    "Consider using website blockers",
                    "Set specific times for social media",
                ],
            ))

        # Interrupt pattern
        avg_daily_interrupts = report.total_interrupts / 5
        if avg_daily_interrupts > 20:
            insights.append(WeeklyInsight(
                category="pattern",
                title="High Interrupt Rate",
                description=f"Average of {avg_daily_interrupts:.0f} interrupts per day",
                impact="medium",
                data_points=[
                    "Check Slack/email less frequently",
                    "Consider batching to 3x/day",
                ],
            ))

        # Swiss cheese days
        if report.avg_swiss_cheese_score > 0.5:
            insights.append(WeeklyInsight(
                category="warning",
                title="Fragmented Schedule",
                description="Meetings are creating too many small gaps",
                impact="high",
                data_points=[
                    f"Worst day: {report.worst_focus_day}",
                    "Consider meeting consolidation",
                ],
            ))

        # Best day insight
        if report.best_focus_day:
            insights.append(WeeklyInsight(
                category="pattern",
                title=f"{report.best_focus_day} = Your Focus Day",
                description=f"{report.best_focus_day} had the best focus score this week",
                impact="low",
                data_points=["Protect this day for deep work"],
            ))

        return insights

    def _generate_recommendations(
        self,
        report: WeeklyReport,
    ) -> list[WeeklyRecommendation]:
        """Generate prioritized recommendations."""
        recommendations = []

        # High distraction time
        if report.eliminate_hours > 5:
            recommendations.append(WeeklyRecommendation(
                title="Reduce Distraction Time",
                action=f"Limit non-work browsing to 1h/day (currently {report.eliminate_hours/5:.1f}h/day)",
                estimated_impact=f"Reclaim {report.eliminate_hours - 5:.1f} hours/week",
                priority=1,
                category="eliminate",
            ))

        # High interrupt count
        if report.total_interrupts > 100:
            recommendations.append(WeeklyRecommendation(
                title="Batch Communication Checks",
                action="Check Slack/email only at 9am, 1pm, and 5pm",
                estimated_impact="Save ~2 hours/week from reduced context switching",
                priority=1,
                category="automate",
            ))

        # Meeting fragmentation
        if report.avg_swiss_cheese_score > 0.4:
            recommendations.append(WeeklyRecommendation(
                title="Consolidate Meetings",
                action=f"Move scattered meetings to {report.worst_focus_day or 'specific days'}",
                estimated_impact="Create 2+ hour focus blocks",
                priority=2,
                category="delegate",
            ))

        # Low deep work
        if report.leverage_hours < 15:
            recommendations.append(WeeklyRecommendation(
                title="Protect Deep Work Time",
                action="Block 9-11 AM daily for uninterrupted work",
                estimated_impact=f"Add {20 - report.leverage_hours:.0f}h of productive time",
                priority=1,
                category="protect",
            ))

        # High context switches
        if report.total_context_switches > 200:
            recommendations.append(WeeklyRecommendation(
                title="Reduce Context Switching",
                action="Work in 45-minute focused blocks with 5-minute breaks",
                estimated_impact="Reduce mental fatigue and improve focus",
                priority=2,
                category="automate",
            ))

        # Sort by priority
        recommendations.sort(key=lambda r: r.priority)

        return recommendations

    def _calculate_savings_progress(
        self,
        report: WeeklyReport,
    ) -> TimeSavingsProgress:
        """Calculate progress toward time savings goal."""
        # Baseline: assume 40 hour work week
        baseline_hours = 40.0

        # Time "saved" = eliminated distractions + time saved by batching
        # This is an estimate of time that could be reclaimed
        eliminated = report.eliminate_hours
        automated = report.automate_hours * 0.5  # Assume 50% could be saved

        total_saved = eliminated + automated
        saved_percent = (total_saved / baseline_hours) * 100 if baseline_hours > 0 else 0

        return TimeSavingsProgress(
            goal_percent=self.target_savings_percent,
            baseline_hours=baseline_hours,
            current_hours=report.total_tracked_hours,
            eliminated_hours=eliminated,
            automated_hours=automated,
            total_saved_percent=saved_percent,
            on_track=saved_percent >= self.target_savings_percent * 0.5,  # 50% toward goal
        )

    async def _save_report(self, report: WeeklyReport) -> int:
        """Save report to database."""
        if not self.db:
            return 0

        try:
            return await self.db.insert(
                "weekly_optimization_insights",
                {
                    "week_start": report.week_start.strftime("%Y-%m-%d"),
                    "week_end": report.week_end.strftime("%Y-%m-%d"),
                    "content": json.dumps(report.to_dict()),
                    "leverage_hours": report.leverage_hours,
                    "eliminate_hours": report.eliminate_hours,
                    "savings_percent": report.savings_progress.total_saved_percent if report.savings_progress else 0,
                    "created_at": datetime.utcnow().isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to save weekly report: {e}")
            return 0

    async def get_report(
        self,
        week_start: datetime | None = None,
    ) -> WeeklyReport | None:
        """Get a saved report from the database.

        Args:
            week_start: Start of the week to retrieve

        Returns:
            WeeklyReport if found, None otherwise
        """
        if not self.db:
            return None

        if not week_start:
            today = datetime.utcnow()
            week_start = today - timedelta(days=today.weekday())

        week_str = week_start.strftime("%Y-%m-%d")

        row = await self.db.fetch_one(
            "SELECT * FROM weekly_optimization_insights WHERE week_start = ?",
            (week_str,),
        )

        if not row:
            return None

        content = json.loads(row["content"])

        # Reconstruct the report from saved content
        report = WeeklyReport(
            week_start=datetime.fromisoformat(content["week_start"]),
            week_end=datetime.fromisoformat(content["week_end"]),
            generated_at=datetime.fromisoformat(content["generated_at"]),
            total_tracked_hours=content.get("total_tracked_hours", 0),
            total_meetings=content.get("total_meetings", 0),
            total_interrupts=content.get("total_interrupts", 0),
            total_context_switches=content.get("total_context_switches", 0),
            leverage_hours=content.get("leverage_hours", 0),
            delegate_hours=content.get("delegate_hours", 0),
            eliminate_hours=content.get("eliminate_hours", 0),
            automate_hours=content.get("automate_hours", 0),
            avg_swiss_cheese_score=content.get("avg_swiss_cheese_score", 0),
            best_focus_day=content.get("best_focus_day", ""),
            worst_focus_day=content.get("worst_focus_day", ""),
        )

        # Reconstruct nested objects
        report.trends = [WeeklyTrend(**t) for t in content.get("trends", [])]
        report.insights = [WeeklyInsight(**i) for i in content.get("insights", [])]
        report.recommendations = [
            WeeklyRecommendation(**r) for r in content.get("recommendations", [])
        ]

        if content.get("savings_progress"):
            report.savings_progress = TimeSavingsProgress(**content["savings_progress"])

        return report
