---
created: 2026-02-01
last_edited: 2026-02-01
version: 1.0
provenance: con_qhrDdDyEQsQq6PCA
---

# Meeting Processing Quality Harness Checks

Comprehensive quality validation framework for the meeting ingestion pipeline. All checks must pass before advancing to the next processing stage.

## Overview

The quality harness validates data at 4 critical pipeline stages:
1. **Pre-processing**: Raw transcript validation
2. **Identification**: Participant and calendar matching validation
3. **Block Generation**: Intelligence block output validation
4. **Post-processing**: Pipeline completion validation

## Pre-processing Checks

### Transcript Validation

**Check: `transcript_length`**
- **Purpose**: Ensure transcript contains sufficient content for analysis
- **Pass Threshold**: ≥ 300 characters of actual content (excluding metadata, timestamps)
- **Fail Threshold**: < 300 characters
- **Implementation**: Strip markdown headers, timestamps, speaker labels, count remaining text
- **HITL Escalation**: < 100 characters (too short for any meaningful processing)

**Check: `transcript_format`**
- **Purpose**: Validate transcript is in expected format and encoding
- **Pass Threshold**: Valid UTF-8, readable text, contains speaker indicators or dialogue
- **Fail Threshold**: Binary data, encoding errors, no recognizable speech patterns
- **Implementation**: 
  - Verify UTF-8 decoding without errors
  - Check for speaker patterns (e.g., "Speaker:", "Name:", timestamps)
  - Validate not pure metadata/system output
- **HITL Escalation**: Encoding corruption, suspected non-transcript content

**Check: `transcript_encoding`**
- **Purpose**: Ensure proper character encoding for downstream processing
- **Pass Threshold**: UTF-8 compliant, no encoding artifacts
- **Fail Threshold**: Encoding errors, corrupted characters
- **Implementation**: Attempt UTF-8 decode, check for replacement characters (�)
- **HITL Escalation**: Non-UTF-8 encoding requiring manual conversion

**Check: `meeting_duration_consistency`**
- **Purpose**: Validate transcript length matches expected meeting duration
- **Pass Threshold**: Transcript word count within 50% of expected based on duration
  - Expected: ~150 words per minute of meeting time
  - Range: 75-300 words per minute (accounting for silence, overlaps)
- **Fail Threshold**: Outside expected range suggests truncated/corrupted transcript
- **Implementation**: Extract duration from filename/metadata, count words, compare
- **HITL Escalation**: Ratio < 0.3 or > 4.0 (suspicious length discrepancy)

## Identification Checks

### Participant Identification

**Check: `participant_confidence`**
- **Purpose**: Ensure participants are identified with sufficient confidence
- **Pass Threshold**: Overall participant confidence ≥ 0.7
- **Fail Threshold**: Overall confidence < 0.7
- **Implementation**: Check `participants.confidence` field from identification process
- **Retry Logic**: Re-run identification with relaxed matching parameters
- **HITL Escalation**: Confidence < 0.4 (manual participant verification needed)

**Check: `host_identified`**
- **Purpose**: Validate meeting host is identified (required for block context)
- **Pass Threshold**: At least one participant has `role: "host"`
- **Fail Threshold**: No host identified
- **Implementation**: Check `participants.identified` array for host role
- **Retry Logic**: Attempt heuristic host detection (V in external meetings, most active speaker)
- **HITL Escalation**: Multiple potential hosts or no clear host pattern

**Check: `external_participant_verification`**
- **Purpose**: For external meetings, ensure external participants are properly identified
- **Pass Threshold**: 
  - External meetings: ≥ 1 non-V participant identified
  - Internal meetings: All participants should be known internal contacts
- **Fail Threshold**: External meeting with only V identified, or internal with unknown participants
- **Implementation**: 
  - Check meeting type and participant roster
  - Verify external participants have names (not just "Speaker 1")
- **Retry Logic**: Use alternative name extraction methods, check against CRM
- **HITL Escalation**: Critical external stakeholder unidentified

### Calendar Matching

**Check: `calendar_match_score`**
- **Purpose**: Validate transcript matches a calendar event for proper context
- **Pass Threshold**: Match confidence ≥ 0.6 OR manual override
- **Fail Threshold**: Match confidence < 0.6 AND no manual override
- **Implementation**: Check `calendar_match.confidence` field
- **Retry Logic**: 
  - Try title-only matching if timestamp match failed
  - Expand time window for matching (±30 minutes)
