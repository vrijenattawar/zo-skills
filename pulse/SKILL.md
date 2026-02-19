---
name: pulse
description: |
  Automated build orchestration system. Spawns headless Zo workers (Drops) in parallel Waves,
  monitors health, validates Deposits via LLM judgment, handles dead Drops, and escalates via SMS.
  Supports sequential Streams within Waves. Replaces manual Build Orchestrator for unattended execution.
---

# Pulse: Automated Build Orchestration

## Overview

Pulse orchestrates complex builds by:
1. **Spawning Drops** (workers) via `/zo/ask` API (or generating launchers for manual Drops)
2. **Monitoring** for deposits, timeouts, failures
3. **Filtering** deposits via LLM judgment
4. **Checkpoint verification** at strategic quality gates
5. **Escalating** via email/SMS when issues arise
6. **Finalizing** with safety checks, integration tests, and learning harvest

## Terminology (Flow Metaphor)

| Term | Meaning |
|------|---------|
| **Build** | The complete orchestrated work |
| **Wave** | Parallel execution round — a hard barrier; Wave N+1 cannot start until all blocking Drops in Wave N are complete |
| **Stream** | Sequential workflow within a Wave — Drops in a Stream run in order (D1.1 → D1.2 → D1.3) |
| **Drop** | Individual worker/task — one conversation's worth of context |
| **Checkpoint** | Strategic quality gate verifying cross-Drop consistency |
| **Deposit** | Worker's completion report (JSON in `deposits/`) |
| **Filter** | LLM judgment of deposit quality |
| **Dredge** | Forensics worker for dead Drops |
| **Launcher** | Generated markdown file for manual Drops with paste-ready prompt |
| **Jettison** | Connected-but-independent build spawned as tangent off-ramp |
| **Lineage** | Parent-child relationship graph between builds |

### Execution Model

```
Wave 1 (barrier)
├── Stream 1: D1.1 → D1.2 → D1.3  (sequential)
├── Stream 2: D2.1 → D2.2         (sequential, parallel to Stream 1)
└── Stream 3: D3.1                (parallel to Streams 1 & 2)

    ↓ (all blocking Drops in Wave 1 must complete)

Wave 2 (barrier)
├── Stream 1: D1.4 → D1.5
└── Stream 2: D2.3
```

- **Waves are hard barriers**: No Drop from Wave 2 spawns until all blocking Drops in Wave 1 are complete.
- **Streams are sequential**: Within a stream, D1.2 waits for D1.1 to complete.
- **Streams run in parallel**: D1.1 and D2.1 can run simultaneously (same Wave, different Streams).

## Quick Start

```bash
# Contract gate (required before start)
python3 N5/scripts/build_contract_check.py <slug>

# Validate plan before starting (recommended)
python3 Skills/pulse/scripts/pulse.py validate <slug>

# Check build status
python3 Skills/pulse/scripts/pulse.py status <slug>

# Start automated orchestration
python3 Skills/pulse/scripts/pulse.py start <slug>

# Manual tick (for testing)
python3 Skills/pulse/scripts/pulse.py tick <slug>

# Stop gracefully
python3 Skills/pulse/scripts/pulse.py stop <slug>

# Resume stopped build
python3 Skills/pulse/scripts/pulse.py resume <slug>

# Post-build finalization
python3 Skills/pulse/scripts/pulse.py finalize <slug>

# Launch a manual Drop (prints launcher content)
python3 Skills/pulse/scripts/pulse.py launch <slug> <drop_id>

# Retry a failed Drop (reset + update brief)
python3 Skills/pulse/scripts/pulse.py retry <slug> <drop_id> --reason "Why it failed"

# Create jettison (off-ramp build)
pulse jettison "<task>" [--from <parent>] [--type <type>]

# View build lineage DAG
pulse lineage [<slug>] [--format tree|json]
```

## Required Contract Gate

Before starting any Pulse build, both checks must pass:

```bash
python3 N5/scripts/build_contract_check.py <slug>
python3 Skills/pulse/scripts/pulse.py validate <slug>
```

If either command fails, do not run `start` yet. Fix missing artifacts first (`PLAN.md`, `meta.json`, and drop briefs in `drops/`).

## Plan Validation

**Principle (from Theo):** Plans are context vehicles, not spec documents. An incomplete plan means the model will guess, and guessing compounds errors across Drops.

Before starting any build, validate the plan is complete:

```bash
python3 Skills/pulse/scripts/pulse.py validate <slug>
```

The validator checks for:
- **Unfilled placeholders** (`{{PLACEHOLDER}}`, `TODO:`, etc.)
- **Missing required sections** (Objective, Open Questions, Phase 1, Success Criteria)
- **Empty sections** (headers without content)
- **Warnings** (unchecked open questions, stale plans >14 days)

A build should NOT start until validation passes. The `start` command does NOT enforce this automatically — you must run `validate` first.

## Retry Failed Drops

**Principle (from Theo):** If output is bad, don't keep appending corrections. Revert and restart with corrected input.

When a Drop fails or produces bad output:

```bash
# Reset Drop and optionally explain why
python3 Skills/pulse/scripts/pulse.py retry <slug> <drop_id> --reason "Missed the auth requirements"
```

The retry command:
1. Archives the old deposit (preserves history)
2. Resets Drop status to `pending`
3. Appends retry context to the brief (if `--reason` provided)
4. Increments retry counter

This gives the model a clean slate with better context rather than compounding errors by appending fix requests to a polluted history.

## Manual Drops & Launchers

Some Drops need human oversight — close prompting control, high-risk changes, or work requiring V's judgment.

### spawn_mode Options

| Mode | Behavior | Use When |
|------|----------|----------|
| `auto` (default) | Pulse spawns via `/zo/ask` headless | Standard automated execution |
| `manual` | Pulse generates launcher, waits for V to execute | High-risk, requires judgment, voice-sensitive |

### Automatic Recommendation

If a Drop's `spawn_mode` is not explicitly set, Pulse analyzes the brief and recommends:
- **Manual** if brief contains: "preferences", "voice protocol", "HITL", "requires V review", "<YOUR_PRODUCT> voice", "ask V", "judgment", "sensitive"
- **Auto** otherwise

The recommendation is stored as `spawn_recommendation` and applied if no explicit mode is set.

### Manual Drop Workflow

1. **Tick detects ready Drop with `spawn_mode: manual`**
2. **Launcher generated** at `N5/builds/<slug>/launchers/<drop_id>.md`
3. **Status set to `awaiting_manual`**
4. **STATUS.md updated** with:
   ```
   ## Awaiting Manual (1)
   - [ ] D1.2 → run: `python3 Skills/pulse/scripts/pulse.py launch <slug> D1.2`
   ```
5. **V runs the launch command** (or opens launcher file directly)
6. **V pastes prompt into new thread**, executes, writes deposit
7. **Next tick detects deposit**, runs Filter, advances

### Launcher File Format

```markdown
# Launcher: my-build / D1.2

## Paste into a new thread

```text
Load and execute: file 'N5/builds/my-build/drops/D1.2-voice-sensitive-task.md'

When complete, write deposit to:
file 'N5/builds/my-build/deposits/D1.2.json'
```

## After you finish

- Confirm the deposit exists at the path above.
- Then run:
  - `python3 Skills/pulse/scripts/pulse.py tick my-build`
  - (or wait for the Sentinel to tick)
```

## blocking Field (Non-Blocking Drops)

By default, all Drops are **blocking** — the next Wave cannot start until they complete.

Set `blocking: false` on a Drop to make it **non-blocking**:
- The Drop still runs and is tracked
- But it does NOT hold up Wave advancement
- Useful for: logging, notifications, optional enrichment, async cleanup

```json
{
  "drops": {
    "D1.1": { "name": "Core work", "wave": "W1", "blocking": true },
    "D1.2": { "name": "Send notification", "wave": "W1", "blocking": false }
  }
}
```

Wave 2 can start once D1.1 completes, even if D1.2 is still running.

**STATUS.md** explicitly surfaces non-blocking Drops so nothing is silently left behind.

## meta.json Structure (v3)

