#!/bin/bash

# <xbar.title>Captain's Log</xbar.title>
# <xbar.version>v0.2.0</xbar.version>
# <xbar.author>Captain's Log</xbar.author>
# <xbar.author.github>hyperkishore</xbar.author.github>
# <xbar.desc>Shows activity tracking stats from Captain's Log</xbar.desc>
# <xbar.dependencies>python3,sqlite3</xbar.dependencies>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>false</swiftbar.hideLastUpdated>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
# <swiftbar.hideSwiftBar>true</swiftbar.hideSwiftBar>

VERSION="0.2.0"
DB_PATH="$HOME/Library/Application Support/CaptainsLog/captains_log.db"
VENV_PATH="$HOME/Desktop/Claude-experiments/captains-log/.venv"
DASHBOARD_URL="http://127.0.0.1:8082"

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "🚢 --"
    echo "---"
    echo "Database not found | color=red"
    echo "Run 'captains-log start' first"
    exit 0
fi

# Get today's date
TODAY=$(date +%Y-%m-%d)

# Query database for stats
read -r TOTAL_TODAY TOP_APP UNIQUE_APPS <<< $(sqlite3 "$DB_PATH" "
    SELECT
        (SELECT COUNT(*) FROM activity_logs WHERE date(timestamp) = '$TODAY'),
        (SELECT app_name FROM activity_logs WHERE date(timestamp) = '$TODAY' GROUP BY app_name ORDER BY COUNT(*) DESC LIMIT 1),
        (SELECT COUNT(DISTINCT app_name) FROM activity_logs WHERE date(timestamp) = '$TODAY')
" 2>/dev/null | tr '|' ' ')

# Handle empty results
TOTAL_TODAY=${TOTAL_TODAY:-0}
TOP_APP=${TOP_APP:-"None"}
UNIQUE_APPS=${UNIQUE_APPS:-0}

# Get last activity
LAST_APP=$(sqlite3 "$DB_PATH" "SELECT app_name FROM activity_logs ORDER BY timestamp DESC LIMIT 1" 2>/dev/null)
LAST_APP=${LAST_APP:-"None"}

# Menu bar display
if [ "$TOTAL_TODAY" -eq 0 ]; then
    echo "🚢 0"
else
    echo "🚢 $TOTAL_TODAY"
fi

echo "---"
echo "Captain's Log v$VERSION | size=14"
echo "---"
echo "Today's Stats | color=#666666 size=11"
echo "📊 $TOTAL_TODAY events | font=SFMono-Regular"
echo "📱 $UNIQUE_APPS apps | font=SFMono-Regular"
echo "⭐ Top: $TOP_APP | font=SFMono-Regular"
echo "🕐 Last: $LAST_APP | font=SFMono-Regular"
echo "---"

# Top 5 apps today
echo "Top Apps Today | color=#666666 size=11"
sqlite3 "$DB_PATH" "
    SELECT app_name, COUNT(*) as count
    FROM activity_logs
    WHERE date(timestamp) = '$TODAY'
    GROUP BY app_name
    ORDER BY count DESC
    LIMIT 5
" 2>/dev/null | while IFS='|' read -r app count; do
    if [ -n "$app" ]; then
        echo "$app ($count) | font=SFMono-Regular"
    fi
done

echo "---"

# Focus Mode Section
echo "Focus Mode | color=#666666 size=11"

# Check for active focus session today
FOCUS_SESSION=$(sqlite3 "$DB_PATH" "
    SELECT fg.name, fs.total_focus_minutes, fg.target_minutes, fs.pomodoro_count, fs.completed
    FROM focus_sessions fs
    JOIN focus_goals fg ON fs.goal_id = fg.id
    WHERE fs.date = '$TODAY'
    ORDER BY fs.created_at DESC
    LIMIT 1
" 2>/dev/null)

if [ -n "$FOCUS_SESSION" ]; then
    IFS='|' read -r GOAL_NAME FOCUS_MINS TARGET_MINS POMODOROS COMPLETED <<< "$FOCUS_SESSION"
    FOCUS_MINS=${FOCUS_MINS%.*}  # Remove decimal
    PROGRESS=$((FOCUS_MINS * 100 / TARGET_MINS))

    if [ "$COMPLETED" = "1" ]; then
        echo "🎉 $GOAL_NAME COMPLETE! | color=green font=SFMono-Regular"
    else
        echo "🍅 $GOAL_NAME | font=SFMono-Regular"
        echo "   ${FOCUS_MINS}m / ${TARGET_MINS}m ($PROGRESS%) | font=SFMono-Regular color=#888888"
    fi
    echo "   Pomodoros: $POMODOROS | font=SFMono-Regular color=#888888"
else
    echo "No focus session today | color=#888888 font=SFMono-Regular"
fi

echo "---"

# Focus Quick Actions
echo "Start Focus Session"
echo "--🎯 Deep Work (2h) | bash='$VENV_PATH/bin/captains-log' param1=focus param2=-g param3='Deep Work' param4=-t param5=120 param6=-a param7='VS Code,Terminal,Cursor' terminal=true"
echo "--📝 Writing (1h) | bash='$VENV_PATH/bin/captains-log' param1=focus param2=-g param3='Writing' param4=-t param5=60 param6=-a param7='Notion,Obsidian,Google Docs' terminal=true"
echo "--💬 Communication (30m) | bash='$VENV_PATH/bin/captains-log' param1=focus param2=-g param3='Communication' param4=-t param5=30 param6=-a param7='Slack,Mail,Messages' terminal=true"
echo "--⚙️ Custom... | bash='$VENV_PATH/bin/captains-log' param1=focus terminal=true"

echo "Focus Status | bash='$VENV_PATH/bin/captains-log' param1=focus-status terminal=true"
echo "Manage Goals | bash='$VENV_PATH/bin/captains-log' param1=focus-goals terminal=true"

echo "---"
echo "Open Dashboard | href=$DASHBOARD_URL"
echo "---"
echo "Status"

# Check if daemon is running
if pgrep -f "captains_log" > /dev/null 2>&1; then
    echo "● Daemon Running | color=green"
else
    echo "○ Daemon Stopped | color=red"
    echo "--Start Daemon | bash='$VENV_PATH/bin/captains-log' param1=start terminal=false refresh=true"
fi

# Check if dashboard is running
if curl -s -o /dev/null -w "%{http_code}" "$DASHBOARD_URL" 2>/dev/null | grep -q "200"; then
    echo "● Dashboard Running | color=green"
else
    echo "○ Dashboard Stopped | color=gray"
    echo "--Start Dashboard | bash='$VENV_PATH/bin/captains-log' param1=dashboard terminal=false refresh=true"
fi

echo "---"
echo "Refresh | refresh=true"
