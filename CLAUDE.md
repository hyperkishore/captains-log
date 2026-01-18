# Captain's Log - Project Context for Claude

## Overview

Captain's Log is a macOS personal activity tracking system that passively captures digital activity and synthesizes it into actionable insights using Claude AI.

## Project Structure

```
captains-log/
├── src/captains_log/
│   ├── core/                 # Core daemon components
│   │   ├── config.py         # Pydantic configuration with YAML
│   │   ├── orchestrator.py   # Main daemon coordinator
│   │   └── permissions.py    # macOS permission checks
│   │
│   ├── trackers/             # Activity tracking components
│   │   ├── app_monitor.py    # NSWorkspace event-based tracking
│   │   ├── window_tracker.py # Accessibility API for titles/URLs
│   │   ├── idle_detector.py  # CGEventSource idle detection
│   │   └── buffer.py         # Event buffering with periodic flush
│   │
│   ├── storage/              # Data persistence
│   │   ├── database.py       # SQLite with WAL mode
│   │   └── screenshot_manager.py  # Screenshot file/DB management
│   │
│   ├── ai/                   # AI summarization (Phase 3)
│   │   ├── claude_client.py  # Anthropic API with vision support
│   │   ├── batch_processor.py # Queue management for batch API
│   │   ├── prompts.py        # Prompt templates
│   │   └── schemas.py        # Pydantic response models
│   │
│   ├── summarizers/          # Summary generation
│   │   ├── five_minute.py    # 5-min activity summarizer
│   │   └── focus_calculator.py # Focus score algorithm
│   │
│   ├── cli/                  # Command-line interface
│   │   ├── main.py           # Typer CLI commands
│   │   └── install.py        # launchd installation
│   │
│   └── web/                  # Web dashboard
│       ├── app.py            # FastAPI application
│       ├── routes/           # API and page routes
│       └── templates/        # Jinja2 HTML templates
│
├── resources/launchd/        # launchd plist template
├── pyproject.toml            # Project dependencies
├── Makefile                  # Build automation
└── README.md                 # User documentation
```

## Key Technical Decisions

### 1. Event-Based Activity Tracking
- Uses `NSWorkspaceDidActivateApplicationNotification` instead of polling
- CPU usage: <0.5% vs 5-8% with polling
- Events are debounced (500ms) to ignore rapid CMD+TAB switching

### 2. macOS APIs Used
- **NSWorkspace**: Application activation notifications
- **Accessibility API (AXUIElement)**: Window titles, URLs
- **CGEventSource**: Idle time tracking (mouse/keyboard)
- **ScreenCaptureKit**: Screenshot capture (Phase 2)

### 3. Database Design
- SQLite with WAL mode for concurrent access
- Tables: `activity_logs`, `screenshots`, `summaries`, `daily_summaries`
- Async operations via `aiosqlite`

### 4. Configuration
- Pydantic settings with YAML file support
- Environment variable overrides (`CAPTAINS_LOG_*`)
- Paths: `~/Library/Application Support/CaptainsLog/`

### Screenshot Capture (Phase 2)

**Implementation**: Uses CoreGraphics `CGDisplayCreateImage` (not ScreenCaptureKit) for simpler synchronous capture.

**Files**:
- `trackers/screenshot_capture.py` - Capture with WebP compression
- `storage/screenshot_manager.py` - DB persistence and retention
- `web/routes/screenshots.py` - API endpoints

**Key Features**:
- **Periodic capture**: Every 5 minutes (configurable)
- **App-change capture**: Screenshot on every app switch (after debounce)
- **Debounce**: 2 seconds - waits for user to settle before recording (filters swipe gestures)
- **Privacy filtering**: Excludes password managers, banking apps
- **WebP compression**: ~80KB per screenshot, max 1280px width
- **Retention**: 7 days, auto-cleanup hourly
- **UTC timestamps**: All timestamps in UTC for consistency with activity logs

**Dashboard Integration**:
- Timeline shows thumbnails matched to activities (within 60 seconds)
- Click thumbnail to view full-size screenshot
- Screenshot count shown in timeline header

## Important Patterns

### Activity Event Flow
```
App Change Event → Debounce (2000ms) → Enrich with:
  - Window title (Accessibility)
  - URL (browser title parsing)
  - Idle state (CGEventSource)
  - Screenshot capture (if enabled)
→ Buffer (in-memory) → Flush every 30s → SQLite
```

