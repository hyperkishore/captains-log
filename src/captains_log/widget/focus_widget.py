"""Floating focus widget using PyObjC for macOS.

Creates a persistent overlay window showing:
- Pomodoro timer with countdown
- Goal progress bar
- Current activity status
- Quick action buttons
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any

logger = logging.getLogger(__name__)

# Try to import PyObjC components
try:
    from AppKit import (
        NSApplication,
        NSWindow,
        NSPanel,
        NSView,
        NSColor,
        NSFont,
        NSTextField,
        NSButton,
        NSProgressIndicator,
        NSWindowStyleMaskBorderless,
        NSWindowStyleMaskNonactivatingPanel,
        NSFloatingWindowLevel,
        NSBackingStoreBuffered,
        NSViewWidthSizable,
        NSViewHeightSizable,
        NSTextAlignmentCenter,
        NSTextAlignmentLeft,
        NSLayoutConstraint,
        NSStackView,
        NSUserInterfaceLayoutOrientationVertical,
        NSUserInterfaceLayoutOrientationHorizontal,
        NSBezelStyleRounded,
        NSProgressIndicatorStyleBar,
    )
    from Foundation import NSRect, NSPoint, NSSize, NSMakeRect, NSTimer, NSRunLoop, NSDefaultRunLoopMode
    from Cocoa import NSScreen
    from objc import super as objc_super
    PYOBJC_AVAILABLE = True
except ImportError:
    PYOBJC_AVAILABLE = False
    logger.warning("PyObjC not available - focus widget will be disabled")


class WidgetMode(Enum):
    """Display mode for the widget."""
    FULL = "full"       # Full display with all details
    COMPACT = "compact" # Minimal display


@dataclass
class WidgetState:
    """Current state of the focus widget."""
    # Timer state
    timer_running: bool = False
    timer_phase: str = "work"  # work, short_break, long_break
    time_remaining: str = "25:00"
    pomodoros_today: int = 0

    # Goal state
    goal_name: str = ""
    goal_progress_percent: float = 0.0
    goal_progress_text: str = "0m / 2h"
    goal_completed: bool = False

    # Activity state
    current_app: str = ""
    is_on_goal: bool = True
    off_goal_reason: str = ""

    # Streak
    streak_days: int = 0

    # Widget state
    mode: WidgetMode = WidgetMode.FULL
    visible: bool = True


if PYOBJC_AVAILABLE:
    class FocusWidgetView(NSView):
        """Custom NSView for the focus widget content."""

        def initWithFrame_(self, frame):
            self = objc_super(FocusWidgetView, self).initWithFrame_(frame)
            if self is None:
                return None

            self._state = WidgetState()
            self._callbacks = {}
            self._setup_ui()
            return self

        def _setup_ui(self):
            """Set up the widget UI components."""
            # Background
            self.setWantsLayer_(True)
            self.layer().setBackgroundColor_(NSColor.colorWithCalibratedWhite_alpha_(0.15, 0.95).CGColor())
            self.layer().setCornerRadius_(12.0)

            bounds = self.bounds()
            width = bounds.size.width
            height = bounds.size.height

            # Title bar with mode indicator
            self._title_label = self._create_label(
                NSMakeRect(12, height - 32, width - 70, 24),
                "FOCUS MODE",
                size=11,
                bold=True,
                color=NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.6, 0.2, 1.0)
            )
            self.addSubview_(self._title_label)

            # Timer display (large)
            self._timer_label = self._create_label(
                NSMakeRect(12, height - 80, width - 24, 42),
                "25:00",
                size=36,
                bold=True,
                color=NSColor.whiteColor(),
                alignment=NSTextAlignmentCenter
            )
            self.addSubview_(self._timer_label)

            # Timer phase label
            self._phase_label = self._create_label(
                NSMakeRect(12, height - 100, width - 24, 18),
                "remaining",
                size=11,
                color=NSColor.lightGrayColor(),
                alignment=NSTextAlignmentCenter
            )
            self.addSubview_(self._phase_label)

            # Control buttons
            button_y = height - 135
            button_width = 60
            button_spacing = 8
            total_buttons_width = (button_width * 3) + (button_spacing * 2)
            start_x = (width - total_buttons_width) / 2

            self._pause_button = self._create_button(
                NSMakeRect(start_x, button_y, button_width, 24),
                "Pause",
                action="pauseClicked:"
            )
            self.addSubview_(self._pause_button)

            self._skip_button = self._create_button(
                NSMakeRect(start_x + button_width + button_spacing, button_y, button_width, 24),
                "Skip",
                action="skipClicked:"
            )
            self.addSubview_(self._skip_button)

            self._reset_button = self._create_button(
                NSMakeRect(start_x + (button_width + button_spacing) * 2, button_y, button_width, 24),
                "Reset",
                action="resetClicked:"
            )
            self.addSubview_(self._reset_button)

            # Divider
            divider_y = height - 155
            divider = NSView.alloc().initWithFrame_(NSMakeRect(12, divider_y, width - 24, 1))
            divider.setWantsLayer_(True)
            divider.layer().setBackgroundColor_(NSColor.darkGrayColor().CGColor())
            self.addSubview_(divider)

            # Goal section
            goal_y = height - 180
            self._goal_icon = self._create_label(
                NSMakeRect(12, goal_y, 20, 18),
                "📎",
                size=12
            )
            self.addSubview_(self._goal_icon)

            self._goal_label = self._create_label(
                NSMakeRect(32, goal_y, width - 44, 18),
                "Goal: Deep work",
                size=11,
                color=NSColor.lightGrayColor()
            )
            self.addSubview_(self._goal_label)

            # Progress bar
            progress_y = height - 205
            self._progress_bar = NSProgressIndicator.alloc().initWithFrame_(
                NSMakeRect(12, progress_y, width - 90, 8)
            )
            self._progress_bar.setStyle_(NSProgressIndicatorStyleBar)
            self._progress_bar.setMinValue_(0)
            self._progress_bar.setMaxValue_(100)
            self._progress_bar.setDoubleValue_(0)
            self._progress_bar.setWantsLayer_(True)
            self.addSubview_(self._progress_bar)

            self._progress_text = self._create_label(
                NSMakeRect(width - 75, progress_y - 2, 63, 14),
                "0m / 2h",
                size=10,
                color=NSColor.lightGrayColor()
            )
            self.addSubview_(self._progress_text)

            # Current activity
            activity_y = height - 235
            self._activity_icon = self._create_label(
                NSMakeRect(12, activity_y, 20, 18),
                "🎯",
                size=12
            )
            self.addSubview_(self._activity_icon)

            self._activity_label = self._create_label(
                NSMakeRect(32, activity_y, width - 44, 18),
                "Current: --",
                size=11,
                color=NSColor.lightGrayColor()
            )
            self.addSubview_(self._activity_label)

            # Status indicator
            self._status_label = self._create_label(
                NSMakeRect(12, activity_y - 20, width - 24, 16),
                "✓ Tracking toward goal",
                size=10,
                color=NSColor.colorWithCalibratedRed_green_blue_alpha_(0.4, 0.8, 0.4, 1.0)
            )
            self.addSubview_(self._status_label)

            # Divider
            divider2_y = height - 275
            divider2 = NSView.alloc().initWithFrame_(NSMakeRect(12, divider2_y, width - 24, 1))
            divider2.setWantsLayer_(True)
            divider2.layer().setBackgroundColor_(NSColor.darkGrayColor().CGColor())
            self.addSubview_(divider2)

            # Bottom stats
            stats_y = height - 300
            self._pomodoro_label = self._create_label(
                NSMakeRect(12, stats_y, width / 2 - 12, 18),
                "Today: 🍅🍅🍅🍅○○○○",
                size=10,
                color=NSColor.lightGrayColor()
            )
            self.addSubview_(self._pomodoro_label)

            self._streak_label = self._create_label(
                NSMakeRect(width / 2, stats_y, width / 2 - 12, 18),
                "Streak: 🔥 0 days",
                size=10,
                color=NSColor.lightGrayColor()
            )
            self.addSubview_(self._streak_label)

        def _create_label(self, frame, text, size=12, bold=False, color=None, alignment=NSTextAlignmentLeft):
            """Create a styled text label."""
            label = NSTextField.alloc().initWithFrame_(frame)
            label.setStringValue_(text)
            label.setBezeled_(False)
            label.setDrawsBackground_(False)
            label.setEditable_(False)
            label.setSelectable_(False)

            if bold:
                label.setFont_(NSFont.boldSystemFontOfSize_(size))
            else:
                label.setFont_(NSFont.systemFontOfSize_(size))

            if color:
                label.setTextColor_(color)
            else:
                label.setTextColor_(NSColor.whiteColor())

            label.setAlignment_(alignment)
            return label

        def _create_button(self, frame, title, action):
            """Create a styled button."""
            button = NSButton.alloc().initWithFrame_(frame)
            button.setTitle_(title)
            button.setBezelStyle_(NSBezelStyleRounded)
            button.setTarget_(self)
            button.setAction_(action)
            button.setFont_(NSFont.systemFontOfSize_(10))
            return button

        def pauseClicked_(self, sender):
            """Handle pause/resume button click."""
            if "pause" in self._callbacks:
                self._callbacks["pause"]()

        def skipClicked_(self, sender):
            """Handle skip button click."""
            if "skip" in self._callbacks:
                self._callbacks["skip"]()

        def resetClicked_(self, sender):
            """Handle reset button click."""
            if "reset" in self._callbacks:
                self._callbacks["reset"]()

        def set_callback(self, name: str, callback: Callable):
            """Set a callback for widget actions."""
            self._callbacks[name] = callback

        def updateState_(self, state: WidgetState):
            """Update the widget display with new state.

            Note: Named with underscore suffix for PyObjC selector compatibility.
            Called via performSelectorOnMainThread_withObject_waitUntilDone_.
            """
            self._state = state

            # Update timer
            self._timer_label.setStringValue_(state.time_remaining)

            # Update phase and button
            if state.timer_phase == "work":
                phase_text = "remaining" if state.timer_running else "ready to focus"
                self._title_label.setStringValue_("🍅 FOCUS MODE" if state.timer_running else "FOCUS MODE")
            elif state.timer_phase == "short_break":
                phase_text = "short break"
                self._title_label.setStringValue_("☕ BREAK TIME")
            else:
                phase_text = "long break"
                self._title_label.setStringValue_("🌴 LONG BREAK")

            self._phase_label.setStringValue_(phase_text)
            self._pause_button.setTitle_("Pause" if state.timer_running else "Start")

            # Update goal
            if state.goal_name:
                self._goal_label.setStringValue_(f"Goal: {state.goal_name}")
            self._progress_bar.setDoubleValue_(state.goal_progress_percent)
            self._progress_text.setStringValue_(state.goal_progress_text)

            # Update activity
            if state.current_app:
                self._activity_label.setStringValue_(f"Current: {state.current_app}")

            # Update status
            if state.is_on_goal:
                self._status_label.setStringValue_("✓ Tracking toward goal")
                self._status_label.setTextColor_(
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(0.4, 0.8, 0.4, 1.0)
                )
            else:
                self._status_label.setStringValue_(f"⚠️ Off-goal: {state.off_goal_reason[:30]}")
                self._status_label.setTextColor_(
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.7, 0.3, 1.0)
                )

            # Update pomodoro count
            completed = "🍅" * min(state.pomodoros_today, 8)
            remaining = "○" * max(0, 8 - state.pomodoros_today)
            self._pomodoro_label.setStringValue_(f"Today: {completed}{remaining}")

            # Update streak
            self._streak_label.setStringValue_(f"Streak: 🔥 {state.streak_days} days")

            # Goal completion celebration
            if state.goal_completed:
                self._goal_label.setStringValue_(f"🎉 {state.goal_name} COMPLETE!")


    class FocusWidget:
        """Floating focus widget window manager.

        Usage:
            widget = FocusWidget()
            widget.show()

            # Update state
            widget.update(WidgetState(
                timer_running=True,
                time_remaining="23:45",
                goal_name="Deep work on captains-log",
                goal_progress_percent=75.0,
            ))

            # Set callbacks
            widget.set_callback("pause", lambda: print("Pause clicked"))
        """

        WIDGET_WIDTH = 280
        WIDGET_HEIGHT = 320
        COMPACT_HEIGHT = 50

        def __init__(self, position: str = "top-right"):
            """Initialize the focus widget.

            Args:
                position: Screen position - "top-right", "top-left", "bottom-right", "bottom-left"
            """
            self._position = position
            self._window: NSPanel | None = None
            self._view: FocusWidgetView | None = None
            self._state = WidgetState()
            self._visible = False
            self._mode = WidgetMode.FULL
            self._app_ref = None

        def _get_window_rect(self) -> NSRect:
            """Calculate window position based on configured position."""
            screen = NSScreen.mainScreen()
            screen_frame = screen.visibleFrame()

            width = self.WIDGET_WIDTH
            height = self.WIDGET_HEIGHT if self._mode == WidgetMode.FULL else self.COMPACT_HEIGHT

            margin = 20

            if "right" in self._position:
                x = screen_frame.origin.x + screen_frame.size.width - width - margin
            else:
                x = screen_frame.origin.x + margin

            if "top" in self._position:
                y = screen_frame.origin.y + screen_frame.size.height - height - margin
            else:
                y = screen_frame.origin.y + margin

            return NSMakeRect(x, y, width, height)

        def show(self):
            """Show the widget window."""
            if self._window is not None:
                self._window.orderFront_(None)
                self._visible = True
                return

            # Create floating panel
            rect = self._get_window_rect()
            style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel

            self._window = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                rect,
                style,
                NSBackingStoreBuffered,
                False
            )

            # Configure window properties
            self._window.setLevel_(NSFloatingWindowLevel)
            self._window.setOpaque_(False)
            self._window.setBackgroundColor_(NSColor.clearColor())
            self._window.setHasShadow_(True)
            self._window.setMovableByWindowBackground_(True)
            self._window.setCollectionBehavior_(1 << 0)  # NSWindowCollectionBehaviorCanJoinAllSpaces

            # Create and set content view
            self._view = FocusWidgetView.alloc().initWithFrame_(
                NSMakeRect(0, 0, rect.size.width, rect.size.height)
            )
            self._window.setContentView_(self._view)

            # Show window
            self._window.orderFront_(None)
            self._visible = True

            logger.info("Focus widget shown")

        def hide(self):
            """Hide the widget window."""
            if self._window:
                self._window.orderOut_(None)
                self._visible = False
                logger.info("Focus widget hidden")

        def close(self):
            """Close and destroy the widget window."""
            if self._window:
                self._window.close()
                self._window = None
                self._view = None
                self._visible = False
                logger.info("Focus widget closed")

        def toggle_mode(self):
            """Toggle between full and compact mode."""
            self._mode = WidgetMode.COMPACT if self._mode == WidgetMode.FULL else WidgetMode.FULL

            if self._window:
                rect = self._get_window_rect()
                self._window.setFrame_display_(rect, True)

        def update(self, state: WidgetState):
            """Update the widget with new state."""
            self._state = state

            if self._view:
                # Must update UI on main thread
                self._view.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "updateState:",
                    state,
                    False
                )

        def set_callback(self, name: str, callback: Callable):
            """Set a callback for widget actions.

            Available callbacks:
            - pause: Called when pause/resume button clicked
            - skip: Called when skip button clicked
            - reset: Called when reset button clicked
            """
            if self._view:
                self._view.set_callback(name, callback)

        @property
        def is_visible(self) -> bool:
            """Whether the widget is currently visible."""
            return self._visible

        @property
        def state(self) -> WidgetState:
            """Get the current widget state."""
            return self._state


else:
    # Fallback when PyObjC is not available
    class FocusWidget:
        """Stub focus widget when PyObjC is not available."""

        def __init__(self, position: str = "top-right"):
            self._state = WidgetState()
            logger.warning("FocusWidget: PyObjC not available, widget disabled")

        def show(self):
            logger.info("FocusWidget.show() - widget disabled (PyObjC not available)")

        def hide(self):
            pass

        def close(self):
            pass

        def toggle_mode(self):
            pass

        def update(self, state: WidgetState):
            self._state = state

        def set_callback(self, name: str, callback: Callable):
            pass

        @property
        def is_visible(self) -> bool:
            return False

        @property
        def state(self) -> WidgetState:
            return self._state
