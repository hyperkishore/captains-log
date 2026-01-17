"""Pomodoro timer state machine with configurable durations."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class TimerPhase(Enum):
    """Current phase of the Pomodoro timer."""
    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


@dataclass
class PomodoroState:
    """Current state of the Pomodoro timer."""
    phase: TimerPhase = TimerPhase.WORK
    is_running: bool = False
    time_remaining_seconds: int = 25 * 60  # Default 25 minutes
    pomodoros_completed: int = 0
    session_started_at: datetime | None = None
    phase_started_at: datetime | None = None
    total_work_seconds: int = 0
    total_break_seconds: int = 0
    interruption_count: int = 0

    @property
    def time_remaining_display(self) -> str:
        """Format time remaining as MM:SS."""
        minutes, seconds = divmod(self.time_remaining_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def progress_percent(self) -> float:
        """Progress through current phase (0-100)."""
        if self.phase == TimerPhase.WORK:
            total = 25 * 60  # Work duration
        elif self.phase == TimerPhase.SHORT_BREAK:
            total = 5 * 60
        else:
            total = 15 * 60  # Long break

        elapsed = total - self.time_remaining_seconds
        return min(100, max(0, (elapsed / total) * 100))


@dataclass
class PomodoroConfig:
    """Configuration for Pomodoro timer durations."""
    work_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    pomodoros_until_long_break: int = 4
    auto_start_breaks: bool = True
    auto_start_work: bool = False


class PomodoroTimer:
    """Pomodoro timer with state machine and callbacks.

    Usage:
        timer = PomodoroTimer()
        timer.on_tick = lambda state: print(state.time_remaining_display)
        timer.on_phase_complete = lambda phase: print(f"{phase} complete!")

        await timer.start()
        # ... timer runs ...
        await timer.pause()
        await timer.resume()
        await timer.skip()  # Skip to next phase
        await timer.reset()  # Reset current phase
    """

    def __init__(self, config: PomodoroConfig | None = None):
        self.config = config or PomodoroConfig()
        self._state = PomodoroState()
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

        # Callbacks
        self.on_tick: Callable[[PomodoroState], None] | None = None
        self.on_phase_complete: Callable[[TimerPhase], Awaitable[None] | None] | None = None
        self.on_pomodoro_complete: Callable[[int], Awaitable[None] | None] | None = None
        self.on_session_complete: Callable[[PomodoroState], Awaitable[None] | None] | None = None

        # Initialize with work duration
        self._state.time_remaining_seconds = self.config.work_minutes * 60

    @property
    def state(self) -> PomodoroState:
        """Get current timer state (read-only copy)."""
        return PomodoroState(
            phase=self._state.phase,
            is_running=self._state.is_running,
            time_remaining_seconds=self._state.time_remaining_seconds,
            pomodoros_completed=self._state.pomodoros_completed,
            session_started_at=self._state.session_started_at,
            phase_started_at=self._state.phase_started_at,
            total_work_seconds=self._state.total_work_seconds,
            total_break_seconds=self._state.total_break_seconds,
            interruption_count=self._state.interruption_count,
        )

    async def start(self) -> None:
        """Start or resume the timer."""
        async with self._lock:
            if self._state.is_running:
                return

            self._state.is_running = True

            if self._state.session_started_at is None:
                self._state.session_started_at = datetime.now()

            if self._state.phase_started_at is None:
                self._state.phase_started_at = datetime.now()

            logger.info(f"Pomodoro timer started: {self._state.phase.value}")

            # Start the tick loop
            self._task = asyncio.create_task(self._tick_loop())

    async def pause(self) -> None:
        """Pause the timer."""
        async with self._lock:
            if not self._state.is_running:
                return

            self._state.is_running = False
            self._state.interruption_count += 1

            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None

            logger.info("Pomodoro timer paused")

    async def resume(self) -> None:
        """Resume a paused timer."""
        await self.start()

    async def skip(self) -> None:
        """Skip to the next phase."""
        async with self._lock:
            was_running = self._state.is_running

            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None

            self._state.is_running = False

        # Complete current phase
        await self._complete_phase()

        # Auto-start if configured and was running
        if was_running:
            if (self._state.phase == TimerPhase.WORK and self.config.auto_start_work) or \
               (self._state.phase != TimerPhase.WORK and self.config.auto_start_breaks):
                await self.start()

    async def reset(self) -> None:
        """Reset the current phase timer."""
        async with self._lock:
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None

            self._state.is_running = False
            self._state.time_remaining_seconds = self._get_phase_duration()
            self._state.phase_started_at = None

            logger.info(f"Pomodoro phase reset: {self._state.phase.value}")

    async def reset_session(self) -> None:
        """Reset the entire session."""
        async with self._lock:
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None

            self._state = PomodoroState()
            self._state.time_remaining_seconds = self.config.work_minutes * 60

            logger.info("Pomodoro session reset")

    def _get_phase_duration(self) -> int:
        """Get duration in seconds for the current phase."""
        if self._state.phase == TimerPhase.WORK:
            return self.config.work_minutes * 60
        elif self._state.phase == TimerPhase.SHORT_BREAK:
            return self.config.short_break_minutes * 60
        else:
            return self.config.long_break_minutes * 60

    async def _tick_loop(self) -> None:
        """Main timer tick loop."""
        try:
            while self._state.is_running and self._state.time_remaining_seconds > 0:
                await asyncio.sleep(1)

                async with self._lock:
                    if not self._state.is_running:
                        break

                    self._state.time_remaining_seconds -= 1

                    # Track total time
                    if self._state.phase == TimerPhase.WORK:
                        self._state.total_work_seconds += 1
                    else:
                        self._state.total_break_seconds += 1

                # Fire tick callback
                if self.on_tick:
                    try:
                        self.on_tick(self.state)
                    except Exception as e:
                        logger.error(f"Error in on_tick callback: {e}")

            # Phase complete
            if self._state.is_running and self._state.time_remaining_seconds <= 0:
                await self._complete_phase()

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in timer tick loop: {e}")

    async def _complete_phase(self) -> None:
        """Handle phase completion and transition."""
        completed_phase = self._state.phase

        # Fire phase complete callback
        if self.on_phase_complete:
            try:
                result = self.on_phase_complete(completed_phase)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in on_phase_complete callback: {e}")

        # Handle work phase completion
        if completed_phase == TimerPhase.WORK:
            self._state.pomodoros_completed += 1

            # Fire pomodoro complete callback
            if self.on_pomodoro_complete:
                try:
                    result = self.on_pomodoro_complete(self._state.pomodoros_completed)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Error in on_pomodoro_complete callback: {e}")

            # Determine next break type
            if self._state.pomodoros_completed % self.config.pomodoros_until_long_break == 0:
                self._state.phase = TimerPhase.LONG_BREAK
            else:
                self._state.phase = TimerPhase.SHORT_BREAK

            logger.info(f"Work phase complete! Starting {self._state.phase.value}")
        else:
            # Break complete, back to work
            self._state.phase = TimerPhase.WORK
            logger.info("Break complete! Starting work phase")

        # Reset timer for new phase
        self._state.time_remaining_seconds = self._get_phase_duration()
        self._state.phase_started_at = None
        self._state.is_running = False

        # Auto-start next phase if configured
        should_auto_start = (
            (self._state.phase == TimerPhase.WORK and self.config.auto_start_work) or
            (self._state.phase != TimerPhase.WORK and self.config.auto_start_breaks)
        )

        if should_auto_start:
            await self.start()

    def get_summary(self) -> dict:
        """Get a summary of the current session."""
        return {
            "phase": self._state.phase.value,
            "is_running": self._state.is_running,
            "time_remaining": self._state.time_remaining_display,
            "pomodoros_completed": self._state.pomodoros_completed,
            "total_work_minutes": round(self._state.total_work_seconds / 60, 1),
            "total_break_minutes": round(self._state.total_break_seconds / 60, 1),
            "interruption_count": self._state.interruption_count,
            "session_started_at": self._state.session_started_at.isoformat() if self._state.session_started_at else None,
        }
