// EventKitProvider.swift
// Captain's Log - macOS EventKit Calendar Provider
//
// Uses Apple's EventKit framework to read calendar events from macOS Calendar.
// Supports iCloud, Google, Exchange, and any other calendars synced to macOS.

import EventKit
import Foundation
import SwiftUI

class EventKitProvider: CalendarProvider {
    let id = "eventkit"
    let name = "macOS Calendar"
    let requiresAuth = true

    private let eventStore = EKEventStore()
    private(set) var isConnected = false
    private(set) var accessDenied = false

    init() {
        checkExistingAccess()
    }

    // MARK: - Permission Handling

    private func checkExistingAccess() {
        let status = EKEventStore.authorizationStatus(for: .event)
        switch status {
        case .fullAccess, .authorized:
            isConnected = true
            accessDenied = false
        case .denied, .restricted:
            isConnected = false
            accessDenied = true
        case .notDetermined, .writeOnly:
            isConnected = false
            accessDenied = false
        @unknown default:
            isConnected = false
            accessDenied = false
        }
    }

    func requestAccess() async -> Bool {
        do {
            // macOS 14+ uses requestFullAccessToEvents
            if #available(macOS 14.0, *) {
                let granted = try await eventStore.requestFullAccessToEvents()
                await MainActor.run {
                    self.isConnected = granted
                    self.accessDenied = !granted
                }
                return granted
            } else {
                // Fallback for older macOS
                return await withCheckedContinuation { continuation in
                    eventStore.requestAccess(to: .event) { granted, error in
                        DispatchQueue.main.async {
                            self.isConnected = granted
                            self.accessDenied = !granted
                        }
                        if let error = error {
                            print("[EventKitProvider] Access error: \(error)")
                        }
                        continuation.resume(returning: granted)
                    }
                }
            }
        } catch {
            print("[EventKitProvider] Request access error: \(error)")
            await MainActor.run {
                self.isConnected = false
                self.accessDenied = true
            }
            return false
        }
    }

    // MARK: - Event Fetching

    func fetchEvents(from startDate: Date, to endDate: Date) async throws -> [CalendarEvent] {
        guard isConnected else {
            throw CalendarError.accessDenied
        }

        // Get all calendars
        let calendars = eventStore.calendars(for: .event)

        // Create predicate for date range
        let predicate = eventStore.predicateForEvents(
            withStart: startDate,
            end: endDate,
            calendars: calendars
        )

        // Fetch and filter events
        let ekEvents = eventStore.events(matching: predicate)
            .filter { !$0.isAllDay }  // Skip all-day events
            .sorted { $0.startDate < $1.startDate }

        // Convert to CalendarEvent model
        return ekEvents.map { event in
            CalendarEvent(
                id: event.eventIdentifier ?? UUID().uuidString,
                title: event.title ?? "Untitled",
                startDate: event.startDate,
                endDate: event.endDate,
                isAllDay: event.isAllDay,
                calendarName: event.calendar?.title ?? "Unknown",
                calendarColor: event.calendar?.cgColor.flatMap { Color(cgColor: $0) }
            )
        }
    }

    // MARK: - Disconnect

    func disconnect() {
        isConnected = false
    }

    // MARK: - System Preferences

    func openSystemPreferences() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Calendars") {
            NSWorkspace.shared.open(url)
        }
    }

    // MARK: - Debug Info

    func getCalendarInfo() -> [(name: String, color: Color?, eventCount: Int)] {
        guard isConnected else { return [] }

        let calendars = eventStore.calendars(for: .event)
        let today = Calendar.current.startOfDay(for: Date())
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: today)!

        return calendars.map { calendar in
            let predicate = eventStore.predicateForEvents(
                withStart: today,
                end: tomorrow,
                calendars: [calendar]
            )
            let eventCount = eventStore.events(matching: predicate).count
            let color = calendar.cgColor.flatMap { Color(cgColor: $0) }

            return (name: calendar.title, color: color, eventCount: eventCount)
        }
    }
}
