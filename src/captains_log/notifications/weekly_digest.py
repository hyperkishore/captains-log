"""Weekly Digest Generator.

Aggregates daily activity data for a Mon-Sun week into a comprehensive
summary with trends vs the previous week.  Uses the duration_calculator
module for per-day metrics and produces a WeeklyDigest dataclass that
the CLI and notification system can render.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from captains_log.summarizers.duration_calculator import (
    _format_duration,
    get_app_durations,
    get_category_durations,
    get_focus_hours,
    get_total_active_hours,
)

logger = logging.getLogger(__name__)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class WeeklyDigest:
    """A complete weekly digest with trends."""

    week_start: date
    week_end: date
    total_active_hours: float
    focus_hours: float
    top_apps: list[dict] = field(default_factory=list)  # [{app: str, hours: float}]
    category_hours: dict[str, float] = field(default_factory=dict)
    daily_breakdown: list[dict] = field(default_factory=list)
    # [{date: str, day_name: str, active_hours: float, focus_hours: float}]
    prev_week_active_hours: float = 0.0
    prev_week_focus_hours: float = 0.0
    most_productive_day: str = ""
    least_productive_day: str = ""
    narrative: str = ""

    @property
    def active_trend_percent(self) -> float:
        """Percentage change in active hours vs previous week."""
        if self.prev_week_active_hours <= 0:
            return 0.0
        return ((self.total_active_hours - self.prev_week_active_hours)
                / self.prev_week_active_hours) * 100

    @property
    def focus_trend_percent(self) -> float:
        """Percentage change in focus hours vs previous week."""
        if self.prev_week_focus_hours <= 0:
            return 0.0
        return ((self.focus_hours - self.prev_week_focus_hours)
                / self.prev_week_focus_hours) * 100

    def format_active_hours(self) -> str:
        return _format_duration(self.total_active_hours * 60)

    def format_focus_hours(self) -> str:
        return _format_duration(self.focus_hours * 60)


class WeeklyDigestGenerator:
    """Generates weekly digests from the database."""

    def __init__(self, db: Any):
        self.db = db

    async def generate(self, week_of: date | None = None) -> WeeklyDigest:
        """Generate weekly digest.

        Args:
            week_of: Any date within the target week. Defaults to the
                     current week (Mon-Sun).

        Returns:
            WeeklyDigest with all computed fields.
        """
        # Determine week boundaries (Monday-Sunday)
        ref = week_of or date.today()
        week_start = ref - timedelta(days=ref.weekday())  # Monday
        week_end = week_start + timedelta(days=6)  # Sunday

        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_start - timedelta(days=1)

        # ------------------------------------------------------------------ #
        # Gather daily data for both weeks
        # ------------------------------------------------------------------ #
        daily_breakdown: list[dict] = []
        total_active = 0.0
        total_focus = 0.0
        app_totals: dict[str, float] = {}
        cat_totals: dict[str, float] = {}

        for offset in range(7):
            day = week_start + timedelta(days=offset)
            ds = day.isoformat()
            active = await get_total_active_hours(self.db, ds)
            focus = await get_focus_hours(self.db, ds)
            apps = await get_app_durations(self.db, ds)
            cats = await get_category_durations(self.db, ds)

            total_active += active
            total_focus += focus

            for app_name, mins in apps.items():
                app_totals[app_name] = app_totals.get(app_name, 0.0) + mins

            for cat, mins in cats.items():
                cat_totals[cat] = cat_totals.get(cat, 0.0) + mins

            daily_breakdown.append({
                "date": ds,
                "day_name": DAY_NAMES[offset],
                "active_hours": active,
                "focus_hours": focus,
            })

        # Previous week totals
        prev_active = 0.0
        prev_focus = 0.0
        for offset in range(7):
            day = prev_week_start + timedelta(days=offset)
            ds = day.isoformat()
            prev_active += await get_total_active_hours(self.db, ds)
            prev_focus += await get_focus_hours(self.db, ds)

        # ------------------------------------------------------------------ #
        # Derived metrics
        # ------------------------------------------------------------------ #

        # Top apps by total hours (descending)
        sorted_apps = sorted(app_totals.items(), key=lambda x: x[1], reverse=True)
        top_apps = [
            {"app": name, "hours": round(mins / 60, 2)}
            for name, mins in sorted_apps[:10]
        ]

        # Category hours (minutes -> hours)
        category_hours = {
            cat: round(mins / 60, 2)
            for cat, mins in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
        }

        # Most / least productive day (by active hours)
        days_with_data = [d for d in daily_breakdown if d["active_hours"] > 0.02]
        if days_with_data:
            best = max(days_with_data, key=lambda d: d["active_hours"])
            worst = min(days_with_data, key=lambda d: d["active_hours"])
            most_productive = best["day_name"]
            least_productive = worst["day_name"]
        else:
            most_productive = ""
            least_productive = ""

        # ------------------------------------------------------------------ #
        # Narrative
        # ------------------------------------------------------------------ #
        narrative = self._build_narrative(
            total_active=total_active,
            total_focus=total_focus,
            prev_active=prev_active,
            most_productive=most_productive,
            category_hours=category_hours,
        )

        return WeeklyDigest(
            week_start=week_start,
            week_end=week_end,
            total_active_hours=round(total_active, 2),
            focus_hours=round(total_focus, 2),
            top_apps=top_apps,
            category_hours=category_hours,
            daily_breakdown=daily_breakdown,
            prev_week_active_hours=round(prev_active, 2),
            prev_week_focus_hours=round(prev_focus, 2),
            most_productive_day=most_productive,
            least_productive_day=least_productive,
            narrative=narrative,
        )

    # ---------------------------------------------------------------------- #
    # Internal helpers
    # ---------------------------------------------------------------------- #

    @staticmethod
    def _build_narrative(
        total_active: float,
        total_focus: float,
        prev_active: float,
        most_productive: str,
        category_hours: dict[str, float],
    ) -> str:
        """Build a short, template-based narrative summary."""
        parts: list[str] = []

        parts.append(
            f"This week you logged {total_active:.1f}h of active work "
            f"({total_focus:.1f}h focused)."
        )

        if prev_active > 0:
            trend = ((total_active - prev_active) / prev_active) * 100
            arrow = "up" if trend > 0 else "down"
            parts.append(f"{abs(trend):.0f}% {arrow} vs last week.")
        else:
            parts.append("No previous week data for comparison.")

        if most_productive:
            parts.append(f"Best day: {most_productive}.")

        if category_hours:
            top_cat = next(iter(category_hours))
            top_hrs = category_hours[top_cat]
            parts.append(f"Top category: {top_cat} ({top_hrs:.1f}h).")

        return " ".join(parts)
