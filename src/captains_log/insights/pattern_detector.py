"""Focus pattern detection from historical activity data.

Analyzes activity_logs to find:
- Peak productive hours (most dev time, fewest switches)
- Context switch spike patterns (when switches exceed 2x daily average)
- Weekly rhythm (which days are most/least productive)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Apps considered "development" / deep-work for peak hour analysis
DEV_BUNDLE_IDS = {
    "com.microsoft.VSCode",
    "com.apple.Terminal",
    "com.googlecode.iterm2",
    "com.todesktop.230313mzl4w4u92",  # Cursor
    "dev.warp.Warp-Stable",
    "com.sublimetext.4",
    "com.jetbrains.intellij",
    "com.jetbrains.pycharm",
}

DEV_APP_NAMES = {
    "Code",
    "VS Code",
    "Cursor",
    "Terminal",
    "iTerm2",
    "Warp",
    "Sublime Text",
    "IntelliJ IDEA",
    "PyCharm",
}


@dataclass
class FocusPattern:
    """A detected pattern in the user's activity history."""

    pattern_type: str  # "peak_hours", "context_switch_spike", "weekly_rhythm"
    description: str
    data: dict = field(default_factory=dict)


class PatternDetector:
    """Detects focus and productivity patterns from activity data."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def _get_db(self) -> Any:
        """Open and return an async database connection."""
        import aiosqlite

        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        return db

    async def detect_peak_hours(self, days: int = 14) -> FocusPattern:
        """Find the hours where the user is most focused.

        Focused = most time in dev apps with fewest context switches.
        Returns the top 3 peak hours.
        """
        db = await self._get_db()
        try:
            since = (datetime.utcnow() - timedelta(days=days)).isoformat()

            rows = await db.execute_fetchall(
                """
                SELECT timestamp, app_name, bundle_id
                FROM activity_logs
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (since,),
            )

            if not rows:
                return FocusPattern(
                    pattern_type="peak_hours",
                    description="Not enough data to detect peak hours.",
                    data={"peak_hours": [], "days_analyzed": days},
                )

            # Accumulate dev minutes and switch counts per hour-of-day
            hour_dev_minutes: dict[int, float] = defaultdict(float)
            hour_total_minutes: dict[int, float] = defaultdict(float)
            hour_switches: dict[int, int] = defaultdict(int)
            hour_days_seen: dict[int, set] = defaultdict(set)

            for i in range(len(rows) - 1):
                ts = datetime.fromisoformat(rows[i]["timestamp"])
                next_ts = datetime.fromisoformat(rows[i + 1]["timestamp"])
                duration_min = (next_ts - ts).total_seconds() / 60.0
                duration_min = min(duration_min, 30.0)  # Cap at 30 min

                hour = ts.hour
                day_key = ts.strftime("%Y-%m-%d")

                hour_total_minutes[hour] += duration_min
                hour_days_seen[hour].add(day_key)
                hour_switches[hour] += 1

                # Check if this is a dev app
                app_name = rows[i]["app_name"]
                bundle_id = rows[i]["bundle_id"] or ""
                if bundle_id in DEV_BUNDLE_IDS or app_name in DEV_APP_NAMES:
                    hour_dev_minutes[hour] += duration_min

            # Compute score per hour: dev_ratio * (1 / switch_rate)
            # Higher dev time + fewer switches = better focus
            hour_scores: list[tuple[int, float, float, float]] = []
            for hour in range(24):
                total = hour_total_minutes.get(hour, 0)
                if total < 10:  # Skip hours with trivial data
                    continue

                n_days = len(hour_days_seen.get(hour, set())) or 1
                avg_dev = hour_dev_minutes.get(hour, 0) / n_days
                avg_switches = hour_switches.get(hour, 0) / n_days
                avg_total = total / n_days

                # Dev ratio (0-1) and switch penalty
                dev_ratio = hour_dev_minutes.get(hour, 0) / total if total > 0 else 0
                switch_rate = avg_switches / (avg_total / 60) if avg_total > 0 else 0

                # Score: focus = dev_ratio / (1 + switch_rate)
                score = dev_ratio / (1 + switch_rate * 0.1)

                hour_scores.append((hour, score, avg_dev, avg_switches))

            # Sort by score descending, take top 3
            hour_scores.sort(key=lambda x: x[1], reverse=True)
            top_3 = hour_scores[:3]

            if not top_3:
                return FocusPattern(
                    pattern_type="peak_hours",
                    description="Not enough data to detect peak hours.",
                    data={"peak_hours": [], "days_analyzed": days},
                )

            # Format peak hours
            peak_hours = []
            for hour, score, avg_dev, avg_switches in top_3:
                start = datetime(2000, 1, 1, hour)
                end = start + timedelta(hours=1)
                label = f"{start.strftime('%-I %p')} - {end.strftime('%-I %p')}"
                peak_hours.append({
                    "hour": hour,
                    "label": label,
                    "avg_focus_minutes": round(avg_dev, 1),
                    "avg_switches": round(avg_switches, 1),
                    "score": round(score, 3),
                })

            best = peak_hours[0]
            description = (
                f"Peak Hours: {best['label']} "
                f"(avg {best['avg_focus_minutes']:.1f}m focused)"
            )

            return FocusPattern(
                pattern_type="peak_hours",
                description=description,
                data={"peak_hours": peak_hours, "days_analyzed": days},
            )
        finally:
            await db.close()

    async def detect_context_switch_patterns(self, days: int = 14) -> FocusPattern:
        """Find when context switches spike.

        A spike = hour where switches exceed 2x the daily average.
        """
        db = await self._get_db()
        try:
            since = (datetime.utcnow() - timedelta(days=days)).isoformat()

            rows = await db.execute_fetchall(
                """
                SELECT timestamp, app_name
                FROM activity_logs
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (since,),
            )

            if not rows:
                return FocusPattern(
                    pattern_type="context_switch_spike",
                    description="Not enough data to detect context switch patterns.",
                    data={"spike_hours": [], "daily_avg": 0},
                )

            # Count switches per hour per day
            day_hour_switches: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
            prev_app = None

            for row in rows:
                ts = datetime.fromisoformat(row["timestamp"])
                day_key = ts.strftime("%Y-%m-%d")
                hour = ts.hour
                app = row["app_name"]

                if prev_app is not None and app != prev_app:
                    day_hour_switches[day_key][hour] += 1

                prev_app = app

            if not day_hour_switches:
                return FocusPattern(
                    pattern_type="context_switch_spike",
                    description="Not enough data to detect context switch patterns.",
                    data={"spike_hours": [], "daily_avg": 0},
                )

            # Compute average switches per hour across all days
            hour_totals: dict[int, list[int]] = defaultdict(list)
            daily_totals: list[int] = []

            for day, hours in day_hour_switches.items():
                day_total = sum(hours.values())
                daily_totals.append(day_total)
                for hour, count in hours.items():
                    hour_totals[hour].append(count)

            daily_avg = sum(daily_totals) / len(daily_totals) if daily_totals else 0
            # Average per hour for a day
            hourly_avg = daily_avg / max(len(set(h for hours in day_hour_switches.values() for h in hours)), 1)

            # Find spike hours (avg switches > 2x the overall hourly avg)
            spike_hours = []
            for hour in sorted(hour_totals.keys()):
                vals = hour_totals[hour]
                avg = sum(vals) / len(vals)

                if avg > hourly_avg * 2 and avg >= 3:  # At least 3 switches/hour on average
                    start = datetime(2000, 1, 1, hour)
                    end = start + timedelta(hours=1)
                    label = f"{start.strftime('%-I %p')} - {end.strftime('%-I %p')}"
                    spike_hours.append({
                        "hour": hour,
                        "label": label,
                        "avg_switches": round(avg, 1),
                    })

            # Sort by avg_switches descending
            spike_hours.sort(key=lambda x: x["avg_switches"], reverse=True)

            if spike_hours:
                worst = spike_hours[0]
                description = (
                    f"Context Switch Spikes: {worst['label']} "
                    f"(avg {worst['avg_switches']:.0f} switches/hour)"
                )
            else:
                description = "No significant context switch spikes detected."

            return FocusPattern(
                pattern_type="context_switch_spike",
                description=description,
                data={
                    "spike_hours": spike_hours,
                    "daily_avg_switches": round(daily_avg, 1),
                },
            )
        finally:
            await db.close()

    async def detect_weekly_rhythm(self, weeks: int = 4) -> FocusPattern:
        """Find which days of the week are most/least productive.

        Productivity = total active hours per day-of-week, averaged
        over the last N weeks.
        """
        db = await self._get_db()
        try:
            since = (datetime.utcnow() - timedelta(weeks=weeks)).isoformat()

            rows = await db.execute_fetchall(
                """
                SELECT timestamp, app_name
                FROM activity_logs
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (since,),
            )

            if not rows:
                return FocusPattern(
                    pattern_type="weekly_rhythm",
                    description="Not enough data to detect weekly rhythm.",
                    data={"day_averages": [], "most_productive": None, "least_productive": None},
                )

            # Compute active minutes per date
            date_minutes: dict[str, float] = defaultdict(float)

            for i in range(len(rows) - 1):
                ts = datetime.fromisoformat(rows[i]["timestamp"])
                next_ts = datetime.fromisoformat(rows[i + 1]["timestamp"])
                duration_min = (next_ts - ts).total_seconds() / 60.0
                duration_min = min(duration_min, 30.0)  # Cap at 30 min
                date_key = ts.strftime("%Y-%m-%d")
                date_minutes[date_key] += duration_min

            # Group by day-of-week
            dow_minutes: dict[int, list[float]] = defaultdict(list)
            for date_str, total_mins in date_minutes.items():
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                dow = dt.weekday()  # 0=Monday
                dow_minutes[dow].append(total_mins)

            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            day_averages = []

            for dow in range(7):
                vals = dow_minutes.get(dow, [])
                if vals:
                    avg_hours = (sum(vals) / len(vals)) / 60.0
                    day_averages.append({
                        "day": day_names[dow],
                        "day_short": day_names[dow][:3],
                        "dow": dow,
                        "avg_hours": round(avg_hours, 1),
                        "sample_days": len(vals),
                    })

            if not day_averages:
                return FocusPattern(
                    pattern_type="weekly_rhythm",
                    description="Not enough data to detect weekly rhythm.",
                    data={"day_averages": [], "most_productive": None, "least_productive": None},
                )

            # Sort to find best and worst
            by_hours = sorted(day_averages, key=lambda x: x["avg_hours"], reverse=True)
            most = by_hours[0]
            least = by_hours[-1]

            description = (
                f"Weekly Rhythm: {most['day']} most productive ({most['avg_hours']:.1f}h avg), "
                f"{least['day']} least ({least['avg_hours']:.1f}h avg)"
            )

            return FocusPattern(
                pattern_type="weekly_rhythm",
                description=description,
                data={
                    "day_averages": day_averages,
                    "most_productive": most,
                    "least_productive": least,
                    "weeks_analyzed": weeks,
                },
            )
        finally:
            await db.close()

    async def get_all_insights(self, days: int = 14) -> list[FocusPattern]:
        """Run all pattern detections and return insights."""
        weeks = max(days // 7, 2)

        peak = await self.detect_peak_hours(days=days)
        switches = await self.detect_context_switch_patterns(days=days)
        rhythm = await self.detect_weekly_rhythm(weeks=weeks)

        return [peak, switches, rhythm]
