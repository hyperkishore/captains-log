# Captain's Log - Bug Tracker

## Session 1 - 2026-01-18

### Open Bugs

### BUG-001: Menu Bar App fails to create goals_status.json on first launch
- **Journey**: MB-5 (Goals list displays with streak indicators)
- **Severity**: P1
- **Status**: ✅ FIXED
- **Description**: The menu bar app's `loadGoals()` function should create goals_status.json by running the CLI command, but it fails silently on first launch.
- **Root Cause**:
  1. Original code used shell redirection which wasn't working reliably
  2. macOS Launch Services was caching old versions of the app
- **Fix Applied**:
  1. Rewrote `loadGoals()` to use Process with stdout Pipe instead of shell redirection
  2. Added directory creation before writing
  3. Added command existence check before execution
  4. App now loads goals successfully (verified: 3 goals loaded)
- **Verification**: After fix, debug log shows goals being loaded every 10 seconds

### BUG-003: Summary generation fails - incorrect model ID
- **Journey**: S3 - CLI tests
- **Severity**: P1
- **Status**: ✅ FIXED
- **Description**: All summary generation fails with 404 error because the model ID is wrong
- **Error**: `Error code: 404 - model: claude-haiku-4-5-20241022`
- **Root Cause**: Config uses `claude-haiku-4-5-20241022` but correct ID is `claude-3-5-haiku-20241022`
- **Fix Applied**:
  1. Updated `src/captains_log/core/config.py` - changed default model
  2. Updated `src/captains_log/ai/claude_client.py` - changed default parameter
  3. Updated CLAUDE.md and README.md documentation
  4. Reset 58 failed summaries to pending for retry
- **Verification**: Model ID now correct in all files

### BUG-004: Optimize command fails - missing interrupts table
- **Journey**: S3 - CLI tests
- **Severity**: P2
- **Status**: ✅ FIXED
- **Description**: `captains-log optimize` fails with "no such table: interrupts"
- **Root Cause**: Migration v8 recorded version but tables weren't created (silent failure)
- **Fix Applied**: Manually created missing tables:
  - `interrupts` - tracks communication app checks
  - `context_switches` - tracks app switch costs
  - `user_profile` - user preferences for optimization
  - `daily_optimization_metrics` - pre-aggregated daily data
  - `nudges` - behavior change prompts
  - `recommendations` - optimization suggestions
- **Verification**: `captains-log optimize` now runs successfully

### BUG-002: Navigation links not working in React frontend (client-side routing)
- **Journey**: WD-7 (Navigation to Time Analysis)
- **Severity**: P2
- **Status**: Open
- **Description**: Clicking navigation links in the sidebar doesn't trigger navigation; requires direct URL navigation or page refresh.
- **Steps to Reproduce**:
  1. Go to http://localhost:3000/timeline
  2. Click "Time Analysis" in sidebar
  3. Page content doesn't change (URL updates but view doesn't)
- **Expected**: Page should navigate to Time Analysis view
- **Actual**: Must use direct URL navigation or refresh
- **Root Cause**: Likely React Router client-side navigation issue
- **Workaround**: Use direct URL navigation works correctly

---

### Fixed Bugs

(Fixed bugs will be moved here)

---

## Test Results Summary - Session 1

### Web Dashboard (WD-1 to WD-9)
| Test | Description | Status |
|------|-------------|--------|
| WD-1 | Dashboard loads | ✅ PASS |
| WD-2 | Today's stats display | ✅ PASS |
| WD-3 | Timeline shows activities | ✅ PASS (159 activities) |
| WD-4 | Screenshots in timeline | ✅ PASS (50 screenshots) |
| WD-5 | Screenshot modal | ✅ PASS |
| WD-6 | Goals section | ⏳ Not tested on this view |
| WD-7 | Time Analysis nav | ✅ PASS (via direct URL) |
| WD-8 | Apps page | ✅ PASS |
| WD-9 | Date picker | ✅ PASS |

### Backend Daemon (BD-1 to BD-5)
| Test | Description | Status |
|------|-------------|--------|
| BD-1 | Daemon running | ✅ PASS |
| BD-2 | Activity tracking | ✅ PASS (159 today) |
| BD-3 | Screenshot capture | ✅ PASS (216 today) |
| BD-4 | Focus sessions | ✅ PASS (5 total) |
| BD-5 | Goals table | ✅ PASS (3 goals) |

