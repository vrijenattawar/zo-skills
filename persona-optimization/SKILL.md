---
name: persona-optimization
description: |
  Persona agency bootloader for Zo Computer. Installs a multi-persona switching architecture
  with hard-switch rules (Builder, Debugger, Strategist, Writer, Architect) and methodology
  injection (Researcher, Teacher). Includes Operator as home base, Librarian for state sync,
  and a routing contract. Scans your existing setup, proposes changes, installs with approval.
compatibility: Created for Zo Computer
metadata:
  author: va.zo.computer
  version: "1.0.0"
---

# Persona Optimization

Install a multi-persona switching architecture on any Zo Computer.

## What It Does

Creates **a small agency** of personas with clearly defined scopes and a routing layer:

- **Hard-switch personas** (full `set_active_persona()` switch): Builder, Debugger, Strategist, Writer, Architect
- **Methodology injection** (technique loading, no switch): Researcher, Teacher
- **Home base**: Operator (always the starting persona, manages state and routing)
- **Support**: Librarian (state sync, filing)

## Quick Start

```bash
# 1. Scan your Zo environment and generate an install proposal
python3 persona-optimization/scripts/bootloader.py --scan

# 2. Review and edit INSTALL_PROPOSAL.md (personalize names, paths)

# 3. Edit templates/personalize.md with your preferences

# 4. Apply the installation
python3 persona-optimization/scripts/bootloader.py --apply
```

## Architecture

Two distinct switching mechanisms based on what the persona contributes:

| Type | Personas | Mechanism | When |
|------|----------|-----------|------|
| **Stance shift** | Builder, Debugger, Strategist, Writer, Architect | Hard `set_active_persona()` via rules | Distinct cognitive mode needed |
| **Technique shift** | Researcher, Teacher | Methodology file loading (no switch) | Process framework needed |

See `references/architecture.md` for the full design rationale.

## Personalization

Edit `templates/personalize.md` before installing:

- Persona names (default: generic "Builder", "Strategist", etc.)
- Rule prefix (avoids collisions with your existing rules)
- File paths for routing contract and learning ledger
- Approval gate (must answer 5 Socratic questions first)

## Persona Templates

All persona prompts are in `templates/personas/`:

| File | Role |
|------|------|
| `operator.md` | Home base — routing, state, orchestration |
| `builder.md` | Implementation, coding, deployment |
| `debugger.md` | Troubleshooting, QA, root cause analysis |
| `strategist.md` | Decisions, tradeoffs, multi-path thinking |
| `writer.md` | External comms, voice fidelity, drafts |
| `architect.md` | System design, planning, major builds |
| `researcher.md` | Multi-source research methodology |
| `teacher.md` | Scaffolded learning, concept explanation |
| `librarian.md` | State sync, filing, knowledge management |

## Failure Modes This Solves

- "It sounds helpful, but doesn't actually switch" → hard-switch rules force it
- "Everything becomes a research task" → clear methodology vs stance separation
- "Specialists get stuck" → explicit return-to-Operator rule
- "Single prompt tries to do everything" → dedicated cognitive modes

## Extensibility

Add a persona by:
1. Deciding if it's **stance** (needs hard switch) or **methodology** (technique injection)
2. Adding a prompt template in `templates/personas/`
3. Adding a rule (if stance) or load behavior (if methodology)
4. Updating the routing contract