```json
{
  "schema_version": 3,
  "slug": "my-build",
  "title": "Build Title",
  "build_type": "code_build",
  "status": "pending",
  "model": "anthropic:claude-sonnet-4-20250514",
  "launch_mode": "orchestrated|manual|jettison",
  "delegate_only": false,
  "first_wins": false,
  "hypothesis_group": [],
  "broadcasts": [],
  "task_pool": {
    "enabled": false,
    "tasks": [],
    "max_concurrent_claims": 4,
    "worker_drops": []
  },
  
  "waves": {
    "W1": ["D1.1", "D1.2", "D2.1"],
    "W2": ["D1.3", "D2.2"]
  },
  "active_wave": "W1",
  
  "drops": {
    "D1.1": {
      "name": "Task name",
      "stream": 1,
      "order": 1,
      "depends_on": [],
      "spawn_mode": "auto",
      "blocking": true,
      "status": "pending"
    },
    "D1.2": {
      "name": "Voice-sensitive task",
      "stream": 1,
      "order": 2,
      "spawn_mode": "manual",
      "blocking": true,
      "status": "pending"
    }
  },
  
  "lineage": {
    "parent_type": "build|jettison|conversation|null",
    "parent_ref": "slug or convo_id",
    "parent_conversation": "convo_id",
    "moment": "description",
    "branched_at": "ISO timestamp"
  }
}
```

### Legacy Compatibility

Builds with `currents` or `current_stream`/`total_streams` (schema v1/v2) still work:
- Pulse normalizes them in-memory
- No migration required for old builds
- New builds should use `waves` schema

## Build Folder Structure

```
N5/builds/<slug>/
├── meta.json           # Build state (status, drops, waves)
├── STATUS.md           # Human-readable progress dashboard
├── BUILD_LESSONS.json  # Build-specific learnings
├── INTEGRATION_TESTS.json  # Test definitions
├── INTEGRATION_RESULTS.json  # Test results
├── FINALIZATION.json   # Post-build report
├── drops/              # Drop briefs
│   ├── D1.1-task-a.md
│   ├── D1.2-voice-task.md
│   └── D2.1-combine.md
├── deposits/           # Completion reports
│   ├── D1.1.json
│   ├── D1.1_filter.json
│   └── D1.1_forensics.json  (if dead)
├── launchers/          # Manual drop launchers (auto-generated)
│   └── D1.2.md
└── artifacts/          # Build outputs
```

## Jettison Launch Mode

Jettisons are **off-ramp builds** — when you hit a tangent worth pursuing without derailing your current thread.

### When to Use

- Debugging issue surfaces mid-build that needs isolated investigation
- Interesting idea emerges that deserves its own exploration
- Current task has a prerequisite that should be handled separately
- You want to branch off without losing the parent context

### Command Syntax

```bash
# Basic jettison
pulse jettison "fix the rate limiting issue"

# Explicit parent build
pulse jettison "debug the API" --from adhd-todo-research

# Explicit type (overrides auto-detection)
pulse jettison "explore gamification approaches" --type research

# Custom moment description
pulse jettison "handle auth edge case" --moment "Discovered during D1.2 execution"
```

### Type Auto-Detection

| Keywords | Detected Type |
|----------|---------------|
| fix, bug, debug, error, refactor | `code_build` |
| research, explore, investigate, analyze | `research` |
| draft, write, content, blog, email | `content` |
| plan, design, architect, strategy | `planning` |
| (default) | `code_build` |

## Sentinel Setup

Pulse requires a **Sentinel** scheduled agent to monitor builds and report via email (preferred) or SMS.

### Sentinel Dry-Run & Diagnostics

```bash
# Test sentinel without mutating builds
python3 Skills/pulse/scripts/sentinel.py --dry-run

# Check if ZO_CLIENT_IDENTITY_TOKEN is available
python3 Skills/pulse/scripts/sentinel.py --check-token
```

### Email Sentinel (Recommended)

Email provides richer updates and allows detailed replies.

**Create Email Sentinel at build start:**
```
RRULE: FREQ=MINUTELY;INTERVAL=5;COUNT=100
Delivery: email

Instruction:
Pulse Sentinel for build: <slug>

1. Run: python3 Skills/pulse/scripts/pulse.py status <slug> --json
2. Parse the status and compose an email update.

EMAIL FORMAT:
Subject: [PULSE] <slug> - <status_summary>

Body:
## Build: <slug>
**Status:** Wave <X> | **Progress:** <completed>/<total> Drops (<pct>%)

### Wave Status
| Wave | Status | Drops |
|------|--------|-------|
| W1 | complete | D1.1 ✓, D1.2 ✓ |
| W2 | running | D2.1 ✓, D2.2 ⏳ (8 min) |
| W3 | pending | - |

### Awaiting Manual
- D2.3 → `python3 Skills/pulse/scripts/pulse.py launch <slug> D2.3`

### Reply Commands
Reply with: `status`, `retry D2.2`, `skip D2.2`, `pause`, `resume`, `stop`

3. ONLY send email if: new completions, drop >15 min, build complete, wave advanced, FAIL verdict, or manual drop waiting.

4. If build complete: Send final summary, then delete yourself.
```

