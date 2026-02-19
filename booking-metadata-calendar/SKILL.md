---
name: booking-metadata-calendar
description: Parse natural-language booking requests into structured metadata, wire metadata into calendar event payloads, and persist retrievable records keyed by meeting ID.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  version: "1.0.0"
  created: 2026-02-16
---

# Booking Metadata + Calendar Skill

## Purpose
Convert free-form booking text into structured booking metadata for downstream routing and meeting ingestion.

## What It Produces
1. Validated metadata fields:
- `meeting_intent`
- `strategic_importance`
- `expected_outputs`
- `relationship_goal`
- `promotion_bias`
2. Calendar event payload with metadata attached.
3. Persistent records keyed by `meeting_id`.

## CLI
```bash
python3 Skills/booking-metadata-calendar/scripts/booking_metadata_calendar.py --help
```

### Parse Only
```bash
python3 Skills/booking-metadata-calendar/scripts/booking_metadata_calendar.py parse \
  --message "Need to schedule a partnership meeting with Acme to align on pilot scope and next steps." \
  --title "Acme Partnership Kickoff" \
  --start "2026-02-18T15:00:00-05:00" \
  --end "2026-02-18T15:45:00-05:00"
```

### End-to-End Booking Record (Parse + Wire + Persist)
```bash
python3 Skills/booking-metadata-calendar/scripts/booking_metadata_calendar.py book \
  --message "Intro call with investor to align on strategic milestones and funding timeline." \
  --title "Investor Intro" \
  --start "2026-02-20T10:00:00-05:00" \
  --end "2026-02-20T10:30:00-05:00" \
  --calendar-event-id "cal_evt_123"
```

### Validation Harness (3 Representative Intents)
```bash
python3 Skills/booking-metadata-calendar/scripts/booking_metadata_calendar.py validate-cases
```

## Storage
- Per-meeting metadata:
  - `N5/data/booking_metadata/by_meeting/<meeting_id>.json`
- Append-only index:
  - `N5/data/booking_metadata/registry.jsonl`

## References
- `file 'Skills/booking-metadata-calendar/references/booking-metadata-schema.md'`
- `file 'Skills/booking-metadata-calendar/references/runbook.md'`
