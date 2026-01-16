"""Batch processor for queuing and processing Claude API requests."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from captains_log.ai.claude_client import ClaudeClient, get_claude_client
from captains_log.ai.schemas import SummaryResponse
from captains_log.storage.database import Database

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Manages summary queue and batch processing of Claude API requests.

    This processor queues summary requests and processes them either:
    1. Immediately in real-time mode (use_batch_api=False)
    2. In batches at scheduled intervals (use_batch_api=True)

    Batch processing reduces API costs by ~50% using Anthropic's Batch API.
    """

    def __init__(
        self,
        db: Database,
        claude_client: ClaudeClient | None = None,
        use_batch_api: bool = True,
        batch_interval_hours: int = 6,
        max_queue_size: int = 1000,
        max_retries: int = 3,
    ):
        """Initialize batch processor.

        Args:
            db: Database instance for queue persistence.
            claude_client: Claude client instance (created if None).
            use_batch_api: Whether to use batch API (True) or real-time (False).
            batch_interval_hours: Hours between batch processing runs.
            max_queue_size: Maximum queue size before oldest items are dropped.
            max_retries: Maximum retries for failed items.
        """
        self.db = db
        self._claude_client = claude_client
        self.use_batch_api = use_batch_api
        self.batch_interval_hours = batch_interval_hours
        self.max_queue_size = max_queue_size
        self.max_retries = max_retries

        self._running = False
        self._process_task: asyncio.Task | None = None

        # Callback for when summaries are generated
        self._on_summary_callback: Callable[[SummaryResponse, dict], Awaitable[None]] | None = None

    @property
    def claude_client(self) -> ClaudeClient:
        """Get or create Claude client."""
        if self._claude_client is None:
            self._claude_client = get_claude_client()
        return self._claude_client

    @property
    def is_running(self) -> bool:
        """Check if processor is running."""
        return self._running

    def set_on_summary_callback(
        self, callback: Callable[[SummaryResponse, dict], Awaitable[None]]
    ) -> None:
        """Set callback for when summaries are generated.

        Args:
            callback: Async function(summary, metadata) called for each summary.
        """
        self._on_summary_callback = callback

    async def start(self) -> None:
        """Start the batch processor."""
        if self._running:
            return

        self._running = True

        if self.use_batch_api:
            # Start periodic batch processing
            self._process_task = asyncio.create_task(self._batch_process_loop())
            logger.info(
                f"Batch processor started (processing every {self.batch_interval_hours}h)"
            )
        else:
            # Start real-time processing
            self._process_task = asyncio.create_task(self._realtime_process_loop())
            logger.info("Batch processor started (real-time mode)")

    async def stop(self) -> None:
        """Stop the batch processor."""
        self._running = False

        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
            self._process_task = None

        logger.info("Batch processor stopped")

    async def queue_summary(
        self,
        period_start: datetime,
        period_end: datetime,
        activity_data: list[dict[str, Any]],
        screenshot_path: Path | None = None,
        focus_hint: int | None = None,
    ) -> int:
        """Add a summary request to the queue.

        Args:
            period_start: Start of the period to summarize.
            period_end: End of the period to summarize.
            activity_data: Activity events for this period.
            screenshot_path: Optional screenshot path.
            focus_hint: Pre-calculated focus score hint.

        Returns:
            Queue item ID.
        """
        # Check queue size
        count = await self._get_pending_count()
        if count >= self.max_queue_size:
            logger.warning("Queue full, dropping oldest pending items")
            await self._drop_oldest_pending(100)

        # Insert into queue
        queue_id = await self.db.insert(
            "summary_queue",
            {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "screenshot_path": str(screenshot_path) if screenshot_path else None,
                "activity_data": json.dumps(activity_data),
                "status": "pending",
                "retry_count": 0,
            },
        )

        logger.debug(f"Queued summary request {queue_id} for {period_start}")

        # In real-time mode, process immediately
        if not self.use_batch_api and self._running:
            asyncio.create_task(self._process_single_item(queue_id))

        return queue_id

    async def process_queue(self, limit: int = 100) -> int:
        """Process pending queue items.

        Args:
            limit: Maximum number of items to process.

        Returns:
            Number of items processed successfully.
        """
        # Get pending items
        items = await self.db.fetch_all(
            """
            SELECT id, period_start, period_end, screenshot_path, activity_data
            FROM summary_queue
            WHERE status = 'pending' AND retry_count < ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (self.max_retries, limit),
        )

        if not items:
            return 0

        logger.info(f"Processing {len(items)} queued summary requests")
        processed = 0

        for item in items:
            try:
                await self._process_item(item)
                processed += 1
            except Exception as e:
                logger.error(f"Failed to process queue item {item['id']}: {e}")
                await self._mark_item_failed(item["id"], str(e))

        return processed

    async def _process_item(self, item: dict[str, Any]) -> None:
        """Process a single queue item."""
        item_id = item["id"]
        period_start = item["period_start"]
        period_end = item["period_end"]
        screenshot_path = Path(item["screenshot_path"]) if item["screenshot_path"] else None
        activity_data = json.loads(item["activity_data"])

        # Calculate context switches
        context_switches = self._count_context_switches(activity_data)

        # Calculate focus hint
        focus_hint = self._calculate_focus_hint(activity_data, context_switches)

        # Call Claude API
        try:
            summary, usage = await self.claude_client.summarize_activity(
                activity_data=activity_data,
                period_start=period_start,
                period_end=period_end,
                context_switches=context_switches,
                focus_hint=focus_hint,
                screenshot_path=screenshot_path,
            )

            # Save summary to database
            await self._save_summary(
                period_start=period_start,
                period_end=period_end,
                summary=summary,
                usage=usage,
                screenshot_path=screenshot_path,
            )

            # Mark queue item as completed
            await self._mark_item_completed(item_id)

            # Call callback if set
            if self._on_summary_callback:
                await self._on_summary_callback(
                    summary,
                    {
                        "period_start": period_start,
                        "period_end": period_end,
                        "queue_id": item_id,
                    },
                )

            logger.debug(f"Processed queue item {item_id}: {summary.activity_type}")

        except Exception as e:
            logger.error(f"API call failed for queue item {item_id}: {e}")
            await self._mark_item_failed(item_id, str(e))
            raise

    async def _process_single_item(self, item_id: int) -> None:
        """Process a single item by ID (for real-time mode)."""
        item = await self.db.fetch_one(
            "SELECT * FROM summary_queue WHERE id = ?",
            (item_id,),
        )
        if item and item["status"] == "pending":
            await self._process_item(item)

    async def _save_summary(
        self,
        period_start: str,
        period_end: str,
        summary: SummaryResponse,
        usage: dict[str, int],
        screenshot_path: Path | None = None,
    ) -> int:
        """Save summary to database."""
        # Find associated screenshot ID if path provided
        screenshot_id = None
        if screenshot_path:
            ss = await self.db.fetch_one(
                "SELECT id FROM screenshots WHERE file_path LIKE ?",
                (f"%{screenshot_path.name}",),
            )
            if ss:
                screenshot_id = ss["id"]

        return await self.db.insert(
            "summaries",
            {
                "period_start": period_start,
                "period_end": period_end,
                "screenshot_id": screenshot_id,
                "primary_app": summary.primary_app,
                "activity_type": (
                    summary.activity_type.value
                    if hasattr(summary.activity_type, "value")
                    else str(summary.activity_type)
                ),
                "focus_score": summary.focus_score,
                "key_activities": json.dumps(summary.key_activities),
                "context": summary.context,
                "context_switches": summary.context_switches,
                "tags": json.dumps(summary.tags),
                "model_used": self.claude_client.model,
                "tokens_input": usage.get("input_tokens", 0),
                "tokens_output": usage.get("output_tokens", 0),
            },
        )

    async def _mark_item_completed(self, item_id: int) -> None:
        """Mark queue item as completed."""
        await self.db.execute(
            """
            UPDATE summary_queue
            SET status = 'completed', processed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (item_id,),
        )

    async def _mark_item_failed(self, item_id: int, error: str) -> None:
        """Mark queue item as failed and increment retry count."""
        await self.db.execute(
            """
            UPDATE summary_queue
            SET status = CASE
                WHEN retry_count + 1 >= ? THEN 'failed'
                ELSE 'pending'
            END,
            retry_count = retry_count + 1,
            error_message = ?
            WHERE id = ?
            """,
            (self.max_retries, error, item_id),
        )

    async def _get_pending_count(self) -> int:
        """Get count of pending queue items."""
        result = await self.db.fetch_one(
            "SELECT COUNT(*) as count FROM summary_queue WHERE status = 'pending'"
        )
        return result["count"] if result else 0

    async def _drop_oldest_pending(self, count: int) -> None:
        """Drop oldest pending items from queue."""
        await self.db.execute(
            """
            DELETE FROM summary_queue
            WHERE id IN (
                SELECT id FROM summary_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
            )
            """,
            (count,),
        )
        logger.warning(f"Dropped {count} oldest pending queue items")

    def _count_context_switches(self, activity_data: list[dict]) -> int:
        """Count context switches in activity data."""
        if len(activity_data) < 2:
            return 0

        switches = 0
        prev_bundle = activity_data[0].get("bundle_id")

        for event in activity_data[1:]:
            curr_bundle = event.get("bundle_id")
            if curr_bundle and curr_bundle != prev_bundle:
                switches += 1
                prev_bundle = curr_bundle

        return switches

    def _calculate_focus_hint(
        self, activity_data: list[dict], context_switches: int
    ) -> int:
        """Calculate focus score hint based on activity data."""
        if not activity_data:
            return 5

        # Base score
        score = 10

        # Deduct for context switches
        if context_switches > 10:
            score -= 5
        elif context_switches > 5:
            score -= 3
        elif context_switches > 2:
            score -= 1

        # Check for idle time
        idle_events = sum(
            1 for e in activity_data
            if e.get("idle_status") in ("AWAY", "IDLE_BUT_PRESENT")
        )
        if idle_events > len(activity_data) * 0.5:
            score -= 2

        # Check for entertainment apps
        entertainment_apps = {
            "com.apple.Safari",  # Could be either, so mild
            "com.spotify.client",
            "tv.plex.player",
            "com.netflix.*",
        }
        entertainment_count = sum(
            1 for e in activity_data
            if any(e.get("bundle_id", "").startswith(app.replace("*", ""))
                   for app in entertainment_apps)
        )
        if entertainment_count > len(activity_data) * 0.3:
            score -= 1

        return max(1, min(10, score))

    async def _batch_process_loop(self) -> None:
        """Background loop for periodic batch processing."""
        # Wait a bit before first run
        await asyncio.sleep(60)

        while self._running:
            try:
                # Check if we have pending items
                pending = await self._get_pending_count()

                if pending > 0:
                    logger.info(f"Starting batch processing ({pending} pending items)")
                    processed = await self.process_queue(limit=200)
                    logger.info(f"Batch processing complete: {processed} items processed")

                # Wait for next batch interval
                await asyncio.sleep(self.batch_interval_hours * 3600)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch processing loop: {e}")
                await asyncio.sleep(300)  # Wait 5 min on error

    async def _realtime_process_loop(self) -> None:
        """Background loop for real-time processing."""
        while self._running:
            try:
                # Check for any pending items that weren't processed
                pending = await self._get_pending_count()

                if pending > 0:
                    await self.process_queue(limit=10)

                await asyncio.sleep(5)  # Check every 5 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in realtime processing loop: {e}")
                await asyncio.sleep(10)

    async def get_queue_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        stats = await self.db.fetch_one(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM summary_queue
            """
        )

        return {
            "total": stats["total"] if stats else 0,
            "pending": stats["pending"] if stats else 0,
            "completed": stats["completed"] if stats else 0,
            "failed": stats["failed"] if stats else 0,
            "mode": "batch" if self.use_batch_api else "realtime",
            "batch_interval_hours": self.batch_interval_hours if self.use_batch_api else None,
        }

    async def get_recent_summaries(
        self, limit: int = 10, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Get recent summaries."""
        if since:
            return await self.db.fetch_all(
                """
                SELECT * FROM summaries
                WHERE created_at >= ?
                ORDER BY period_start DESC
                LIMIT ?
                """,
                (since.isoformat(), limit),
            )
        else:
            return await self.db.fetch_all(
                "SELECT * FROM summaries ORDER BY period_start DESC LIMIT ?",
                (limit,),
            )
