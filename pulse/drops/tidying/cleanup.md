---
template_type: hygiene_check
hygiene_phase: tidying
auto_fix: true
auto_fix_scope: safe_removals
judgment_method: hybrid
priority: 5
version: 2.0
---

# Cleanup Hygiene Check

## Scope

Removes development artifacts that shouldn't ship:
- Debug logging (console.log, print statements used for debugging)
- Commented-out code blocks (>3 lines)
- Unused variables
- Dead code paths
- Debugging flags left enabled

## Purpose

These artifacts:
- Pollute logs in production
- Add noise to codebase
- May leak sensitive information
- Indicate incomplete cleanup by Drops

## Commands (Phase 1: Find Candidates)

```bash
BUILD_DIR="N5/builds/${BUILD_SLUG}"
ARTIFACTS_DIR="${BUILD_DIR}/artifacts"

# Debug print statements (Python)
grep -rn "print(" "$ARTIFACTS_DIR" --include="*.py" | grep -v "# keep\|# production\|logger\."

# Debug console statements (JS/TS)
grep -rn "console\.log\|console\.debug\|console\.warn" "$ARTIFACTS_DIR" --include="*.ts" --include="*.js" | grep -v "// keep\|// production"

# Commented-out code blocks (3+ consecutive comment lines that look like code)
grep -Pzo "(#[^\n]*\n){3,}" "$ARTIFACTS_DIR"/*.py 2>/dev/null | grep -E "def |class |import |return |if |for "

# Unused variables (Python - basic detection)
for file in $(find "$ARTIFACTS_DIR" -name "*.py"); do
  python3 -c "
import ast
import sys
with open('$file') as f:
    tree = ast.parse(f.read())
assigned = set()
used = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Name):
        if isinstance(node.ctx, ast.Store):
            assigned.add(node.id)
        elif isinstance(node.ctx, ast.Load):
            used.add(node.id)
unused = assigned - used - {'_', '__'}
if unused:
    print(f'$file: unused: {unused}')
" 2>/dev/null
done

# Debug flags
grep -rn "DEBUG\s*=\s*True\|VERBOSE\s*=\s*True" "$ARTIFACTS_DIR" --include="*.py" --include="*.ts"
```

## Hybrid Approach (Grep → LLM)

**Why hybrid?** Grep/regex is fast at finding candidates, but distinguishing "debug code" from "intentional output" is a *semantic* judgment that requires understanding context.

### Phase 1: Syntactic Discovery (grep)
Run the commands above to generate a candidates list. This is fast and cheap.

### Phase 2: Semantic Judgment (LLM)
For each candidate, use `/zo/ask` to make the judgment call:

```python
import requests
import os

def judge_candidate(file_path, line_num, content, context_lines):
    """Use LLM to judge if this is debug code or intentional."""
    prompt = f"""You are a code hygiene judge. Determine if this line is debug code that should be removed, or intentional output that should stay.

FILE: {file_path}
LINE {line_num}: {content}

SURROUNDING CONTEXT:
{context_lines}

Consider:
1. Is this in a `if __name__ == "__main__":` block? (likely intentional)
2. Does it use a logger object? (intentional logging infrastructure)
3. Does it print user-facing output? (intentional)
4. Does it have markers like "DEBUG:", "TEMP:", variable dumps? (debug)
5. Is it commented with # keep or # production? (intentional)

Respond with JSON:
{"verdict": "remove" | "keep", "confidence": 0.0-1.0, "reason": "..."}
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

### When to Use Each Phase

| Finding Type | Phase 1 (grep) | Phase 2 (LLM) |
|--------------|----------------|---------------|
| `print()` statements | ✅ Find all | ✅ Judge each |
| `console.log` | ✅ Find all | ✅ Judge each |
| Commented code blocks | ✅ Find candidates | ✅ "Is this dead code or documentation?" |
| Unused variables | ✅ AST detection | ❌ Not needed (structural) |
| Debug flags | ✅ Find all | ✅ "Is this config or leftover?" |

### Batch Judgment for Efficiency

For builds with many candidates, batch them:

```python
def batch_judge(candidates, batch_size=10):
    """Judge multiple candidates in one LLM call."""
    prompt = f"""Judge each candidate. For each, respond with verdict and confidence.

CANDIDATES:
{format_candidates(candidates)}

Respond with JSON array:
[{"id": 1, "verdict": "remove"|"keep", "confidence": 0.0-1.0, "reason": "..."}, ...]
"""
    # Single LLM call for batch
    ...
