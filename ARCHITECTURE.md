# Captain's Log -- Architecture

Technical reference for developers working on the Captain's Log codebase.

---

## 1. System Overview

```
+----------------------------------------------------------------------+
|                         macOS Machine                                 |
|                                                                      |
|  +----------------------------+    +-----------------------------+   |
|  |   Captain's Log Daemon     |    |   Menu Bar App (Swift)      |   |
|  |   (Python, launchd)        |    |   CaptainsLogMenuBar.app    |   |
|  |                            |    |                             |   |
|  |  AppMonitor                |    |  Daily focus hours          |   |
|  |  WindowTracker             |    |  Goal list + streaks        |   |
|  |  IdleDetector              |    |  Start/pause/stop session   |   |
|  |  InputMonitor              |    |  Reads focus_status.json    |   |
|  |  ScreenshotCapture         |    +----------+------------------+   |
|  |  Buffer -> SQLite          |               |                      |
|  |  AI Summarizer             |    +----------v------------------+   |
|  |  OptimizationEngine        |    |   Focus Widget (Swift)      |   |
|  |  CloudSync                 |    |   FocusWidget.app           |   |
|  |  NotificationScheduler     |    |                             |   |
|  +---+----+-------------------+    |  Ambient timer + session    |   |
|      |    |                        |  dots, off-goal indicator   |   |
|      |    |  writes                |  Reads focus_status.json    |   |
|      |    v                        +-----------------------------+   |
|  +---+----+-------------------+                                      |
|  |   SQLite (WAL mode)        |    +-----------------------------+   |
|  |   ~/Library/App Support/   |    |   Daemon Watchdog (bash)    |   |
|  |   CaptainsLog/             |    |   launchd, every 60s        |   |
|  |   captains_log.db          |    |                             |   |
|  +---+------------------------+    |  Checks last DB event +     |   |
|      |                             |  IOKit idle time.           |   |
|      | POST /api/sync/*            |  Kills brain-dead daemon    |   |
|      v                             |  so launchd restarts it.    |   |
|  +-----------------------------+   +-----------------------------+   |
|  |   CloudSync (aiohttp)      |                                     |
+--+---+-------------------------+-------------------------------------+
       |
       | HTTPS
       v
+------+-----------------------------+    +----------------------------+
|   Next.js Frontend (Vercel)        |    |   Supabase (Postgres)      |
|   captainslog.hyperverge.space     +--->|   Auth (Google OAuth)      |
|                                    |    |   daily_stats, summaries   |
|   Dashboard, Timeline, Analytics   |    |   @hyperverge.co only     |
+------------------------------------+    +----------------------------+
```

### Component summary

| Component | Language | Runtime | Purpose |
|-----------|----------|---------|---------|
| Daemon | Python 3 + PyObjC | launchd (KeepAlive) | Core tracking, AI, sync |
| Menu Bar App | Swift | NSStatusBar | Glanceable daily hours, session controls |
| Focus Widget | Swift | NSWindow (floating) | Ambient timer during focus sessions |
| Watchdog | Bash | launchd (60s cron) | Liveness monitor for daemon |
| Web Dashboard | Next.js / React | Vercel | Cloud dashboard at captainslog.hyperverge.space |
| Cloud DB | Postgres | Supabase | Synced daily stats and AI summaries |
| Local DB | SQLite (WAL) | Embedded | Raw activity data, screenshots, focus sessions |
| CLI | Python (Typer + Rich) | User shell | All commands: `captains-log <cmd>` |

---

## 2. Event Pipeline

An app switch triggers the following chain:

