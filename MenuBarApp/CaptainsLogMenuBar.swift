import SwiftUI
import AppKit

// MARK: - Data Models

struct GoalProgress: Codable, Identifiable {
    let date: String
    let status: String
    let progress_percent: Double

    var id: String { date }

    var color: Color {
        switch status {
        case "green": return .green
        case "amber": return .orange
        case "red": return .red
        default: return Color.primary.opacity(0.15)
        }
    }

    var fillPercent: Double {
        min(1.0, max(0.0, progress_percent / 100.0))
    }
}

struct GoalTask: Codable, Identifiable {
    let id: Int
    let name: String
    let estimated_minutes: Int
}

struct ProductivityGoal: Codable, Identifiable {
    let id: Int
    let name: String
    let color: String
    let estimated_hours: Double
    let progress_percent: Double
    let daily_target_minutes: Double
    let today_status: String
    let recent_progress: [GoalProgress]
    let tasks: [GoalTask]

    var statusColor: Color {
        switch today_status {
        case "green": return .green
        case "amber": return .orange
        case "red": return .red
        default: return Color.primary.opacity(0.3)
        }
    }

    var statusEmoji: String {
        switch today_status {
        case "green": return "✓"
        case "amber": return "◐"
        case "red": return "○"
        default: return "·"
        }
    }

    var goalColor: Color {
        Color(hex: color) ?? .blue
    }
}

struct GoalsData: Codable {
    let goals: [ProductivityGoal]
    let todayFocusMinutes: Double?

    enum CodingKeys: String, CodingKey {
        case goals
        case todayFocusMinutes = "today_focus_minutes"
    }
}

struct FocusStatus: Codable {
    var active: Bool = false
    var currentApp: String = ""
    var streakDays: Int = 0
    var goalName: String = ""
    var targetMinutes: Int = 0
    var focusMinutes: Double = 0
    var pomodoroCount: Int = 0
    var estimatedSessions: Int = 4
    var completed: Bool = false
    var isOnGoal: Bool = true
    var timerPhase: String = "work"
    var timeRemaining: String = "25:00"
    var timerRunning: Bool = false
    var dailyFocusMinutes: Double = 0

    enum CodingKeys: String, CodingKey {
        case active
        case currentApp = "current_app"
        case streakDays = "streak_days"
        case goalName = "goal_name"
        case targetMinutes = "target_minutes"
        case focusMinutes = "focus_minutes"
        case pomodoroCount = "pomodoro_count"
        case estimatedSessions = "estimated_sessions"
        case completed
        case isOnGoal = "is_on_goal"
        case timerPhase = "timer_phase"
        case timeRemaining = "time_remaining"
        case timerRunning = "timer_running"
        case dailyFocusMinutes = "daily_focus_minutes"
    }
}

// MARK: - Color Extension

extension Color {
    init?(hex: String) {
        var hexSanitized = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        hexSanitized = hexSanitized.replacingOccurrences(of: "#", with: "")

        var rgb: UInt64 = 0
        guard Scanner(string: hexSanitized).scanHexInt64(&rgb) else { return nil }

        self.init(
            red: Double((rgb & 0xFF0000) >> 16) / 255.0,
            green: Double((rgb & 0x00FF00) >> 8) / 255.0,
            blue: Double(rgb & 0x0000FF) / 255.0
        )
    }
}

// MARK: - Status Manager

class StatusManager: ObservableObject {
    @Published var focusStatus = FocusStatus()
    @Published var goals: [ProductivityGoal] = []
    @Published var daemonRunning = false
    @Published var todayFocusMinutes: Double = 0

    private var refreshTimer: Timer?
    private let statusFilePath = NSHomeDirectory() + "/Library/Application Support/CaptainsLog/focus_status.json"
    private let goalsFilePath = NSHomeDirectory() + "/Library/Application Support/CaptainsLog/goals_status.json"
    private let venvPath = NSHomeDirectory() + "/Desktop/Claude-experiments/captains-log/.venv"

