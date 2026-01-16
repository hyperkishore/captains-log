"""SQLAlchemy models for cloud-synced activity data."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON, Index
from database import Base


class Device(Base):
    """Registered devices that sync data."""
    __tablename__ = "devices"

    id = Column(String(64), primary_key=True)  # UUID or hashed identifier
    name = Column(String(255), nullable=True)  # User-friendly name
    created_at = Column(DateTime, default=datetime.utcnow)
    last_sync = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_devices_last_sync", "last_sync"),
    )


class SyncedActivity(Base):
    """Activity logs synced from local devices."""
    __tablename__ = "synced_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)
    app_name = Column(String(255), nullable=False)
    bundle_id = Column(String(255), nullable=True)
    window_title = Column(Text, nullable=True)
    url = Column(Text, nullable=True)
    idle_seconds = Column(Float, nullable=True)
    idle_status = Column(String(50), nullable=True)
    work_category = Column(String(100), nullable=True)

    __table_args__ = (
        Index("idx_activity_device_timestamp", "device_id", "timestamp"),
    )


class SyncedSummary(Base):
    """AI summaries synced from local devices."""
    __tablename__ = "synced_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), nullable=False, index=True)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    primary_app = Column(String(255), nullable=True)
    activity_type = Column(String(100), nullable=True)
    focus_score = Column(Integer, nullable=True)
    key_activities = Column(JSON, nullable=True)
    context = Column(Text, nullable=True)
    context_switches = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_summary_device_period", "device_id", "period_start"),
    )


class DailyStats(Base):
    """Aggregated daily statistics for quick dashboard loading."""
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    total_events = Column(Integer, default=0)
    unique_apps = Column(Integer, default=0)
    top_apps = Column(JSON, nullable=True)  # [{app_name, count}, ...]
    hourly_breakdown = Column(JSON, nullable=True)  # [{hour, count}, ...]
    time_blocks = Column(JSON, nullable=True)  # Full time block data
    categories = Column(JSON, nullable=True)  # Category breakdown
    focus_data = Column(JSON, nullable=True)  # Focus scores over time
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_daily_device_date", "device_id", "date", unique=True),
    )
