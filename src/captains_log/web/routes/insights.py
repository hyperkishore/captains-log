"""Insights routes for AI-generated productivity recommendations."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from captains_log.core.config import get_config
from captains_log.storage.database import Database

router = APIRouter()
config = get_config()


async def get_db() -> Database:
    """Get database connection."""
    db = Database(config.db_path)
    await db.connect()
    return db


def analyze_productivity_patterns(events: list[dict]) -> dict:
    """Analyze events to find productivity patterns."""
    if not events:
        return {"wins": [], "improvements": [], "recommendations": []}

    # Calculate metrics
    total_events = len(events)

    # Count context switches
    switches = 0
    prev_app = None
    for event in events:
        app = event.get("bundle_id") or event.get("app_name")
        if prev_app and app != prev_app:
            switches += 1
        prev_app = app

    # Category breakdown
    category_counts = Counter(e.get("work_category") or "Other" for e in events)
    total_cats = sum(category_counts.values()) or 1

    # App breakdown
    app_counts = Counter(e.get("app_name", "Unknown") for e in events)

    # Hourly distribution
    hourly_counts = defaultdict(int)
    for event in events:
        ts = event.get("timestamp", "")
        if ts:
            try:
                hour = datetime.fromisoformat(ts.replace("Z", "")).hour
                hourly_counts[hour] += 1
            except (ValueError, TypeError):
                continue

    # Deep work sessions (25+ min same app)
    deep_work_minutes = 0
    session_app = None
    session_events = []

    for event in events:
        app = event.get("app_name", "Unknown")
        ts = event.get("timestamp", "")

        if not ts:
            continue

        try:
            dt = datetime.fromisoformat(ts.replace("Z", ""))
        except (ValueError, TypeError):
            continue

        if session_app == app:
            session_events.append(dt)
        else:
            # Check if previous session was deep work
            if session_events and len(session_events) >= 2:
                duration = (session_events[-1] - session_events[0]).total_seconds() / 60
                if duration >= 25:
                    deep_work_minutes += duration

            session_app = app
            session_events = [dt]

    # Generate insights
    wins = []
    improvements = []
    recommendations = []

    # Win: Good deep work
    if deep_work_minutes >= 120:
        wins.append({
            "title": "Deep Work Champion",
            "description": f"You achieved {int(deep_work_minutes)} minutes of deep work today. That's excellent focus!",
            "metric": f"{int(deep_work_minutes)}m"
        })
    elif deep_work_minutes >= 60:
        wins.append({
            "title": "Solid Focus Time",
            "description": f"You had {int(deep_work_minutes)} minutes of uninterrupted work. Good job!",
            "metric": f"{int(deep_work_minutes)}m"
        })

    # Win: Low context switching
    switch_rate = switches / (total_events / 12) if total_events > 12 else switches
    if switch_rate < 3:
        wins.append({
            "title": "Minimal Distractions",
            "description": f"Only {switches} context switches today. Your focus was strong!",
            "metric": str(switches)
        })

    # Win: Productive hours
    productive_hours = sum(1 for h, c in hourly_counts.items() if c > 5)
    if productive_hours >= 6:
        wins.append({
            "title": "Productive Day",
            "description": f"You were active during {productive_hours} hours today.",
            "metric": f"{productive_hours}h"
        })

    # Improvement: High context switching
    if switch_rate > 8:
        improvements.append({
            "title": "Frequent Context Switching",
            "description": f"You switched between apps {switches} times. Try batching similar tasks.",
            "severity": "warning"
        })

    # Improvement: Communication heavy
    comm_percent = category_counts.get("Communication", 0) / total_cats * 100
    if comm_percent > 40:
        improvements.append({
            "title": "Communication Heavy",
            "description": f"Communication took up {comm_percent:.0f}% of your time. Consider batching emails and messages.",
            "severity": "info"
        })

    # Improvement: No deep work
    if deep_work_minutes < 25:
        improvements.append({
            "title": "No Deep Work Sessions",
            "description": "You didn't have any uninterrupted work blocks of 25+ minutes today.",
            "severity": "warning"
        })

    # Recommendations based on patterns
    if hourly_counts:
        peak_hour = max(hourly_counts, key=hourly_counts.get)
        recommendations.append({
            "title": "Optimize Your Peak Time",
            "description": f"Your most productive hour is {peak_hour:02d}:00. Schedule important tasks then.",
            "action": f"Block {peak_hour:02d}:00-{(peak_hour+2)%24:02d}:00 for deep work",
            "priority": "high"
        })

    # Top app recommendation
    top_app = app_counts.most_common(1)[0] if app_counts else ("Unknown", 0)
    if top_app[1] > total_events * 0.5:
        recommendations.append({
            "title": f"Focused on {top_app[0]}",
            "description": f"You spent most of your time in {top_app[0]}. Great focus!",
            "action": "Keep this pattern for deep work days",
            "priority": "medium"
        })

    # Pareto recommendation
    sorted_apps = app_counts.most_common()
    cumulative = 0
    top_apps = []
    for app, count in sorted_apps:
        cumulative += count
        top_apps.append(app)
        if cumulative >= total_events * 0.8:
            break

    if len(top_apps) <= 3:
        recommendations.append({
            "title": "Good 80/20 Distribution",
            "description": f"Your top {len(top_apps)} apps account for 80% of your time. Efficient focus!",
            "action": "Continue prioritizing these core tools",
            "priority": "low"
        })
    else:
        recommendations.append({
            "title": "Consider Tool Consolidation",
            "description": f"You used {len(top_apps)} apps for 80% of your work. Some overlap possible?",
            "action": "Audit which apps serve similar purposes",
            "priority": "medium"
        })

    return {
        "wins": wins,
        "improvements": improvements,
        "recommendations": recommendations,
        "metrics": {
            "total_events": total_events,
            "context_switches": switches,
            "deep_work_minutes": int(deep_work_minutes),
            "productive_hours": productive_hours,
            "top_category": category_counts.most_common(1)[0][0] if category_counts else "Unknown"
        }
    }


def generate_daily_narrative(events: list[dict], date: str) -> str:
    """Generate a narrative summary of the day."""
    if not events:
        return "No activity recorded today."

    total_events = len(events)
    hours_estimate = total_events * 0.5 / 60

    # Get top apps and categories
    app_counts = Counter(e.get("app_name", "Unknown") for e in events)
    category_counts = Counter(e.get("work_category") or "Other" for e in events)

    top_apps = [app for app, _ in app_counts.most_common(3)]
    top_category = category_counts.most_common(1)[0][0] if category_counts else "work"

    # Determine day character
    if hours_estimate < 2:
        intensity = "light"
    elif hours_estimate < 5:
        intensity = "moderate"
    else:
        intensity = "intensive"

    # Build narrative
    day_name = datetime.fromisoformat(date).strftime("%A")

    narrative = f"Your {day_name} was a {intensity} day with approximately {hours_estimate:.1f} hours of tracked activity. "
    narrative += f"You focused primarily on {top_category.lower()} work, "
    narrative += f"spending most of your time in {', '.join(top_apps[:2])}. "

    return narrative


@router.get("/analytics/insights", response_class=HTMLResponse)
async def analytics_insights(request: Request, date: str | None = None):
    """AI-generated insights and recommendations."""
    db = await get_db()

    try:
        # Parse date
        if date:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        else:
            target_date = datetime.now().date()

        # Fetch today's events
        events = await db.fetch_all(
            """
            SELECT * FROM activity_logs
            WHERE date(timestamp) = ?
            ORDER BY timestamp ASC
            """,
            (target_date.isoformat(),),
        )

        # Fetch last 7 days for comparison
        week_ago = (target_date - timedelta(days=7)).isoformat()
        week_events = await db.fetch_all(
            """
            SELECT * FROM activity_logs
            WHERE date(timestamp) >= ? AND date(timestamp) < ?
            ORDER BY timestamp ASC
            """,
            (week_ago, target_date.isoformat()),
        )

        # Generate insights
        insights = analyze_productivity_patterns(events)
        narrative = generate_daily_narrative(events, target_date.isoformat())

        # Weekly comparison
        week_total = len(week_events)
        daily_avg = week_total / 7 if week_total > 0 else 0
        today_vs_avg = "above" if len(events) > daily_avg * 1.1 else ("below" if len(events) < daily_avg * 0.9 else "at")

        # Check if Sunday for weekly reflection
        is_sunday = target_date.weekday() == 6
        weekly_reflection = None

        if is_sunday and week_events:
            week_insights = analyze_productivity_patterns(week_events)
            weekly_reflection = {
                "total_hours": round(len(week_events) * 0.5 / 60, 1),
                "deep_work_hours": round(week_insights["metrics"]["deep_work_minutes"] / 60, 1),
                "top_category": week_insights["metrics"]["top_category"],
                "wins": len(week_insights["wins"]),
                "improvements": len(week_insights["improvements"])
            }

        templates = request.app.state.templates
        return templates.TemplateResponse(
            "analytics/insights.html",
            {
                "request": request,
                "date": target_date.isoformat(),
                "date_display": target_date.strftime("%A, %B %d, %Y"),
                "narrative": narrative,
                "wins": insights["wins"],
                "improvements": insights["improvements"],
                "recommendations": insights["recommendations"],
                "metrics": insights["metrics"],
                "today_vs_avg": today_vs_avg,
                "daily_avg": round(daily_avg * 0.5 / 60, 1),
                "has_data": len(events) > 0,
                "is_sunday": is_sunday,
                "weekly_reflection": weekly_reflection,
            },
        )
    finally:
        await db.close()


@router.get("/api/insights/daily/{date}")
async def api_daily_insights(date: str):
    """Get AI insights for a specific date."""
    db = await get_db()
    try:
        events = await db.fetch_all(
            "SELECT * FROM activity_logs WHERE date(timestamp) = ? ORDER BY timestamp",
            (date,),
        )
        insights = analyze_productivity_patterns(events)
        narrative = generate_daily_narrative(events, date)
        return {
            "narrative": narrative,
            **insights
        }
    finally:
        await db.close()
