---
name: claude-code-window-primer
description: Optimizes Claude Code Pro/Max usage by priming the 5-hour rolling window early morning, ensuring resets align with peak work hours for maximum Opus availability.
compatibility: Zo Computer with Claude Code Pro or Max subscription
metadata:
  author: <YOUR_HANDLE>.zo.computer
  version: "1.0"
  created: 2026-02-12
  tags: ["claude-code", "optimization", "scheduling"]
---

# Claude Code Window Primer

## The Problem

Claude Code Pro has a 5-hour rolling usage window. If you start using Opus at 9am, you hit the limit around 2pm and wait until... 2pm for reset. That's a dead zone right when you're productive.

## The Solution

Prime the window before you wake up. A trivial Opus request at 6:30am starts the clock, giving you resets at useful times:

| Time | Event |
|------|-------|
| 6:30am | Window primed (while sleeping) |
| 11:30am | First reset (mid-morning) |
| 4:30pm | Second reset (afternoon) |
| 9:30pm | Third reset (evening if needed) |

This maximizes Opus availability during typical work hours (9am–11pm).

## Does This Burn Through Weekly Limits?

No. The primer uses ~15 tokens (asks Opus to return 0 or 1). Weekly limits track *actual usage*, not window starts. This is pure timing optimization.

## Installation

### 1. Create the scheduled agent

In a Zo conversation:

```
Create a scheduled agent:
- Schedule: Daily at 6:30am (your timezone)
- Instruction: Run python3 Skills/claude-code-window-primer/scripts/prime_window.py
- Delivery: None (silent)
```

Or adjust the time to ~3 hours before you typically start working.

### 2. Verify it's working

Check your Claude Code usage after the first run — you should see a tiny blip at 6:30am.

## Manual Trigger

Shift your window anytime:

```bash
python3 Skills/claude-code-window-primer/scripts/prime_window.py
```

Useful if you wake up early or want to realign mid-day.

## Configuration

**Different wake time?** Edit the agent schedule. The math:
- Set primer to fire ~3 hours before you start working
- First reset lands ~2 hours into your work day
- Second reset lands ~7 hours in

**Max subscription?** Same principle applies — you just have more headroom per window.

## How It Works

The script calls `/zo/ask` with a trivial prompt targeting Opus specifically:

```
"Return either 0 or 1 at random. Nothing else."
```

Minimal tokens, starts the window, done.

## Files

```
claude-code-window-primer/
├── SKILL.md              # This file
└── scripts/
    └── prime_window.py   # The primer script
```