### Idle State Classification
```python
# Context-aware classification
if bundle_id in VIDEO_APPS and mouse_idle < 60:
    return "WATCHING_MEDIA"
if bundle_id in READING_APPS and keyboard_idle < 600:
    return "READING"
if mouse_idle > 300 and keyboard_idle > 300:
    return "AWAY"
if min(mouse_idle, keyboard_idle) > 60:
    return "IDLE_BUT_PRESENT"
return "ACTIVE"
```

### Browser URL Extraction
- Chrome/Chromium: Parse from window title (after " - ")
- Safari: Use `AXDocument` accessibility attribute
- Firefox: Parse title, strip " - Mozilla Firefox" suffix

## CLI Commands

```bash
captains-log start [-f]      # Start daemon
captains-log stop            # Stop daemon
captains-log status          # Show status
captains-log health          # Detailed health
captains-log dashboard       # Web UI
captains-log logs [-f]       # View logs
captains-log install         # Auto-start setup
```

## Database Schema (Key Tables)

```sql
-- Activity tracking
CREATE TABLE activity_logs (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    app_name TEXT NOT NULL,
    bundle_id TEXT,
    window_title TEXT,
    url TEXT,
    idle_seconds REAL,
    idle_status TEXT,  -- ACTIVE, WATCHING_MEDIA, READING, AWAY
    is_fullscreen BOOLEAN,
    display_index INTEGER
);

-- AI summaries (Phase 3)
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY,
    period_start DATETIME,
    period_end DATETIME,
    primary_app TEXT,
    activity_type TEXT,
    focus_score INTEGER,
    key_activities JSON,
    context TEXT
);
```

## Phase Implementation Status

- [x] **Phase 1**: Core Daemon - Activity tracking, CLI, Web Dashboard
- [x] **Phase 2**: Screenshot Capture - CoreGraphics, WebP compression, app-change triggers
- [x] **Phase 3**: AI Summaries - Claude Haiku, Batch API, vision support, focus calculator
- [x] **Phase 4**: Focus UI/UX - Menu bar app, floating widget, goal streaks, one-click start
- [ ] **Phase 5**: Calendar Integration - macOS EventKit, smart suggestions (NEXT)
- [ ] **Phase 6**: Proactive AI - Morning/evening notifications, nudges
- [ ] **Phase 7**: Social/Growth - Shareable weekly summaries, milestones

See `ROADMAP.md` for detailed product roadmap.

## Development Notes

### Running Tests
```bash
make test
```

### Code Style
- Ruff for linting and formatting
- MyPy for type checking
- Line length: 100 characters

### Key Dependencies
- `pyobjc-*`: macOS API bindings
- `pydantic`: Configuration and validation
- `aiosqlite`: Async SQLite
- `typer` + `rich`: CLI
- `fastapi` + `jinja2`: Web dashboard
- `anthropic`: Claude API (Phase 3)

## Known Issues & Deviations from Plan

### NSWorkspace Notifications in Background Contexts (RESOLVED)

**Status**: RESOLVED with polling fallback

**Problem**: NSWorkspace notifications are not delivered when running in background contexts (launchd, subprocess, etc.) because they require an active connection to WindowServer.

**Solution Implemented**:
- Added **polling fallback** that activates automatically after 10 seconds if no NSWorkspace events are received
- Polling checks the frontmost application every 2 seconds
- Event-based tracking still works when running from Terminal.app
- Polling fallback provides equivalent functionality with minimal CPU overhead

**How It Works**:
```
1. Daemon starts and registers for NSWorkspace notifications
2. After 10 seconds, if no events received, polling fallback enables
3. Polling checks every 2 seconds for app changes
4. Events flow through same pipeline: monitor → buffer → database
```

**Result**: The daemon now captures activity correctly regardless of how it's started.

### Missing Dependency Issue (RESOLVED)

**Problem**: `pyobjc-framework-ApplicationServices` was not in dependencies.

**Fix**: Added to pyproject.toml:
```toml
"pyobjc-framework-ApplicationServices>=10.0",
```

### Permission Display Name Issue

**Problem**: macOS shows "Python 3" instead of "Captain's Log" in permission dialogs.

**Cause**: Running as Python script, not bundled app.

**Status**: Cosmetic issue only. Permissions work correctly.

## Common Issues