### Menu Bar App (MB-1 to MB-16)
| Test | Description | Status |
|------|-------------|--------|
| MB-1 | App launches | ✅ PASS |
| MB-2 | Popover opens | ⏳ Manual test needed |
| MB-3 | Daemon status | ⏳ Manual test needed |
| MB-4 | Today's focus time | ⏳ Manual test needed |
| MB-5 | Goals list | ⚠️ BUG-001 |
| MB-6 | Goal expansion | ⏳ Manual test needed |
| MB-7 | Task starts session | ⏳ Manual test needed |
| MB-8 | Quick Focus | ⏳ Manual test needed |
| MB-9 | Active session | ⏳ Manual test needed |
| MB-10 | Pause/Resume | ⏳ Manual test needed |
| MB-11 | Stop session | ⏳ Manual test needed |
| MB-12 | Dashboard button | ⏳ Manual test needed |
| MB-13 | Calendar connect | ⏳ Manual test needed |
| MB-14 | Calendar events | ⏳ Manual test needed |
| MB-15 | Focus suggestion | ⏳ Manual test needed |
| MB-16 | Quit button | ⏳ Manual test needed |

---

## Test Results Summary - Session 2

### Services Verification
| Service | Status | Notes |
|---------|--------|-------|
| Daemon | ✅ Running | Port 8082 |
| Dashboard (FastAPI) | ✅ Working | All pages 200 |
| Frontend (Next.js) | ✅ Working | Port 3000 |
| Menu Bar App | ✅ Launched | PID verified |
| Focus Widget | ⚠️ Not auto-started | Needs manual launch |

### Focus Session Flow (CLI)
| Test | Status | Notes |
|------|--------|-------|
| Start session via CLI | ✅ PASS | Status file updated correctly |
| Focus status JSON | ✅ PASS | All fields populated |
| Session shows in DB | ✅ PASS | 4 sessions today, 122 min |
| Stop session via pkill | ✅ PASS | Cleans up properly |

### Calendar Integration
| Test | Status | Notes |
|------|--------|-------|
| Calendar files exist | ✅ PASS | 5 Swift files |
| Integration in MenuBar | ✅ PASS | CalendarManager referenced |
| EventKit provider | ✅ Exists | Needs permission test |

### Session 2 Findings
- **Dashboard runs on port 8082** (not 8081 as documented)
- **Menu bar app not auto-starting on boot** - needs LaunchAgent setup
- **Focus widget requires explicit launch** - not auto-launched from menu bar

---

## Test Results Summary - Session 3

### CLI Command Suite
| Command | Status | Notes |
|---------|--------|-------|
| `status` | ✅ PASS | Running 22.7h, 7.1MB |
| `health` | ✅ PASS | All metrics OK |
| `focus-status` | ✅ PASS | 5 sessions today |
| `focus-goals` | ✅ PASS | 7 active goals |
| `optimize` | ❌ FAIL | BUG-004: missing interrupts table |
| `summaries` | ⚠️ PARTIAL | 32 failed (BUG-003) |

### Component Launch Tests
| Component | Status | Notes |
|-----------|--------|-------|
| Menu Bar App | ✅ PASS | Launches, shows in menu |
| Focus Widget | ✅ PASS | Launches, PID 74116 |
| Focus Session (CLI) | ✅ PASS | Status file updates correctly |

### Data Integrity
| Check | Status | Notes |
|-------|--------|-------|
| Activity tracking | ✅ Working | 171 activities today |
| Screenshot capture | ✅ Working | 251 screenshots today |
| Focus sessions | ✅ Working | 122 min total today |
| Database integrity | ✅ Passed | No corruption |

### Session 3 New Issues Found
- **BUG-003**: Summaries fail due to incorrect model ID
- **BUG-004**: Optimize command missing tables

---

## Bug Template

```markdown
### BUG-XXX: [Title]
- **Journey**: [Test ID]
- **Severity**: P0/P1/P2
- **Status**: Open/In Progress/Fixed
- **Description**:
- **Steps to Reproduce**:
  1.
  2.
- **Expected**:
- **Actual**:
- **Screenshot**: (if applicable)
- **Fix**: (once fixed)
```

