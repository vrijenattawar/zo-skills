---
created: 2026-02-10
last_edited: 2026-02-10
version: 1.0
provenance: con_XXXXXXXXXX
---

# Persona Optimization Architecture

## Why this exists

A single, all‑purpose system prompt tends to blur roles. The outcome: weak specialization, inconsistent outputs, and brittle switching. This package creates **a small agency** of personas with clearly defined scopes and a routing layer that keeps them in their lanes.

## The core model (hybrid switching)

We use **two distinct mechanisms** based on what the persona actually contributes:

### 1) Hard‑switch personas (stance shift)
These personas require a **full persona switch** because they represent a distinct cognitive stance:

- **Builder** — engineering discipline + implementation rigor
- **Debugger** — skeptical verification + root cause analysis
- **Strategist** — multi‑path thinking + tradeoff framing
- **Writer** — voice fidelity + audience‑aware communication

Mechanism: **rules with MUST language** that trigger `set_active_persona()` before substantive work.

### 2) Methodology injection (technique shift)
These personas provide **process frameworks** rather than a distinct stance:

- **Researcher** — multi‑source search + synthesis discipline
- **Teacher** — scaffolded explanations + learning calibration

Mechanism: **rule‑triggered methodology loading** (no persona switch).

## Control flow (Operator‑centric)

- **Operator is always the home base.** Every conversation begins there.
- Operator routes based on intent and keeps state coherent.
- After specialists finish, they **return to Operator** with a summary.

## Why this works

- **Stance changes need hard switches** (LLMs won’t self‑interrupt reliably)
- **Technique changes can be injected** without switching (faster, lower overhead)
- Operator remains the continuity layer (state, progress, and safety)

## Failure modes this solves

- “It sounds helpful, but doesn’t actually switch” → hard‑switch rules
- “Everything is a research task” → clear methodology vs stance separation
- “Specialists get stuck” → explicit return‑to‑Operator rule

## What gets installed

- 7 personas (prompts in `templates/personas/`)
- 6 rules (4 hard‑switch + 2 methodology)
- Routing contract file in the recipient’s system docs

## Extensibility

This architecture supports additional personas by:
1. Deciding if they are **stance** or **methodology**
2. Adding a prompt
3. Adding a rule (if stance) or load behavior (if methodology)
4. Updating the routing contract
