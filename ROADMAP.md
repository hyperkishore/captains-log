# Captain's Log: Product Roadmap

## Vision

**"Your work, automatically journaled. Your time, honestly understood."**

Captain's Log is a personal activity tracking system that passively captures your digital work life and surfaces insights at the right moment — not buried in dashboards you'll never check, but pushed to you as a daily rhythm.

The name says it all: a *log*. A quiet, honest record of where your time goes. Combined with goal tracking to help you spend it where you intend.

---

## The Honest Assessment (April 2026)

### What the Data Shows

| Period | Activity Events | Active Days | Reality |
|--------|----------------|-------------|---------|
| Jan 15–29 | 2,622 | 15 | Built the product, used it while building |
| Jan 30–Mar 31 | 0 | 0 | Complete abandonment — daemon wasn't running |
| Apr 1–now | 35 | 1 | Restarted, coming back |

**Focus sessions**: 11 total, last one Jan 26.
**Key insight**: The daemon ran for 2 weeks, stopped, and nobody noticed for 2 months.

### Root Causes

1. **No daily pull**: Nothing brings you back. No notification, no morning ping, no habit trigger.
2. **Value buried in dashboards**: Rich data exists but you have to seek it out — and you don't.
3. **Daemon reliability**: It stopped and there was no alert. Silent failure = invisible tool.

### What Works Well

- Passive activity tracking (app switches, window titles, idle detection, screenshots)
- AI summarization with Claude
- Goal tracking and focus session infrastructure
- SQLite local-first architecture
- Menu bar app and floating widget
- Optimization engine analysis (DEAL, interrupts, context switches)

---

## Core Design Principles

### 1. Passive Capture, Active Reflection
The tracking is invisible. The insights are pushed. You never "use" the tracker — you *receive* its output.

### 2. The Right Data at the Right Time
- **Morning**: What did yesterday look like? What's the plan?
- **During work**: Ambient awareness (menu bar total, widget timer)
- **Evening**: Here's what you actually did today
- **Weekly**: Patterns, trends, honest assessment

### 3. Honest Mirror, Not Gamification
Streaks and scores can motivate, but the primary value is *truth*. "You spent 3 hours in Slack today" is more useful than a focus score of 7/10.

### 4. Goals Give Direction
Passive tracking answers "where did my time go?" Goal tracking answers "did my time go where I wanted?" Both matter.

---

## The Daily Rhythm (Core Loop)

```
  6:00 PM YESTERDAY                    9:00 AM TODAY
  ┌─────────────────┐                  ┌─────────────────┐
  │ Evening Digest   │                  │ Morning Briefing │
  │                  │                  │                  │
  │ Today: 6h 23m    │                  │ Yesterday: 6h    │
  │ Chrome    2h 40m │                  │ Deep work: 3.2h  │
  │ VS Code   2h 10m │                  │                  │
  │ Slack     1h 33m │                  │ Today's calendar:│
  │                  │                  │ 2 meetings, 4h   │
  │ Most focused:    │                  │ free for focus   │
  │ 10am-12pm        │                  │                  │
  │                  │                  │ Suggestion:      │
  │ AI: "Productive  │                  │ Start Deep Work  │
  │ coding day,      │                  │ at 9:30am        │
  │ shipped feature" │                  └─────────────────┘
  └─────────────────┘
              │
              ▼ DURING WORK
  ┌─────────────────────────────────┐
  │ Menu Bar: ● 3h 12m              │  ← Glanceable
  │ Widget: Deep Work  18:42  ●●○○  │  ← When focusing
  │ Goal tracking running silently  │  ← Passive
  └─────────────────────────────────┘
              │
              ▼ FRIDAY 5 PM
  ┌─────────────────────────────────┐
  │ Weekly Digest                   │
  │ This week: 28h active           │
  │ vs last week: 32h               │
  │ Most productive: Tuesday        │
  │ Top: Chrome (12h), Code (8h)    │
  │ Deep work hours: 14h            │
  │ Slack grew 20% vs last week     │
  └─────────────────────────────────┘
```

**This loop is what was missing.** The evening digest is the single most important feature to build.

---

## Feature Inventory: What Exists

### Tier 1: Working & Core
| Feature | Status | Value |
|---------|--------|-------|
| Passive activity tracking | Working | Foundation — captures all app usage |
| AI 5-minute summaries | Working | Rich context from Claude |
| Screenshot capture | Working | Visual record every 5 min + app change |
| SQLite database (local-first) | Working | Fast, private, reliable |
| CLI (start/stop/status/health) | Working | Daemon management |
| FastAPI web dashboard | Working | Timeline, analytics, insights |
| Focus goals & sessions | Working | Goal-based focus tracking |
| Pomodoro timer | Working | Session-based work intervals |
| Menu bar app (Swift) | Working | Glanceable daily total + goals |
| Floating focus widget (Swift) | Working | Ambient timer during sessions |

### Tier 2: Built but Underused
| Feature | Status | Issue |
|---------|--------|-------|
| Optimization engine (DEAL, interrupts, context switches) | Built | Only accessible via CLI — not surfaced |
| Daily briefing generator | Built | Never wired to notifications |
| Weekly report generator | Built | Only via CLI command |
| Next.js frontend | Built | Duplicate of FastAPI dashboard |
| Cloud sync | Built | Railway backend dead (404) |

### Tier 3: Missing (Causes Abandonment)
| Feature | Impact |
|---------|--------|
| **Daily digest notification** | No daily pull = no habit |
| **Daemon health alert** | Silent failure = invisible tool |
| **`captains-log today`** (quick summary) | Can't quickly check the day |
| **`captains-log recall`** (query history) | Can't ask questions about past |
| **launchd auto-start verified** | Daemon should survive reboots |

