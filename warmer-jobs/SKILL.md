---
name: warmer-jobs
description: >
  Search the Warmer Jobs API for job listings by title, seniority, location, industry,
  and many other filters. Use when V asks to search for jobs, find open roles, or pull
  job market data via the Warmer Jobs platform.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  api_base: https://warmerjobs.com/api/v1
  auth_env: WARMERJOBS_API_TOKEN
---

## Usage

```bash
python3 Skills/warmer-jobs/scripts/warmer_jobs.py search --title "vp sales"
python3 Skills/warmer-jobs/scripts/warmer_jobs.py search --title "customer success" --seniority director --locations "san francisco" "new york"
python3 Skills/warmer-jobs/scripts/warmer_jobs.py search --title "software" --work-type remote --industries "software/it services" --funding-stage series_b series_c
python3 Skills/warmer-jobs/scripts/warmer_jobs.py search --help
```

## Authentication

Reads `WARMERJOBS_API_TOKEN` from environment variables. V has this configured in Settings > Developers.

## Key Notes

- API uses `application/x-www-form-urlencoded` POST to `/api/v1/search`
- Array params are passed as repeated keys (e.g. `seniority[]=director&seniority[]=vp`)
- Booleans sent as string `"true"` / `"false"`
- Response is `{ "jobs": [...] }` — treat missing/null `jobs` as empty array
- See `references/api-docs.md` for full parameter reference
