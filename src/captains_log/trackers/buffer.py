"""Activity event buffer for batching database writes."""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from captains_log.storage.database import Database

logger = logging.getLogger(__name__)


@dataclass
class ActivityEvent:
    """A single activity event to be stored."""

    timestamp: datetime
    app_name: str
    bundle_id: str
    window_title: str | None = None
    url: str | None = None
    idle_seconds: float = 0.0
    idle_status: str = "ACTIVE"
    is_fullscreen: bool = False
    display_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "app_name": self.app_name,
            "bundle_id": self.bundle_id,
            "window_title": self.window_title,
            "url": self.url,
            "idle_seconds": self.idle_seconds,
            "idle_status": self.idle_status,
            "is_fullscreen": self.is_fullscreen,
            "display_index": self.display_index,
        }


class ActivityBuffer:
    """Buffer for batching activity events before database writes.

    Events are collected in memory and flushed to the database
    periodically (default: every 30 seconds) or when the buffer
    reaches a certain size.

    This reduces database write frequency and improves performance.
    """

    DEFAULT_FLUSH_INTERVAL = 30  # seconds
    DEFAULT_MAX_SIZE = 100  # events

    def __init__(
        self,
        db: Database | None = None,
        flush_interval: int = DEFAULT_FLUSH_INTERVAL,
        max_size: int = DEFAULT_MAX_SIZE,
    ):
        self._db = db
        self._flush_interval = flush_interval
        self._max_size = max_size

        self._events: list[ActivityEvent] = []
        self._lock = threading.Lock()
        self._flush_task: asyncio.Task | None = None
        self._running = False

    def set_database(self, db: Database) -> None:
        """Set the database instance."""
        self._db = db

    def add(self, event: ActivityEvent) -> None:
        """Add an event to the buffer.

        Thread-safe. Will trigger immediate flush if buffer is full.
        """
        with self._lock:
            self._events.append(event)
            event_count = len(self._events)

        logger.debug(f"Buffered event: {event.app_name} ({event_count} in buffer)")

        # Trigger flush if buffer is full
        if event_count >= self._max_size:
            logger.debug("Buffer full, triggering flush")
            asyncio.create_task(self.flush())

    async def flush(self) -> int:
        """Flush buffered events to the database.

        Returns the number of events flushed.
        """
        if self._db is None:
            logger.warning("No database configured, cannot flush")
            return 0

        # Get events from buffer
        with self._lock:
            if not self._events:
                return 0
            events = self._events.copy()
            self._events.clear()

        # Write to database in a transaction
        try:
            async with self._db.transaction():
                for event in events:
                    await self._db.insert("activity_logs", event.to_dict())

            logger.debug(f"Flushed {len(events)} events to database")
            return len(events)

        except Exception as e:
            # Put events back on failure
            with self._lock:
                self._events = events + self._events
            logger.error(f"Failed to flush events: {e}")
            raise

    def flush_sync(self) -> int:
        """Synchronous flush for shutdown scenarios.

        Uses a new event loop if necessary.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Schedule the flush and wait
            future = asyncio.run_coroutine_threadsafe(self.flush(), loop)
            return future.result(timeout=5)
        else:
            # Create new loop
            return asyncio.run(self.flush())

    async def start(self) -> None:
        """Start the periodic flush task."""
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info(f"Buffer started (flush every {self._flush_interval}s)")

    async def stop(self) -> None:
        """Stop the periodic flush task and flush remaining events."""
        if not self._running:
            return

        self._running = False

        # Cancel flush task
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        # Final flush
        await self.flush()
        logger.info("Buffer stopped")

    async def _periodic_flush(self) -> None:
        """Periodically flush the buffer."""
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                if self._running:  # Check again after sleep
                    await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush: {e}")

    @property
    def pending_count(self) -> int:
        """Get number of events pending in buffer."""
        with self._lock:
            return len(self._events)

    @property
    def is_running(self) -> bool:
        """Check if buffer flush task is running."""
        return self._running

    def clear(self) -> list[ActivityEvent]:
        """Clear and return all buffered events without flushing."""
        with self._lock:
            events = self._events.copy()
            self._events.clear()
        return events
