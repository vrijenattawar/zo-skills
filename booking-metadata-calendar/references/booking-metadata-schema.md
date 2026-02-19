---
created: 2026-02-16
last_edited: 2026-02-16
version: 1.0
provenance: con_N35yIIEohUFx11xg
---

# Booking Metadata Schema

## Canonical Fields

| Field | Type | Required | Allowed Values |
|---|---|---|---|
| `meeting_intent` | string | yes | `partnership`, `sales`, `investor`, `hiring`, `intro`, `advisory`, `support`, `internal-planning`, `check-in`, `other` |
| `strategic_importance` | string | yes | `high`, `medium`, `low` |
| `expected_outputs` | string[] | yes | Non-empty list of concise expected outcomes |
| `relationship_goal` | string | yes | `deepen-trust`, `advance-deal`, `qualify-fit`, `request-support`, `offer-support`, `maintain-cadence`, `explore-opportunity`, `other` |
| `promotion_bias` | string | yes | `promote-now`, `promote-if-novel`, `archive-only` |

## Extended Fields (Produced by Parser)

| Field | Type | Notes |
|---|---|---|
| `parser_version` | string | Parser build version |
| `raw_booking_message` | string | Original NL booking request |
| `parsed_at_utc` | string | ISO timestamp |

## Persistence Contract

### Storage Layout
- `N5/data/booking_metadata/by_meeting/<meeting_id>.json`
- `N5/data/booking_metadata/registry.jsonl`

### Per-Meeting Record Shape
```json
{
  "meeting_id": "2026-02-18_acme-partnership-kickoff",
  "title": "Acme Partnership Kickoff",
  "start": "2026-02-18T15:00:00-05:00",
  "end": "2026-02-18T15:45:00-05:00",
  "timezone": "America/New_York",
  "attendees": ["alice@acme.com"],
  "metadata": {
    "meeting_intent": "partnership",
    "strategic_importance": "high",
    "expected_outputs": ["define pilot scope and next steps"],
    "relationship_goal": "explore-opportunity",
    "promotion_bias": "promote-now",
    "parser_version": "1.0.0",
    "raw_booking_message": "...",
    "parsed_at_utc": "..."
  },
  "calendar": {
    "calendar_event_id": "cal_evt_123",
    "title": "...",
    "start": "...",
    "end": "...",
    "timezone": "America/New_York",
    "attendees": [],
    "description": "BOOKING_METADATA..."
  },
  "stored_at_utc": "..."
}
```