### SMS Sentinel (Fallback)

```
RRULE: FREQ=MINUTELY;INTERVAL=3;COUNT=120
Delivery: sms

Instruction:
Pulse SMS Sentinel for build: <slug>

1. Run: python3 Skills/pulse/scripts/pulse.py status <slug>
2. ONLY text if:
   - Drop FAILED → "[PULSE] ❌ D#.# FAILED: <reason>"
   - Drop dead (>15 min) → "[PULSE] ⚠️ D#.# may be dead"
   - Manual drop waiting → "[PULSE] 🖐️ D#.# awaiting manual launch"
   - Build complete → "[PULSE] ✅ <slug> COMPLETE"
3. Stay silent for routine progress.
```

## SMS Commands

Text these to control Pulse:
- `pulse stop` — Stop all builds, delete Sentinel
- `pulse done` — Mark builds complete, delete Sentinel
- `pulse pause` — Pause ticking (agent stays alive)
- `pulse resume` — Resume ticking
- `n5 task <description>` — Add task to queue (v2)

## Smart Sentinel (Recovery)

The Sentinel includes a **recovery engine** that automatically handles failed/dead Drops using deterministic rules, with AI judgment as a fallback.

### Recovery Rules

| Rule | Condition | Action |
|------|-----------|--------|
| R1 | Drop dead (timeout) + retry_count < max | Auto-retry with timeout context |
| R2 | Drop failed (spawn error) + retry_count < max | Auto-retry (transient failure) |
| R3 | Drop failed (content/logic error) | Needs AI judgment → escalate |
| R4 | All blocking Drops in current Wave dead/failed + retries exhausted | Build set to BLOCKED, escalate |
| R5 | Build active >threshold with no progress | Stale build escalation |

### How It Works

After each `tick()` cycle, the Sentinel calls `assess_and_recover()` which:

1. Scans all dead/failed Drops
2. Classifies each failure (dead_timeout, spawn_error, content_error, unknown)
3. Applies rules R1-R5 in priority order
4. Auto-retries eligible Drops via the existing `retry_drop()` function
5. Logs every action to `RECOVERY_LOG.jsonl` (P39 audit trail)
6. Updates STATUS.md with recovery indicators

### Configuration

Per-build overrides in `meta.json`:

```json
{
  "recovery": {
    "max_auto_retries": 2,
    "dead_threshold_seconds": 900,
    "stale_threshold_hours": 4,
    "stale_no_progress_minutes": 60,
    "enable_ai_judgment": true
  }
}
```

All fields are optional — defaults from `RECOVERY_DEFAULTS` in `pulse_common.py` are used for any missing field. Set `max_auto_retries: 0` to disable auto-recovery for a specific build.

### RECOVERY_LOG.jsonl Format

Append-only log at `N5/builds/<slug>/RECOVERY_LOG.jsonl`:

```json
{"timestamp": "ISO", "drop_id": "D1.1", "rule": "R1", "action": "auto_retry", "failure_type": "dead_timeout", "reason": "Dead (timeout), auto-retry 1/2", "retry_number": 1}
{"timestamp": "ISO", "drop_id": "D2.1", "rule": "R3", "action": "needs_judgment", "failure_type": "content_error", "reason": "Schema mismatch in output"}
{"timestamp": "ISO", "drop_id": "*", "rule": "R4", "action": "escalate", "failure_type": "wave_death", "reason": "All blocking drops in W2 dead/failed"}
```

### Commands

```bash
# Dry-run: see what recovery would do without mutations
python3 Skills/pulse/scripts/sentinel.py --dry-run

# Check token availability
python3 Skills/pulse/scripts/sentinel.py --check-token
```

### Enhanced Sentinel Agent Prompt Template

```
Pulse Smart Sentinel for build: <slug>

1. Run: python3 Skills/pulse/scripts/sentinel.py
2. The script handles tick + auto-recovery for all active builds.
3. Read its output to understand what happened.

POST-SCRIPT JUDGMENT (only if output reports items needing AI judgment):

If the script reports Drops needing AI assessment:
- Read the Drop's brief and any archived deposits
- Assess: Is this a transient failure (retry) or a fundamental issue (escalate)?
- If retry: run `python3 Skills/pulse/scripts/pulse.py retry <slug> <drop_id> --reason "<assessment>"`
- If escalate: include in your email with specific guidance for V

REPORT:
- Only email if: recovery actions taken, drops needing attention, build complete, or wave advanced
- Stay silent for routine ticks with no changes

GUARDRAILS:
- Max 2 auto-retries per Drop (script enforces this)
- Never retry a Drop retried 2x — escalate instead
- If build is BLOCKED, always escalate to V
```

