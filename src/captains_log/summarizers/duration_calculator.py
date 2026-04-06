"""Calculate time-in-app durations from activity log events.

The activity_logs table records app-switch events (timestamps when the user
switched to a new app). Duration in each app is derived from the gap between
consecutive events: you were in app A from event_A.timestamp until
event_B.timestamp.

Caps:
  - Individual event gap > 30 min  => assume user was away, cap at 30 min.
  - idle_status == "AWAY"          => cap that event's duration at 2 min.
  - Last event of day: if within 30 min of *now* (same day), use
    now - timestamp; otherwise cap at 5 min.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# App-category mapping (matches cloud_sync.py categories)
# --------------------------------------------------------------------------- #

CATEGORY_MAP: dict[str, str] = {
    # Development
    "com.microsoft.VSCode": "Development",
    "com.apple.Terminal": "Development",
    "com.googlecode.iterm2": "Development",
    "com.github.atom": "Development",
    "com.jetbrains": "Development",
    "dev.warp.Warp-Stable": "Development",
    "com.todesktop.230313mzl4w4u92": "Development",  # Cursor
    # Browsing
    "com.google.Chrome": "Browsing",
    "com.apple.Safari": "Browsing",
    "org.mozilla.firefox": "Browsing",
    "company.thebrowser.Browser": "Browsing",  # Arc
    # Communication
    "com.tinyspeck.slackmacgap": "Communication",
    "com.apple.mail": "Communication",
    "com.apple.MobileSMS": "Communication",
    "com.readdle.smartemail-macos": "Communication",
    "WhatsApp": "Communication",
    # Meeting
    "us.zoom.xos": "Meeting",
    "com.google.Meet": "Meeting",
    # Design
    "com.figma.Desktop": "Design",
    "com.adobe": "Design",
    # Writing / Notes
    "com.apple.Notes": "Writing",
    "md.obsidian": "Writing",
    "com.notion.Notion": "Writing",
}

# Categories that count as "focus work"
FOCUS_CATEGORIES = {"Development", "Design"}


def _get_category(bundle_id: str | None, app_name: str) -> str:
    """Classify an app into a category."""
    if bundle_id:
        for prefix, cat in CATEGORY_MAP.items():
            if bundle_id.startswith(prefix) or prefix in bundle_id.lower():
                return cat
    # Fallback heuristics on app name
    name_lower = app_name.lower()
    if any(kw in name_lower for kw in ("code", "terminal", "iterm", "warp", "cursor")):
        return "Development"
    if any(kw in name_lower for kw in ("slack", "mail", "messages", "whatsapp", "telegram")):
        return "Communication"
    if any(kw in name_lower for kw in ("chrome", "safari", "firefox", "arc", "browser")):
        return "Browsing"
    if any(kw in name_lower for kw in ("zoom", "meet", "teams")):
        return "Meeting"
    if any(kw in name_lower for kw in ("figma", "sketch", "photoshop", "illustrator")):
        return "Design"
    if any(kw in name_lower for kw in ("notes", "obsidian", "notion", "bear")):
        return "Writing"
    return "Other"


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

# System apps we always exclude from user-facing totals
_SYSTEM_APPS = frozenset({
    "loginwindow",
    "UserNotificationCenter",
    "coreautha",
    "SecurityAgent",
    "ScreenSaverEngine",
})

# Max gap for a single event (minutes)
_MAX_GAP_MINUTES = 30.0
# Duration assigned to AWAY events (minutes)
_AWAY_CAP_MINUTES = 2.0
# Duration assigned to last event when it's stale (minutes)
_LAST_EVENT_CAP_MINUTES = 5.0


def _format_duration(minutes: float) -> str:
    """Format minutes into a human-readable string like '3h 25m' or '45m'."""
    if minutes < 1:
        return "<1m"
    h = int(minutes // 60)
    m = int(minutes % 60)
    if h > 0:
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    return f"{m}m"


def _compute_durations(
    rows: list[dict[str, Any]],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Given ordered activity rows, compute duration for each event.

    Returns a list of dicts with keys: app_name, bundle_id, idle_status,
    duration_minutes.
    """
    if not rows:
        return []

    now = now or datetime.now()
    results: list[dict[str, Any]] = []

    for i, row in enumerate(rows):
        ts = datetime.fromisoformat(row["timestamp"])
        app_name = row["app_name"]
        bundle_id = row.get("bundle_id")
        idle_status = row.get("idle_status", "")

        if i < len(rows) - 1:
            next_ts = datetime.fromisoformat(rows[i + 1]["timestamp"])
            duration_min = (next_ts - ts).total_seconds() / 60.0
            duration_min = min(duration_min, _MAX_GAP_MINUTES)
        else:
            # Last event of the day
            gap = (now - ts).total_seconds() / 60.0
            if gap <= _MAX_GAP_MINUTES and ts.date() == now.date():
                duration_min = gap
            else:
                duration_min = _LAST_EVENT_CAP_MINUTES

        # AWAY events get a hard cap
        if idle_status == "AWAY":
            duration_min = min(duration_min, _AWAY_CAP_MINUTES)

        results.append({
            "app_name": app_name,
            "bundle_id": bundle_id,
            "idle_status": idle_status,
            "duration_minutes": duration_min,
            "timestamp": ts,
        })

    return results


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


