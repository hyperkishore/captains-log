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
| Apr 1–5 | 100+ | 5 | Restarted, reliability fixes, daily use resuming |

**Focus sessions**: 11 total, last one Jan 26.
**Key insight**: The daemon ran for 2 weeks, stopped, and nobody noticed for 2 months. Now fixed with watchdog + launchd auto-restart.

### Root Causes (identified Apr 2 — addressed Apr 5-6)

1. **No daily pull**: Nothing brings you back. No notification, no morning ping, no habit trigger. **→ FIXED: Daily digest system, `today`/`week` CLI commands with duration data**
2. **Value buried in dashboards**: Rich data exists but you have to seek it out — and you don't. **→ PARTIALLY FIXED: CLI commands surface insights; dashboard still needs work**
3. **Daemon reliability**: It stopped and there was no alert. Silent failure = invisible tool. **→ FIXED: Watchdog, launchd KeepAlive, smart health alerts, log rotation**

### What Works Well

- Passive activity tracking (app switches, window titles, idle detection, screenshots)
- AI summarization with Claude (updated to claude-haiku-4-5)
- Goal tracking and focus session infrastructure
- SQLite local-first architecture
- Menu bar app and floating widget
- Optimization engine analysis (DEAL, interrupts, context switches)
- Duration calculator — accurate time-in-app from event gaps
- Cloud sync to Supabase via Vercel deployment
- Daemon watchdog with launchd auto-restart
- Pattern detection from 14+ days of historical data

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
| AI 5-minute summaries | Working | Rich context from Claude (claude-haiku-4-5) |
| Screenshot capture | Working | Visual record every 5 min + app change |
| SQLite database (local-first) | Working | Fast, private, reliable |
| CLI (start/stop/status/health) | Working | Daemon management |
| FastAPI web dashboard | Working | Timeline, analytics, insights |
| Focus goals & sessions | Working | Goal-based focus tracking |
| Pomodoro timer | Working | Session-based work intervals |
| Menu bar app (Swift) | Working | Glanceable daily total + goals |
| Floating focus widget (Swift) | Working | Ambient timer during sessions |
| Daemon watchdog (launchd) | Working | Detects brain-dead daemon, auto-restarts |
| launchd auto-start | Working | KeepAlive=true, RunAtLoad=true, ThrottleInterval=30 |
| Log rotation | Working | RotatingFileHandler, 1MB max, 5 backups |
| Duration calculator | Working | Accurate time-in-app from event gaps |
| Cloud sync (Supabase) | Working | Daily stats + AI summaries to captainslog.hyperverge.space |
| Sync deduplication | Working | `synced_at` column prevents re-uploading |

### Tier 2: Built & Functional (Recently Upgraded)
| Feature | Status | Notes |
|---------|--------|-------|
| `captains-log today` | Working | Duration breakdown by app/category, focus hours, most focused hour |
| `captains-log week` | Working | This week vs last week, daily breakdown, top apps, projections |
| `captains-log recall` | Working | Natural language query via Claude |
| Daily digest notification | Working | macOS notification at 6pm with duration data |
| Smart health alerts | Working | Checks IOKit idle time — no false positives during lunch |
| Optimization engine | Built | DEAL, interrupts, context switches — CLI only |
| Pattern detector | Built | Peak hours, context switch spikes, weekly rhythms (14+ day history) |
| Weekly digest generator | Built | Comprehensive weekly summary with trends |
| `captains-log insights` | Built | Shows detected patterns from historical data |
| `captains-log weekly` | Built | Shows weekly digest |
| Next.js frontend | Built | Deployed at captainslog.hyperverge.space with Google OAuth |

### Tier 3: Next to Build
| Feature | Impact |
|---------|--------|
| **Menu bar live focus hours** | "4.2h focused" — ambient daily awareness |
| **Evening digest verification** | Confirm notifications actually fire reliably |
| **Dashboard landing page** | Time breakdown charts, donut chart, weekly bar chart |
| **Morning briefing opt-in** | Yesterday summary + today's plan |

---

## Roadmap: Prioritized by "What Makes You Come Back"

### Phase 0: Foundation -- DONE (Apr 5-6, 2026)
**Goal: The daemon runs reliably and you know when it doesn't.**

- [x] Daemon liveness watchdog (`scripts/daemon-watchdog.sh` + launchd plist) — 60-second cron detects brain-dead daemon by checking last event timestamp + IOKit idle time
- [x] launchd auto-start with KeepAlive=true, RunAtLoad=true, ThrottleInterval=30
- [x] Smart health alerts — checks IOKit idle time before alerting (no false positives during lunch/meetings)
- [x] Log rotation — RotatingFileHandler with 1MB max, 5 backups (6MB total cap)
- [x] Cloud sync fixed — Supabase + Vercel at captainslog.hyperverge.space (replaced dead Railway)
- [x] Sync deduplication — `synced_at` column, only syncs unsynced rows
- [x] AI model updated from deprecated `claude-3-5-haiku-20241022` to `claude-haiku-4-5-20251001`
- [x] Async bug fix — properly closes unawaited coroutine in OptimizationEngine.on_activity

### Phase 1: The Daily Pull -- DONE (Apr 5-6, 2026)
**Goal: A notification at 6pm that makes you glance at your day. This is the #1 priority.**

