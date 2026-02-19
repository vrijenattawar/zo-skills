---
created: '2026-02-07'
last_edited: '2026-02-07'
version: 1.0
provenance: systematic-debugging-integration/D1.1
---

# Root Cause Tracing

## Purpose
Trace bugs backward through the call stack to find the original trigger, rather than treating symptoms.

## When to Use
- Error manifests deep in call stack, far from actual problem
- Bad values surface in unexpected places
- Intermittent failures that seem to come from nowhere
- Complex data flows where corruption could happen at multiple points

## The Backward Tracing Technique

1. **Start at the error point** - Note exact values, state, and context
2. **Identify immediate inputs** - What data/parameters led to this state?
3. **Trace each input backward** - Where did each input come from?
4. **Look for transformation points** - Where could values have been modified?
5. **Check assumptions** - Verify data types, ranges, null handling at each step
6. **Follow the earliest divergence** - When did actual behavior differ from expected?

## Example Walkthrough

```
Error: "Cannot read property 'name' of undefined"
↓ Trace backward
user.profile is undefined
↓ Where did user come from?
getUserById(userId) returned null
↓ Where did userId come from?
parseInt(req.params.id) returned NaN
↓ Root cause found
URL parameter contains non-numeric value
```

## Common Mistakes
- **Stopping too early** - Fixing the symptom instead of the cause
- **Assuming instead of checking** - "This should never be null" without verification
- **Ignoring data flow** - Not tracing how values move through the system
- **Missing edge cases** - Only testing happy path scenarios

The goal is finding where the problem *started*, not where it *appeared*.