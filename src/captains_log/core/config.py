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
    debounce_ms: int = Field(default=500, description="Ignore app focus shorter than this")


class ScreenshotConfig(BaseModel):
    """Screenshot capture configuration."""

    enabled: bool = True
    interval_minutes: int = Field(default=5, ge=1, le=60)
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
    model: str = Field(default="claude-haiku-4-5-20241022")
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
    provider: str = Field(default="s3", pattern="^(s3|r2)$")
    bucket: str = Field(default="")
    region: str = Field(default="us-west-2")
    endpoint: str | None = Field(default=None, description="Custom endpoint for R2")
    encrypt: bool = Field(default=True, description="Client-side encryption")


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

    @property
    def db_path(self) -> Path:
        """Path to SQLite database."""
        return self.data_dir / "captains_log.db"

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
