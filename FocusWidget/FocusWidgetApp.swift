import SwiftUI
import AppKit

// MARK: - Focus Session Data
class FocusSessionData: ObservableObject {
    @Published var goalName: String = ""  // Empty until loaded from status file
    @Published var targetMinutes: Int = 120
    @Published var focusMinutes: Double = 0.0
    @Published var pomodoroCount: Int = 0
    @Published var estimatedSessions: Int = 4
    @Published var isCompleted: Bool = false
    @Published var isActive: Bool = false

    @Published var timerPhase: String = "work"
    @Published var timeRemaining: String = "25:00"
    @Published var timerRunning: Bool = false

    @Published var currentApp: String = ""
    @Published var isOnGoal: Bool = true
    @Published var streakDays: Int = 0

    // Track previous state for sound triggers
    private var previousPhase: String = "work"
    private var previousTimeRemaining: String = "25:00"

    private var refreshTimer: Timer?
    private let statusFile = NSHomeDirectory() + "/Library/Application Support/CaptainsLog/focus_status.json"

    init() {
        refresh()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            self?.refresh()
        }
    }

    func refresh() {
        guard FileManager.default.fileExists(atPath: statusFile),
              let data = try? Data(contentsOf: URL(fileURLWithPath: statusFile)),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return
        }

        // Store previous values for change detection
        let oldPhase = timerPhase
        let oldRemaining = timeRemaining
        let wasActive = isActive

        if let active = json["active"] as? Bool { isActive = active }
        if let goal = json["goal_name"] as? String { goalName = goal }

        // Auto-close widget when session stops (BUG-008 fix)
        if wasActive && !isActive {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                NSApplication.shared.terminate(nil)
            }
        }
        if let target = json["target_minutes"] as? Int { targetMinutes = target }
        if let focus = json["focus_minutes"] as? Double { focusMinutes = focus }
        if let pomodoros = json["pomodoro_count"] as? Int { pomodoroCount = pomodoros }
        if let sessions = json["estimated_sessions"] as? Int { estimatedSessions = sessions }
        if let completed = json["completed"] as? Bool { isCompleted = completed }
        if let app = json["current_app"] as? String { currentApp = app }
        if let onGoal = json["is_on_goal"] as? Bool { isOnGoal = onGoal }
        if let streak = json["streak_days"] as? Int { streakDays = streak }
        if let phase = json["timer_phase"] as? String { timerPhase = phase }
        if let remaining = json["time_remaining"] as? String { timeRemaining = remaining }
        if let running = json["timer_running"] as? Bool { timerRunning = running }

        // Detect phase changes for sound
        if oldPhase != timerPhase && oldPhase != "" {
            playPhaseChangeSound()
        }

        // Detect timer completion (when remaining goes to 00:00 or phase changes)
        if oldRemaining == "00:01" && timeRemaining != "00:01" {
            playCompletionSound()
        }
    }

    func playPhaseChangeSound() {
        NSSound(named: "Glass")?.play()
    }

    func playCompletionSound() {
        NSSound(named: "Hero")?.play()
    }
}

// MARK: - Session Dots View
struct SessionDots: View {
    let completed: Int
    let total: Int

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<total, id: \.self) { i in
                Circle()
                    .fill(i < completed ? Color.primary : Color.primary.opacity(0.2))
                    .frame(width: 6, height: 6)
            }
        }
    }
}

// MARK: - Floating Widget View
struct FloatingWidgetView: View {
    @ObservedObject var sessionData: FocusSessionData
    @State private var isHovering: Bool = false

    private let venvPath = NSHomeDirectory() + "/Desktop/Claude-experiments/captains-log/.venv"

    var body: some View {
        HStack(spacing: 10) {
            Text(sessionData.goalName.isEmpty ? "Loading..." : sessionData.goalName)
                .font(.system(size: 12, weight: .medium))
                .foregroundColor(.primary)
                .lineLimit(1)

            Spacer()

            Text(sessionData.timeRemaining)
                .font(.system(size: 14, weight: .semibold, design: .monospaced))
                .foregroundColor(timerColor)

            SessionDots(
                completed: sessionData.pomodoroCount,
                total: sessionData.estimatedSessions
            )

            // Controls - visible on hover
            if isHovering {
                // Pause/Play button
                Button(action: {
                    togglePause()
                }) {
                    Image(systemName: sessionData.timerRunning ? "pause.fill" : "play.fill")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundColor(.blue)
                        .frame(width: 16, height: 16)
                        .background(Color.blue.opacity(0.15))
                        .cornerRadius(8)
                }
                .buttonStyle(.plain)

                // Close button
                Button(action: {
                    NSApplication.shared.terminate(nil)
                }) {
                    Image(systemName: "xmark")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundColor(.secondary)
                        .frame(width: 16, height: 16)
                        .background(Color.primary.opacity(0.1))
                        .cornerRadius(8)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .frame(minWidth: 260)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color(NSColor.windowBackgroundColor).opacity(0.92))
                .shadow(color: .black.opacity(0.15), radius: 4, x: 0, y: 2)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(borderColor, lineWidth: sessionData.isOnGoal ? 0 : 2)
        )
        .onHover { hovering in
            isHovering = hovering
        }
    }

    var borderColor: Color {
        sessionData.isOnGoal ? .clear : Color.orange.opacity(0.6)
    }

    var timerColor: Color {
        switch sessionData.timerPhase {
        case "work": return sessionData.timerRunning ? .primary : .secondary
        case "short_break": return .green
        case "long_break": return .blue
        default: return .primary
        }
    }

    func togglePause() {
        let command = sessionData.timerRunning
            ? "\"\(venvPath)/bin/captains-log\" focus-timer pause"
            : "\"\(venvPath)/bin/captains-log\" focus-timer start"

        DispatchQueue.global(qos: .userInitiated).async {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/bin/bash")
            process.arguments = ["-c", command]
            process.environment = ["PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"]
            try? process.run()
        }
    }
}


// MARK: - Floating Panel
class FloatingPanel: NSPanel {
    override var canBecomeKey: Bool { true }

    init(contentRect: NSRect, rootView: some View) {
        super.init(
            contentRect: contentRect,
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )

        self.level = .floating
        self.isOpaque = false
        self.backgroundColor = .clear
        self.hasShadow = false
        self.isMovableByWindowBackground = true
        self.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]

        let hostingView = NSHostingView(rootView: rootView)
        self.contentView = hostingView

        if let screen = NSScreen.main {
            let screenFrame = screen.visibleFrame
            let x = screenFrame.maxX - contentRect.width - 20
            let y = screenFrame.maxY - contentRect.height - 20
            self.setFrameOrigin(NSPoint(x: x, y: y))
        }
    }
}

// MARK: - App Delegate
class AppDelegate: NSObject, NSApplicationDelegate {
    var floatingPanel: FloatingPanel!
    var sessionData = FocusSessionData()

    func applicationDidFinishLaunching(_ notification: Notification) {
        let rootView = FloatingWidgetView(sessionData: sessionData)

        let contentRect = NSRect(x: 0, y: 0, width: 280, height: 50)
        floatingPanel = FloatingPanel(contentRect: contentRect, rootView: rootView)
        floatingPanel.orderFront(nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false  // Keep running even if window closes
    }
}

// MARK: - Main App
@main
struct FocusWidgetApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        Settings {
            EmptyView()
        }
    }
}
