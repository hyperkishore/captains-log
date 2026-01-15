"""SQLite database management with WAL mode and migrations."""

from __future__ import annotations

import asyncio
import logging
import shutil
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite

logger = logging.getLogger(__name__)

# Schema version for migrations
SCHEMA_VERSION = 1

# Database schema
SCHEMA = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Core activity tracking
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
            await self._connection.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            logger.info(f"Schema updated to version {SCHEMA_VERSION}")

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
