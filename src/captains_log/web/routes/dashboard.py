"""Dashboard page routes."""

from __future__ import annotations

from datetime import datetime, timedelta
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


# Category mapping: app switches within same category don't break "deep work"
_APP_CATEGORY: dict[str, str] = {}
for _cat, _apps in {
    "Development": [
        "Terminal", "VS Code", "Xcode", "PyCharm", "IntelliJ", "Cursor",
        "iTerm2", "Code", "Sublime Text", "Warp", "Alacritty",
        "Screen Sharing",  # Remote dev via screen sharing
    ],
    "Communication": [
        "Slack", "Messages", "Mail", "Microsoft Outlook", "Zoom", "Discord",
        "Teams", "WhatsApp", "Telegram", "FaceTime",
        "Granola",  # Meeting notes
    ],
    "Browsing": [
        "Google Chrome", "Safari", "Firefox", "Arc", "Brave Browser", "Microsoft Edge",
    ],
    "Productivity": [
        "Notes", "Notion", "Obsidian", "Bear", "Things", "Reminders",
        "Calendar", "Preview", "Finder",
        "Wispr Flow",  # Dictation/productivity
    ],
    "System": [
        "loginwindow", "NetAuthAgent", "System Preferences", "System Settings",
        "UserNotificationCenter", "SecurityAgent", "CoreServicesUIAgent",
    ],
    "Media": [
        "Spotify", "Music", "YouTube", "Netflix", "Podcasts", "VLC", "QuickTime Player",
    ],
}.items():
    for _a in _apps:
        _APP_CATEGORY[_a] = _cat


def _get_cat(app_name: str) -> str:
    return _APP_CATEGORY.get(app_name, "Other")


