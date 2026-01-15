#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚢 Captain's Log Installer"
echo "=========================="
echo

# Check macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}Error: Captain's Log only works on macOS${NC}"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"

if [[ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]]; then
    echo -e "${RED}Error: Python 3.11+ is required (found $PYTHON_VERSION)${NC}"
    echo "Install with: brew install python@3.11"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"

# Determine installation directory
INSTALL_DIR="${CAPTAINS_LOG_DIR:-$HOME/.captains-log}"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$INSTALL_DIR/bin"

echo "Installing to: $INSTALL_DIR"
echo

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install package
echo "Installing Captain's Log..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

pip install --upgrade pip
pip install "$PROJECT_DIR"

# Create wrapper script
cat > "$BIN_DIR/captains-log" << EOF
#!/bin/bash
source "$VENV_DIR/bin/activate"
exec python -m captains_log.cli.main "\$@"
EOF
chmod +x "$BIN_DIR/captains-log"

echo -e "${GREEN}✓${NC} Captain's Log installed"

# Add to PATH suggestion
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo
    echo -e "${YELLOW}Add to your shell profile (~/.zshrc or ~/.bashrc):${NC}"
    echo "  export PATH=\"$BIN_DIR:\$PATH\""
fi

# Install launchd service
echo
read -p "Install auto-start service? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    PLIST_PATH="$HOME/Library/LaunchAgents/com.captainslog.daemon.plist"

    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.captainslog.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>-m</string>
        <string>captains_log.cli.main</string>
        <string>start</string>
        <string>--foreground</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/CaptainsLog/daemon.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/CaptainsLog/daemon.error.log</string>
    <key>ProcessType</key>
    <string>Background</string>
    <key>Nice</key>
    <integer>10</integer>
</dict>
</plist>
EOF

    mkdir -p "$HOME/Library/Logs/CaptainsLog"
    launchctl load "$PLIST_PATH" 2>/dev/null || true

    echo -e "${GREEN}✓${NC} Auto-start service installed"
fi

# Install SwiftBar plugin
echo
read -p "Install SwiftBar menu bar plugin? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SWIFTBAR_DIR="$HOME/Library/Application Support/SwiftBar/Plugins"

    if [ -d "$SWIFTBAR_DIR" ]; then
        cp "$PROJECT_DIR/scripts/captains-log.1m.sh" "$SWIFTBAR_DIR/"
        # Update paths in the plugin
        sed -i '' "s|VENV_PATH=.*|VENV_PATH=\"$VENV_DIR\"|g" "$SWIFTBAR_DIR/captains-log.1m.sh"
        chmod +x "$SWIFTBAR_DIR/captains-log.1m.sh"
        echo -e "${GREEN}✓${NC} SwiftBar plugin installed"
    else
        echo -e "${YELLOW}SwiftBar plugins directory not found${NC}"
        echo "Install SwiftBar first: brew install --cask swiftbar"
    fi
fi

echo
echo -e "${GREEN}🚢 Installation complete!${NC}"
echo
echo "Quick start:"
echo "  captains-log start        # Start tracking"
echo "  captains-log dashboard    # Open web dashboard"
echo "  captains-log status       # Check status"
echo
echo "Note: Grant Accessibility permission in System Preferences"
echo "for full functionality (window titles, URLs)."
