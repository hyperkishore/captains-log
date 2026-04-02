"""Daily Digest Generator.

Queries the database for today's activity and generates a concise
summary that gets pushed as a macOS notification. This is the
primary "pull" mechanism that brings the user back daily.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AppUsage:
    """Time spent in a single app."""

    app_name: str
    minutes: float
    event_count: int

    @property
    def hours_str(self) -> str:
        if self.minutes >= 60:
            h = int(self.minutes // 60)
            m = int(self.minutes % 60)
            return f"{h}h {m}m" if m > 0 else f"{h}h"
        return f"{int(self.minutes)}m"


@dataclass
class DailyDigest:
    """A complete daily digest."""

    date: str
    total_active_minutes: float = 0.0
    top_apps: list[AppUsage] = field(default_factory=list)
    context_switches: int = 0
    most_focused_hour: str = ""
    focus_session_count: int = 0
    focus_minutes: float = 0.0
    ai_narrative: str = ""

    @property
    def total_hours_str(self) -> str:
        h = int(self.total_active_minutes // 60)
        m = int(self.total_active_minutes % 60)
        if h > 0:
            return f"{h}h {m}m" if m > 0 else f"{h}h"
        return f"{m}m"

    @property
    def notification_title(self) -> str:
        return f"Today: {self.total_hours_str} active"

    @property
    def notification_body(self) -> str:
        parts = []

        # Top apps (max 3)
        if self.top_apps:
            app_strs = [f"{a.app_name} {a.hours_str}" for a in self.top_apps[:3]]
            parts.append(" | ".join(app_strs))

        # Most focused hour
        if self.most_focused_hour:
            parts.append(f"Most focused: {self.most_focused_hour}")

        # Focus sessions
        if self.focus_session_count > 0:
            parts.append(f"Focus: {self.focus_session_count} sessions ({int(self.focus_minutes)}m)")

        return "\n".join(parts) if parts else "No activity recorded today"

    @property
    def notification_subtitle(self) -> str:
        if self.ai_narrative:
            # Truncate to fit notification subtitle
            return self.ai_narrative[:80]
        return ""

    def to_rich_text(self) -> str:
        """Generate rich terminal output for `captains-log today`."""
        lines = []
        lines.append(f"  Date: {self.date}")
        lines.append(f"  Active: {self.total_hours_str}")
        lines.append("")

        if self.top_apps:
            lines.append("  Apps:")
            max_name_len = max(len(a.app_name) for a in self.top_apps[:8])
            for app in self.top_apps[:8]:
                bar_len = int(app.minutes / max(a.minutes for a in self.top_apps) * 20) if self.top_apps else 0
                bar = "\u2588" * bar_len
                lines.append(f"    {app.app_name:<{max_name_len}}  {app.hours_str:>6}  {bar}")
            lines.append("")

        if self.most_focused_hour:
            lines.append(f"  Most focused hour: {self.most_focused_hour}")

        if self.context_switches > 0:
            lines.append(f"  Context switches: {self.context_switches}")

        if self.focus_session_count > 0:
            lines.append(f"  Focus sessions: {self.focus_session_count} ({int(self.focus_minutes)}m)")

        if self.ai_narrative:
            lines.append("")
            lines.append(f"  AI: {self.ai_narrative}")

        return "\n".join(lines)


class DailyDigestGenerator:
    """Generates daily digests from the database."""

    def __init__(self, db: Any):
        self.db = db

    async def generate(self, target_date: datetime | None = None) -> DailyDigest:
        """Generate a daily digest for the given date.

        Args:
            target_date: Date to generate digest for (defaults to today)

        Returns:
            DailyDigest with all computed fields
        """
        target_date = target_date or datetime.now()
        date_str = target_date.strftime("%Y-%m-%d")

        digest = DailyDigest(date=date_str)

        # Get total active time and app breakdown
        await self._compute_app_usage(digest, date_str)

        # Get context switches
        await self._compute_context_switches(digest, date_str)

        # Get most focused hour
        await self._compute_most_focused_hour(digest, date_str)

        # Get focus session data
        await self._compute_focus_sessions(digest, date_str)

        # Generate AI narrative from summaries
        await self._compute_ai_narrative(digest, date_str)

        return digest

    async def _compute_app_usage(self, digest: DailyDigest, date_str: str) -> None:
        """Compute per-app time spent.

        Uses consecutive activity_log entries to calculate duration per app.
        Each entry represents "I switched to this app at this time", so the
        duration is the gap between consecutive entries.
        """
        rows = await self.db.fetch_all(
            """
            SELECT app_name, timestamp
            FROM activity_logs
            WHERE date(timestamp) = ?
            ORDER BY timestamp ASC
            """,
            (date_str,),
        )

        if not rows:
            return

        app_minutes: dict[str, float] = {}
        app_counts: dict[str, int] = {}

        for i in range(len(rows)):
            app = rows[i]["app_name"]
            app_counts[app] = app_counts.get(app, 0) + 1

            if i < len(rows) - 1:
                start = datetime.fromisoformat(rows[i]["timestamp"])
                end = datetime.fromisoformat(rows[i + 1]["timestamp"])
                duration_min = (end - start).total_seconds() / 60.0

                # Cap single segment at 30 min (likely idle beyond that)
                duration_min = min(duration_min, 30.0)

                app_minutes[app] = app_minutes.get(app, 0.0) + duration_min

        # Sort by time spent
        sorted_apps = sorted(app_minutes.items(), key=lambda x: x[1], reverse=True)

        # Filter out system apps with trivial usage
        system_apps = {"loginwindow", "UserNotificationCenter", "coreautha", "SecurityAgent"}
        sorted_apps = [(name, mins) for name, mins in sorted_apps if name not in system_apps and mins >= 1.0]

        digest.top_apps = [
            AppUsage(app_name=name, minutes=mins, event_count=app_counts.get(name, 0))
            for name, mins in sorted_apps
        ]

        digest.total_active_minutes = sum(a.minutes for a in digest.top_apps)

    async def _compute_context_switches(self, digest: DailyDigest, date_str: str) -> None:
        """Count app switches (context switches) for the day."""
        row = await self.db.fetch_one(
            """
            SELECT COUNT(*) as switches
            FROM activity_logs
            WHERE date(timestamp) = ?
            """,
            (date_str,),
        )
        if row:
            digest.context_switches = row["switches"]

    async def _compute_most_focused_hour(self, digest: DailyDigest, date_str: str) -> None:
        """Find the hour with the fewest context switches (most focused).

        The most focused hour is the one where you stayed in the fewest
        different apps — meaning you were locked in.
        """
        rows = await self.db.fetch_all(
            """
            SELECT
                strftime('%H', timestamp) as hour,
                COUNT(DISTINCT app_name) as unique_apps,
                COUNT(*) as switches
            FROM activity_logs
            WHERE date(timestamp) = ?
            GROUP BY hour
            HAVING switches >= 2
            ORDER BY unique_apps ASC, switches ASC
            LIMIT 1
            """,
            (date_str,),
        )

        if rows:
            hour = int(rows[0]["hour"])
            # Format as 12-hour time range
            start = datetime(2000, 1, 1, hour)
            end = start + timedelta(hours=1)
            digest.most_focused_hour = (
                f"{start.strftime('%-I%p').lower()}-{end.strftime('%-I%p').lower()}"
            )

    async def _compute_focus_sessions(self, digest: DailyDigest, date_str: str) -> None:
        """Get focus session data for the day."""
        row = await self.db.fetch_one(
            """
            SELECT
                COUNT(*) as session_count,
                COALESCE(SUM(total_focus_minutes), 0) as total_minutes
            FROM focus_sessions
            WHERE date = ?
            """,
            (date_str,),
        )
        if row and row["session_count"]:
            digest.focus_session_count = row["session_count"]
            digest.focus_minutes = row["total_minutes"]

    async def _compute_ai_narrative(self, digest: DailyDigest, date_str: str) -> None:
        """Generate a short narrative from existing AI summaries.

        Uses the most common activity_type and key_activities from
        the summaries table to create a one-line narrative.
        """
        rows = await self.db.fetch_all(
            """
            SELECT activity_type, context, key_activities
            FROM summaries
            WHERE date(period_start) = ?
            ORDER BY period_start ASC
            """,
            (date_str,),
        )

        if not rows:
            return

        # Collect activity types and contexts
        activity_types: dict[str, int] = {}
        contexts: list[str] = []

        for row in rows:
            if row["activity_type"]:
                at = row["activity_type"]
                activity_types[at] = activity_types.get(at, 0) + 1
            if row["context"]:
                contexts.append(row["context"])

        # Build narrative from most common activity type + last context
        if activity_types:
            primary_type = max(activity_types, key=activity_types.get)
            type_label = primary_type.replace("_", " ").title()

            if contexts:
                # Use the last meaningful context
                last_context = contexts[-1]
                if len(last_context) > 60:
                    last_context = last_context[:57] + "..."
                digest.ai_narrative = f"Mostly {type_label.lower()}. {last_context}"
            else:
                digest.ai_narrative = f"Mostly {type_label.lower()} today."
