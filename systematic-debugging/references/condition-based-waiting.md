---
created: '2026-02-07'
last_edited: '2026-02-07'
version: 1.0
provenance: systematic-debugging-integration/D1.1
---

# Condition-Based Waiting

## Purpose
Replace arbitrary timeouts with condition polling to create reliable, self-adapting waits that handle variable timing.

## Why Hardcoded Timeouts Fail
- **Too short** - Creates flaky tests and race conditions
- **Too long** - Slows down development and CI pipelines
- **Environment dependent** - What works locally fails in production
- **Load dependent** - Performance varies with system load

## Condition Polling Pattern

Instead of: `sleep(5)` or `setTimeout(5000)`

Use: Poll for the expected condition with a reasonable timeout as fallback

```
while (!condition_met() && elapsed < max_timeout) {
    sleep(poll_interval)
    elapsed += poll_interval
}
if (!condition_met()) throw TimeoutError()
```

## Code Examples

**Bash Pattern:**
```bash
wait_for_service() {
    local timeout=30
    local elapsed=0
    while ! curl -s localhost:8080/health >/dev/null && [ $elapsed -lt $timeout ]; do
        sleep 1
        ((elapsed++))
    done
    [ $elapsed -lt $timeout ] || { echo "Service failed to start"; return 1; }
}
```

**Python Pattern:**
```python
def wait_for_condition(check_fn, timeout=30, poll_interval=0.5):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_fn():
            return True
        time.sleep(poll_interval)
    return False
```

## Anti-Patterns
- **Tight polling loops** - Use backoff or reasonable intervals (0.1s+)
- **No timeout fallback** - Always have a maximum wait time
- **Ignoring failure modes** - Check for error conditions, not just success
- **Inconsistent intervals** - Use exponential backoff for expensive checks

## Best Practices
- Start with short intervals (0.1-0.5s) for fast operations
- Use exponential backoff for expensive checks or remote services
- Log polling attempts for debugging timing issues
- Make timeouts configurable for different environments

Condition-based waiting makes systems robust across varying performance conditions.