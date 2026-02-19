---
created: 2026-01-24
last_edited: 2026-01-25
version: 2.0
provenance: con_xrhltA7BHuQGYNyw
---

# Filter Criteria

The Filter is an LLM-based judge that validates Deposits against their briefs.

## Judgment Process

Filter receives:
1. The original Drop brief
2. The Deposit JSON
3. File contents of artifacts (if accessible)

Filter outputs:
```json
{
  "drop_id": "D1.1",
  "verdict": "PASS" | "FAIL" | "WARN",
  "confidence": 0.0-1.0,
  "reasoning": "Explanation of judgment",
  "criteria_results": [
    {"criterion": "Schema has 5 tables", "met": true},
    {"criterion": "Soft-delete pattern used", "met": true}
  ],
  "concerns": [],
  "timestamp": "ISO timestamp"
}
```

## Verdict Definitions

| Verdict | Meaning | Action |
|---------|---------|--------|
| **PASS** | All success criteria met, no red flags | Mark complete, advance |
| **WARN** | Criteria met but concerns exist | Mark complete, log concerns, notify |
| **FAIL** | Criteria not met or artifacts missing | Mark failed, escalate via SMS |

## Evaluation Rubric

### 1. Artifact Existence (Required)
- Do all specified output files exist?
- Are they non-empty?

### 2. Success Criteria (Required)
- Each checkbox in the brief must be verifiable
- Check file contents when possible
- If a criterion cannot be verified, note it

### 3. Coherence (Advisory)
- Does the work make sense given the context?
- Any obvious errors or anti-patterns?

### 4. Scope Creep (Advisory)
- Did the Drop create unexpected files?
- Did it modify files outside its scope?

### 5. Skills Utilization (Advisory)
Evaluate whether the Drop used skills appropriately:

**Check for existing skills:**
- Did the Drop check for existing skills before building?
- If a relevant skill existed, did the Drop use it?
- If the Drop built functionality that exists in a skill, this is a WARN

**Check for skill creation:**
- Did the Drop create reusable functionality?
- If yes, was it packaged as a skill (under `Skills/`) or a one-off script?
- Reusable functionality as one-off script → WARN with note "Consider extracting to skill"

**Signals of good skills discipline:**
- Deposit mentions "used existing skill X"
- Deposit mentions "created new skill Y because Z"
- No duplicate functionality with existing skills

**Signals of poor skills discipline:**
- Created script that duplicates existing skill
- Built reusable functionality but didn't package as skill
- No mention of skills consideration in deposit

### 6. Technique Selection (Advisory)
Evaluate whether the Drop used the right tool for the job:

**LLM vs Code/Regex:**
| Task Type | Should Use |
|-----------|------------|
| Extract meaning from unstructured text | LLM |
| Classify or categorize content | LLM |
| Parse natural language | LLM |
| Structured data (JSON, CSV) parsing | Code |
| Math/calculations | Code |
| File operations | Code |
| Pattern matching on structured data | Regex |
| Pattern matching on natural language | LLM |

**Red flags (potential WARN):**
- Complex regex (3+ alternations) for natural language parsing
- Regex that keeps breaking on edge cases
- Hard-coded string matching for semantic classification
- LLM calls for simple structural operations (wasteful)

**Check the code:**
- Does it use `/zo/ask` for semantic tasks?
- Does it use regex/code for structural tasks?
- Is there brittle pattern matching that should be LLM?

**Signals of good technique selection:**
- Deposit notes explain technique choices
- LLM used for meaning extraction, code used for structure
- BUILD_LESSONS.json updated with technique learnings

**Signals of poor technique selection:**
- Regex soup for natural language
- LLM calls for trivial structural tasks
- No consideration of technique tradeoffs

### 7. Learning Annotations (Advisory)
Evaluate whether the Drop captured learning-relevant metadata:

**Check for concept tracking:**
- Did the deposit include `concepts_exercised`?
- If the Drop involved a Decision Point, was V's decision recorded?
- If the Drop was tagged `pedagogical` in the Learning Landscape, was V's engagement documented?

**Signals of good learning discipline:**
- Deposit lists specific concepts exercised
- Decisions include V's reasoning, not just the choice
- Learning Drops include understanding_update assessments

**Signals of poor learning discipline:**
- Pedagogical Drop with no concepts or decisions logged
- Decision Points resolved without documenting V's reasoning
- No concept tracking despite plan flagging concepts

## Filter Prompt Template

```
You are the Filter, a quality judge for automated builds.

BRIEF:
{brief_content}

DEPOSIT:
{deposit_json}

ARTIFACTS (if available):
{artifact_contents}

Evaluate this Deposit against the brief's success criteria.

EVALUATION AREAS:
1. **Artifact Existence**: Do all required files exist and have content?
2. **Success Criteria**: Are all checkboxes from the brief satisfied?
3. **Coherence**: Does the work make sense? Any obvious errors?
4. **Scope Creep**: Did the Drop stay within its scope?
5. **Skills Utilization**: Did the Drop use existing skills where available? If it created reusable functionality, is it packaged as a skill?
6. **Technique Selection**: Did the Drop use LLM for semantic tasks and code/regex for structural tasks appropriately?
7. **Learning Annotations**: If the Drop was tagged pedagogical or involved Decision Points, did it capture concept tracking and V's reasoning?

Return JSON:
{
  "drop_id": "...",
  "verdict": "PASS" | "FAIL" | "WARN",
  "confidence": 0.0-1.0,
  "reasoning": "...",
  "criteria_results": [
    {"criterion": "...", "met": true/false}
  ],
  "concerns": [
    {"area": "skills_utilization" | "technique_selection" | "learning_annotations" | "scope" | "other", "detail": "..."}
  ]
}

Be strict on required criteria (1-2). 
For advisory criteria (3-7), note concerns but don't fail unless egregious.
If criteria cannot be verified, verdict is WARN not PASS.
```

## Escalation on FAIL

When Filter returns FAIL:
1. SMS sent immediately with drop_id and reasoning
2. Build continues (other Drops not blocked unless dependent)
3. Human review required before retry

## Escalation on WARN

When Filter returns WARN with skills/technique concerns:
1. Log concerns to BUILD_LESSONS.json for future reference
2. Continue build (these are advisory, not blocking)
3. Include in build AAR for pattern analysis