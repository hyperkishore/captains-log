"""Cloud sync module for pushing data to Railway cloud API."""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Any

import aiohttp
import aiosqlite

from captains_log.core.config import Config

logger = logging.getLogger(__name__)


class CloudSync:
    """Handles syncing local data to cloud API."""

    def __init__(self, config: Config):
        self.config = config
        self.device_id = config.device_id
        self.api_url = config.sync.cloud_api_url.rstrip("/")
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_sync: datetime | None = None

    async def start(self) -> None:
        """Start periodic sync."""
        if not self.config.sync.enabled:
            logger.info("Cloud sync is disabled")
            return

        self._running = True
        logger.info(f"Starting cloud sync to {self.api_url}")
        logger.info(f"Device ID: {self.device_id}")

        # Register device
        await self._register_device()

        # Start sync loop
        self._task = asyncio.create_task(self._sync_loop())

    async def stop(self) -> None:
        """Stop periodic sync."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Cloud sync stopped")

    async def _sync_loop(self) -> None:
        """Main sync loop."""
        interval = self.config.sync.sync_interval_minutes * 60
        while self._running:
            try:
                await self.sync_now()
            except Exception as e:
                logger.error(f"Sync error: {e}")
            await asyncio.sleep(interval)

    async def sync_now(self) -> dict[str, Any]:
        """Perform immediate sync."""
        results = {"synced": [], "errors": []}
        today = date.today().isoformat()

        try:
            async with aiohttp.ClientSession() as session:
                # Sync daily stats
                if self.config.sync.sync_stats:
                    try:
                        await self._sync_daily_stats(session, today)
                        results["synced"].append("daily_stats")
                    except Exception as e:
                        logger.error(f"Failed to sync daily stats: {e}")
                        results["errors"].append(f"daily_stats: {e}")

                # Sync summaries
                if self.config.sync.sync_summaries:
                    try:
                        count = await self._sync_summaries(session)
                        if count > 0:
                            results["synced"].append(f"summaries ({count})")
                    except Exception as e:
                        logger.error(f"Failed to sync summaries: {e}")
                        results["errors"].append(f"summaries: {e}")

                # Sync activities (optional, more data)
                if self.config.sync.sync_activities:
                    try:
                        count = await self._sync_activities(session)
                        if count > 0:
                            results["synced"].append(f"activities ({count})")
                    except Exception as e:
                        logger.error(f"Failed to sync activities: {e}")
                        results["errors"].append(f"activities: {e}")

            self._last_sync = datetime.utcnow()
            logger.info(f"Sync completed: {results['synced']}")

        except aiohttp.ClientError as e:
            logger.error(f"Network error during sync: {e}")
            results["errors"].append(f"network: {e}")

        return results

    async def _register_device(self) -> None:
        """Register device with cloud API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/api/devices/register",
                    json={"device_id": self.device_id, "name": None},
                ) as resp:
                    if resp.status == 200:
                        logger.info("Device registered with cloud")
                    else:
                        logger.warning(f"Device registration failed: {resp.status}")
        except Exception as e:
            logger.error(f"Failed to register device: {e}")

    async def _sync_daily_stats(self, session: aiohttp.ClientSession, date_str: str) -> None:
        """Sync daily stats to cloud."""
        async with aiosqlite.connect(self.config.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Get total events and unique apps
            async with db.execute(
                """
                SELECT COUNT(*) as total, COUNT(DISTINCT app_name) as unique_apps
                FROM activity_logs
                WHERE date(timestamp) = ?
                """,
                (date_str,),
            ) as cursor:
                row = await cursor.fetchone()
                total_events = row["total"] if row else 0
                unique_apps = row["unique_apps"] if row else 0

            # Get top apps
            top_apps = []
            async with db.execute(
                """
                SELECT app_name, COUNT(*) as count
                FROM activity_logs
                WHERE date(timestamp) = ?
                GROUP BY app_name
                ORDER BY count DESC
                LIMIT 10
                """,
                (date_str,),
            ) as cursor:
                async for row in cursor:
                    top_apps.append({"app_name": row["app_name"], "count": row["count"]})

            # Get hourly breakdown
            hourly_breakdown = []
            async with db.execute(
                """
                SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
                FROM activity_logs
                WHERE date(timestamp) = ?
                GROUP BY hour
                ORDER BY hour
                """,
                (date_str,),
            ) as cursor:
                async for row in cursor:
                    hour_int = int(row["hour"])
                    hour_label = f"{hour_int % 12 or 12} {'AM' if hour_int < 12 else 'PM'}"
                    hourly_breakdown.append({"hour": hour_label, "count": row["count"]})

            # Get time blocks with categories
            time_blocks = await self._get_time_blocks(db, date_str)

            # Get category breakdown
            categories = {}
            for block in time_blocks:
                for cat, count in block.get("categories", {}).items():
                    categories[cat] = categories.get(cat, 0) + count

        # Push to cloud
        payload = {
            "device_id": self.device_id,
            "date": date_str,
            "total_events": total_events,
            "unique_apps": unique_apps,
            "top_apps": top_apps,
            "hourly_breakdown": hourly_breakdown,
            "time_blocks": time_blocks,
            "categories": categories,
        }

        async with session.post(
            f"{self.api_url}/api/sync/daily-stats",
            json=payload,
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Failed to sync daily stats: {resp.status} - {text}")

    async def _get_time_blocks(self, db: aiosqlite.Connection, date_str: str) -> list[dict]:
        """Get time blocks with categories for a date."""
        # App to category mapping (simplified)
        category_map = {
            "com.microsoft.VSCode": "Development",
            "com.apple.Terminal": "Development",
            "com.googlecode.iterm2": "Development",
            "com.github.atom": "Development",
            "com.jetbrains": "Development",
            "com.google.Chrome": "Browsing",
            "com.apple.Safari": "Browsing",
            "org.mozilla.firefox": "Browsing",
            "com.tinyspeck.slackmacgap": "Communication",
            "com.apple.mail": "Communication",
            "us.zoom.xos": "Meeting",
            "com.figma.Desktop": "Design",
            "com.adobe": "Design",
        }

        def get_category(bundle_id: str | None, app_name: str) -> str:
            if not bundle_id:
                return "Other"
            for prefix, cat in category_map.items():
                if bundle_id.startswith(prefix) or prefix in bundle_id.lower():
                    return cat
            if "code" in app_name.lower() or "terminal" in app_name.lower():
                return "Development"
            if "slack" in app_name.lower() or "mail" in app_name.lower():
                return "Communication"
            if "chrome" in app_name.lower() or "safari" in app_name.lower():
                return "Browsing"
            return "Other"

        time_blocks = []
        async with db.execute(
            """
            SELECT strftime('%H', timestamp) as hour, app_name, bundle_id, COUNT(*) as count
            FROM activity_logs
            WHERE date(timestamp) = ?
            GROUP BY hour, app_name
            ORDER BY hour
            """,
            (date_str,),
        ) as cursor:
            hourly_data: dict[int, dict] = {}
            async for row in cursor:
                hour = int(row["hour"])
                if hour not in hourly_data:
                    hourly_data[hour] = {"categories": {}, "total": 0}

                category = get_category(row["bundle_id"], row["app_name"])
                hourly_data[hour]["categories"][category] = (
                    hourly_data[hour]["categories"].get(category, 0) + row["count"]
                )
                hourly_data[hour]["total"] += row["count"]

            for hour, data in sorted(hourly_data.items()):
                hour_label = f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}"
                primary = max(data["categories"].items(), key=lambda x: x[1])[0] if data["categories"] else "Other"
                time_blocks.append({
                    "hour": hour,
                    "hour_label": hour_label,
                    "categories": data["categories"],
                    "total": data["total"],
                    "primary_category": primary,
                })

        return time_blocks

    async def _sync_summaries(self, session: aiohttp.ClientSession) -> int:
        """Sync AI summaries to cloud."""
        async with aiosqlite.connect(self.config.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Get summaries from last 24 hours that haven't been synced
            async with db.execute(
                """
                SELECT * FROM summaries
                WHERE period_start > datetime('now', '-1 day')
                ORDER BY period_start DESC
                LIMIT 100
                """,
            ) as cursor:
                summaries = []
                async for row in cursor:
                    summaries.append({
                        "period_start": row["period_start"],
                        "period_end": row["period_end"],
                        "primary_app": row["primary_app"],
                        "activity_type": row["activity_type"],
                        "focus_score": row["focus_score"],
                        "key_activities": row["key_activities"],
                        "context": row["context"],
                        "context_switches": row["context_switches"],
                    })

        if not summaries:
            return 0

        # Push to cloud
        async with session.post(
            f"{self.api_url}/api/sync/summaries",
            json={"device_id": self.device_id, "summaries": summaries},
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Failed to sync summaries: {resp.status} - {text}")

        return len(summaries)

    async def _sync_activities(self, session: aiohttp.ClientSession) -> int:
        """Sync raw activities to cloud (optional, more data)."""
        # Get activities from last sync or last hour
        since = self._last_sync or (datetime.utcnow() - timedelta(hours=1))

        async with aiosqlite.connect(self.config.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                """
                SELECT * FROM activity_logs
                WHERE timestamp > ?
                ORDER BY timestamp
                LIMIT 1000
                """,
                (since.isoformat(),),
            ) as cursor:
                activities = []
                async for row in cursor:
                    activities.append({
                        "timestamp": row["timestamp"],
                        "app_name": row["app_name"],
                        "bundle_id": row["bundle_id"],
                        "window_title": row["window_title"],
                        "url": row["url"],
                        "idle_seconds": row["idle_seconds"],
                        "idle_status": row["idle_status"],
                        "work_category": row.get("work_category"),
                    })

        if not activities:
            return 0

        # Push to cloud
        async with session.post(
            f"{self.api_url}/api/sync/activities",
            json={"device_id": self.device_id, "activities": activities},
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Failed to sync activities: {resp.status} - {text}")

        return len(activities)

    @property
    def status(self) -> dict[str, Any]:
        """Get sync status."""
        return {
            "enabled": self.config.sync.enabled,
            "device_id": self.device_id,
            "api_url": self.api_url,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "running": self._running,
        }
