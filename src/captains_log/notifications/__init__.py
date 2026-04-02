"""Notification system for Captain's Log.

Sends macOS notifications for daily digests, weekly summaries,
and daemon health alerts.
"""

from captains_log.notifications.daily_digest import DailyDigestGenerator
from captains_log.notifications.notifier import send_notification

__all__ = ["DailyDigestGenerator", "send_notification"]
