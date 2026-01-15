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
│   │   └── database.py       # SQLite with WAL mode
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

## Important Patterns

### Activity Event Flow
```
App Change Event → Debounce (500ms) → Enrich with:
  - Window title (Accessibility)
  - URL (browser title parsing)
  - Idle state (CGEventSource)
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
- [ ] **Phase 2**: Screenshot Capture - ScreenCaptureKit, WebP compression
- [ ] **Phase 3**: AI Summaries - Claude Haiku, Batch API
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

## Testing the Application

```bash
# Install
make install
source .venv/bin/activate

# Test daemon
captains-log start -f  # Foreground mode

# Test dashboard (new terminal)
captains-log dashboard
# Open http://127.0.0.1:8080

# Check health
captains-log health
```