### Permission Denied Errors
- User needs to grant Accessibility permission in System Preferences
- App guides user to the correct settings pane

### High Memory Usage
- Event buffer is limited to 100 events
- Flush interval prevents unbounded growth

### Database Locked
- WAL mode handles concurrent access
- Busy timeout set to 5000ms

### Daemon Won't Track Activity
- Check that Terminal.app has Accessibility permission granted
- Verify daemon is running: `captains-log status`
- Polling fallback enables after 10 seconds if event-based tracking fails
- Run in foreground for debugging: `captains-log start -f`

## Testing the Application

```bash
# Install
make install
source .venv/bin/activate

# Test daemon (background mode)
captains-log start         # Background daemon
captains-log status        # Check status
captains-log logs -f       # Follow logs

# Test daemon (foreground mode for debugging)
captains-log start -f      # Foreground mode (Ctrl+C to stop)

# Test dashboard
captains-log dashboard --port 8081   # Start on port 8081
# Open http://127.0.0.1:8081

# Check health
captains-log health
```

## Method of Operation for Development

When developing or debugging Captain's Log:

### 1. Recursive Testing Workflow
- Test changes by running commands and verifying output
- If testing UI changes, use `open http://127.0.0.1:8081/` to open in browser
- Check logs with `captains-log logs -f` for debugging
- Query database directly: `sqlite3 ~/Library/Application\ Support/CaptainsLog/captains_log.db`

### 2. Common Development Commands
```bash
# Check daemon status
ps aux | grep captains-log | grep -v grep

# View recent activity
sqlite3 ~/Library/Application\ Support/CaptainsLog/captains_log.db \
  "SELECT datetime(timestamp), app_name FROM activity_logs ORDER BY timestamp DESC LIMIT 10;"

# Restart daemon
captains-log stop && captains-log start

# Check SwiftBar output
bash "/Users/kishore/Library/Application Support/SwiftBar/Plugins/captains-log.1m.sh"
```

### 3. Dashboard URLs
- Main Dashboard: http://127.0.0.1:8081/
- Time Analysis: http://127.0.0.1:8081/time-analysis
- Timeline: http://127.0.0.1:8081/timeline
- Apps: http://127.0.0.1:8081/apps

---

## Recurring Instructions for Claude

**IMPORTANT**: Follow these instructions in every session working on this project.

### 1. Before Starting Work
- Read the plan file at `~/.claude/plans/peaceful-cooking-lake.md` for current implementation status
- Check the Phase Implementation Status above to understand what's complete
- See `ROADMAP.md` for product roadmap and prioritization

### 2. After Completing Work
- Update this CLAUDE.md file with any significant changes or new patterns
- Update the plan file with implementation progress
- Commit changes with clear commit messages
- **Push to git**: Always push changes to remote after committing

### 3. Key Design Principles
- **UTC timestamps everywhere**: All timestamps in database should be UTC for consistency
- **Debounce user interactions**: Wait 2+ seconds before recording app switches to filter swipe gestures
- **Graceful degradation**: Features should fail gracefully if permissions are denied
- **Local-first**: Raw data stays local, only summaries sync to cloud

### 4. Version Synchronization (CRITICAL)
**ALWAYS keep version numbers in sync across ALL components when making changes:**

| Component | File | Version Field |
|-----------|------|---------------|
| Main Package | `pyproject.toml` | `version = "X.Y.Z"` |
| Frontend | `frontend/package.json` | `"version": "X.Y.Z"` |
| Frontend API | `frontend/src/lib/api.ts` | `API_VERSION = 'X.Y.Z'` |
| Backend API | `backend/main.py` | `version="X.Y.Z"` |
| SwiftBar Plugin | `scripts/captains-log.1m.sh` | `VERSION="X.Y.Z"` |
| VERSION file | `VERSION` | `X.Y.Z` |

**When to bump version:**
- Major (X): Breaking changes, major features
- Minor (Y): New features, significant improvements
- Patch (Z): Bug fixes, small changes

**Current Version: 0.2.0**

### 5. Testing Changes
```bash
# Restart daemon to apply changes
.venv/bin/python -m captains_log stop && .venv/bin/python -m captains_log start

# Restart dashboard
pkill -f "uvicorn.*captains_log"; .venv/bin/python -m captains_log dashboard &

# Check logs
tail -f ~/Library/Logs/CaptainsLog/daemon.log

# Query database
sqlite3 ~/Library/Application\ Support/CaptainsLog/captains_log.db
```

