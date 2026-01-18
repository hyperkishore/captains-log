"""Pydantic schemas for time optimization engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class DEALCategory(str, Enum):
    """DEAL framework categories for activity classification."""

    DELEGATE = "delegate"  # Tasks someone else could do
    ELIMINATE = "eliminate"  # Low-value distractions
    AUTOMATE = "automate"  # Repetitive patterns
    LEVERAGE = "leverage"  # High-value work to double down on


class InterruptType(str, Enum):
    """Types of interrupts based on duration."""

    QUICK_CHECK = "quick_check"  # < 30 seconds
    SHORT_RESPONSE = "short_response"  # 30s - 2 min
    ACTIVE_COMMUNICATION = "active_communication"  # 2 - 15 min
    DEEP_COMMUNICATION = "deep_communication"  # > 15 min


class NudgeType(str, Enum):
    """Types of nudges for behavior change."""

    INTERRUPT_FREQUENCY = "interrupt_frequency"
    CONTEXT_SWITCH = "context_switch"
    MEETING_FRAGMENTATION = "meeting_fragmentation"
    DISTRACTION_ALERT = "distraction_alert"
    DEEP_WORK_OPPORTUNITY = "deep_work_opportunity"
    BREAK_SUGGESTION = "break_suggestion"
    GOAL_PROGRESS = "goal_progress"


class SwitchType(str, Enum):
    """Types of context switches."""

    VOLUNTARY = "voluntary"  # User-initiated switch
    INTERRUPT = "interrupt"  # External interruption
    MEETING = "meeting"  # Meeting start/end
    BREAK = "break"  # Break time


@dataclass
class UserProfile:
    """User profile for personalized optimization."""

    id: int | None = None
    role: str = ""  # Software Engineer, Manager, Designer, etc.
    department: str = ""  # Engineering, Product, Sales, etc.
    hourly_rate: float = 0.0  # For ROI calculations
    work_hours_per_week: int = 40
    time_savings_goal: float = 0.20  # 20%
    ideal_deep_work_hours: float = 4.0  # Daily goal
    preferred_work_start: str = "09:00"
    preferred_work_end: str = "18:00"
    focus_apps: list[str] = field(default_factory=list)  # Apps for deep work
    communication_apps: list[str] = field(default_factory=lambda: [
        "Slack", "Discord", "Mail", "Messages", "Teams", "Zoom"
    ])
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> UserProfile:
        """Create from database row."""
        import json
        return cls(
            id=row.get("id"),
            role=row.get("role", ""),
            department=row.get("department", ""),
            hourly_rate=row.get("hourly_rate", 0.0),
            work_hours_per_week=row.get("work_hours_per_week", 40),
            time_savings_goal=row.get("time_savings_goal", 0.20),
            ideal_deep_work_hours=row.get("ideal_deep_work_hours", 4.0),
            preferred_work_start=row.get("preferred_work_start", "09:00"),
            preferred_work_end=row.get("preferred_work_end", "18:00"),
            focus_apps=json.loads(row.get("focus_apps", "[]") or "[]"),
            communication_apps=json.loads(row.get("communication_apps", "[]") or "[]"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


@dataclass
class InterruptEvent:
    """Represents an interrupt (communication check)."""

    id: int | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    interrupt_app: str = ""  # e.g., "Slack", "Mail"
    duration_seconds: float = 0.0
    previous_app: str = ""  # What was being done before
    next_app: str = ""  # What happened after
    interrupt_type: InterruptType = InterruptType.QUICK_CHECK
    context_loss_estimate: float = 0.0  # Estimated minutes lost
    work_context_before: str = ""  # e.g., "coding", "writing"

    @classmethod
    def classify_interrupt(cls, duration_seconds: float) -> InterruptType:
        """Classify interrupt type based on duration."""
        if duration_seconds < 30:
            return InterruptType.QUICK_CHECK
        elif duration_seconds < 120:  # 2 min
            return InterruptType.SHORT_RESPONSE
        elif duration_seconds < 900:  # 15 min
            return InterruptType.ACTIVE_COMMUNICATION
        else:
            return InterruptType.DEEP_COMMUNICATION

    def to_db_dict(self) -> dict[str, Any]:
        """Convert to database dictionary."""
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "interrupt_app": self.interrupt_app,
            "duration_seconds": self.duration_seconds,
            "previous_app": self.previous_app,
            "next_app": self.next_app,
            "interrupt_type": self.interrupt_type.value,
            "context_loss_estimate": self.context_loss_estimate,
            "work_context_before": self.work_context_before,
        }


@dataclass
class ContextSwitch:
    """Represents a context switch between apps/tasks."""

    id: int | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    from_app: str = ""
    from_category: str = ""  # e.g., "coding", "communication"
    to_app: str = ""
    to_category: str = ""
    deep_work_duration_before: float = 0.0  # Minutes in focused work
    estimated_cost_minutes: float = 0.0
    actual_recovery_seconds: float | None = None  # Measured recovery time
    switch_type: SwitchType = SwitchType.VOLUNTARY

    # Cost multipliers based on context affinity
    AFFINITY_COSTS = {
        ("coding", "coding"): 0.5,
        ("writing", "writing"): 0.5,
        ("coding", "docs"): 1.0,
        ("coding", "communication"): 2.0,
        ("coding", "entertainment"): 3.0,
        ("deep_work", "communication"): 2.5,
        ("deep_work", "entertainment"): 4.0,
    }

    # Depth multipliers based on time in previous context
    DEPTH_MULTIPLIERS = {
        "shallow": 1.0,  # < 5 min
        "building": 2.0,  # 5-25 min
        "deep": 3.0,  # > 25 min
    }

    @classmethod
    def calculate_cost(
        cls,
        from_category: str,
        to_category: str,
        deep_work_duration_before: float,
    ) -> float:
        """Calculate estimated cost of a context switch in minutes."""
        # Get base cost from affinity matrix
        key = (from_category, to_category)
        base_cost = cls.AFFINITY_COSTS.get(key, 1.5)  # Default 1.5 min

        # Get depth multiplier
        if deep_work_duration_before < 5:
            multiplier = cls.DEPTH_MULTIPLIERS["shallow"]
        elif deep_work_duration_before < 25:
            multiplier = cls.DEPTH_MULTIPLIERS["building"]
        else:
            multiplier = cls.DEPTH_MULTIPLIERS["deep"]

        return base_cost * multiplier

    def to_db_dict(self) -> dict[str, Any]:
        """Convert to database dictionary."""
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "from_app": self.from_app,
            "from_category": self.from_category,
            "to_app": self.to_app,
            "to_category": self.to_category,
            "deep_work_duration_before": self.deep_work_duration_before,
            "estimated_cost_minutes": self.estimated_cost_minutes,
            "actual_recovery_seconds": self.actual_recovery_seconds,
            "switch_type": self.switch_type.value if self.switch_type else None,
        }


@dataclass
class DailyOptimizationMetrics:
    """Pre-aggregated daily optimization metrics."""

    id: int | None = None
    date: date = field(default_factory=date.today)

    # Time metrics (in minutes)
    total_tracked_minutes: float = 0.0
    deep_work_minutes: float = 0.0
    communication_minutes: float = 0.0
    meeting_minutes: float = 0.0
    admin_minutes: float = 0.0
    entertainment_minutes: float = 0.0

    # Interrupt metrics
    interrupt_count: int = 0
    quick_check_count: int = 0
    avg_interrupt_duration_seconds: float = 0.0
    estimated_interrupt_cost_minutes: float = 0.0

    # Context switch metrics
    context_switch_count: int = 0
    estimated_switch_cost_minutes: float = 0.0

    # Meeting fragmentation
    meeting_count: int = 0
    usable_blocks_count: int = 0  # Gaps >= 30 min
    fragmented_blocks_count: int = 0  # Gaps 5-30 min
    swiss_cheese_score: float = 0.0  # 0-1, higher = more fragmented

    # DEAL classification (minutes per category)
    delegate_minutes: float = 0.0
    eliminate_minutes: float = 0.0
    automate_minutes: float = 0.0
    leverage_minutes: float = 0.0

    # Savings potential
    potential_savings_minutes: float = 0.0
    savings_breakdown: dict[str, float] = field(default_factory=dict)

    def to_db_dict(self) -> dict[str, Any]:
        """Convert to database dictionary."""
        import json
        return {
            "date": self.date.isoformat() if self.date else None,
            "total_tracked_minutes": self.total_tracked_minutes,
            "deep_work_minutes": self.deep_work_minutes,
            "communication_minutes": self.communication_minutes,
            "meeting_minutes": self.meeting_minutes,
            "admin_minutes": self.admin_minutes,
            "entertainment_minutes": self.entertainment_minutes,
            "interrupt_count": self.interrupt_count,
            "quick_check_count": self.quick_check_count,
            "avg_interrupt_duration_seconds": self.avg_interrupt_duration_seconds,
            "estimated_interrupt_cost_minutes": self.estimated_interrupt_cost_minutes,
            "context_switch_count": self.context_switch_count,
            "estimated_switch_cost_minutes": self.estimated_switch_cost_minutes,
            "meeting_count": self.meeting_count,
            "usable_blocks_count": self.usable_blocks_count,
            "fragmented_blocks_count": self.fragmented_blocks_count,
            "swiss_cheese_score": self.swiss_cheese_score,
            "delegate_minutes": self.delegate_minutes,
            "eliminate_minutes": self.eliminate_minutes,
            "automate_minutes": self.automate_minutes,
            "leverage_minutes": self.leverage_minutes,
            "potential_savings_minutes": self.potential_savings_minutes,
            "savings_breakdown": json.dumps(self.savings_breakdown),
        }


@dataclass
class WeeklyOptimizationInsights:
    """AI-generated weekly optimization insights."""

    id: int | None = None
    week_start: date = field(default_factory=date.today)
    week_end: date = field(default_factory=date.today)

    # Aggregated metrics
    total_tracked_hours: float = 0.0
    deep_work_hours: float = 0.0
    time_saved_estimate: float = 0.0

    # AI analysis
    top_time_wasters: list[dict[str, Any]] = field(default_factory=list)
    automation_opportunities: list[dict[str, Any]] = field(default_factory=list)
    schedule_recommendations: list[dict[str, Any]] = field(default_factory=list)

    # Insights
    ai_narrative: str = ""
    key_insights: list[str] = field(default_factory=list)
    action_items: list[dict[str, Any]] = field(default_factory=list)

    # Comparison
    vs_previous_week: dict[str, Any] = field(default_factory=dict)

    model_used: str = ""


@dataclass
class Nudge:
    """Real-time nudge for behavior change."""

    id: int | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    nudge_type: NudgeType = NudgeType.INTERRUPT_FREQUENCY
    message: str = ""
    suggestion: str = ""
    urgency: str = "gentle"  # gentle, moderate, important
    was_dismissed: bool = False
    was_acted_upon: bool | None = None

    def to_db_dict(self) -> dict[str, Any]:
        """Convert to database dictionary."""
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "nudge_type": self.nudge_type.value,
            "nudge_content": f"{self.message}\n{self.suggestion}",
            "was_dismissed": self.was_dismissed,
            "was_acted_upon": self.was_acted_upon,
        }


@dataclass
class Recommendation:
    """Time optimization recommendation."""

    id: int | None = None
    category: str = ""  # "Batch Processing", "Meeting Consolidation", etc.
    title: str = ""
    current_behavior: str = ""
    suggested_behavior: str = ""
    estimated_savings_minutes: float = 0.0
    confidence: float = 0.0  # 0-1
    evidence: list[str] = field(default_factory=list)
    implementation_steps: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, accepted, dismissed
    created_at: datetime | None = None
    accepted_at: datetime | None = None
    dismissed_at: datetime | None = None

    def to_db_dict(self) -> dict[str, Any]:
        """Convert to database dictionary."""
        import json
        return {
            "category": self.category,
            "title": self.title,
            "current_behavior": self.current_behavior,
            "suggested_behavior": self.suggested_behavior,
            "estimated_savings_minutes": self.estimated_savings_minutes,
            "confidence": self.confidence,
            "evidence": json.dumps(self.evidence),
            "implementation_steps": json.dumps(self.implementation_steps),
            "status": self.status,
        }


@dataclass
class OptimizationStatus:
    """Status written to optimization_status.json for menu bar integration."""

    status_color: str = "green"  # green, amber, red
    daily_deep_work_hours: float = 0.0
    interrupt_count_today: int = 0
    context_switch_cost_minutes: float = 0.0
    latest_nudge: dict[str, Any] | None = None
    savings_progress: dict[str, float] = field(default_factory=lambda: {
        "goal_percent": 20,
        "actual_percent": 0.0,
    })

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status_color": self.status_color,
            "daily_deep_work_hours": self.daily_deep_work_hours,
            "interrupt_count_today": self.interrupt_count_today,
            "context_switch_cost_minutes": self.context_switch_cost_minutes,
            "latest_nudge": self.latest_nudge,
            "savings_progress": self.savings_progress,
        }
