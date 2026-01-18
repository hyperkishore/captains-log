# Captain's Log: Product Roadmap

## 80-20 Analysis: What Features Drive 80% of Value

### Daily Usage (HIGH FREQUENCY - the 20%)
| Feature | Usage | Why It Matters |
|---------|-------|----------------|
| **Start Focus Session** | 5-10x/day | The core action - without this, nothing else matters |
| **Glance at Timer** | 50x/day | Ambient awareness keeps you accountable |
| **Daily Time Total** | 10x/day | "How's my day going?" answered in 1 second |
| **Goal Streaks** | 5x/day | Visual motivation - don't break the chain |

### Weekly Usage (MEDIUM FREQUENCY)
| Feature | Usage | Why It Matters |
|---------|-------|----------------|
| Daily Summary | 1x/day | Reflection and closure |
| Weekly Report | 1x/week | Trends and patterns |
| App Usage Breakdown | 1x/week | Understanding time allocation |

### Rarely Used (LOW VALUE for daily experience)
| Feature | Usage | Reality |
|---------|-------|---------|
| Screenshot Browser | Monthly | Nice for recall, but not daily |
| Detailed Analytics | Monthly | Information overload |
| Optimization Metrics | Weekly | Too abstract for most users |
| Settings | Rarely | Set once, forget |

---

## The Core Loop (What Makes Users Return)

```
┌─────────────────────────────────────────────────────┐
│                    DAILY RHYTHM                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│   MORNING (9am)                                      │
│   ┌─────────────────────────────────────┐           │
│   │ "Yesterday: 4.5h deep work          │           │
│   │  Top: Captain's Log (2h), Writing   │           │
│   │  Today's goals ready to start"      │           │
│   └─────────────────────────────────────┘           │
│              ↓                                       │
│   WORK DAY                                          │
│   ┌─────────────────────────────────────┐           │
│   │ Click goal → Timer starts           │           │
│   │ Floating widget shows countdown     │           │
│   │ Session completes → Streak updates  │           │
│   └─────────────────────────────────────┘           │
│              ↓                                       │
│   EVENING (6pm)                                     │
│   ┌─────────────────────────────────────┐           │
│   │ "Today: 5.2h focused                │           │
│   │  3 goals progressed                 │           │
│   │  Great day!"                        │           │
│   └─────────────────────────────────────┘           │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## Three Perspectives

### AI Developer: Technical Excellence

**Current State:**
- Passive tracking works well
- AI summarization exists but isn't surfaced proactively
- Data is rich but insights are buried

**Opportunity:**
The AI should be **proactive, not reactive**:

| Trigger | AI Action |
|---------|-----------|
| 9:00 AM | Push morning briefing: "Yesterday you focused 4h. Goals for today?" |
| After 2h meetings | Nudge: "Heavy meeting morning. Block 2h for deep work?" |
| 5:00 PM | Evening summary: "You accomplished X, Y, Z" |
| Off-goal 10min | Gentle: "You started 'Writing' but you're in Slack..." |
| Week end | Weekly insight: "Your most productive day was Tuesday" |

**Technical Implementation:**
- macOS notifications via UserNotifications framework
- Smart scheduling based on calendar integration
- Context-aware nudging (don't interrupt deep work)

---

### Product Designer: User Experience

**Design Principles:**
1. **Zero friction** - One click to start, zero clicks to track
2. **Ambient, not demanding** - Glanceable information, never interrupting
3. **Emotional design** - Celebrate wins, gentle accountability
4. **Progressive disclosure** - Simple surface, depth when needed

**The Perfect Menu Bar:**
```
┌─────────────────────────────────────┐
│ Today                        2.5h   │  ← Glanceable daily total
├─────────────────────────────────────┤
│ ▶ Deep Work          🟢🟢🟡⚪⚪   │  ← Goals with streaks
│ ▸ Learn Swift UI     🟡🔴🟢🔴⚪   │
│ ▶ Writing            🔴🔴🔴🔴⚪   │
├─────────────────────────────────────┤
│ Yesterday: 4.2h focused             │  ← Proactive insight
│    "Great progress on Captain's Log" │
├─────────────────────────────────────┤
│ + Quick Focus    Dashboard          │
└─────────────────────────────────────┘
```

**When Timer is Running:**
```
┌─────────────────────────────────────┐
│ Deep Work                   18:42   │  ← Current session
│ Session 2 of 4  ●●○○               │
├─────────────────────────────────────┤
│ [▶]  [⏹]  [Widget]                 │  ← Minimal controls
├─────────────────────────────────────┤
│ Today                        3.2h   │
└─────────────────────────────────────┘
```

---

### Growth Marketer: Adoption & Retention

**The Hook:** "Know exactly where your time goes"

**The Habit Loop:**
```
CUE        → Menu bar icon shows your daily time
ROUTINE    → Start focus session with one click
REWARD     → See streak update, hear completion sound
INVESTMENT → Goals with progress over days/weeks
```

**Retention Mechanics:**
| Mechanic | Implementation |
|----------|----------------|
| **Streaks** | Visual 🟢🟡🔴 circles - don't break the chain |
| **Daily Total** | Gamification without points - "4.5h today!" |
| **Weekly Email** | "Your week: 22h focused, 15% more than last week" |
| **Milestones** | "100 hours of deep work!" notifications |

**Share Moments:**
- Weekly summary image for Twitter/LinkedIn
- "I focused 20h this week" shareable card
- Streak screenshots (like Duolingo)

**Viral Loop:**
```
User focuses → Sees progress → Shares achievement
                                    ↓
                           Friend sees post
                                    ↓
                           Downloads Captain's Log
                                    ↓
                           Becomes new user
