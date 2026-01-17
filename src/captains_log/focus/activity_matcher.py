"""Activity matcher for determining if current activity matches focus goal criteria."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MatchCriteria:
    """Criteria for matching activities to a focus goal.

    All specified criteria use OR logic - matching any criterion counts.
    Use exclude_* for blacklist patterns that override matches.
    """
    # Whitelist (match any)
    apps: list[str] | None = None          # App names (case-insensitive substring)
    bundle_ids: list[str] | None = None    # Bundle ID patterns
    projects: list[str] | None = None      # Work project names
    categories: list[str] | None = None    # Work categories (Development, Writing, etc.)
    url_patterns: list[str] | None = None  # URL regex patterns
    title_patterns: list[str] | None = None  # Window title regex patterns

    # Blacklist (exclude if matched)
    exclude_apps: list[str] | None = None
    exclude_bundle_ids: list[str] | None = None
    exclude_url_patterns: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MatchCriteria:
        """Create from dictionary (e.g., from JSON)."""
        return cls(
            apps=data.get("apps"),
            bundle_ids=data.get("bundle_ids"),
            projects=data.get("projects"),
            categories=data.get("categories"),
            url_patterns=data.get("url_patterns"),
            title_patterns=data.get("title_patterns"),
            exclude_apps=data.get("exclude_apps"),
            exclude_bundle_ids=data.get("exclude_bundle_ids"),
            exclude_url_patterns=data.get("exclude_url_patterns"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        result = {}
        for field in ["apps", "bundle_ids", "projects", "categories",
                      "url_patterns", "title_patterns",
                      "exclude_apps", "exclude_bundle_ids", "exclude_url_patterns"]:
            value = getattr(self, field)
            if value:
                result[field] = value
        return result


class ActivityMatcher:
    """Match current activity against focus goal criteria.

    Usage:
        matcher = ActivityMatcher()

        criteria = MatchCriteria(
            apps=["VS Code", "Terminal"],
            projects=["captains-log"],
            exclude_apps=["Slack"]
        )

        activity = {
            "app_name": "Visual Studio Code",
            "bundle_id": "com.microsoft.VSCode",
            "work_project": "captains-log",
            "url": None,
            "window_title": "pomodoro.py - captains-log"
        }

        result = matcher.matches(criteria, activity)
        # result.matches == True
        # result.reason == "App matches: VS Code"
    """

    @dataclass
    class MatchResult:
        """Result of a match check."""
        matches: bool
        reason: str
        match_type: str | None = None  # "app", "project", "category", etc.

    def matches(self, criteria: MatchCriteria, activity: dict[str, Any]) -> MatchResult:
        """Check if an activity matches the given criteria.

        Args:
            criteria: The matching criteria
            activity: Activity dict with keys like app_name, bundle_id, work_project, etc.

        Returns:
            MatchResult with match status and reason
        """
        app_name = activity.get("app_name", "")
        bundle_id = activity.get("bundle_id", "")
        work_project = activity.get("work_project", "")
        work_category = activity.get("work_category", "")
        url = activity.get("url", "")
        window_title = activity.get("window_title", "")

        # Check exclusions first (blacklist takes priority)
        if criteria.exclude_apps:
            for excluded in criteria.exclude_apps:
                if excluded.lower() in app_name.lower():
                    return self.MatchResult(
                        matches=False,
                        reason=f"Excluded app: {excluded}",
                        match_type="exclude_app"
                    )

        if criteria.exclude_bundle_ids:
            for excluded in criteria.exclude_bundle_ids:
                if excluded.lower() in bundle_id.lower():
                    return self.MatchResult(
                        matches=False,
                        reason=f"Excluded bundle: {excluded}",
                        match_type="exclude_bundle"
                    )

        if criteria.exclude_url_patterns and url:
            for pattern in criteria.exclude_url_patterns:
                try:
                    if re.search(pattern, url, re.IGNORECASE):
                        return self.MatchResult(
                            matches=False,
                            reason=f"Excluded URL pattern: {pattern}",
                            match_type="exclude_url"
                        )
                except re.error:
                    logger.warning(f"Invalid exclude URL regex: {pattern}")

        # Check whitelist (any match is a positive)
        if criteria.apps:
            for target_app in criteria.apps:
                if target_app.lower() in app_name.lower():
                    return self.MatchResult(
                        matches=True,
                        reason=f"App matches: {target_app}",
                        match_type="app"
                    )

        if criteria.bundle_ids:
            for target_bundle in criteria.bundle_ids:
                if target_bundle.lower() in bundle_id.lower():
                    return self.MatchResult(
                        matches=True,
                        reason=f"Bundle matches: {target_bundle}",
                        match_type="bundle"
                    )

        if criteria.projects and work_project:
            for target_project in criteria.projects:
                if target_project.lower() in work_project.lower():
                    return self.MatchResult(
                        matches=True,
                        reason=f"Project matches: {target_project}",
                        match_type="project"
                    )

        if criteria.categories and work_category:
            for target_category in criteria.categories:
                if target_category.lower() == work_category.lower():
                    return self.MatchResult(
                        matches=True,
                        reason=f"Category matches: {target_category}",
                        match_type="category"
                    )

        if criteria.url_patterns and url:
            for pattern in criteria.url_patterns:
                try:
                    if re.search(pattern, url, re.IGNORECASE):
                        return self.MatchResult(
                            matches=True,
                            reason=f"URL matches: {pattern}",
                            match_type="url"
                        )
                except re.error:
                    logger.warning(f"Invalid URL regex: {pattern}")

        if criteria.title_patterns and window_title:
            for pattern in criteria.title_patterns:
                try:
                    if re.search(pattern, window_title, re.IGNORECASE):
                        return self.MatchResult(
                            matches=True,
                            reason=f"Title matches: {pattern}",
                            match_type="title"
                        )
                except re.error:
                    logger.warning(f"Invalid title regex: {pattern}")

        # No match found
        return self.MatchResult(
            matches=False,
            reason="No criteria matched",
            match_type=None
        )

    def get_match_summary(self, criteria: MatchCriteria) -> str:
        """Get a human-readable summary of what this criteria matches.

        Example: "VS Code, Terminal (captains-log project)"
        """
        parts = []

        if criteria.apps:
            parts.append(", ".join(criteria.apps))

        if criteria.projects:
            parts.append(f"({', '.join(criteria.projects)} project)")

        if criteria.categories:
            parts.append(f"[{', '.join(criteria.categories)}]")

        if criteria.exclude_apps:
            parts.append(f"excluding {', '.join(criteria.exclude_apps)}")

        return " ".join(parts) if parts else "All activities"


# Pre-defined criteria templates for common goals
GOAL_TEMPLATES = {
    "deep_work_development": MatchCriteria(
        apps=["VS Code", "Visual Studio Code", "Cursor", "Terminal", "iTerm", "Xcode"],
        categories=["Development", "Coding"],
        exclude_apps=["Slack", "Discord", "Messages", "Mail", "Twitter", "Safari", "Chrome"]
    ),
    "writing": MatchCriteria(
        apps=["Notion", "Obsidian", "Google Docs", "Word", "Bear", "Ulysses", "iA Writer"],
        categories=["Writing", "Documentation"],
        exclude_apps=["Slack", "Discord", "Messages", "Twitter"]
    ),
    "communication": MatchCriteria(
        apps=["Slack", "Discord", "Messages", "Mail", "Zoom", "Teams"],
        categories=["Communication"]
    ),
    "research": MatchCriteria(
        apps=["Safari", "Chrome", "Firefox", "Arc"],
        categories=["Research", "Learning"],
        exclude_url_patterns=[
            r"twitter\.com", r"x\.com", r"reddit\.com", r"youtube\.com",
            r"facebook\.com", r"instagram\.com", r"tiktok\.com"
        ]
    ),
    "no_distractions": MatchCriteria(
        exclude_apps=[
            "Twitter", "X", "Reddit", "YouTube", "Facebook", "Instagram",
            "TikTok", "Netflix", "Hulu", "Disney+", "Messages"
        ],
        exclude_url_patterns=[
            r"twitter\.com", r"x\.com", r"reddit\.com", r"youtube\.com",
            r"facebook\.com", r"instagram\.com", r"tiktok\.com",
            r"netflix\.com", r"hulu\.com", r"disneyplus\.com"
        ]
    ),
}
