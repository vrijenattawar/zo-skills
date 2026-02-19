---
created: 2026-01-24
last_edited: 2026-01-25
version: 2.0
provenance: con_xrhltA7BHuQGYNyw
---

# Pulse Interview Protocol

Pre-build interview to decompose work into Streams, Drops, and Checkpoints.

## When to Use

Before any build that will use Pulse orchestration.

## The Six Questions

### 1. What are we building?
- Concrete deliverables (files, features, systems)
- Success criteria
- Out of scope

### 2. What are the independent tracks?
These become **Streams** (parallel execution).
- Can run simultaneously
- No dependencies between them
- Examples: backend vs frontend, different features

### 3. What must happen in sequence?
These become **Currents** (sequential chains within a Stream).
- A feeds into B feeds into C
- Order matters
- Examples: schema → API → tests

### 4. What are the risks?
- Technical unknowns
- External dependencies
- Potential blockers

### 5. Where are the checkpoints?
Checkpoints are **strategic quality gates** at high-risk junctures.

**Identify build type:**
- API build? Data pipeline? Frontend? Integration?
- What typically goes wrong with this type?

**Identify high-risk handoffs:**
- Where does one Drop's bad output cascade to multiple downstream Drops?
- Where must multiple Drops' outputs be consistent?

**Place checkpoints:**
- 1-2 checkpoints per build is typical
- Each checkpoint gets a specific verification brief
- Reference: `Skills/pulse/drops/checkpoint-template.md`

| Build Type | Common Checkpoint Placements |
|------------|------------------------------|
| API | After schema, before frontend integration |
| Data Pipeline | After ingest, after transform |
| Frontend | After components, before deploy |
| Integration | After both sides built, before E2E |

## Output

Generate in `N5/builds/<slug>/`:
- `meta.json` — Build metadata with streams, drops, checkpoints
- `drops/D*.md` — Drop briefs
- `drops/C*.md` — Checkpoint briefs

## Decomposition Patterns

### Layer Cake (most common)
```
Stream 1: Foundation (schema, types, config)
    → Checkpoint C1: Verify foundation consistency
Stream 2: Core (business logic, APIs)
    → Checkpoint C2: Verify API matches schema
Stream 3: Surface (UI, integrations)
```

### Feature Slices
```
Stream 1: Feature A (full stack)
Stream 2: Feature B (full stack)
Stream 3: Feature C (full stack)
    → Checkpoint C1: Verify features don't conflict
```

### Pipeline
```
Current 1: Ingest → Checkpoint → Transform → Checkpoint → Validate → Store
```

## Anti-Patterns

- **Too granular**: >5 Drops per Stream = overhead exceeds value
- **False parallelism**: Drops that actually depend on each other
- **Missing dependencies**: Drop assumes artifact that doesn't exist yet
- **No checkpoints**: Complex builds without quality gates = cascade failures
- **Over-checkpointing**: >3 checkpoints = decompose the build differently

### 6. What should V learn from this build?
These inform the **Learning Landscape** in the plan.
- Which technical concepts in this build are new to V? (Check `N5/config/understanding_bank.json`)
- Which decisions have the highest pedagogical value?
- What level of engagement does V want? (minimal / standard / full)
- Are there concepts V specifically wants to deep dive into?