```
User switches apps
       |
       v
NSWorkspace.didActivateApplicationNotification
  (or polling fallback every 2s if events unavailable)
       |
       v
AppMonitor._on_notification()
       |
       +-- Debounce 500ms (ignore rapid CMD+TAB)
       |   If user switches away within 500ms, event is dropped
       |
       v
Orchestrator._on_app_change(app_info)
       |
       +-- WindowTracker.get_window_title(pid)       [AXUIElement API]
       +-- WindowTracker.get_browser_url(bundle_id)   [AppleScript for Chrome/Arc]
       +-- IdleDetector.get_idle_state(bundle_id)     [CGEventSource]
       +-- InputMonitor.get_current_stats()           [keystrokes, clicks, scrolls]
       +-- WorkContextExtractor.extract(url, title)   [GitHub/Slack/Figma parsing]
       |
       v
ActivityEvent created (dataclass)
       |
       +---> Buffer.add(event)                        [in-memory, max 100 events]
       +---> OptimizationEngine.on_activity()          [async task, interrupt/switch analysis]
       +---> ScreenshotCapture.capture_sync()          [if app changed, 5s min interval]
       |       queued to _pending_screenshots list
       |       saved to DB by _process_pending_screenshots (every 1s)
       |
       v
Every 30s: Buffer.flush() --> SQLite activity_logs table
```

### Event enrichment detail

```
                    +-- bundle_id, app_name, pid, timestamp
                    |
ActivityEvent ------+-- window_title      (from AXUIElement)
                    |-- url               (AppleScript or title parse)
                    |-- idle_seconds      (CGEventSource mouse/keyboard idle)
                    |-- idle_status       (ACTIVE | IDLE_BUT_PRESENT | WATCHING_MEDIA | READING | AWAY)
                    |-- is_fullscreen     (AXUIElement attribute)
                    |-- work_category     (coding | communication | browsing | ...)
                    |-- work_service      (github | slack | figma | ...)
                    |-- work_project      (extracted from URL/title patterns)
                    |-- keystrokes        (count since last app switch)
                    |-- mouse_clicks      (left + right + other)
                    |-- scroll_events     (count)
                    +-- engagement_score  (composite of input activity)
```

---

## 3. Daemon State Machine

```
                  captains-log start
                        |
                        v
  STOPPED ---------> STARTING ---------> RUNNING
                        |                    |
                   (on error)          captains-log stop
                        |              SIGTERM / SIGINT
                        v                    |
                     STOPPED <--- STOPPING <-+
```

### Startup sequence (`Orchestrator.start()`)

1. Create data directories, write PID file
2. Initialize SQLite database (WAL mode, run migrations)
3. Check macOS permissions (Accessibility, Screen Recording)
4. Initialize trackers: IdleDetector, WindowTracker, InputMonitor
5. Initialize ActivityBuffer, AppMonitor (with debounce)
6. Initialize ScreenshotCapture + ScreenshotManager (optional)
7. Start buffer flush loop, register AppMonitor callback
8. Initialize AI summarization: FocusCalculator, BatchProcessor, FiveMinuteSummarizer (optional)
9. Initialize CloudSync (optional)
10. Initialize OptimizationEngine (optional)
11. Initialize NotificationScheduler (optional)
12. Enter NSRunLoop (0.5s intervals) + asyncio event loop

### Shutdown sequence (`Orchestrator.stop()`)

Reverse order: stop NotificationScheduler, OptimizationEngine, CloudSync, Summarizer, BatchProcessor, ScreenshotCapture, InputMonitor, AppMonitor, Buffer (final flush), cancel async tasks, close database, remove PID file.

### Periodic tasks

| Interval | Task | Component |
|----------|------|-----------|
| 0.5s | NSRunLoop tick (process macOS events) | Orchestrator |
| 1s | Save pending app-change screenshots to DB | Orchestrator |
| 30s | Flush event buffer to SQLite | ActivityBuffer |
| 60s | Check if notifications should be sent | NotificationScheduler |
| 5m | Periodic screenshot capture | ScreenshotCapture |
| 5m | Cloud sync (daily stats + summaries) | CloudSync |
| 5m | Generate 5-minute AI summary | FiveMinuteSummarizer |
| 1h | Delete expired screenshots (>7 days) | ScreenshotManager |
| 6h | Process AI summary batch queue | BatchProcessor |

---

## 4. Background Tasks (Parallel)

The daemon runs these concurrent `asyncio.Task` instances:

