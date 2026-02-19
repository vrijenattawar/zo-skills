---
template_type: hygiene_check
hygiene_phase: tidying
auto_fix: false
judgment_method: hybrid
priority: 3
version: 2.0
---

# Stub Scan Hygiene Check

## Scope

Detects incomplete implementation markers that indicate unfinished work:
- TODO/FIXME/HACK comments
- `NotImplementedError` and `raise NotImplemented`
- Placeholder strings ("TBD", "PLACEHOLDER", "XXX")
- Empty function/method bodies
- `pass` statements in non-abstract methods

## Purpose

Stubs indicate work that was scoped but not completed. Finding stubs after a build suggests:
- A Drop didn't complete its scope
- Work was intentionally deferred
- Implementation was blocked

These MUST be escalated for review.

## Commands (Phase 1: Find Candidates)

```bash
BUILD_DIR="N5/builds/${BUILD_SLUG}"
ARTIFACTS_DIR="${BUILD_DIR}/artifacts"

# TODO/FIXME/HACK comments
grep -rn "TODO\|FIXME\|HACK\|XXX" "$ARTIFACTS_DIR" --include="*.py" --include="*.ts" --include="*.js"

# NotImplementedError
grep -rn "NotImplementedError\|raise NotImplemented" "$ARTIFACTS_DIR" --include="*.py"

# Placeholder strings
grep -rn "PLACEHOLDER\|TBD\|STUB\|TODO:" "$ARTIFACTS_DIR" --include="*.py" --include="*.ts" --include="*.json"

# Empty function bodies (Python)
grep -Pzo "def \w+\([^)]*\):\s*\n\s*(pass|\.\.\.)\s*\n" "$ARTIFACTS_DIR"/*.py 2>/dev/null

# TypeScript: Empty functions
grep -Pzo "function \w+\([^)]*\)\s*{\s*}" "$ARTIFACTS_DIR"/*.ts 2>/dev/null
```

## Hybrid Approach (Grep → LLM)

**Why hybrid?** Grep finds TODOs fast, but the critical questions are semantic:
- "Is this deferred intentionally with a plan, or forgotten?"
- "Is this empty function a stub, or intentionally empty (abstract/interface)?"
- "Is this HACK acceptable tech debt or a ticking time bomb?"

### Phase 1: Syntactic Discovery (grep)
Run the commands above to find all candidates. Fast and comprehensive.

### Phase 2: Semantic Judgment (LLM)
For each candidate, use `/zo/ask` to assess severity and intent:

```python
import requests
import os

def judge_stub(file_path, line_num, content, context_lines, stub_type):
    """Use LLM to judge stub severity and intent."""
    prompt = f"""You are a code completeness judge. Assess this potential stub/incomplete code.

FILE: {file_path}
LINE {line_num}: {content}
TYPE: {stub_type}

SURROUNDING CONTEXT:
{context_lines}

Determine:
1. Is this INTENTIONAL (documented deferral, abstract method, interface stub)?
2. Is this FORGOTTEN (no context, should have been implemented)?
3. Is this BLOCKED (depends on something not yet available)?

For TODO/FIXME, check:
- Does it reference a ticket/issue number? (intentional tracking)
- Does it have a date or owner? (planned work)
- Is it vague like "TODO: fix this"? (likely forgotten)

For empty functions, check:
- Is the class marked abstract or is this an interface?
- Does the docstring explain why it's empty?
- Is this a hook/callback that's optionally implemented?

Respond with JSON:
{{
  "intent": "intentional" | "forgotten" | "blocked",
  "severity": "high" | "medium" | "low",
  "confidence": 0.0-1.0,
  "reason": "...",
  "recommended_action": "escalate" | "document" | "implement" | "remove"
}}
"""
    
    response = requests.post(
        "https://api.zo.computer/zo/ask",
        headers={
            "authorization": os.environ["ZO_CLIENT_IDENTITY_TOKEN"],
            "content-type": "application/json"
        },
        json={"input": prompt}
    )
    return response.json()["output"]
```

### Judgment Matrix