```

## Output Schema

```json
{
  "findings": [
    {
      "type": "debug_print",
      "file": "scripts/main.py",
      "line": 45,
      "content": "print(f\"DEBUG: {data}\")",
      "safe_to_remove": true
    },
    {
      "type": "commented_code",
      "file": "scripts/api.py",
      "start_line": 20,
      "end_line": 28,
      "lines": 9,
      "preview": "# def old_handler(...):\n#     return ...",
      "safe_to_remove": true
    },
    {
      "type": "unused_variable",
      "file": "scripts/utils.py",
      "line": 15,
      "variable": "temp_data",
      "safe_to_remove": true
    },
    {
      "type": "debug_flag",
      "file": "scripts/config.py",
      "line": 8,
      "content": "DEBUG = True",
      "safe_to_remove": false,
      "reason": "May be intentional configuration"
    }
  ],
  "auto_fixable": [
    {
      "type": "debug_print",
      "file": "scripts/main.py",
      "line": 45,
      "fix": "Remove line"
    },
    {
      "type": "commented_code",
      "file": "scripts/api.py",
      "start_line": 20,
      "end_line": 28,
      "fix": "Remove lines 20-28"
    }
  ],
  "requires_review": [
    {
      "type": "debug_flag",
      "severity": "medium",
      "issue": "DEBUG flag set to True",
      "recommendation": "Verify this should be False for production"
    }
  ],
  "summary": {
    "total_findings": 12,
    "auto_fixed": 8,
    "requires_review": 4,
    "lines_removed": 23
  }
}
```

## Auto-Fix Rules

**auto_fix: true** (for safe removals)

Safe to auto-fix:
- `debug_print` → Remove line (unless marked `# keep` or `# production`)
- `console.log` → Remove line (unless marked `// keep` or `// production`)
- `commented_code` → Remove block (>3 lines of commented code-like content)
- `unused_variable` → Remove assignment (only if never read)

Do NOT auto-fix:
- `debug_flag` → May be intentional configuration
- Print statements in `if __name__ == "__main__":` blocks
- Logging to actual logger objects (`logger.debug()`, etc.)
- Variables starting with `_` (intentionally unused)
- Comments that look like documentation, not code

## Auto-Fix Implementation

```python
def auto_fix_debug_cleanup(file_path, findings):
    """Remove debug artifacts from file."""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Sort by line number descending to preserve indices
    to_remove = sorted(
        [f for f in findings if f['safe_to_remove']],
        key=lambda x: x.get('end_line', x['line']),
        reverse=True
    )
    
    for finding in to_remove:
        if 'end_line' in finding:
            # Block removal
            del lines[finding['start_line']-1:finding['end_line']]
        else:
            # Single line removal
            del lines[finding['line']-1]
    
    with open(file_path, 'w') as f:
        f.writelines(lines)
    
    return len(to_remove)
```

## Escalation Triggers

- DEBUG/VERBOSE flag enabled → Escalate for confirmation
- >20 debug statements → Escalate (may indicate logging strategy issue)
- Unused variable in function signature → Escalate (interface issue)
- Commented code with TODO → Escalate (deferred work)

## Preservation Markers

Lines with these markers are NEVER removed:
- `# keep` / `// keep`
- `# production` / `// production`
- `# intentional` / `// intentional`
- `# noqa`