```

---

## Roadmap: Prioritized by Impact

### Phase 1: Core Loop Excellence ✅ DONE
- [x] Menu bar app with goals
- [x] Floating timer widget
- [x] Daily time tracking
- [x] Goal streaks visualization
- [x] One-click focus start

### Phase 2: Proactive AI
**Goal: AI surfaces insights at the right moment**

| Feature | Priority | Effort |
|---------|----------|--------|
| Morning briefing notification | P0 | 2 days |
| Evening summary notification | P0 | 1 day |
| "Yesterday" card in menu bar | P0 | 1 day |
| Off-goal gentle nudge | P1 | 2 days |
| Smart notification timing | P2 | 3 days |

**Files to modify:**
- `src/captains_log/notifications/` (NEW)
- `MenuBarApp/CaptainsLogMenuBar.swift` - Add yesterday card

### Phase 3: Emotional Design
**Goal: Make progress feel rewarding**

| Feature | Priority | Effort |
|---------|----------|--------|
| Session completion sound | P0 | 1 hour |
| Session completion animation | P1 | 1 day |
| Milestone notifications (10h, 50h, 100h) | P1 | 1 day |
| Weekly achievement badge | P2 | 2 days |

### Phase 4: Weekly Insights
**Goal: Reflection drives improvement**

| Feature | Priority | Effort |
|---------|----------|--------|
| Weekly summary generation | P0 | 2 days |
| Shareable weekly card image | P1 | 2 days |
| Week-over-week comparison | P1 | 1 day |
| Top productive day/time insights | P2 | 1 day |

### Phase 5: Calendar Integration (NEXT)
**Goal: Smart scheduling around meetings**

#### Why This Matters
- Users don't know when to focus without seeing their calendar
- "2 hours until next meeting" is actionable intelligence
- Meeting fragmentation is the #1 productivity killer

#### Features

| Feature | Priority | Value |
|---------|----------|-------|
| Read macOS Calendar events | P0 | Foundation for everything |
| "Next meeting in Xh" in menu bar | P0 | Instant awareness |
| "You have 2h free - start focus?" | P0 | Smart nudging |
| Show meeting blocks in timeline | P1 | Visual context |
| "Meeting-heavy day" warning | P1 | Daily planning |
| Auto-detect meeting from Zoom/Meet | P2 | No manual tracking |

---

## Scalable Calendar Architecture

### Design Principles
1. **Protocol-based** - Abstract calendar sources behind unified interface
2. **EventKit first** - Ship fast with native macOS
3. **Google Calendar next** - Add OAuth flow in iteration 2
4. **Local-first, cloud-optional** - Privacy by default, sync when needed

### Phased Implementation

#### Phase 5a: EventKit Foundation (Week 1)
- CalendarProvider protocol (Swift)
- EventKitProvider implementation
- Menu bar integration
- Local caching in SQLite

#### Phase 5b: Google Calendar (Week 2-3)
- GoogleCalendarProvider implementation
- OAuth 2.0 flow in menu bar app (opens browser, handles redirect)
- Token storage in Keychain
- Provider selection UI in settings

#### Phase 5c: Cloud Sync - Optional (Week 4+)
- Calendar events sync to cloud (encrypted)
- Cross-device availability
- User opt-in only

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Menu Bar App                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              CalendarManager                         │    │
│  │  - Aggregates events from all providers              │    │
│  │  - Deduplicates (same event from multiple sources)   │    │
│  │  - Provides unified API to UI                        │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│            ┌─────────────┴─────────────┐                    │
│            ▼                           ▼                    │
│  ┌─────────────────┐         ┌─────────────────┐           │
│  │ EventKitProvider │         │ GoogleProvider  │           │
│  │ (Phase 5a)       │         │ (Phase 5b)      │           │
│  └─────────────────┘         └─────────────────┘           │
│            │                           │                    │
│            ▼                           ▼                    │
│     macOS Calendar              Google Calendar API         │
│     (via EventKit)              (via OAuth 2.0)             │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌─────────────────────┐
              │   Local SQLite DB   │
              │   (cached events)   │
              └─────────────────────┘
                          │
                          ▼ (Optional - Phase 5c)
              ┌─────────────────────┐
              │   Cloud Sync        │
              │   (encrypted)       │
              └─────────────────────┘
```