### 5. Session Summary Template
At the end of each session, update this file with:
- What was implemented/changed
- Any new files created
- Configuration changes
- Known issues or TODOs

---

## Session Log

### 2026-01-15: Phase 2 Screenshot Capture Implementation

**Completed**:
- Implemented screenshot capture using CoreGraphics `CGDisplayCreateImage`
- Added WebP compression with Pillow (quality 80, max 1280px width)
- Screenshots captured on app change (after 2s debounce) AND every 5 minutes
- Dashboard timeline shows screenshot thumbnails matched to activities
- Retention system with 7-day auto-cleanup

**Files Created**:
- `src/captains_log/trackers/screenshot_capture.py`
- `src/captains_log/storage/screenshot_manager.py`
- `src/captains_log/web/routes/screenshots.py`

**Files Modified**:
- `src/captains_log/core/orchestrator.py` - Screenshot lifecycle integration
- `src/captains_log/core/config.py` - Added `capture_on_app_change` option, increased debounce to 2s
- `src/captains_log/web/app.py` - Mount screenshots static files
- `src/captains_log/web/routes/dashboard.py` - Proximity-based screenshot matching (60s window)
- `src/captains_log/web/templates/timeline.html` - Thumbnail display

**Key Decisions**:
- Used CoreGraphics instead of ScreenCaptureKit (simpler synchronous API)
- UTC timestamps for screenshots to match activity log timestamps
- Proximity matching (within 60 seconds) instead of 5-minute interval rounding
- 2-second debounce to filter swipe gestures

**Configuration**:
```yaml
tracking:
  debounce_ms: 2000  # Wait 2s before recording app switch

screenshots:
  enabled: true
  interval_minutes: 5
  capture_on_app_change: true
  quality: 80
  max_width: 1280
  retention_days: 7
```

### 2026-01-15: Added Git Push Recurring Instruction

**Completed**:
- Added recurring instruction to always push changes to git after committing

**Files Modified**:
- `CLAUDE.md` - Added "Push to git" instruction to "After Completing Work" section

### 2026-01-15: Phase 3 AI Summaries Implementation

**Completed**:
- Implemented Claude client with vision support (async, rate limiting, retry logic)
- Created batch processor for queue management (batch API for 50% cost savings)
- Implemented focus calculator with multi-factor scoring algorithm
- Created 5-minute summarizer with periodic summary generation
- Integrated AI summarization into orchestrator lifecycle
- Added CLI commands for summary management

**Files Created**:
- `src/captains_log/ai/__init__.py` - AI module exports
- `src/captains_log/ai/schemas.py` - Pydantic models (SummaryResponse, ActivityType, etc.)
- `src/captains_log/ai/prompts.py` - Prompt templates for Claude
- `src/captains_log/ai/claude_client.py` - Claude API wrapper with vision
- `src/captains_log/ai/batch_processor.py` - Queue management and batch processing
- `src/captains_log/summarizers/__init__.py` - Summarizer module exports
- `src/captains_log/summarizers/focus_calculator.py` - Focus score algorithm
- `src/captains_log/summarizers/five_minute.py` - 5-minute summary generator

**Files Modified**:
- `src/captains_log/core/orchestrator.py` - AI summarization lifecycle integration
- `src/captains_log/cli/main.py` - Added `summaries`, `summaries-backfill`, `summaries-process` commands

**Key Features**:
- **Vision support**: Screenshots sent to Claude for context-aware analysis
- **Batch API**: 50% cost reduction with scheduled batch processing (default: every 6 hours)
- **Realtime mode**: Option to process summaries immediately (higher cost)
- **Focus scoring**: Multi-factor algorithm considering context switches, app types, engagement
- **Backfill support**: Generate summaries for historical data

**CLI Commands**:
```bash
captains-log summaries                  # Show recent summaries
captains-log summaries-backfill --hours 24  # Generate missing summaries
captains-log summaries-process          # Process pending queue
```

**Configuration**:
```yaml
summarization:
  enabled: true
  model: claude-haiku-4-5-20241022
  use_batch_api: true
  batch_interval_hours: 6
  vision_enabled: true
  max_tokens: 1024

# Requires: ANTHROPIC_API_KEY or CAPTAINS_LOG_CLAUDE_API_KEY
```

