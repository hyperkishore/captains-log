"""Dashboard page routes."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

if TYPE_CHECKING:
    pass

router = APIRouter(tags=["dashboard"])

# URL to Work Category Mapping
URL_CATEGORIES = {
    # Development
    "github.com": ("Development", "🛠️", "#10b981"),
    "gitlab.com": ("Development", "🛠️", "#10b981"),
    "bitbucket.org": ("Development", "🛠️", "#10b981"),
    "stackoverflow.com": ("Development", "🛠️", "#10b981"),
    "developer.apple.com": ("Development", "🛠️", "#10b981"),
    "docs.python.org": ("Development", "🛠️", "#10b981"),
    "npmjs.com": ("Development", "🛠️", "#10b981"),
    "pypi.org": ("Development", "🛠️", "#10b981"),

    # Communication
    "slack.com": ("Communication", "💬", "#ff9500"),
    "mail.google.com": ("Communication", "💬", "#ff9500"),
    "outlook.live.com": ("Communication", "💬", "#ff9500"),
    "teams.microsoft.com": ("Communication", "💬", "#ff9500"),
    "discord.com": ("Communication", "💬", "#ff9500"),
    "zoom.us": ("Communication", "💬", "#ff9500"),

    # Productivity
    "notion.so": ("Productivity", "📝", "#0071e3"),
    "docs.google.com": ("Productivity", "📝", "#0071e3"),
    "sheets.google.com": ("Productivity", "📝", "#0071e3"),
    "drive.google.com": ("Productivity", "📝", "#0071e3"),
    "figma.com": ("Productivity", "📝", "#0071e3"),
    "linear.app": ("Productivity", "📝", "#0071e3"),
    "trello.com": ("Productivity", "📝", "#0071e3"),
    "asana.com": ("Productivity", "📝", "#0071e3"),
    "jira.atlassian.com": ("Productivity", "📝", "#0071e3"),

    # Research/Learning
    "youtube.com": ("Research", "📚", "#af52de"),
    "medium.com": ("Research", "📚", "#af52de"),
    "dev.to": ("Research", "📚", "#af52de"),
    "arxiv.org": ("Research", "📚", "#af52de"),
    "news.ycombinator.com": ("Research", "📚", "#af52de"),

    # Social/Distractions
    "twitter.com": ("Social", "🎭", "#ff3b30"),
    "x.com": ("Social", "🎭", "#ff3b30"),
    "facebook.com": ("Social", "🎭", "#ff3b30"),
    "instagram.com": ("Social", "🎭", "#ff3b30"),
    "reddit.com": ("Social", "🎭", "#ff3b30"),
    "linkedin.com": ("Social", "🎭", "#ff3b30"),
    "tiktok.com": ("Social", "🎭", "#ff3b30"),
}

def categorize_url(url: str) -> tuple[str, str, str]:
    """Categorize a URL into work category."""
    if not url:
        return ("Other", "🔗", "#86868b")

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Remove www prefix
        if domain.startswith("www."):
            domain = domain[4:]

        # Check exact match
        if domain in URL_CATEGORIES:
            return URL_CATEGORIES[domain]

        # Check subdomain matches
        for known_domain, category in URL_CATEGORIES.items():
            if domain.endswith("." + known_domain) or domain == known_domain:
                return category

        # Localhost = Development
        if domain.startswith("127.0.0.1") or domain.startswith("localhost"):
            return ("Development", "🛠️", "#10b981")

    except Exception:
        pass

    return ("Other", "🔗", "#86868b")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Apple-style unified dashboard."""
    from captains_log.web.app import get_db

    db = await get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    # Get all activity events for today (including new work context and input fields)
    events = await db.fetch_all(
        """
        SELECT timestamp, app_name, bundle_id, window_title, url, idle_status,
               work_category, work_service, work_project, work_document,
               work_meeting, work_channel, work_issue_id, work_organization,
               keystrokes, mouse_clicks, scroll_events, engagement_score
        FROM activity_logs
        WHERE date(timestamp) = ?
        ORDER BY timestamp ASC
        """,
        (today,)
    )

    # Calculate time spent per app and URLs
    app_time: dict[str, float] = {}
    url_time: dict[str, float] = {}
    url_visits: dict[str, int] = {}
    context_switches = 0
    total_minutes = 0.0
    deep_work_minutes = 0.0

    # Track work context
    project_time: dict[str, float] = {}  # Time per project/repo
    meeting_time: dict[str, float] = {}  # Time per meeting
    document_time: dict[str, float] = {}  # Time per document
    service_time: dict[str, float] = {}  # Time per service (github, slack, etc.)
    org_time: dict[str, float] = {}  # Time per organization

    # Track engagement metrics
    total_keystrokes = 0
    total_clicks = 0
    total_scrolls = 0

    prev_event = None
    current_focus_start = None
    current_focus_app = None

    for event in events:
        ts = datetime.fromisoformat(event["timestamp"])
        app = event["app_name"]

        # Accumulate input metrics
        total_keystrokes += event.get("keystrokes", 0) or 0
        total_clicks += event.get("mouse_clicks", 0) or 0
        total_scrolls += event.get("scroll_events", 0) or 0

        if prev_event:
            prev_ts = datetime.fromisoformat(prev_event["timestamp"])
            duration = min((ts - prev_ts).total_seconds() / 60, 15)  # Cap at 15 min
            total_minutes += duration

            prev_app = prev_event["app_name"]
            app_time[prev_app] = app_time.get(prev_app, 0) + duration

            # Track URL time
            prev_url = prev_event["url"]
            if prev_url:
                domain = urlparse(prev_url).netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                url_time[domain] = url_time.get(domain, 0) + duration
                url_visits[domain] = url_visits.get(domain, 0) + 1

            # Track work context time
            if prev_event.get("work_project"):
                project_time[prev_event["work_project"]] = project_time.get(prev_event["work_project"], 0) + duration
            if prev_event.get("work_meeting"):
                meeting_time[prev_event["work_meeting"]] = meeting_time.get(prev_event["work_meeting"], 0) + duration
            if prev_event.get("work_document"):
                document_time[prev_event["work_document"]] = document_time.get(prev_event["work_document"], 0) + duration
            if prev_event.get("work_service"):
                service_time[prev_event["work_service"]] = service_time.get(prev_event["work_service"], 0) + duration
            if prev_event.get("work_organization"):
                org_time[prev_event["work_organization"]] = org_time.get(prev_event["work_organization"], 0) + duration

            # Track context switches and deep work
            if app != prev_app:
                context_switches += 1
                if current_focus_start and current_focus_app:
                    focus_duration = (prev_ts - current_focus_start).total_seconds() / 60
                    if focus_duration >= 25:
                        deep_work_minutes += focus_duration
                current_focus_start = ts
                current_focus_app = app
        else:
            current_focus_start = ts
            current_focus_app = app

        prev_event = event

    # Calculate work categories from apps
    app_categories = {
        "Development": ["Terminal", "VS Code", "Xcode", "PyCharm", "IntelliJ", "Cursor", "iTerm2", "Code"],
        "Communication": ["Slack", "Messages", "Mail", "Microsoft Outlook", "Zoom", "Discord", "Teams"],
        "Productivity": ["Notes", "Notion", "Obsidian", "Bear", "Things", "Reminders", "Calendar", "Preview"],
        "Media": ["Spotify", "Music", "YouTube", "Netflix", "Podcasts", "VLC", "QuickTime Player"],
        "Browsing": ["Google Chrome", "Safari", "Firefox", "Arc", "Brave Browser", "Microsoft Edge"],
    }

    work_categories = []
    max_minutes = max(sum(app_time.values()), 1)

    for cat_name, apps in app_categories.items():
        cat_minutes = sum(app_time.get(app, 0) for app in apps)
        if cat_minutes > 0:
            top_apps = [(app, app_time.get(app, 0)) for app in apps if app_time.get(app, 0) > 0]
            top_apps.sort(key=lambda x: x[1], reverse=True)

            colors = {
                "Development": "#10b981",
                "Communication": "#ff9500",
                "Productivity": "#0071e3",
                "Media": "#af52de",
                "Browsing": "#3b82f6",
            }
            icons = {
                "Development": "🛠️",
                "Communication": "💬",
                "Productivity": "📝",
                "Media": "🎵",
                "Browsing": "🌐",
            }

            work_categories.append({
                "name": cat_name,
                "minutes": cat_minutes,
                "percent": min(100, (cat_minutes / max_minutes) * 100),
                "color": colors.get(cat_name, "#86868b"),
                "icon": icons.get(cat_name, "📁"),
                "top_items": [app for app, _ in top_apps[:4]],
            })

    work_categories.sort(key=lambda x: x["minutes"], reverse=True)

    # Calculate focus score
    focus_score = max(0, min(100, 100 - (context_switches * 2))) if events else 0

    # Generate insights
    insights = []

    # Find biggest time sink
    if app_time:
        top_app = max(app_time.items(), key=lambda x: x[1])
        insights.append({
            "label": "Top time consumer",
            "value": top_app[0],
            "style": "",
        })

    # Communication time warning
    comm_time = sum(app_time.get(app, 0) for app in app_categories["Communication"])
    if comm_time > 60:
        insights.append({
            "label": "Communication overhead",
            "value": f"{comm_time/60:.1f}h",
            "style": "orange",
        })
    else:
        insights.append({
            "label": "Communication",
            "value": f"{comm_time:.0f}m",
            "style": "green",
        })

    # Context switch warning
    if context_switches > 20:
        insights.append({
            "label": "High switching",
            "value": f"{context_switches} times",
            "style": "orange",
        })
    else:
        insights.append({
            "label": "Focus maintained",
            "value": f"{context_switches} switches",
            "style": "green",
        })

    # Get recent activity with duration
    recent_activities = []
    recent = await db.fetch_all(
        """
        SELECT timestamp, app_name, window_title, url
        FROM activity_logs
        WHERE date(timestamp) = ?
        ORDER BY timestamp DESC
        LIMIT 10
        """,
        (today,)
    )

    for i, activity in enumerate(recent):
        ts = datetime.fromisoformat(activity["timestamp"])
        detail = activity["window_title"] or activity["url"] or ""

        # Calculate duration to next event
        if i < len(recent) - 1:
            next_ts = datetime.fromisoformat(recent[i + 1]["timestamp"])
            duration = (ts - next_ts).total_seconds() / 60
            duration = min(duration, 15)
            duration_str = f"{duration:.0f}m" if duration < 60 else f"{duration/60:.1f}h"
        else:
            duration_str = "-"

        recent_activities.append({
            "time": ts.strftime("%H:%M"),
            "app": activity["app_name"],
            "detail": detail[:60] + "..." if len(detail) > 60 else detail,
            "duration": duration_str,
        })

    # Get browser work by domain
    browser_work = []
    for domain, minutes in sorted(url_time.items(), key=lambda x: x[1], reverse=True)[:8]:
        cat, icon, color = categorize_url(f"https://{domain}")
        time_str = f"{minutes:.0f}m" if minutes < 60 else f"{minutes/60:.1f}h"
        browser_work.append({
            "domain": domain,
            "category": cat,
            "visits": url_visits.get(domain, 0),
            "time": time_str,
        })

    # Build project work list (deep work context)
    project_work = []
    for project, minutes in sorted(project_time.items(), key=lambda x: x[1], reverse=True)[:6]:
        time_str = f"{minutes:.0f}m" if minutes < 60 else f"{minutes/60:.1f}h"
        project_work.append({
            "name": project,
            "time": time_str,
            "minutes": minutes,
        })

    # Build meeting list
    meetings = []
    for meeting, minutes in sorted(meeting_time.items(), key=lambda x: x[1], reverse=True)[:5]:
        time_str = f"{minutes:.0f}m" if minutes < 60 else f"{minutes/60:.1f}h"
        meetings.append({
            "name": meeting,
            "time": time_str,
            "minutes": minutes,
        })

    # Build documents list
    documents = []
    for doc, minutes in sorted(document_time.items(), key=lambda x: x[1], reverse=True)[:6]:
        time_str = f"{minutes:.0f}m" if minutes < 60 else f"{minutes/60:.1f}h"
        documents.append({
            "name": doc[:40] + "..." if len(doc) > 40 else doc,
            "time": time_str,
            "minutes": minutes,
        })

    # Calculate engagement rate
    engagement_rate = 0
    if total_minutes > 0:
        # Keystrokes per minute baseline: 40 WPM = ~200 keystrokes/min for active typing
        # We're measuring across all time including reading, so expect lower
        kpm = total_keystrokes / total_minutes if total_minutes > 0 else 0
        engagement_rate = min(100, (kpm / 50) * 100)  # 50 KPM = 100% engagement

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "dashboard_apple.html",
        {
            "request": request,
            "today": datetime.now().strftime("%A, %B %d, %Y"),
            "total_hours": round(total_minutes / 60, 1),
            "focus_score": focus_score,
            "context_switches": context_switches,
            "deep_work_hours": round(deep_work_minutes / 60, 1),
            "work_categories": work_categories[:6],
            "insights": insights,
            "recent_activities": recent_activities,
            "browser_work": browser_work,
            # New work context data
            "project_work": project_work,
            "meetings": meetings,
            "documents": documents,
            "total_keystrokes": total_keystrokes,
            "total_clicks": total_clicks,
            "engagement_rate": round(engagement_rate),
        }
    )