```
Orchestrator._tasks[]
  |
  +-- _periodic_screenshot_cleanup()     1h loop, deletes files + marks DB records
  +-- _process_pending_screenshots()     1s loop, saves app-change screenshots to DB
  +-- _periodic_notification_check()     60s loop, checks digest/briefing/health times
  +-- buffer._flush_loop()               30s loop, writes events to SQLite
  +-- screenshot_capture._capture_loop() 5m loop, periodic screen capture
  +-- summarizer._summarize_loop()       5m loop, generates AI summaries
  +-- batch_processor._process_loop()    6h loop, processes queued summaries via Claude
  +-- cloud_sync._sync_loop()            5m loop, pushes to Supabase
  +-- optimization_engine tasks          Per-activity async analysis
```

All tasks respect `self._running` flag and handle `CancelledError` for clean shutdown.

---

## 5. Focus Mode State Machine

```
                captains-log focus -g "Deep work" -t 120 --sessions 4
                        |
                        v
  IDLE -------> WORK (25 min) -------> SHORT BREAK (5 min) --+
                   ^    |                                     |
                   |    +--- pomodoro_count < 4 --------------+
                   |    |
                   |    +--- pomodoro_count == 4 ---> LONG BREAK (15 min)
                   |                                          |
                   +------------------------------------------+
                              (cycle repeats)

  At any point:
    captains-log focus-timer pause  -->  Timer paused (via focus_control.json)
    captains-log focus-timer resume -->  Timer resumed
    captains-log focus-stop         -->  Session ends, stats saved
```

### Component interaction

```
CLI (captains-log focus)
  |
  v
WidgetController
  |
  +-- PomodoroTimer           State machine: WORK/BREAK/LONG_BREAK
  |     on_tick -> update status file every second
  |     on_phase_complete -> advance to next phase
  |
  +-- GoalTracker             Reads/writes focus_goals, focus_sessions tables
  |     tracks pomodoro count, focus minutes, streaks
  |
  +-- ActivityMatcher          Evaluates if current app matches goal criteria
  |     match_criteria: apps=["VS Code","Terminal"], projects=["captains-log"]
  |
  +-- FocusWidget (PyObjC)     Floating NSWindow overlay
  |     displays timer, session dots, off-goal amber border
  |
  +-- focus_status.json        Written every tick, read by Swift apps
        {active, goal_name, time_remaining, pomodoro_count, estimated_sessions, ...}
```

### Session dots display

```
estimated_sessions = 6, pomodoro_count = 3

  Display: ●●●○○○   (3 of 6 complete)
```

---

## 6. Data Flow: Local to Cloud to Dashboard

```
+-------------------+     +-----------------+     +------------------------+
|   Python Daemon   |     |   Next.js API   |     |   Supabase Postgres    |
|                   |     |   (Vercel)      |     |                        |
|  activity_logs    |     |                 |     |  daily_stats           |
|  summaries        +---->+  POST /api/     +---->+  summaries             |
|  daily_summaries  |     |    sync/daily   |     |  devices               |
|                   |     |    sync/summaries|    |                        |
+-------------------+     |                 |     +----------+-------------+
                          |  GET /api/      |                |
                          |    stats/:date  |<---------------+
                          |    timeline     |
                          |    apps         |
                          +--------+--------+
                                   |
                                   v
                          +--------+--------+
                          |   React UI      |
                          |                 |
                          |  Dashboard page |
                          |  Timeline page  |
                          |  Analytics page |
                          |  Apps page      |
                          +-----------------+
```

### Sync details

- **Interval**: Every 5 minutes (configurable via `sync_interval_minutes`)
- **Deduplication**: `synced_at` column on summaries table. Only rows where `synced_at IS NULL` are uploaded.
- **Device ID**: UUID generated on first run, stored in config. Identifies this machine in cloud.
- **Auth**: Supabase service role key. Dashboard uses Google OAuth restricted to `@hyperverge.co`.

---

## 7. Database Schema (Key Tables)

Schema version: 9. Migrations run automatically on startup.

