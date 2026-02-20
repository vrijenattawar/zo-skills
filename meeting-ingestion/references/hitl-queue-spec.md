---
created: 2026-02-01
last_edited: 2026-02-01
version: 1.0
provenance: con_Fh23yPkleoCF45kZ
---

# HITL Queue Specification

## Overview

The Human-In-The-Loop (HITL) queue is a JSON Lines file that stores meeting processing tasks requiring V's attention. Items are added when automated processing cannot complete without human input.

## Queue Location

`scripts/review/meetings/hitl-queue.jsonl`

## Queue Item Schema

```json
{
  "id": "string",           // Format: "HITL-{timestamp}-{counter}"
  "meeting_id": "string",   // Meeting ID following convention: YYYY-MM-DD_Participant-Name
  "created_at": "string",   // ISO 8601 timestamp
  "reason": "string",       // Reason code (see below)
  "context": "object",      // Context data specific to reason
  "status": "string",       // "pending" | "resolved" | "dismissed"
  "resolved_by": "string",  // "sms" | "manual" | null
  "resolved_at": "string",  // ISO 8601 timestamp or null
  "resolution": "object"    // Resolution data or null
}
```

## Reason Types

### `unidentified_participant`
**Trigger**: Speaker identification fails or confidence is too low
**Context Schema**:
```json
{
  "transcript_excerpt": "string",      // Sample text from unknown speaker
  "known_participants": ["string"],    // List of identified participants
  "unknown_speakers": ["string"],      // List of speaker labels needing identification
  "confidence_scores": "object"        // Speaker identification confidence
}
```

### `unclear_meeting_topic`
**Trigger**: Meeting topic extraction fails or is ambiguous
**Context Schema**:
```json
{
  "transcript_excerpt": "string",      // Key portions of transcript
  "extracted_topics": ["string"],      // Candidate topics found
  "confidence": "number"               // Topic extraction confidence (0-1)
}
```

### `low_transcript_quality`
**Trigger**: Transcript quality below threshold
**Context Schema**:
```json
{
  "quality_score": "number",          // Overall quality score (0-1)
  "issues": ["string"],               // List of quality issues
  "transcript_excerpt": "string",     // Sample of problematic text
  "suggested_action": "string"        // "manual_review" | "reprocess" | "skip"
}
```

### `duplicate_detection_uncertainty`
**Trigger**: Potential duplicate meeting but not certain
**Context Schema**:
```json
{
  "candidate_duplicates": ["string"], // Meeting IDs of potential duplicates
  "similarity_scores": "object",      // Similarity metrics
  "date_range": "string",             // Date range of candidates
  "key_differences": ["string"]       // Notable differences found
}
```

### `sensitive_content_detected`
**Trigger**: Potential sensitive information requires review
**Context Schema**:
```json
{
  "content_type": "string",           // "financial" | "personal" | "confidential"
  "locations": ["object"],            // Where sensitive content was found
  "confidence": "number",             // Detection confidence (0-1)
  "suggested_redaction": "boolean"    // Whether redaction is recommended
}
```

### `processing_error`
**Trigger**: Unexpected error during processing
**Context Schema**:
```json
{
  "error_type": "string",            // Error classification
  "error_message": "string",         // Full error message
  "processing_stage": "string",      // Where error occurred
  "retry_count": "number",           // Number of retry attempts
  "stack_trace": "string"            // Technical details (if available)
}
```

## SMS Notification Triggers

### Immediate Notifications
- `unidentified_participant` with >2 unknown speakers
- `sensitive_content_detected` with confidence >0.8
- `processing_error` after 3 failed retries

### Batched Notifications (every 2 hours during business hours)
- `unclear_meeting_topic`
- `low_transcript_quality` 
- `duplicate_detection_uncertainty`
- `unidentified_participant` with ≤2 unknown speakers

### No Notifications
- `processing_error` with retry_count <3 (auto-retry first)

## SMS Response Format

V responds to SMS notifications with simple commands:

### For `unidentified_participant`:
- `Speaker 2 = John Smith` - Identify speaker
- `Skip unknown speakers` - Proceed without identification
- `Manual review needed` - Mark for full manual review