### CalendarProvider Protocol (Swift)

```swift
protocol CalendarProvider {
    var id: String { get }
    var name: String { get }
    var isConnected: Bool { get }
    var requiresAuth: Bool { get }

    func requestAccess() async -> Bool
    func fetchEvents(from: Date, to: Date) async throws -> [CalendarEvent]
    func disconnect()
}

// Unified event model (provider-agnostic)
struct CalendarEvent: Identifiable, Hashable {
    let id: String
    let providerId: String  // "eventkit" or "google"
    let externalId: String  // Original ID from provider
    let title: String
    let startDate: Date
    let endDate: Date
    let isAllDay: Bool
    let location: String?
    let meetingUrl: String?  // Zoom/Meet link if detected
    let calendarName: String
    let calendarColor: Color?

    // For deduplication
    func matches(_ other: CalendarEvent) -> Bool {
        // Same event synced from multiple sources
        return title == other.title &&
               abs(startDate.timeIntervalSince(other.startDate)) < 60 &&
               abs(endDate.timeIntervalSince(other.endDate)) < 60
    }
}
```

### CalendarManager (Aggregator)

```swift
class CalendarManager: ObservableObject {
    @Published var providers: [CalendarProvider] = []
    @Published var events: [CalendarEvent] = []
    @Published var nextEvent: CalendarEvent?
    @Published var freeMinutes: Int = 0

    private let cache: CalendarCache  // SQLite

    init() {
        // Always try EventKit first
        let eventKit = EventKitProvider()
        providers.append(eventKit)

        // Check if Google is configured
        if let google = GoogleCalendarProvider.loadFromKeychain() {
            providers.append(google)
        }
    }

    func fetchAllEvents() async {
        var allEvents: [CalendarEvent] = []

        for provider in providers where provider.isConnected {
            let events = try? await provider.fetchEvents(
                from: Date(),
                to: Calendar.current.date(byAdding: .day, value: 1, to: Date())!
            )
            allEvents.append(contentsOf: events ?? [])
        }

        // Deduplicate and sort
        events = deduplicateEvents(allEvents)
            .filter { !$0.isAllDay }
            .sorted { $0.startDate < $1.startDate }

        // Cache locally
        cache.store(events)

        updateNextEvent()
    }

    private func deduplicateEvents(_ events: [CalendarEvent]) -> [CalendarEvent] {
        var unique: [CalendarEvent] = []
        for event in events {
            if !unique.contains(where: { $0.matches(event) }) {
                unique.append(event)
            }
        }
        return unique
    }
}
```

