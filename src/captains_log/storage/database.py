"""SQLite database management with WAL mode and migrations."""

from __future__ import annotations

import asyncio
import logging
import shutil
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

# Schema version for migrations
SCHEMA_VERSION = 8

# Database schema
SCHEMA = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Core activity tracking (base schema - new columns added via migration)
CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    app_name TEXT NOT NULL,
    bundle_id TEXT,
    window_title TEXT,
    url TEXT,
    idle_seconds REAL,
    idle_status TEXT,
    is_fullscreen BOOLEAN DEFAULT FALSE,
    display_index INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_activity_app ON activity_logs(bundle_id);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_logs(created_at);

-- Screenshot metadata
CREATE TABLE IF NOT EXISTS screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    file_path TEXT NOT NULL,
    file_size_bytes INTEGER,
    width INTEGER,
    height INTEGER,
    expires_at DATETIME NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_screenshot_ts ON screenshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_screenshot_expires ON screenshots(expires_at);

-- 5-minute AI summaries
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start DATETIME NOT NULL,
    period_end DATETIME NOT NULL,
    screenshot_id INTEGER REFERENCES screenshots(id),
    primary_app TEXT,
    activity_type TEXT,
    focus_score INTEGER,
    key_activities JSON,
    context TEXT,
    context_switches INTEGER,
    tags JSON,
    model_used TEXT,
    tokens_input INTEGER,
    tokens_output INTEGER,
    batch_id TEXT,
    synced_to_cloud BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_summary_period ON summaries(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_summary_synced ON summaries(synced_to_cloud);

-- Daily aggregations
CREATE TABLE IF NOT EXISTS daily_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL UNIQUE,
    total_active_minutes INTEGER,
    total_idle_minutes INTEGER,
    app_usage JSON,
    focus_periods JSON,
    peak_hour INTEGER,
    context_switches_total INTEGER,
    daily_narrative TEXT,
    accomplishments JSON,
    patterns JSON,
    synced_to_cloud BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_summaries(date);

-- Weekly aggregations
CREATE TABLE IF NOT EXISTS weekly_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    total_active_hours REAL,
    daily_average_hours REAL,
    most_productive_day TEXT,
    app_usage_trend JSON,
    focus_trend JSON,
    weekly_narrative TEXT,
    key_accomplishments JSON,
    improvement_suggestions JSON,
    synced_to_cloud BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_weekly_range ON weekly_summaries(week_start, week_end);

-- Summary processing queue (for batch API)
CREATE TABLE IF NOT EXISTS summary_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start DATETIME NOT NULL,
    period_end DATETIME NOT NULL,
    screenshot_path TEXT,
    activity_data JSON,
    status TEXT DEFAULT 'pending',
    batch_id TEXT,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_queue_status ON summary_queue(status);

-- Configuration store
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Sync queue for cloud uploads
CREATE TABLE IF NOT EXISTS sync_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    operation TEXT NOT NULL,
    payload JSON,
    status TEXT DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_sync_status ON sync_queue(status);

-- System health metrics
CREATE TABLE IF NOT EXISTS system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    cpu_percent REAL,
    memory_mb REAL,
    db_size_mb REAL,
    screenshots_size_mb REAL,
    api_calls_count INTEGER,
    errors_count INTEGER
);

-- Error log
CREATE TABLE IF NOT EXISTS error_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    component TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    context JSON
);

CREATE INDEX IF NOT EXISTS idx_error_ts ON error_log(timestamp);

-- Focus goals for productivity tracking
CREATE TABLE IF NOT EXISTS focus_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    goal_type TEXT NOT NULL DEFAULT 'app_based',
    target_minutes INTEGER NOT NULL DEFAULT 120,
    estimated_sessions INTEGER DEFAULT 4,
    match_criteria JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_focus_goals_active ON focus_goals(is_active);

