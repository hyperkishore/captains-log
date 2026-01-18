// CalendarProvider.swift
// Captain's Log - Calendar Provider Protocol
//
// Protocol-based design for multiple calendar sources.
// Implement this protocol to add new calendar providers (e.g., Google Calendar, Outlook).

import Foundation

// MARK: - Calendar Provider Protocol

protocol CalendarProvider {
    /// Unique identifier for this provider (e.g., "eventkit", "google")
    var id: String { get }

    /// Display name (e.g., "macOS Calendar", "Google Calendar")
    var name: String { get }

    /// Whether the provider is currently connected and can fetch events
    var isConnected: Bool { get }

    /// Whether this provider requires explicit user authorization
    var requiresAuth: Bool { get }

    /// Request access to the calendar
    /// - Returns: true if access was granted
    func requestAccess() async -> Bool

    /// Fetch events within a date range
    /// - Parameters:
    ///   - from: Start date
    ///   - to: End date
    /// - Returns: Array of calendar events
    func fetchEvents(from: Date, to: Date) async throws -> [CalendarEvent]

    /// Disconnect from this provider
    func disconnect()
}

// MARK: - Default Implementation

extension CalendarProvider {
    /// Fetch today's events (convenience method)
    func fetchTodaysEvents() async throws -> [CalendarEvent] {
        let start = Calendar.current.startOfDay(for: Date())
        let end = Calendar.current.date(byAdding: .day, value: 1, to: start)!
        return try await fetchEvents(from: start, to: end)
    }

    /// Fetch events for the next N hours
    func fetchEvents(nextHours hours: Int) async throws -> [CalendarEvent] {
        let start = Date()
        let end = Calendar.current.date(byAdding: .hour, value: hours, to: start)!
        return try await fetchEvents(from: start, to: end)
    }
}