## Learnings System

Two tiers:
1. **Build-local** → `N5/builds/<slug>/BUILD_LESSONS.json`
2. **System-wide** → `N5/learnings/SYSTEM_LEARNINGS.json`

```bash
# Add build learning
python3 Skills/pulse/scripts/pulse_learnings.py add <slug> "lesson text"

# Add system learning
python3 Skills/pulse/scripts/pulse_learnings.py add <slug> "lesson text" --system

# List learnings
python3 Skills/pulse/scripts/pulse_learnings.py list <slug>
python3 Skills/pulse/scripts/pulse_learnings.py list-system

# Promote build learning to system
python3 Skills/pulse/scripts/pulse_learnings.py promote <slug> <index>

# Inject system learnings into briefs
python3 Skills/pulse/scripts/pulse_learnings.py inject <slug>

# Harvest learnings from deposits
python3 Skills/pulse/scripts/pulse_learnings.py harvest <slug>
```

## Forward Broadcast

Drops can share findings with subsequent Drops via the `broadcast` field in deposits.

### How It Works

1. Drop includes `broadcast` string in deposit JSON
2. Pulse collects all broadcasts from completed Drops
3. New Drops receive a "## Broadcasts from Prior Drops" section in their brief

### Deposit Schema

```json
{
  "drop_id": "D1.1",
  "status": "complete",
  "broadcast": "Auth tokens expire after 30 min—don't cache beyond that",
  ...
}
```

### Injected Format

```markdown
## Broadcasts from Prior Drops

These findings were shared by earlier Drops in this build:

- **D1.1:** Auth tokens expire after 30 min—don't cache beyond that
```

### Best Practices

- Keep broadcasts short (~500 chars max)
- Broadcast discoveries that affect other Drops
- Don't broadcast obvious things already in briefs

## Hypothesis Racing

For debugging or exploration builds where you want to test multiple theories in parallel.

### Enabling

In `meta.json`:

```json
{
  "first_wins": true,
  "hypothesis_group": ["D1.1", "D1.2", "D1.3"]  // optional
}
```

### Verdict Field

Racing Drops include `verdict` in their deposit:

```json
{
  "drop_id": "D1.2",
  "status": "complete",
  "verdict": "confirmed",
  "summary": "Theory confirmed: rate limit is client-side"
}
```

Valid verdicts: `confirmed`, `rejected`, `inconclusive`

### Behavior

- When a Drop deposits `verdict: "confirmed"`, other Drops in the race are marked `superseded`
- Superseded Drops are not spawned (if pending) or ignored (if running)
- Wave can advance once winner confirms — superseded Drops don't block

### Use Cases

- Debugging with multiple theories
- A/B testing approaches
- Finding the first working solution among alternatives

## Delegate-Only Mode

Prevents the orchestrator from directly editing code, keeping all work in Drops.

### Enabling

In `meta.json`:

```json
{
  "delegate_only": true
}
```

### Constraints

When enabled, the orchestrator:
- **MAY**: Run pulse.py commands, read files, create/modify briefs, retry Drops
- **MUST NOT**: Edit source files, run application code, "fix" issues directly

### Why Use It

- Clear provenance (every change has a Drop source)
- Prevents long-build confusion
- Better audit trail

See `file 'Skills/pulse/references/delegate-only-mode.md'` for full details.

## Task Pool (Dynamic Claiming)

For builds with many similar tasks, Drops can claim work from a shared pool.

### Enabling

In `meta.json`:

```json
{
  "task_pool": {
    "enabled": true,
    "tasks": [
      {"id": "T001", "type": "enrich", "target": "file1.json", "status": "pending"},
      {"id": "T002", "type": "enrich", "target": "file2.json", "status": "pending"}
    ],
    "max_concurrent_claims": 4,
    "worker_drops": ["D1.1", "D1.2", "D1.3", "D1.4"]
  }
}
```

### Task States

- `pending` — Available for claiming
- `claimed` — Assigned to a Drop
- `complete` — Finished successfully
- `failed` — Failed, may be re-claimable