-- Focus sessions tracking progress toward goals
CREATE TABLE IF NOT EXISTS focus_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER REFERENCES focus_goals(id),
    date DATE NOT NULL,
    pomodoro_count INTEGER DEFAULT 0,
    total_focus_minutes REAL DEFAULT 0,
    total_break_minutes REAL DEFAULT 0,
    off_goal_minutes REAL DEFAULT 0,
    completed BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_focus_sessions_date ON focus_sessions(date);
CREATE INDEX IF NOT EXISTS idx_focus_sessions_goal ON focus_sessions(goal_id);

-- Pomodoro history for detailed tracking
CREATE TABLE IF NOT EXISTS pomodoro_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES focus_sessions(id),
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    duration_minutes REAL,
    was_completed BOOLEAN DEFAULT FALSE,
    interruption_count INTEGER DEFAULT 0,
    primary_app TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pomodoro_session ON pomodoro_history(session_id);
CREATE INDEX IF NOT EXISTS idx_pomodoro_started ON pomodoro_history(started_at);

-- Productivity goals (quarterly/half-year objectives)
CREATE TABLE IF NOT EXISTS productivity_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    estimated_hours REAL NOT NULL DEFAULT 40,
    deadline DATE,
    priority INTEGER DEFAULT 0,
    color TEXT DEFAULT '#3B82F6',
    is_active BOOLEAN DEFAULT TRUE,
    is_completed BOOLEAN DEFAULT FALSE,
    target_mode TEXT DEFAULT 'fixed',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_prod_goals_active ON productivity_goals(is_active);
CREATE INDEX IF NOT EXISTS idx_prod_goals_priority ON productivity_goals(priority);