### activity_logs

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| timestamp | DATETIME | UTC, when app became active |
| app_name | TEXT | Display name (e.g., "Google Chrome") |
| bundle_id | TEXT | macOS bundle ID (e.g., "com.google.Chrome") |
| window_title | TEXT | Active window title |
| url | TEXT | Browser URL if applicable |
| idle_seconds | REAL | Seconds since last input |
| idle_status | TEXT | ACTIVE, IDLE_BUT_PRESENT, WATCHING_MEDIA, READING, AWAY |
| is_fullscreen | BOOLEAN | Whether app was fullscreen |
| work_category | TEXT | coding, communication, browsing, writing, design, ... |
| work_service | TEXT | github, slack, figma, notion, ... |
| work_project | TEXT | Extracted project name |
| keystrokes | INTEGER | Key presses since last app switch |
| mouse_clicks | INTEGER | Click count since last app switch |
| engagement_score | REAL | Composite input activity metric |

Indexes: `timestamp`, `bundle_id`, `created_at`

### summaries

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| period_start | DATETIME | 5-minute window start |
| period_end | DATETIME | 5-minute window end |
| primary_app | TEXT | Most-used app in period |
| activity_type | TEXT | coding, communication, browsing, ... |
| focus_score | INTEGER | 0-10, multi-factor algorithm |
| key_activities | JSON | List of activity descriptions |
| context | TEXT | AI-generated narrative |
| context_switches | INTEGER | App switches in period |
| tags | JSON | Auto-generated tags |
| model_used | TEXT | e.g., "claude-haiku-4-5-20251001" |
| synced_at | DATETIME | NULL until synced to cloud |

### screenshots

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| timestamp | DATETIME | UTC capture time |
| file_path | TEXT | Path to WebP file |
| file_size_bytes | INTEGER | Typically ~80KB |
| expires_at | DATETIME | timestamp + 7 days |
| is_deleted | BOOLEAN | Soft delete flag |

### focus_goals

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | TEXT | "Deep work on captains-log" |
| goal_type | TEXT | app_based, project_based, category_based |
| target_minutes | INTEGER | Daily target (default 120) |
| estimated_sessions | INTEGER | Pomodoro sessions (default 4) |
| match_criteria | JSON | `{"apps": ["VS Code"], "projects": [...]}` |
| is_active | BOOLEAN | |

### focus_sessions

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| goal_id | INTEGER FK | References focus_goals |
| date | DATE | Session date |
| pomodoro_count | INTEGER | Completed pomodoros |
| total_focus_minutes | REAL | Time on-goal |
| total_break_minutes | REAL | Break time |
| off_goal_minutes | REAL | Time in non-goal apps |

### pomodoro_history

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| session_id | INTEGER FK | References focus_sessions |
| started_at | DATETIME | |
| ended_at | DATETIME | |
| duration_minutes | REAL | |
| was_completed | BOOLEAN | Did user finish the full pomodoro? |
| interruption_count | INTEGER | Context switches during pomodoro |
| primary_app | TEXT | Most-used app during pomodoro |

### Other tables

- **daily_summaries** -- Aggregated daily stats (app usage JSON, peak hour, narrative)
- **weekly_summaries** -- Weekly aggregations (trends, focus trend, accomplishments)
- **summary_queue** -- Batch API processing queue (status: pending/processing/complete/failed)
- **sync_queue** -- Cloud upload queue
- **productivity_goals** -- Quarterly/half-year objectives with deadlines
- **system_metrics** -- CPU, memory, DB size snapshots
- **error_log** -- Component errors with stack traces

---

## 8. File-Based IPC

Components communicate via files in `~/Library/Application Support/CaptainsLog/`. No direct process-to-process communication.

