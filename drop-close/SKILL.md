---
name: drop-close
description: |
  Close Pulse worker (Drop) threads. Writes structured deposit JSON for
  orchestrator review. Does NOT commit - that's the orchestrator's job.
  For normal threads use thread-close. For post-build synthesis use build-close.
---

# Drop Close

Close Pulse Drop worker threads with structured deposits.

## When to Use

- Pulse Drops (headless workers spawned via `/zo/ask`)
- Any thread with `drop_id` in SESSION_STATE

**Wrong tool?**
- If normal thread → use `thread-close`
- If closing a completed build → use `build-close`

## Quick Start

```bash
# Close current drop (reads context from SESSION_STATE)
python3 Skills/drop-close/scripts/close.py --convo-id con_XXXXX
```

## What It Does

1. **Validates context** — Guards check you ARE a Drop
2. **Reads drop_id and build_slug** from SESSION_STATE
3. **Generates title** — 3-slot emoji system with build context
4. **Gathers deposit data**:
   - Summary of work done
   - List of artifacts created
   - Key learnings
   - Concerns for orchestrator
   - Decisions made (with rationale)
   - Concepts exercised (from Learning Landscape)
5. **Writes deposit JSON** to `N5/builds/<slug>/deposits/<drop_id>.json`
6. **Does NOT commit** — Orchestrator handles that

## Title Generation (REQUIRED)

After the script outputs context JSON, you MUST generate a title using the 3-slot emoji system.

### Format
```
MMM DD | {state} {type} {content} [Build Title] Drop Task Summary
```

### For Drops:
- **Slot 1 (State):** `✅` complete, `❌` failed, `⏸️` blocked
- **Slot 2 (Type):** Always `👷🏽‍♂️` (worker)
- **Slot 3 (Content):** Match the work type (🏗️ build, 🛠️ repair, 🔎 research, etc.)
- **[Brackets]:** ALWAYS include the build title (from `build_slug` → meta.json)

### Example Titles
```
Jan 24 | ✅ 👷🏽‍♂️ 🏗️ [Pulse System] D1.1 Core Script Implementation
Jan 24 | ✅ 👷🏽‍♂️ 🛠️ [Close Skills] D2.3 Guards Module Fixes  
Jan 24 | ❌ 👷🏽‍♂️ 🏗️ [API Integration] D1.2 Auth Handler (blocked on API key)
```

### Title Generation Steps
1. Get `build_slug` from SESSION_STATE or script output
2. Look up build title: `cat N5/builds/<slug>/meta.json | jq -r '.title'`
3. Determine state from work outcome (complete/failed/blocked)
4. Use 👷🏽‍♂️ for type (always worker)
5. Pick content emoji based on what the drop did
6. Include drop_id (D1.1, D2.3, etc.) in the semantic title
7. Describe what was accomplished in 3-5 words

### Emoji Quick Reference

| Slot | Emoji | Meaning |
|------|-------|---------|
| State | ✅ | Complete |
| State | ❌ | Failed |
| State | ⏸️ | Blocked/waiting |
| Type | 👷🏽‍♂️ | Worker (always for drops) |
| Content | 🏗️ | Building/implementing |
| Content | 🛠️ | Fixing/repairing |
| Content | 🔎 | Research/investigation |
| Content | ✍️ | Writing/content |
| Content | 📊 | Data work |

## Deposit Format

```json
{
  "drop_id": "D1.1",
  "convo_id": "con_XXXXX",
  "status": "complete",
  "completed_at": "2026-01-24T12:00:00Z",
  "summary": "Created foo.py and bar.py with tests",
  "artifacts": [
    "Skills/my-skill/scripts/foo.py",
    "Skills/my-skill/scripts/bar.py"
  ],
  "learnings": "The API requires auth header even for public endpoints",
  "concerns": "Rate limiting may be an issue at scale",
  "decisions": [
    {
      "decision": "Used async/await over threads",
      "rationale": "Better performance for I/O-bound operations"
    }
  ],
  "concepts_exercised": ["async-patterns", "error-handling"]
}
```

## Options

- `--convo-id` (required): Conversation ID
- `--force`: Bypass context guards
- `--status`: Override status (complete|partial|failed|blocked)

## Fail-Safes

This skill includes context guards. If you call it incorrectly:

```
⚠️  WRONG SKILL DETECTED

You called: drop-close
Suggested:  thread-close
Reason:     No drop context — use thread-close instead

Run the suggested skill instead, or use --force to override.
```

## Integration with Pulse

Drops should call this at the end of their work:

```python
# In drop brief template
# At end of work:
# python3 Skills/drop-close/scripts/close.py --convo-id {CONVO_ID}
```

The deposit is then:
1. Detected by Pulse tick loop
2. Filtered via LLM judgment
3. Used in build-close synthesis

## Checklist Before Completing

- [ ] Title generated with all 3 emoji slots
- [ ] Title includes [Build Title] in brackets
- [ ] Title includes drop_id (D#.#)
- [ ] Deposit JSON written to correct path
- [ ] Artifacts list is complete and uses relative paths
- [ ] Learnings captured (if any discoveries made)
- [ ] Concerns noted (if any issues for orchestrator)
- [ ] Concepts exercised listed (if build has Learning Landscape)

## Related

- `file 'N5/config/emoji-legend.json'` — Full emoji definitions
- `file 'N5/lib/close/emoji.py'` — Title generation helpers
- `file 'Skills/thread-close/SKILL.md'` — Normal thread close
- `file 'Skills/build-close/SKILL.md'` — Build synthesis close