### For `unclear_meeting_topic`:
- `Topic: Project Planning` - Set explicit topic
- `Auto-detect topic` - Use best automatic guess
- `Skip topic detection` - Proceed without topic

### For `low_transcript_quality`:
- `Reprocess audio` - Attempt reprocessing
- `Accept quality` - Proceed despite quality issues
- `Manual transcription` - Mark for human transcription

### For `duplicate_detection_uncertainty`:
- `Keep both` - Process as separate meetings
- `Merge with YYYY-MM-DD_Name` - Merge with specified meeting
- `Delete duplicate` - Remove current meeting

### For `sensitive_content_detected`:
- `Redact sensitive` - Apply automatic redaction
- `Keep content` - Proceed without redaction
- `Manual review` - Mark for detailed review

### For `processing_error`:
- `Retry processing` - Attempt processing again
- `Skip meeting` - Mark as unprocessable
- `Debug needed` - Escalate to technical review

## Resolution Processing

SMS responses are parsed and converted to resolution objects:

```json
{
  "action": "string",      // Parsed action type
  "parameters": "object",  // Action-specific parameters
  "raw_response": "string" // Original SMS text
}
```

## HITL CLI Commands

### Queue Management
```bash
# List pending items
python3 Skills/meeting-ingestion/scripts/hitl.py list [--status pending|resolved|dismissed]

# Show specific item
python3 Skills/meeting-ingestion/scripts/hitl.py show <hitl-id>

# Mark as resolved manually
python3 Skills/meeting-ingestion/scripts/hitl.py resolve <hitl-id> --action <action> [--params <json>]

# Dismiss item
python3 Skills/meeting-ingestion/scripts/hitl.py dismiss <hitl-id> [--reason <reason>]

# Clear resolved items older than N days
python3 Skills/meeting-ingestion/scripts/hitl.py cleanup [--days 30]
```

### Queue Statistics
```bash
# Show queue stats
python3 Skills/meeting-ingestion/scripts/hitl.py stats

# Show reason breakdown
python3 Skills/meeting-ingestion/scripts/hitl.py reasons
```

### Testing/Development
```bash
# Add test item
python3 Skills/meeting-ingestion/scripts/hitl.py add-test --reason <reason> --meeting-id <id>

# Simulate SMS response
python3 Skills/meeting-ingestion/scripts/hitl.py test-sms --hitl-id <id> --response "<sms text>"
```

## Queue File Format

The queue is stored as JSON Lines (`.jsonl`), with one JSON object per line:

```jsonl
{"id":"HITL-20260201-001","meeting_id":"2026-01-26_Unknown-Participant","created_at":"2026-02-01T18:45:00Z","reason":"unidentified_participant","context":{"transcript_excerpt":"So as I was saying...","known_participants":["V"],"unknown_speakers":["Speaker 2"]},"status":"pending","resolved_by":null,"resolved_at":null,"resolution":null}
{"id":"HITL-20260201-002","meeting_id":"2026-01-28_Team-Meeting","created_at":"2026-02-01T19:12:00Z","reason":"unclear_meeting_topic","context":{"transcript_excerpt":"Let's discuss the next steps...","extracted_topics":["Planning","Review","Discussion"],"confidence":0.4},"status":"resolved","resolved_by":"sms","resolved_at":"2026-02-01T20:15:00Z","resolution":{"action":"set_topic","parameters":{"topic":"Sprint Planning"},"raw_response":"Topic: Sprint Planning"}}
```

## Integration Points

### Adding Items
```python
from Skills.meeting_ingestion.scripts.hitl import add_hitl_item

add_hitl_item(
    meeting_id="2026-01-26_Meeting",
    reason="unidentified_participant", 
    context={
        "transcript_excerpt": "...",
        "known_participants": ["V"],
        "unknown_speakers": ["Speaker 2"]
    }
)
```

### Processing Responses
```python
from Skills.meeting_ingestion.scripts.hitl import process_sms_response

result = process_sms_response(
    hitl_id="HITL-20260201-001",
    sms_text="Speaker 2 = John Smith"
)
```

### Queue Monitoring
```python
from Skills.meeting_ingestion.scripts.hitl import get_queue_stats

stats = get_queue_stats()  # Returns counts by status and reason
```