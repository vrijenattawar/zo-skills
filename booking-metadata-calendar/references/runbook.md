---
created: 2026-02-16
last_edited: 2026-02-16
version: 1.0
provenance: con_N35yIIEohUFx11xg
---

# Booking Metadata + Calendar Runbook

## Goal
Capture structured booking intent at scheduling time so downstream ingestion and promotion can consume it by `meeting_id`.

## Preconditions
1. Python 3.10+ available.
2. Workspace path exists: `N5/data/booking_metadata/`.

## Workflow

### 1. Validate Parser Cases
```bash
python3 Skills/booking-metadata-calendar/scripts/booking_metadata_calendar.py validate-cases
```

Expected: `passed: true` with at least 3 representative intents.

### 2. Parse a New Booking Request
```bash
python3 Skills/booking-metadata-calendar/scripts/booking_metadata_calendar.py parse \
  --message "Schedule a strategic partnership call with Acme to align on pilot goals and ownership." \
  --title "Acme Partnership Strategy" \
  --start "2026-02-18T15:00:00-05:00" \
  --end "2026-02-18T15:45:00-05:00"
```

### 3. Book + Persist Metadata (Canonical Path)
```bash
python3 Skills/booking-metadata-calendar/scripts/booking_metadata_calendar.py book \
  --message "Schedule a strategic partnership call with Acme to align on pilot goals and ownership." \
  --title "Acme Partnership Strategy" \
  --start "2026-02-18T15:00:00-05:00" \
  --end "2026-02-18T15:45:00-05:00" \
  --calendar-event-id "google_event_id_123"
```

Outputs:
1. `meeting_id`
2. `record_path` under `N5/data/booking_metadata/by_meeting/`
3. Calendar payload containing metadata reference in description.

### 4. Retrieval
1. Direct by meeting ID:
```bash
cat N5/data/booking_metadata/by_meeting/<meeting_id>.json
```
2. Index scan:
```bash
tail -n 20 N5/data/booking_metadata/registry.jsonl
```

## Calendar Integration Wiring Pattern
1. Create calendar event payload from `book` output.
2. Push event through calendar API.
3. Store returned `calendar_event_id` in persisted record.
4. Ingestion can resolve metadata via:
   - `meeting_id` from event title/date convention, or
   - `calendar_event_id` from registry entry.

## Representative Intents Covered
1. Partnership strategy call.
2. Investor update discussion.
3. Casual check-in marked archive-only.
