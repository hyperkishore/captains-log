"""Prompt templates for Claude AI summarization."""

from __future__ import annotations

# System prompt for activity summarization
SUMMARY_SYSTEM_PROMPT = """You are an AI assistant analyzing a user's computer activity to generate insights about their work patterns. Your goal is to understand what they were doing and provide helpful summaries.

IMPORTANT GUIDELINES:
1. Be concise and factual - describe what you observe
2. Focus on the "what" (activities) not the "why" (intentions)
3. Identify the primary type of work being done
4. Note context switches that may indicate distraction or multitasking
5. Assign a focus score based on how concentrated the work session appears
6. Extract relevant tags like project names, tools used, or task types

FOCUS SCORE GUIDELINES:
- 10: Single-task deep work, no switches, sustained engagement
- 8-9: Primarily focused with minimal, relevant switches
- 6-7: Moderate focus with some context switching
- 4-5: Fragmented attention, frequent switches between unrelated apps
- 1-3: Highly distracted, rapid switching, no clear focus

ACTIVITY TYPE DEFINITIONS:
- coding: Writing or reviewing code, using IDEs/editors
- writing: Creating documents, emails, notes
- communication: Slack, Discord, email reading/responding, messaging
- browsing: General web browsing, research, reading articles
- meetings: Video calls, calendar events, meeting tools
- design: Using design tools like Figma, Sketch
- admin: System settings, file management, organization tasks
- entertainment: Social media, videos, games, non-work content
- learning: Tutorials, documentation, educational content
- breaks: Away from computer or idle

Always respond with valid JSON matching the requested schema."""


# 5-minute summary prompt (with optional screenshot)
FIVE_MINUTE_SUMMARY_PROMPT = """Analyze this 5-minute activity session and provide a structured summary.

ACTIVITY DATA (events captured during this period):
{activity_json}

STATISTICS:
- Period: {period_start} to {period_end}
- Total events: {event_count}
- Unique apps: {unique_apps}
- Context switches: {context_switches}
- Pre-calculated focus hint: {focus_hint}/10

{screenshot_instruction}

Respond with a JSON object containing:
{{
  "primary_app": "string - most used app",
  "activity_type": "string - one of: coding, writing, communication, browsing, meetings, design, admin, entertainment, learning, breaks, unknown",
  "focus_score": number 1-10,
  "key_activities": ["up to 5 bullet points describing what was done"],
  "context": "2-3 sentence description",
  "context_switches": number,
  "tags": ["relevant tags"],
  "project_detected": "string or null",
  "meeting_detected": "string or null"
}}"""

SCREENSHOT_INSTRUCTION_WITH_IMAGE = """A screenshot from this period is attached. Use it to:
1. Confirm or refine the activity type
2. Identify specific content being worked on (code, documents, etc.)
3. Extract project names, document titles, or meeting names visible
4. Better understand the context of the work session"""

SCREENSHOT_INSTRUCTION_WITHOUT_IMAGE = """No screenshot available for this period. Base your analysis solely on the activity data."""


# Daily summary prompt
DAILY_SUMMARY_PROMPT = """Analyze the 5-minute summaries from this day and generate a daily summary.

DATE: {date}

5-MINUTE SUMMARIES ({summary_count} periods):
{summaries_json}

AGGREGATE STATISTICS:
- Total tracked time: {total_minutes} minutes
- Idle time: {idle_minutes} minutes
- Most used apps: {top_apps}
- Average focus score: {avg_focus:.1f}
- Total context switches: {total_switches}

Generate a comprehensive daily summary as JSON:
{{
  "total_active_minutes": number,
  "total_idle_minutes": number,
  "app_usage": {{"app_name": minutes}},
  "focus_periods": [{{"start": "HH:MM", "end": "HH:MM", "score": number, "activity": "string"}}],
  "peak_hour": number 0-23,
  "context_switches_total": number,
  "daily_narrative": "2-4 sentence narrative of the day",
  "accomplishments": ["key things accomplished"],
  "patterns": ["observed patterns - both positive and areas for improvement"],
  "improvement_suggestions": ["specific, actionable suggestions"]
}}"""