    init() {
        refresh()
        loadGoals()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            self?.refresh()
        }
        Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { [weak self] _ in
            self?.loadGoals()
        }
    }

    func refresh() {
        checkDaemon()
        loadFocusStatus()
    }

    private func checkDaemon() {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/pgrep")
        process.arguments = ["-f", "captains_log"]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        do {
            try process.run()
            process.waitUntilExit()
            daemonRunning = process.terminationStatus == 0
        } catch {
            daemonRunning = false
        }
    }

    private func loadFocusStatus() {
        guard FileManager.default.fileExists(atPath: statusFilePath),
              let data = try? Data(contentsOf: URL(fileURLWithPath: statusFilePath)),
              let status = try? JSONDecoder().decode(FocusStatus.self, from: data) else {
            focusStatus = FocusStatus()
            return
        }
        focusStatus = status
    }

    func loadGoals() {
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/bin/bash")
            process.arguments = ["-c", "\"\(self.venvPath)/bin/captains-log\" goals-status > \"\(self.goalsFilePath)\" 2>/dev/null"]
            process.environment = ["PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"]
            try? process.run()
            process.waitUntilExit()

            guard FileManager.default.fileExists(atPath: self.goalsFilePath),
                  let data = try? Data(contentsOf: URL(fileURLWithPath: self.goalsFilePath)),
                  let goalsData = try? JSONDecoder().decode(GoalsData.self, from: data) else {
                return
            }
            DispatchQueue.main.async {
                self.goals = goalsData.goals
                self.todayFocusMinutes = goalsData.todayFocusMinutes ?? 0
            }
        }
    }

    func startFocusSession(taskName: String, minutes: Int) {
        // Stop any existing session first
        let stopScript = "pkill -f 'captains-log focus' 2>/dev/null; sleep 0.3"
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = ["-c", stopScript]
        try? process.run()
        process.waitUntilExit()

        // Clear old status
        let emptyStatus = "{\"active\": false}"
        try? emptyStatus.write(toFile: statusFilePath, atomically: true, encoding: .utf8)

        // Start new focus session
        let script = "\"\(venvPath)/bin/captains-log\" focus -g \"\(taskName)\" -t \(minutes) --sessions 1 --no-widget &"
        runShellCommand(script)

        // Launch the floating widget after a short delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            NSWorkspace.shared.open(URL(fileURLWithPath: "/Applications/FocusWidget.app"))
        }
    }

    func pauseTimer() {
        runShellCommand("\"\(venvPath)/bin/captains-log\" focus-timer pause")
    }

    func resumeTimer() {
        runShellCommand("\"\(venvPath)/bin/captains-log\" focus-timer start")
    }

    func stopSession() {
        runShellCommand("\"\(venvPath)/bin/captains-log\" focus-stop")
        runShellCommand("pkill -f 'captains-log focus' 2>/dev/null || true")
        // Clear status file
        let emptyStatus = "{\"active\": false}"
        try? emptyStatus.write(toFile: statusFilePath, atomically: true, encoding: .utf8)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            self.refresh()
        }
    }

    private func runShellCommand(_ command: String) {
        DispatchQueue.global(qos: .userInitiated).async {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/bin/bash")
            process.arguments = ["-c", command]
            process.environment = ["PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"]
            try? process.run()
        }
    }

    var dailyHours: String {
        // Use todayFocusMinutes from database (persists across sessions)
        let minutes = todayFocusMinutes
        let hours = minutes / 60.0
        if hours >= 1 {
            return String(format: "%.1fh", hours)
        } else {
            return "\(Int(minutes))m"
        }
    }
}

// MARK: - Progress Ring

struct ProgressRing: View {
    let progress: Double
    let color: Color
    let size: CGFloat
    let lineWidth: CGFloat

    init(progress: Double, color: Color, size: CGFloat = 16, lineWidth: CGFloat = 2.5) {
        self.progress = min(1.0, max(0.0, progress))
        self.color = color
        self.size = size
        self.lineWidth = lineWidth
    }

    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.primary.opacity(0.1), lineWidth: lineWidth)

            Circle()
                .trim(from: 0, to: CGFloat(progress))
                .stroke(color, style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                .rotationEffect(.degrees(-90))

            if progress >= 1.0 {
                Image(systemName: "checkmark")
                    .font(.system(size: size * 0.4, weight: .bold))
                    .foregroundColor(color)
            }
        }
        .frame(width: size, height: size)
    }
}

// MARK: - Streak View

