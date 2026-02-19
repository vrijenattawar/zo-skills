---
name: fillout-survey-monitor
description: Automated monitoring of Fillout survey changes with intelligent refresh triggering. Watches for new submissions and coordinates with dynamic-survey-analyzer to refresh analysis and dashboards. Supports scheduled execution and smart change detection.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  version: 1.0
---

# Fillout Survey Monitor

Automated monitoring system for Fillout survey changes. This skill watches for new survey submissions and triggers refresh workflows when meaningful changes occur.

## When to Use

- When you need to keep survey analysis current as responses come in
- Before important events (pre-event surveys need up-to-date data)
- When you have scheduled surveys receiving ongoing responses
- When you want automated refreshes without manual intervention

## How It Works

1. **Check for changes**: Fetches current submission count from Fillout
2. **Compare to baseline**: Reads `meta.json` from existing analysis
3. **Screen responses**: Excludes non-attending responses (configurable)
4. **Trigger refresh**: If net new responses ≥ threshold, runs full refresh workflow
5. **Notify**: Sends SMS notification with key insights (only on meaningful changes)

## Installation

This skill depends on `dynamic-survey-analyzer` for the actual analysis and dashboard generation.

```bash
# Ensure dynamic-survey-analyzer is installed at:
Skills/dynamic-survey-analyzer/
```

## Usage

### Basic Monitoring (Check & Refresh)

```bash
python3 Skills/fillout-survey-monitor/scripts/monitor.py \
  --form-id jPQRwpT4nGus \
  --account <YOUR_PRODUCT> \
  --refresh-threshold 2
```

Parameters:
- `--form-id`: Fillout form ID (required)
- `--account`: Fillout account name (required)
- `--refresh-threshold`: Minimum new responses to trigger refresh (default: 2)
- `--screening-question`: Question ID for screening (default: dGZw)
- `--screening-exclude`: Value that excludes response (default: "No")

### Check Only (Dry Run)

```bash
python3 Skills/fillout-survey-monitor/scripts/monitor.py \
  --form-id jPQRwpT4nGus \
  --account <YOUR_PRODUCT> \
  --check-only
```

Returns status without triggering refresh.

### Force Refresh

```bash
python3 Skills/fillout-survey-monitor/scripts/monitor.py \
  --form-id jPQRwpT4nGus \
  --account <YOUR_PRODUCT> \
  --force-refresh
```

Skips threshold check and forces full refresh workflow.

## Output

### Console Output

```
[2026-01-28 10:05:00] Survey Monitor: jPQRwpT4nGus
[2026-01-28 10:05:01] Current total responses: 16
[2026-01-28 10:05:01] Previous total: 13 (from meta.json)
[2026-01-28 10:05:02] Net new responses: 3 (excluding 1 non-attending)
[2026-01-28 10:05:02] ✓ Threshold met (≥2), triggering refresh...
[2026-01-28 10:05:15] ✓ Data cache updated
[2026-01-28 10:05:45] ✓ Analysis regenerated (N=15)
[2026-01-28 10:05:50] ✓ Dashboard updated
[2026-01-28 10:05:50] ✓ Meta updated: total_submissions=16, eligible=15
```

### SMS Notification Format

When threshold is met:

```
📊 Survey update: 15 attending responses now (was 12). Key change: New VP-level attendees from Sales & Product want advanced tactics.
```

(max 400 characters)

## Scheduled Agent Integration

Use this with a scheduled agent for automated monitoring. Example agent instruction:

```
Fillout Survey Monitor: jPQRwpT4nGus

STEP 1: Check for changes
python3 Skills/fillout-survey-monitor/scripts/monitor.py --form-id jPQRwpT4nGus --account <YOUR_PRODUCT> --refresh-threshold 2

STEP 2: If new responses, notify V via SMS with key insight
```

## Dependencies

- `dynamic-survey-analyzer` skill (at `Skills/dynamic-survey-analyzer/`)
- Python 3.10+
- `requests`, `json` (standard library)
- Fillout API credentials (configured in `dynamic-survey-analyzer`)

## Files

- `scripts/monitor.py`: Main monitoring script
- `SKILL.md`: This file

## Integration Notes

This skill **orchestrates** but does not analyze. It:
- Calls `fillout_client.py` (from dynamic-survey-analyzer)
- Triggers analysis updates via file writes
- Invokes `generate_dashboard.py` for dashboard refresh
- Updates `meta.json` with new counts

The actual semantic analysis, percentage calculations, and insight generation happen in `dynamic-survey-analyzer`.

## Troubleshooting

**Issue**: "No existing meta.json found"
- **Fix**: Run `dynamic-survey-analyzer` once to create baseline analysis

**Issue**: "Threshold not met, no refresh triggered"
- **Fix**: Use `--force-refresh` or lower `--refresh-threshold`

**Issue**: "SMS notification not sent"
- **Fix**: Check that SMS is configured in Zo settings
