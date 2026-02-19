---
created: 2026-01-25
last_edited: 2026-01-25
version: 1.0
provenance: con_xrhltA7BHuQGYNyw
template_type: checkpoint
---

# Checkpoint Drop Template

Checkpoints are **strategic quality gates** placed at high-risk junctures in a build. Unlike regular Drops that produce artifacts, Checkpoints verify work and guide downstream Drops.

## When to Place Checkpoints

During planning, Architect identifies:
1. **Build type** → Known failure modes
2. **High-risk handoffs** → Where bad output cascades
3. **Integration points** → Where multiple Drops' work must align

## Checkpoint Brief Template

```markdown
---
drop_id: C<n>
build_slug: <slug>
type: checkpoint
depends_on: [D1.1, D1.2]  # Drops this checkpoint reviews
gates: [D2.1, D2.2]       # Drops that wait for this checkpoint
priority: critical        # critical = pause build on failure
---

# Checkpoint: <Verification Goal>

**Purpose:** <What risk this checkpoint mitigates>

**Upstream Drops:** <What work is being verified>

**Downstream Impact:** <What depends on this passing>

---

## Verification Tasks

<Specific checks tuned to this build's failure modes>

### 1. <Check Category>
- [ ] <Specific verification>
- [ ] <Specific verification>

### 2. <Check Category>
- [ ] <Specific verification>

## Known Failure Modes

<What typically goes wrong at this juncture>

- **Failure mode 1:** <Description> → Check: <What to verify>
- **Failure mode 2:** <Description> → Check: <What to verify>

## On Pass

1. Write to `N5/builds/<slug>/guidance/C<n>-guidance.md`:
   - Observations for downstream Drops
   - Any decisions that should be consistent
   - Warnings about edge cases noticed

2. Write deposit with `status: "pass"`

## On Fail

1. Write deposit with `status: "fail"` and detailed `concerns`
2. If `priority: critical`:
   - Email V immediately with findings
   - Downstream Drops should NOT proceed
3. Include specific remediation guidance

---

## Deposit Schema

```json
{
  "drop_id": "C1",
  "type": "checkpoint",
  "status": "pass" | "fail" | "warn",
  "timestamp": "ISO timestamp",
  "verified": [
    {"check": "Schema has users table", "passed": true},
    {"check": "Types match schema", "passed": true}
  ],
  "failed": [],
  "guidance_written": "N5/builds/<slug>/guidance/C1-guidance.md",
  "concerns": [],
  "recommendations_for_downstream": [
    "D2.1 should use soft-delete pattern consistent with schema"
  ]
}
```
```

---

## Common Checkpoint Types by Build Category

### API Builds
| Checkpoint | Placement | Verifies |
|------------|-----------|----------|
| Schema Gate | After schema Drop | Tables, relationships, naming |
| Contract Gate | After API Drop | Endpoints match schema, consistent patterns |
| Integration Gate | Before frontend | API actually works, auth flows correct |

### Data Pipeline Builds
| Checkpoint | Placement | Verifies |
|------------|-----------|----------|
| Ingestion Gate | After ingest Drop | Data loaded, schema correct |
| Transform Gate | After transform Drop | No data loss, types preserved |
| Output Gate | Before consumers | Format correct, validation passes |

### Frontend Builds
| Checkpoint | Placement | Verifies |
|------------|-----------|----------|
| Component Gate | After component Drops | Props consistent, no orphans |
| State Gate | After state management | Actions/reducers aligned |
| Integration Gate | Before deploy | API calls work, routing correct |

### Integration Builds
| Checkpoint | Placement | Verifies |
|------------|-----------|----------|
| Contract Gate | After both sides built | Interfaces match |
| Auth Gate | After auth implemented | Flows work end-to-end |
| E2E Gate | Before deploy | Happy path works |

---

## Architect Guidance: Placing Checkpoints

**Rule of thumb:** Place a checkpoint wherever:
1. Multiple Drops' outputs must be consistent
2. A bad decision would cascade to 2+ downstream Drops
3. The build type has a known failure pattern at that point

**Don't over-checkpoint:** 1-2 checkpoints per build is typical. More than 3 suggests the build should be decomposed differently.

**Checkpoint ≠ Filter:** Filter validates individual Drops. Checkpoints validate cross-Drop consistency and guide downstream work.
