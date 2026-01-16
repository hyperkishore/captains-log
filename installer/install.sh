#!/bin/bash
# Captain's Log v0.1.0 - One-line installer for macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/hyperkishore/captains-log/main/installer/install.sh | bash

set -e

VERSION="0.1.0"
APP_NAME="captains-log"
INSTALL_DIR="$HOME/.local/share/captains-log"
CONFIG_DIR="$HOME/Library/Application Support/CaptainsLog"
LOG_DIR="$HOME/Library/Logs/CaptainsLog"
BIN_DIR="$HOME/.local/bin"
PLIST_NAME="com.captainslog.daemon.plist"
DASHBOARD_PLIST_NAME="com.captainslog.dashboard.plist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}       ${GREEN}Captain's Log v${VERSION}${NC} - Activity Tracker Installer      ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}Error: Captain's Log only supports macOS${NC}"
    exit 1
fi

# Create directories
echo -e "${BLUE}[1/7]${NC} Creating directories..."
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR" "$BIN_DIR"

# Check for Python 3.10+
echo -e "${BLUE}[2/7]${NC} Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 10 ]]; then
        echo -e "${YELLOW}Python $PYTHON_VERSION found, but 3.10+ required${NC}"
        NEED_PYTHON=true
    else
        echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
        NEED_PYTHON=false
    fi
else
    echo -e "${YELLOW}Python 3 not found${NC}"
    NEED_PYTHON=true
fi

# Install Homebrew if needed
if ! command -v brew &> /dev/null; then
    echo -e "${BLUE}[3/7]${NC} Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for this session
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo -e "${BLUE}[3/7]${NC} ${GREEN}✓ Homebrew already installed${NC}"
fi

# Install Python if needed
if [[ "$NEED_PYTHON" == "true" ]]; then
    echo -e "${BLUE}[4/7]${NC} Installing Python 3.12..."
    brew install python@3.12
    PYTHON_CMD="$(brew --prefix)/bin/python3.12"
else
    echo -e "${BLUE}[4/7]${NC} ${GREEN}✓ Python ready${NC}"
    PYTHON_CMD="python3"
fi

# Install pipx for isolated installation
echo -e "${BLUE}[5/7]${NC} Setting up package manager..."
if ! command -v pipx &> /dev/null; then
    brew install pipx
    pipx ensurepath
fi

# Install Captain's Log
echo -e "${BLUE}[6/7]${NC} Installing Captain's Log..."

# Create virtual environment and install
if [[ -d "$INSTALL_DIR/venv" ]]; then
    rm -rf "$INSTALL_DIR/venv"
fi

$PYTHON_CMD -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

# Install from GitHub
pip install --upgrade pip wheel setuptools
pip install "git+https://github.com/hyperkishore/captains-log.git"

# Create wrapper script
cat > "$BIN_DIR/captains-log" << 'WRAPPER'
#!/bin/bash
source "$HOME/.local/share/captains-log/venv/bin/activate"
exec python -m captains_log "$@"
WRAPPER
chmod +x "$BIN_DIR/captains-log"

# Create launchd plist for daemon
echo -e "${BLUE}[7/7]${NC} Setting up auto-start service..."

cat > "$HOME/Library/LaunchAgents/$PLIST_NAME" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.captainslog.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/venv/bin/python</string>
        <string>-m</string>
        <string>captains_log</string>
        <string>start</string>
        <string>--foreground</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/daemon.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/daemon_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>$HOME</string>
</dict>
</plist>
EOF

# Unload existing service if present
launchctl unload "$HOME/Library/LaunchAgents/$PLIST_NAME" 2>/dev/null || true

# Load the service
launchctl load "$HOME/Library/LaunchAgents/$PLIST_NAME"

# Add bin to PATH if not already there
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    SHELL_RC=""
    if [[ -n "$ZSH_VERSION" ]] || [[ "$SHELL" == *"zsh"* ]]; then
        SHELL_RC="$HOME/.zshrc"
    elif [[ -n "$BASH_VERSION" ]] || [[ "$SHELL" == *"bash"* ]]; then
        SHELL_RC="$HOME/.bashrc"
    fi

    if [[ -n "$SHELL_RC" ]] && [[ -f "$SHELL_RC" ]]; then
        if ! grep -q "captains-log" "$SHELL_RC"; then
            echo "" >> "$SHELL_RC"
            echo "# Captain's Log" >> "$SHELL_RC"
            echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_RC"
        fi
    fi
fi

# Request accessibility permissions
echo ""
echo -e "${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║${NC}              ${RED}IMPORTANT: Grant Accessibility Permission${NC}       ${YELLOW}║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Captain's Log needs Accessibility permission to track window titles."
echo ""
echo "1. System Settings will open automatically"
echo "2. Go to: Privacy & Security → Accessibility"
echo "3. Enable the toggle for 'Terminal' (or your terminal app)"
echo ""
read -p "Press Enter to open System Settings..."

# Open System Preferences to Accessibility
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}              ${GREEN}Installation Complete!${NC}                          ${GREEN}║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Captain's Log is now running and will:"
echo "  • Track your application usage automatically"
echo "  • Capture screenshots every 5 minutes"
echo "  • Generate AI-powered work summaries"
echo ""
echo -e "${BLUE}Dashboard:${NC}"
echo "  Start:    captains-log dashboard"
echo "  URL:      http://localhost:3000"
echo ""
echo -e "${BLUE}Commands:${NC}"
echo "  Status:   captains-log status"
echo "  Logs:     captains-log logs -f"
echo "  Stop:     captains-log stop"
echo "  Health:   captains-log health"
echo ""
echo -e "${BLUE}Data Location:${NC}"
echo "  Config:   $CONFIG_DIR"
echo "  Logs:     $LOG_DIR"
echo "  Database: $CONFIG_DIR/captains_log.db"
echo ""
echo -e "${YELLOW}Note:${NC} Run 'source ~/.zshrc' or restart terminal for PATH changes."
echo ""

# Install Node.js and frontend
echo ""
echo -e "${BLUE}[Bonus]${NC} Setting up React dashboard..."

if ! command -v node &> /dev/null; then
    echo "Installing Node.js..."
    brew install node
fi

# Clone and setup frontend
FRONTEND_DIR="$INSTALL_DIR/frontend"
if [[ ! -d "$FRONTEND_DIR" ]]; then
    echo "Downloading frontend..."
    git clone --depth 1 https://github.com/hyperkishore/captains-log.git "$INSTALL_DIR/repo" 2>/dev/null || true
    if [[ -d "$INSTALL_DIR/repo/frontend" ]]; then
        mv "$INSTALL_DIR/repo/frontend" "$FRONTEND_DIR"
        rm -rf "$INSTALL_DIR/repo"
    fi
fi

if [[ -d "$FRONTEND_DIR" ]]; then
    echo "Installing frontend dependencies..."
    cd "$FRONTEND_DIR"
    npm install --silent 2>/dev/null || true

    # Create start-dashboard script
    cat > "$BIN_DIR/captains-log-dashboard" << 'DASHWRAPPER'
#!/bin/bash
cd "$HOME/.local/share/captains-log/frontend"
npm run dev
DASHWRAPPER
    chmod +x "$BIN_DIR/captains-log-dashboard"
    echo -e "${GREEN}✓ Frontend installed${NC}"
fi

echo ""
echo -e "${BLUE}Start the dashboard:${NC}"
echo "  captains-log-dashboard"
echo ""
echo "Then open: http://localhost:3000"
echo ""