async def get_app_durations(db: Any, date_str: str) -> dict[str, float]:
    """Get total minutes per app for a given date.

    Returns {app_name: minutes}, sorted descending by duration.
    System apps and apps with < 1 min are excluded.
    """
    rows = await db.fetch_all(
        """
        SELECT app_name, bundle_id, timestamp, idle_status
        FROM activity_logs
        WHERE date(timestamp) = ?
        ORDER BY timestamp ASC
        """,
        (date_str,),
    )

    durations = _compute_durations(rows)

    totals: dict[str, float] = {}
    for d in durations:
        name = d["app_name"]
        if name in _SYSTEM_APPS:
            continue
        totals[name] = totals.get(name, 0.0) + d["duration_minutes"]

    # Filter out trivial usage
    totals = {k: v for k, v in totals.items() if v >= 1.0}
    # Sort descending
    return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))


async def get_hourly_durations(
    db: Any, date_str: str
) -> dict[int, dict[str, float]]:
    """Get per-hour breakdown.

    Returns {hour: {app_name: minutes}}.  Each event's duration is assigned
    to the hour its timestamp falls in (no splitting across hours).
    """
    rows = await db.fetch_all(
        """
        SELECT app_name, bundle_id, timestamp, idle_status
        FROM activity_logs
        WHERE date(timestamp) = ?
        ORDER BY timestamp ASC
        """,
        (date_str,),
    )

    durations = _compute_durations(rows)

    hourly: dict[int, dict[str, float]] = {}
    for d in durations:
        if d["app_name"] in _SYSTEM_APPS:
            continue
        hour = d["timestamp"].hour
        if hour not in hourly:
            hourly[hour] = {}
        hourly[hour][d["app_name"]] = (
            hourly[hour].get(d["app_name"], 0.0) + d["duration_minutes"]
        )

    return hourly


async def get_category_durations(db: Any, date_str: str) -> dict[str, float]:
    """Get durations grouped by category.

    Returns {category: minutes}, sorted descending.
    """
    rows = await db.fetch_all(
        """
        SELECT app_name, bundle_id, timestamp, idle_status
        FROM activity_logs
        WHERE date(timestamp) = ?
        ORDER BY timestamp ASC
        """,
        (date_str,),
    )

    durations = _compute_durations(rows)

    totals: dict[str, float] = {}
    for d in durations:
        if d["app_name"] in _SYSTEM_APPS:
            continue
        cat = _get_category(d["bundle_id"], d["app_name"])
        totals[cat] = totals.get(cat, 0.0) + d["duration_minutes"]

    return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))


async def get_total_active_hours(db: Any, date_str: str) -> float:
    """Get total active hours (sum of all app durations, excluding AWAY)."""
    rows = await db.fetch_all(
        """
        SELECT app_name, bundle_id, timestamp, idle_status
        FROM activity_logs
        WHERE date(timestamp) = ?
        ORDER BY timestamp ASC
        """,
        (date_str,),
    )

    durations = _compute_durations(rows)

    total_min = sum(
        d["duration_minutes"]
        for d in durations
        if d["app_name"] not in _SYSTEM_APPS and d["idle_status"] != "AWAY"
    )
    return total_min / 60.0


async def get_focus_hours(db: Any, date_str: str) -> float:
    """Get focus hours (time in Development + Design apps only)."""
    rows = await db.fetch_all(
        """
        SELECT app_name, bundle_id, timestamp, idle_status
        FROM activity_logs
        WHERE date(timestamp) = ?
        ORDER BY timestamp ASC
        """,
        (date_str,),
    )

    durations = _compute_durations(rows)

    focus_min = sum(
        d["duration_minutes"]
        for d in durations
        if d["app_name"] not in _SYSTEM_APPS
        and d["idle_status"] != "AWAY"
        and _get_category(d["bundle_id"], d["app_name"]) in FOCUS_CATEGORIES
    )
    return focus_min / 60.0


async def get_most_focused_hour(db: Any, date_str: str) -> str | None:
    """Find the hour with the most Development+Design time.

    Returns a formatted string like '2pm-3pm' or None if no focus activity.
    """
    hourly = await get_hourly_durations(db, date_str)

    best_hour: int | None = None
    best_focus_min = 0.0

    for hour, apps in hourly.items():
        focus_min = sum(
            mins for app, mins in apps.items()
            if _get_category(None, app) in FOCUS_CATEGORIES
        )
        if focus_min > best_focus_min:
            best_focus_min = focus_min
            best_hour = hour

    if best_hour is None or best_focus_min < 1.0:
        return None

    start = datetime(2000, 1, 1, best_hour)
    end = start + timedelta(hours=1)
    return f"{start.strftime('%-I%p').lower()}-{end.strftime('%-I%p').lower()}"
