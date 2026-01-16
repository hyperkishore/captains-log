"""Screenshot file management and retention cleanup."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from captains_log.storage.database import Database
    from captains_log.trackers.screenshot_capture import ScreenshotInfo

logger = logging.getLogger(__name__)


@dataclass
class ScreenshotRecord:
    """Database record for a screenshot."""

    id: int
    timestamp: datetime
    file_path: str
    file_size_bytes: int
    width: int
    height: int
    expires_at: datetime
    is_deleted: bool
    created_at: datetime


class ScreenshotManager:
    """Manages screenshot persistence and retention.

    Handles:
    - Saving screenshot metadata to database
    - File cleanup when retention expires
    - Querying screenshots by timestamp/proximity
    """

    def __init__(self, db: Database, screenshots_dir: Path):
        """Initialize screenshot manager.

        Args:
            db: Database instance for metadata storage
            screenshots_dir: Base directory for screenshot files
        """
        self._db = db
        self._screenshots_dir = screenshots_dir
        self._cleanup_lock = asyncio.Lock()

    async def save_screenshot(self, info: ScreenshotInfo) -> int:
        """Save screenshot metadata to database.

        Args:
            info: Screenshot metadata from capture

        Returns:
            Inserted record ID
        """
        # Store relative path for portability
        try:
            relative_path = info.file_path.relative_to(self._screenshots_dir)
        except ValueError:
            # If not relative, use the full path
            relative_path = info.file_path

        data = {
            "timestamp": info.timestamp.isoformat(),
            "file_path": str(relative_path),
            "file_size_bytes": info.file_size_bytes,
            "width": info.width,
            "height": info.height,
            "expires_at": info.expires_at.isoformat(),
            "is_deleted": False,
        }

        record_id = await self._db.insert("screenshots", data)
        logger.debug(f"Saved screenshot metadata: ID={record_id}, path={relative_path}")
        return record_id

    async def get_screenshot_by_id(self, screenshot_id: int) -> ScreenshotRecord | None:
        """Get screenshot record by ID."""
        row = await self._db.fetch_one(
            """
            SELECT id, timestamp, file_path, file_size_bytes, width, height,
                   expires_at, is_deleted, created_at
            FROM screenshots
            WHERE id = ? AND is_deleted = FALSE
            """,
            (screenshot_id,),
        )

        if row is None:
            return None

        return self._row_to_record(row)

    async def get_screenshots_for_date(self, date: str) -> list[ScreenshotRecord]:
        """Get all screenshots for a date (YYYY-MM-DD format)."""
        rows = await self._db.fetch_all(
            """
            SELECT id, timestamp, file_path, file_size_bytes, width, height,
                   expires_at, is_deleted, created_at
            FROM screenshots
            WHERE date(timestamp) = ? AND is_deleted = FALSE
            ORDER BY timestamp ASC
            """,
            (date,),
        )

        return [self._row_to_record(row) for row in rows]

    async def get_nearest_screenshot(
        self,
        timestamp: datetime,
        max_delta_seconds: int = 300,
    ) -> ScreenshotRecord | None:
        """Find screenshot closest to a given timestamp.

        Used for correlating activity logs with screenshots.

        Args:
            timestamp: Target timestamp
            max_delta_seconds: Maximum seconds from timestamp (default: 5 minutes)

        Returns:
            Nearest screenshot record, or None if none within max_delta
        """
        ts_str = timestamp.isoformat()

        row = await self._db.fetch_one(
            """
            SELECT id, timestamp, file_path, file_size_bytes, width, height,
                   expires_at, is_deleted, created_at,
                   ABS(strftime('%s', timestamp) - strftime('%s', ?)) as delta
            FROM screenshots
            WHERE is_deleted = FALSE
              AND ABS(strftime('%s', timestamp) - strftime('%s', ?)) <= ?
            ORDER BY delta ASC
            LIMIT 1
            """,
            (ts_str, ts_str, max_delta_seconds),
        )

        if row is None:
            return None

        return self._row_to_record(row)

    async def cleanup_expired(self) -> tuple[int, int]:
        """Delete expired screenshots (files and database records).

        Returns:
            (files_deleted, records_updated) count
        """
        async with self._cleanup_lock:
            now = datetime.utcnow().isoformat()

            # Get expired records
            expired = await self._db.fetch_all(
                """
                SELECT id, file_path FROM screenshots
                WHERE expires_at <= ? AND is_deleted = FALSE
                """,
                (now,),
            )

            if not expired:
                return 0, 0

            files_deleted = 0
            record_ids = []

            for record in expired:
                record_ids.append(record["id"])

                # Delete the file
                file_path = self._screenshots_dir / record["file_path"]
                try:
                    if file_path.exists():
                        file_path.unlink()
                        files_deleted += 1
                        logger.debug(f"Deleted expired screenshot: {file_path}")
                except FileNotFoundError:
                    # Already deleted (race condition)
                    pass
                except PermissionError as e:
                    logger.warning(f"Cannot delete {file_path}: {e}")
                except Exception as e:
                    logger.error(f"Error deleting {file_path}: {e}")

            # Mark records as deleted in database
            if record_ids:
                placeholders = ",".join("?" * len(record_ids))
                await self._db.execute(
                    f"UPDATE screenshots SET is_deleted = TRUE WHERE id IN ({placeholders})",
                    tuple(record_ids),
                )

            # Try to remove empty date directories
            await self._cleanup_empty_dirs()

            logger.info(
                f"Cleanup complete: {files_deleted} files deleted, "
                f"{len(record_ids)} records marked"
            )

            return files_deleted, len(record_ids)

    async def get_storage_stats(self) -> dict:
        """Get screenshot storage statistics."""
        # Get count and total size from database
        stats_row = await self._db.fetch_one(
            """
            SELECT
                COUNT(*) as total_count,
                COALESCE(SUM(file_size_bytes), 0) as total_bytes,
                MIN(timestamp) as oldest,
                MAX(timestamp) as newest
            FROM screenshots
            WHERE is_deleted = FALSE
            """
        )

        # Count today's screenshots
        today = datetime.now().strftime("%Y-%m-%d")
        today_row = await self._db.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM screenshots
            WHERE date(timestamp) = ? AND is_deleted = FALSE
            """,
            (today,),
        )

        # Get pending cleanup count
        now = datetime.utcnow().isoformat()
        pending_row = await self._db.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM screenshots
            WHERE expires_at <= ? AND is_deleted = FALSE
            """,
            (now,),
        )

        return {
            "total_count": stats_row["total_count"] if stats_row else 0,
            "total_size_mb": (stats_row["total_bytes"] / (1024 * 1024)) if stats_row else 0,
            "oldest_timestamp": stats_row["oldest"] if stats_row else None,
            "newest_timestamp": stats_row["newest"] if stats_row else None,
            "count_today": today_row["count"] if today_row else 0,
            "pending_cleanup": pending_row["count"] if pending_row else 0,
        }

    def get_screenshot_path(self, file_path: str) -> Path | None:
        """Get absolute path to screenshot file, or None if not found."""
        full_path = self._screenshots_dir / file_path
        if full_path.exists():
            return full_path
        return None

    async def _cleanup_empty_dirs(self) -> None:
        """Remove empty date directories."""
        try:
            for item in self._screenshots_dir.iterdir():
                if item.is_dir():
                    # Check if directory is empty
                    try:
                        next(item.iterdir())
                    except StopIteration:
                        # Directory is empty, remove it
                        item.rmdir()
                        logger.debug(f"Removed empty directory: {item}")
        except Exception as e:
            logger.warning(f"Error cleaning up empty directories: {e}")

    def _row_to_record(self, row: dict) -> ScreenshotRecord:
        """Convert database row to ScreenshotRecord."""
        return ScreenshotRecord(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            file_path=row["file_path"],
            file_size_bytes=row["file_size_bytes"],
            width=row["width"],
            height=row["height"],
            expires_at=datetime.fromisoformat(row["expires_at"]),
            is_deleted=bool(row["is_deleted"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def get_screenshots_between(
        self,
        start: datetime,
        end: datetime,
    ) -> list[ScreenshotRecord]:
        """Get screenshots between two timestamps."""
        rows = await self._db.fetch_all(
            """
            SELECT id, timestamp, file_path, file_size_bytes, width, height,
                   expires_at, is_deleted, created_at
            FROM screenshots
            WHERE timestamp >= ? AND timestamp <= ? AND is_deleted = FALSE
            ORDER BY timestamp ASC
            """,
            (start.isoformat(), end.isoformat()),
        )

        return [self._row_to_record(row) for row in rows]

    async def mark_deleted(self, screenshot_id: int) -> bool:
        """Mark a screenshot as deleted (soft delete).

        Returns:
            True if record was found and marked, False otherwise
        """
        result = await self._db.execute(
            "UPDATE screenshots SET is_deleted = TRUE WHERE id = ? AND is_deleted = FALSE",
            (screenshot_id,),
        )
        return result > 0

    async def get_recent_screenshots(self, limit: int = 10) -> list[ScreenshotRecord]:
        """Get the most recent screenshots."""
        rows = await self._db.fetch_all(
            """
            SELECT id, timestamp, file_path, file_size_bytes, width, height,
                   expires_at, is_deleted, created_at
            FROM screenshots
            WHERE is_deleted = FALSE
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )

        return [self._row_to_record(row) for row in rows]