```
+------------------+                    +-------------------+
|  Python Daemon   |  writes every 1s   |  Swift Menu Bar   |
|  (WidgetController) +--------------->  |  (reads every 5s) |
|                  |  focus_status.json  +-------------------+
|                  |                    +-------------------+
|                  +--------------->   |  Swift Widget     |
|                  |  focus_status.json  |  (reads every 5s) |
+------------------+                    +-------------------+

+------------------+                    +-------------------+
|  OptimizationEngine | writes on event |  Widget / CLI     |
|                  +--------------->   |  (reads on demand) |
|                  | optimization_     +-------------------+
|                  | status.json
+------------------+

+------------------+                    +-------------------+
|  CLI (focus-timer | writes command    |  Python Daemon    |
|  pause/resume)   +--------------->   |  (polls every 1s) |
|                  | focus_control.json +-------------------+
+------------------+

+------------------+                    +-------------------+
|  Python Daemon   |  writes on start   |  Watchdog (bash)  |
|                  +--------------->   |  reads every 60s  |
|                  |  daemon.pid        +-------------------+
+------------------+
```

### File formats

**focus_status.json** (daemon writes, Swift apps read):
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

**focus_control.json** (CLI writes, daemon reads):
```json
{
  "command": "pause",
  "timestamp": "2026-04-06T14:30:00"
}
```

**daemon.pid** (daemon writes, watchdog reads):
```
12345
```

---

## 9. CLI Command Map

All commands: `captains-log <command> [options]`

### Daemon management

| Command | Description |
|---------|-------------|
| `start [-f]` | Start daemon (background or foreground with `-f`) |
| `stop` | Stop daemon (SIGTERM) |
| `status` | Show running/stopped, PID, uptime |
| `health` | Detailed component health (DB, buffer, permissions, sync) |
| `logs [-f]` | View daemon logs (follow with `-f`) |
| `install` | Install launchd plist for auto-start |
| `install-status` | Check launchd installation |
| `dashboard` | Start local FastAPI web dashboard |

### Daily insights

| Command | Description |
|---------|-------------|
| `today` | Duration breakdown by app and category, focus hours, most focused hour |
| `digest [--date] [--notify]` | Generate daily digest, optionally send as macOS notification |
| `recall "query"` | Natural language query via Claude (e.g., "what did I work on Thursday") |

### Weekly and patterns

| Command | Description |
|---------|-------------|
| `week` | This week vs last week, daily breakdown, top apps, projections |
| `weekly` | Weekly digest with trends |
| `insights` | Detected patterns from 14+ days of history (peak hours, rhythms) |

### Focus sessions

| Command | Description |
|---------|-------------|
| `focus -g NAME -t MIN -a APPS [-s N]` | Start focus session with goal, duration, allowed apps, sessions |
| `focus-status` | Today's focus sessions |
| `focus-goals [--create]` | List or create goals |
| `focus-timer pause\|resume\|skip` | Control running timer |
| `focus-stop` | End current focus session |

### AI summaries

| Command | Description |
|---------|-------------|
| `summaries` | Show recent AI summaries |
| `summaries-backfill --hours N` | Generate summaries for historical data |
| `summaries-process` | Process pending batch queue |

### Optimization

| Command | Description |
|---------|-------------|
| `optimize` | DEAL breakdown, interrupts, context switches |
| `optimize-briefing` | Morning summary with wins and focus tips |
| `optimize-report` | Weekly comprehensive report |
| `optimize-profile` | Set role, hourly rate, savings goal |

---

## 10. Reliability Architecture

```
+---------------------------------------------------------------+
|  Layer 0: launchd (KeepAlive=true, RunAtLoad=true)            |
|  Process-level restart. If daemon crashes, launchd restarts   |
|  it within ThrottleInterval (30s).                            |
+---------------------------------------------------------------+
        |
        v
+---------------------------------------------------------------+
|  Layer 1: Watchdog (60s cron via launchd)                     |
|  scripts/daemon-watchdog.sh                                   |
|                                                               |
|  Detects brain-dead daemon:                                   |
|    1. Read PID file, check process alive                      |
|    2. Check daemon uptime > 2 min (skip freshly started)      |
|    3. Read IOKit idle time (is user active?)                   |
|    4. Query SQLite: age of most recent event                  |
|    5. If event > 30 min old AND user idle < 5 min:            |
|       KILL daemon --> launchd restarts it                     |
|       Send macOS notification about restart                   |
+---------------------------------------------------------------+
        |
        v
+---------------------------------------------------------------+
|  Layer 2: Smart Health Alerts                                 |
|  NotificationScheduler checks health_alerts config            |
|                                                               |
|  If no activity for 1 hour during work hours (9-18):          |
|    Check IOKit idle time first -- skip if user is away        |
|    Only alert if user is active but daemon isn't logging      |
+---------------------------------------------------------------+
        |
        v
+---------------------------------------------------------------+
|  Layer 3: Log Rotation                                        |
|  RotatingFileHandler: 1 MB max, 5 backups (6 MB total cap)   |
|  Watchdog log: rotated at 1 MB by watchdog script itself      |
+---------------------------------------------------------------+
        |
        v
+---------------------------------------------------------------+
|  Layer 4: Sync Deduplication                                  |
|  `synced_at` column on summaries table                        |
|  CloudSync only uploads rows where synced_at IS NULL          |
|  Prevents re-uploading same data every 5-minute sync cycle    |
+---------------------------------------------------------------+
```

