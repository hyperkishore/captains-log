"""Window title extraction using macOS Accessibility API."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Browser bundle IDs for URL extraction
BROWSER_BUNDLES = {
    "com.apple.Safari",
    "com.google.Chrome",
    "org.chromium.Chromium",
    "org.mozilla.firefox",
    "company.thebrowser.Browser",  # Arc
    "com.microsoft.edgemac",
    "com.brave.Browser",
    "com.operasoftware.Opera",
    "com.vivaldi.Vivaldi",
}


class WindowTracker:
    """Extracts window titles and URLs using Accessibility API."""

    def __init__(self, daemon_mode: bool = False):
        self._accessibility_available = False
        self._daemon_mode = daemon_mode
        self._check_accessibility()

    def _check_accessibility(self) -> None:
        """Check if accessibility features are available."""
        try:
            # In daemon mode, skip the ApplicationServices check (it crashes)
            # Assume accessibility is available; it will fail gracefully if not
            if self._daemon_mode:
                logger.info("Running in daemon mode, assuming accessibility available")
                self._accessibility_available = True
                return

            from ApplicationServices import AXIsProcessTrusted

            self._accessibility_available = AXIsProcessTrusted()
            if not self._accessibility_available:
                logger.warning("Accessibility permission not granted - window titles unavailable")
        except ImportError:
            logger.warning("ApplicationServices not available")
            self._accessibility_available = False
        except Exception as e:
            logger.warning(f"Error checking accessibility: {e}")
            # Assume available in daemon mode
            self._accessibility_available = self._daemon_mode

    @property
    def is_available(self) -> bool:
        """Check if window tracking is available."""
        return self._accessibility_available

    def refresh_permission_status(self) -> bool:
        """Re-check accessibility permission status."""
        self._check_accessibility()
        return self._accessibility_available

    def get_window_title(self, pid: int) -> str | None:
        """Get the title of the focused window for a process.

        Args:
            pid: Process ID of the application

        Returns:
            Window title or None if not available
        """
        if not self._accessibility_available:
            return None

        try:
            import ctypes

            from Quartz import (
                AXUIElementCopyAttributeValue,
                AXUIElementCreateApplication,
                kAXFocusedWindowAttribute,
                kAXTitleAttribute,
            )

            # Create accessibility element for the application
            app_element = AXUIElementCreateApplication(pid)
            if app_element is None:
                return None

            # Get focused window
            window_ref = ctypes.c_void_p()
            result = AXUIElementCopyAttributeValue(
                app_element,
                kAXFocusedWindowAttribute,
                ctypes.byref(window_ref),
            )

            if result != 0:  # kAXErrorSuccess = 0
                return None

            if not window_ref.value:
                return None

            # Cast to AXUIElement
            window = ctypes.cast(window_ref, ctypes.py_object).value

            # Get window title
            title_ref = ctypes.c_void_p()
            result = AXUIElementCopyAttributeValue(
                window,
                kAXTitleAttribute,
                ctypes.byref(title_ref),
            )

            if result != 0:
                return None

            if title_ref.value:
                return ctypes.cast(title_ref, ctypes.py_object).value

            return None

        except Exception as e:
            logger.debug(f"Error getting window title for PID {pid}: {e}")
            return None

    def get_window_title_simple(self, pid: int) -> str | None:
        """Simpler approach using PyObjC directly."""
        if not self._accessibility_available:
            return None

        try:
            from Quartz import (
                CGWindowListCopyWindowInfo,
                kCGNullWindowID,
                kCGWindowListOptionOnScreenOnly,
            )

            # Get all windows
            window_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID,
            )

            if not window_list:
                return None

            # Find window for this PID
            for window in window_list:
                owner_pid = window.get("kCGWindowOwnerPID")
                if owner_pid == pid:
                    # Get window name (title)
                    name = window.get("kCGWindowName")
                    if name:
                        return name

            return None

        except Exception as e:
            logger.debug(f"Error getting window title (simple) for PID {pid}: {e}")
            return None

    def extract_url_from_title(self, bundle_id: str, title: str | None) -> str | None:
        """Extract URL or domain from browser window title.

        Different browsers format titles differently:
        - Chrome/Chromium: "Page Title - Domain"
        - Safari: "Page Title"
        - Firefox: "Page Title - Mozilla Firefox" or "Page Title — Mozilla Firefox"

        Args:
            bundle_id: Application bundle identifier
            title: Window title

        Returns:
            URL/domain or None
        """
        if not title or bundle_id not in BROWSER_BUNDLES:
            return None

        # Chrome/Chromium-based browsers: "Page Title - domain.com"
        if bundle_id in {
            "com.google.Chrome",
            "org.chromium.Chromium",
            "company.thebrowser.Browser",
            "com.microsoft.edgemac",
            "com.brave.Browser",
            "com.operasoftware.Opera",
            "com.vivaldi.Vivaldi",
        }:
            # Extract the last part after " - "
            parts = title.rsplit(" - ", 1)
            if len(parts) == 2:
                domain = parts[1].strip()
                # Validate it looks like a domain
                if self._looks_like_domain(domain):
                    return domain

        # Firefox: "Page Title - Mozilla Firefox" or "Page Title — Mozilla Firefox"
        elif bundle_id == "org.mozilla.firefox":
            # Remove the Firefox suffix
            for suffix in [" - Mozilla Firefox", " — Mozilla Firefox"]:
                if title.endswith(suffix):
                    title = title[: -len(suffix)]
                    break

            # Try to extract domain from remaining title
            parts = title.rsplit(" - ", 1)
            if len(parts) == 2:
                domain = parts[1].strip()
                if self._looks_like_domain(domain):
                    return domain

        # Safari: Title only, but sometimes includes domain in tab
        # We can't reliably extract URL from Safari title
        elif bundle_id == "com.apple.Safari":
            # Safari's title is just the page title
            # We'd need to use accessibility to get the address bar
            pass

        return None

    def _looks_like_domain(self, text: str) -> bool:
        """Check if text looks like a domain name."""
        # Simple heuristic: contains dot, no spaces, reasonable length
        if " " in text or len(text) > 100 or len(text) < 3:
            return False

        # Check for domain-like pattern
        domain_pattern = r"^[a-zA-Z0-9][-a-zA-Z0-9]*(\.[a-zA-Z0-9][-a-zA-Z0-9]*)+$"
        return bool(re.match(domain_pattern, text))

    def get_chrome_url(self) -> str | None:
        """Get URL from Chrome's active tab using AppleScript."""
        try:
            import subprocess

            script = '''
            tell application "Google Chrome"
                if (count of windows) > 0 then
                    return URL of active tab of front window
                end if
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        except Exception as e:
            logger.debug(f"Error getting Chrome URL: {e}")
            return None

    def get_arc_url(self) -> str | None:
        """Get URL from Arc browser's active tab using AppleScript."""
        try:
            import subprocess

            script = '''
            tell application "Arc"
                if (count of windows) > 0 then
                    return URL of active tab of front window
                end if
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        except Exception as e:
            logger.debug(f"Error getting Arc URL: {e}")
            return None

    def get_browser_url(self, bundle_id: str, pid: int) -> str | None:
        """Get URL from browser using the best available method."""
        if bundle_id == "com.google.Chrome":
            return self.get_chrome_url()
        elif bundle_id == "company.thebrowser.Browser":  # Arc
            return self.get_arc_url()
        elif bundle_id == "com.apple.Safari":
            return self.get_safari_url(pid)
        return None

    def get_safari_url(self, pid: int) -> str | None:
        """Get URL from Safari using accessibility AXDocument attribute.

        Safari exposes the URL through a special accessibility attribute.
        """
        if not self._accessibility_available:
            return None

        try:
            import ctypes

            from Quartz import (
                AXUIElementCopyAttributeValue,
                AXUIElementCreateApplication,
                kAXFocusedWindowAttribute,
            )

            app_element = AXUIElementCreateApplication(pid)
            if app_element is None:
                return None

            # Get focused window
            window_ref = ctypes.c_void_p()
            result = AXUIElementCopyAttributeValue(
                app_element,
                kAXFocusedWindowAttribute,
                ctypes.byref(window_ref),
            )

            if result != 0 or not window_ref.value:
                return None

            window = ctypes.cast(window_ref, ctypes.py_object).value

            # Try to get AXDocument (URL) attribute
            url_ref = ctypes.c_void_p()
            result = AXUIElementCopyAttributeValue(
                window,
                "AXDocument",  # Safari-specific attribute
                ctypes.byref(url_ref),
            )

            if result == 0 and url_ref.value:
                return ctypes.cast(url_ref, ctypes.py_object).value

            return None

        except Exception as e:
            logger.debug(f"Error getting Safari URL: {e}")
            return None

    def is_fullscreen(self, pid: int) -> bool:
        """Check if the application window is in fullscreen mode."""
        try:
            from AppKit import NSScreen
            from Quartz import (
                CGWindowListCopyWindowInfo,
                kCGNullWindowID,
                kCGWindowListOptionOnScreenOnly,
            )

            window_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID,
            )

            if not window_list:
                return False

            # Get main screen size
            main_screen = NSScreen.mainScreen()
            if not main_screen:
                return False

            screen_frame = main_screen.frame()
            screen_width = screen_frame.size.width
            screen_height = screen_frame.size.height

            for window in window_list:
                owner_pid = window.get("kCGWindowOwnerPID")
                if owner_pid == pid:
                    bounds = window.get("kCGWindowBounds", {})
                    width = bounds.get("Width", 0)
                    height = bounds.get("Height", 0)

                    # Check if window fills screen
                    if width >= screen_width and height >= screen_height:
                        return True

            return False

        except Exception as e:
            logger.debug(f"Error checking fullscreen: {e}")
            return False