| Stub Type | Phase 1 (grep) | Phase 2 (LLM) Question |
|-----------|----------------|------------------------|
| TODO comment | ✅ Find all | "Intentional deferral or forgotten?" |
| FIXME comment | ✅ Find all | "Known issue being tracked or abandoned?" |
| NotImplementedError | ✅ Find all | "Abstract method or incomplete implementation?" |
| Empty function | ✅ Find pattern | "Interface stub or missing implementation?" |
| Placeholder string | ✅ Find all | "Config template or hardcoded stub?" |

### Severity Upgrade Rules

LLM judgment can UPGRADE severity based on context:
- TODO with no ticket reference → upgrade to HIGH
- Empty function in non-abstract class with no docstring → upgrade to HIGH  
- PLACEHOLDER in production config path → upgrade to CRITICAL
- HACK older than the build date → upgrade (tech debt accumulating)

## Output Schema

```json
{
  "findings": [
    {
      "type": "todo_comment",
      "file": "scripts/main.py",
      "line": 42,
      "content": "# TODO: implement error handling",
      "severity": "medium",
      "llm_judgment": {
        "intent": "forgotten",
        "confidence": 0.85,
        "reason": "No ticket reference, vague description"
      }
    },
    {
      "type": "not_implemented",
      "file": "scripts/api.py",
      "line": 78,
      "function": "process_webhook",
      "severity": "high",
      "llm_judgment": {
        "intent": "blocked",
        "confidence": 0.9,
        "reason": "Docstring mentions waiting for external API spec"
      }
    },
    {
      "type": "empty_body",
      "file": "scripts/handlers.py",
      "line": 15,
      "function": "on_complete",
      "body": "pass",
      "severity": "high",
      "llm_judgment": {
        "intent": "intentional",
        "confidence": 0.95,
        "reason": "Base class method, subclasses override"
      }
    },
    {
      "type": "placeholder_string",
      "file": "config.json",
      "line": 12,
      "content": "\"api_key\": \"PLACEHOLDER\"",
      "severity": "medium"
    }
  ],
  "auto_fixable": [],
  "requires_review": [
    {
      "type": "not_implemented",
      "severity": "high",
      "issue": "Function has NotImplementedError",
      "recommendation": "Either implement or mark as intentionally abstract",
      "llm_recommendation": "implement"
    }
  ],
  "summary": {
    "total_stubs": 8,
    "high_severity": 3,
    "medium_severity": 5,
    "by_type": {
      "todo_comment": 4,
      "not_implemented": 2,
      "empty_body": 1,
      "placeholder_string": 1
    },
    "by_intent": {
      "intentional": 2,
      "forgotten": 4,
      "blocked": 2
    }
  }
}
```

## Auto-Fix Rules

**auto_fix: false**

Stubs indicate incomplete work and MUST be escalated. Auto-fixing would:
- Hide incomplete features
- Create silent failures
- Mask scope creep

**However**, LLM judgment can DOWNGRADE escalation for clearly intentional stubs:
- Abstract methods with proper docstrings → log but don't escalate
- TODOs with ticket references → track but don't block

## Severity Classification

| Type | Base Severity | LLM Can Adjust |
|------|---------------|----------------|
| `not_implemented` | HIGH | ↓ if abstract method |
| `empty_body` | HIGH | ↓ if interface/hook pattern |
| `todo_comment` | MEDIUM | ↑ if no tracking, ↓ if ticketed |
| `placeholder_string` | MEDIUM | ↑ if in prod config |
| `hack_comment` | LOW | ↑ if old/risky |

## Escalation Triggers

- ANY `not_implemented` → Immediate escalation (unless LLM confirms abstract)
- ANY `empty_body` in non-abstract class → Immediate escalation
- >3 TODO comments in single file → Escalate
- Placeholder in config/secrets → HIGH priority escalation
- LLM judgment "forgotten" with high confidence → Escalate

## Expected Resolution

When this check finds stubs, orchestrator must:
1. Identify which Drop was responsible for that code
2. Review LLM judgment for intent classification
3. For "forgotten" stubs: complete the work or document why deferred
4. For "blocked" stubs: document the blocker and create tracking
5. Update build AAR with stub disposition