- **HITL Escalation**: Confidence < 0.3 (manual calendar association needed)

**Check: `meeting_type_consistency`**
- **Purpose**: Ensure meeting type aligns with participants and calendar event
- **Pass Threshold**: Meeting type correctly classified based on participant roster
- **Fail Threshold**: Type mismatch (e.g., external marked as internal with external participants)
- **Implementation**: 
  - Validate external meetings have non-internal participants
  - Validate internal meetings have only known internal contacts
- **Retry Logic**: Re-run type detection with updated participant information
- **HITL Escalation**: Ambiguous participant roster requiring manual classification

## Block Generation Checks

### Output Length Validation

**Check: `block_output_length`**
- **Purpose**: Ensure generated blocks contain sufficient content
- **Pass Threshold**: 
  - B01 (Detailed Recap): ≥ 200 words
  - B02-B08: ≥ 50 words
  - B25-B28: ≥ 30 words
  - B40+ (Internal): ≥ 40 words
- **Fail Threshold**: Below minimum thresholds
- **Implementation**: Count words in generated markdown, exclude YAML frontmatter
- **Retry Logic**: Regenerate with enhanced prompts emphasizing detail
- **HITL Escalation**: Multiple regeneration failures, suggesting insufficient transcript content

**Check: `block_format_compliance`**
- **Purpose**: Validate blocks follow expected markdown structure
- **Pass Threshold**: 
  - Contains valid YAML frontmatter
  - Proper markdown headers
  - Structured content (not just paragraph text)
- **Fail Threshold**: Missing frontmatter, malformed structure, plain text output
- **Implementation**: Parse YAML frontmatter, validate markdown structure
- **Retry Logic**: Regenerate with explicit formatting instructions
- **HITL Escalation**: Consistent formatting failures indicating prompt issues

**Check: `no_hallucination_markers`**
- **Purpose**: Detect AI hallucination or fabricated content
- **Pass Threshold**: No obvious hallucination markers detected
- **Fail Threshold**: Contains hallucination indicators:
  - "I cannot access...", "As an AI..."
  - Fabricated details not in transcript
  - Contradictory information across blocks
- **Implementation**: 
  - Scan for meta-commentary phrases
  - Cross-reference claims against transcript content
  - Check for impossible details (future dates, non-participants)
- **Retry Logic**: Regenerate with strict "transcript only" instructions
- **HITL Escalation**: Persistent hallucination patterns requiring prompt revision

**Check: `block_content_accuracy`**
- **Purpose**: Validate block content accurately reflects transcript
- **Pass Threshold**: Key facts and decisions verifiable in source transcript
- **Fail Threshold**: Contains information not found in transcript
- **Implementation**: 
  - Sample key claims from blocks
  - Verify presence in transcript using fuzzy matching
  - Flag blocks with >20% unverifiable content
- **Retry Logic**: Regenerate with "quote directly from transcript" emphasis
- **HITL Escalation**: Systematic accuracy issues across multiple blocks

## Post-processing Checks

### Completion Validation

**Check: `all_requested_blocks_generated`**
- **Purpose**: Ensure all blocks in the manifest were successfully generated
- **Pass Threshold**: `blocks.generated` contains all items from `blocks.requested`
- **Fail Threshold**: Missing blocks from requested set
- **Implementation**: Compare arrays in manifest JSON
- **Retry Logic**: Regenerate specific missing blocks
- **HITL Escalation**: Blocks consistently failing after 3 retry attempts

**Check: `no_processing_errors`**
- **Purpose**: Validate pipeline completed without errors
- **Pass Threshold**: No errors in processing logs, all files created successfully
- **Fail Threshold**: Errors in logs, missing expected files
- **Implementation**: Check processing logs, verify file existence
- **Retry Logic**: Reprocess from last successful stage
- **HITL Escalation**: System errors requiring manual intervention

**Check: `manifest_completeness`**
- **Purpose**: Ensure manifest contains all required metadata
- **Pass Threshold**: Manifest validates against v3 schema
- **Fail Threshold**: Schema validation errors
- **Implementation**: Validate against `manifest-v3.schema.json`
- **Retry Logic**: Regenerate manifest with corrected data
- **HITL Escalation**: Persistent schema violations indicating data corruption

