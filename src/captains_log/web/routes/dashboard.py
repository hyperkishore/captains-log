"""Dashboard page routes."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

if TYPE_CHECKING:
    pass

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Main dashboard page."""
    from captains_log.web.app import get_db

    db = await get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    # Get today's stats
    activity_count = await db.fetch_one(
        "SELECT COUNT(*) as count FROM activity_logs WHERE date(timestamp) = ?",
        (today,)
    )

    # Get top apps today
    top_apps = await db.fetch_all(
        """
        SELECT app_name, COUNT(*) as count
        FROM activity_logs
        WHERE date(timestamp) = ?
        GROUP BY app_name
        ORDER BY count DESC
        LIMIT 10
        """,
        (today,)
    )

    # Get recent activity
    recent = await db.fetch_all(
        """
        SELECT timestamp, app_name, window_title, idle_status
        FROM activity_logs
        ORDER BY timestamp DESC
        LIMIT 20
        """
    )

    # Get hourly breakdown
    hourly = await db.fetch_all(
        """
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
        FROM activity_logs
        WHERE date(timestamp) = ?
        GROUP BY hour
        ORDER BY hour
        """,
        (today,)
    )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "today": today,
            "activity_count": activity_count["count"] if activity_count else 0,
            "top_apps": top_apps,
            "recent_activity": recent,
            "hourly_data": hourly,
        }
    )


@router.get("/timeline", response_class=HTMLResponse)
async def timeline(
    request: Request,
    date: str | None = None,
) -> HTMLResponse:
    """Activity timeline view."""
    from captains_log.web.app import get_db

    db = await get_db()

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Get all activity for the date
    activities = await db.fetch_all(
        """
        SELECT timestamp, app_name, bundle_id, window_title, url, idle_status, is_fullscreen
        FROM activity_logs
        WHERE date(timestamp) = ?
        ORDER BY timestamp DESC
        """,
        (date,)
    )

    # Get available dates for navigation
    dates = await db.fetch_all(
        """
        SELECT DISTINCT date(timestamp) as date
        FROM activity_logs
        ORDER BY date DESC
        LIMIT 30
        """
    )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "timeline.html",
        {
            "request": request,
            "date": date,
            "activities": activities,
            "available_dates": [d["date"] for d in dates],
        }
    )


@router.get("/apps", response_class=HTMLResponse)
async def apps(request: Request) -> HTMLResponse:
    """App usage breakdown view."""
    from captains_log.web.app import get_db

    db = await get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    # Get app usage stats
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

    # Get today's app usage
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

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "apps.html",
        {
            "request": request,
            "app_stats": app_stats,
            "today_apps": today_apps,
            "today": today,
        }
    )
