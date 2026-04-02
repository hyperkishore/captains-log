"""macOS notification sender using osascript."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


def send_notification(
    title: str,
    body: str,
    subtitle: str = "",
    sound: str = "default",
) -> bool:
    """Send a macOS notification via osascript.

    Args:
        title: Notification title
        body: Notification body text
        subtitle: Optional subtitle
        sound: Sound name ("default", "Ping", "Pop", etc.) or empty for silent

    Returns:
        True if notification was sent successfully
    """
    # Escape quotes for AppleScript
    title = title.replace('"', '\\"')
    body = body.replace('"', '\\"')
    subtitle = subtitle.replace('"', '\\"')

    script_parts = [f'display notification "{body}" with title "{title}"']

    if subtitle:
        script_parts[0] += f' subtitle "{subtitle}"'

    if sound:
        script_parts[0] += f' sound name "{sound}"'

    script = script_parts[0]

    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        logger.debug(f"Notification sent: {title}")
        return True
    except subprocess.TimeoutExpired:
        logger.warning("Notification timed out")
        return False
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False
