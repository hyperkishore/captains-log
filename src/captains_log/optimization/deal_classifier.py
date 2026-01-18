"""DEAL Framework Activity Classifier.

Classifies activities into four categories:
- Delegate: Tasks someone else could do
- Eliminate: Low-value distractions
- Automate: Repetitive patterns
- Leverage: High-value work to double down on
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from captains_log.optimization.schemas import DEALCategory

logger = logging.getLogger(__name__)


# Activity patterns for classification
LEVERAGE_PATTERNS = {
    # Deep work apps
    "apps": {
        "Code", "Visual Studio Code", "Xcode", "IntelliJ IDEA",
        "PyCharm", "WebStorm", "Sublime Text", "Cursor",
        "Figma", "Sketch", "Adobe XD", "Photoshop", "Illustrator",
        "Notion", "Obsidian", "Bear", "iA Writer", "Ulysses",
    },
    # Window title patterns suggesting deep work
    "title_patterns": [
        r"\.py$", r"\.js$", r"\.ts$", r"\.swift$", r"\.go$",  # Code files
        r"\.md$", r"\.txt$",  # Writing
        r"design|prototype|mockup|wireframe",  # Design work
        r"draft|writing|chapter|article",  # Long-form writing
    ],
    # Minimum duration to be considered "deep work"
    "min_duration_minutes": 10,
}

DELEGATE_PATTERNS = {
    # Admin tasks that could be delegated
    "apps": {
        "Calendar", "Calendly",
    },
    # Window title patterns
    "title_patterns": [
        r"schedule|scheduling|meeting request",
        r"invoice|expense|receipt",
        r"status update|standup|weekly update",
        r"data entry|spreadsheet",
        r"booking|reservation",
    ],
    # Activities that are clearly admin/overhead
    "activity_types": ["admin", "scheduling", "data_entry"],
}

ELIMINATE_PATTERNS = {
    # Distraction apps
    "apps": {
        "Twitter", "X", "Facebook", "Instagram", "TikTok",
        "Reddit", "Hacker News", "YouTube", "Netflix",
        "Spotify", "Music", "Apple Music",
        "News", "Apple News",
    },
    # Window title patterns suggesting distraction
    "title_patterns": [
        r"feed|timeline|trending",
        r"youtube\.com/(watch|shorts)",
        r"reddit\.com/r/",
        r"twitter\.com|x\.com",
        r"facebook\.com",
        r"instagram\.com",
        r"tiktok\.com",
        r"netflix\.com/browse",
    ],
    # URLs that are distracting
    "url_patterns": [
        r"youtube\.com/(watch|shorts)",
        r"reddit\.com",
        r"twitter\.com|x\.com",
        r"facebook\.com",
        r"instagram\.com",
        r"tiktok\.com",
        r"netflix\.com",
        r"hulu\.com",
        r"twitch\.tv",
    ],
}

AUTOMATE_PATTERNS = {
    # Communication apps with repetitive patterns
    "apps": {
        "Mail", "Microsoft Outlook", "Spark", "Airmail",
        "Slack", "Discord", "Microsoft Teams",
    },
    # Repetitive communication patterns
    "title_patterns": [
        r"inbox|unread",
        r"compose|reply|forward",
        r"#\w+-status|#\w+-updates",  # Slack status channels
    ],
    # Activities detected as repetitive
    "repetitive_threshold": 5,  # Times per day to flag as automatable
}


@dataclass
class ClassificationResult:
    """Result of classifying an activity."""

    category: DEALCategory
    confidence: float  # 0-1
    reasoning: str
    suggested_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "suggested_action": self.suggested_action,
        }


@dataclass
class ActivityPattern:
    """Detected pattern in user activities."""

    pattern_type: str  # "repetitive_app", "repetitive_url", "time_sink"
    description: str
    frequency: int  # Times per day/week
    total_time_minutes: float
    suggested_category: DEALCategory
    automation_suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "frequency": self.frequency,
            "total_time_minutes": self.total_time_minutes,
            "suggested_category": self.suggested_category.value,
            "automation_suggestion": self.automation_suggestion,
        }


@dataclass
class DEALMetrics:
    """Aggregated DEAL metrics for a time period."""

    # Time by category (minutes)
    leverage_minutes: float = 0.0
    delegate_minutes: float = 0.0
    eliminate_minutes: float = 0.0
    automate_minutes: float = 0.0
    unclassified_minutes: float = 0.0

    # Counts
    leverage_count: int = 0
    delegate_count: int = 0
    eliminate_count: int = 0
    automate_count: int = 0

    # Detected patterns
    detected_patterns: list[ActivityPattern] = field(default_factory=list)

    @property
    def total_minutes(self) -> float:
        """Total tracked time."""
        return (
            self.leverage_minutes + self.delegate_minutes +
            self.eliminate_minutes + self.automate_minutes +
            self.unclassified_minutes
        )

    @property
    def leverage_percent(self) -> float:
        """Percentage of time on high-value work."""
        if self.total_minutes == 0:
            return 0.0
        return (self.leverage_minutes / self.total_minutes) * 100

    @property
    def potential_savings_minutes(self) -> float:
        """Time that could potentially be saved (eliminate + automate)."""
        return self.eliminate_minutes + self.automate_minutes

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "leverage_minutes": self.leverage_minutes,
            "delegate_minutes": self.delegate_minutes,
            "eliminate_minutes": self.eliminate_minutes,
            "automate_minutes": self.automate_minutes,
            "unclassified_minutes": self.unclassified_minutes,
            "total_minutes": self.total_minutes,
            "leverage_percent": self.leverage_percent,
            "potential_savings_minutes": self.potential_savings_minutes,
            "leverage_count": self.leverage_count,
            "delegate_count": self.delegate_count,
            "eliminate_count": self.eliminate_count,
            "automate_count": self.automate_count,
            "detected_patterns": [p.to_dict() for p in self.detected_patterns],
        }


class DEALClassifier:
    """Classifies activities using the DEAL framework."""

    def __init__(self, db: Any | None = None):
        """Initialize the DEAL classifier.

        Args:
            db: Database instance for persistence
        """
        self.db = db

        # Cache for pattern detection
        self._app_frequency: dict[str, int] = {}
        self._url_frequency: dict[str, int] = {}

    def classify_activity(
        self,
        app_name: str,
        window_title: str | None = None,
        url: str | None = None,
        duration_seconds: float = 0,
        work_category: str | None = None,
    ) -> ClassificationResult:
        """Classify a single activity.

        Args:
            app_name: Name of the application
            window_title: Window title (optional)
            url: URL if browser (optional)
            duration_seconds: Duration of the activity
            work_category: Pre-classified category (optional)

        Returns:
            ClassificationResult with category and confidence
        """
        duration_minutes = duration_seconds / 60.0

        # Check for ELIMINATE first (distractions)
        if self._matches_eliminate(app_name, window_title, url):
            return ClassificationResult(
                category=DEALCategory.ELIMINATE,
                confidence=0.85,
                reasoning=f"'{app_name}' is typically a distraction app",
                suggested_action="Consider time-boxing or blocking during focus hours",
            )

        # Check for LEVERAGE (high-value deep work)
        if self._matches_leverage(app_name, window_title, duration_minutes):
            return ClassificationResult(
                category=DEALCategory.LEVERAGE,
                confidence=0.80,
                reasoning=f"'{app_name}' is used for focused, high-value work",
                suggested_action="Protect more time for this type of work",
            )

        # Check for DELEGATE (admin tasks)
        if self._matches_delegate(app_name, window_title):
            return ClassificationResult(
                category=DEALCategory.DELEGATE,
                confidence=0.70,
                reasoning="Activity appears to be administrative/schedulable task",
                suggested_action="Consider if this could be delegated or batched",
            )

        # Check for AUTOMATE (repetitive patterns)
        if self._matches_automate(app_name, window_title, url):
            return ClassificationResult(
                category=DEALCategory.AUTOMATE,
                confidence=0.65,
                reasoning="Activity is repetitive and could be automated",
                suggested_action="Look for automation opportunities or batching",
            )

        # Default: Unclassified (needs more context)
        return ClassificationResult(
            category=DEALCategory.LEVERAGE,  # Default to leverage
            confidence=0.30,
            reasoning="Activity could not be confidently classified",
            suggested_action=None,
        )

    def _matches_eliminate(
        self,
        app_name: str,
        window_title: str | None,
        url: str | None,
    ) -> bool:
        """Check if activity matches ELIMINATE patterns."""
        # Check app name
        if app_name in ELIMINATE_PATTERNS["apps"]:
            return True

        # Check window title
        if window_title:
            for pattern in ELIMINATE_PATTERNS["title_patterns"]:
                if re.search(pattern, window_title, re.IGNORECASE):
                    return True

        # Check URL
        if url:
            for pattern in ELIMINATE_PATTERNS["url_patterns"]:
                if re.search(pattern, url, re.IGNORECASE):
                    return True

        return False

    def _matches_leverage(
        self,
        app_name: str,
        window_title: str | None,
        duration_minutes: float,
    ) -> bool:
        """Check if activity matches LEVERAGE patterns."""
        # Check app name
        if app_name in LEVERAGE_PATTERNS["apps"]:
            # For deep work apps, require minimum duration
            min_duration = LEVERAGE_PATTERNS["min_duration_minutes"]
            if duration_minutes >= min_duration:
                return True
            # Still leverage even if short, just lower confidence
            return True

        # Check window title patterns
        if window_title:
            for pattern in LEVERAGE_PATTERNS["title_patterns"]:
                if re.search(pattern, window_title, re.IGNORECASE):
                    return True

        return False

    def _matches_delegate(
        self,
        app_name: str,
        window_title: str | None,
    ) -> bool:
        """Check if activity matches DELEGATE patterns."""
        # Check app name
        if app_name in DELEGATE_PATTERNS["apps"]:
            return True

        # Check window title
        if window_title:
            for pattern in DELEGATE_PATTERNS["title_patterns"]:
                if re.search(pattern, window_title, re.IGNORECASE):
                    return True

        return False

    def _matches_automate(
        self,
        app_name: str,
        window_title: str | None,
        url: str | None,
    ) -> bool:
        """Check if activity matches AUTOMATE patterns."""
        # Check app name (communication apps)
        if app_name in AUTOMATE_PATTERNS["apps"]:
            # Track frequency for pattern detection
            self._app_frequency[app_name] = self._app_frequency.get(app_name, 0) + 1

            # Check if used frequently (repetitive)
            threshold = AUTOMATE_PATTERNS["repetitive_threshold"]
            if self._app_frequency.get(app_name, 0) >= threshold:
                return True

        # Check window title
        if window_title:
            for pattern in AUTOMATE_PATTERNS["title_patterns"]:
                if re.search(pattern, window_title, re.IGNORECASE):
                    return True

        return False

    async def get_daily_metrics(
        self,
        target_date: datetime | None = None,
    ) -> DEALMetrics:
        """Get DEAL metrics for a specific day.

        Args:
            target_date: The date to analyze (defaults to today)

        Returns:
            DEALMetrics with category breakdowns
        """
        if not self.db:
            return DEALMetrics()

        target_date = target_date or datetime.utcnow()
        date_str = target_date.strftime("%Y-%m-%d")

        # Get all activities for the day
        rows = await self.db.fetch_all(
            """
            SELECT app_name, window_title, url,
                   MIN(timestamp) as start_time,
                   MAX(timestamp) as end_time,
                   COUNT(*) as event_count
            FROM activity_logs
            WHERE date(timestamp) = ?
            GROUP BY app_name, window_title
            ORDER BY start_time
            """,
            (date_str,),
        )

        metrics = DEALMetrics()
        app_totals: dict[str, float] = {}

        for row in rows:
            app_name = row.get("app_name", "Unknown")
            window_title = row.get("window_title")
            url = row.get("url")
            event_count = row.get("event_count", 1)

            # Estimate duration (rough estimate based on event frequency)
            # In reality, we should calculate from actual timestamps
            estimated_minutes = event_count * 0.5  # Assume 30 sec per event

            # Classify the activity
            result = self.classify_activity(
                app_name=app_name,
                window_title=window_title,
                url=url,
                duration_seconds=estimated_minutes * 60,
            )

            # Aggregate by category
            if result.category == DEALCategory.LEVERAGE:
                metrics.leverage_minutes += estimated_minutes
                metrics.leverage_count += 1
            elif result.category == DEALCategory.DELEGATE:
                metrics.delegate_minutes += estimated_minutes
                metrics.delegate_count += 1
            elif result.category == DEALCategory.ELIMINATE:
                metrics.eliminate_minutes += estimated_minutes
                metrics.eliminate_count += 1
            elif result.category == DEALCategory.AUTOMATE:
                metrics.automate_minutes += estimated_minutes
                metrics.automate_count += 1
            else:
                metrics.unclassified_minutes += estimated_minutes

            # Track app totals for pattern detection
            app_totals[app_name] = app_totals.get(app_name, 0) + estimated_minutes

        # Detect patterns
        metrics.detected_patterns = self._detect_patterns(app_totals, rows)

        return metrics

    def _detect_patterns(
        self,
        app_totals: dict[str, float],
        activity_rows: list[dict],
    ) -> list[ActivityPattern]:
        """Detect optimization patterns from activity data."""
        patterns = []

        # Pattern 1: Time sinks (apps with high total time)
        for app_name, total_minutes in app_totals.items():
            if total_minutes > 60:  # More than 1 hour
                if app_name in ELIMINATE_PATTERNS["apps"]:
                    patterns.append(ActivityPattern(
                        pattern_type="time_sink",
                        description=f"Spent {total_minutes:.0f} min on {app_name}",
                        frequency=1,
                        total_time_minutes=total_minutes,
                        suggested_category=DEALCategory.ELIMINATE,
                        automation_suggestion=f"Consider limiting {app_name} to 30 min/day",
                    ))

        # Pattern 2: Repetitive app usage (frequent short visits)
        app_visit_counts: dict[str, int] = {}
        for row in activity_rows:
            app_name = row.get("app_name", "Unknown")
            app_visit_counts[app_name] = app_visit_counts.get(app_name, 0) + 1

        for app_name, count in app_visit_counts.items():
            if count > 20 and app_name in AUTOMATE_PATTERNS["apps"]:
                patterns.append(ActivityPattern(
                    pattern_type="repetitive_app",
                    description=f"Checked {app_name} {count} times",
                    frequency=count,
                    total_time_minutes=app_totals.get(app_name, 0),
                    suggested_category=DEALCategory.AUTOMATE,
                    automation_suggestion=f"Batch {app_name} checks to 3x/day",
                ))

        return patterns

    async def save_classification(
        self,
        activity_log_id: int,
        classification: ClassificationResult,
    ) -> int:
        """Save a classification to the database.

        Args:
            activity_log_id: ID of the activity log entry
            classification: The classification result

        Returns:
            ID of the saved record
        """
        if not self.db:
            logger.warning("No database configured for DEAL classifier")
            return 0

        return await self.db.insert(
            "activity_classifications",
            {
                "activity_log_id": activity_log_id,
                "deal_category": classification.category.value,
                "confidence": classification.confidence,
                "reasoning": classification.reasoning,
                "classified_at": datetime.utcnow().isoformat(),
            },
        )

    def get_category_recommendations(
        self,
        category: DEALCategory,
    ) -> list[str]:
        """Get recommendations for a specific category.

        Args:
            category: The DEAL category

        Returns:
            List of actionable recommendations
        """
        recommendations = {
            DEALCategory.DELEGATE: [
                "Consider hiring a virtual assistant for scheduling",
                "Use Calendly or similar for meeting scheduling",
                "Batch administrative tasks to specific times",
                "Create templates for repetitive communications",
            ],
            DEALCategory.ELIMINATE: [
                "Use website blockers during focus time",
                "Set specific times for social media (e.g., lunch break)",
                "Remove distracting apps from your phone home screen",
                "Use 'Do Not Disturb' mode during deep work",
            ],
            DEALCategory.AUTOMATE: [
                "Set up email filters and rules",
                "Create Slack notification schedules",
                "Use text expansion for common phrases",
                "Set up automated reports where possible",
            ],
            DEALCategory.LEVERAGE: [
                "Protect your peak productivity hours for this work",
                "Batch meetings to create longer focus blocks",
                "Start your day with high-leverage work",
                "Say no to meetings during your best hours",
            ],
        }

        return recommendations.get(category, [])
