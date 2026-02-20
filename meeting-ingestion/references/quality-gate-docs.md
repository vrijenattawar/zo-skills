---
created: 2026-02-01
last_edited: 2026-02-01
version: 1.0
provenance: con_9DFaOUlVxQNVwbTG
---

# Quality Gate Documentation

The `quality_gate.py` script validates meeting readiness before block generation using a comprehensive 4-stage quality framework. It sits between the 'identified' and 'gated' statuses in the processing pipeline, ensuring only high-quality meetings proceed to block generation.

## Purpose

The quality gate performs systematic validation across 4 pipeline stages:
1. **Pre-processing**: Raw transcript validation (length, format, encoding, duration consistency)
2. **Identification**: Participant and calendar matching validation
3. **Block Generation**: Intelligence block output validation (not implemented yet - future)
4. **Post-processing**: Pipeline completion validation (not implemented yet - future)

## Usage

```bash
# Validate a meeting (uses manifest.json + transcript.md)
python3 Skills/meeting-ingestion/scripts/quality_gate.py /path/to/manifest.json --transcript /path/to/transcript.md

# Verbose output showing all check details
python3 Skills/meeting-ingestion/scripts/quality_gate.py /path/to/manifest.json --transcript /path/to/transcript.md --verbose

# JSON output for programmatic use
python3 Skills/meeting-ingestion/scripts/quality_gate.py /path/to/manifest.json --transcript /path/to/transcript.md --json

# Use custom configuration
python3 Skills/meeting-ingestion/scripts/quality_gate.py /path/to/manifest.json --transcript /path/to/transcript.md --config /path/to/quality-config.yaml
```

## Quality Checks

The quality gate implements 8 specific checks with measurable pass/fail thresholds:

### Pre-processing Checks
- **`transcript_length`**: Ensures ≥300 characters of content (strips metadata/timestamps)
- **`transcript_format`**: Validates UTF-8 encoding and speaker patterns
- **`meeting_duration_consistency`**: Checks word count vs expected duration (75-300 words/min)

### Identification Checks  
- **`participant_confidence`**: Requires overall confidence ≥0.7 for participant identification
- **`host_identified`**: Validates at least one participant has `role: "host"`
- **`external_participant_verification`**: For external meetings, ensures non-V participants identified
- **`calendar_match_score`**: Validates calendar event matching confidence ≥0.6
- **`meeting_type_consistency`**: Checks meeting type aligns with participant roster

## Scoring & Thresholds

- **Overall threshold**: 0.8 (configurable)
- **Individual check thresholds**: Vary by check type (0.6-1.0)
- **HITL escalation thresholds**: Confidence <0.4 or critical failures
- **Pass condition**: Overall score ≥0.8 AND no critical failures AND no HITL escalations

## HITL Escalation

Failed checks automatically create HITL queue items in `scripts/review/meetings/hitl-queue.jsonl`:

**Immediate Escalation (P0)**:
- Encoding corruption or unreadable transcripts
- Very low participant confidence (<0.4)
- Critical external stakeholder identification failures

**Standard Escalation (P1)**:
- Low calendar match confidence (<0.3)
- Meeting type ambiguity with external participants
- Suspicious transcript length discrepancies

## Pipeline Integration

The quality gate updates the manifest's `quality_gate` object:

```json
{
  "quality_gate": {
    "passed": true,
    "checks": {
      "has_transcript": true,
      "participants_identified": true,
      "meeting_type_determined": true,
      "no_hitl_pending": true
    },
    "score": 0.85,
    "executed_at": "2026-02-01T20:10:00Z",
    "check_results": [...]
  }
}
```

On success, the meeting status advances to `"gated"` with timestamp.

## Configuration

Optional YAML config at `scripts/config/quality-harness.yaml`:

```yaml
enabled: true
overall_threshold: 0.8
retry_max_attempts: 3
hitl_escalation: true
checks_enabled:
  transcript_length: true
  participant_confidence: true
  # ... other checks
```

## Integration Example

```python
from quality_gate import QualityGate

# Initialize with config
gate = QualityGate(config_path=Path("scripts/config/quality-harness.yaml"))

# Execute checks
results = gate.execute(
    manifest_path=Path("meeting/manifest.json"),
    transcript_path=Path("meeting/transcript.md")
)

if results["passed"]:
    print(f"✓ Quality gate passed (score: {results['score']:.3f})")
    # Proceed to block generation
else:
    print(f"✗ Quality gate failed - {len(results['hitl_escalations'])} escalations")
    # Handle HITL items
```