# Weekly summary prompt
WEEKLY_SUMMARY_PROMPT = """Analyze the daily summaries from this week and generate a weekly summary.

WEEK: {week_start} to {week_end}

DAILY SUMMARIES:
{daily_summaries_json}

WEEKLY STATISTICS:
- Total active hours: {total_hours:.1f}
- Average daily hours: {avg_daily_hours:.1f}
- Most productive day: {best_day}
- Least productive day: {worst_day}
- Average focus score: {avg_focus:.1f}

Generate a comprehensive weekly summary as JSON:
{{
  "total_active_hours": number,
  "daily_average_hours": number,
  "most_productive_day": "day name",
  "app_usage_trend": {{"app_name": percentage_change}},
  "focus_trend": {{"Monday": score, "Tuesday": score, ...}},
  "weekly_narrative": "3-5 sentence narrative",
  "key_accomplishments": ["major accomplishments"],
  "improvement_areas": ["areas that need improvement"],
  "recommendations": ["specific recommendations for next week"]
}}"""


# Fallback local summary template (when API unavailable)
FALLBACK_SUMMARY_TEMPLATE = """{
  "primary_app": "{primary_app}",
  "activity_type": "{activity_type}",
  "focus_score": {focus_score},
  "key_activities": ["Used {primary_app} primarily"],
  "context": "Activity session with {event_count} events across {unique_apps} apps. Focus score based on {context_switches} context switches.",
  "context_switches": {context_switches},
  "tags": [],
  "project_detected": null,
  "meeting_detected": null
}"""


def format_five_minute_prompt(
    activity_data: list[dict],
    period_start: str,
    period_end: str,
    context_switches: int,
    focus_hint: int,
    has_screenshot: bool = False,
) -> str:
    """Format the 5-minute summary prompt with activity data."""
    import json

    # Calculate stats
    apps = [a.get("app_name", "Unknown") for a in activity_data]
    unique_apps = len(set(apps))

    # Format activity JSON (limit to essential fields)
    simplified_data = []
    for event in activity_data:
        simplified_data.append({
            "timestamp": event.get("timestamp", ""),
            "app": event.get("app_name", ""),
            "title": event.get("window_title", "")[:100] if event.get("window_title") else None,
            "url": event.get("url", "")[:200] if event.get("url") else None,
            "idle_status": event.get("idle_status", "ACTIVE"),
            "work_category": event.get("work_category"),
            "work_project": event.get("work_project"),
        })

    screenshot_instruction = (
        SCREENSHOT_INSTRUCTION_WITH_IMAGE
        if has_screenshot
        else SCREENSHOT_INSTRUCTION_WITHOUT_IMAGE
    )

    return FIVE_MINUTE_SUMMARY_PROMPT.format(
        activity_json=json.dumps(simplified_data, indent=2),
        period_start=period_start,
        period_end=period_end,
        event_count=len(activity_data),
        unique_apps=unique_apps,
        context_switches=context_switches,
        focus_hint=focus_hint,
        screenshot_instruction=screenshot_instruction,
    )


def format_daily_prompt(
    date: str,
    summaries: list[dict],
    total_minutes: int,
    idle_minutes: int,
    total_switches: int,
) -> str:
    """Format the daily summary prompt with 5-minute summaries."""
    import json
    from collections import Counter

    # Calculate stats
    apps = []
    focus_scores = []
    for s in summaries:
        if s.get("primary_app"):
            apps.append(s["primary_app"])
        if s.get("focus_score"):
            focus_scores.append(s["focus_score"])

    top_apps = ", ".join([f"{app} ({count})" for app, count in Counter(apps).most_common(5)])
    avg_focus = sum(focus_scores) / len(focus_scores) if focus_scores else 5.0

    return DAILY_SUMMARY_PROMPT.format(
        date=date,
        summary_count=len(summaries),
        summaries_json=json.dumps(summaries, indent=2),
        total_minutes=total_minutes,
        idle_minutes=idle_minutes,
        top_apps=top_apps,
        avg_focus=avg_focus,
        total_switches=total_switches,
    )