def _process_events(events: list) -> dict:
    """Process activity events and return computed metrics.

    Tracks two levels of focus:
    - app-level: stretches of 25+ min on one app (intense focus)
    - category-level: stretches of 25+ min in one category (deep work)
      e.g. Terminal → VS Code → Terminal all counts as "Development" deep work.
    """
    total_minutes = 0.0
    app_deep_work = 0.0
    cat_deep_work = 0.0
    app_switches = 0
    cat_switches = 0
    hourly_minutes = [0.0] * 24
    app_time: dict[str, float] = {}

    # App-level stretch tracking
    app_stretch_start = None
    app_stretch_name = None
    longest_app_stretch = 0.0
    longest_app_stretch_name = ""

    # Category-level stretch tracking
    cat_stretch_start = None
    cat_stretch_name = None
    longest_cat_stretch = 0.0
    longest_cat_stretch_name = ""

    prev = None

    for event in events:
        ts = datetime.fromisoformat(event["timestamp"])
        app = event["app_name"]
        cat = _get_cat(app)

        if prev:
            prev_ts = datetime.fromisoformat(prev["timestamp"])
            dur = min((ts - prev_ts).total_seconds() / 60, 15)
            total_minutes += dur
            p_app = prev["app_name"]
            p_cat = _get_cat(p_app)
            app_time[p_app] = app_time.get(p_app, 0) + dur
            hourly_minutes[prev_ts.hour] += dur

            # App-level switches
            if app != p_app:
                app_switches += 1
                if app_stretch_start:
                    s = (prev_ts - app_stretch_start).total_seconds() / 60
                    if s > longest_app_stretch:
                        longest_app_stretch = s
                        longest_app_stretch_name = app_stretch_name or ""
                    if s >= 25:
                        app_deep_work += s
                app_stretch_start = ts
                app_stretch_name = app

            # Category-level switches (the one that matters for deep work)
            if cat != p_cat:
                cat_switches += 1
                if cat_stretch_start:
                    s = (prev_ts - cat_stretch_start).total_seconds() / 60
                    if s > longest_cat_stretch:
                        longest_cat_stretch = s
                        longest_cat_stretch_name = cat_stretch_name or ""
                    if s >= 25:
                        cat_deep_work += s
                cat_stretch_start = ts
                cat_stretch_name = cat
        else:
            app_stretch_start = ts
            app_stretch_name = app
            cat_stretch_start = ts
            cat_stretch_name = cat
        prev = event

    # Handle last stretches
    if prev:
        last_ts = datetime.fromisoformat(prev["timestamp"])
        if app_stretch_start:
            s = (last_ts - app_stretch_start).total_seconds() / 60
            if s > longest_app_stretch:
                longest_app_stretch = s
                longest_app_stretch_name = app_stretch_name or ""
            if s >= 25:
                app_deep_work += s
        if cat_stretch_start:
            s = (last_ts - cat_stretch_start).total_seconds() / 60
            if s > longest_cat_stretch:
                longest_cat_stretch = s
                longest_cat_stretch_name = cat_stretch_name or ""
            if s >= 25:
                cat_deep_work += s

    return {
        "total_minutes": total_minutes,
        "deep_work_minutes": cat_deep_work,         # category-based (primary)
        "intense_focus_minutes": app_deep_work,      # single-app (secondary)
        "context_switches": app_switches,            # all app switches
        "category_switches": cat_switches,           # only cross-category
        "longest_stretch": longest_cat_stretch,      # category-based
        "longest_stretch_name": longest_cat_stretch_name,
        "longest_app_stretch": longest_app_stretch,
        "longest_app_stretch_name": longest_app_stretch_name,
        "hourly_minutes": hourly_minutes,
        "app_time": app_time,
    }


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, date: str | None = None) -> HTMLResponse:
    """Productivity-focused dashboard."""
    from captains_log.web.app import get_db

    db = await get_db()

    # Determine date - default to today, fallback to latest with data
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    count = await db.fetch_one(
        "SELECT COUNT(*) as c FROM activity_logs WHERE date(timestamp) = ?", (date,)
    )
    if count["c"] == 0:
        latest = await db.fetch_one(
            "SELECT date(timestamp) as d FROM activity_logs ORDER BY timestamp DESC LIMIT 1"
        )
        if latest and latest["d"]:
            date = latest["d"]

    # Available dates for navigation
    dates_rows = await db.fetch_all(
        "SELECT DISTINCT date(timestamp) as date FROM activity_logs ORDER BY date DESC LIMIT 60"
    )
    available_dates = [d["date"] for d in dates_rows]

    idx = available_dates.index(date) if date in available_dates else -1
    prev_date = available_dates[idx + 1] if 0 <= idx < len(available_dates) - 1 else None
    next_date = available_dates[idx - 1] if idx > 0 else None

    # Get events for selected date
    events = await db.fetch_all(
        """SELECT timestamp, app_name, bundle_id, window_title, url, idle_status,
               work_category, work_project, work_document, work_meeting,
               keystrokes, mouse_clicks, scroll_events, engagement_score
        FROM activity_logs WHERE date(timestamp) = ? ORDER BY timestamp ASC""",
        (date,)
    )

    # Process metrics
    metrics = _process_events(events)

    # Engagement totals
    total_keystrokes = sum(e.get("keystrokes", 0) or 0 for e in events)
    total_clicks = sum(e.get("mouse_clicks", 0) or 0 for e in events)
    engagement_rate = min(100, (total_keystrokes / max(metrics["total_minutes"], 1) / 50) * 100)

    # Work categories (must match _APP_CATEGORY keys)
    cat_apps = {
        "Development": [
            "Terminal", "VS Code", "Xcode", "PyCharm", "IntelliJ", "Cursor", "iTerm2",
            "Code", "Screen Sharing", "Sublime Text", "Warp", "Alacritty",
        ],
        "Communication": [
            "Slack", "Messages", "Mail", "Microsoft Outlook", "Zoom", "Discord",
            "Teams", "WhatsApp", "Granola",
        ],
        "Browsing": ["Google Chrome", "Safari", "Firefox", "Arc", "Brave Browser", "Microsoft Edge"],
        "Productivity": [
            "Notes", "Notion", "Obsidian", "Bear", "Things", "Reminders",
            "Calendar", "Preview", "Finder", "Wispr Flow",
        ],
        "Media": ["Spotify", "Music", "YouTube", "Netflix", "Podcasts", "VLC", "QuickTime Player"],
    }

    total_cat_minutes = sum(metrics["app_time"].values()) or 1
    categories = []
    for cat_name, apps in cat_apps.items():
        cat_min = sum(metrics["app_time"].get(a, 0) for a in apps)
        if cat_min > 0:
            categories.append({
                "name": cat_name,
                "minutes": round(cat_min, 1),
                "percent": round((cat_min / total_cat_minutes) * 100, 1),
            })
    categories.sort(key=lambda x: x["minutes"], reverse=True)

    # Top apps
    top_apps = [
        {"name": n, "minutes": round(m, 1)}
        for n, m in sorted(metrics["app_time"].items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    # Weekly trend (7 days ending on selected date)
    end_dt = datetime.strptime(date, "%Y-%m-%d")
    weekly_events = await db.fetch_all(
        """SELECT date(timestamp) as day, timestamp, app_name
        FROM activity_logs
        WHERE date(timestamp) BETWEEN date(?, '-6 days') AND date(?)
        ORDER BY day ASC, timestamp ASC""",
        (date, date)
    )

    by_day: dict[str, list] = {}
    for ev in weekly_events:
        d = ev["day"]
        if d not in by_day:
            by_day[d] = []
        by_day[d].append(ev)

    weekly_trend = []
    for i in range(6, -1, -1):
        d = end_dt - timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        day_evts = by_day.get(ds, [])
        day_m = _process_events(day_evts) if day_evts else {"deep_work_minutes": 0, "total_minutes": 0}
        weekly_trend.append({
            "day": d.strftime("%a"),
            "deep_work": round(day_m["deep_work_minutes"] / 60, 1),
            "total": round(day_m["total_minutes"] / 60, 1),
        })

    # 30-day heatmap
    heatmap_rows = await db.fetch_all(
        """SELECT date(timestamp) as day, COUNT(*) as events
        FROM activity_logs
        WHERE date(timestamp) BETWEEN date(?, '-29 days') AND date(?)
        GROUP BY day ORDER BY day ASC""",
        (date, date)
    )
    max_events = max((r["events"] for r in heatmap_rows), default=1)
    heatmap_levels = {}
    for r in heatmap_rows:
        heatmap_levels[r["day"]] = min(4, int((r["events"] / max_events) * 4) + 1)

    heatmap_dates = []
    for i in range(29, -1, -1):
        d = (end_dt - timedelta(days=i)).strftime("%Y-%m-%d")
        heatmap_dates.append({"date": d, "level": heatmap_levels.get(d, 0)})

    # AI insight from summaries
    summaries = await db.fetch_all(
        """SELECT context, focus_score, activity_type
        FROM summaries WHERE date(period_start) = ? ORDER BY period_start DESC LIMIT 5""",
        (date,)
    )

    # Previous day comparison
    prev_day_str = (end_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_day_evts = by_day.get(prev_day_str, [])
    prev_m = _process_events(prev_day_evts) if prev_day_evts else {"deep_work_minutes": 0, "total_minutes": 0}
    deep_work_change = round((metrics["deep_work_minutes"] - prev_m["deep_work_minutes"]) / 60, 1)

    # Recent activity
    recent = await db.fetch_all(
        """SELECT timestamp, app_name, window_title, url
        FROM activity_logs WHERE date(timestamp) = ? ORDER BY timestamp DESC LIMIT 12""",
        (date,)
    )

    recent_activities = []
    for i, act in enumerate(recent):
        ts = datetime.fromisoformat(act["timestamp"])
        detail = act["window_title"] or act["url"] or ""
        dur_str = ""
        if i < len(recent) - 1:
            next_ts = datetime.fromisoformat(recent[i + 1]["timestamp"])
            dur = min((ts - next_ts).total_seconds() / 60, 15)
            dur_str = f"{dur:.0f}m" if dur < 60 else f"{dur/60:.1f}h"
        recent_activities.append({
            "time": ts.strftime("%H:%M"),
            "app": act["app_name"],
            "detail": detail[:50] + "..." if len(detail) > 50 else detail,
            "duration": dur_str,
        })

    # Focus score — based on category switches per hour (not raw app switches)
    total_hours = metrics["total_minutes"] / 60
    if total_hours > 0 and events:
        cat_switches_per_hr = metrics["category_switches"] / total_hours
        # Smooth formula: 2/hr = 100, 10/hr = 60, 20/hr = 10, capped at 5 min
        focus_score = max(5, min(100, int(105 - cat_switches_per_hr * 5)))
    else:
        focus_score = 0

    # Streak — consecutive days with activity ending on selected date
    streak = 0
    expected = datetime.strptime(date, "%Y-%m-%d").date()
    for d_str in available_dates:
        d = datetime.strptime(d_str, "%Y-%m-%d").date()
        if d == expected:
            streak += 1
            expected -= timedelta(days=1)
        elif d < expected:
            break

    # Historical averages across all tracked days
    avg_row = await db.fetch_one(
        """SELECT COUNT(DISTINCT date(timestamp)) as days,
                  COUNT(*) as total_events
           FROM activity_logs"""
    )
    num_days = max(avg_row["days"], 1) if avg_row else 1

    avg_totals = await db.fetch_all(
        """SELECT date(timestamp) as day, COUNT(*) as events
           FROM activity_logs GROUP BY day"""
    )
    # Compute averages using per-day event counts as proxy for hours
    # Each event ≈ 2-3 min of tracked time on average
    day_hours = []
    for r in avg_totals:
        # Approximate: total_minutes for today = total_minutes, for others use event count * 2.5
        day_hours.append(r["events"] * 2.5 / 60)
    avg_total_hours = round(sum(day_hours) / len(day_hours), 1) if day_hours else 0
    avg_deep_work_hours = round(avg_total_hours * 0.4, 1)  # Rough estimate

    # Better AI insight — narrative style
    ai_insight = None
    total_hrs_display = round(total_hours, 1)

    if events:
        parts = []

        # Compare to average
        if total_hrs_display > avg_total_hours * 1.15:
            parts.append(f"An above-average day — {total_hrs_display}h tracked vs your {avg_total_hours}h daily average.")
        elif total_hrs_display < avg_total_hours * 0.85:
            parts.append(f"A lighter day — {total_hrs_display}h tracked vs your {avg_total_hours}h daily average.")
        else:
            parts.append(f"A typical day — {total_hrs_display}h tracked, close to your {avg_total_hours}h average.")

        # Top category
        if categories:
            top_cat = categories[0]
            cat_hrs = round(top_cat["minutes"] / 60, 1)
            parts.append(f"Most time in {top_cat['name']} ({cat_hrs}h).")

        # Deep work highlight
        dw_hrs = round(metrics["deep_work_minutes"] / 60, 1)
        if dw_hrs > 0:
            parts.append(f"Deep work: {dw_hrs}h of sustained focus.")

        # Longest stretch
        if metrics["longest_stretch"] > 0:
            sh = int(metrics["longest_stretch"] // 60)
            sm = int(metrics["longest_stretch"] % 60)
            s_str = f"{sh}h {sm}m" if sh > 0 else f"{sm}m"
            parts.append(f"Longest unbroken stretch: {s_str} in {metrics['longest_stretch_name']}.")

        # Peak hour
        if any(metrics["hourly_minutes"]):
            peak = metrics["hourly_minutes"].index(max(metrics["hourly_minutes"]))
            parts.append(f"Peak productivity around {peak}:00.")

        # AI summary data if available
        if summaries:
            avg_focus = sum(s.get("focus_score", 0) or 0 for s in summaries) / len(summaries)
            if avg_focus > 0:
                parts.append(f"AI focus score: {avg_focus:.0f}/100.")

        ai_insight = " ".join(parts)

    # --- Personal Chronotype (computed from ALL historical data) ---
    chrono_hourly = await db.fetch_all(
        """SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                  COUNT(*) as events, COUNT(DISTINCT date(timestamp)) as days
           FROM activity_logs GROUP BY hour ORDER BY hour"""
    )
    hour_avg = {}
    for r in chrono_hourly:
        hour_avg[r["hour"]] = round(r["events"] * 2.5 / 60 / max(r["days"], 1), 1)

    # Peak hours: top 3 work hours (6AM-11PM)
    work_hours = {h: v for h, v in hour_avg.items() if 6 <= h <= 22 and v > 0}
    peak_hours = sorted(work_hours, key=lambda h: work_hours[h], reverse=True)[:3]
    peak_hours.sort()

    # Valley hours: bottom 2 work hours (8AM-6PM with some activity)
    mid_hours = {h: v for h, v in hour_avg.items() if 8 <= h <= 17 and v > 0}
    valley_hours = sorted(mid_hours, key=lambda h: mid_hours[h])[:2]

    # Best day of week
    chrono_dow = await db.fetch_all(
        """SELECT CAST(strftime('%w', timestamp) AS INTEGER) as dow,
                  COUNT(*) as events, COUNT(DISTINCT date(timestamp)) as days
           FROM activity_logs GROUP BY dow ORDER BY dow"""
    )
    dow_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    dow_avg = {}
    for r in chrono_dow:
        dow_avg[r["dow"]] = round(r["events"] * 2.5 / 60 / max(r["days"], 1), 1)

    best_dow = max(dow_avg.items(), key=lambda x: x[1]) if dow_avg else (1, 0)

    chronotype = {
        "peak_hours": peak_hours,
        "peak_start": f"{peak_hours[0]}:00" if peak_hours else "10:00",
        "peak_end": f"{peak_hours[-1] + 1}:00" if peak_hours else "12:00",
        "valley_hours": valley_hours,
        "valley_str": f"{valley_hours[0]}:00-{valley_hours[-1]+1}:00" if valley_hours else "",
        "best_day": dow_names[best_dow[0]],
        "best_day_hours": best_dow[1],
        "avg_daily_capacity": avg_total_hours,
    }

    # --- Last Session (context recovery) ---
    last_session = await db.fetch_one(
        """SELECT timestamp, app_name, window_title, url
           FROM activity_logs WHERE date(timestamp) < ?
           ORDER BY timestamp DESC LIMIT 1""",
        (date,)
    )
    last_session_info = None
    if last_session:
        ls_ts = datetime.fromisoformat(last_session["timestamp"])
        ls_detail = last_session["window_title"] or last_session["url"] or ""
        last_session_info = {
            "date": ls_ts.strftime("%a, %b %d"),
            "time": ls_ts.strftime("%H:%M"),
            "app": last_session["app_name"],
            "detail": ls_detail[:55] + "..." if len(ls_detail) > 55 else ls_detail,
        }

    # --- Personal Bests ---
    best_day_row = await db.fetch_one(
        """SELECT date(timestamp) as day, COUNT(*) as events
           FROM activity_logs GROUP BY day ORDER BY events DESC LIMIT 1"""
    )
    best_day_date = best_day_row["day"] if best_day_row else None
    best_day_hours = round(best_day_row["events"] * 2.5 / 60, 1) if best_day_row else 0

    personal_bests = {
        "most_active_date": best_day_date,
        "most_active_hours": best_day_hours,
        "total_days": num_days,
        "total_hours_all_time": round(sum(day_hours), 0),
    }

    # Format date display
    date_display = datetime.strptime(date, "%Y-%m-%d").strftime("%A, %B %d, %Y")

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "dashboard_apple.html",
        {
            "request": request,
            "date": date,
            "date_display": date_display,
            "available_dates": available_dates,
            "prev_date": prev_date,
            "next_date": next_date,
            "deep_work_hours": round(metrics["deep_work_minutes"] / 60, 1),
            "deep_work_target": 4.0,
            "deep_work_percent": min(100, round((metrics["deep_work_minutes"] / 60 / 4.0) * 100)),
            "deep_work_change": deep_work_change,
            "total_hours": round(total_hours, 1),
            "focus_score": focus_score,
            "context_switches": metrics["context_switches"],
            "category_switches": metrics["category_switches"],
            "longest_stretch": round(metrics["longest_stretch"]),
            "longest_stretch_name": metrics["longest_stretch_name"],
            "hourly_focus": [round(m, 1) for m in metrics["hourly_minutes"]],
            "weekly_trend": weekly_trend,
            "categories": categories,
            "top_apps": top_apps,
            "heatmap_dates": heatmap_dates,
            "ai_insight": ai_insight,
            "recent_activities": recent_activities,
            "total_keystrokes": total_keystrokes,
            "total_clicks": total_clicks,
            "engagement_rate": round(engagement_rate),
            "streak": streak,
            "avg_total_hours": avg_total_hours,
            "avg_deep_work_hours": avg_deep_work_hours,
            "chronotype": chronotype,
            "last_session": last_session_info,
            "personal_bests": personal_bests,
        }
    )


@router.get("/weekly", response_class=HTMLResponse)
async def weekly_report(request: Request, date: str | None = None) -> HTMLResponse:
    """Weekly narrative productivity report."""
    from captains_log.web.app import get_db

    db = await get_db()

    # Determine which week to show (find Monday of the week containing `date`)
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    dt = datetime.strptime(date, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())  # Monday of that week
    sunday = monday + timedelta(days=6)

    week_start = monday.strftime("%Y-%m-%d")
    week_end = sunday.strftime("%Y-%m-%d")
    prev_week = (monday - timedelta(days=7)).strftime("%Y-%m-%d")
    next_week = (monday + timedelta(days=7)).strftime("%Y-%m-%d")

    # Get events for this week and previous week (for comparison)
    two_week_events = await db.fetch_all(
        """SELECT date(timestamp) as day, timestamp, app_name
        FROM activity_logs
        WHERE date(timestamp) BETWEEN date(?, '-7 days') AND date(?)
        ORDER BY day ASC, timestamp ASC""",
        (week_start, week_end)
    )

    by_day: dict[str, list] = {}
    for ev in two_week_events:
        d = ev["day"]
        if d not in by_day:
            by_day[d] = []
        by_day[d].append(ev)

    # Compute daily metrics for current week
    days = []
    week_total = 0.0
    week_deep = 0.0
    week_focus_scores = []
    week_switches = 0
    best_day = None
    worst_day = None
    best_stretch = 0.0
    best_stretch_cat = ""
    best_stretch_day = ""

    for i in range(7):
        d = monday + timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        day_evts = by_day.get(ds, [])

        if day_evts:
            m = _process_events(day_evts)
            th = round(m["total_minutes"] / 60, 1)
            dw = round(m["deep_work_minutes"] / 60, 1)
            cat_sw = m["category_switches"]
            total_h = m["total_minutes"] / 60
            fs = max(5, min(100, int(105 - (cat_sw / max(total_h, 0.1)) * 5))) if total_h > 0 else 0

            # Find top app
            top = max(m["app_time"].items(), key=lambda x: x[1])[0] if m["app_time"] else ""

            # Track best/worst
            if best_day is None or dw > best_day.get("deep_work_hours", 0):
                best_day = {"day_name": d.strftime("%A"), "deep_work_hours": dw, "total_hours": th}
            if worst_day is None or (th > 0 and fs < worst_day.get("focus_score", 999)):
                worst_day = {"day_name": d.strftime("%A"), "focus_score": fs, "reason": f"{cat_sw} category switches"}

            if m["longest_stretch"] > best_stretch:
                best_stretch = m["longest_stretch"]
                best_stretch_cat = m["longest_stretch_name"]
                best_stretch_day = d.strftime("%a")

            week_total += th
            week_deep += dw
            week_focus_scores.append(fs)
            week_switches += cat_sw
        else:
            th, dw, fs, cat_sw, top = 0, 0, 0, 0, ""

        days.append({
            "date": ds,
            "day_name": d.strftime("%a"),
            "total_hours": th,
            "deep_work_hours": dw,
            "focus_score": fs,
            "top_app": top,
            "category_switches": cat_sw,
        })

    # Previous week totals for comparison
    prev_monday = monday - timedelta(days=7)
    prev_total = 0.0
    prev_deep = 0.0
    for i in range(7):
        ds = (prev_monday + timedelta(days=i)).strftime("%Y-%m-%d")
        prev_evts = by_day.get(ds, [])
        if prev_evts:
            pm = _process_events(prev_evts)
            prev_total += pm["total_minutes"] / 60
            prev_deep += pm["deep_work_minutes"] / 60

    avg_focus = round(sum(week_focus_scores) / len(week_focus_scores)) if week_focus_scores else 0

    # Build narrative
    parts = []
    active_days = sum(1 for d in days if d["total_hours"] > 0)

    if week_total > prev_total * 1.1 and prev_total > 0:
        parts.append(f"A strong week — {round(week_total, 1)}h tracked across {active_days} days, up {round(week_total - prev_total, 1)}h from last week.")
    elif week_total < prev_total * 0.9 and prev_total > 0:
        parts.append(f"A lighter week — {round(week_total, 1)}h tracked across {active_days} days, down {round(prev_total - week_total, 1)}h from last week.")
    else:
        parts.append(f"A steady week — {round(week_total, 1)}h tracked across {active_days} days.")

    if best_day and best_day["deep_work_hours"] > 0:
        parts.append(f"{best_day['day_name']} was your best focus day with {best_day['deep_work_hours']}h of deep work.")

    if round(week_deep, 1) > 0:
        parts.append(f"You logged {round(week_deep, 1)}h of deep work total — sustained stretches of 25+ minutes in the same work category.")

    if best_stretch > 0:
        sh = int(best_stretch // 60)
        sm = int(best_stretch % 60)
        s_str = f"{sh}h {sm}m" if sh > 0 else f"{sm}m"
        parts.append(f"Your longest unbroken focus stretch was {s_str} in {best_stretch_cat} on {best_stretch_day}.")

    if worst_day and worst_day.get("focus_score", 100) < 30:
        parts.append(f"{worst_day['day_name']} was your most fragmented day ({worst_day['reason']}).")

    narrative = " ".join(parts)

    # Suggestion
    if week_switches > 0 and active_days > 0:
        avg_switches_per_day = week_switches / active_days
        if avg_switches_per_day > 30:
            suggestion = "Your category switching is high. Try time-blocking: dedicate 90-minute blocks to a single type of work before switching."
        elif avg_switches_per_day > 15:
            suggestion = "Consider batching communication — check Slack/email at set times (e.g., 9 AM, 12 PM, 4 PM) instead of reacting to each notification."
        else:
            suggestion = "Your focus discipline is solid. Try extending your best deep work sessions by 15 minutes to build even more momentum."
    else:
        suggestion = "Start tracking consistently to get personalized suggestions."

    week_display = f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d, %Y')}"

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "weekly.html",
        {
            "request": request,
            "week_start": week_start,
            "week_end": week_end,
            "week_display": week_display,
            "prev_week": prev_week,
            "next_week": next_week,
            "days": days,
            "week_total_hours": round(week_total, 1),
            "week_deep_work_hours": round(week_deep, 1),
            "week_avg_focus_score": avg_focus,
            "week_total_switches": week_switches,
            "prev_week_total_hours": round(prev_total, 1),
            "prev_week_deep_work_hours": round(prev_deep, 1),
            "best_day": best_day or {"day_name": "-", "deep_work_hours": 0},
            "worst_day": worst_day or {"day_name": "-", "reason": ""},
            "longest_stretch": {
                "minutes": round(best_stretch),
                "category": best_stretch_cat,
                "day": best_stretch_day,
            },
            "narrative": narrative,
            "suggestion": suggestion,
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
    # Filter parameters
    app: str | None = None,
    category: str | None = None,
    project: str | None = None,
    document: str | None = None,
    domain: str | None = None,
    meeting: str | None = None,
    status: str | None = None,
) -> HTMLResponse:
    """Activity timeline view."""
    from captains_log.web.app import get_db

    db = await get_db()

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Build dynamic query based on filters
    query = """
        SELECT timestamp, app_name, bundle_id, window_title, url, idle_status, is_fullscreen,
               work_category, work_project, work_document, work_meeting
        FROM activity_logs
        WHERE date(timestamp) = ?
    """
    params = [date]

    # Add filters dynamically
    if app:
        query += " AND LOWER(app_name) = LOWER(?)"
        params.append(app)

    if category:
        query += " AND LOWER(work_category) = LOWER(?)"
        params.append(category)

    if project:
        query += " AND LOWER(work_project) = LOWER(?)"
        params.append(project)

    if document:
        query += " AND LOWER(work_document) = LOWER(?)"
        params.append(document)

    if domain:
        query += " AND LOWER(url) LIKE LOWER(?)"
        params.append(f"%{domain}%")

    if meeting:
        query += " AND LOWER(work_meeting) = LOWER(?)"
        params.append(meeting)

    if status:
        query += " AND LOWER(idle_status) = LOWER(?)"
        params.append(status)

    query += " ORDER BY timestamp DESC"

    # Get all activity for the date (with filters applied)
    activities = await db.fetch_all(query, tuple(params))

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

    # Build active filters dict
    active_filters = {
        "app": app,
        "category": category,
        "project": project,
        "document": document,
        "domain": domain,
        "meeting": meeting,
        "status": status,
    }

    # Check if any filter is active
    is_filtered = any(active_filters.values())

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "timeline.html",
        {
            "request": request,
            "date": date,
            "activities": activities_with_screenshots,
            "available_dates": [d["date"] for d in dates],
            "screenshot_count": len(screenshots),
            "active_filters": active_filters,
            "is_filtered": is_filtered,
            "total_activities": len(activities),
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
