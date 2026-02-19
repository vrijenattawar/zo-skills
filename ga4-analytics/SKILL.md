---
name: ga4-analytics
description: Pull Google Analytics 4 traffic stats for V's personal website (<YOUR_GITHUB>.com). Supports overall traffic, specific page tracking (e.g. /mind), breakdowns by source/device/date, and custom date ranges.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  ga4_property_id: "520487128"
  measurement_id: G-KRHEG1ZD6C
  stream_id: "13325419184"
---

## Usage

```bash
python3 Skills/ga4-analytics/scripts/ga4.py <command> [options]
```

## Commands

### `overview` — Site traffic summary
```bash
python3 Skills/ga4-analytics/scripts/ga4.py overview
python3 Skills/ga4-analytics/scripts/ga4.py overview --days 30
python3 Skills/ga4-analytics/scripts/ga4.py overview --start 2026-01-01 --end 2026-02-14
```

### `pages` — Top pages by pageviews
```bash
python3 Skills/ga4-analytics/scripts/ga4.py pages
python3 Skills/ga4-analytics/scripts/ga4.py pages --days 30 --limit 20
```

### `page` — Stats for a specific page
```bash
python3 Skills/ga4-analytics/scripts/ga4.py page /mind
python3 Skills/ga4-analytics/scripts/ga4.py page /mind --days 30
```

### `sources` — Traffic sources breakdown
```bash
python3 Skills/ga4-analytics/scripts/ga4.py sources
python3 Skills/ga4-analytics/scripts/ga4.py sources --days 7
```

### `devices` — Device category breakdown
```bash
python3 Skills/ga4-analytics/scripts/ga4.py devices
```

### `daily` — Day-by-day traffic
```bash
python3 Skills/ga4-analytics/scripts/ga4.py daily --days 14
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--days N` | Look back N days | 90 |
| `--start YYYY-MM-DD` | Custom start date | — |
| `--end YYYY-MM-DD` | Custom end date | today |
| `--limit N` | Max rows to return | 10 |
| `--property ID` | Override GA4 property ID | env/default |
| `--host HOSTNAME` | Filter to specific hostname | www.<YOUR_GITHUB>.com |

## Configuration

Requires `GA4_SERVICE_ACCOUNT_JSON` secret in [Settings > Advanced](/?t=settings&s=advanced).

Property ID sourced from (in order):
1. `--property` flag
2. `GA4_VA_COM_PROPERTY_ID` env var
3. Hardcoded default (520487128)
