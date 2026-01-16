"""Screenshot capture using CoreGraphics API.

Captures periodic screenshots with privacy filtering and WebP compression.
"""

from __future__ import annotations

import asyncio
import io
import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class ScreenshotInfo:
    """Metadata for a captured screenshot."""

    timestamp: datetime
    file_path: Path
    file_size_bytes: int
    width: int
    height: int
    expires_at: datetime
    capture_duration_ms: float = 0.0
    current_app_bundle_id: str | None = None


class ScreenshotCapture:
    """Periodic screenshot capture with privacy filtering.

    Uses CoreGraphics CGDisplayCreateImage for synchronous, reliable capture.
    Follows the tracker lifecycle pattern: start() -> running -> stop()
    """

    MIN_FREE_SPACE_MB = 100  # Skip capture if less than 100MB free

    def __init__(
        self,
        screenshots_dir: Path,
        interval_minutes: int = 5,
        quality: int = 80,
        max_width: int = 1280,
        retention_days: int = 7,
        excluded_apps: list[str] | None = None,
    ):
        """Initialize screenshot capture.

        Args:
            screenshots_dir: Base directory for screenshot storage
            interval_minutes: Time between captures (1-60)
            quality: WebP quality (1-100)
            max_width: Maximum width for Retina downscaling
            retention_days: Days before auto-deletion
            excluded_apps: Bundle IDs to skip capture for (e.g., password managers)
        """
        self._screenshots_dir = screenshots_dir
        self._interval_seconds = interval_minutes * 60
        self._quality = quality
        self._max_width = max_width
        self._retention_days = retention_days
        self._excluded_apps = set(excluded_apps or [])

        self._running = False
        self._capture_task: asyncio.Task | None = None
        self._on_capture: Callable[[ScreenshotInfo], None] | None = None
        self._get_current_app: Callable[[], str | None] | None = None

        # Track permission state
        self._permission_available: bool | None = None

    @property
    def is_running(self) -> bool:
        """Check if capture is running."""
        return self._running

    @property
    def is_available(self) -> bool:
        """Check if screen recording permission is available."""
        if self._permission_available is None:
            self._permission_available = self._check_permission()
        return self._permission_available

    def set_current_app_callback(self, callback: Callable[[], str | None]) -> None:
        """Set callback to get current app bundle_id for filtering."""
        self._get_current_app = callback

    async def start(
        self,
        on_capture: Callable[[ScreenshotInfo], None] | None = None,
    ) -> bool:
        """Start periodic screenshot capture.

        Args:
            on_capture: Callback invoked after each successful capture

        Returns:
            True if started successfully, False if permission denied
        """
        if self._running:
            logger.warning("Screenshot capture already running")
            return True

        # Check permission first
        if not self.is_available:
            logger.warning(
                "Screen Recording permission not granted - screenshots disabled"
            )
            return False

        # Ensure screenshots directory exists
        self._screenshots_dir.mkdir(parents=True, exist_ok=True)

        self._on_capture = on_capture
        self._running = True
        self._capture_task = asyncio.create_task(self._periodic_capture())

        logger.info(
            f"Screenshot capture started (interval: {self._interval_seconds}s, "
            f"quality: {self._quality}, max_width: {self._max_width})"
        )
        return True

    async def stop(self) -> None:
        """Stop screenshot capture and cleanup."""
        if not self._running:
            return

        self._running = False

        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
            self._capture_task = None

        logger.info("Screenshot capture stopped")

    def capture_sync(self) -> ScreenshotInfo | None:
        """Capture a screenshot synchronously.

        This method is safe to call from sync callbacks.

        Returns:
            ScreenshotInfo if successful, None if skipped or failed
        """
        # Check if we should skip
        should_skip, reason = self._should_skip_capture()
        if should_skip:
            logger.info(f"Skipping screenshot capture: {reason}")
            return None

        # Get current app bundle_id
        current_bundle_id = None
        if self._get_current_app:
            current_bundle_id = self._get_current_app()

        # Capture - use UTC for consistent timestamps with activity logs
        start_time = datetime.utcnow()
        timestamp = start_time

        try:
            # Capture screen as raw image data
            raw_data = self._capture_screen()
            if raw_data is None:
                logger.warning("Screen capture returned None - permission may be revoked")
                self._permission_available = False
                return None

            # Process image (downscale + compress to WebP)
            webp_data, width, height = self._process_image(raw_data)

            # Generate storage path
            file_path = self._get_storage_path(timestamp)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to disk
            file_path.write_bytes(webp_data)
            file_size = len(webp_data)

            # Calculate expiration
            expires_at = timestamp + timedelta(days=self._retention_days)

            # Calculate duration
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            info = ScreenshotInfo(
                timestamp=timestamp,
                file_path=file_path,
                file_size_bytes=file_size,
                width=width,
                height=height,
                expires_at=expires_at,
                capture_duration_ms=duration_ms,
                current_app_bundle_id=current_bundle_id,
            )

            logger.debug(
                f"Screenshot captured: {file_path.name} "
                f"({width}x{height}, {file_size / 1024:.1f}KB, {duration_ms:.0f}ms)"
            )

            return info

        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            return None

    async def capture_now(self) -> ScreenshotInfo | None:
        """Capture a screenshot immediately (async wrapper).

        Returns:
            ScreenshotInfo if successful, None if skipped or failed
        """
        return self.capture_sync()

    def _check_permission(self) -> bool:
        """Check if Screen Recording permission is granted.

        Uses a 1x1 pixel capture test since there's no direct API.
        """
        try:
            import Quartz

            # Try to capture a tiny area
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
            return False

    def _should_skip_capture(self) -> tuple[bool, str]:
        """Check if capture should be skipped.

        Returns:
            (should_skip, reason) tuple
        """
        # Check if current app is excluded
        if self._get_current_app:
            current_bundle_id = self._get_current_app()
            if current_bundle_id and current_bundle_id in self._excluded_apps:
                return True, f"Excluded app active: {current_bundle_id}"

        # Check disk space
        try:
            usage = shutil.disk_usage(self._screenshots_dir)
            free_mb = usage.free / (1024 * 1024)
            if free_mb < self.MIN_FREE_SPACE_MB:
                return True, f"Low disk space: {free_mb:.0f}MB free"
        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")

        return False, ""

    def _capture_screen(self) -> bytes | None:
        """Capture screen using CoreGraphics.

        Uses CGDisplayCreateImage(CGMainDisplayID()) for reliable capture.
        Returns raw PNG image data or None on failure.
        """
        try:
            import objc
            import Quartz
            from Foundation import NSMutableData

            with objc.autorelease_pool():
                # Get the main display
                main_display = Quartz.CGMainDisplayID()

                # Capture the display
                image = Quartz.CGDisplayCreateImage(main_display)

                if image is None:
                    logger.warning("CGDisplayCreateImage returned None")
                    return None

                # Convert CGImage to PNG data
                data = NSMutableData.alloc().init()

                # Create a destination for PNG format
                dest = Quartz.CGImageDestinationCreateWithData(
                    data, "public.png", 1, None
                )

                if dest is None:
                    logger.error("Failed to create image destination")
                    return None

                # Add the image
                Quartz.CGImageDestinationAddImage(dest, image, None)

                # Finalize
                if not Quartz.CGImageDestinationFinalize(dest):
                    logger.error("Failed to finalize image")
                    return None

                return bytes(data)

        except Exception as e:
            logger.error(f"Error capturing screen: {e}")
            return None

    def _process_image(
        self,
        image_data: bytes,
    ) -> tuple[bytes, int, int]:
        """Downscale and compress image to WebP.

        Args:
            image_data: Raw PNG image bytes

        Returns:
            (webp_bytes, width, height)
        """
        from PIL import Image

        # Open the image
        with Image.open(io.BytesIO(image_data)) as img:
            orig_width, orig_height = img.size

            # Downscale if wider than max_width (handles Retina 2x/3x)
            if orig_width > self._max_width:
                ratio = self._max_width / orig_width
                new_height = int(orig_height * ratio)
                img = img.resize((self._max_width, new_height), Image.LANCZOS)

            # Convert to RGB if necessary (WebP doesn't support all modes)
            if img.mode in ("RGBA", "P"):
                # Create white background for transparency
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[3] if len(img.split()) == 4 else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Compress to WebP
            output = io.BytesIO()
            img.save(output, format="WebP", quality=self._quality, method=4)
            webp_bytes = output.getvalue()

            return webp_bytes, img.width, img.height

    def _get_storage_path(self, timestamp: datetime) -> Path:
        """Generate storage path: screenshots/YYYY-MM-DD/HH-MM-SS.webp"""
        date_dir = timestamp.strftime("%Y-%m-%d")
        filename = timestamp.strftime("%H-%M-%S.webp")
        return self._screenshots_dir / date_dir / filename

    async def _periodic_capture(self) -> None:
        """Background task for periodic captures."""
        # Initial capture on start
        await asyncio.sleep(1)  # Brief delay to let system settle

        while self._running:
            try:
                # Capture
                info = await self.capture_now()

                # Invoke callback if capture succeeded
                if info and self._on_capture:
                    try:
                        # Handle both sync and async callbacks
                        result = self._on_capture(info)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Error in capture callback: {e}")

                # Wait for next interval
                await asyncio.sleep(self._interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic capture: {e}")
                # Continue despite errors
                await asyncio.sleep(self._interval_seconds)

    def add_excluded_app(self, bundle_id: str) -> None:
        """Add an app to the exclusion list."""
        self._excluded_apps.add(bundle_id)

    def remove_excluded_app(self, bundle_id: str) -> None:
        """Remove an app from the exclusion list."""
        self._excluded_apps.discard(bundle_id)

    @property
    def excluded_apps(self) -> set[str]:
        """Get the current exclusion list."""
        return self._excluded_apps.copy()