### Google OAuth Flow (Phase 5b)

```swift
class GoogleCalendarProvider: CalendarProvider {
    let id = "google"
    let name = "Google Calendar"
    let requiresAuth = true

    private var accessToken: String?
    private var refreshToken: String?

    var isConnected: Bool { accessToken != nil }

    // OAuth configuration
    private let clientId = "YOUR_CLIENT_ID.apps.googleusercontent.com"
    private let redirectUri = "captainslog://oauth/google"
    private let scopes = ["https://www.googleapis.com/auth/calendar.readonly"]

    func requestAccess() async -> Bool {
        // 1. Build OAuth URL
        let authUrl = buildAuthUrl()

        // 2. Open in default browser
        NSWorkspace.shared.open(authUrl)

        // 3. Wait for redirect (handled by URL scheme)
        // App delegate handles: captainslog://oauth/google?code=XXX

        // 4. Exchange code for tokens
        // 5. Store in Keychain

        return true
    }

    func fetchEvents(from: Date, to: Date) async throws -> [CalendarEvent] {
        guard let token = accessToken else { throw AuthError.notAuthenticated }

        // Call Google Calendar API
        let url = URL(string: "https://www.googleapis.com/calendar/v3/calendars/primary/events")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode(GoogleEventsResponse.self, from: data)

        return response.items.map { $0.toCalendarEvent(providerId: id) }
    }
}
```

### URL Scheme Registration (Info.plist)

```xml
<key>CFBundleURLTypes</key>
<array>
    <dict>
        <key>CFBundleURLName</key>
        <string>OAuth Callback</string>
        <key>CFBundleURLSchemes</key>
        <array>
            <string>captainslog</string>
        </array>
    </dict>
</array>
```

### Settings UI for Calendar Sources

