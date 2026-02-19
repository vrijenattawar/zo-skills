---
name: vapi
description: Voice AI integration with Vapi. Enables inbound/outbound phone calls with AI voice agents that can check calendars and book appointments. Webhook server handles dynamic assistant config, call history, and post-call recaps.
compatibility: Created for Zo Computer
created: 2026-02-12
last_edited: 2026-02-12
version: 1.0
provenance: con_QTABCDASvBcVRxAC
metadata:
  author: <YOUR_HANDLE>.zo.computer
  upstream: https://github.com/zocomputer/skills/pull/8
  upstream_author: nloui
---
# Vapi Voice Integration

AI-powered voice assistant that handles phone calls, checks calendar availability, and books appointments.

## Setup

### Environment Variables

Set in [Settings → Advanced](/?t=settings&s=advanced):

| Variable | Required | Value |
|----------|----------|-------|
| `VAPI_API_KEY` | ✅ | Vapi Private API Key |
| `VAPI_OWNER_PHONE` | ✅ | V's phone number (auto-authenticated) |
| `VAPI_OWNER_NAME` | Recommended | `V` |
| `VAPI_ASSISTANT_NAME` | Recommended | Name the voice assistant uses |
| `VAPI_OWNER_CONTEXT` | Recommended | e.g. `Founder of <YOUR_PRODUCT>` |
| `VAPI_CALENDAR_ID` | For booking | Google Calendar email |
| `VAPI_TIMEZONE` | Default: `America/New_York` | Timezone for scheduling |
| `VAPI_VOICE_ID` | For custom voice | ElevenLabs Voice ID |
| `VAPI_VOICE_MODEL` | Default: `eleven_flash_v2_5` | ElevenLabs model |
| `VAPI_LLM_MODEL` | Default: `claude-sonnet-4-20250514` | LLM for voice responses |
| `VAPI_SECURITY_PIN` | Optional | DTMF PIN for non-owner callers |
| `VAPI_WEBHOOK_PORT` | Default: `4242` | Webhook server port |

### Phone Number

Vapi number: `+1 (878) 879-2087`
Phone Number ID: `7facf530-6cb1-4c6c-859b-d3fa700cfe4b`

### Service

Registered as Zo user service `vapi-webhook` on port 4242.

## Usage

### Inbound Calls
People call the Vapi number → webhook dynamically generates assistant config → AI handles the call → recap emailed to V.

### Outbound Calls
```bash
bun Skills/vapi/scripts/vapi.ts call +15551234567
bun Skills/vapi/scripts/vapi.ts call +15551234567 --purpose "Following up on the deck"
bun Skills/vapi/scripts/vapi.ts call +15551234567 --context "Meeting about Q4 planning"
```

### Manage Assistants
```bash
bun Skills/vapi/scripts/vapi.ts assistant list
bun Skills/vapi/scripts/vapi.ts assistant create
```

### Call History
```bash
bun Skills/vapi/scripts/vapi.ts calls
duckdb Datasets/vapi-calls/data.duckdb -c "SELECT * FROM calls ORDER BY started_at DESC LIMIT 10"
```

## Architecture

- **webhook.ts** — Bun HTTP server handling Vapi webhooks (assistant-request, tool-calls, end-of-call-report)
- **vapi.ts** — CLI for managing assistants, phone numbers, and making outbound calls
- Call data stored in DuckDB at `Datasets/vapi-calls/data.duckdb`
- Calendar integration via Google Calendar API (direct OAuth)
- Post-call recaps sent via Zo API → email
