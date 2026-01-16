# Captain's Log - Installation

## One-Line Install

```bash
curl -fsSL https://raw.githubusercontent.com/hyperkishore/captains-log/main/installer/install.sh | bash
```

## What Gets Installed

- **Captain's Log daemon** - Background service tracking your activity
- **CLI tool** - `captains-log` command for managing the tracker
- **Web Dashboard** - React-based dashboard at `http://localhost:3000`
- **Auto-start** - Launches automatically on login via launchd

## Requirements

- macOS 12+ (Monterey or later)
- Python 3.10+ (installed automatically if needed)
- Homebrew (installed automatically if needed)

## Post-Installation

### Grant Accessibility Permission

Captain's Log needs Accessibility permission to read window titles:

1. Open **System Settings**
2. Go to **Privacy & Security** → **Accessibility**
3. Enable the toggle for **Terminal** (or your terminal app)

### Start the Dashboard

```bash
captains-log dashboard
```

Then open http://localhost:3000 in your browser.

## Commands

| Command | Description |
|---------|-------------|
| `captains-log status` | Check if daemon is running |
| `captains-log dashboard` | Start the web dashboard |
| `captains-log logs -f` | Follow daemon logs |
| `captains-log health` | Show detailed health info |
| `captains-log stop` | Stop the daemon |
| `captains-log start` | Start the daemon |

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/hyperkishore/captains-log/main/installer/uninstall.sh | bash
```

## Data Locations

| Type | Path |
|------|------|
| Config | `~/Library/Application Support/CaptainsLog/` |
| Logs | `~/Library/Logs/CaptainsLog/` |
| Database | `~/Library/Application Support/CaptainsLog/captains_log.db` |
| Screenshots | `~/Library/Application Support/CaptainsLog/screenshots/` |

## Troubleshooting

### Daemon won't start

1. Check accessibility permission is granted
2. View logs: `captains-log logs -f`
3. Try manual start: `captains-log start -f` (foreground mode)

### No activity being tracked

1. Ensure Terminal has Accessibility permission
2. Check daemon status: `captains-log status`
3. Verify with: `captains-log health`

### Dashboard won't load

1. Check if port 3000 is available
2. Try a different port: `captains-log dashboard --port 8080`
