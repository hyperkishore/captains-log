// CalendarModels.swift
// Captain's Log - Calendar Integration Models

import Foundation
import SwiftUI

// MARK: - Calendar Event

struct CalendarEvent: Identifiable, Hashable {
    let id: String
    let title: String
    let startDate: Date
    let endDate: Date
    let isAllDay: Bool
    let calendarName: String
    let calendarColor: Color?

    var durationMinutes: Int {
        Int(endDate.timeIntervalSince(startDate) / 60)
    }

    var isHappeningNow: Bool {
        let now = Date()
        return startDate <= now && endDate > now
    }

    var minutesUntilStart: Int {
        max(0, Int(startDate.timeIntervalSince(Date()) / 60))
    }

    var minutesUntilEnd: Int {
        max(0, Int(endDate.timeIntervalSince(Date()) / 60))
    }

    // For display: "Team Standup in 45m" or "ends in 12m"
    var displayTime: String {
        if isHappeningNow {
            return "ends in \(minutesUntilEnd)m"
        }
        let mins = minutesUntilStart
        if mins >= 60 {
            let hours = mins / 60
            let remainingMins = mins % 60
            return remainingMins > 0 ? "in \(hours)h \(remainingMins)m" : "in \(hours)h"
        }
        return "in \(mins)m"
    }

    // For deduplication (same event from multiple providers)
    func matches(_ other: CalendarEvent) -> Bool {
        return title == other.title &&
               abs(startDate.timeIntervalSince(other.startDate)) < 60 &&
               abs(endDate.timeIntervalSince(other.endDate)) < 60
    }

    // Hashable conformance
    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }

    static func == (lhs: CalendarEvent, rhs: CalendarEvent) -> Bool {
        lhs.id == rhs.id
    }
}

// MARK: - Focus Suggestion

struct FocusSuggestion {
    let goalName: String
    let durationMinutes: Int
    let freeMinutes: Int

    var displayText: String {
        "\(freeMinutes)m free — Start \"\(goalName)\"?"
    }

    var shortDisplayText: String {
        "\(freeMinutes)m free — \(goalName)"
    }
}

// MARK: - Calendar Error

enum CalendarError: Error, LocalizedError {
    case accessDenied
    case notConfigured
    case fetchFailed(String)

    var errorDescription: String? {
        switch self {
        case .accessDenied:
            return "Calendar access denied"
        case .notConfigured:
            return "Calendar not configured"
        case .fetchFailed(let message):
            return "Failed to fetch events: \(message)"
        }
    }
}