### 2026-01-18: Focus UI/UX Redesign

**Problem Statement**: Help people maintain focused effort while working. The UI should provide ambient awareness without being distracting.

**Design Principles**:
1. Minimal cognitive load - Glanceable, not interactive
2. Ambient presence - Always visible but unobtrusive
3. Accountability - What am I working on? How long? How many sessions to go?
4. Session-based thinking - "3 of 6 sessions" not "75% complete"

**Completed**:

1. **Native Menu Bar App** (`MenuBarApp/CaptainsLogMenuBar.swift`):
   - Replaced SwiftBar plugin with native Swift app using NSStatusBar + NSPopover
   - Fixed size popup (220x180) to prevent shifting
   - New session form: task name, duration picker, sessions picker, apps field
   - Active session controls: Pause/Resume button, End button, Widget button
   - Session dots showing progress (●●○○ = 2 of 4 sessions)
   - Daily focus time in header
   - Daemon status indicator (green/red dot)

2. **Focus Widget Redesign** (`FocusWidget/FocusWidgetApp.swift`):
   - Removed Full mode - now only Compact and Mini
   - Removed progress bar, percentage, pause/skip/reset buttons
   - Added session dots (●●●○○○)
   - Click to toggle between Compact ↔ Mini
   - Off-goal activities show amber border
   - Sounds on phase change and completion

3. **Database Schema** (`storage/database.py`):
   - Added `estimated_sessions INTEGER DEFAULT 4` to `focus_goals` table
   - Schema version bumped from 5 to 6
   - Migration automatically adds column to existing databases

4. **CLI Commands** (`cli/main.py`):
   - Added `--sessions` / `-s` flag to `focus` command
   - Added `focus-timer pause|resume|skip` command
   - Added `focus-stop` command
   - Control file mechanism (`~/Library/Application Support/CaptainsLog/focus_control.json`)
   - Running focus session polls control file for commands

5. **Widget Controller** (`widget/widget_controller.py`):
   - `start_focus()` accepts `estimated_sessions` parameter
   - Status file writes `estimated_sessions` and `daily_focus_minutes`

6. **Goal Tracker** (`focus/goal_tracker.py`):
   - `FocusGoal` dataclass includes `estimated_sessions` field
   - `from_db_row()` and `to_db_dict()` handle the new field

**Files Created**:
- `MenuBarApp/CaptainsLogMenuBar.swift` - Native menu bar app
- `MenuBarApp/build.sh` - Build script
- `MenuBarApp/Info.plist` - App bundle config

**Files Modified**:
- `FocusWidget/FocusWidgetApp.swift` - Simplified to Compact + Mini only
- `src/captains_log/storage/database.py` - Added estimated_sessions column
- `src/captains_log/focus/goal_tracker.py` - Added estimated_sessions to FocusGoal
- `src/captains_log/widget/widget_controller.py` - Added estimated_sessions support
- `src/captains_log/cli/main.py` - Added --sessions flag and timer control commands

**CLI Usage**:
```bash
# Start focus session with 4 pomodoro sessions
captains-log focus -g "Deep work" -t 120 -a "VS Code,Terminal" --sessions 4

# Control running session
captains-log focus-timer pause
captains-log focus-timer resume
captains-log focus-stop
```

**Menu Bar Flow**:
1. Click menu bar icon → popup appears
2. Click "Start Focus Session" → form appears
3. Enter task name, pick duration/sessions → click "Start Focus"
4. Session runs, use Pause/Resume/End buttons to control
5. Widget shows ambient timer + session dots

**Status File** (`~/Library/Application Support/CaptainsLog/focus_status.json`):
```json
{
  "active": true,
  "goal_name": "Deep Work",
  "target_minutes": 120,
  "focus_minutes": 45.5,
  "pomodoro_count": 2,
  "estimated_sessions": 4,
  "time_remaining": "18:42",
  "timer_running": true,
  "daily_focus_minutes": 45.5
}
```

**Removed from Design**:
- Progress bar (anxiety-inducing)
- Percentage display (unnecessary cognitive load)
- Pause/Skip/Reset buttons on widget (encourages fiddling)
- Full widget mode (too much information)
- Dashboard link from menu bar (to be added back with correct URL)

**Known Issues / TODO**:
- Dashboard link needs to be added back (user will specify URL)
- Next.js frontend exists at `frontend/` (runs on port 3000)

