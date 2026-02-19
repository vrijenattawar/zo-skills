---
name: resume-decoded
description: |
  Generates <YOUR_PRODUCT> "Resume:Decoded" candidate briefs as 2-page branded PDFs.
  Takes decomposer output directory → Outputs signal-based analysis with v4.3 linguistic framing.
  Uses Puppeteer for pixel-perfect PDF rendering. No deficit language — only "what we know" and "what to verify."
  v4.3: Extracts behavioral signals from "our_take" narratives, uses actual culture alignment from alignment.yaml.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  version: "4.3"
  created: "2026-02-04"
  updated: "2026-02-07"
---

# Resume:Decoded

Generates signal-based candidate intelligence briefs for employer decision-making.

## Quick Start

```bash
# Full pipeline: decomposer output → PDF
cd Skills/resume-decoded/scripts

# Step 1: Generate template data (with LLM analysis)
python3 adapter.py <decomposer_dir> output.json

# Step 2: Render PDF
bun run render.ts output.json output.pdf

# Or use the --from-decomposer flag for one-step:
bun run render.ts --from-decomposer <decomposer_dir> output.pdf
```

## Example

```bash
python3 adapter.py ./<YOUR_PRODUCT>/meta-resumes/inbox/hardik-docsum/ /tmp/hardik.json
bun run render.ts /tmp/hardik.json ./<YOUR_PRODUCT>/resumes-decoded/hardik-decoded.pdf
```

## Input

Decomposer output directory containing:
- `scores_complete.json` — Main assessment data (required)
- `overview.yaml` — Overall score, verdict, recommendation
- `jd.yaml` — Job description
- `profile.yaml` — Candidate profile
- `experience.yaml` — Work history with positions[] and duration fields
- `hard_skills.yaml` — Technical skills with Direct/Transferable classification
- `tools.yaml` — Tools and technologies
- `alignment.yaml` — JD ↔ Candidate alignment including culture_alignment (v4.3)
- `culture_signals.yaml` — Culture requirements extracted from JD (v4.3)

## Output

2-page branded PDF:

**Page 1: The Decision Page**
- Candidate Bottom Line (summary box)
- Verdict box (👍 Take This Meeting — 85/100)
- Skills Signal (screen-verified % / resume-backed % · X screens)
- Behavioral Evidence (2x2 grid from "our_take" narratives)
- Questions That Matter (5 targeted questions)

**Page 2: The Prep Page**  
- Your Priorities → Fit (trade-offs table)
- Culture Alignment Signals (Strong Fit / Concerns / Verify columns)

## Architecture

```
Skills/resume-decoded/
├── SKILL.md              # This file
├── scripts/
│   ├── adapter.py        # Decomposer → Template data (LLM-powered, v4.3)
│   └── render.ts         # Template data → PDF (Puppeteer)
├── templates/
│   └── template.html     # Handlebars HTML template (v4.3)
└── examples/
    └── hardik-reference.json  # Known-good template data
```

## v4.3 Changes

| Area | Before | After |
|------|--------|-------|
| Tenure calculation | Looked for `work_history[]` | Reads from `experience.positions[]` with `duration` field |
| Screen count | Always showed 0 | Counts positions with <YOUR_PRODUCT> data |
| Terminology | "interviews" | "screens" |
| Behavioral signals | Empty or from `stories[]` | Extracted from `our_take` narratives via LLM |
| Culture Alignment | Used skills as proxies | Uses actual `culture_alignment` from alignment.yaml |

## Linguistic Principles (v4.3)

| Instead of... | Use... |
|---------------|--------|
| "No direct evidence" | "More direct evidence needed" |
| "Gap in experience" | "Verify: [area]" |
| "Doesn't have X" | "X: [current signal] — ask for story" |
| "Risk: Y" | "Watch for: Y — verify with [question]" |
| "0 interviews" | "X screens" (actual <YOUR_PRODUCT> screen count) |

**Signal encoding:**
- **Bold** = screen-verified (from <YOUR_PRODUCT> structured assessments)
- Regular = resume-backed (from profile only)

## Dependencies

```bash
cd Skills/resume-decoded/scripts
pip install pyyaml requests  # Python
bun install                   # TypeScript (puppeteer, handlebars)
```

## LLM Analysis

The adapter uses `/zo/ask` for semantic analysis:
- Behavioral signal extraction from "our_take" narratives
- Interview question generation
- Trade-off analysis (balanced, not overly positive)
- Culture alignment classification (from alignment.yaml)

If LLM calls fail, structural fallbacks are used.

## Testing

```bash
# Run full pipeline test
cd Skills/resume-decoded/scripts
python3 adapter.py ./<YOUR_PRODUCT>/meta-resumes/inbox/hardik-docsum/ /tmp/test.json
bun run render.ts /tmp/test.json /tmp/test.pdf
```

## Reference Output

See `examples/hardik-reference.json` for known-good template data structure.

---

*<YOUR_PRODUCT> Proprietary Skill — v4.3*