### Claiming

Pool workers claim tasks atomically (file-locked to prevent races):

```python
task = claim_task(slug, drop_id)
if task is None:
    # Pool exhausted, exit
```

### Use Cases

- Processing batches of similar items
- Parallelizing uniform work without pre-planning assignments
- Variable-duration tasks where fast Drops should grab more work

## Integration Tests

```bash
# Generate tests from artifacts
python3 Skills/pulse/scripts/pulse_integration_test.py generate <slug>

# Run tests
python3 Skills/pulse/scripts/pulse_integration_test.py run <slug>

# Add custom test
python3 Skills/pulse/scripts/pulse_integration_test.py add <slug> \
  --type file_exists \
  --name "Check output" \
  --config '{"path": "Sites/mysite/dist/index.html"}'
```

Test types: `file_exists`, `file_contains`, `command`, `http`, `service_running`

## Safety Layer

```bash
# Pre-build checks
python3 Skills/pulse/scripts/pulse_safety.py pre-check <slug>

# Verify artifacts after build
python3 Skills/pulse/scripts/pulse_safety.py verify <slug>

# Create git snapshot
python3 Skills/pulse/scripts/pulse_safety.py snapshot <slug>

# Restore from snapshot
python3 Skills/pulse/scripts/pulse_safety.py restore <slug>
```

## Scripts

| Script | Purpose |
|--------|---------|
| `pulse.py` | Main orchestrator (start, tick, stop, finalize, launch) |
| `sentinel.py` | Lightweight monitor for scheduled polling (supports --dry-run) |
| `pulse_common.py` | Shared paths, config, parsing utilities |
| `pulse_safety.py` | Pre-build checks, artifact verification, snapshots |
| `pulse_learnings.py` | Capture/propagate learnings (build + system) |
| `pulse_integration_test.py` | Post-build integration tests |

## Related Files

- `file 'Skills/pulse-interview/SKILL.md'` — Pre-build interview skill
- `file 'N5/learnings/SYSTEM_LEARNINGS.json'` — System-wide learnings
- `file 'N5/config/pulse_control.json'` — Sentinel control state
- `file 'Documents/System/Build-Orchestrator-System.md'` — Legacy manual system
- `file 'N5/pulse/'` — v2 scripts directory

## Learning-Engaged Build Mode

When `build_mode: "learning"` in meta.json (the default):

### Orchestrator Responsibilities

1. **Generate Learning Landscape** — During planning, read `N5/config/understanding_bank.json` and analyze plan concepts against V's levels. Flag Decision Points and tag Drops.

2. **Present Decision Points** — Before launching Drops that involve flagged decisions:
   - Present the question in plain language
   - Offer 2-3 options with tradeoffs explained at V's level
   - Include a recommendation with reasoning
   - Support multi-round Socratic dialogue if V wants to explore
   - Log resolved decisions to `DECISIONS.md` in the build folder

3. **Spawn Learning Drops** — When V says "I want to deep dive into X":
   - Create an L-prefix Drop brief using `references/learning-drop-template.md`
   - The Learning Drop is always manual spawn
   - It never blocks the build — other Drops continue
   - When V completes the Learning Drop, integrate conclusions into subsequent briefs

4. **Generate Wave Reviews** — At wave boundaries:
   - Summarize what was accomplished
   - List concepts V was exposed to
   - Ask ONE Socratic question testing the most important concept
   - V can opt to deep dive (spawns Learning Drop) or continue

5. **Default Manual Spawn** — Pedagogical Drops use `spawn_mode: manual`. V opens them in new threads. Mechanical Drops (tagged in Learning Landscape) can be auto-spawned with V's approval.

### Rush Mode Override

V can override learning mode at any scope:
- **Per-Drop:** "Run D1.2 headless"
- **Per-Wave:** "Auto-spawn wave 2"
- **Per-Build:** `build_mode: "rush"` in meta.json, or V says "rush mode"

Rush mode reverts to Pulse v2 behavior: auto-spawn, no Decision Points, no Wave Reviews.

### Understanding Bank Integration

- **Read at plan time:** Architect reads `N5/config/understanding_bank.json` to calibrate Learning Landscape
- **Update at build close:** Pedagogical AAR updates concept levels based on V's demonstrated understanding
- **Updated by Learning Drops:** L-prefix deposits include `understanding_update` assessments
