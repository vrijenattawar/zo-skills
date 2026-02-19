---
template_type: hygiene_check
hygiene_phase: tidying
auto_fix: partial
auto_fix_scope: suggest_only
priority: 4
---

# Deduplication Hygiene Check

## Scope

Identifies code and file duplication that should be refactored:
- Duplicate code blocks (>10 lines identical or near-identical)
- Redundant files (same content, different names)
- Copy-paste patterns across Drops
- Similar function implementations

## Purpose

Duplication indicates:
- Drops worked in isolation without coordination
- Missing shared utilities
- Opportunities for abstraction
- Potential maintenance burden

## Commands

```bash
BUILD_DIR="N5/builds/${BUILD_SLUG}"
ARTIFACTS_DIR="${BUILD_DIR}/artifacts"

# File-level duplicates (exact match)
find "$ARTIFACTS_DIR" -type f \( -name "*.py" -o -name "*.ts" -o -name "*.js" \) -exec md5sum {} + | \
  sort | uniq -w32 -d

# Code block duplicates using jscpd (if available)
if command -v jscpd &> /dev/null; then
  jscpd "$ARTIFACTS_DIR" --min-lines 10 --reporters json --output /tmp/jscpd-report.json
fi

# Simple line-based duplicate detection
for file in $(find "$ARTIFACTS_DIR" -name "*.py"); do
  awk 'NR==FNR{a[NR]=$0;next} {for(i=1;i<=length(a)-10;i++){match=1;for(j=0;j<10;j++)if(a[i+j]!=$(FNR+j-1))match=0;if(match)print FILENAME":"FNR" matches "ARGV[1]":"i}}' "$file" $(find "$ARTIFACTS_DIR" -name "*.py" ! -path "$file")
done 2>/dev/null

# Function signature duplicates
grep -rh "^def \|^async def \|^function " "$ARTIFACTS_DIR" --include="*.py" --include="*.ts" | \
  sort | uniq -c | sort -rn | awk '$1>1'
```

## Output Schema

```json
{
  "findings": [
    {
      "type": "duplicate_file",
      "files": ["scripts/utils.py", "scripts/helpers.py"],
      "similarity": 100,
      "recommendation": "Consolidate into single module"
    },
    {
      "type": "duplicate_block",
      "locations": [
        {"file": "scripts/a.py", "start_line": 45, "end_line": 60},
        {"file": "scripts/b.py", "start_line": 20, "end_line": 35}
      ],
      "lines": 16,
      "similarity": 95,
      "recommendation": "Extract to shared function"
    },
    {
      "type": "similar_functions",
      "functions": [
        {"file": "scripts/a.py", "name": "validate_input", "line": 10},
        {"file": "scripts/b.py", "name": "check_input", "line": 25}
      ],
      "similarity": 80,
      "recommendation": "Review for consolidation opportunity"
    }
  ],
  "auto_fixable": [],
  "requires_review": [
    {
      "type": "duplicate_block",
      "severity": "medium",
      "issue": "16 lines duplicated across 2 files",
      "suggested_refactor": "Create shared utility function"
    }
  ],
  "summary": {
    "total_duplications": 5,
    "duplicate_files": 1,
    "duplicate_blocks": 3,
    "similar_functions": 1,
    "estimated_lines_saveable": 48
  }
}
```

## Auto-Fix Rules

**auto_fix: partial** (suggest only, never auto-apply)

This check identifies duplication but does NOT auto-fix because:
- Requires design decisions about abstraction location
- May need new shared module creation
- Could break imports across files
- Naming decisions require human judgment

What the check CAN do:
- Generate refactoring suggestions
- Create draft PR description for dedup work
- Estimate effort and lines saved

## Suggested Fix Format

```json
{
  "suggested_fix": {
    "action": "extract_function",
    "new_file": "scripts/shared/validators.py",
    "new_function": "validate_and_normalize",
    "affected_files": ["scripts/a.py", "scripts/b.py"],
    "import_changes": [
      "scripts/a.py: from shared.validators import validate_and_normalize",
      "scripts/b.py: from shared.validators import validate_and_normalize"
    ],
    "lines_removed": 32,
    "lines_added": 18,
    "net_reduction": 14
  }
}
```

## Escalation Triggers

- >50 lines duplicated → Escalate for refactoring decision
- Identical file content → Escalate (likely error)
- >3 similar functions → Escalate for abstraction review
- Duplication across >3 files → Escalate (systemic issue)

## Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| Block size | >10 lines | Flag |
| Similarity | >80% | Flag |
| Cross-file instances | >2 | Escalate |
| Total duplicate lines | >100 | Escalate for dedicated cleanup |
