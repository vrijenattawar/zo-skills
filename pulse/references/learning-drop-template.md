---
created: 2026-02-17
last_edited: 2026-02-17
version: 1.0
provenance: learning-engaged-builds
---

# Learning Drop Brief Template

Use this template for L-prefix (Learning) Drops in Pulse builds.

---

```markdown
---
drop_id: L<stream>.<seq>
build_slug: <slug>
spawn_mode: manual
type: learning
thread_title: "[<slug>] L<stream>.<seq>: Learn — <Concept>"
---

# Learning Drop: <Concept>

**Mission:** Help V understand <concept> well enough to make informed decisions about <specific decision point in the build>.

**V's Current Level:** <from understanding_bank.json>

---

## Build Context

<Why this concept matters for this specific build. What decisions hinge on understanding this.>

## Files to Read

| File | Why Read It |
|------|-------------|
| `N5/config/understanding_bank.json` | V's current understanding level |
| `N5/builds/<slug>/PLAN.md` | Build context, Learning Landscape |
| `<relevant source files>` | Real code examples for grounded teaching |

## Teaching Approach

Follow Vibe Teacher methodology (Documents/System/personas/vibe_teacher_persona.md):

1. **Start with analogy** from V's domain (career coaching, <YOUR_PRODUCT>, N5 systems)
2. **Explain WHY** this concept exists before HOW it works
3. **10-15% knowledge stretch** from V's current level — don't jump 50%
4. **Socratic dialogue** — ask questions, let V connect dots, validate reasoning
5. **Ground in the build** — use actual files and decisions from THIS build, not abstract examples
6. **Check comprehension** every 2-3 concepts

## On Completion

Write deposit to `N5/builds/<slug>/deposits/<drop_id>.json`:

```json
{
  "drop_id": "<drop_id>",
  "type": "learning",
  "status": "complete",
  "timestamp": "<ISO timestamp>",
  "concepts_covered": ["<concept1>", "<concept2>"],
  "v_conclusions": ["<decisions or preferences V expressed>"],
  "understanding_update": {
    "<concept>": "<new level: encountered/learning/familiar/solid>"
  },
  "build_relevant_insights": "<anything the orchestrator should know for subsequent Drops>"
}
```

**DO NOT COMMIT CODE.** The orchestrator commits at build completion.
```

---

## Key Differences from Standard Drops

| Aspect | Standard Drop | Learning Drop |
|--------|--------------|---------------|
| Prefix | D (e.g. D1.1) | L (e.g. L1.1) |
| spawn_mode | auto (default) or manual | ALWAYS manual |
| type | (none) | learning |
| Goal | Produce artifacts | Produce understanding |
| Deposit | Artifacts + decisions | Concepts + V's conclusions |
| Blocks build? | May block downstream | Never blocks build |
