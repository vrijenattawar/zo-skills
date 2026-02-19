---
created: 2026-02-07
last_edited: 2026-02-07
version: 1.0
provenance: pulse-self-upgrade
---

# Delegate-Only Mode

## Overview

When `delegate_only: true` is set in a build's `meta.json`, the orchestrating conversation operates in **delegate-only mode** — it coordinates Drops but does NOT directly modify source files or run application code.

## Why Use It

- **Provenance clarity**: Every code change has a clear source (a specific Drop)
- **Prevents confusion**: Long builds can cause the orchestrator to "helpfully" intervene
- **Merge safety**: No risk of orchestrator edits conflicting with Drop work
- **Audit trail**: All work is captured in deposits, not conversation history

## When to Enable

Enable for:
- Large builds (5+ Drops)
- Builds where multiple Drops modify related files
- Builds where provenance matters for review
- Self-modifying builds (like Pulse upgrading itself)

## Orchestrator Constraints

When `delegate_only: true`, the orchestrator **MAY**:
- Run `pulse.py` commands (start, tick, stop, status, etc.)
- Read and review deposits
- Read source files (for context, not editing)
- Create/modify Drop briefs
- Retry failed Drops with better context
- Create new Drops for discovered work
- Update STATUS.md and meta.json
- Run `git status`, `git diff` (read-only git operations)

The orchestrator **MUST NOT**:
- Edit source files directly (*.py, *.ts, *.md in Sites/, Skills/, etc.)
- Run application code (except pulse.py orchestration commands)
- "Fix" issues found in deposits (create a retry Drop instead)
- Commit code (wait for finalization)
- Modify files in the build's `artifacts/` directory

## How to Enable

In `meta.json`:

```json
{
  "slug": "my-build",
  "delegate_only": true,
  ...
}
```

## What Happens If Violated

This is a **discipline**, not an enforcement. If the orchestrator violates delegate-only mode:

1. The build's audit trail is compromised
2. V may not notice which changes came from Drops vs. orchestrator
3. Git blame becomes unreliable

**Self-check**: Before any file edit, the orchestrator should ask: "Is this a pulse.py command, a brief, or meta.json? If not, don't touch it."

## Exceptions

The orchestrator MAY break delegate-only for:
- **Critical safety issues** (e.g., Drop is about to delete protected files)
- **V's explicit override** ("Go ahead and fix it directly")
- **Build-blocking infrastructure** (e.g., pulse.py itself is broken)

Document any exceptions in the build's STATUS.md with reason.

## Example Workflow

1. Orchestrator runs `pulse.py tick` → Drop D1.1 deposits with error
2. Orchestrator reads deposit, identifies issue
3. **Wrong**: Orchestrator edits the file to fix it
4. **Right**: Orchestrator runs `pulse.py retry D1.1 --reason "Missed X requirement"`
5. D1.1 re-runs with updated brief, fixes issue itself

## Related

- `file 'Skills/pulse/SKILL.md'` — Main Pulse documentation
- `file 'Skills/pulse/references/drop-brief-template.md'` — How to write good briefs