@router.get("/classic", response_class=HTMLResponse)
async def classic_dashboard(request: Request) -> HTMLResponse:
    """Classic dashboard page (old multi-tab design)."""
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

    # Get screenshots for the date
    screenshots = await db.fetch_all(
        """
        SELECT id, timestamp, file_path, width, height
        FROM screenshots
        WHERE date(timestamp) = ? AND is_deleted = FALSE
        ORDER BY timestamp ASC
        """,
        (date,)
    )

    # Build list of screenshot timestamps for proximity matching
    screenshot_list = []
    for ss in screenshots:
        ts = datetime.fromisoformat(ss["timestamp"])
        screenshot_list.append({
            "timestamp": ts,
            "id": ss["id"],
            "url": f"/screenshots/files/{ss['file_path']}",
            "timestamp_str": ss["timestamp"],
            "width": ss["width"],
            "height": ss["height"],
        })

    # Attach nearest screenshot to each activity (within 60 seconds)
    max_delta_seconds = 60  # Match screenshots within 60 seconds of activity

    activities_with_screenshots = []
    for activity in activities:
        activity_dict = dict(activity)
        activity_ts = datetime.fromisoformat(activity_dict["timestamp"])

        # Find nearest screenshot within threshold
        best_match = None
        best_delta = float('inf')

        for ss in screenshot_list:
            delta = abs((activity_ts - ss["timestamp"]).total_seconds())
            if delta < best_delta and delta <= max_delta_seconds:
                best_delta = delta
                best_match = {
                    "id": ss["id"],
                    "url": ss["url"],
                    "timestamp": ss["timestamp_str"],
                    "width": ss["width"],
                    "height": ss["height"],
                }

        activity_dict["screenshot"] = best_match
        activities_with_screenshots.append(activity_dict)

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
            "activities": activities_with_screenshots,
            "available_dates": [d["date"] for d in dates],
            "screenshot_count": len(screenshots),
        }
    )


