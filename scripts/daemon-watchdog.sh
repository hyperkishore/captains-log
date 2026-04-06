#!/bin/bash
# Captain's Log Daemon Liveness Watchdog
# Runs every 60 seconds via launchd to detect brain-dead daemon processes.
# If the daemon process is alive but hasn't logged events while the user is active,
# it kills the daemon so launchd can restart it.

LOG_DIR="$HOME/Library/Logs/CaptainsLog"
LOG_FILE="$LOG_DIR/watchdog.log"
DB_PATH="$HOME/Library/Application Support/CaptainsLog/captains_log.db"
PID_FILE="$HOME/Library/Application Support/CaptainsLog/daemon.pid"

# Thresholds
IDLE_THRESHOLD=300        # User is "active" if idle < 300 seconds
STALE_THRESHOLD=600       # Daemon is "brain-dead" if last event > 600 seconds old

# Ensure log directory exists
mkdir -p "$LOG_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Rotate log if > 1MB
LOG_SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)
if [ "$LOG_SIZE" -gt 1048576 ]; then
    mv "$LOG_FILE" "${LOG_FILE}.old"
    log "Log rotated"
fi

# Check if daemon process is running
if [ ! -f "$PID_FILE" ]; then
    # No PID file — daemon not managed by us, let launchd handle it
    exit 0
fi

DAEMON_PID=$(cat "$PID_FILE" 2>/dev/null)
if [ -z "$DAEMON_PID" ] || ! kill -0 "$DAEMON_PID" 2>/dev/null; then
    # Daemon process is not running — launchd will restart it
    log "Daemon process not running (PID: ${DAEMON_PID:-unknown}), launchd will handle restart"
    exit 0
fi

# Daemon is running — check if it's actually capturing events

# Get macOS idle time in seconds
IDLE_TIME=$(ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print int($NF/1000000000); exit}')
if [ -z "$IDLE_TIME" ]; then
    log "Could not read idle time, skipping check"
    exit 0
fi

# If user is idle (away from computer), no need to check
if [ "$IDLE_TIME" -ge "$IDLE_THRESHOLD" ]; then
    exit 0
fi

# User is active — check the database for the most recent event
if [ ! -f "$DB_PATH" ]; then
    log "Database not found at $DB_PATH, skipping check"
    exit 0
fi

LAST_EVENT=$(sqlite3 "$DB_PATH" "SELECT MAX(timestamp) FROM activity_logs;" 2>/dev/null)
if [ -z "$LAST_EVENT" ]; then
    log "No events in database, skipping check"
    exit 0
fi

# Calculate age of last event in seconds
LAST_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$LAST_EVENT" "+%s" 2>/dev/null)
if [ -z "$LAST_EPOCH" ]; then
    # Try ISO format with T separator
    LAST_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$LAST_EVENT" "+%s" 2>/dev/null)
fi
if [ -z "$LAST_EPOCH" ]; then
    log "Could not parse last event timestamp: $LAST_EVENT"
    exit 0
fi

NOW_EPOCH=$(date "+%s")
EVENT_AGE=$((NOW_EPOCH - LAST_EPOCH))

# If last event is too old and user is active, daemon is brain-dead
if [ "$EVENT_AGE" -gt "$STALE_THRESHOLD" ]; then
    log "BRAIN-DEAD DETECTED: Last event ${EVENT_AGE}s ago, user idle ${IDLE_TIME}s, killing daemon PID $DAEMON_PID"

    kill "$DAEMON_PID"
    sleep 2

    # Force kill if still alive
    if kill -0 "$DAEMON_PID" 2>/dev/null; then
        log "Daemon did not exit gracefully, sending SIGKILL"
        kill -9 "$DAEMON_PID"
    fi

    # Send macOS notification
    osascript -e 'display notification "Daemon was unresponsive and has been restarted" with title "Captain'\''s Log"' 2>/dev/null

    log "Daemon killed, launchd will restart it"
fi