struct StreakView: View {
    let progress: [GoalProgress]

    var body: some View {
        HStack(spacing: 2) {
            ForEach(progress) { p in
                ProgressRing(
                    progress: p.fillPercent,
                    color: p.color,
                    size: 12,
                    lineWidth: 1.5
                )
            }
        }
        .frame(width: 70, alignment: .trailing) // Fixed width for 5 dots
    }
}

// MARK: - Menu Bar Content

struct MenuBarView: View {
    @ObservedObject var statusManager: StatusManager
    @State private var newTaskName: String = ""
    @State private var showNewTask: Bool = false
    @State private var expandedGoalId: Int? = nil

    private let rowHeight: CGFloat = 28
    private let iconSize: CGFloat = 14

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack {
                Text("Captain's Log")
                    .font(.system(size: 13, weight: .semibold))
                Spacer()
                Circle()
                    .fill(statusManager.daemonRunning ? Color.green : Color.red)
                    .frame(width: 8, height: 8)
            }
            .frame(height: rowHeight)
            .padding(.horizontal, 12)

            Divider().padding(.horizontal, 8)

            // Active Session
            if statusManager.focusStatus.active {
                activeSessionSection
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                Divider().padding(.horizontal, 8)
            }

            // Today's Stats
            HStack(spacing: 6) {
                Image(systemName: "flame.fill")
                    .font(.system(size: iconSize))
                    .foregroundColor(.orange)
                    .frame(width: 36) // chevronWidth + ringWidth
                Text("Today")
                    .font(.system(size: 13))
                    .frame(maxWidth: .infinity, alignment: .leading)
                Text(statusManager.dailyHours)
                    .font(.system(size: 13, weight: .medium))
                    .frame(width: 70, alignment: .trailing)
            }
            .frame(height: rowHeight)
            .padding(.horizontal, 12)

            Divider().padding(.horizontal, 8)

            // Goals Section
            if !statusManager.goals.isEmpty {
                Text("GOALS")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 12)
                    .padding(.top, 8)
                    .padding(.bottom, 4)