@router.get("/time-analysis", response_class=HTMLResponse)
async def time_analysis(
    request: Request,
    date: str | None = None,
) -> HTMLResponse:
    """Time analysis view - shows where time is spent."""
    from captains_log.web.app import get_db

    db = await get_db()

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Get all activity events for the day, ordered by time
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
            duration = (ts - prev_ts).total_seconds() / 60  # in minutes

            # Cap duration at 15 minutes (user likely away if gap is larger)
            duration = min(duration, 15)
            total_tracked_minutes += duration

            prev_app = prev_event["app_name"]
            app_time[prev_app] = app_time.get(prev_app, 0) + duration

            # Track context switches
            if app != prev_app:
                context_switches += 1
                # End current focus session
                if current_focus_start and current_focus_app:
                    focus_duration = (prev_ts - current_focus_start).total_seconds() / 60
                    if focus_duration >= 5:  # Only count focus sessions >= 5 min
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

    # Categorize apps for insights
    categories = {
        "Communication": ["Slack", "Messages", "Mail", "Microsoft Outlook", "Zoom", "Discord", "Microsoft Teams"],
        "Development": ["Terminal", "VS Code", "Xcode", "PyCharm", "IntelliJ", "Cursor", "Sublime Text", "iTerm2"],
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

    # Sort apps by time
    sorted_apps = sorted(app_time.items(), key=lambda x: x[1], reverse=True)

    # Calculate focus score (less switches = better)
    focus_score = max(0, min(100, 100 - (context_switches * 3))) if events else 0

    # Get available dates
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
        "time_analysis.html",
        {
            "request": request,
            "date": date,
            "app_time": sorted_apps[:15],  # Top 15 apps
            "category_time": sorted(category_time.items(), key=lambda x: x[1], reverse=True),
            "total_hours": round(total_tracked_minutes / 60, 1),
            "context_switches": context_switches,
            "focus_score": focus_score,
            "focus_sessions": sorted(focus_sessions, key=lambda x: x["duration"], reverse=True)[:10],
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