- [x] macOS notification at configurable time (default 6pm)
- [x] Content: hours active, top 3 apps, AI-generated 1-sentence narrative
- [x] `captains-log digest` — generate/view the daily digest on demand
- [x] `captains-log today` — duration breakdown by app and category, focus hours, most focused hour
- [x] `captains-log week` — this week vs last week with duration data, daily breakdown, projections
- [x] Duration calculator (`summarizers/duration_calculator.py`) — accurate time-in-app from event gaps
- [ ] Clicking notification opens dashboard to today's timeline
- [ ] Morning briefing notification (optional, default 9am) — verify it works
- [ ] Evening digest notification verification — confirm notifications fire reliably every day

### Phase 2: Understanding Where Time Goes -- DONE (Apr 5-6, 2026)
**Goal: Make time-spent analysis effortless and honest.**

- [x] `captains-log recall "last Thursday"` — natural language history query via Claude
- [x] `captains-log week` — this week vs last week comparison with duration data
- [x] Pattern detector (`insights/pattern_detector.py`) — detects peak productive hours, context switch spikes, weekly rhythm patterns from 14+ days of history
- [x] `captains-log insights` — shows detected patterns
- [x] `captains-log weekly` — shows weekly digest with trends
- [x] Surface optimization engine insights in daily/weekly digest (context switches, interrupt patterns, deep vs shallow work)
- [ ] Improve dashboard with "time spent" as the primary view
  - App usage donut chart front and center
  - Weekly focus hours bar chart (Mon-Sun)
  - Deep work hours trend line
  - "Where did today go?" narrative

### Phase 3: Menu Bar & Notifications (NEXT)
**Goal: Ambient awareness without opening a terminal.**

- [ ] Menu bar showing live focus hours ("4.2h focused")
- [ ] Evening digest notification verification — confirm it fires every day
- [ ] Morning briefing opt-in with yesterday's summary
- [ ] Friday 5 PM weekly summary notification

### Phase 4: Dashboard (NEXT)
**Goal: Visual home for your productivity data.**

- [ ] Dashboard landing page with time breakdown charts
- [ ] Today's activity donut chart by category
- [ ] Weekly focus hours bar chart (Mon-Sun)
- [ ] Streak visualization
- [ ] "Where did today go?" AI narrative

### Phase 5: Proactive AI
**Goal: AI surfaces insights at the right moment, not when you ask.**

| Trigger | Action | Status |
|---------|--------|--------|
| 6:00 PM | Evening digest notification | DONE |
| 9:00 AM | Morning briefing notification | Built, needs verification |
| Friday 5 PM | Weekly summary notification | TODO |
| Off-goal >10min during focus | Gentle nudge (amber border on widget) | Built |
| Unusual pattern detected | "You spent 2x more time in Slack than usual today" | Pattern detector built, nudge TODO |

### Phase 6: Advanced Insights
**Goal: Deeper analysis and actionable recommendations.**

- [ ] Meeting fragmentation score (Swiss Cheese Score — built in optimization engine)
- [ ] "Time saved" counter — concrete ROI users can share
- [ ] Weekly email digest option
- [ ] Shareable weekly card image
- [ ] Export: "What I accomplished this week" for standups/updates

### Phase 7: Calendar Integration
**Goal: Smart scheduling around meetings.**

- [ ] macOS EventKit integration (read calendar events)
- [ ] "Next meeting in Xh" in menu bar
- [ ] "You have 2h free — start focus?" smart suggestion
- [ ] Meeting fragmentation warnings
- [ ] Google Calendar as optional second source

### Phase 8: Emotional Design & Social
**Goal: Make progress feel rewarding, sharing drives accountability.**

- [ ] Session completion sound + subtle animation
- [ ] Milestone notifications (10h, 50h, 100h deep work)
- [ ] Weekly achievement summary
- [ ] Goal streak visualization in menu bar
- [ ] Shareable weekly card image

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
| Third frontend framework | Two is already enough (FastAPI local + Next.js cloud) |

---

## Technical Decisions

### Keep
- **Python + PyObjC** for daemon (macOS native APIs)
- **SQLite + WAL** for storage (fast, local, reliable)
- **Claude AI** for summarization (quality justifies cost)
- **Swift** for menu bar + widget (native macOS feel)
- **FastAPI + Jinja2** for dashboard (server-rendered, fast)

### Simplified (Apr 2026)
- **Cloud sync fixed** — moved from dead Railway to Supabase + Vercel deployment
- **Next.js frontend** — deployed at captainslog.hyperverge.space with Google OAuth (Supabase auth)
- **Optimization insights surfaced** — via `today`, `week`, `insights`, `weekly` CLI commands and daily digest

### Added (Apr 2026)
- **macOS notifications** for daily digest via osascript
- **Notification scheduler** in orchestrator for timed digests
- **Natural language query** via Claude for `recall` command
- **Daemon watchdog** with launchd for reliability
- **Duration calculator** for accurate time-in-app analysis
- **Pattern detector** for historical productivity insights

---

## Success Metrics

| Metric | Target | How to Measure | Status |
|--------|--------|---------------|--------|
| Daemon uptime | >99% (crashes auto-recover) | launchd KeepAlive + watchdog | **INFRA DONE** |
| Daily digest viewed | 5+ days/week | Notification interaction tracking | Built, verifying |
| `today`/`recall` usage | 3+ times/week | CLI command logging | Built |
| Consecutive days tracked | 30+ days | Activity log continuity | Tracking since Apr 1 |
| Focus sessions/week | 5+ | focus_sessions table | Available |

The most important metric: **Is the daemon running, and do you look at the digest?** The daemon reliability is now solved. Next: verify digest notifications fire daily.

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

## Current Version: 0.2.03

See `CLAUDE.md` for implementation details and session history.
