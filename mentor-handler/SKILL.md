---
name: mentor-handler
description: Handle escalation requests from <YOUR_INSTANCE> instances and provide thoughtful mentor guidance based on precedent and context analysis
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  version: "1.0.0"
  build_ref: <YOUR_INSTANCE>-autonomy-v2/D2.3
---

# Mentor Handler

VA-side handler for receiving and responding to escalation requests from <YOUR_INSTANCE> instances.

## Purpose

This skill processes escalation requests from client Zo instances (<YOUR_INSTANCE>s) and provides mentor guidance based on:
- Previous precedent patterns
- Confidence assessment 
- Context analysis
- Risk evaluation

## When to Use

Activated when receiving mentor_escalation type requests via the VA API bridge from <YOUR_INSTANCE> instances.

## Integration Points

- **Audit System**: All escalations are logged with correlation IDs
- **Precedent Store**: Builds knowledge base of guidance patterns  
- **Human Escalation Bridge** (D3.x): Flags requests needing human review
- **VA API**: Receives requests through established reverse bridge

## Core Functionality

### handle_escalation.py

Main script for processing escalation requests:

```bash
# Process an escalation request
python3 Scripts/mentor-handler/scripts/handle_escalation.py --request '{"type": "mentor_escalation", ...}'

# Test with sample data
python3 Scripts/mentor-handler/scripts/handle_escalation.py --test

# Check precedent patterns
python3 Scripts/mentor-handler/scripts/handle_escalation.py --list-precedents
```

### Request Format (from <YOUR_INSTANCE>)

```json
{
  "type": "mentor_escalation", 
  "from": "<YOUR_INSTANCE>",
  "confidence": 0.4,
  "situation": "Client requests removing review gate",
  "context": {
    "client_tier": "enterprise",
    "change_type": "security_gate_change",
    "risk_level": "medium"
  },
  "question": "Should we allow disabling review gates for this client?",
  "correlation_id": "uuid-here",
  "timestamp": "2026-02-07T12:00:00Z"
}
```

### Response Format (to <YOUR_INSTANCE>)

```json
{
  "type": "mentor_response",
  "recommendation": "deny", 
  "confidence": 0.8,
  "rationale": "Review gates are security-critical...",
  "precedent_id": "prec_001",
  "sets_new_precedent": false,
  "needs_human": false,
  "correlation_id": "uuid-here",
  "learning_guidance": "Remember that enterprise clients..."
}
```

### Key Decision Factors

1. **Precedent Matching**: Fuzzy match against stored patterns
2. **Risk Assessment**: Evaluate potential impact 
3. **Confidence Scoring**: VA's certainty in the guidance
4. **Context Analysis**: Client tier, change type, timing
5. **Human Escalation**: Flag when VA is also uncertain (<0.5 confidence)

## Precedent Storage

Maintained in `N5/data/mentor_precedents.json`:

```json
{
  "precedents": [
    {
      "id": "prec_001", 
      "created": "2026-02-07T12:00:00Z",
      "situation_pattern": "security gate removal requests",
      "guidance_given": "deny unless exceptional business justification",
      "outcome": "successful",
      "reusable": true,
      "context_factors": ["client_tier", "risk_level"],
      "confidence_used": 0.8
    }
  ]
}
```

## Quality Guidelines

### Strong Responses Include

- Clear recommendation with rationale
- Reference to precedent when applicable  
- Specific learning guidance for <YOUR_INSTANCE>
- Confidence assessment
- Risk mitigation suggestions

### Escalate to Human When

- VA confidence < 0.5 (uncertainty)
- Novel situation with no precedent
- High-risk decisions requiring V's judgment
- Security or compliance implications
- Conflicting precedents

## Verification

Run tests to ensure:
- Request validation works correctly
- Precedent matching functions properly  
- Response format is valid
- Human escalation triggers appropriately
- Audit logging captures all interactions