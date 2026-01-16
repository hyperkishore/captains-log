"""Five-minute activity summarizer."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from captains_log.ai.batch_processor import BatchProcessor
from captains_log.storage.database import Database
from captains_log.summarizers.focus_calculator import FocusCalculator

logger = logging.getLogger(__name__)


class FiveMinuteSummarizer:
    """Generates 5-minute activity summaries using Claude AI.

    This summarizer:
    1. Collects activity data for 5-minute periods
    2. Calculates focus metrics locally
    3. Queues summary requests for Claude API
    4. Associates screenshots with summaries
    """

    def __init__(
        self,
        db: Database,
        batch_processor: BatchProcessor,
        focus_calculator: FocusCalculator | None = None,
        interval_minutes: int = 5,
        screenshots_dir: Path | None = None,
    ):
        """Initialize the summarizer.

        Args:
            db: Database instance.
            batch_processor: Batch processor for API requests.
            focus_calculator: Focus calculator (created if None).
            interval_minutes: Summary interval in minutes.
            screenshots_dir: Directory containing screenshots.
        """
        self.db = db
        self.batch_processor = batch_processor
        self.focus_calculator = focus_calculator or FocusCalculator()
        self.interval_minutes = interval_minutes
        self.screenshots_dir = screenshots_dir

        self._running = False
        self._summarize_task: asyncio.Task | None = None
        self._last_summary_end: datetime | None = None

        # Callback for summary generation
        self._on_summary_callback: Callable[[dict], Awaitable[None]] | None = None

    @property
    def is_running(self) -> bool:
        """Check if summarizer is running."""
        return self._running

    def set_on_summary_callback(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Set callback for when summaries are queued.

        Args:
            callback: Async function(metadata) called when summary is queued.
        """
        self._on_summary_callback = callback

    async def start(self) -> None:
        """Start the periodic summarizer."""
        if self._running:
            return

        self._running = True

        # Find where we left off
        last_summary = await self.db.fetch_one(
            "SELECT period_end FROM summaries ORDER BY period_end DESC LIMIT 1"
        )

        if last_summary and last_summary["period_end"]:
            try:
                self._last_summary_end = datetime.fromisoformat(
                    last_summary["period_end"].replace("Z", "+00:00")
                )
            except ValueError:
                self._last_summary_end = None

        # Start periodic task
        self._summarize_task = asyncio.create_task(self._summarize_loop())

        logger.info(
            f"Five-minute summarizer started (interval: {self.interval_minutes} min)"
        )

    async def stop(self) -> None:
        """Stop the summarizer."""
        self._running = False

        if self._summarize_task:
            self._summarize_task.cancel()
            try:
                await self._summarize_task
            except asyncio.CancelledError:
                pass
            self._summarize_task = None

        logger.info("Five-minute summarizer stopped")

    async def _summarize_loop(self) -> None:
        """Background loop for periodic summarization."""
        # Wait until next interval boundary
        await self._wait_for_next_interval()

        while self._running:
            try:
                # Generate summary for the completed interval
                await self._generate_current_summary()

                # Wait for next interval
                await asyncio.sleep(self.interval_minutes * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in summarize loop: {e}")
                await asyncio.sleep(60)  # Wait a minute on error

    async def _wait_for_next_interval(self) -> None:
        """Wait until the next interval boundary."""
        now = datetime.utcnow()
        minutes = now.minute
        next_boundary = (minutes // self.interval_minutes + 1) * self.interval_minutes

        if next_boundary >= 60:
            # Next hour
            wait_minutes = 60 - minutes + (next_boundary - 60)
        else:
            wait_minutes = next_boundary - minutes

        wait_seconds = wait_minutes * 60 - now.second

        if wait_seconds > 0:
            logger.debug(f"Waiting {wait_seconds}s until next summary interval")
            await asyncio.sleep(wait_seconds)

    async def _generate_current_summary(self) -> None:
        """Generate summary for the just-completed interval."""
        now = datetime.utcnow()

        # Calculate period boundaries
        period_end = now.replace(second=0, microsecond=0)
        period_start = period_end - timedelta(minutes=self.interval_minutes)

        # Check if we already have a summary for this period
        existing = await self.db.fetch_one(
            """
            SELECT id FROM summaries
            WHERE period_start = ? AND period_end = ?
            """,
            (period_start.isoformat(), period_end.isoformat()),
        )

        if existing:
            logger.debug(f"Summary already exists for {period_start}")
            return

        # Fetch activity data for this period
        activity_data = await self._fetch_activity_data(period_start, period_end)

        if not activity_data:
            logger.debug(f"No activity data for {period_start} - {period_end}")
            return

        # Find nearest screenshot
        screenshot_path = await self._find_nearest_screenshot(period_start, period_end)

        # Calculate focus metrics
        focus_metrics = self.focus_calculator.calculate(activity_data)

        # Queue for summarization
        queue_id = await self.batch_processor.queue_summary(
            period_start=period_start,
            period_end=period_end,
            activity_data=activity_data,
            screenshot_path=screenshot_path,
            focus_hint=focus_metrics.focus_score,
        )

        logger.info(
            f"Queued summary for {period_start.strftime('%H:%M')} - "
            f"{period_end.strftime('%H:%M')} (focus: {focus_metrics.focus_score}/10, "
            f"queue_id: {queue_id})"
        )

        # Call callback if set
        if self._on_summary_callback:
            await self._on_summary_callback({
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "focus_hint": focus_metrics.focus_score,
                "queue_id": queue_id,
                "activity_count": len(activity_data),
                "has_screenshot": screenshot_path is not None,
            })

        self._last_summary_end = period_end

    async def _fetch_activity_data(
        self, period_start: datetime, period_end: datetime
    ) -> list[dict[str, Any]]:
        """Fetch activity data for a period."""
        rows = await self.db.fetch_all(
            """
            SELECT
                timestamp, app_name, bundle_id, window_title, url,
                idle_seconds, idle_status, is_fullscreen,
                work_category, work_service, work_project, work_document,
                work_meeting, work_channel, work_issue_id, work_organization,
                keystrokes, mouse_clicks, scroll_events, engagement_score
            FROM activity_logs
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp ASC
            """,
            (period_start.isoformat(), period_end.isoformat()),
        )

        return rows

    async def _find_nearest_screenshot(
        self, period_start: datetime, period_end: datetime
    ) -> Path | None:
        """Find the nearest screenshot for a period."""
        # Look for screenshots within or near the period
        search_start = period_start - timedelta(minutes=1)
        search_end = period_end + timedelta(minutes=1)

        screenshot = await self.db.fetch_one(
            """
            SELECT file_path FROM screenshots
            WHERE timestamp >= ? AND timestamp <= ?
            AND is_deleted = FALSE
            ORDER BY ABS(
                julianday(timestamp) - julianday(?)
            ) ASC
            LIMIT 1
            """,
            (
                search_start.isoformat(),
                search_end.isoformat(),
                period_start.isoformat(),
            ),
        )

        if screenshot and screenshot["file_path"]:
            path = Path(screenshot["file_path"])
            if self.screenshots_dir:
                path = self.screenshots_dir / path.name

            if path.exists():
                return path

        return None

    async def generate_for_period(
        self, period_start: datetime, period_end: datetime
    ) -> int | None:
        """Manually generate summary for a specific period.

        Args:
            period_start: Start of period.
            period_end: End of period.

        Returns:
            Queue ID if queued, None if no data.
        """
        activity_data = await self._fetch_activity_data(period_start, period_end)

        if not activity_data:
            return None

        screenshot_path = await self._find_nearest_screenshot(period_start, period_end)
        focus_metrics = self.focus_calculator.calculate(activity_data)

        return await self.batch_processor.queue_summary(
            period_start=period_start,
            period_end=period_end,
            activity_data=activity_data,
            screenshot_path=screenshot_path,
            focus_hint=focus_metrics.focus_score,
        )

    async def backfill_summaries(
        self,
        since: datetime | None = None,
        limit: int = 100,
    ) -> int:
        """Generate summaries for historical periods that are missing.

        Args:
            since: Start from this time (default: 24 hours ago).
            limit: Maximum number of summaries to generate.

        Returns:
            Number of summaries queued.
        """
        since = since or (datetime.utcnow() - timedelta(hours=24))

        # Find periods without summaries
        queued = 0
        current = since.replace(
            minute=(since.minute // self.interval_minutes) * self.interval_minutes,
            second=0,
            microsecond=0,
        )
        end = datetime.utcnow()

        while current < end and queued < limit:
            period_end = current + timedelta(minutes=self.interval_minutes)

            # Check if summary exists
            existing = await self.db.fetch_one(
                """
                SELECT id FROM summaries
                WHERE period_start = ? AND period_end = ?
                """,
                (current.isoformat(), period_end.isoformat()),
            )

            if not existing:
                queue_id = await self.generate_for_period(current, period_end)
                if queue_id:
                    queued += 1
                    logger.debug(
                        f"Backfilled summary for {current.strftime('%H:%M')} "
                        f"(queue_id: {queue_id})"
                    )

            current = period_end

        if queued > 0:
            logger.info(f"Backfilled {queued} summaries since {since}")

        return queued

    async def get_local_summary(
        self, period_start: datetime, period_end: datetime
    ) -> dict[str, Any] | None:
        """Get a local summary without using the API.

        This provides immediate insights using only local analysis.

        Args:
            period_start: Start of period.
            period_end: End of period.

        Returns:
            Local summary dict or None if no data.
        """
        activity_data = await self._fetch_activity_data(period_start, period_end)

        if not activity_data:
            return None

        # Calculate metrics locally
        focus_metrics = self.focus_calculator.calculate(activity_data)

        # Get app usage
        apps = [e.get("app_name", "Unknown") for e in activity_data]
        app_counts = Counter(apps)

        # Get work categories
        categories = [e.get("work_category") for e in activity_data if e.get("work_category")]
        category_counts = Counter(categories)

        # Detect activity type based on primary app and category
        activity_type = self._detect_activity_type(
            focus_metrics.primary_app,
            category_counts.most_common(1)[0][0] if category_counts else None,
        )

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "primary_app": focus_metrics.primary_app,
            "activity_type": activity_type,
            "focus_score": focus_metrics.focus_score,
            "focus_category": focus_metrics.focus_category,
            "context_switches": focus_metrics.context_switches,
            "unique_apps": focus_metrics.unique_apps,
            "idle_percentage": focus_metrics.idle_percentage,
            "engagement_score": focus_metrics.engagement_score,
            "app_usage": dict(app_counts.most_common(5)),
            "work_categories": dict(category_counts) if category_counts else {},
            "total_events": focus_metrics.total_events,
            "is_local": True,  # Flag that this is not AI-generated
        }

    def _detect_activity_type(
        self, primary_app: str, work_category: str | None
    ) -> str:
        """Detect activity type from app and category."""
        # Map work categories to activity types
        category_map = {
            "coding": "coding",
            "development": "coding",
            "documentation": "writing",
            "communication": "communication",
            "meetings": "meetings",
            "design": "design",
            "project_management": "admin",
            "productivity": "admin",
        }

        if work_category and work_category.lower() in category_map:
            return category_map[work_category.lower()]

        # Map common apps to activity types
        app_lower = primary_app.lower()

        if any(x in app_lower for x in ["code", "studio", "xcode", "terminal", "iterm"]):
            return "coding"
        if any(x in app_lower for x in ["slack", "teams", "discord", "mail", "messages"]):
            return "communication"
        if any(x in app_lower for x in ["zoom", "meet", "facetime"]):
            return "meetings"
        if any(x in app_lower for x in ["figma", "sketch", "photoshop"]):
            return "design"
        if any(x in app_lower for x in ["chrome", "safari", "firefox", "arc"]):
            return "browsing"
        if any(x in app_lower for x in ["word", "pages", "notion", "docs"]):
            return "writing"
        if any(x in app_lower for x in ["spotify", "music", "netflix", "youtube"]):
            return "entertainment"

        return "unknown"

    async def get_stats(self) -> dict[str, Any]:
        """Get summarizer statistics."""
        # Count summaries by status
        summary_stats = await self.db.fetch_one(
            """
            SELECT
                COUNT(*) as total_summaries,
                AVG(focus_score) as avg_focus,
                SUM(tokens_input) as total_input_tokens,
                SUM(tokens_output) as total_output_tokens
            FROM summaries
            """
        )

        queue_stats = await self.batch_processor.get_queue_stats()

        return {
            "is_running": self._running,
            "interval_minutes": self.interval_minutes,
            "last_summary_end": (
                self._last_summary_end.isoformat() if self._last_summary_end else None
            ),
            "total_summaries": summary_stats["total_summaries"] if summary_stats else 0,
            "avg_focus_score": (
                round(summary_stats["avg_focus"], 1)
                if summary_stats and summary_stats["avg_focus"]
                else None
            ),
            "total_tokens": {
                "input": summary_stats["total_input_tokens"] if summary_stats else 0,
                "output": summary_stats["total_output_tokens"] if summary_stats else 0,
            },
            "queue": queue_stats,
        }