```
┌─────────────────────────────────────────────────────────────┐
│ Calendar Sources                                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ✅ macOS Calendar (EventKit)                    Connected   │
│     Calendars: Work, Personal, Holidays                      │
│                                                              │
│  ⬜ Google Calendar                         [Connect]        │
│     Sign in to see Google Calendar events                    │
│                                                              │
│  ⬜ Microsoft Outlook                       Coming Soon      │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  ☁️ Cloud Sync                              [ ] Enabled     │
│     Sync calendar cache across devices                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Implementation: macOS EventKit (Phase 5a)

**Why EventKit first:**
- No OAuth complexity
- Ships in 1 week
- Works for users with synced calendars
- Validates the UX before adding complexity

#### Menu Bar States

**State A: No Active Session, Calendar Connected**
```
┌─────────────────────────────────────┐
│ Captain's Log                    🟢 │
├─────────────────────────────────────┤
│ Today                         1.2h  │
│ Team Standup in 45m                 │
├─────────────────────────────────────┤
│ GOALS                               │
│ ▶ Deep Work            🟢🟢🟡⚪⚪  │
│ ▸ Learn Swift UI       🟡🔴🟢🔴⚪  │
│ ▶ Writing              🔴🔴🔴🔴⚪  │
├─────────────────────────────────────┤
│ 45m free — Start "Deep Work"?       │  ← Contextual suggestion
├─────────────────────────────────────┤
│ + Quick Focus      Dashboard        │
│ Quit                                │
└─────────────────────────────────────┘
```

**State B: Active Session with Upcoming Meeting**
```
┌─────────────────────────────────────┐
│ Deep Work                    18:42  │
│ ●●○○  Session 2 of 4                │
│ [Widget] [Pause] [Stop]             │
├─────────────────────────────────────┤
│ Today                         2.1h  │
│ Warning: Meeting in 12m             │  ← Warning when <15m
├─────────────────────────────────────┤
│ GOALS                               │
│ ...                                 │
└─────────────────────────────────────┘
```

#### Calendar Row Design Rules
| Condition | Display |
|-----------|---------|
| Next meeting >60m away | `{Title} in {X}h {Y}m` |
| Next meeting 15-60m away | `{Title} in {X}m` |
| Next meeting <15m away | `Warning: Meeting in {X}m` (orange) |
| Currently in meeting | `In: {Title} (ends in {X}m)` |
| No more meetings today | `No more meetings today` |
| Meeting-heavy (>4h) | Show warning badge |

#### Suggestion Row Logic
| Free Time | Suggestion |
|-----------|------------|
| ≥90m | `{X}m free — Start "{Best Goal}"?` (suggest 50m) |
| 60-89m | `{X}m free — Start "{Best Goal}"?` (suggest 50m) |
| 30-59m | `{X}m free — Quick 25m focus?` |
| 15-29m | `{X}m free — Quick 15m focus?` |
| <15m | No suggestion shown |

#### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `MenuBarApp/CalendarManager.swift` | CREATE | EventKit integration |
| `MenuBarApp/CaptainsLogMenuBar.swift` | MODIFY | Add calendar display, suggestions |
| `MenuBarApp/Info.plist` | MODIFY | Add calendar permission description |

### Phase 6: Social & Growth
**Goal: Word of mouth growth**

| Feature | Priority | Effort |
|---------|----------|--------|
| Shareable weekly summary image | P0 | 2 days |
| Copy-to-clipboard stats | P0 | 1 day |
| Twitter/LinkedIn share button | P1 | 1 day |
| Referral tracking | P2 | 2 days |

---

## Metrics to Track

### Activation
- % of installs that start first focus session
- Time to first focus session

### Engagement
- Daily active users (DAU)
- Focus sessions per user per day
- Average session length

### Retention
- D1, D7, D30 retention
- Streak length distribution
- Users with 7+ day streaks

### Growth
- Weekly summary shares
- Referral installs
- Organic mentions

---

## What NOT to Build

| Feature | Why Skip |
|---------|----------|
| Team features | Adds complexity, different product |
| Mobile app | Desktop focus is the niche |
| Detailed analytics dashboard | Users don't look at it |
| Integrations with 10+ tools | Start with 1-2 that matter |
| AI chat interface | Overkill for the use case |

---

## Summary: The 80-20 Focus

**Build these (20% of effort, 80% of value):**
1. ✅ One-click focus start
2. ✅ Glanceable daily time
3. ✅ Visual goal streaks
4. ⬜ Morning/evening notifications
5. ⬜ Session completion celebration
6. ⬜ Shareable weekly summary

**Skip these (80% of effort, 20% of value):**
- Complex analytics dashboards
- Multiple integrations
- Team collaboration
- Mobile apps
- AI chat interfaces

---

## Market Research: Competitive Landscape (January 2026)

### Category 1: Automatic Time Tracking

| Tool | Strengths | Weaknesses | Pricing |
|------|-----------|------------|---------|
| **RescueTime** | Fully automatic tracking, Focus Sessions, distraction blocking, AI insights | Web-only analytics, no local data, limited Mac app, outdated UI | $78-144/year |
| **Timing (Mac)** | Mac-native, beautiful UI, local data, 10+ years of development | Mac-only, subscription required, no focus mode | ~$60/year |
| **ActivityWatch** | Open-source, privacy-first, local storage, cross-platform | No AI insights, no focus features, technical setup | Free |
| **Rize** | AI-powered insights, burnout detection, break reminders | Subscription required, web-focused | ~$100/year |

**Key Insight**: RescueTime dominates but users complain about web-only experience. Timing is loved by Mac users for its local-first approach. Neither combines automatic tracking with goal-based focus sessions.

### Category 2: Focus/Pomodoro Apps

| Tool | Strengths | Weaknesses | Pricing |
|------|-----------|------------|---------|
| **Flow (Mac)** | Beautiful design, Apple ecosystem integration, widgets | No automatic tracking, no activity insights | $5/month |
| **Forest** | Gamification (grow trees), real tree planting | Mobile-first, no desktop analytics | $4 one-time |
| **Be Focused** | Apple-native, simple Pomodoro | No automatic tracking, basic features | Free/Premium |
| **Focus To-Do** | Combines Pomodoro with task management | Complex UI, no activity tracking | Freemium |

**Key Insight**: Focus apps are either (1) simple timers without insights or (2) complex task managers. None automatically track what you're actually doing during focus time.

### Category 3: Calendar-Aware Scheduling

| Tool | Strengths | Weaknesses | Pricing |
|------|-----------|------------|---------|
| **Reclaim.ai** | AI scheduling, Focus Time protection, Microsoft/Google integration | Team-focused, complex setup, subscription | $8-15/user/month |
| **Clockwise** | Focus time blocks, team sync, MCP integration | Enterprise-focused, Google Calendar only | $6-12/user/month |
| **Motion** | AI task scheduling, automatic rescheduling | Complex, expensive, overkill for individuals | $19/month |

**Key Insight**: Calendar tools focus on *scheduling* focus time, not *tracking* whether you actually focused. They're team-oriented and require significant setup.

### Category 4: Screen Time Monitoring

| Tool | Strengths | Weaknesses | Pricing |
|------|-----------|------------|---------|
| **macOS Screen Time** | Built-in, free, app limits | No productivity insights, no goals | Free |
| **Flipd** | Focus lock mode, group challenges | Mobile-first, no Mac analytics | Freemium |
| **Freedom** | Cross-platform blocking, scheduled sessions | No tracking/analytics, just blocking | $7/month |

**Key Insight**: These tools block distractions but don't help you understand where your time goes or build focus habits.

---

## Captain's Log Differentiation

### Our Unique Position

**The Gap We Fill**: No existing tool combines:
1. Automatic passive tracking (like RescueTime)
2. Goal-based focus sessions (like Flow)
3. Calendar awareness (like Reclaim)
4. Local-first privacy (like ActivityWatch)
5. AI-powered insights (like Rize)

### Competitive Advantages

| Feature | Captain's Log | RescueTime | Flow | Reclaim |
|---------|--------------|------------|------|---------|
| Automatic tracking | ✅ | ✅ | ❌ | ❌ |
| Local-first data | ✅ | ❌ | ✅ | ❌ |
| Goal-based focus | ✅ | ❌ | ✅ | ❌ |
| Visual streaks | ✅ | ❌ | ❌ | ❌ |
| Calendar integration | Planned | ❌ | ❌ | ✅ |
| AI insights | ✅ | ✅ | ❌ | ❌ |
| Menu bar presence | ✅ | ❌ | ✅ | ❌ |
| Floating widget | ✅ | ❌ | ✅ | ❌ |
| macOS native | ✅ | ❌ | ✅ | ❌ |

### Target User

**Primary Persona**: Solo knowledge worker (developer, writer, designer) who:
- Works primarily on Mac
- Values privacy (doesn't want data in the cloud)
- Wants to understand where time goes without manual tracking
- Uses Pomodoro/focus techniques for deep work
- Cares about building consistent habits (streaks)

**NOT our user**:
- Teams needing shared analytics
- Freelancers needing billing/invoicing
- Mobile-first workers
- Enterprise compliance requirements

---

## Research-Backed Design Decisions

### From Cal Newport's Deep Work Philosophy

> "Focus creates happiness... the satisfaction at the end of a focused day is built-in."

**Applied in Captain's Log**:
- Session completion celebration (emotional reward)
- Daily focus total (visible progress)
- Streak visualization (habit formation)

### From Behavioral Psychology (Habit Loop)

**CUE → ROUTINE → REWARD → INVESTMENT**

| Stage | Captain's Log Implementation |
|-------|------------------------------|
| Cue | Menu bar icon shows daily time |
| Routine | One-click focus start |
| Reward | Streak update, completion sound |
| Investment | Goals with multi-day progress |

### From Market Data (2025-2026)

- **37%** of professional time spent in meetings (opportunity for calendar integration)
- **23 hours/week** average executive meeting time (need meeting-heavy warnings)
- **6 hours/week** lost to context switching (need gentle nudges)
- **7.6 hours/week** saved by AI scheduling tools (opportunity for smart suggestions)
- **26 minutes/day** saved by AI productivity tools (validates AI-powered approach)

---

## Sources

- [Toggl: Best Time Tracking Apps 2026](https://toggl.com/blog/best-time-tracking-apps)
- [Timing: Mac Time Tracking Apps](https://timingapp.com/blog/mac-time-tracking-apps/)
- [Reclaim: Best Pomodoro Timer Apps](https://reclaim.ai/blog/best-pomodoro-timer-apps)
- [Zapier: Best Pomodoro Apps](https://zapier.com/blog/best-pomodoro-apps/)
- [Reclaim.ai](https://reclaim.ai)
- [Clockwise](https://max-productive.ai/ai-tools/clockwise/)
- [Flow App](https://www.flow.app/)
- [ActivityWatch](https://activitywatch.net/)
- [Cal Newport: Time Block Planner](https://www.timeblockplanner.com/)

---

## The Core Problem

**"Value not visible"** - We built sophisticated tracking and AI analysis, but the insights don't surface in a way that feels useful day-to-day.

**Key Metric:** Deep Work Hours - concrete, meaningful, checkable daily.

**Value Prop:** "AI Productivity Co-pilot - Get more done."

The product has:
- ✅ Activity tracking (excellent)
- ✅ AI summaries (sophisticated)
- ✅ Optimization engine (advanced)
- ✅ Focus timer (complete)
- ✅ Dashboard (functional)

But the value is buried. Users need to **dig** to find insights instead of having insights **pushed** to them.

---

## Success Metrics for Public Launch

| Metric | Target |
|--------|--------|
| Day 1 retention | 70% check score next day |
| Day 7 retention | 40% still using |
| Time to value | < 5 minutes |
| Can articulate value | "I save X hours/week" |
| Referral | 10% share with friend |

---

## The "Time Saved" Feature

**Goal:** User sees concrete value and tells others

**The Problem:**
- Abstract metrics (switches, interrupts) don't feel real
- No "aha" moment that makes users share
- ROI isn't visible

**The Fix - Time Saved Counter:**
```
This Week: 2.3 hours saved
This Month: 8.5 hours saved

