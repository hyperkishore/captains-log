#!/bin/bash
# Captain's Log - Uninstaller
# Usage: curl -fsSL https://raw.githubusercontent.com/hyperkishore/captains-log/main/dist/uninstall.sh | bash

set -e

INSTALL_DIR="$HOME/.local/share/captains-log"
CONFIG_DIR="$HOME/Library/Application Support/CaptainsLog"
LOG_DIR="$HOME/Library/Logs/CaptainsLog"
BIN_DIR="$HOME/.local/bin"
PLIST_NAME="com.captainslog.daemon.plist"
DASHBOARD_PLIST_NAME="com.captainslog.dashboard.plist"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║${NC}            Captain's Log Uninstaller                        ${RED}║${NC}"
echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Confirm
echo -e "${YELLOW}This will remove Captain's Log and all its data.${NC}"
echo ""
read -p "Are you sure you want to uninstall? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}[1/5]${NC} Stopping daemon..."
launchctl unload "$HOME/Library/LaunchAgents/$PLIST_NAME" 2>/dev/null || true
launchctl unload "$HOME/Library/LaunchAgents/$DASHBOARD_PLIST_NAME" 2>/dev/null || true

# Kill any running processes
pkill -f "captains_log" 2>/dev/null || true
pkill -f "captains-log" 2>/dev/null || true

echo -e "${BLUE}[2/5]${NC} Removing launchd plists..."
rm -f "$HOME/Library/LaunchAgents/$PLIST_NAME"
rm -f "$HOME/Library/LaunchAgents/$DASHBOARD_PLIST_NAME"

echo -e "${BLUE}[3/5]${NC} Removing installation files..."
rm -rf "$INSTALL_DIR"
rm -f "$BIN_DIR/captains-log"

echo -e "${BLUE}[4/5]${NC} Removing configuration..."
rm -rf "$CONFIG_DIR"

echo -e "${BLUE}[5/5]${NC} Removing logs..."
rm -rf "$LOG_DIR"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}            Uninstall Complete                               ${GREEN}║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Captain's Log has been removed from your system."
echo ""
echo "Note: You may want to manually remove the PATH entry from ~/.zshrc"
echo ""