### Failure recovery scenarios

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Daemon crashes | launchd detects exit | Auto-restart within 30s |
| Daemon brain-dead (alive but no events) | Watchdog checks DB + idle | Kill process, launchd restarts |
| User away during check | Watchdog reads IOKit idle | No action (avoids false positives) |
| Database locked | WAL mode + 5000ms busy timeout | Retry with backoff |
| Cloud sync fails | HTTP error caught in sync loop | Retry next 5-minute cycle |
| AI API fails | Exception caught in summarizer | Retry with exponential backoff |

---

## 11. Privacy and Security

### Data locality

- All raw activity data (app names, window titles, URLs, screenshots) stays on the local machine in SQLite.
- Only aggregated daily stats and AI-generated summaries are synced to cloud.
- Screenshots are never synced to cloud.

### Excluded apps (screenshots)

Screenshots are skipped when these apps are in the foreground:

- 1Password (`com.1password.1password`, `com.agilebits.onepassword7`)
- Keychain Access (`com.apple.keychainaccess`)
- LastPass (`com.lastpass.lastpassmacdesktop`)
- Bitwarden (`com.bitwarden.desktop`)

Configurable via `config.yaml` under `screenshots.excluded_apps`.

### Screenshot retention

- Default retention: 7 days
- Cleanup runs every hour
- Files are deleted from disk, DB records marked `is_deleted = TRUE`
- WebP format, ~80 KB per image, max 1280px width

### Cloud authentication

- Supabase with Google OAuth
- Domain restriction: only `@hyperverge.co` email addresses can authenticate
- Service role key for daemon-to-cloud sync (not exposed to browser)

### macOS permissions required

| Permission | Used for | Fallback if denied |
|------------|----------|--------------------|
| Accessibility | Window titles, URLs via AXUIElement | Titles unavailable, tracking continues |
| Screen Recording | Screenshot capture | Screenshots disabled, tracking continues |
| Notifications | Daily digest, health alerts | Notifications silent, CLI still works |

---

## 12. Key Design Decisions

### Event-based tracking over polling

NSWorkspace `didActivateApplicationNotification` fires on app switch. CPU usage: <0.5%. Polling fallback (every 2s) activates automatically if events are not received (e.g., launchd background context).

### SQLite with WAL mode

Write-Ahead Logging allows concurrent reads while daemon writes. Busy timeout: 5000ms. All access via `aiosqlite` for async compatibility with the daemon's event loop.

### Debounce at 500ms (configurable to 2000ms)

Filters rapid CMD+TAB switching and trackpad swipe gestures. A 500ms window means the user must stay on an app for at least 500ms before it is recorded. App-change screenshots use a separate 5-second minimum interval to avoid disk thrash.

### Duration calculated from event gaps

Time-in-app is derived from the gap between consecutive `activity_logs` entries, not from explicit start/stop tracking. A 30-minute cap prevents inflated durations when the daemon stops and restarts. Events with `idle_status = AWAY` are excluded from productive time.

### Batch API for AI summaries (50% cost savings)

