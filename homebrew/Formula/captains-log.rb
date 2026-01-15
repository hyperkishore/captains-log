class CaptainsLog < Formula
  include Language::Python::Virtualenv

  desc "macOS personal activity tracking system with AI-powered insights"
  homepage "https://github.com/hyperkishore/captains-log"
  url "https://github.com/hyperkishore/captains-log/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"
  head "https://github.com/hyperkishore/captains-log.git", branch: "main"

  depends_on "python@3.11"
  depends_on :macos

  def install
    virtualenv_install_with_resources

    # Install the package
    system libexec/"bin/pip", "install", ".", "--no-deps"

    # Create bin wrapper
    (bin/"captains-log").write_env_script(
      libexec/"bin/captains-log",
      PATH: "#{libexec}/bin:$PATH"
    )

    # Install launchd plist
    (prefix/"com.captainslog.daemon.plist").write <<~EOS
      <?xml version="1.0" encoding="UTF-8"?>
      <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
      <plist version="1.0">
      <dict>
          <key>Label</key>
          <string>com.captainslog.daemon</string>
          <key>ProgramArguments</key>
          <array>
              <string>#{opt_bin}/captains-log</string>
              <string>start</string>
              <string>--foreground</string>
          </array>
          <key>RunAtLoad</key>
          <true/>
          <key>KeepAlive</key>
          <true/>
          <key>StandardOutPath</key>
          <string>#{var}/log/captains-log/daemon.log</string>
          <key>StandardErrorPath</key>
          <string>#{var}/log/captains-log/daemon.error.log</string>
          <key>EnvironmentVariables</key>
          <dict>
              <key>PATH</key>
              <string>#{opt_libexec}/bin:/usr/local/bin:/usr/bin:/bin</string>
          </dict>
          <key>ProcessType</key>
          <string>Background</string>
          <key>Nice</key>
          <integer>10</integer>
      </dict>
      </plist>
    EOS

    # Install SwiftBar plugin
    (share/"swiftbar/captains-log.1m.sh").write <<~EOS
      #!/bin/bash

      # <xbar.title>Captain's Log</xbar.title>
      # <xbar.version>v1.0</xbar.version>
      # <xbar.author>Captain's Log</xbar.author>
      # <xbar.desc>Shows activity tracking stats from Captain's Log</xbar.desc>
      # <xbar.dependencies>python3,sqlite3</xbar.dependencies>
      # <swiftbar.hideAbout>true</swiftbar.hideAbout>
      # <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
      # <swiftbar.hideLastUpdated>false</swiftbar.hideLastUpdated>
      # <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
      # <swiftbar.hideSwiftBar>true</swiftbar.hideSwiftBar>

      DB_PATH="$HOME/Library/Application Support/CaptainsLog/captains_log.db"
      CAPTAINS_LOG_BIN="#{opt_bin}/captains-log"
      DASHBOARD_URL="http://127.0.0.1:8080"

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
      TOTAL_TODAY=\${TOTAL_TODAY:-0}
      TOP_APP=\${TOP_APP:-"None"}
      UNIQUE_APPS=\${UNIQUE_APPS:-0}

      # Get last activity
      LAST_APP=$(sqlite3 "$DB_PATH" "SELECT app_name FROM activity_logs ORDER BY timestamp DESC LIMIT 1" 2>/dev/null)
      LAST_APP=\${LAST_APP:-"None"}

      # Menu bar display
      if [ "$TOTAL_TODAY" -eq 0 ]; then
          echo "🚢 0"
      else
          echo "🚢 $TOTAL_TODAY"
      fi

      echo "---"
      echo "Captain's Log | size=14"
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
      echo "Open Dashboard | href=$DASHBOARD_URL"
      echo "---"
      echo "Status"

      # Check if daemon is running
      if pgrep -f "captains_log" > /dev/null 2>&1; then
          echo "● Daemon Running | color=green"
      else
          echo "○ Daemon Stopped | color=red"
          echo "--Start Daemon | bash='$CAPTAINS_LOG_BIN' param1=start terminal=false refresh=true"
      fi

      # Check if dashboard is running
      if curl -s -o /dev/null -w "%{http_code}" "$DASHBOARD_URL" 2>/dev/null | grep -q "200"; then
          echo "● Dashboard Running | color=green"
      else
          echo "○ Dashboard Stopped | color=gray"
          echo "--Start Dashboard | bash='$CAPTAINS_LOG_BIN' param1=dashboard terminal=false refresh=true"
      fi

      echo "---"
      echo "Refresh | refresh=true"
    EOS
    chmod 0755, share/"swiftbar/captains-log.1m.sh"
  end

  def post_install
    (var/"log/captains-log").mkpath
  end

  def caveats
    <<~EOS
      To start Captain's Log now and restart at login:
        brew services start captains-log

      Or, start manually:
        captains-log start

      To run the web dashboard:
        captains-log dashboard
        # Then open http://127.0.0.1:8080

      For SwiftBar integration:
        1. Install SwiftBar: brew install --cask swiftbar
        2. Copy the plugin to your SwiftBar plugins folder:
           cp #{share}/swiftbar/captains-log.1m.sh ~/Library/Application\\ Support/SwiftBar/Plugins/
        3. Make it executable (already done by brew)

      Important: Grant Accessibility permission in System Preferences for
      full functionality (window titles, URLs).

      Data is stored in:
        ~/Library/Application Support/CaptainsLog/
    EOS
  end

  service do
    run [opt_bin/"captains-log", "start", "--foreground"]
    keep_alive true
    log_path var/"log/captains-log/daemon.log"
    error_log_path var/"log/captains-log/daemon.error.log"
    environment_variables PATH: std_service_path_env
    process_type :background
  end

  test do
    system "#{bin}/captains-log", "--help"
  end
end
