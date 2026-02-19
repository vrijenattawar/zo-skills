---
template_type: hygiene_check
hygiene_phase: tidying
auto_fix: true
auto_fix_scope: unused_imports_only
priority: 2
---

# Reference Check Hygiene Check

## Scope

Finds broken references across the codebase:
- Broken imports (Python, TypeScript)
- Dead file references in configs
- Invalid paths in documentation
- Orphaned file references

## Prerequisites

- Build artifacts directory identified
- pylint and/or tsc available for respective languages

## Commands

```bash
BUILD_DIR="N5/builds/${BUILD_SLUG}"
ARTIFACTS_DIR="${BUILD_DIR}/artifacts"

# Python: Check imports
find "$ARTIFACTS_DIR" -name "*.py" -exec pylint --disable=all --enable=E0401,E0611 {} + 2>/dev/null | grep -E "^E"

# TypeScript: Check imports  
if command -v tsc &> /dev/null; then
  find "$ARTIFACTS_DIR" -name "*.ts" -exec tsc --noEmit {} + 2>&1 | grep -E "Cannot find|not found"
fi

# Config file references
for config in $(find "$ARTIFACTS_DIR" -name "*.json" -o -name "*.yaml" -o -name "*.yml"); do
  # Extract path-like strings and verify they exist
  grep -oE '"[^"]+\.(py|ts|js|md|json)"' "$config" | tr -d '"' | while read -r ref; do
    if [ ! -f "$ARTIFACTS_DIR/$ref" ] && [ ! -f "$ref" ]; then
      echo "DEAD_REF:$config:$ref"
    fi
  done
done
```

## Output Schema

```json
{
  "findings": [
    {
      "type": "broken_import",
      "file": "scripts/main.py",
      "line": 5,
      "import_path": "utils.nonexistent",
      "error": "No module named 'utils.nonexistent'"
    },
    {
      "type": "dead_reference",
      "source_file": "config.json",
      "referenced_path": "old_script.py",
      "exists": false
    },
    {
      "type": "unused_import",
      "file": "scripts/main.py",
      "line": 3,
      "import_name": "os"
    }
  ],
  "auto_fixable": [
    {
      "type": "unused_import",
      "file": "scripts/main.py",
      "line": 3,
      "fix": "Remove line: import os"
    }
  ],
  "requires_review": [
    {
      "type": "broken_import",
      "file": "scripts/main.py",
      "severity": "high",
      "issue": "Module not found",
      "recommendation": "Install missing package or fix import path"
    }
  ]
}
```

## Auto-Fix Rules

**auto_fix: true** (for unused imports only)

Safe to auto-fix:
- `unused_import` → Remove the import line
- Only when import is confirmed unused by static analysis
- Preserve import if it has side effects (flagged by comments)

Escalate (do not auto-fix):
- `broken_import` → Requires investigation
- `dead_reference` → May need config update or file restoration
- Any import with `# noqa` or `# side-effect` comment

## Auto-Fix Implementation

```python
def auto_fix_unused_import(file_path, line_number):
    """Remove a single unused import line."""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Safety: only remove if line is pure import
    line = lines[line_number - 1]
    if line.strip().startswith('import ') or line.strip().startswith('from '):
        if '# noqa' not in line and '# side-effect' not in line:
            del lines[line_number - 1]
            with open(file_path, 'w') as f:
                f.writelines(lines)
            return True
    return False
```

## Escalation Triggers

- Any broken_import → Escalate (blocks runtime)
- >5 dead references → Escalate (suggests structural issue)
- Import resolution errors → Escalate with dependency info