---

## Roadmap: Prioritized by "What Makes You Come Back"

### Phase 0: Foundation (NOW)
**Goal: The daemon runs reliably and you know when it doesn't.**

- [ ] Verify launchd auto-start is installed and working
- [ ] Add daemon health notification (if no activity logged in 1 hour → macOS alert)
- [ ] Fix cloud sync (either fix Railway or remove dead code)
- [ ] `captains-log today` — quick terminal summary of current day

### Phase 1: The Daily Pull
**Goal: A notification at 6pm that makes you glance at your day. This is the #1 priority.**

- [ ] macOS notification at configurable time (default 6pm)
- [ ] Content: hours active, top 3 apps, AI-generated 1-sentence narrative
- [ ] Clicking notification opens dashboard to today's timeline
- [ ] `captains-log digest` — generate/view the daily digest on demand
- [ ] Morning briefing notification (optional, default 9am)
- [ ] Briefing: yesterday's summary + today's calendar context + suggestion

### Phase 2: Understanding Where Time Goes
**Goal: Make time-spent analysis effortless and honest.**

- [ ] `captains-log recall "last Thursday"` — natural language history query
- [ ] `captains-log week` — this week vs last week comparison
- [ ] Surface optimization engine insights in the daily/weekly digest
  - Context switches count
  - Interrupt patterns (Slack/email frequency)
  - Deep work vs shallow work ratio
- [ ] Improve dashboard with "time spent" as the primary view
  - App usage pie chart front and center
  - Deep work hours trend line
  - "Where did today go?" narrative

### Phase 3: Proactive AI
**Goal: AI surfaces insights at the right moment, not when you ask.**

| Trigger | Action |
|---------|--------|
| 9:00 AM | Morning briefing notification |
| 6:00 PM | Evening digest notification |
| Friday 5 PM | Weekly summary notification |
| Off-goal >10min during focus | Gentle nudge (amber border on widget) |
| Unusual pattern detected | "You spent 2x more time in Slack than usual today" |

### Phase 4: Calendar Integration
**Goal: Smart scheduling around meetings.**

- [ ] macOS EventKit integration (read calendar events)
- [ ] "Next meeting in Xh" in menu bar
- [ ] "You have 2h free — start focus?" smart suggestion
- [ ] Meeting fragmentation warnings
- [ ] Google Calendar as optional second source

### Phase 5: Emotional Design
**Goal: Make progress feel rewarding.**

- [ ] Session completion sound + subtle animation
- [ ] Milestone notifications (10h, 50h, 100h deep work)
- [ ] Weekly achievement summary
- [ ] Goal streak visualization in menu bar

### Phase 6: Weekly Insights & Sharing
**Goal: Reflection drives improvement, sharing drives accountability.**

- [ ] Weekly summary generation (already built — needs scheduling)
- [ ] Shareable weekly card image
- [ ] Week-over-week comparison
- [ ] Export: "What I accomplished this week" for standups/updates

---

## What NOT to Build (Learned from Experience)

| Feature | Why Skip |
|---------|----------|
| Team features | Different product, different market |
| Mobile app | Desktop focus is the niche |
| Complex dashboards with 10 charts | Nobody looks at dashboards unprompted |
| Integrations with 10+ tools | Start with macOS native, add one at a time |
| AI chat interface | Natural language recall is enough |
| Viral loops / growth hacks | Build for yourself first |
| Second frontend framework | One dashboard (FastAPI) is enough |

---

## Technical Decisions

### Keep
- **Python + PyObjC** for daemon (macOS native APIs)
- **SQLite + WAL** for storage (fast, local, reliable)
- **Claude AI** for summarization (quality justifies cost)
- **Swift** for menu bar + widget (native macOS feel)
- **FastAPI + Jinja2** for dashboard (server-rendered, fast)

### Simplify
- **Remove cloud sync** or fix the Railway deployment — dead infrastructure is worse than no infrastructure
- **Consolidate to one frontend** — FastAPI dashboard is sufficient, Next.js is duplicative
- **Surface optimization engine insights via digest** — don't require CLI commands to see them

### Add
- **macOS UserNotifications** for daily/weekly digests
- **APScheduler integration** in orchestrator for timed digests
- **Natural language query** via Claude for `recall` command

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|---------------|
| Daemon uptime | >99% (crashes auto-recover) | launchd KeepAlive + health alerts |
| Daily digest viewed | 5+ days/week | Notification interaction tracking |
| `today`/`recall` usage | 3+ times/week | CLI command logging |
| Consecutive days tracked | 30+ days | Activity log continuity |
| Focus sessions/week | 5+ | focus_sessions table |

The most important metric: **Is the daemon running, and do you look at the digest?** Everything else follows from that.

---

## Competitive Position

Captain's Log uniquely combines:
1. **Automatic passive tracking** (like RescueTime) — no manual time entry
2. **Goal-based focus sessions** (like Flow) — intentional deep work
3. **Local-first privacy** (like ActivityWatch) — data stays on your Mac
4. **AI-powered insights** (unique) — Claude summarizes and answers questions
5. **Push-based engagement** (the key differentiator) — insights come to you

No existing tool does all five. Most track OR focus OR analyze. Captain's Log does all three, and with the daily digest, it *pushes* the value instead of waiting for you to pull it.

---

## Current Version: 0.2.02

See `CLAUDE.md` for implementation details and session history.