**Example Summary Output**:
```json
{
  "primary_app": "VS Code",
  "activity_type": "coding",
  "focus_score": 8,
  "key_activities": ["Implementing AI summarization", "Writing Claude client"],
  "context": "Deep work session implementing Phase 3 AI features",
  "context_switches": 2,
  "tags": ["captains-log", "python", "anthropic"]
}
```

### 2026-01-17: Focus Timer Widget MVP Implementation

**Completed**:
- Implemented Focus Timer Widget with Pomodoro timer and goal-based activity tracking
- Created floating macOS overlay widget using PyObjC
- Added database schema for focus goals, sessions, and pomodoro history
- Implemented activity matcher for flexible goal criteria (app-based, project-based)
- Added CLI commands for focus mode management

**Files Created**:
- `src/captains_log/focus/__init__.py` - Focus module exports
- `src/captains_log/focus/pomodoro.py` - Pomodoro timer state machine with callbacks
- `src/captains_log/focus/activity_matcher.py` - Activity matching against goal criteria
- `src/captains_log/focus/goal_tracker.py` - Goal and session tracking with streaks
- `src/captains_log/widget/__init__.py` - Widget module exports
- `src/captains_log/widget/focus_widget.py` - PyObjC floating overlay window
- `src/captains_log/widget/widget_controller.py` - Controller coordinating timer, tracker, and widget

**Files Modified**:
- `src/captains_log/storage/database.py` - Added focus_goals, focus_sessions, pomodoro_history tables (schema v5)
- `src/captains_log/core/config.py` - Added FocusConfig with Pomodoro settings
- `src/captains_log/cli/main.py` - Added `focus`, `focus-status`, `focus-goals` commands

**Key Features**:
- **Pomodoro Timer**: 25/5/15 minute cycles with auto-start options
- **Goal Tracking**: App-based, project-based, or category-based goals
- **Floating Widget**: Always-on-top macOS overlay showing timer and progress
- **Activity Matching**: Flexible criteria with whitelist/blacklist patterns
- **Streak Tracking**: Current and longest streak with calendar support
- **Tracking Modes**: "passive" (always track) or "strict" (timer only)
- **Gentle Nudges**: Visual indicator when switching to off-goal apps

**CLI Commands**:
```bash
captains-log focus -g "Deep work" -t 120 -a "VS Code,Terminal"
captains-log focus -p "captains-log"  # Track by project
captains-log focus  # Interactive mode
captains-log focus-status  # Show today's sessions
captains-log focus-goals --create "Writing" -t 60  # Create goal
captains-log focus-goals  # List goals
```

**Configuration** (config.yaml):
```yaml
focus:
  enabled: true
  work_minutes: 25
  short_break_minutes: 5
  long_break_minutes: 15
  pomodoros_until_long_break: 4
  auto_start_breaks: true
  auto_start_work: false
  tracking_mode: passive  # or "strict"
  show_widget: true
  widget_position: top-right
  gentle_nudges: true
  default_goal_minutes: 120
```

**Widget Visual Design**:
```
┌─────────────────────────────────────────────────┐
│  🍅 FOCUS MODE                                  │
├─────────────────────────────────────────────────┤
│           ⏱️  23:45                            │
│           remaining                             │
│     [ Pause ]  [ Skip ]  [ Reset ]              │
├─────────────────────────────────────────────────┤
│  📎 Goal: Deep work on captains-log             │
│  ████████████░░░░░░  1.5h / 2h  (75%)          │
│  🎯 Current: VS Code - pomodoro.py              │
│  ✓ Tracking toward goal                         │
├─────────────────────────────────────────────────┤
│  Today: 🍅🍅🍅🍅○○○○  4/8 pomodoros             │
│  Streak: 🔥 3 days                              │
└─────────────────────────────────────────────────┘
```

**Database Schema** (v5):
```sql
CREATE TABLE focus_goals (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    goal_type TEXT NOT NULL,  -- app_based, project_based, category_based
    target_minutes INTEGER NOT NULL,
    match_criteria JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME
);

CREATE TABLE focus_sessions (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER REFERENCES focus_goals(id),
    date DATE NOT NULL,
    pomodoro_count INTEGER DEFAULT 0,
    total_focus_minutes REAL DEFAULT 0,
    total_break_minutes REAL DEFAULT 0,
    off_goal_minutes REAL DEFAULT 0,
    completed BOOLEAN DEFAULT FALSE,
    created_at DATETIME
);

CREATE TABLE pomodoro_history (
    id INTEGER PRIMARY KEY,
    session_id INTEGER REFERENCES focus_sessions(id),
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    duration_minutes REAL,
    was_completed BOOLEAN,
    interruption_count INTEGER,
    primary_app TEXT
);
```

