---
created: '2026-02-07'
last_edited: '2026-02-07'
version: 1.0
provenance: systematic-debugging-integration/D1.1
---

# Defense in Depth

## Purpose
Add validation and safeguards at multiple layers after finding the root cause, creating resilient systems that fail gracefully.

## Why Single-Layer Fixes Are Fragile
- Root cause fixes can be bypassed by new code paths
- Edge cases emerge that weren't considered in the original fix
- Dependencies change behavior over time
- Human error introduces new vulnerabilities

## The Multi-Layer Validation Pattern

**Layer 1: Input Validation**
- Sanitize and validate at entry points
- Type checking, range validation, format verification

**Layer 2: Business Logic Guards**
- Validate assumptions within core logic
- Check preconditions before operations
- Assert postconditions after operations

**Layer 3: Data Layer Constraints**
- Database constraints and triggers
- Schema enforcement
- Referential integrity

**Layer 4: Monitoring & Alerting**
- Log anomalies for investigation
- Circuit breakers for cascading failures
- Health checks and automated recovery

## Example Implementation

```
// Layer 1: API validation
if (!isValidEmail(email)) throw new ValidationError()

// Layer 2: Business logic
if (user.isBlocked()) throw new AccessError()

// Layer 3: Database constraint
CONSTRAINT email_unique UNIQUE (email)

// Layer 4: Monitoring
logger.warn('Suspicious login pattern detected')
```

## When NOT to Use
- **Simple, isolated functions** - Don't over-engineer basic utilities
- **Performance-critical paths** - Balance safety with speed requirements
- **Prototype/experimental code** - Focus on proving concepts first

Defense in depth prevents single points of failure and makes systems self-healing.