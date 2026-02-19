---
template_type: hygiene_check
hygiene_phase: tidying
auto_fix: false
priority: 1
---

# Integration Test Hygiene Check

## Scope

Validates cross-component behavior using INTEGRATION_TESTS.json if present in the build. Ensures that components work together correctly after assembly.

## Prerequisites

- Build must have a valid `INTEGRATION_TESTS.json` in `N5/builds/<slug>/` or `artifacts/`
- All code Drops must be complete

## Commands

```bash
# Check for integration tests definition
BUILD_DIR="N5/builds/${BUILD_SLUG}"
TEST_FILE="${BUILD_DIR}/INTEGRATION_TESTS.json"

if [ -f "$TEST_FILE" ]; then
  python3 Skills/pulse/scripts/pulse_integration_test.py run "$BUILD_SLUG"
else
  echo '{"findings": [], "skipped": true, "reason": "No INTEGRATION_TESTS.json found"}'
fi
```

## Test File Format

```json
{
  "tests": [
    {
      "id": "T1",
      "name": "Component A calls Component B",
      "type": "import_chain",
      "source": "scripts/a.py",
      "target": "scripts/b.py",
      "expected": "function_x is callable"
    },
    {
      "id": "T2", 
      "name": "CLI end-to-end",
      "type": "cli",
      "command": "python3 scripts/main.py --help",
      "expected_exit": 0,
      "expected_output_contains": "usage:"
    }
  ]
}
```

## Output Schema

```json
{
  "findings": [
    {
      "test_id": "T1",
      "test_name": "string",
      "passed": false,
      "error": "string",
      "file_path": "string"
    }
  ],
  "auto_fixable": [],
  "requires_review": [
    {
      "test_id": "T1",
      "severity": "high",
      "issue": "Integration test failed",
      "recommendation": "Review component interfaces"
    }
  ],
  "summary": {
    "total": 5,
    "passed": 3,
    "failed": 2,
    "skipped": 0
  }
}
```

## Auto-Fix Rules

**auto_fix: false**

Integration test failures indicate real problems with component interactions. These require human review to determine:
- Whether the test expectation is wrong
- Whether the implementation has a bug
- Whether an interface changed and consumers need updating

## Escalation Triggers

- Any test failure → Escalate to orchestrator
- Missing test file (when expected) → Warning in deposit
- Test infrastructure error → Escalate with error details

## Notes

- This hygiene check is report-only
- Results feed into build AAR
- Failed integration tests should block build completion