Claude Haiku 4.5 processes 5-minute activity windows. Default mode: queue summaries and process in batch every 6 hours using Anthropic's Batch API (50% discount). Realtime mode available via config for immediate processing at full price.

### File-based IPC instead of sockets

Swift apps (Menu Bar, Widget) read `focus_status.json` on a timer. This avoids the complexity of IPC protocols, works across language boundaries (Python writes, Swift reads), and is trivially debuggable (`cat focus_status.json`).

### Local-first with optional cloud sync

Raw data never leaves the machine. Cloud sync is opt-in and only pushes aggregated stats and AI summaries. The app is fully functional without any cloud connection.

### Polling fallback for NSWorkspace

NSWorkspace notifications require an active WindowServer connection, which may not be available in launchd background contexts. After 10 seconds with no events, the daemon switches to polling the frontmost application every 2 seconds, providing equivalent functionality.

### UTC timestamps everywhere

All timestamps stored in the database are UTC. Conversion to local time happens only at display time (CLI output, dashboard rendering). This avoids timezone-related bugs and simplifies cloud sync across potential future devices.

---

## Appendix: File Tree (Key Files)

```
captains-log/
  src/captains_log/
    core/
      config.py               Pydantic config with YAML support
      orchestrator.py          Main daemon coordinator
      permissions.py           macOS permission checks
    trackers/
      app_monitor.py           NSWorkspace events + polling fallback
      window_tracker.py        AXUIElement titles, AppleScript URLs
      idle_detector.py         CGEventSource idle time
      input_monitor.py         Keyboard/mouse event counting
      screenshot_capture.py    CoreGraphics screen capture
      buffer.py                In-memory event buffer with periodic flush
      work_context.py          URL/title parsing for service/project
    storage/
      database.py              SQLite schema (v9), migrations, async access
      screenshot_manager.py    Screenshot file + DB lifecycle
    ai/
      claude_client.py         Anthropic API wrapper with vision
      batch_processor.py       Queue management, batch API
      prompts.py               Prompt templates
      schemas.py               Pydantic response models
    summarizers/
      five_minute.py           5-min window summarizer
      focus_calculator.py      Multi-factor focus score (0-10)
      duration_calculator.py   Time-in-app from event gaps
    insights/
      pattern_detector.py      Peak hours, rhythms, switch spikes
    notifications/
      notifier.py              macOS notifications via osascript
      daily_digest.py          Evening digest generator
      weekly_digest.py         Weekly digest generator
      scheduler.py             Timed notification dispatch
    optimization/
      schemas.py               Data models
      interrupt_detector.py    Communication app interrupts
      context_switch_analyzer.py  Switch cost analysis
      deal_classifier.py       Delegate/Eliminate/Automate/Leverage
      meeting_fragmentation.py Swiss Cheese Score
      daily_briefing.py        Morning summary
      weekly_report.py         Weekly analysis
      nudge_system.py          Real-time nudges
      optimization_engine.py   Engine coordinator
    focus/
      pomodoro.py              Timer state machine
      activity_matcher.py      Goal criteria matching
      goal_tracker.py          Goal + session persistence
    widget/
      widget_controller.py     Coordinates timer, tracker, widget
      focus_widget.py          PyObjC floating overlay
    sync/
      cloud_sync.py            aiohttp sync to Supabase via Vercel
    cli/
      main.py                  Typer CLI (all commands)
      install.py               launchd plist installation
    web/
      app.py                   FastAPI local dashboard
      routes/                  API and page routes
      templates/               Jinja2 HTML templates
  MenuBarApp/
    CaptainsLogMenuBar.swift   Native Swift menu bar app
    build.sh                   Build script
    Info.plist                 App bundle config
  FocusWidget/
    FocusWidgetApp.swift       Native Swift floating widget
  frontend/                    Next.js cloud dashboard
    src/app/                   App router pages
    src/components/            React UI components
    src/lib/                   API client, auth, types
  scripts/
    daemon-watchdog.sh         Liveness watchdog (launchd cron)
  resources/launchd/           launchd plist templates
  pyproject.toml               Python dependencies
  VERSION                      Current version number
```
