"""Notification scheduler for the daemon.

Runs inside the orchestrator and sends notifications at configured times:
- Evening digest (default 6pm)
- Morning briefing (default 9am)
- Weekly summary (default Friday 5pm)
- Daemon health alert (if no activity in 1 hour)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Any

from captains_log.notifications.daily_digest import DailyDigestGenerator
from captains_log.notifications.notifier import send_notification

logger = logging.getLogger(__name__)


class NotificationScheduler:
    """Schedules and sends notifications from the daemon."""

    def __init__(
        self,
        db: Any,
        evening_time: str = "18:00",
        morning_time: str = "09:00",
        morning_enabled: bool = False,
    ):
        self.db = db
        self.digest_generator = DailyDigestGenerator(db)

        # Parse times
        h, m = evening_time.split(":")
        self._evening_time = time(int(h), int(m))
        h, m = morning_time.split(":")
        self._morning_time = time(int(h), int(m))

        self._morning_enabled = morning_enabled
        self._running = False

        # Track what we've sent today to avoid duplicates
        self._last_evening_date: str | None = None
        self._last_morning_date: str | None = None
        self._last_health_check: datetime | None = None

    async def start(self) -> None:
        """Start the notification scheduler loop."""
        self._running = True
        logger.info(
            f"Notification scheduler started (evening: {self._evening_time}, "
            f"morning: {'enabled' if self._morning_enabled else 'disabled'})"
        )

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False

    async def check_and_send(self) -> None:
        """Check if any notifications should be sent now.

        Called periodically by the orchestrator (every 60 seconds).
        """
        if not self._running:
            return

        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        # Evening digest check
        if (
            now.time() >= self._evening_time
            and self._last_evening_date != today
        ):
            await self._send_evening_digest(now)
            self._last_evening_date = today

        # Morning briefing check
        if (
            self._morning_enabled
            and now.time() >= self._morning_time
            and now.time() < time(12, 0)  # Don't send after noon
            and self._last_morning_date != today
        ):
            await self._send_morning_briefing(now)
            self._last_morning_date = today

        # Health check — alert if no activity in 1 hour during work hours
        if now.hour >= 9 and now.hour <= 18:
            await self._check_daemon_health(now)

    async def _send_evening_digest(self, now: datetime) -> None:
        """Generate and send the evening digest notification."""
        try:
            digest = await self.digest_generator.generate(now)

            if digest.total_active_minutes < 5:
                logger.info("Skipping evening digest — minimal activity today")
                return

            send_notification(
                title=digest.notification_title,
                body=digest.notification_body,
                subtitle=digest.notification_subtitle,
                sound="Pop",
            )
            logger.info(
                f"Evening digest sent: {digest.total_hours_str} active, "
                f"{len(digest.top_apps)} apps"
            )
        except Exception as e:
            logger.error(f"Failed to generate evening digest: {e}")

    async def _send_morning_briefing(self, now: datetime) -> None:
        """Generate and send morning briefing with yesterday's summary."""
        try:
            yesterday = now - timedelta(days=1)
            digest = await self.digest_generator.generate(yesterday)

            if digest.total_active_minutes < 5:
                send_notification(
                    title="Good morning",
                    body="No activity tracked yesterday. Daemon may have been stopped.",
                    sound="default",
                )
                return

            send_notification(
                title=f"Yesterday: {digest.total_hours_str} active",
                body=digest.notification_body,
                subtitle=digest.notification_subtitle,
                sound="default",
            )
            logger.info("Morning briefing sent")
        except Exception as e:
            logger.error(f"Failed to generate morning briefing: {e}")

    async def _check_daemon_health(self, now: datetime) -> None:
        """Alert if no activity has been logged recently."""
        # Only check once per hour
        if self._last_health_check and (now - self._last_health_check).seconds < 3600:
            return

        self._last_health_check = now

        try:
            one_hour_ago = (now - timedelta(hours=1)).isoformat()
            row = await self.db.fetch_one(
                "SELECT COUNT(*) as cnt FROM activity_logs WHERE timestamp > ?",
                (one_hour_ago,),
            )

            if row and row["cnt"] == 0:
                send_notification(
                    title="Captain's Log",
                    body="No activity recorded in the last hour. Is tracking working?",
                    subtitle="Check: captains-log health",
                    sound="Ping",
                )
                logger.warning("Health alert: no activity in the last hour")
        except Exception as e:
            logger.error(f"Health check failed: {e}")
