"""Analytics routes for productivity insights dashboard."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from captains_log.core.config import get_config
from captains_log.storage.database import Database

router = APIRouter()
config = get_config()


# ============================================================================
# CALCULATION FUNCTIONS
# ============================================================================

def calculate_time_blocks(events: list[dict], interval_minutes: int = 60) -> list[dict]:
    """Calculate time blocks by hour with category breakdown."""
    blocks = defaultdict(lambda: defaultdict(int))

    for event in events:
        ts = event.get("timestamp", "")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", ""))
            hour = dt.hour
            category = event.get("work_category") or "Other"
            blocks[hour][category] += 1
        except (ValueError, TypeError):
            continue

    result = []
    for hour in range(24):
        if hour in blocks:
            categories = dict(blocks[hour])
            total = sum(categories.values())
            result.append({
                "hour": hour,
                "hour_label": f"{hour:02d}:00",
                "categories": categories,
                "total": total,
                "primary_category": max(categories, key=categories.get) if categories else "Other"
            })

    return result


def calculate_deep_work_sessions(events: list[dict], min_duration_min: int = 25) -> list[dict]:
    """Identify uninterrupted work sessions of 25+ minutes."""
    if not events:
        return []

    sessions = []
    current_session = None

    for i, event in enumerate(events):
        ts = event.get("timestamp", "")
        app = event.get("app_name", "Unknown")

        if not ts:
            continue

        try:
            dt = datetime.fromisoformat(ts.replace("Z", ""))
        except (ValueError, TypeError):
            continue

        if current_session is None:
            current_session = {
                "start": dt,
                "app": app,
                "events": 1,
                "category": event.get("work_category", "Other")
            }
        elif app == current_session["app"]:
            current_session["events"] += 1
            current_session["end"] = dt
        else:
            # Session ended - check duration
            end_dt = current_session.get("end", current_session["start"])
            duration_min = (end_dt - current_session["start"]).total_seconds() / 60

            if duration_min >= min_duration_min:
                sessions.append({
                    "app": current_session["app"],
                    "category": current_session["category"],
                    "start": current_session["start"].strftime("%H:%M"),
                    "duration_min": round(duration_min),
                    "events": current_session["events"]
                })

            # Start new session
            current_session = {
                "start": dt,
                "app": app,
                "events": 1,
                "category": event.get("work_category", "Other")
            }

    # Don't forget last session
    if current_session and "end" in current_session:
        duration_min = (current_session["end"] - current_session["start"]).total_seconds() / 60
        if duration_min >= min_duration_min:
            sessions.append({
                "app": current_session["app"],
                "category": current_session["category"],
                "start": current_session["start"].strftime("%H:%M"),
                "duration_min": round(duration_min),
                "events": current_session["events"]
            })

    return sessions


def calculate_pareto_breakdown(events: list[dict]) -> dict:
    """Calculate 80/20 Pareto analysis by app."""
    app_counts = Counter(e.get("app_name", "Unknown") for e in events)
    total = sum(app_counts.values())

    if total == 0:
        return {"top_apps": [], "rest_apps": [], "ratio": "0/0", "top_percent": 0}

    sorted_apps = app_counts.most_common()
    cumulative = 0
    top_apps = []
    rest_apps = []

    for app, count in sorted_apps:
        percent = count / total * 100
        cumulative += count

        entry = {
            "app": app,
            "count": count,
            "percent": round(percent, 1),
            "cumulative_percent": round(cumulative / total * 100, 1)
        }

        if cumulative <= total * 0.8:
            top_apps.append(entry)
        else:
            rest_apps.append(entry)

    top_percent = round(sum(a["percent"] for a in top_apps), 1) if top_apps else 0

    return {
        "top_apps": top_apps,
        "rest_apps": rest_apps,
        "ratio": f"{len(top_apps)}/{len(rest_apps)}",
        "top_percent": top_percent
    }


def calculate_category_breakdown(events: list[dict]) -> list[dict]:
    """Calculate time breakdown by work category."""
    category_counts = Counter(e.get("work_category") or "Other" for e in events)
    total = sum(category_counts.values())

    result = []
    for category, count in category_counts.most_common():
        percent = count / total * 100 if total > 0 else 0

        # Get top apps for this category
        category_events = [e for e in events if (e.get("work_category") or "Other") == category]
        app_counts = Counter(e.get("app_name", "Unknown") for e in category_events)
        top_apps = [{"app": app, "count": c} for app, c in app_counts.most_common(3)]

        result.append({
            "category": category,
            "count": count,
            "percent": round(percent, 1),
            "minutes": round(count * 0.5),  # Rough estimate: 30 sec per event
            "top_apps": top_apps
        })

    return result


def calculate_project_breakdown(events: list[dict]) -> list[dict]:
    """Calculate time breakdown by project."""
    project_counts = defaultdict(lambda: {"count": 0, "apps": Counter()})

    for event in events:
        project = event.get("work_project") or event.get("app_name", "Unknown")
        project_counts[project]["count"] += 1
        project_counts[project]["apps"][event.get("app_name", "Unknown")] += 1

    total = sum(p["count"] for p in project_counts.values())

    result = []
    for project, data in sorted(project_counts.items(), key=lambda x: x[1]["count"], reverse=True)[:10]:
        percent = data["count"] / total * 100 if total > 0 else 0
        result.append({
            "project": project,
            "count": data["count"],
            "percent": round(percent, 1),
            "minutes": round(data["count"] * 0.5),
            "primary_app": data["apps"].most_common(1)[0][0] if data["apps"] else "Unknown"
        })

    return result


def calculate_focus_score(events: list[dict]) -> int:
    """Calculate overall focus score (0-100)."""
    if not events:
        return 0

    # Count context switches
    switches = 0
    prev_app = None
    for event in events:
        app = event.get("bundle_id") or event.get("app_name")
        if prev_app and app != prev_app:
            switches += 1
        prev_app = app

    # Calculate engagement
    total_engagement = sum(e.get("engagement_score", 0) for e in events)
    avg_engagement = total_engagement / len(events) if events else 0

    # Calculate active percentage
    active_events = sum(1 for e in events if e.get("idle_status") == "ACTIVE")
    active_percent = active_events / len(events) * 100 if events else 0

    # Focus score formula
    # Fewer switches = higher score
    switch_penalty = min(50, switches * 2)  # Max 50 point penalty
    engagement_bonus = avg_engagement * 0.3  # Up to 30 points
    active_bonus = active_percent * 0.2  # Up to 20 points

    score = 100 - switch_penalty + engagement_bonus + active_bonus
    return max(0, min(100, round(score)))


def calculate_context_switches(events: list[dict]) -> int:
    """Count context switches (app changes)."""
    if len(events) < 2:
        return 0

    switches = 0
    prev_app = events[0].get("bundle_id") or events[0].get("app_name")

    for event in events[1:]:
        app = event.get("bundle_id") or event.get("app_name")
        if app and app != prev_app:
            switches += 1
            prev_app = app

    return switches


def calculate_focus_over_time(events: list[dict], interval_minutes: int = 30) -> list[dict]:
    """Calculate focus score over time in intervals."""
    if not events:
        return []

    # Group events by interval
    intervals = defaultdict(list)

    for event in events:
        ts = event.get("timestamp", "")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", ""))
            interval_key = dt.replace(minute=(dt.minute // interval_minutes) * interval_minutes, second=0, microsecond=0)
            intervals[interval_key].append(event)
        except (ValueError, TypeError):
            continue

    result = []
    for interval_time in sorted(intervals.keys()):
        interval_events = intervals[interval_time]
        focus = calculate_focus_score(interval_events)
        switches = calculate_context_switches(interval_events)

        result.append({
            "time": interval_time.strftime("%H:%M"),
            "timestamp": interval_time.isoformat(),
            "focus_score": focus,
            "context_switches": switches,
            "event_count": len(interval_events)
        })

    return result


def get_quick_insights(events: list[dict], deep_work_sessions: list[dict], pareto: dict) -> list[dict]:
    """Generate quick insights from activity data."""
    insights = []

    # Deep work insight
    if deep_work_sessions:
        longest = max(deep_work_sessions, key=lambda x: x["duration_min"])
        insights.append({
            "type": "success",
            "icon": "✓",
            "text": f"Longest focus block: {longest['duration_min']} min on {longest['app']}"
        })
    else:
        insights.append({
            "type": "warning",
            "icon": "!",
            "text": "No deep work sessions (25+ min) detected today"
        })

    # Context switching insight
    switches = calculate_context_switches(events)
    events_count = len(events)
    if events_count > 0:
        switch_rate = switches / (events_count / 12)  # per 5 min
        if switch_rate > 5:
            insights.append({
                "type": "warning",
                "icon": "!",
                "text": f"High context switching: {switches} switches today"
            })
        else:
            insights.append({
                "type": "success",
                "icon": "✓",
                "text": f"Good focus: only {switches} context switches"
            })

    # Pareto insight
    if pareto["top_apps"]:
        insights.append({
            "type": "info",
            "icon": "→",
            "text": f"80/20 ratio: {pareto['ratio']} - top {len(pareto['top_apps'])} apps = {pareto['top_percent']:.0f}% of time"
        })

    return insights


def build_treemap_data(events: list[dict]) -> dict:
    """Build hierarchical data for treemap visualization."""
    # Category -> App -> Count
    hierarchy = defaultdict(lambda: defaultdict(int))

    for event in events:
        category = event.get("work_category") or "Other"
        app = event.get("app_name", "Unknown")
        hierarchy[category][app] += 1

    # Convert to treemap format
    children = []
    for category, apps in hierarchy.items():
        category_children = [
            {"name": app, "value": count}
            for app, count in sorted(apps.items(), key=lambda x: x[1], reverse=True)
        ]
        children.append({
            "name": category,
            "children": category_children
        })

    return {
        "name": "Activity",
        "children": sorted(children, key=lambda x: sum(c["value"] for c in x["children"]), reverse=True)
    }


# ============================================================================
# ROUTE HANDLERS
# ============================================================================

async def get_db() -> Database:
    """Get database connection."""
    db = Database(config.db_path)
    await db.connect()
    return db


@router.get("/analytics", response_class=HTMLResponse)
@router.get("/analytics/overview", response_class=HTMLResponse)
async def analytics_overview(request: Request, date: str | None = None):
    """Main analytics dashboard with all key metrics."""
    db = await get_db()

    try:
        # Parse date
        if date:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        else:
            target_date = datetime.now().date()

        # Fetch activities for the day
        events = await db.fetch_all(
            """
            SELECT * FROM activity_logs
            WHERE date(timestamp) = ?
            ORDER BY timestamp ASC
            """,
            (target_date.isoformat(),),
        )

        # Calculate all metrics
        time_blocks = calculate_time_blocks(events)
        categories = calculate_category_breakdown(events)
        projects = calculate_project_breakdown(events)
        deep_work = calculate_deep_work_sessions(events)
        pareto = calculate_pareto_breakdown(events)
        focus_score = calculate_focus_score(events)
        focus_over_time = calculate_focus_over_time(events)
        context_switches = calculate_context_switches(events)
        insights = get_quick_insights(events, deep_work, pareto)

        # Calculate totals
        total_events = len(events)
        total_hours = round(total_events * 0.5 / 60, 1)  # ~30 sec per event
        deep_work_hours = round(sum(s["duration_min"] for s in deep_work) / 60, 1)

        templates = request.app.state.templates
        return templates.TemplateResponse(
            "analytics/overview.html",
            {
                "request": request,
                "date": target_date.isoformat(),
                "date_display": target_date.strftime("%A, %B %d, %Y"),
                "total_hours": total_hours,
                "deep_work_hours": deep_work_hours,
                "focus_score": focus_score,
                "context_switches": context_switches,
                "pareto_ratio": pareto["ratio"],
                "time_blocks": time_blocks,
                "time_blocks_json": json.dumps(time_blocks),
                "categories": categories,
                "categories_json": json.dumps(categories),
                "projects": projects,
                "deep_work_sessions": deep_work,
                "focus_over_time": focus_over_time,
                "focus_over_time_json": json.dumps(focus_over_time),
                "insights": insights,
                "total_events": total_events,
            },
        )
    finally:
        await db.close()


@router.get("/analytics/deep-dive", response_class=HTMLResponse)
async def analytics_deep_dive(
    request: Request,
    date: str | None = None,
    category: str | None = None,
):
    """Detailed breakdown with treemap and drill-down."""
    db = await get_db()

    try:
        if date:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        else:
            target_date = datetime.now().date()

        # Build query
        query = "SELECT * FROM activity_logs WHERE date(timestamp) = ?"
        params: list[Any] = [target_date.isoformat()]

        if category:
            query += " AND work_category = ?"
            params.append(category)

        query += " ORDER BY timestamp ASC"

        events = await db.fetch_all(query, tuple(params))

        # Calculate metrics
        treemap_data = build_treemap_data(events)
        categories = calculate_category_breakdown(events)
        projects = calculate_project_breakdown(events)
        pareto = calculate_pareto_breakdown(events)

        templates = request.app.state.templates
        return templates.TemplateResponse(
            "analytics/deep_dive.html",
            {
                "request": request,
                "date": target_date.isoformat(),
                "date_display": target_date.strftime("%A, %B %d, %Y"),
                "selected_category": category,
                "treemap_data": json.dumps(treemap_data),
                "categories": categories,
                "projects": projects,
                "pareto": pareto,
                "total_events": len(events),
            },
        )
    finally:
        await db.close()


@router.get("/analytics/trends", response_class=HTMLResponse)
async def analytics_trends(request: Request, weeks: int = 4):
    """Week-over-week comparison and patterns."""
    db = await get_db()

    try:
        # Get data for the past N weeks
        today = datetime.now().date()
        start_date = today - timedelta(days=weeks * 7)

        events = await db.fetch_all(
            """
            SELECT * FROM activity_logs
            WHERE date(timestamp) >= ?
            ORDER BY timestamp ASC
            """,
            (start_date.isoformat(),),
        )

        has_data = len(events) > 0

        # Group by day
        daily_data = defaultdict(list)
        for event in events:
            ts = event.get("timestamp", "")
            if ts:
                try:
                    day = datetime.fromisoformat(ts.replace("Z", "")).date().isoformat()
                    daily_data[day].append(event)
                except (ValueError, TypeError):
                    continue

        # Calculate daily metrics
        daily_metrics = {}
        for day in sorted(daily_data.keys()):
            day_events = daily_data[day]
            daily_metrics[day] = {
                "date": day,
                "day_name": datetime.fromisoformat(day).strftime("%a"),
                "total_events": len(day_events),
                "hours": round(len(day_events) * 0.5 / 60, 1),
                "focus_score": calculate_focus_score(day_events),
                "context_switches": calculate_context_switches(day_events),
                "categories": calculate_category_breakdown(day_events)
            }

        # Split into this week vs last week
        week_start = today - timedelta(days=today.weekday())
        last_week_start = week_start - timedelta(days=7)

        # Get days so far this week (up to and including today)
        days_in_week = today.weekday() + 1
        this_week_days = [(week_start + timedelta(days=i)).isoformat() for i in range(days_in_week)]
        last_week_same_days = [(last_week_start + timedelta(days=i)).isoformat() for i in range(days_in_week)]

        # Calculate week totals
        this_week_hours = sum(daily_metrics.get(d, {}).get("hours", 0) for d in this_week_days)
        last_week_hours = sum(daily_metrics.get(d, {}).get("hours", 0) for d in last_week_same_days)

        total_change = 0
        if last_week_hours > 0:
            total_change = round((this_week_hours - last_week_hours) / last_week_hours * 100)
        total_change_class = "positive" if total_change > 0 else ("negative" if total_change < 0 else "neutral")

        # Calculate category trends
        this_week_events = []
        last_week_events = []
        for d in this_week_days:
            this_week_events.extend(daily_data.get(d, []))
        for d in last_week_same_days:
            last_week_events.extend(daily_data.get(d, []))

        this_week_cats = Counter(e.get("work_category") or "Other" for e in this_week_events)
        last_week_cats = Counter(e.get("work_category") or "Other" for e in last_week_events)

        this_week_total = sum(this_week_cats.values()) or 1
        last_week_total = sum(last_week_cats.values()) or 1

        all_categories = set(this_week_cats.keys()) | set(last_week_cats.keys())
        category_trends = []
        for cat in all_categories:
            this_pct = round(this_week_cats.get(cat, 0) / this_week_total * 100)
            last_pct = round(last_week_cats.get(cat, 0) / last_week_total * 100)
            change = this_pct - last_pct
            direction = "up" if change > 0 else ("down" if change < 0 else "same")
            category_trends.append({
                "category": cat,
                "this_week_pct": this_pct,
                "last_week_pct": last_pct,
                "change": abs(change),
                "direction": direction
            })
        category_trends.sort(key=lambda x: x["this_week_pct"], reverse=True)

        # Calculate hourly patterns for peak hours
        hourly_this = defaultdict(int)
        hourly_last = defaultdict(int)

        for event in this_week_events:
            ts = event.get("timestamp", "")
            if ts:
                try:
                    hour = datetime.fromisoformat(ts.replace("Z", "")).hour
                    hourly_this[hour] += 1
                except (ValueError, TypeError):
                    continue

        for event in last_week_events:
            ts = event.get("timestamp", "")
            if ts:
                try:
                    hour = datetime.fromisoformat(ts.replace("Z", "")).hour
                    hourly_last[hour] += 1
                except (ValueError, TypeError):
                    continue

        max_this = max(hourly_this.values()) if hourly_this else 1
        max_last = max(hourly_last.values()) if hourly_last else 1
        max_overall = max(max_this, max_last, 1)

        peak_hours = []
        for hour in range(6, 24):  # Show 6am to 11pm
            this_count = hourly_this.get(hour, 0)
            last_count = hourly_last.get(hour, 0)
            peak_hours.append({
                "hour": hour,
                "label": f"{hour:02d}",
                "this_week_pct": round(this_count / max_overall * 100),
                "last_week_pct": round(last_count / max_overall * 100)
            })

        # Build heatmap data (last 4 weeks)
        heatmap_data = []
        for week in range(4):
            week_start_date = today - timedelta(days=today.weekday() + (3 - week) * 7)
            for day_offset in range(7):
                day_date = week_start_date + timedelta(days=day_offset)
                day_str = day_date.isoformat()
                day_events = daily_data.get(day_str, [])
                focus = calculate_focus_score(day_events) if day_events else 0

                # Calculate level (0-5 based on focus score)
                level = min(5, focus // 20) if day_events else 0

                heatmap_data.append({
                    "date": day_str,
                    "day": day_date.day,
                    "score": focus,
                    "level": level,
                    "is_today": day_date == today
                })

        # Weekly chart data
        day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        weekly_chart_data = {
            "labels": day_labels[:days_in_week],
            "this_week": [daily_metrics.get(d, {}).get("hours", 0) for d in this_week_days],
            "last_week": [daily_metrics.get(d, {}).get("hours", 0) for d in last_week_same_days]
        }

        # Pattern detection
        patterns = []

        # Peak productivity time
        if hourly_this:
            peak_hour = max(hourly_this, key=hourly_this.get)
            patterns.append({
                "icon": "⏰",
                "title": f"Peak Productivity at {peak_hour:02d}:00",
                "description": f"You're most active around {peak_hour:02d}:00. Consider scheduling important tasks during this time."
            })

        # Deep work trend
        this_week_deep = sum(1 for d in this_week_days if daily_metrics.get(d, {}).get("focus_score", 0) > 70)
        if this_week_deep >= 3:
            patterns.append({
                "icon": "🎯",
                "title": "Strong Focus Week",
                "description": f"You've had {this_week_deep} high-focus days this week. Keep up the momentum!"
            })
        elif this_week_deep == 0 and len(this_week_days) >= 3:
            patterns.append({
                "icon": "⚡",
                "title": "Focus Opportunity",
                "description": "No high-focus days detected this week. Consider blocking distractions for deeper work."
            })

        # Category shift
        for trend in category_trends[:2]:
            if trend["change"] >= 15:
                patterns.append({
                    "icon": "📊",
                    "title": f"{trend['category']} {'Increased' if trend['direction'] == 'up' else 'Decreased'}",
                    "description": f"{trend['category']} is {'up' if trend['direction'] == 'up' else 'down'} {trend['change']}% compared to last week."
                })

        templates = request.app.state.templates
        return templates.TemplateResponse(
            "analytics/trends.html",
            {
                "request": request,
                "has_data": has_data,
                "this_week_hours": round(this_week_hours, 1),
                "last_week_hours": round(last_week_hours, 1),
                "total_change": total_change,
                "total_change_class": total_change_class,
                "category_trends": category_trends,
                "peak_hours": peak_hours,
                "heatmap_data": heatmap_data,
                "patterns": patterns,
                "weekly_chart_data": json.dumps(weekly_chart_data),
            },
        )
    finally:
        await db.close()


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/api/analytics/time-blocks/{date}")
async def api_time_blocks(date: str):
    """Get hourly time blocks for visualization."""
    db = await get_db()
    try:
        events = await db.fetch_all(
            "SELECT * FROM activity_logs WHERE date(timestamp) = ? ORDER BY timestamp",
            (date,),
        )
        return calculate_time_blocks(events)
    finally:
        await db.close()


@router.get("/api/analytics/treemap/{date}")
async def api_treemap(date: str):
    """Get hierarchical data for treemap."""
    db = await get_db()
    try:
        events = await db.fetch_all(
            "SELECT * FROM activity_logs WHERE date(timestamp) = ? ORDER BY timestamp",
            (date,),
        )
        return build_treemap_data(events)
    finally:
        await db.close()


@router.get("/api/analytics/pareto/{date}")
async def api_pareto(date: str):
    """Get 80/20 analysis data."""
    db = await get_db()
    try:
        events = await db.fetch_all(
            "SELECT * FROM activity_logs WHERE date(timestamp) = ? ORDER BY timestamp",
            (date,),
        )
        return calculate_pareto_breakdown(events)
    finally:
        await db.close()


@router.get("/api/analytics/focus-history")
async def api_focus_history(days: int = 28):
    """Get focus score history for heatmap."""
    db = await get_db()
    try:
        start_date = (datetime.now() - timedelta(days=days)).date().isoformat()

        events = await db.fetch_all(
            "SELECT * FROM activity_logs WHERE date(timestamp) >= ? ORDER BY timestamp",
            (start_date,),
        )

        # Group by day and calculate focus
        daily_focus = defaultdict(list)
        for event in events:
            ts = event.get("timestamp", "")
            if ts:
                try:
                    day = datetime.fromisoformat(ts.replace("Z", "")).date().isoformat()
                    daily_focus[day].append(event)
                except (ValueError, TypeError):
                    continue

        result = []
        for day in sorted(daily_focus.keys()):
            result.append({
                "date": day,
                "focus_score": calculate_focus_score(daily_focus[day]),
                "event_count": len(daily_focus[day])
            })

        return result
    finally:
        await db.close()