                ForEach(statusManager.goals) { goal in
                    VStack(spacing: 0) {
                        goalRow(goal)

                        // Expanded tasks
                        if expandedGoalId == goal.id && !goal.tasks.isEmpty {
                            VStack(spacing: 0) {
                                ForEach(goal.tasks) { task in
                                    taskRow(task, goal: goal)
                                }
                            }
                            .background(Color(NSColor.controlBackgroundColor).opacity(0.5))
                        }
                    }
                }
            } else {
                HStack(spacing: 6) {
                    Image(systemName: "target")
                        .font(.system(size: iconSize))
                        .foregroundColor(.secondary)
                        .frame(width: 36)
                    Text("No goals yet")
                        .font(.system(size: 13))
                        .foregroundColor(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: rowHeight)
                .padding(.horizontal, 12)
            }

            Divider().padding(.horizontal, 8).padding(.top, 4)

            // Quick Actions
            if showNewTask {
                newTaskSection
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
            } else {
                Button(action: { showNewTask = true }) {
                    HStack(spacing: 6) {
                        Image(systemName: "plus.circle.fill")
                            .font(.system(size: iconSize))
                            .foregroundColor(.blue)
                            .frame(width: 36)
                        Text("Quick Focus")
                            .font(.system(size: 13))
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(height: rowHeight)
                    .padding(.horizontal, 12)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }

            Button(action: {
                if let url = URL(string: "http://localhost:3000") {
                    NSWorkspace.shared.open(url)
                }
            }) {
                HStack(spacing: 6) {
                    Image(systemName: "chart.bar.fill")
                        .font(.system(size: iconSize))
                        .foregroundColor(.purple)
                        .frame(width: 36)
                    Text("Dashboard")
                        .font(.system(size: 13))
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: rowHeight)
                .padding(.horizontal, 12)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            Divider().padding(.horizontal, 8)

            Button(action: { NSApplication.shared.terminate(nil) }) {
                HStack(spacing: 6) {
                    Image(systemName: "power")
                        .font(.system(size: iconSize))
                        .foregroundColor(.secondary)
                        .frame(width: 36)
                    Text("Quit")
                        .font(.system(size: 13))
                        .foregroundColor(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: rowHeight)
                .padding(.horizontal, 12)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
        }
        .padding(.vertical, 8)
        .frame(width: 280)
    }

    // MARK: - Active Session Section

    var activeSessionSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Timer row
            HStack(spacing: 8) {
                Image(systemName: statusManager.focusStatus.timerRunning ? "play.circle.fill" : "pause.circle.fill")
                    .foregroundColor(statusManager.focusStatus.timerRunning ? .green : .orange)
                    .font(.system(size: 14))
                    .frame(width: 20)

                Text(statusManager.focusStatus.goalName)
                    .font(.system(size: 13, weight: .medium))
                    .lineLimit(1)

                Spacer()

                Text(statusManager.focusStatus.timeRemaining)
                    .font(.system(size: 20, weight: .semibold, design: .monospaced))
                    .foregroundColor(timerColor)
            }

            // Progress and controls row
            HStack(spacing: 4) {
                // Session dots
                ForEach(0..<statusManager.focusStatus.estimatedSessions, id: \.self) { i in
                    Circle()
                        .fill(i < statusManager.focusStatus.pomodoroCount ? Color.green : Color.primary.opacity(0.2))
                        .frame(width: 6, height: 6)
                }

                Text("\(statusManager.focusStatus.pomodoroCount)/\(statusManager.focusStatus.estimatedSessions)")
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
                    .padding(.leading, 2)

                Spacer()

                // Controls
                Button(action: {
                    NSWorkspace.shared.open(URL(fileURLWithPath: "/Applications/FocusWidget.app"))
                }) {
                    Image(systemName: "pip")
                        .font(.system(size: 10))
                        .frame(width: 26, height: 26)
                        .background(Color(NSColor.separatorColor).opacity(0.3))
                        .foregroundColor(.primary)
                        .cornerRadius(5)
                }
                .buttonStyle(.plain)
                .help("Show floating widget")

                Button(action: {
                    if statusManager.focusStatus.timerRunning {
                        statusManager.pauseTimer()
                    } else {
                        statusManager.resumeTimer()
                    }
                }) {
                    Image(systemName: statusManager.focusStatus.timerRunning ? "pause.fill" : "play.fill")
                        .font(.system(size: 10))
                        .frame(width: 26, height: 26)
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(5)
                }
                .buttonStyle(.plain)

                Button(action: { statusManager.stopSession() }) {
                    Image(systemName: "stop.fill")
                        .font(.system(size: 9))
                        .frame(width: 26, height: 26)
                        .background(Color(NSColor.separatorColor).opacity(0.3))
                        .foregroundColor(.primary)
                        .cornerRadius(5)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(10)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }

    var timerColor: Color {
        switch statusManager.focusStatus.timerPhase {
        case "short_break": return .green
        case "long_break": return .blue
        default: return statusManager.focusStatus.timerRunning ? .primary : .secondary
        }
    }

    // MARK: - Goal Row

    private let chevronWidth: CGFloat = 16
    private let streakWidth: CGFloat = 70

    func goalRow(_ goal: ProductivityGoal) -> some View {
        HStack(spacing: 6) {
            // Chevron for expandable goals, play button for goals without tasks
            Group {
                if !goal.tasks.isEmpty {
                    Image(systemName: expandedGoalId == goal.id ? "chevron.down" : "chevron.right")
                        .font(.system(size: 10, weight: .medium))
                        .foregroundColor(.secondary)
                } else {
                    // Play button for goals without tasks
                    Button(action: {
                        statusManager.startFocusSession(taskName: goal.name, minutes: 25)
                    }) {
                        Image(systemName: "play.fill")
                            .font(.system(size: 8))
                            .foregroundColor(.blue)
                    }
                    .buttonStyle(.plain)
                }
            }
            .frame(width: chevronWidth, alignment: .center)

            // Goal name
            Text(goal.name)
                .font(.system(size: 13))
                .lineLimit(1)
                .frame(maxWidth: .infinity, alignment: .leading)

            // Streak - last 5 days
            StreakView(progress: goal.recent_progress)
        }
        .frame(height: rowHeight)
        .padding(.horizontal, 12)
        .contentShape(Rectangle())
        .background(expandedGoalId == goal.id ? Color(NSColor.controlBackgroundColor).opacity(0.3) : Color.clear)
        .onTapGesture {
            if goal.tasks.isEmpty {
                // No tasks - start session directly
                statusManager.startFocusSession(taskName: goal.name, minutes: 25)
            } else {
                // Has tasks - expand/collapse
                withAnimation(.easeInOut(duration: 0.15)) {
                    if expandedGoalId == goal.id {
                        expandedGoalId = nil
                    } else {
                        expandedGoalId = goal.id
                    }
                }
            }
        }
    }

    // MARK: - Task Row

    func taskRow(_ task: GoalTask, goal: ProductivityGoal) -> some View {
        Button(action: {
            statusManager.startFocusSession(taskName: task.name, minutes: task.estimated_minutes)
        }) {
            HStack(spacing: 6) {
                // Indent to align with goal name
                Color.clear.frame(width: chevronWidth)

                // Task name
                Text(task.name)
                    .font(.system(size: 12))
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)

                // Duration + play button
                HStack(spacing: 4) {
                    Text("\(task.estimated_minutes)m")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                    Image(systemName: "play.fill")
                        .font(.system(size: 8))
                        .foregroundColor(.blue)
                }
                .frame(width: streakWidth, alignment: .trailing)
            }
            .frame(height: 26)
            .padding(.horizontal, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    // MARK: - New Task Section

    var newTaskSection: some View {
        VStack(spacing: 6) {
            TextField("What are you working on?", text: $newTaskName)
                .textFieldStyle(.roundedBorder)
                .font(.system(size: 12))

            HStack {
                Button(action: {
                    showNewTask = false
                    newTaskName = ""
                }) {
                    Text("Cancel")
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)

                Spacer()

                Button(action: {
                    if !newTaskName.isEmpty {
                        statusManager.startFocusSession(taskName: newTaskName, minutes: 25)
                        showNewTask = false
                        newTaskName = ""
                    }
                }) {
                    HStack(spacing: 4) {
                        Image(systemName: "play.fill")
                            .font(.system(size: 10))
                        Text("Start 25m")
                            .font(.system(size: 12, weight: .medium))
                    }
                    .foregroundColor(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(newTaskName.isEmpty ? Color.blue.opacity(0.5) : Color.blue)
                    .cornerRadius(5)
                }
                .buttonStyle(.plain)
                .disabled(newTaskName.isEmpty)
            }
        }
        .padding(10)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
}

// MARK: - App Delegate

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var popover: NSPopover!
    var statusManager = StatusManager()

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)

        if let button = statusItem.button {
            updateStatusButton(button)
            Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
                if let button = self?.statusItem.button {
                    self?.updateStatusButton(button)
                }
            }
        }

        popover = NSPopover()
        popover.contentSize = NSSize(width: 280, height: 400)
        popover.behavior = .transient
        popover.contentViewController = NSHostingController(rootView: MenuBarView(statusManager: statusManager))

        statusItem.button?.action = #selector(togglePopover)
        statusItem.button?.target = self
    }

    func updateStatusButton(_ button: NSStatusBarButton) {
        let status = statusManager.focusStatus
        let config = NSImage.SymbolConfiguration(pointSize: 13, weight: .medium)

        if status.active {
            let iconName = status.timerRunning ? "play.circle.fill" : "pause.circle.fill"
            if let image = NSImage(systemSymbolName: iconName, accessibilityDescription: nil)?.withSymbolConfiguration(config) {
                button.image = image
            }
            button.title = " " + status.timeRemaining
            button.imagePosition = .imageLeft
        } else {
            if let image = NSImage(systemSymbolName: "target", accessibilityDescription: nil)?.withSymbolConfiguration(config) {
                button.image = image
            }
            button.title = ""
            button.imagePosition = .imageOnly
        }
    }

    @objc func togglePopover() {
        if let button = statusItem.button {
            if popover.isShown {
                popover.performClose(nil)
            } else {
                statusManager.refresh()
                statusManager.loadGoals()
                popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
                popover.contentViewController?.view.window?.makeKey()
            }
        }
    }
}

// MARK: - Main App

@main
struct CaptainsLogMenuBarApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        Settings { EmptyView() }
    }
}
