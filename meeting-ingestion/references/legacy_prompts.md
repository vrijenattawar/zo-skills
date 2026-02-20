---
created: 2026-01-26
last_edited: 2026-01-26
version: 1.1
provenance: con_TRpqstPn1qgxSiAb
---

# Legacy Meeting Prompts Reference

This document consolidates the logic from legacy prompt files that have been replaced by the unified meeting-ingestion skill. It serves as a reference for understanding the historical approach and the intelligence block definitions.

---

## Source Prompts

The following prompts have been consolidated into this skill:

| Legacy Prompt | Status | Replaced By |
|--------------|--------|-------------|
| `Prompts/drive_meeting_ingestion.prompt.md` | Consolidated | `scripts/pull.py` |
| `Prompts/Analyze Meeting.prompt.md` | Consolidated | `scripts/processor.py` |
| `Prompts/Internal Meeting Process.prompt.md` | Reference | Block definitions |
| `Prompts/Meeting State Transition.prompt.md` | Reference | State machine logic |
| `Prompts/standardize_meeting_folder.prompt.md` | Reference | Naming conventions |

---

## Meeting Types

### External Meetings
Meetings with people outside the organization (prospects, partners, advisors).

**Detection:**
- Default type when no internal markers present
- Contains markers: `_external`, `_partnership`, `_discovery`, `_sales`, `_coaching`, `_advisory`, `_demo`, `_networking`

**Standard Blocks:**
- B01_DETAILED_RECAP (always)
- B02_COMMITMENTS (always)
- B03_DECISIONS (always)
- B05_ACTION_ITEMS (always)
- B08_STAKEHOLDER_INTELLIGENCE (always for external)
- B25_DELIVERABLES (always)
- B26_MEETING_METADATA (always)
- Plus conditional blocks based on content analysis

### Internal Meetings
Team meetings, co-founder syncs, standups.

**Detection:**
- Contains `_internal` in folder name
- Ends with `_[M]` suffix

**Standard Blocks:**
- B26_MEETING_METADATA
- B40_INTERNAL_DECISIONS
- B41_TEAM_COORDINATION
- B47_OPEN_DEBATES
- Plus conditional B42-B48 based on content

---

## Intelligence Block Definitions

### Core Blocks (B01-B26)

#### B01_DETAILED_RECAP
Comprehensive meeting summary covering all topics discussed, decisions made, and outcomes. Should enable someone who wasn't present to understand what happened.

#### B02_COMMITMENTS
Explicit commitments made by participants. Format: WHO committed to WHAT by WHEN.

#### B03_DECISIONS
Key decisions made during the meeting with rationale. Includes what was decided, why, and who made the decision.

#### B04_OPEN_QUESTIONS
Unresolved questions that need follow-up. Questions raised but not answered.

#### B05_ACTION_ITEMS
Concrete action items with owners and deadlines. Format: WHO | ACTION | DUE DATE | STATUS.

#### B06_BUSINESS_CONTEXT
Business implications and strategic context. How does this meeting relate to business goals?

#### B07_TONE_AND_CONTEXT
Emotional tone, relationship dynamics, and interpersonal context. Non-verbal communication patterns, relationship health indicators.

#### B08_STAKEHOLDER_INTELLIGENCE
Deep insights about external stakeholders:
- Communication style and preferences
- Decision-making patterns
- Personal interests and motivations
- Professional background and context
- Relationship dynamics
- Red flags or concerns

**Critical for:** Building long-term relationships, deal intelligence, personalized follow-ups.

#### B10_RISKS_AND_FLAGS
Potential risks, concerns, and red flags identified during the meeting.

#### B13_PLAN_OF_ACTION
Coordinated plan of action based on meeting outcomes. Multi-stakeholder coordination.

#### B21_KEY_MOMENTS
Significant moments, quotes, or turning points. Memorable exchanges that capture essence.

#### B25_DELIVERABLES
Specific deliverables discussed or committed to. What artifacts need to be created?

#### B26_MEETING_METADATA
Meeting metadata: date, participants, duration, purpose, location.

#### B28_STRATEGIC_INTELLIGENCE
Long-term strategic implications and insights. How does this meeting affect strategy?

### Internal Blocks (B40-B48)

#### B40_INTERNAL_DECISIONS
Strategic and tactical decisions made in internal meetings.

**Structure:**
- Strategic Decisions table
- Tactical Decisions table
- Holistic Pushes (strategy + execution path)
- Resolved Tactical Debates

#### B41_TEAM_COORDINATION
Action items with decision context via cross-references.

**Structure:** Table with Owner | Action | Context [B40 ref] | Due Date | Dependencies | Status

#### B42_MARKET_COMPETITIVE_INTEL (Conditional)
Market trends, competitive landscape, customer insights from internal discussion.

#### B43_PRODUCT_INTELLIGENCE (Conditional)
Product strategy, roadmap, architecture, technical decisions.

#### B44_GTM_SALES_INTEL (Conditional)
Go-to-market strategy, sales process, pricing, distribution.

#### B45_OPERATIONS_PROCESS (Conditional)
Operational processes, tools, workflows, organizational decisions.

#### B46_HIRING_TEAM (Conditional)
Hiring decisions, role definitions, team expansion.

#### B47_OPEN_DEBATES
Unresolved strategic questions requiring future resolution.

#### B48_STRATEGIC_MEMO (Conditional)
Executive synthesis for meetings ≥30min with significant strategic decisions.

---

## Meeting State Machine

Meetings progress through processing states indicated by folder suffixes:

```
[Raw] → _[M] (Manifested) → _[B] (Blocked) → _[C] (Complete)
```

### States