How? You batched Slack checks (saved 45min)
     You had 2 fewer meetings (saved 1h)
     You avoided Twitter rabbit holes (saved 45min)
```
- Makes the invisible visible
- Concrete, not abstract
- Shareable ("I saved 8 hours this month!")

---

## Simplified Product Vision

**One sentence:** "Know where your time goes and get it back."

**Core loop:**
1. Wake up → See yesterday's score (motivation)
2. Work → Menu bar shows live score (awareness)
3. Slip → Gentle nudge (course correction)
4. End day → See time saved (reward)
5. End week → Email digest (reflection)
6. Repeat

**Key insight:** The goal isn't to show MORE data. It's to show the RIGHT data at the RIGHT time.

---

## Implementation Priority (Week by Week)

### Week 1: Core Engagement Loop
- [ ] Simplify menu bar to show focus score number
- [ ] Add morning notification with yesterday's highlight
- [ ] Create "one number" dashboard view

### Week 2: Progress & Motivation
- [ ] Implement "Time Saved" calculation
- [ ] Add weekly streak visualization
- [ ] Create simple before/after comparison

### Week 3: Polish & Share
- [ ] Weekly email digest
- [ ] Improve first-time experience
- [ ] Add share capability ("I saved 8h this month with Captain's Log")

### Week 4: Public Launch Prep
- [ ] Landing page with clear value prop
- [ ] Installation docs with screenshots
- [ ] Demo mode for website
