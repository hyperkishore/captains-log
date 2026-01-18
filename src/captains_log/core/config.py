"""Configuration management with Pydantic and YAML support."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TrackingConfig(BaseModel):
    """Activity tracking configuration."""

    buffer_flush_seconds: int = Field(default=30, description="Flush buffer to DB interval")
    idle_threshold_seconds: int = Field(default=300, description="Seconds before marking idle")
    debounce_ms: int = Field(default=2000, description="Wait this long before recording app switch (filters swipes)")


class ScreenshotConfig(BaseModel):
    """Screenshot capture configuration."""

    enabled: bool = True
    interval_minutes: int = Field(default=5, ge=1, le=60)
    capture_on_app_change: bool = Field(default=True, description="Capture screenshot on app switch")
    quality: int = Field(default=80, ge=1, le=100, description="WebP quality")
    max_width: int = Field(default=1280, description="Downscale Retina to this width")
    retention_days: int = Field(default=7, ge=1)
    excluded_apps: list[str] = Field(
        default_factory=lambda: [
            "com.1password.1password",
            "com.agilebits.onepassword7",
            "com.apple.keychainaccess",
            "com.lastpass.lastpassmacdesktop",
            "com.bitwarden.desktop",
        ]
    )


class SummarizationConfig(BaseModel):
    """AI summarization configuration."""

    enabled: bool = True
    model: str = Field(default="claude-3-5-haiku-20241022")
    use_batch_api: bool = Field(default=True, description="Use batch API for 50% cost savings")
    batch_interval_hours: int = Field(default=6, description="Process queue every N hours")
    vision_enabled: bool = True
    max_tokens: int = Field(default=1024)


class AggregationConfig(BaseModel):
    """Summary aggregation configuration."""

    daily_time: str = Field(default="23:00", description="Time to generate daily summary")
    weekly_day: str = Field(default="sunday", description="Day to generate weekly summary")


class WebConfig(BaseModel):
    """Web dashboard configuration."""

    enabled: bool = True
    host: str = Field(default="127.0.0.1", description="Bind to localhost only")
    port: int = Field(default=8080, ge=1024, le=65535)


class SyncConfig(BaseModel):
    """Cloud sync configuration."""

    enabled: bool = False
    cloud_api_url: str = Field(
        default="https://generous-gentleness-production.up.railway.app",
        description="Cloud API URL for syncing"
    )
    sync_interval_minutes: int = Field(default=5, ge=1, le=60, description="Sync frequency")
    sync_activities: bool = Field(default=False, description="Sync raw activities (more data)")
    sync_stats: bool = Field(default=True, description="Sync daily aggregated stats")
    sync_summaries: bool = Field(default=True, description="Sync AI summaries")


class FocusConfig(BaseModel):
    """Focus mode and Pomodoro configuration."""

    enabled: bool = True
    work_minutes: int = Field(default=25, ge=1, le=120, description="Pomodoro work duration")
    short_break_minutes: int = Field(default=5, ge=1, le=30, description="Short break duration")
    long_break_minutes: int = Field(default=15, ge=5, le=60, description="Long break duration")
    pomodoros_until_long_break: int = Field(default=4, ge=2, le=10)
    auto_start_breaks: bool = Field(default=True, description="Auto-start breaks after work")
    auto_start_work: bool = Field(default=False, description="Auto-start work after breaks")
    tracking_mode: str = Field(
        default="passive",
        description="'passive' (always track) or 'strict' (only when timer running)"
    )
    show_widget: bool = Field(default=True, description="Show floating focus widget")
    widget_position: str = Field(default="top-right", description="Widget screen position")
    gentle_nudges: bool = Field(default=True, description="Show gentle off-goal indicators")
    default_goal_minutes: int = Field(default=120, ge=15, le=480, description="Default daily goal")


class OptimizationConfig(BaseModel):
    """Time optimization engine configuration."""

    enabled: bool = Field(default=True, description="Enable time optimization features")

    # Analysis settings
    interrupt_threshold_seconds: int = Field(
        default=30, ge=5, le=120,
        description="Max duration for 'quick check' classification"
    )
    deep_work_min_minutes: int = Field(
        default=25, ge=10, le=60,
        description="Minimum duration for deep work block"
    )

    # DEAL classification thresholds
    repetitive_task_min_occurrences: int = Field(
        default=5, ge=2, le=20,
        description="Min occurrences to flag as repetitive/automatable"
    )

    # Nudge settings
    enable_nudges: bool = Field(default=True, description="Enable real-time nudges")
    nudge_cooldown_minutes: int = Field(
        default=30, ge=10, le=120,
        description="Minimum time between nudges"
    )
    interrupt_nudge_threshold: int = Field(
        default=6, ge=2, le=20,
        description="Interrupts per hour to trigger nudge"
    )

    # Briefing settings
    morning_briefing_enabled: bool = Field(default=True, description="Enable morning briefing")
    morning_briefing_time: str = Field(
        default="09:00",
        description="Time for morning briefing (HH:MM)"
    )
    weekly_report_enabled: bool = Field(default=True, description="Enable weekly report")
    weekly_report_day: str = Field(
        default="monday",
        description="Day for weekly report (lowercase)"
    )

    # Goals
    target_savings_percent: int = Field(
        default=20, ge=5, le=50,
        description="Target time savings percentage"
    )
    ideal_deep_work_hours: float = Field(
        default=4.0, ge=1.0, le=8.0,
        description="Daily deep work goal in hours"
    )

    # Status file for menu bar integration
    write_status_file: bool = Field(
        default=True,
        description="Write optimization_status.json for menu bar"
    )


class Config(BaseSettings):
    """Main application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="CAPTAINS_LOG_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Paths
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / "Library/Application Support/CaptainsLog"
    )
    log_dir: Path = Field(default_factory=lambda: Path.home() / "Library/Logs/CaptainsLog")
    config_dir: Path = Field(default_factory=lambda: Path.home() / ".config/captains-log")

    # Log level
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    # API Keys (from environment or keychain)
    claude_api_key: str | None = Field(default=None, description="Claude API key")

    # Sub-configurations
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    screenshots: ScreenshotConfig = Field(default_factory=ScreenshotConfig)
    summarization: SummarizationConfig = Field(default_factory=SummarizationConfig)
    aggregation: AggregationConfig = Field(default_factory=AggregationConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    focus: FocusConfig = Field(default_factory=FocusConfig)
    optimization: OptimizationConfig = Field(default_factory=OptimizationConfig)

    @property
    def db_path(self) -> Path:
        """Path to SQLite database."""
        return self.data_dir / "captains_log.db"

    @property
    def device_id_file(self) -> Path:
        """Path to device ID file."""
        return self.data_dir / "device_id"

    @property
    def device_id(self) -> str:
        """Get or generate unique device ID."""
        import uuid
        device_file = self.device_id_file
        if device_file.exists():
            return device_file.read_text().strip()
        # Generate new UUID
        new_id = str(uuid.uuid4())
        self.data_dir.mkdir(parents=True, exist_ok=True)
        device_file.write_text(new_id)
        os.chmod(device_file, 0o600)
        return new_id

    @property
    def screenshots_dir(self) -> Path:
        """Path to screenshots directory."""
        return self.data_dir / "screenshots"

    @property
    def config_file(self) -> Path:
        """Path to YAML config file."""
        return self.config_dir / "config.yaml"

    def ensure_directories(self) -> None:
        """Create all required directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions on data directory
        os.chmod(self.data_dir, 0o700)

    @classmethod
    def load(cls, config_path: Path | None = None) -> Config:
        """Load configuration from YAML file, environment variables, and defaults.

        Priority (highest to lowest):
        1. Environment variables
        2. YAML config file
        3. Default values
        """
        config_path = config_path or Path.home() / ".config/captains-log/config.yaml"

        # Load YAML file if exists
        yaml_config: dict[str, Any] = {}
        if config_path.exists():
            with open(config_path) as f:
                yaml_config = yaml.safe_load(f) or {}

        # Create config with YAML as init data, env vars will override
        return cls(**yaml_config)

    def save(self, config_path: Path | None = None) -> None:
        """Save current configuration to YAML file."""
        config_path = config_path or self.config_file
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Exclude sensitive data and computed fields
        data = self.model_dump(
            exclude={"claude_api_key", "db_path", "screenshots_dir", "config_file"},
            exclude_none=True,
        )

        # Convert Path objects to strings for YAML
        for key in ["data_dir", "log_dir", "config_dir"]:
            if key in data:
                data[key] = str(data[key])

        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        # Set restrictive permissions on config file
        os.chmod(config_path, 0o600)


@lru_cache
def get_config() -> Config:
    """Get cached configuration instance."""
    return Config.load()
