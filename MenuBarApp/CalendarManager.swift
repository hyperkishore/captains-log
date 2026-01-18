// CalendarManager.swift
// Captain's Log - Calendar Manager
//
// Aggregates calendar providers and computes free time for focus suggestions.
// Supports multiple providers (EventKit, Google Calendar, etc.) with deduplication.

import Foundation
import Combine
import EventKit
import SwiftUI

class CalendarManager: ObservableObject {
    // MARK: - Published State

    @Published var providers: [any CalendarProvider] = []
    @Published var todaysEvents: [CalendarEvent] = []
    @Published var nextEvent: CalendarEvent?
    @Published var currentEvent: CalendarEvent?
    @Published var freeMinutes: Int = 0
    @Published var totalMeetingMinutes: Int = 0
    @Published var isMeetingHeavyDay: Bool = false
    @Published var hasAccess: Bool = false
    @Published var accessDenied: Bool = false

    // MARK: - Private Properties

    private var refreshTimer: Timer?
    private var notificationObserver: Any?
    private let eventKit = EventKitProvider()

    // MARK: - Initialization

    init() {
        providers = [eventKit]
        hasAccess = eventKit.isConnected
        accessDenied = eventKit.accessDenied

        if hasAccess {
            startMonitoring()
        }
    }

    // MARK: - Access Control

    func requestAccess() async -> Bool {
        let granted = await eventKit.requestAccess()
        await MainActor.run {
            self.hasAccess = granted
            self.accessDenied = !granted
            if granted {
                self.startMonitoring()
            }
        }
        return granted
    }

    // MARK: - Monitoring

    func startMonitoring() {
        // Initial fetch
        fetchEvents()

        // Refresh every 5 minutes
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in
            self?.fetchEvents()
        }

        // Listen for calendar changes
        notificationObserver = NotificationCenter.default.addObserver(
            forName: .EKEventStoreChanged,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.fetchEvents()
        }
    }

    func stopMonitoring() {
        refreshTimer?.invalidate()
        refreshTimer = nil
        if let observer = notificationObserver {
            NotificationCenter.default.removeObserver(observer)
            notificationObserver = nil
        }
    }

    // MARK: - Event Fetching

    func fetchEvents() {
        guard hasAccess else { return }

        Task {
            let start = Calendar.current.startOfDay(for: Date())
            let end = Calendar.current.date(byAdding: .day, value: 1, to: start)!

            var allEvents: [CalendarEvent] = []

            // Fetch from all connected providers
            for provider in providers where provider.isConnected {
                do {
                    let events = try await provider.fetchEvents(from: start, to: end)
                    allEvents.append(contentsOf: events)
                } catch {
                    print("[CalendarManager] Error fetching from \(provider.name): \(error)")
                }
            }

            // Sort and deduplicate
            let sortedEvents = allEvents.sorted { $0.startDate < $1.startDate }
            let deduplicatedEvents = deduplicateEvents(sortedEvents)

            await MainActor.run {
                self.todaysEvents = deduplicatedEvents
                self.updateCurrentState()
            }
        }
    }

    // MARK: - State Updates

    private func updateCurrentState() {
        let now = Date()

        // Find current meeting (if any)
        currentEvent = todaysEvents.first { $0.isHappeningNow }

        // Find next meeting
        nextEvent = todaysEvents.first { $0.startDate > now }

        // Calculate free time until next meeting
        if let next = nextEvent {
            freeMinutes = next.minutesUntilStart
        } else {
            // No more meetings - calculate until end of workday (6 PM)
            let endOfWorkday = Calendar.current.date(
                bySettingHour: 18, minute: 0, second: 0, of: now
            ) ?? now

            if endOfWorkday > now {
                freeMinutes = Int(endOfWorkday.timeIntervalSince(now) / 60)
            } else {
                freeMinutes = 0
            }
        }

        // Calculate total meeting time today
        totalMeetingMinutes = todaysEvents.reduce(0) { $0 + $1.durationMinutes }

        // Meeting-heavy day = more than 4 hours of meetings
        isMeetingHeavyDay = totalMeetingMinutes > 240
    }

    // MARK: - Deduplication

    /// Remove duplicate events (same event from multiple providers)
    private func deduplicateEvents(_ events: [CalendarEvent]) -> [CalendarEvent] {
        var result: [CalendarEvent] = []

        for event in events {
            // Check if we already have a matching event
            let isDuplicate = result.contains { existing in
                existing.matches(event)
            }

            if !isDuplicate {
                result.append(event)
            }
        }

        return result
    }

    // MARK: - Focus Suggestions

    /// Generate a smart focus suggestion based on goals and free time
    func suggestFocus(goals: [ProductivityGoal]) -> FocusSuggestion? {
        // Don't suggest during meetings
        guard currentEvent == nil else { return nil }

        // Need at least 20 minutes of free time
        guard freeMinutes >= 20 else { return nil }

        // Find goals that need work (not green today)
        let needsWork = goals.filter { $0.today_status != "green" }
        guard let bestGoal = needsWork.first else { return nil }

        // Determine session duration based on available time
        let duration: Int
        if freeMinutes >= 55 {
            duration = 50  // Full pomodoro + 5 minute buffer
        } else if freeMinutes >= 30 {
            duration = 25  // Half pomodoro
        } else {
            duration = 15  // Mini session
        }

        return FocusSuggestion(
            goalName: bestGoal.name,
            durationMinutes: duration,
            freeMinutes: freeMinutes
        )
    }

    // MARK: - Helper Methods

    /// Open System Preferences to Calendar privacy settings
    func openSystemPreferences() {
        eventKit.openSystemPreferences()
    }

    /// Get debug info about connected calendars
    func getCalendarInfo() -> [(name: String, color: Color?, eventCount: Int)] {
        return eventKit.getCalendarInfo()
    }

    // MARK: - Deinitialization

    deinit {
        stopMonitoring()
    }
}
