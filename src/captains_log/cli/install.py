"""launchd installation utilities for Captain's Log."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from string import Template

# Service identifier
SERVICE_LABEL = "com.captainslog.daemon"

# Plist template path (relative to package)
PLIST_TEMPLATE = Path(__file__).parent.parent.parent.parent / "resources/launchd/com.captainslog.daemon.plist"


def get_launch_agents_dir() -> Path:
    """Get the user's LaunchAgents directory."""
    return Path.home() / "Library/LaunchAgents"


def get_plist_path() -> Path:
    """Get the installed plist path."""
    return get_launch_agents_dir() / f"{SERVICE_LABEL}.plist"


def is_installed() -> bool:
    """Check if launchd service is installed."""
    return get_plist_path().exists()


def is_loaded() -> bool:
    """Check if launchd service is currently loaded."""
    result = subprocess.run(
        ["launchctl", "list", SERVICE_LABEL],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def get_python_path() -> str:
    """Get the Python interpreter path."""
    return sys.executable


def get_python_bin_dir() -> str:
    """Get the directory containing the Python interpreter."""
    return str(Path(sys.executable).parent)


def get_pythonpath() -> str:
    """Get the PYTHONPATH for the installed package."""
    # Find the captains_log package location
    import captains_log
    package_dir = Path(captains_log.__file__).parent.parent
    return str(package_dir)


def create_plist() -> str:
    """Create the plist content with current environment values."""
    if not PLIST_TEMPLATE.exists():
        # If template not found, use embedded template
        template_content = get_embedded_template()
    else:
        template_content = PLIST_TEMPLATE.read_text()

    # Replace placeholders
    home = str(Path.home())
    content = template_content.replace("__PYTHON_PATH__", get_python_path())
    content = content.replace("__PYTHON_BIN_PATH__", get_python_bin_dir())
    content = content.replace("__HOME__", home)
    content = content.replace("__PYTHONPATH__", get_pythonpath())

    return content


def get_embedded_template() -> str:
    """Get embedded plist template."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.captainslog.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>__PYTHON_PATH__</string>
        <string>-m</string>
        <string>captains_log</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>10</integer>
    <key>Nice</key>
    <integer>10</integer>
    <key>WorkingDirectory</key>
    <string>__HOME__</string>
    <key>StandardOutPath</key>
    <string>__HOME__/Library/Logs/CaptainsLog/daemon.log</string>
    <key>StandardErrorPath</key>
    <string>__HOME__/Library/Logs/CaptainsLog/daemon.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:__PYTHON_BIN_PATH__</string>
        <key>HOME</key>
        <string>__HOME__</string>
        <key>PYTHONPATH</key>
        <string>__PYTHONPATH__</string>
    </dict>
    <key>ProcessType</key>
    <string>Background</string>
    <key>AbandonProcessGroup</key>
    <true/>
</dict>
</plist>'''


def install() -> tuple[bool, str]:
    """Install the launchd service.

    Returns:
        Tuple of (success, message)
    """
    plist_path = get_plist_path()

    # Create LaunchAgents directory if needed
    launch_agents_dir = get_launch_agents_dir()
    launch_agents_dir.mkdir(parents=True, exist_ok=True)

    # Create log directory
    log_dir = Path.home() / "Library/Logs/CaptainsLog"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Unload if already loaded
    if is_loaded():
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
        )

    # Write plist
    try:
        plist_content = create_plist()
        plist_path.write_text(plist_content)

        # Set permissions (readable by owner only)
        os.chmod(plist_path, 0o600)
    except Exception as e:
        return False, f"Failed to write plist: {e}"

    # Load the service
    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return False, f"Failed to load service: {result.stderr}"

    return True, f"Service installed and loaded. Plist: {plist_path}"


def uninstall() -> tuple[bool, str]:
    """Uninstall the launchd service.

    Returns:
        Tuple of (success, message)
    """
    plist_path = get_plist_path()

    if not plist_path.exists():
        return True, "Service not installed"

    # Unload if loaded
    if is_loaded():
        result = subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False, f"Failed to unload service: {result.stderr}"

    # Remove plist file
    try:
        plist_path.unlink()
    except Exception as e:
        return False, f"Failed to remove plist: {e}"

    return True, "Service uninstalled"


def get_status() -> dict:
    """Get launchd service status.

    Returns:
        Dictionary with status information
    """
    plist_path = get_plist_path()

    status = {
        "installed": plist_path.exists(),
        "loaded": is_loaded(),
        "plist_path": str(plist_path) if plist_path.exists() else None,
    }

    if status["loaded"]:
        # Get PID if running
        result = subprocess.run(
            ["launchctl", "list", SERVICE_LABEL],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            # Parse output: "PID	Status	Label"
            lines = result.stdout.strip().split("\n")
            if len(lines) > 0:
                parts = lines[0].split("\t")
                if len(parts) >= 2:
                    pid = parts[0]
                    status["pid"] = int(pid) if pid != "-" else None
                    status["exit_status"] = int(parts[1]) if len(parts) > 1 else None

    return status
