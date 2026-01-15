# Captain's Log 🚢

A macOS personal activity tracking system with AI-powered insights. Passively captures your digital activity and synthesizes it into actionable insights.

## Features

- **Event-based Activity Tracking** - Near-zero CPU usage with NSWorkspace notifications
- **Window Title & URL Extraction** - Via macOS Accessibility API
- **Idle Detection** - Context-aware classification (Active, Reading, Watching Media, Away)
- **Web Dashboard** - Real-time visualization of your activity
- **AI Summaries** (Coming Soon) - Claude-powered 5-minute, daily, and weekly summaries

## Requirements

- macOS 12.3+ (Monterey or later)
- Python 3.11+
- Accessibility permission (for window titles)
- Screen Recording permission (for screenshots, optional)

## Quick Start

### Using Homebrew (Recommended)

```bash
# Add the tap and install
brew tap hyperkishore/captains-log
brew install captains-log

# Start the service (runs at login)
brew services start captains-log

# Open the dashboard
captains-log dashboard
# Then open http://127.0.0.1:8080
```

### Using the Install Script

```bash
# Clone the repository
git clone https://github.com/hyperkishore/captains-log.git
cd captains-log

# Run the installer
./scripts/install.sh
```

### Using Make

```bash
# Clone the repository
git clone https://github.com/hyperkishore/captains-log.git
cd captains-log

# Install
make install

# Activate virtual environment
source .venv/bin/activate

# Start tracking (foreground mode for testing)
captains-log start -f

# In another terminal, start the dashboard
captains-log dashboard
```

### Using pip

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .

# Run
captains-log start -f
```

## CLI Commands

```bash
# Daemon control
captains-log start           # Start daemon (background)
captains-log start -f        # Start in foreground
captains-log stop            # Stop daemon
captains-log status          # Show status
captains-log health          # Detailed health check

# Dashboard
captains-log dashboard       # Start web UI at http://127.0.0.1:8080

# Logs & Config
captains-log logs            # View recent logs
captains-log logs -f         # Follow logs (tail -f)
captains-log config-show     # Show configuration

# Auto-start on login
captains-log install         # Install launchd service
captains-log uninstall       # Remove launchd service
captains-log install-status  # Check service status

# Other
captains-log version         # Show version
```

## Configuration

Configuration file: `~/.config/captains-log/config.yaml`

```yaml
# Activity tracking
tracking:
  buffer_flush_seconds: 30    # How often to write to database
  idle_threshold_seconds: 300 # Time before marking as idle
  debounce_ms: 500           # Ignore app switches shorter than this

# Screenshot capture (Phase 2)
screenshots:
  enabled: true
  interval_minutes: 5
  quality: 80                # WebP quality (1-100)
  retention_days: 7

# AI Summarization (Phase 3)
summarization:
  enabled: true
  model: claude-haiku-4-5-20241022
  use_batch_api: true        # 50% cost savings

# Web dashboard
web:
  host: 127.0.0.1            # Localhost only
  port: 8080
```

## Data Storage

All data is stored locally:

- **Database**: `~/Library/Application Support/CaptainsLog/captains_log.db`
- **Screenshots**: `~/Library/Application Support/CaptainsLog/screenshots/`
- **Logs**: `~/Library/Logs/CaptainsLog/`
- **Config**: `~/.config/captains-log/`

## macOS Permissions

Captain's Log requires certain permissions to function:

1. **Accessibility** (Required) - For reading window titles and URLs
   - System Preferences → Privacy & Security → Accessibility → Add your terminal/app

2. **Screen Recording** (Optional) - For screenshot capture
   - System Preferences → Privacy & Security → Screen Recording → Add your terminal/app

The app will prompt you on first run and provide instructions.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Captain's Log                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐               │
│  │  Activity Layer  │    │  Web Dashboard   │               │
│  │                  │    │                  │               │
│  │  • App Monitor   │    │  • Timeline View │               │
│  │  • Window Titles │    │  • App Stats     │               │
│  │  • URL Extract   │    │  • Charts        │               │
│  │  • Idle Detect   │    │  • API Endpoints │               │
│  └────────┬─────────┘    └────────┬─────────┘               │
│           │                       │                          │
│           └───────────┬───────────┘                          │
│                       │                                      │
│              ┌────────▼────────┐                             │
│              │  SQLite (WAL)   │                             │
│              │  activity_logs  │                             │
│              │  screenshots    │                             │
│              │  summaries      │                             │
│              └─────────────────┘                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Development

```bash
# Install with dev dependencies
make install-dev

# Run tests
make test

# Lint code
make lint

# Format code
make format

# Type check
make typecheck
```

## Menu Bar Integration (SwiftBar)

Captain's Log includes a SwiftBar plugin for quick access to your stats from the menu bar.

### Installation

```bash
# Install SwiftBar
brew install --cask swiftbar

# If installed via Homebrew
cp $(brew --prefix)/share/swiftbar/captains-log.1m.sh ~/Library/Application\ Support/SwiftBar/Plugins/

# If installed from source
cp scripts/captains-log.1m.sh ~/Library/Application\ Support/SwiftBar/Plugins/
```

### Features

- Shows today's activity count in menu bar (🚢 123)
- Dropdown with:
  - Today's stats (events, apps, top app, last activity)
  - Top 5 apps for the day
  - Quick link to open dashboard
  - Daemon and dashboard status with start buttons
  - Manual refresh option

## Privacy & Security

- All raw data stays on your local machine
- Database and screenshots are never uploaded without explicit configuration
- API keys are stored in macOS Keychain
- Sensitive apps (password managers, banking) are excluded from capture
- Web dashboard binds to localhost only by default

## Roadmap

- [x] Phase 1: Core Daemon (Activity tracking, CLI, Dashboard)
- [ ] Phase 2: Screenshot Capture (ScreenCaptureKit)
- [ ] Phase 3: AI Summaries (Claude integration)
- [ ] Phase 4: Daily/Weekly Aggregation
- [ ] Phase 5: Cloud Sync (encrypted)
- [ ] Phase 6: External Integrations (Gmail, Calendar, Slack)

## License

MIT License - See LICENSE file for details.
