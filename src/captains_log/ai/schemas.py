"""Pydantic schemas for AI responses."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ActivityType(str, Enum):
    """Types of activity detected by AI analysis."""

    CODING = "coding"
    WRITING = "writing"
    COMMUNICATION = "communication"
    BROWSING = "browsing"
    MEETINGS = "meetings"
    DESIGN = "design"
    ADMIN = "admin"
    ENTERTAINMENT = "entertainment"
    LEARNING = "learning"
    BREAKS = "breaks"
    UNKNOWN = "unknown"


class SummaryResponse(BaseModel):
    """Structured response from Claude for activity summary."""

    primary_app: str = Field(description="Most used application in this period")
    activity_type: ActivityType = Field(description="Type of activity being performed")
    focus_score: int = Field(
        ge=1, le=10, description="Focus score from 1-10 (10 = highly focused)"
    )
    key_activities: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Up to 5 key activities performed",
    )
    context: str = Field(description="2-3 sentence description of what was being done")
    context_switches: int = Field(
        ge=0, description="Number of app/context switches"
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Relevant tags like project name, task type",
    )

    # Optional fields for additional context
    project_detected: str | None = Field(
        default=None, description="Detected project name if identifiable"
    )
    meeting_detected: str | None = Field(
        default=None, description="Meeting name if in a meeting"
    )

    class Config:
        use_enum_values = True


class DailySummaryResponse(BaseModel):
    """Structured response for daily summary aggregation."""

    total_active_minutes: int = Field(description="Total active time in minutes")
    total_idle_minutes: int = Field(description="Total idle time in minutes")
    app_usage: dict[str, int] = Field(
        description="Minutes spent per application"
    )
    focus_periods: list[dict[str, Any]] = Field(
        description="High focus periods with start, end, score"
    )
    peak_hour: int = Field(ge=0, le=23, description="Most productive hour (0-23)")
    context_switches_total: int = Field(description="Total context switches")
    daily_narrative: str = Field(
        description="2-4 sentence narrative of the day"
    )
    accomplishments: list[str] = Field(
        default_factory=list, description="Key accomplishments"
    )
    patterns: list[str] = Field(
        default_factory=list, description="Observed patterns"
    )
    improvement_suggestions: list[str] = Field(
        default_factory=list, description="Suggestions for improvement"
    )


class WeeklySummaryResponse(BaseModel):
    """Structured response for weekly summary aggregation."""

    total_active_hours: float = Field(description="Total active hours for the week")
    daily_average_hours: float = Field(description="Average daily active hours")
    most_productive_day: str = Field(description="Day with highest productivity")
    app_usage_trend: dict[str, float] = Field(
        description="Weekly app usage trends (percentage change)"
    )
    focus_trend: dict[str, float] = Field(
        description="Daily focus scores across the week"
    )
    weekly_narrative: str = Field(
        description="3-5 sentence narrative of the week"
    )
    key_accomplishments: list[str] = Field(
        default_factory=list, description="Major accomplishments"
    )
    improvement_areas: list[str] = Field(
        default_factory=list, description="Areas for improvement"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Specific recommendations"
    )


class QueuedSummaryRequest(BaseModel):
    """Request stored in summary queue for batch processing."""

    period_start: str = Field(description="ISO format start time")
    period_end: str = Field(description="ISO format end time")
    screenshot_path: str | None = Field(description="Path to screenshot file")
    activity_data: list[dict[str, Any]] = Field(
        description="Activity events in this period"
    )
    focus_score_hint: int | None = Field(
        default=None, description="Pre-calculated focus score hint"
    )
