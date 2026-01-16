"""macOS permission checks and requests for Accessibility and Screen Recording."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from captains_log.storage.database import Database

logger = logging.getLogger(__name__)


class PermissionType(str, Enum):
    """Types of macOS permissions needed."""

    ACCESSIBILITY = "accessibility"
    SCREEN_RECORDING = "screen_recording"


class PermissionStatus(str, Enum):
    """Permission status."""

    GRANTED = "granted"
    DENIED = "denied"
    UNKNOWN = "unknown"


@dataclass
class PermissionState:
    """State tracking for a permission."""

    status: PermissionStatus
    ask_count: int = 0
    last_asked: datetime | None = None
    denied_at: datetime | None = None


class PermissionManager:
    """Manages macOS permission checks and requests."""

    # Don't re-ask within this many days after denial
    DENIAL_COOLDOWN_DAYS = 7
    # Maximum times to ask for a permission
    MAX_ASK_COUNT = 3

    def __init__(self, db: Database | None = None, daemon_mode: bool = False):
        self._db = db
        self._daemon_mode = daemon_mode  # Skip GUI-dependent checks in daemon mode
        self._state_cache: dict[PermissionType, PermissionState] = {}

    @property
    def has_accessibility(self) -> bool:
        """Check if accessibility permission is granted."""
        return self.check_accessibility()

    @property
    def has_screen_recording(self) -> bool:
        """Check if screen recording permission is granted."""
        return self.check_screen_recording()

    async def load_state(self) -> None:
        """Load permission state from database."""
        if self._db is None:
            return

        for perm_type in PermissionType:
            state_json = await self._db.get_config(f"permission_{perm_type.value}")
            if state_json:
                # Parse stored state
                import json
                data = json.loads(state_json)
                self._state_cache[perm_type] = PermissionState(
                    status=PermissionStatus(data.get("status", "unknown")),
                    ask_count=data.get("ask_count", 0),
                    last_asked=datetime.fromisoformat(data["last_asked"])
                    if data.get("last_asked") else None,
                    denied_at=datetime.fromisoformat(data["denied_at"])
                    if data.get("denied_at") else None,
                )
            else:
                self._state_cache[perm_type] = PermissionState(
                    status=PermissionStatus.UNKNOWN
                )

    async def save_state(self, perm_type: PermissionType) -> None:
        """Save permission state to database."""
        if self._db is None:
            return

        state = self._state_cache.get(perm_type)
        if state is None:
            return

        import json
        data = {
            "status": state.status.value,
            "ask_count": state.ask_count,
            "last_asked": state.last_asked.isoformat() if state.last_asked else None,
            "denied_at": state.denied_at.isoformat() if state.denied_at else None,
        }
        await self._db.set_config(f"permission_{perm_type.value}", json.dumps(data))

    def check_accessibility(self) -> bool:
        """Check if Accessibility permission is granted.

        Uses AXIsProcessTrusted() which is the official API.
        Note: This can fail in daemon mode without WindowServer connection.
        """
        try:
            # Skip GUI-dependent checks in daemon mode
            if self._daemon_mode:
                logger.info("Running in daemon mode, assuming accessibility granted")
                return True

            from ApplicationServices import AXIsProcessTrusted
            return AXIsProcessTrusted()
        except ImportError:
            logger.warning("Could not import ApplicationServices, assuming no permission")
            return False
        except Exception as e:
            logger.error(f"Error checking accessibility permission: {e}")
            return True

    def check_screen_recording(self) -> bool:
        """Check if Screen Recording permission is granted.

        There's no direct API for this. We try to capture a tiny area
        and see if it succeeds.
        Note: This can fail in daemon mode without WindowServer connection.
        """
        try:
            # Skip GUI-dependent checks in daemon mode
            if self._daemon_mode:
                logger.info("Running in daemon mode, assuming screen recording granted")
                return True

            import Quartz

            # Try to capture a 1x1 pixel region
            rect = Quartz.CGRectMake(0, 0, 1, 1)
            image = Quartz.CGWindowListCreateImage(
                rect,
                Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
                Quartz.kCGWindowImageDefault,
            )

            # If we got a valid image, we have permission
            if image is not None:
                width = Quartz.CGImageGetWidth(image)
                return width > 0

            return False
        except Exception as e:
            logger.error(f"Error checking screen recording permission: {e}")
            return True

    def check(self, perm_type: PermissionType) -> bool:
        """Check a specific permission."""
        if perm_type == PermissionType.ACCESSIBILITY:
            return self.check_accessibility()
        elif perm_type == PermissionType.SCREEN_RECORDING:
            return self.check_screen_recording()
        return False

    def check_all(self) -> dict[PermissionType, bool]:
        """Check all permissions."""
        return {
            perm_type: self.check(perm_type)
            for perm_type in PermissionType
        }

    async def verify_all(self) -> dict[PermissionType, bool]:
        """Verify all permissions and update state cache."""
        results = self.check_all()

        for perm_type, granted in results.items():
            if perm_type not in self._state_cache:
                self._state_cache[perm_type] = PermissionState(
                    status=PermissionStatus.UNKNOWN
                )

            state = self._state_cache[perm_type]
            new_status = PermissionStatus.GRANTED if granted else PermissionStatus.DENIED

            if state.status != new_status:
                state.status = new_status
                await self.save_state(perm_type)
                logger.info(f"{perm_type.value} permission: {new_status.value}")

        return results

    def should_request(self, perm_type: PermissionType) -> bool:
        """Determine if we should request this permission.

        Returns False if:
        - Already granted
        - Already asked MAX_ASK_COUNT times
        - Denied within DENIAL_COOLDOWN_DAYS
        """
        # First check if currently granted
        if self.check(perm_type):
            return False

        state = self._state_cache.get(perm_type)
        if state is None:
            return True

        # Don't ask if we've reached max count
        if state.ask_count >= self.MAX_ASK_COUNT:
            logger.debug(f"{perm_type.value}: max ask count reached")
            return False

        # Don't ask if recently denied
        if state.denied_at:
            days_since = (datetime.now() - state.denied_at).days
            if days_since < self.DENIAL_COOLDOWN_DAYS:
                logger.debug(
                    f"{perm_type.value}: denied {days_since} days ago, cooling down"
                )
                return False

        return True

    @staticmethod
    def open_accessibility_settings() -> None:
        """Open System Preferences to Accessibility pane."""
        subprocess.run([
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        ])

    @staticmethod
    def open_screen_recording_settings() -> None:
        """Open System Preferences to Screen Recording pane."""
        subprocess.run([
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
        ])

    def open_settings(self, perm_type: PermissionType) -> None:
        """Open System Preferences to the appropriate pane."""
        if perm_type == PermissionType.ACCESSIBILITY:
            self.open_accessibility_settings()
        elif perm_type == PermissionType.SCREEN_RECORDING:
            self.open_screen_recording_settings()

    async def request_permission(self, perm_type: PermissionType) -> bool:
        """Request a permission from the user.

        This opens System Preferences to the appropriate pane.
        Returns True if the permission is now granted.
        """
        if not self.should_request(perm_type):
            return self.check(perm_type)

        # Update state
        state = self._state_cache.get(perm_type)
        if state is None:
            state = PermissionState(status=PermissionStatus.UNKNOWN)
            self._state_cache[perm_type] = state

        state.ask_count += 1
        state.last_asked = datetime.now()

        # Open settings
        self.open_settings(perm_type)
        logger.info(
            f"Opened settings for {perm_type.value} "
            f"(ask count: {state.ask_count}/{self.MAX_ASK_COUNT})"
        )

        # Check if granted now (user might have already enabled it)
        is_granted = self.check(perm_type)
        if not is_granted:
            state.denied_at = datetime.now()
            state.status = PermissionStatus.DENIED
        else:
            state.status = PermissionStatus.GRANTED
            state.denied_at = None

        await self.save_state(perm_type)
        return is_granted

    def get_missing_permissions(self) -> list[PermissionType]:
        """Get list of permissions that are not granted."""
        return [
            perm_type
            for perm_type in PermissionType
            if not self.check(perm_type)
        ]

    @staticmethod
    def prompt_for_accessibility_with_dialog() -> bool:
        """Prompt for accessibility using system dialog.

        This triggers the system's accessibility prompt if the app
        hasn't been authorized yet.
        """
        try:
            from ApplicationServices import AXIsProcessTrustedWithOptions
            from Foundation import NSDictionary

            # Setting kAXTrustedCheckOptionPrompt triggers the system dialog
            options = NSDictionary.dictionaryWithObject_forKey_(
                True, "AXTrustedCheckOptionPrompt"
            )
            return AXIsProcessTrustedWithOptions(options)
        except ImportError:
            logger.warning("Could not import ApplicationServices")
            return False
        except Exception as e:
            logger.error(f"Error prompting for accessibility: {e}")
            return False
