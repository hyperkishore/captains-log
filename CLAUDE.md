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
- [ ] **Phase 4**: Aggregation - Daily/weekly summaries
- [ ] **Phase 5**: Cloud Sync - Encrypted S3/R2
- [ ] **Phase 6**: Integrations - Gmail, Calendar, Slack

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
- Read the plan file at `~/.claude/plans/zippy-crunching-hickey.md` for current implementation status
- Check the Phase Implementation Status above to understand what's complete

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

### 4. Testing Changes
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