**Check: `status_consistency`**
- **Purpose**: Validate status transitions follow expected pipeline progression
- **Pass Threshold**: Status history shows logical progression (raw → ingested → identified → gated → processed)
- **Fail Threshold**: Missing status transitions, backwards progression
- **Implementation**: Validate status_history array for proper sequence
- **Retry Logic**: Correct status history based on actual processing state
- **HITL Escalation**: Status inconsistencies indicating pipeline bugs

## Retry Logic Framework

### Automatic Retry Conditions
- **Max Attempts**: 3 per check type
- **Retry Delays**: 30s, 60s, 120s (exponential backoff)
- **Retry Triggers**: 
  - Temporary API failures
  - Resource availability issues
  - Confidence scores in "warning" range (0.4-0.7)

### Retry Strategies by Check Type
1. **Transcript Issues**: Re-process with different encoding/parsing
2. **Identification Issues**: Try alternative matching algorithms
3. **Block Generation Issues**: Regenerate with modified prompts
4. **System Issues**: Retry after resource availability

### No-Retry Conditions
- Hard validation failures (corrupt files, schema violations)
- Confidence scores < 0.3 (require human judgment)
- Hallucination detection (indicates prompt/model issues)
- 3 consecutive failures of same check type

## HITL Escalation Framework

### Escalation Triggers

**Immediate Escalation (P0)**
- Encoding corruption or unreadable transcripts
- System errors preventing pipeline progression
- Critical external stakeholder identification failures
- Persistent hallucination in generated blocks

**Standard Escalation (P1)**
- Participant confidence < 0.4
- Calendar match confidence < 0.3
- Missing critical blocks after 3 retry attempts
- Meeting type ambiguity with external participants

**Batch Review (P2)**
- Multiple minor validation failures
- Borderline confidence scores across multiple checks
- Format compliance issues requiring prompt tuning

### Escalation Process
1. **Queue Assignment**: Add to `scripts/review/meetings/` with priority level
2. **Context Packaging**: Include transcript, manifest, failed check details
3. **Notification**: Alert via configured channel (email/SMS) for P0/P1
4. **Resolution Tracking**: Update manifest with HITL resolution details

### HITL Review Queue Structure
```
scripts/review/meetings/
├── YYYY-MM-DD_priority-escalations_batch-001.md
├── meeting-specific/
│   ├── YYYY-MM-DD_Meeting-Name_identification-issue.md
│   └── YYYY-MM-DD_Other-Meeting_quality-failure.md
└── batch-reviews/
    └── YYYY-MM-DD_minor-issues_batch-001.md
```

## Implementation Integration

### Quality Gate in Manifest
The `quality_gate` object in the manifest tracks overall quality validation:

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
    "score": 0.85
  }
}
```

### Check Execution Order
1. Pre-processing checks (block pipeline progression)
2. Identification checks (block quality gate)
3. Block generation checks (per-block validation)
4. Post-processing checks (pipeline completion)

### Integration with Processing Pipeline
- **Stage Gates**: Each pipeline stage waits for quality validation before proceeding
- **Manifest Updates**: Quality check results update manifest in real-time
- **Error Propagation**: Failed checks prevent status advancement
- **Retry Coordination**: Quality harness manages retry attempts across pipeline stages

## Metrics and Monitoring

### Quality Metrics
- **Pass Rate**: Percentage of meetings passing all quality checks
- **Check-Specific Rates**: Pass rates for individual check types
- **HITL Escalation Rate**: Percentage requiring human intervention
- **Retry Effectiveness**: Success rate of retry attempts

### Performance Targets
- Overall pass rate: ≥ 90%
- HITL escalation rate: ≤ 5%
- Average processing time: ≤ 10 minutes per meeting
- Check execution time: ≤ 30 seconds per check

### Alerting Thresholds
- Pass rate drops below 85%: Alert
- HITL queue exceeds 10 items: Alert
- Check execution time exceeds 60 seconds: Warning
- 3+ consecutive failures same check type: Alert

## Configuration

### Check Thresholds
All thresholds defined in this document should be configurable via:
```
scripts/config/quality-harness.yaml
```

### Environment Variables
- `QUALITY_CHECKS_ENABLED`: Enable/disable quality validation
- `QUALITY_RETRY_MAX_ATTEMPTS`: Maximum retry attempts (default: 3)
- `QUALITY_HITL_ESCALATION`: Enable HITL escalation (default: true)
- `QUALITY_METRICS_LOGGING`: Enable metrics collection (default: true)

This framework ensures systematic quality validation while maintaining processing efficiency and providing clear escalation paths for edge cases requiring human judgment.