| Suffix | State | Meaning |
|--------|-------|---------|
| (none) | Raw | Transcript present, not processed |
| `_[M]` | Manifested | Manifest generated, blocks not yet created |
| `_[B]` | Blocked | Intelligence blocks generated |
| `_[C]` | Complete | CRM sync complete, fully processed |

### Transition Rules

1. **Raw → Manifested:** Run manifest generator, write manifest.json
2. **Manifested → Blocked:** Generate all blocks in manifest
3. **Blocked → Complete:** CRM sync successful (external meetings only)

---

## Folder Naming Convention

### Standard Format
```
YYYY-MM-DD_FirstLast_FirstLast[_Suffix]
```

### Examples
```
2025-01-15_UserName_JohnDoe
2025-01-15_UserName_JohnDoe_[M]
2025-01-15_UserName_JohnDoe_[B]
2025-01-15_UserName_JohnDoe_[C]
2025-01-15_TeamStandup_internal
```

### Parsing Rules
1. Extract date from first YYYY-MM-DD segment
2. Split remaining on underscores
3. Filter out state suffixes ([M], [B], [C])
4. Filter out type markers (internal, external)
5. Remaining segments are participant names

---

## MECEM Principles

From Internal Meeting Process prompt:

**M**utually **E**xclusive, **C**ollectively **E**xhaustive, **M**inimally repeating

### Mutually Exclusive
Each piece of information belongs in exactly ONE canonical location:
- Strategic decisions → B40 only
- Action items → B41 (references B40 for context)
- Market intelligence → B42 (not in B40)

### Collectively Exhaustive
All relevant information captured somewhere:
- Strategic + tactical decisions → B40
- Unresolved items → B47
- Execution → B41
- Domain intelligence → B42-B46

### Minimally Repeating
Information stored once, referenced everywhere:
- Use cross-references: `[B40.D3]`, `[B41.A5]`, `[B47.Q2]`
- Action items reference B40 for WHY (don't duplicate rationale)
- B48 synthesizes (exception for executive readability)

---

## Cross-Reference Format

```markdown
[B40.D3]  → Decision 3 in B40 (current meeting)
[B40.T5]  → Tactical decision 5 in B40
[B41.A7]  → Action 7 in B41
[B47.Q2]  → Open question 2 in B47
[2025-08-27_internal-team/B40.D2]  → Decision from past meeting
```

---

## CRM Sync Logic

For external meetings, B08_STAKEHOLDER_INTELLIGENCE feeds into CRM:

1. Parse B08 for stakeholder entries
2. Match stakeholders to CRM records (by name/email)
3. Update stakeholder profiles with:
   - Communication preferences
   - Recent interaction summary
   - Decision-making patterns
   - Relationship health indicators
4. Create interaction log entry

---

## Migration Notes

### What Changed
1. **Single skill replaces 5+ agents** - No more MG-1 through MG-6 chain
2. **Unified CLI** - `meeting-ingestion pull && meeting-ingestion process`
3. **Thin wrappers** - Skill orchestrates existing scripts/scripts
4. **Zo API for Drive** - Leverages authenticated connections

### What Stayed the Same
- Block definitions and structure
- MECEM principles
- State machine logic
- Folder naming conventions
- CRM sync process

## Deleted Files (2026-01-26)

The following legacy prompts were deleted as part of the skill consolidation:

1. **Prompts/drive_meeting_ingestion.prompt.md** - Replaced by `pull.py`
2. **Prompts/Analyze Meeting.prompt.md** - Replaced by `processor.py`
3. **Prompts/Auto Process Meetings.prompt.md** - Consolidated into skill
4. **Prompts/Meeting Process.prompt.md** - Consolidated into skill
5. **Prompts/Meeting Transcript Process.prompt.md** - Consolidated into skill
6. **Prompts/Meeting Transcript Scan.prompt.md** - Consolidated into skill
7. **Prompts/meeting-block-selector.prompt.md** - Duplicate
8. **Prompts/meeting-block-generator.prompt.md** - Duplicate
9. **Prompts/standardize_meeting_folder.prompt.md** - Legacy
10. **Prompts/deduplicate-meetings.prompt.md** - Handled by registry
11. **Prompts/Meeting Detect.prompt.md** - Legacy
12. **Prompts/worker-meeting-cleanup.prompt.md** - Legacy worker
13. **Prompts/Meeting Metadata Extractor.prompt.md** - Consolidated

### Build Folder Deleted

- `scripts/builds/meeting-skill-migration/` - Superseded by `meeting-ingestion-skill`

## Deleted Files - Final Cleanup (2026-01-26 - D4.1 Drop)

After agent migration (D3.1), the following agent-specific prompts were deleted:

1. **Prompts/Meeting Manifest Generation.prompt.md** - Used by MG-1 agent to generate manifests
2. **Prompts/Meeting Block Generation.prompt.md** - Used by MG-2 agent to generate intelligence blocks
3. **Prompts/Meeting Warm Intro Generation.prompt.md** - Used by MG-4 agent to generate warm intro emails
4. **Prompts/Meeting State Transition.prompt.md** - Used by MG-6 agent to transition meeting states
5. **Prompts/Meeting Follow-Up Generation.prompt.md** - Used by MG-5 agent (already disabled)
6. **Prompts/Meeting Blurb Generation.prompt.md** - Used by MG-3 agent (already disabled), replaced by Zo Take Heed system
7. **Prompts/Meeting_Block_Selector.prompt.md** - Duplicate/obsolete, replaced by meeting-ingestion skill's manifest generation

All of these prompts were only used by the now-deleted MG agents and have been consolidated into the unified meeting-ingestion skill.

---

