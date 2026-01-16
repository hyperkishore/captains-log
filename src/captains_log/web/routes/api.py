"""API routes for data access."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(tags=["api"])


class ActivityResponse(BaseModel):
    """Activity log response."""
    timestamp: str
    app_name: str
    bundle_id: str | None
    window_title: str | None
    url: str | None
    idle_status: str | None


class StatsResponse(BaseModel):
    """Statistics response."""
    date: str
    total_events: int
    unique_apps: int
    top_apps: list[dict[str, Any]]
    hourly_breakdown: list[dict[str, Any]]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    database_connected: bool
    database_size_mb: float
    total_activities: int


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """API health check."""
    from captains_log.web.app import get_db

    try:
        db = await get_db()
        size = await db.get_size_mb()
        count = await db.fetch_one("SELECT COUNT(*) as count FROM activity_logs")

        return HealthResponse(
            status="healthy",
            database_connected=True,
            database_size_mb=size,
            total_activities=count["count"] if count else 0,
        )
    except Exception as e:
        return HealthResponse(
            status=f"unhealthy: {e}",
            database_connected=False,
            database_size_mb=0,
            total_activities=0,
        )


@router.get("/activities", response_model=list[ActivityResponse])
async def get_activities(
    date: str | None = Query(None, description="Date in YYYY-MM-DD format"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[ActivityResponse]:
    """Get activity logs."""
    from captains_log.web.app import get_db

    db = await get_db()

    if date:
        rows = await db.fetch_all(
            """
            SELECT timestamp, app_name, bundle_id, window_title, url, idle_status
            FROM activity_logs
            WHERE date(timestamp) = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (date, limit, offset)
        )
    else:
        rows = await db.fetch_all(
            """
            SELECT timestamp, app_name, bundle_id, window_title, url, idle_status
            FROM activity_logs
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )

    return [ActivityResponse(**row) for row in rows]


@router.get("/stats/{date}", response_model=StatsResponse)
async def get_stats(date: str) -> StatsResponse:
    """Get statistics for a specific date."""
    from captains_log.web.app import get_db

    db = await get_db()

    # Total events
    total = await db.fetch_one(
        "SELECT COUNT(*) as count FROM activity_logs WHERE date(timestamp) = ?",
        (date,)
    )

    # Unique apps
    unique = await db.fetch_one(
        "SELECT COUNT(DISTINCT bundle_id) as count FROM activity_logs WHERE date(timestamp) = ?",
        (date,)
    )

    # Top apps
    top_apps = await db.fetch_all(
        """
        SELECT app_name, COUNT(*) as count
        FROM activity_logs
        WHERE date(timestamp) = ?
        GROUP BY app_name
        ORDER BY count DESC
        LIMIT 10
        """,
        (date,)
    )

    # Hourly breakdown
    hourly = await db.fetch_all(
        """
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
        FROM activity_logs
        WHERE date(timestamp) = ?
        GROUP BY hour
        ORDER BY hour
        """,
        (date,)
    )

    return StatsResponse(
        date=date,
        total_events=total["count"] if total else 0,
        unique_apps=unique["count"] if unique else 0,
        top_apps=[dict(row) for row in top_apps],
        hourly_breakdown=[dict(row) for row in hourly],
    )


@router.get("/apps/summary")
async def get_app_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to summarize"),
) -> list[dict[str, Any]]:
    """Get app usage summary over time."""
    from captains_log.web.app import get_db

    db = await get_db()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    rows = await db.fetch_all(
        """
        SELECT
            app_name,
            bundle_id,
            COUNT(*) as total_events,
            COUNT(DISTINCT date(timestamp)) as active_days
        FROM activity_logs
        WHERE date(timestamp) >= ?
        GROUP BY bundle_id
        ORDER BY total_events DESC
        LIMIT 20
        """,
        (cutoff,)
    )

    return [dict(row) for row in rows]


@router.get("/timeline/{date}")
async def get_timeline(date: str) -> list[dict[str, Any]]:
    """Get activity timeline for a date, grouped by app sessions."""
    from captains_log.web.app import get_db

    db = await get_db()

    rows = await db.fetch_all(
        """
        SELECT
            timestamp,
            app_name,
            bundle_id,
            window_title,
            url,
            idle_status
        FROM activity_logs
        WHERE date(timestamp) = ?
        ORDER BY timestamp ASC
        """,
        (date,)
    )

    # Group consecutive same-app events into sessions
    sessions = []
    current_session = None

    for row in rows:
        row_dict = dict(row)
        if current_session is None or current_session["bundle_id"] != row_dict["bundle_id"]:
            if current_session:
                sessions.append(current_session)
            current_session = {
                "app_name": row_dict["app_name"],
                "bundle_id": row_dict["bundle_id"],
                "start_time": row_dict["timestamp"],
                "end_time": row_dict["timestamp"],
                "event_count": 1,
                "window_titles": [row_dict["window_title"]] if row_dict["window_title"] else [],
                "urls": [row_dict["url"]] if row_dict["url"] else [],
            }
        else:
            current_session["end_time"] = row_dict["timestamp"]
            current_session["event_count"] += 1
            if row_dict["window_title"] and row_dict["window_title"] not in current_session["window_titles"]:
                current_session["window_titles"].append(row_dict["window_title"])
            if row_dict["url"] and row_dict["url"] not in current_session["urls"]:
                current_session["urls"].append(row_dict["url"])

    if current_session:
        sessions.append(current_session)

    return sessions


@router.get("/time-analysis/{date}")
async def get_time_analysis(date: str) -> dict[str, Any]:
    """Get time analysis data for a specific date."""
    from captains_log.web.app import get_db

    db = await get_db()

    events = await db.fetch_all(
        """
        SELECT timestamp, app_name, bundle_id, window_title, idle_status
        FROM activity_logs
        WHERE date(timestamp) = ?
        ORDER BY timestamp ASC
        """,
        (date,)
    )

    # Calculate time spent per app
    app_time: dict[str, float] = {}
    focus_sessions: list[dict] = []
    context_switches = 0
    total_tracked_minutes = 0.0

    prev_event = None
    current_focus_start = None
    current_focus_app = None

    for event in events:
        ts = datetime.fromisoformat(event["timestamp"])
        app = event["app_name"]

        if prev_event:
            prev_ts = datetime.fromisoformat(prev_event["timestamp"])
            duration = (ts - prev_ts).total_seconds() / 60
            duration = min(duration, 15)  # Cap at 15 minutes
            total_tracked_minutes += duration

            prev_app = prev_event["app_name"]
            app_time[prev_app] = app_time.get(prev_app, 0) + duration

            if app != prev_app:
                context_switches += 1
                if current_focus_start and current_focus_app:
                    focus_duration = (prev_ts - current_focus_start).total_seconds() / 60
                    if focus_duration >= 5:
                        focus_sessions.append({
                            "app": current_focus_app,
                            "start": current_focus_start.strftime("%H:%M"),
                            "duration": round(focus_duration),
                        })
                current_focus_start = ts
                current_focus_app = app
        else:
            current_focus_start = ts
            current_focus_app = app

        prev_event = event

    # Categorize apps
    categories = {
        "Communication": ["Slack", "Messages", "Mail", "Microsoft Outlook", "Zoom", "Discord", "Microsoft Teams"],
        "Development": ["Terminal", "VS Code", "Xcode", "PyCharm", "IntelliJ", "Cursor", "Sublime Text", "iTerm2", "Code"],
        "Browsing": ["Google Chrome", "Safari", "Firefox", "Arc", "Brave Browser", "Microsoft Edge"],
        "Productivity": ["Notes", "Notion", "Obsidian", "Bear", "Things", "Reminders", "Calendar"],
        "Media": ["Spotify", "Music", "YouTube", "Netflix", "Podcasts", "VLC"],
    }

    category_time: dict[str, float] = {}
    for app, time_mins in app_time.items():
        categorized = False
        for cat, apps_list in categories.items():
            if app in apps_list:
                category_time[cat] = category_time.get(cat, 0) + time_mins
                categorized = True
                break
        if not categorized:
            category_time["Other"] = category_time.get("Other", 0) + time_mins

    # Sort and format
    sorted_apps = sorted(app_time.items(), key=lambda x: x[1], reverse=True)
    sorted_categories = sorted(category_time.items(), key=lambda x: x[1], reverse=True)
    focus_score = max(0, min(100, 100 - (context_switches * 3))) if events else 0

    return {
        "app_time": [{"app": app, "minutes": round(mins, 1)} for app, mins in sorted_apps[:15]],
        "category_time": [{"category": cat, "minutes": round(mins, 1)} for cat, mins in sorted_categories],
        "total_hours": round(total_tracked_minutes / 60, 1),
        "context_switches": context_switches,
        "focus_score": focus_score,
        "focus_sessions": sorted(focus_sessions, key=lambda x: x["duration"], reverse=True)[:10],
    }


@router.get("/apps/all")
async def get_all_apps() -> dict[str, Any]:
    """Get all-time app statistics."""
    from captains_log.web.app import get_db

    db = await get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    # All-time stats
    app_stats = await db.fetch_all(
        """
        SELECT
            app_name,
            bundle_id,
            COUNT(*) as event_count,
            MIN(timestamp) as first_seen,
            MAX(timestamp) as last_seen
        FROM activity_logs
        GROUP BY bundle_id
        ORDER BY event_count DESC
        """
    )

    # Today's apps
    today_apps = await db.fetch_all(
        """
        SELECT app_name, COUNT(*) as count
        FROM activity_logs
        WHERE date(timestamp) = ?
        GROUP BY app_name
        ORDER BY count DESC
        """,
        (today,)
    )

    return {
        "app_stats": [dict(row) for row in app_stats],
        "today_apps": [dict(row) for row in today_apps],
        "today": today,
    }