**Next Steps** (from plan):
- Integrate widget with orchestrator for real-time activity updates
- Add morning/evening briefings
- Implement pattern detection from historical data
- Add schedule optimizer based on focus patterns

### 2026-01-18: Menu Bar UI Improvements & Product Roadmap

**Completed**:

1. **Menu Bar UI Fixes**:
   - Fixed element sizing for uniform appearance (28px row heights, 14px icons)
   - Added expandable subtasks for goals with chevron disclosure
   - Removed large progress rings per user request
   - Fixed "Today" row to show cumulative focus time from database (not just current session)
   - Added fixed column widths (chevronWidth: 16px, streakWidth: 70px) to prevent layout jumping
   - Added play button for goals without tasks to start 25m focus sessions

2. **Floating Widget Fixes**:
   - Fixed widget not appearing when starting focus sessions - added `NSWorkspace.shared.open()` call
   - Fixed widget crashing on click - removed mode toggling and click handlers
   - Removed HotkeyManager that was causing crashes on Cmd+Shift+M
   - Added hover-to-show close button (X) for closing widget
   - Added "Show Widget" button in menu bar for re-opening widget

3. **Focus Session Switching Fix**:
   - Fixed old session overwriting new session when switching tasks
   - Added `pkill -f 'captains-log focus'` before starting new session
   - Clear old status file before starting new session

4. **Product Roadmap Created** (`ROADMAP.md`):
   - 80-20 analysis of feature usage (daily vs weekly vs rarely used)
   - Three perspectives: AI Developer, Product Designer, Growth Marketer
   - Identified core loop: Start session → Timer glance → Daily total → Streaks
   - Prioritized phases: Core Loop ✅ → Proactive AI → Emotional Design → Weekly Insights → Calendar Integration → Social/Growth

5. **Calendar Integration Planning** (Next Phase):
   - Decided on macOS EventKit (native) over Google Calendar API
   - Designed CalendarManager.swift with permission handling, event fetching
   - Created smart suggestions algorithm based on free time and goal streaks
   - Designed 4 menu bar UI states for calendar integration

**Files Created**:
- `ROADMAP.md` - Comprehensive product roadmap with 80-20 analysis

**Files Modified**:
- `MenuBarApp/CaptainsLogMenuBar.swift`:
  - Added `todayFocusMinutes` from database via goals-status JSON
  - Fixed `startFocusSession()` to kill old process first
  - Added "Show Widget" button
  - Added play button for goals without tasks
  - Fixed column widths for stable layout

- `FocusWidget/FocusWidgetApp.swift`:
  - Removed click handler and HotkeyManager
  - Added hover-to-show close button

- `src/captains_log/focus/productivity_goals.py`:
  - Added `_get_today_total_focus_minutes()` method
  - Updated `get_goals_status_json()` to include `today_focus_minutes` from database

**Key Code Changes**:

```swift
// Kill old session before starting new one
func startFocusSession(taskName: String, minutes: Int) {
    let stopScript = "pkill -f 'captains-log focus' 2>/dev/null; sleep 0.3"
    // ... run script

    // Clear old status
    let emptyStatus = "{\"active\": false}"
    try? emptyStatus.write(toFile: statusFilePath, ...)

    // Start new session + launch widget
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
        NSWorkspace.shared.open(URL(fileURLWithPath: "/Applications/FocusWidget.app"))
    }
}
```

```python
# Get today's total focus minutes from database
async def _get_today_total_focus_minutes(self) -> float:
    today = date.today().isoformat()
    row = await self.db.fetch_one(
        "SELECT COALESCE(SUM(total_focus_minutes), 0) as total FROM focus_sessions WHERE date = ?",
        (today,)
    )
    return float(row["total"]) if row else 0.0
```

**Next Steps**:
- Implement Calendar Integration using macOS EventKit
- Research existing productivity tools in market
- Add morning/evening notification system
