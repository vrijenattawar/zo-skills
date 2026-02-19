---
created: 2026-02-17
last_edited: 2026-02-17
version: 1.0
provenance: learning-engaged-builds
---

# Decisions Log Template

Placed in each build folder as `DECISIONS.md`. Records V's engagement with technical decisions.

---

```markdown
---
created: {{DATE}}
build_slug: {{SLUG}}
---

# Decisions Log: {{TITLE}}

Tracks technical decisions V engaged with during this build.

## Decision Points

### DP-1: {{QUESTION}}
- **Date:** {{DATE}}
- **Context:** {{WHY_THIS_DECISION_MATTERS}}
- **Options Considered:**
  1. **{{OPTION_A}}** — {{TRADEOFF_A}}
  2. **{{OPTION_B}}** — {{TRADEOFF_B}}
  3. **{{OPTION_C}}** — {{TRADEOFF_C}} *(if applicable)*
- **V's Choice:** {{CHOICE}}
- **V's Reasoning:** {{V_REASONING}}
- **Concepts Involved:** {{CONCEPTS}}
- **Dialogue Rounds:** {{N}}
- **Understanding Evidence:** {{WHAT_V_DEMONSTRATED}}

<!-- Repeat for each Decision Point -->
```
