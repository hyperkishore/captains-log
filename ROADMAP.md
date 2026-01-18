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

#### Implementation: macOS EventKit (Native)

**Why EventKit over Google Calendar API:**
- No OAuth flow needed (simpler UX)
- Reads ALL calendars synced to macOS (iCloud, Google, Outlook, Exchange)
- Native Swift integration with menu bar app

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