-- Tasks within productivity goals (30-60 min chunks)
CREATE TABLE IF NOT EXISTS goal_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER REFERENCES productivity_goals(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    estimated_minutes INTEGER DEFAULT 30,
    parent_task_id INTEGER REFERENCES goal_tasks(id),
    sort_order INTEGER DEFAULT 0,
    is_completed BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_goal_tasks_goal ON goal_tasks(goal_id);
CREATE INDEX IF NOT EXISTS idx_goal_tasks_parent ON goal_tasks(parent_task_id);

-- Daily progress per productivity goal (for streak visualization)
CREATE TABLE IF NOT EXISTS goal_daily_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER REFERENCES productivity_goals(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    focus_minutes REAL DEFAULT 0,
    target_minutes REAL NOT NULL,
    status TEXT DEFAULT 'pending',
    sessions_completed INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(goal_id, date)
);

CREATE INDEX IF NOT EXISTS idx_goal_progress_date ON goal_daily_progress(date);
CREATE INDEX IF NOT EXISTS idx_goal_progress_goal ON goal_daily_progress(goal_id);

-- App settings
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    """SQLite database manager with WAL mode and connection pooling."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Initialize database connection with WAL mode."""
        if self._connection is not None:
            return

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(
            self.db_path,
            isolation_level=None,  # Autocommit mode, we handle transactions manually
        )

        # Enable WAL mode for better concurrent access
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA synchronous=NORMAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")
        await self._connection.execute("PRAGMA busy_timeout=5000")

        # Row factory for dict-like access
        self._connection.row_factory = aiosqlite.Row

        # Initialize schema
        await self._init_schema()

        logger.info(f"Database connected: {self.db_path}")

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        if self._connection is None:
            raise RuntimeError("Database not connected")

        # Execute schema
        await self._connection.executescript(SCHEMA)

        # Check/update schema version
        async with self._connection.execute(
            "SELECT MAX(version) FROM schema_version"
        ) as cursor:
            row = await cursor.fetchone()
            current_version = row[0] if row and row[0] else 0

        if current_version < SCHEMA_VERSION:
            # Run migrations
            await self._run_migrations(current_version)
            await self._connection.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            logger.info(f"Schema updated to version {SCHEMA_VERSION}")

    async def _run_migrations(self, from_version: int) -> None:
        """Run database migrations."""
        if self._connection is None:
            return

        # Migration from version 1 to 2: Add work context and input stats columns
        if from_version < 2:
            logger.info("Running migration v1 -> v2: Adding work context and input stats columns")

            # Get existing columns
            async with self._connection.execute("PRAGMA table_info(activity_logs)") as cursor:
                existing_cols = {row[1] for row in await cursor.fetchall()}

            # Add new columns if they don't exist
            new_columns = [
                ("work_category", "TEXT"),
                ("work_service", "TEXT"),
                ("work_project", "TEXT"),
                ("work_document", "TEXT"),
                ("work_meeting", "TEXT"),
                ("work_channel", "TEXT"),
                ("work_issue_id", "TEXT"),
                ("work_organization", "TEXT"),
                ("keystrokes", "INTEGER DEFAULT 0"),
                ("mouse_clicks", "INTEGER DEFAULT 0"),
                ("scroll_events", "INTEGER DEFAULT 0"),
                ("engagement_score", "REAL DEFAULT 0"),
            ]

            for col_name, col_type in new_columns:
                if col_name not in existing_cols:
                    try:
                        await self._connection.execute(
                            f"ALTER TABLE activity_logs ADD COLUMN {col_name} {col_type}"
                        )
                        logger.debug(f"Added column {col_name}")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" not in str(e).lower():
                            raise

            # Create indexes for new columns (ignore errors if they already exist)
            new_indexes = [
                ("idx_activity_work_category", "work_category"),
                ("idx_activity_work_project", "work_project"),
                ("idx_activity_work_org", "work_organization"),
            ]
            for idx_name, col_name in new_indexes:
                try:
                    await self._connection.execute(
                        f"CREATE INDEX IF NOT EXISTS {idx_name} ON activity_logs({col_name})"
                    )
                except sqlite3.OperationalError:
                    pass  # Index might already exist

            logger.info("Migration v1 -> v2 complete")

        # Migration from version 2 to 3: Add screenshot analysis columns
        if from_version < 3:
            logger.info("Running migration v2 -> v3: Adding screenshot analysis columns")

            # Get existing columns in screenshots table
            async with self._connection.execute("PRAGMA table_info(screenshots)") as cursor:
                existing_cols = {row[1] for row in await cursor.fetchall()}

            # Add new analysis columns if they don't exist
            analysis_columns = [
                ("analysis_summary", "TEXT"),
                ("analysis_type", "TEXT"),
                ("analysis_focus", "TEXT"),
                ("analysis_cost", "REAL"),
                ("analyzed_at", "DATETIME"),
            ]

            for col_name, col_type in analysis_columns:
                if col_name not in existing_cols:
                    try:
                        await self._connection.execute(
                            f"ALTER TABLE screenshots ADD COLUMN {col_name} {col_type}"
                        )
                        logger.debug(f"Added column {col_name} to screenshots")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" not in str(e).lower():
                            raise

            logger.info("Migration v2 -> v3 complete")

        # Migration from version 3 to 4: Add rich work analysis columns to screenshots
        if from_version < 4:
            logger.info("Running migration v3 -> v4: Adding rich work analysis columns")

            # Get existing columns in screenshots table
            async with self._connection.execute("PRAGMA table_info(screenshots)") as cursor:
                existing_cols = {row[1] for row in await cursor.fetchall()}

            # Add new work analysis columns
            work_columns = [
                ("analysis_project", "TEXT"),
                ("analysis_category", "TEXT"),
                ("analysis_subcategory", "TEXT"),
                ("analysis_technologies", "TEXT"),  # JSON array
                ("analysis_task", "TEXT"),
                ("analysis_file", "TEXT"),
                ("analysis_deep_work_score", "INTEGER"),
                ("analysis_context_richness", "INTEGER"),
                ("analysis_full", "TEXT"),  # Full JSON response
            ]

            for col_name, col_type in work_columns:
                if col_name not in existing_cols:
                    try:
                        await self._connection.execute(
                            f"ALTER TABLE screenshots ADD COLUMN {col_name} {col_type}"
                        )
                        logger.debug(f"Added column {col_name} to screenshots")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" not in str(e).lower():
                            raise

            # Add indexes for project and category queries
            try:
                await self._connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_screenshot_project ON screenshots(analysis_project)"
                )
                await self._connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_screenshot_category ON screenshots(analysis_category)"
                )
            except sqlite3.OperationalError:
                pass

            logger.info("Migration v3 -> v4 complete")

        # Migration from version 4 to 5: Add focus tracking tables
        if from_version < 5:
            logger.info("Running migration v4 -> v5: Adding focus tracking tables")

            # Create focus_goals table if not exists
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS focus_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    goal_type TEXT NOT NULL DEFAULT 'app_based',
                    target_minutes INTEGER NOT NULL DEFAULT 120,
                    estimated_sessions INTEGER DEFAULT 4,
                    match_criteria JSON,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_focus_goals_active ON focus_goals(is_active)"
            )

            # Create focus_sessions table if not exists
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS focus_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_id INTEGER REFERENCES focus_goals(id),
                    date DATE NOT NULL,
                    pomodoro_count INTEGER DEFAULT 0,
                    total_focus_minutes REAL DEFAULT 0,
                    total_break_minutes REAL DEFAULT 0,
                    off_goal_minutes REAL DEFAULT 0,
                    completed BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_focus_sessions_date ON focus_sessions(date)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_focus_sessions_goal ON focus_sessions(goal_id)"
            )

            # Create pomodoro_history table if not exists
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS pomodoro_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER REFERENCES focus_sessions(id),
                    started_at DATETIME NOT NULL,
                    ended_at DATETIME,
                    duration_minutes REAL,
                    was_completed BOOLEAN DEFAULT FALSE,
                    interruption_count INTEGER DEFAULT 0,
                    primary_app TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pomodoro_session ON pomodoro_history(session_id)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pomodoro_started ON pomodoro_history(started_at)"
            )

            logger.info("Migration v4 -> v5 complete")

        # Migration from version 5 to 6: Add estimated_sessions to focus_goals
        if from_version < 6:
            logger.info("Running migration v5 -> v6: Adding estimated_sessions to focus_goals")

            # Get existing columns in focus_goals table
            async with self._connection.execute("PRAGMA table_info(focus_goals)") as cursor:
                existing_cols = {row[1] for row in await cursor.fetchall()}

            if "estimated_sessions" not in existing_cols:
                try:
                    await self._connection.execute(
                        "ALTER TABLE focus_goals ADD COLUMN estimated_sessions INTEGER DEFAULT 4"
                    )
                    logger.debug("Added column estimated_sessions to focus_goals")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        raise

            logger.info("Migration v5 -> v6 complete")

        # Migration from version 6 to 7: Add productivity goals and tasks
        if from_version < 7:
            logger.info("Running migration v6 -> v7: Adding productivity goals and tasks tables")

            # Create productivity_goals table
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS productivity_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    estimated_hours REAL NOT NULL DEFAULT 40,
                    deadline DATE,
                    priority INTEGER DEFAULT 0,
                    color TEXT DEFAULT '#3B82F6',
                    is_active BOOLEAN DEFAULT TRUE,
                    is_completed BOOLEAN DEFAULT FALSE,
                    target_mode TEXT DEFAULT 'fixed',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_prod_goals_active ON productivity_goals(is_active)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_prod_goals_priority ON productivity_goals(priority)"
            )

            # Create goal_tasks table
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS goal_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_id INTEGER REFERENCES productivity_goals(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    description TEXT,
                    estimated_minutes INTEGER DEFAULT 30,
                    parent_task_id INTEGER REFERENCES goal_tasks(id),
                    sort_order INTEGER DEFAULT 0,
                    is_completed BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_goal_tasks_goal ON goal_tasks(goal_id)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_goal_tasks_parent ON goal_tasks(parent_task_id)"
            )

            # Create goal_daily_progress table
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS goal_daily_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_id INTEGER REFERENCES productivity_goals(id) ON DELETE CASCADE,
                    date DATE NOT NULL,
                    focus_minutes REAL DEFAULT 0,
                    target_minutes REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    sessions_completed INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(goal_id, date)
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_goal_progress_date ON goal_daily_progress(date)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_goal_progress_goal ON goal_daily_progress(goal_id)"
            )

            # Create app_settings table
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insert default settings
            default_settings = [
                ("default_pomodoro_minutes", "25"),
                ("target_mode", "fixed"),
            ]
            for key, value in default_settings:
                await self._connection.execute(
                    """INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)""",
                    (key, value),
                )

            logger.info("Migration v6 -> v7 complete")

        # Migration from version 7 to 8: Add time optimization tables
        if from_version < 8:
            logger.info("Running migration v7 -> v8: Adding time optimization tables")

            # Create user_profile table for personalized optimization
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY,
                    role TEXT,
                    department TEXT,
                    hourly_rate REAL,
                    work_hours_per_week INTEGER DEFAULT 40,
                    time_savings_goal REAL DEFAULT 0.20,
                    ideal_deep_work_hours REAL DEFAULT 4.0,
                    preferred_work_start TEXT DEFAULT '09:00',
                    preferred_work_end TEXT DEFAULT '18:00',
                    focus_apps JSON,
                    communication_apps JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create interrupts table for tracking communication checks
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS interrupts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    interrupt_app TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    previous_app TEXT,
                    next_app TEXT,
                    interrupt_type TEXT,
                    context_loss_estimate REAL,
                    work_context_before TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_interrupts_ts ON interrupts(timestamp)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_interrupts_type ON interrupts(interrupt_type)"
            )

            # Create context_switches table for tracking switch costs
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS context_switches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    from_app TEXT,
                    from_category TEXT,
                    to_app TEXT,
                    to_category TEXT,
                    deep_work_duration_before REAL,
                    estimated_cost_minutes REAL,
                    actual_recovery_seconds REAL,
                    switch_type TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_context_switch_ts ON context_switches(timestamp)"
            )

            # Create daily_optimization_metrics table for pre-aggregated daily data
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS daily_optimization_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL UNIQUE,
                    total_tracked_minutes REAL,
                    deep_work_minutes REAL,
                    communication_minutes REAL,
                    meeting_minutes REAL,
                    admin_minutes REAL,
                    entertainment_minutes REAL,
                    interrupt_count INTEGER,
                    quick_check_count INTEGER,
                    avg_interrupt_duration_seconds REAL,
                    estimated_interrupt_cost_minutes REAL,
                    context_switch_count INTEGER,
                    estimated_switch_cost_minutes REAL,
                    meeting_count INTEGER,
                    usable_blocks_count INTEGER,
                    fragmented_blocks_count INTEGER,
                    swiss_cheese_score REAL,
                    delegate_minutes REAL,
                    eliminate_minutes REAL,
                    automate_minutes REAL,
                    leverage_minutes REAL,
                    potential_savings_minutes REAL,
                    savings_breakdown JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_daily_opt_date ON daily_optimization_metrics(date)"
            )

            # Create weekly_optimization_insights table for AI-generated insights
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS weekly_optimization_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_start DATE NOT NULL,
                    week_end DATE NOT NULL,
                    total_tracked_hours REAL,
                    deep_work_hours REAL,
                    time_saved_estimate REAL,
                    top_time_wasters JSON,
                    automation_opportunities JSON,
                    schedule_recommendations JSON,
                    ai_narrative TEXT,
                    key_insights JSON,
                    action_items JSON,
                    vs_previous_week JSON,
                    model_used TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(week_start, week_end)
                )
            """)

            # Create repetitive_patterns table for automation opportunities
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS repetitive_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    pattern_signature TEXT NOT NULL,
                    description TEXT,
                    frequency_per_week REAL,
                    avg_duration_minutes REAL,
                    total_time_week_minutes REAL,
                    automation_potential TEXT,
                    deal_classification TEXT,
                    ai_suggestion TEXT,
                    first_seen DATE,
                    last_seen DATE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_repetitive_active ON repetitive_patterns(is_active)"
            )

            # Create nudge_history table for tracking nudges
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS nudge_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    nudge_type TEXT NOT NULL,
                    nudge_content TEXT,
                    was_dismissed BOOLEAN DEFAULT FALSE,
                    was_acted_upon BOOLEAN,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_nudge_ts ON nudge_history(timestamp)"
            )

            # Create optimization_recommendations table
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS optimization_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    current_behavior TEXT,
                    suggested_behavior TEXT,
                    estimated_savings_minutes REAL,
                    confidence REAL,
                    evidence JSON,
                    implementation_steps JSON,
                    status TEXT DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    accepted_at DATETIME,
                    dismissed_at DATETIME
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_recommendations_status ON optimization_recommendations(status)"
            )

            # Create daily_briefings table
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS daily_briefings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL UNIQUE,
                    content JSON,
                    viewed_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            logger.info("Migration v7 -> v8 complete")

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        """Context manager for database transactions."""
        if self._connection is None:
            raise RuntimeError("Database not connected")

        async with self._lock:
            await self._connection.execute("BEGIN")
            try:
                yield
                await self._connection.execute("COMMIT")
            except Exception:
                await self._connection.execute("ROLLBACK")
                raise

    async def execute(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> int:
        """Execute a query and return last row ID."""
        if self._connection is None:
            raise RuntimeError("Database not connected")

        async with self._lock:
            cursor = await self._connection.execute(query, params)
            return cursor.lastrowid or 0

    async def execute_many(
        self, query: str, params_list: list[tuple[Any, ...]]
    ) -> None:
        """Execute a query with multiple parameter sets."""
        if self._connection is None:
            raise RuntimeError("Database not connected")

        async with self._lock:
            await self._connection.executemany(query, params_list)

    async def fetch_one(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> dict[str, Any] | None:
        """Fetch a single row."""
        if self._connection is None:
            raise RuntimeError("Database not connected")

        async with self._connection.execute(query, params) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def fetch_all(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        """Fetch all rows."""
        if self._connection is None:
            raise RuntimeError("Database not connected")

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def insert(self, table: str, data: dict[str, Any]) -> int:
        """Insert a row into a table."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        return await self.execute(query, tuple(data.values()))

    async def check_integrity(self) -> bool:
        """Check database integrity."""
        if self._connection is None:
            raise RuntimeError("Database not connected")

        async with self._connection.execute("PRAGMA integrity_check") as cursor:
            row = await cursor.fetchone()
            is_ok = row is not None and row[0] == "ok"

        if not is_ok:
            logger.error("Database integrity check failed!")
        return is_ok

    async def vacuum(self) -> None:
        """Reclaim unused space."""
        if self._connection is None:
            raise RuntimeError("Database not connected")

        await self._connection.execute("VACUUM")
        logger.info("Database vacuumed")

    async def analyze(self) -> None:
        """Update query planner statistics."""
        if self._connection is None:
            raise RuntimeError("Database not connected")

        await self._connection.execute("ANALYZE")
        logger.info("Database analyzed")

    async def get_size_mb(self) -> float:
        """Get database file size in MB."""
        if self.db_path.exists():
            return self.db_path.stat().st_size / (1024 * 1024)
        return 0.0

    def backup(self, backup_dir: Path | None = None) -> Path:
        """Create a backup of the database (synchronous)."""
        backup_dir = backup_dir or self.db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"captains_log_{timestamp}.db"

        shutil.copy2(self.db_path, backup_path)
        logger.info(f"Database backed up to: {backup_path}")
        return backup_path

    # Config helpers
    async def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        row = await self.fetch_one(
            "SELECT value FROM config WHERE key = ?", (key,)
        )
        if row:
            return row["value"]
        return default

    async def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        await self.execute(
            """INSERT INTO config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP""",
            (key, str(value), str(value)),
        )


# Singleton instance
_database: Database | None = None


def get_database(db_path: Path | None = None) -> Database:
    """Get the database singleton instance."""
    global _database

    if _database is None:
        if db_path is None:
            from captains_log.core.config import get_config
            db_path = get_config().db_path
        _database = Database(db_path)

    return _database


async def init_database(db_path: Path | None = None) -> Database:
    """Initialize and connect to the database."""
    db = get_database(db_path)
    await db.connect()
    return db
