#!/bin/bash

# <xbar.title>Captain's Log</xbar.title>
# <xbar.version>v0.2.0</xbar.version>
# <xbar.author>Captain's Log</xbar.author>
# <xbar.author.github>hyperkishore</xbar.author.github>
# <xbar.desc>Focus timer and activity tracking</xbar.desc>
# <xbar.dependencies>python3,sqlite3</xbar.dependencies>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
# <swiftbar.hideSwiftBar>true</swiftbar.hideSwiftBar>

VERSION="0.2.0"
DB_PATH="$HOME/Library/Application Support/CaptainsLog/captains_log.db"
VENV_PATH="$HOME/Desktop/Claude-experiments/captains-log/.venv"
DASHBOARD_URL="http://127.0.0.1:8082"
WIDGET_APP="/Applications/FocusWidget.app"

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "◐"
    echo "---"
    echo "Captain's Log | size=13"
    echo "Database not found | color=#888888 size=11"
    exit 0
fi

# Get today's date
TODAY=$(date +%Y-%m-%d)

# Check daemon status - look for python process running captains_log
if pgrep -f "captains_log" > /dev/null 2>&1; then
    DAEMON_STATUS="●"
    DAEMON_COLOR="#34C759"
else
    DAEMON_STATUS="○"
    DAEMON_COLOR="#FF3B30"
fi

# Check dashboard status with timeout
DASH_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 1 "$DASHBOARD_URL" 2>/dev/null)
if [ "$DASH_CODE" = "200" ]; then
    DASHBOARD_STATUS="●"
    DASHBOARD_COLOR="#34C759"
else
    DASHBOARD_STATUS="○"
    DASHBOARD_COLOR="#8E8E93"
fi

# Get focus session info
FOCUS_SESSION=$(sqlite3 "$DB_PATH" "
    SELECT fg.name, fs.total_focus_minutes, fg.target_minutes, fs.pomodoro_count, fs.completed
    FROM focus_sessions fs
    JOIN focus_goals fg ON fs.goal_id = fg.id
    WHERE fs.date = '$TODAY'
    ORDER BY fs.created_at DESC
    LIMIT 1
" 2>/dev/null)

# Parse focus session
if [ -n "$FOCUS_SESSION" ]; then
    IFS='|' read -r GOAL_NAME FOCUS_MINS TARGET_MINS POMODOROS COMPLETED <<< "$FOCUS_SESSION"
    FOCUS_MINS=${FOCUS_MINS%.*}  # Remove decimal
    FOCUS_MINS=${FOCUS_MINS:-0}
    TARGET_MINS=${TARGET_MINS:-60}
    POMODOROS=${POMODOROS:-0}
    PROGRESS=$((FOCUS_MINS * 100 / TARGET_MINS))
    HAS_SESSION=true
else
    HAS_SESSION=false
    POMODOROS=0
fi

# Build pomodoro circles (8 total)
POMO_CIRCLES=""
for i in {1..8}; do
    if [ $i -le ${POMODOROS:-0} ]; then
        POMO_CIRCLES="${POMO_CIRCLES}●"
    else
        POMO_CIRCLES="${POMO_CIRCLES}○"
    fi
done

# Menu bar icon - show pomodoro count or status
if [ "$HAS_SESSION" = true ] && [ "$COMPLETED" = "1" ]; then
    echo "✓ $POMODOROS"
elif [ "$HAS_SESSION" = true ]; then
    echo "◐ $POMODOROS"
else
    echo "◐"
fi

echo "---"

# Header with status indicators on separate lines for proper coloring
echo "Captain's Log | size=13"
echo "$DAEMON_STATUS Daemon | color=$DAEMON_COLOR size=10"
echo "$DASHBOARD_STATUS Dashboard | color=$DASHBOARD_COLOR size=10 href=$DASHBOARD_URL"
echo "---"

# Focus Mode Section
if [ "$HAS_SESSION" = true ]; then
    if [ "$COMPLETED" = "1" ]; then
        echo "✓ $GOAL_NAME | color=#34C759 size=12 bash=open param1=$WIDGET_APP terminal=false"
    else
        echo "◐ $GOAL_NAME | size=12 bash=open param1=$WIDGET_APP terminal=false"
    fi
    echo "$POMO_CIRCLES | font=SFMono-Regular size=12 color=#FF6B6B"
    echo "${FOCUS_MINS}m / ${TARGET_MINS}m ($PROGRESS%) | size=11 color=#8E8E93"
else
    echo "No active session | color=#8E8E93 size=11"
fi

echo "---"

# Start Focus Session submenu
echo "Start Focus Session"
echo "--Deep Work (2h) | bash=bash param1=-c param2='\"$VENV_PATH/bin/captains-log\" focus -g \"Deep Work\" -t 120 -a \"VS Code,Terminal,Cursor\" --no-widget && open \"$WIDGET_APP\"' terminal=false"
echo "--Writing (1h) | bash=bash param1=-c param2='\"$VENV_PATH/bin/captains-log\" focus -g \"Writing\" -t 60 -a \"Notion,Obsidian\" --no-widget && open \"$WIDGET_APP\"' terminal=false"
echo "--Communication (30m) | bash=bash param1=-c param2='\"$VENV_PATH/bin/captains-log\" focus -g \"Communication\" -t 30 -a \"Slack,Mail,Messages\" --no-widget && open \"$WIDGET_APP\"' terminal=false"
echo "--Custom... | bash=$VENV_PATH/bin/captains-log param1=focus terminal=true"

echo "---"

# Footer with version - no more separator after this
echo "v$VERSION | size=10 color=#8E8E93"
