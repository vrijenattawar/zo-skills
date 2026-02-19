---
name: sourcestack-monitor
description: >
  <YOUR_PRODUCT> Job Sourcing Pipeline powered by SourceStack API.
  Supports daily watchlist scans, role-based sweeps using an archetype taxonomy,
  three-tier geo classification (NYC / US-Remote / Intl-Remote), freshness scoring,
  human-in-the-loop approval, Notion sync, and automated lifecycle pruning.
  All operations are prompt-driven — no separate UI needed.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  version: "2.0.0"
  created: "2026-02-09"
  updated: "2026-02-19"
---

## Overview

Full job sourcing pipeline for <YOUR_PRODUCT>:

1. **Watchlist scan** (daily) — monitor specific companies for new postings
2. **Role sweep** (every 3-4 days) — broad search using archetype-based role taxonomy
3. **Review** — inspect, approve/reject pending jobs via prompting
4. **Publish** — push approved jobs to Notion "Job board" database
5. **Lifecycle** — 30/60/90-day freshness management with weekly pruning

## Setup

API key in [Settings > Advanced](/?t=settings&s=advanced):
- Name: `SOURCESTACK_API_KEY`

Install dependencies:
```bash
pip install -r Skills/sourcestack-monitor/scripts/requirements.txt
```

## CLI Reference

```bash
SS="python3 Skills/sourcestack-monitor/scripts/sourcestack.py"

# === Discovery ===
$SS sweep --geo nyc --all-archetypes --limit 100
$SS sweep --geo us-remote --archetypes backend-engineer,frontend-engineer --limit 50
$SS sweep --geo intl-remote --archetypes ml-engineer --limit 25
$SS scan                            # daily watchlist scan
$SS search --role "staff engineer" --country "United States" --limit 20

# === Review & Approve ===
$SS review --pending --limit 20     # show all pending
$SS review --geo nyc --fresh-only   # NYC fresh jobs only
$SS review --archetype backend-engineer  # filter by archetype
$SS review --approve abc123 def456 --type source_job
$SS review --approve abc123 --type direct_apply
$SS review --reject abc123 def456

# === Notion Sync ===
$SS publish                         # show approved jobs ready for Notion
$SS --dry-run publish               # preview what would be published
$SS notion-prune                    # show stale jobs to remove from Notion

# === Lifecycle ===
$SS lifecycle                       # run freshness state transitions
$SS --dry-run lifecycle             # preview transitions
$SS prune                           # lifecycle + Notion prune combined

# === Config & Status ===
$SS archetypes                      # list all archetypes and title patterns
$SS watchlist                       # show current watchlist
$SS watchlist --add-company "openai.com:OpenAI"
$SS watchlist --add-role "staff engineer"
$SS credits                         # daily credit usage and budget
$SS quota                           # account-level credit balance
$SS query --geo nyc --archetype backend-engineer --since-days 7
$SS delta --since-days 1            # recent changes
```

## Archetype System

Edit `assets/archetypes.yaml` to add/remove role archetypes and their title patterns.
Current archetypes: backend, frontend, fullstack, founding, staff, SRE/platform, data, ML, mobile, security.

## Geo Lists

Three geography tiers defined in `assets/archetypes.yaml` under `geo_lists`:
- **nyc** — NYC metro area cities
- **us-remote** — US-based, remote-friendly or major US cities
- **intl-remote** — International, remote-accepting

## Freshness Tiers

| Age | Tier | Action |
|-----|------|--------|
| 0-14d | fresh | Active |
| 15-29d | aging | Active (flagged) |
| 30d+ | stale | Auto-close, remove from Notion |
| 60d+ | expired | Delete from local DB |

## Credit Budget

- Daily cap: 500 credits
- Watchlist scan: ~5-20 credits/day
- Role sweep: ~100-300 credits per run
- Check with `credits` command

## Database

SQLite at `data/sourcestack.db`. Tables: `jobs`, `scans`, `credit_log`, `schema_meta`.

## Notion Integration

Notion "Job board" DB ID: `29c5c3d6-a5db-81a3-9aa6-000b1c83fa24`.
The `publish` command outputs structured JSON that Zo executes via Notion API tools.
After Zo pushes to Notion, it calls `mark_published()` to update the local DB link.

## Scheduled Agent

Weekly pruner: Sundays at 8 AM ET. Runs `prune` and emails V a summary.
