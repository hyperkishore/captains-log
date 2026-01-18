"""Context switch cost analysis.

Calculates the productivity cost of switching between different contexts,
considering the depth of focus and affinity between activities.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from captains_log.optimization.schemas import ContextSwitch, SwitchType

logger = logging.getLogger(__name__)


# Category mappings for apps
APP_CATEGORIES = {
    # Coding/Development
    "Code": "coding",
    "Visual Studio Code": "coding",
    "Xcode": "coding",
    "IntelliJ IDEA": "coding",
    "PyCharm": "coding",
    "WebStorm": "coding",
    "Sublime Text": "coding",
    "Cursor": "coding",
    "Terminal": "coding",
    "iTerm2": "coding",
    "Warp": "coding",
    "Ghostty": "coding",

    # Writing/Documentation
    "Notion": "writing",
    "Obsidian": "writing",
    "Bear": "writing",
    "Notes": "writing",
    "TextEdit": "writing",
    "Word": "writing",
    "Google Docs": "writing",
    "Pages": "writing",
    "Ulysses": "writing",
    "iA Writer": "writing",

    # Communication
    "Slack": "communication",
    "Discord": "communication",
    "Mail": "communication",
    "Microsoft Outlook": "communication",
    "Messages": "communication",
    "WhatsApp": "communication",
    "Telegram": "communication",
    "Microsoft Teams": "communication",

    # Meetings
    "Zoom": "meeting",
    "Google Meet": "meeting",
    "FaceTime": "meeting",
    "Skype": "meeting",
    "Around": "meeting",

    # Design
    "Figma": "design",
    "Sketch": "design",
    "Adobe XD": "design",
    "Photoshop": "design",
    "Illustrator": "design",
    "Canva": "design",

    # Research/Browsing
    "Safari": "browsing",
    "Google Chrome": "browsing",
    "Firefox": "browsing",
    "Arc": "browsing",
    "Brave": "browsing",
    "Edge": "browsing",

    # Admin/Productivity
    "Calendar": "admin",
    "Finder": "admin",
    "Preview": "admin",
    "Excel": "admin",
    "Numbers": "admin",
    "Sheets": "admin",
    "1Password": "admin",

    # Entertainment
    "Spotify": "entertainment",
    "Music": "entertainment",
    "YouTube": "entertainment",
    "Netflix": "entertainment",
    "Twitter": "entertainment",
    "Reddit": "entertainment",
}

# Category affinity matrix - how related categories are (0-1)
# Higher = more related = lower switch cost
CATEGORY_AFFINITY = {
    ("coding", "coding"): 1.0,
    ("coding", "writing"): 0.7,  # Related (docs)
    ("coding", "browsing"): 0.5,  # Stack Overflow lookup
    ("coding", "design"): 0.4,
    ("coding", "communication"): 0.2,
    ("coding", "meeting"): 0.1,
    ("coding", "admin"): 0.3,
    ("coding", "entertainment"): 0.0,

    ("writing", "writing"): 1.0,
    ("writing", "browsing"): 0.6,  # Research
    ("writing", "coding"): 0.5,
    ("writing", "communication"): 0.3,
    ("writing", "admin"): 0.4,

    ("communication", "communication"): 1.0,
    ("communication", "meeting"): 0.8,
    ("communication", "admin"): 0.5,

    ("meeting", "meeting"): 1.0,
    ("meeting", "communication"): 0.7,

    ("browsing", "browsing"): 1.0,
    ("browsing", "entertainment"): 0.6,

    ("design", "design"): 1.0,
    ("design", "coding"): 0.4,
    ("design", "browsing"): 0.5,

    ("admin", "admin"): 1.0,
    ("admin", "communication"): 0.5,

    ("entertainment", "entertainment"): 1.0,
}


@dataclass
class ContextSwitchMetrics:
    """Aggregated context switch metrics for a time period."""

    total_switches: int = 0
    estimated_total_cost_minutes: float = 0.0
    avg_cost_per_switch: float = 0.0

    # By type
    voluntary_switches: int = 0
    interrupt_switches: int = 0
    meeting_switches: int = 0

    # By category transition
    productive_to_communication: int = 0
    productive_to_entertainment: int = 0
    productive_to_productive: int = 0

    # Deep work impact
    deep_work_interrupted: int = 0  # Switches that broke 25+ min focus
    flow_state_broken: int = 0  # Switches that broke 45+ min focus

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_switches": self.total_switches,
            "estimated_total_cost_minutes": self.estimated_total_cost_minutes,
            "avg_cost_per_switch": self.avg_cost_per_switch,
            "voluntary_switches": self.voluntary_switches,
            "interrupt_switches": self.interrupt_switches,
            "meeting_switches": self.meeting_switches,
            "productive_to_communication": self.productive_to_communication,
            "productive_to_entertainment": self.productive_to_entertainment,
            "productive_to_productive": self.productive_to_productive,
            "deep_work_interrupted": self.deep_work_interrupted,
            "flow_state_broken": self.flow_state_broken,
        }


class ContextSwitchAnalyzer:
    """Analyzes context switches and calculates productivity costs."""

    # Base cost for switching between unrelated categories (minutes)
    BASE_SWITCH_COST = 2.0

    # Multipliers based on depth of focus
    DEPTH_MULTIPLIERS = {
        "shallow": 1.0,   # < 5 min in previous context
        "building": 1.5,  # 5-15 min (building focus)
        "focused": 2.0,   # 15-25 min (focused work)
        "deep": 2.5,      # 25-45 min (deep work)
        "flow": 3.0,      # 45+ min (flow state)
    }

    # Productive categories (for tracking productive interruptions)
    PRODUCTIVE_CATEGORIES = {"coding", "writing", "design"}

    def __init__(self, db: Any | None = None):
        """Initialize the context switch analyzer.

        Args:
            db: Database instance for persistence (optional)
        """
        self.db = db

        # Track recent activity
        self._recent_switches: deque[ContextSwitch] = deque(maxlen=100)

        # Current context tracking
        self._current_app: str | None = None
        self._current_category: str | None = None
        self._context_start: datetime | None = None
        self._engagement_samples: list[float] = []

    def get_category(self, app_name: str) -> str:
        """Get the category for an app.

        Args:
            app_name: Name of the application

        Returns:
            Category string
        """
        return APP_CATEGORIES.get(app_name, "other")

    def get_affinity(self, from_category: str, to_category: str) -> float:
        """Get the affinity between two categories.

        Args:
            from_category: Source category
            to_category: Destination category

        Returns:
            Affinity score (0-1)
        """
        # Check both directions (symmetric)
        key = (from_category, to_category)
        if key in CATEGORY_AFFINITY:
            return CATEGORY_AFFINITY[key]

        key = (to_category, from_category)
        if key in CATEGORY_AFFINITY:
            return CATEGORY_AFFINITY[key]

        # Same category = perfect affinity
        if from_category == to_category:
            return 1.0

        # Default low affinity for unrelated categories
        return 0.2

    def get_depth_level(self, duration_minutes: float) -> str:
        """Get the depth level based on time in context.

        Args:
            duration_minutes: Minutes in the previous context

        Returns:
            Depth level string
        """
        if duration_minutes < 5:
            return "shallow"
        elif duration_minutes < 15:
            return "building"
        elif duration_minutes < 25:
            return "focused"
        elif duration_minutes < 45:
            return "deep"
        else:
            return "flow"

    def calculate_switch_cost(
        self,
        from_category: str,
        to_category: str,
        duration_in_previous: float,
    ) -> float:
        """Calculate the cost of a context switch in minutes.

        Uses affinity between categories and depth of focus.

        Args:
            from_category: Category being switched from
            to_category: Category being switched to
            duration_in_previous: Minutes spent in previous context

        Returns:
            Estimated cost in minutes
        """
        # Get affinity (higher = lower cost)
        affinity = self.get_affinity(from_category, to_category)

        # Calculate base cost (inverse of affinity)
        # No cost for same/related categories
        base_cost = self.BASE_SWITCH_COST * (1 - affinity)

        # Get depth multiplier
        depth_level = self.get_depth_level(duration_in_previous)
        depth_multiplier = self.DEPTH_MULTIPLIERS[depth_level]

        return base_cost * depth_multiplier

    def on_app_change(
        self,
        timestamp: datetime,
        new_app: str,
        switch_type: SwitchType = SwitchType.VOLUNTARY,
    ) -> ContextSwitch | None:
        """Process an app change and calculate context switch cost.

        Args:
            timestamp: When the switch occurred
            new_app: The app being switched to
            switch_type: Type of switch (voluntary, interrupt, meeting)

        Returns:
            ContextSwitch if a switch was recorded, None otherwise
        """
        new_category = self.get_category(new_app)

        # First event - just initialize
        if self._current_app is None:
            self._current_app = new_app
            self._current_category = new_category
            self._context_start = timestamp
            return None

        # Same app - no switch
        if new_app == self._current_app:
            return None

        # Calculate duration in previous context
        duration_minutes = 0.0
        if self._context_start:
            duration = (timestamp - self._context_start).total_seconds()
            duration_minutes = duration / 60.0

        # Calculate switch cost
        cost = self.calculate_switch_cost(
            self._current_category or "other",
            new_category,
            duration_minutes,
        )

        # Create switch record
        switch = ContextSwitch(
            timestamp=timestamp,
            from_app=self._current_app or "",
            from_category=self._current_category or "",
            to_app=new_app,
            to_category=new_category,
            deep_work_duration_before=duration_minutes,
            estimated_cost_minutes=cost,
            switch_type=switch_type,
        )

        self._recent_switches.append(switch)

        # Update current context
        self._current_app = new_app
        self._current_category = new_category
        self._context_start = timestamp
        self._engagement_samples = []

        logger.debug(
            f"Context switch: {switch.from_app}({switch.from_category}) -> "
            f"{switch.to_app}({switch.to_category}), "
            f"duration: {duration_minutes:.1f}m, cost: {cost:.1f}m"
        )

        return switch

    async def save_switch(self, switch: ContextSwitch) -> int:
        """Save a context switch to the database.

        Args:
            switch: The context switch to save

        Returns:
            The ID of the saved record
        """
        if not self.db:
            logger.warning("No database configured for context switch analyzer")
            return 0

        return await self.db.insert("context_switches", switch.to_db_dict())

    async def get_daily_metrics(
        self, target_date: datetime | None = None
    ) -> ContextSwitchMetrics:
        """Get context switch metrics for a specific day.

        Args:
            target_date: The date to get metrics for (defaults to today)

        Returns:
            ContextSwitchMetrics for the day
        """
        if not self.db:
            return ContextSwitchMetrics()

        target_date = target_date or datetime.utcnow()
        date_str = target_date.strftime("%Y-%m-%d")

        rows = await self.db.fetch_all(
            """
            SELECT * FROM context_switches
            WHERE date(timestamp) = ?
            ORDER BY timestamp
            """,
            (date_str,),
        )

        metrics = ContextSwitchMetrics()

        for row in rows:
            metrics.total_switches += 1
            cost = row.get("estimated_cost_minutes", 0)
            metrics.estimated_total_cost_minutes += cost

            # By switch type
            switch_type = row.get("switch_type", "voluntary")
            if switch_type == "voluntary":
                metrics.voluntary_switches += 1
            elif switch_type == "interrupt":
                metrics.interrupt_switches += 1
            elif switch_type == "meeting":
                metrics.meeting_switches += 1

            # Category transitions
            from_cat = row.get("from_category", "")
            to_cat = row.get("to_category", "")

            if from_cat in self.PRODUCTIVE_CATEGORIES:
                if to_cat == "communication":
                    metrics.productive_to_communication += 1
                elif to_cat == "entertainment":
                    metrics.productive_to_entertainment += 1
                elif to_cat in self.PRODUCTIVE_CATEGORIES:
                    metrics.productive_to_productive += 1

            # Deep work impact
            duration = row.get("deep_work_duration_before", 0)
            if duration >= 25:
                metrics.deep_work_interrupted += 1
            if duration >= 45:
                metrics.flow_state_broken += 1

        # Calculate average
        if metrics.total_switches > 0:
            metrics.avg_cost_per_switch = (
                metrics.estimated_total_cost_minutes / metrics.total_switches
            )

        return metrics

    async def get_recent_switch_count(self, minutes: int = 60) -> int:
        """Get the number of context switches in the last N minutes.

        Args:
            minutes: Time window in minutes

        Returns:
            Number of switches
        """
        if not self.db:
            return 0

        cutoff = datetime.utcnow() - timedelta(minutes=minutes)

        result = await self.db.fetch_one(
            """
            SELECT COUNT(*) as count FROM context_switches
            WHERE timestamp > ?
            """,
            (cutoff.isoformat(),),
        )

        return result["count"] if result else 0

    def get_current_focus_duration(self) -> float:
        """Get the current duration in the current context in minutes.

        Returns:
            Duration in minutes
        """
        if not self._context_start:
            return 0.0

        duration = (datetime.utcnow() - self._context_start).total_seconds()
        return duration / 60.0

    def is_in_deep_work(self) -> bool:
        """Check if user is currently in deep work (25+ min focused).

        Returns:
            True if in deep work
        """
        duration = self.get_current_focus_duration()
        return (
            duration >= 25 and
            self._current_category in self.PRODUCTIVE_CATEGORIES
        )
