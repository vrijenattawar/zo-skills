---
name: <YOUR_PRODUCT>-decomposer
description: |
  Decomposes <YOUR_PRODUCT> Intelligence Briefs into structured YAML using LLM semantic extraction.
  Takes raw <YOUR_PRODUCT> doc + JD → Outputs indexed YAML files to inbox for Meta-Resume generation.
  NO regex, NO string parsing — pure LLM semantic understanding.
  Supports three input modes: Chunked parallel (auto for large docs), manual extraction, or structured API data.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  updated: 2026-02-15
  version: 3.0
---
# <YOUR_PRODUCT> Decomposer

Transforms <YOUR_PRODUCT> Intelligence Briefs into structured, employer-ready data.

## Quick Start

```bash
# From OCR/text document (auto-detects large docs for chunked processing)
python3 Skills/<YOUR_PRODUCT>-decomposer/scripts/decompose.py \
  --doc /path/to/<YOUR_PRODUCT>_ocr.txt \
  --jd /path/to/jd.yaml \
  --candidate "firstname" \
  --company "company"

# From structured JSON (preferred when available)
python3 Skills/<YOUR_PRODUCT>-decomposer/scripts/decompose.py \
  --input-json /path/to/structured_data.json \
  --doc /path/to/source_doc.txt \
  --candidate "firstname" \
  --company "company"

# Validate outputs
python3 Skills/<YOUR_PRODUCT>-decomposer/scripts/validate.py --all
python3 Skills/<YOUR_PRODUCT>-decomposer/scripts/validate.py hardik-flowfuse
```

## Input Modes

### Mode A: OCR/Text Extraction (Small Documents)
- Uses LLM to extract skills from unstructured text
- For documents < 1500 lines
- Batched extraction with verification
- Higher hallucination risk — use fail-fast mode

### Mode B: Structured JSON (Preferred)
- Accepts pre-structured data from endpoint
- Copies verbatim fields directly
- Still validates against source document
- Minimal LLM involvement

### Mode C: Chunked Parallel Processing (Large Documents) ⭐ NEW
- **Auto-activated** when document > 1500 lines
- Splits document into logical sections (Overview, Responsibilities, Soft Skills, Hard Skills)
- Processes chunks in parallel via `/zo/ask` API
- Significantly faster for 50+ page briefs
- More reliable than single-pass extraction for large docs

**Chunked mode output:**
```
<YOUR_PRODUCT>/meta-resumes/inbox/<candidate>-<company>/
├── manifest.yaml           # Includes processing.mode: "chunked_parallel"
├── jd.yaml
├── overview.yaml
├── scores_complete.json
├── <YOUR_PRODUCT>_full_ocr.txt
└── .work/                  # Debug artifacts
    └── chunks/             # Split document sections
```

## Output Location

```
<YOUR_PRODUCT>/meta-resumes/inbox/<candidate>-<company>/
├── manifest.yaml           # Processing metadata + counts
├── jd.yaml                 # Job description (copied)
├── overview.yaml           # Profile summary, <YOUR_PRODUCT>_score
├── profile.yaml            # Background, education
├── experience.yaml         # Work history
├── hard_skills.yaml        # Technical competencies
├── soft_skills.yaml        # Working style
├── achievements.yaml       # Awards, recognition
├── tools.yaml              # Technologies
├── interests.yaml          # Hobbies, culture fit
├── alignment.yaml          # JD ↔ Candidate mapping
├── gaps_and_caveats.yaml   # Cross-cutting gaps, story metadata
├── scores_complete.json    # ⭐ All skill assessments with "Our Take"
├── scores_complete.csv     # Flat export for spreadsheets
└── <YOUR_PRODUCT>_full_ocr.txt # Raw OCR (if Mode A/C)
```

## Canonical Schema (scores_complete.json) — v3.0

```json
{
  "overall_score": 90,
  "bottom_line": "Strong, user-obsessed PM with proven, metric-backed delivery...",
  "qualification": "Well-aligned",
  "qualification_detail": "Atypical Background",
  "career_trajectory": "Industry Shift",
  "elevator_pitch": "You get a founding-minded builder who...",
  "recommendation": "YES",
  "overall_strengths": "Proven PM with metric-backed delivery and executive judgment",
  "overall_weaknesses": "Limited consumer tooling experience (Figma/React)",
  "potential_dealbreakers": [
    "Do you require a meaningful equity stake in the company to accept a position?",
    "Are you willing to accept a benefits package that starts in Q2 2026?"
  ],
  "category_scores": {
    "background": {"score": 78, "max": 100},
    "uniqueness": {"score": 81, "max": 100},
    "responsibilities": {"score": 96, "max": 100},
    "hard_skills": {"score": 85, "max": 100},
    "soft_skills": {"score": 100, "max": 100}
  },
  "signal_strength": {
    "story_verified_pct": 78.5,
    "resume_only_pct": 21.5,
    "inferred_pct": 0
  },
  "stories_told": 2,
  "story_ids": ["o94wesBFvqnIgr9l5YVz", "fD33sFRzb4mHgSYFM7Ps"],
  "cross_cutting_gaps": [
    {
      "area": "AI safety and guardrails",
      "severity": "significant",
      "detail": "No concrete examples of LLM fallback strategies...",
      "interview_probes": ["What specific LLM fallback strategies have you implemented?"],
      "affected_skills": ["AI Reliability Engineering", "Production AI System Design"]
    }
  ],
  "skills": [
    {
      "skill_name": "Manage Product Launches",
      "category": "Responsibility",
      "rating": "Excellent",
      "required_level": "Intermediate",
      "importance": 8,
      "max_importance": 10,
      "direct_experience_score": 9,
      "max_experience_score": 10,
      "experience_type": "Direct",
      "evidence_type": "Story + profile",
      "our_take": "Full verbatim assessment text from the document...",
      "contributing_skills": [
        "Product Management",
        "Feature Prioritization",
        "Collaboration",
        "Communication"
      ],
      "support": [
        {
          "source": "o94wesBFvqnIgr9l5YVz",
          "type": "Direct",
          "score": "9/10",
          "rating": "Excellent",
          "is_best": false
        },
        {
          "source": "fD33sFRzb4mHgSYFM7Ps",
          "type": "Direct",
          "score": "8/10",
          "rating": "Excellent",
          "is_best": true
        }
      ],
      "support_note": null,
      "source_page": "page-31"
    }
  ]
}
```

**Top-Level Fields:**
- `overall_score`: Integer 0-100, the <YOUR_PRODUCT> score
- `bottom_line`: Single sentence verdict/summary
- `qualification`: "Well-aligned", "Partially aligned", "Not aligned"
- `qualification_detail`: Additional context like "Atypical Background"
- `career_trajectory`: "Industry Shift", "Lateral Move", "Step Up", etc.
- `elevator_pitch`: Full elevator pitch paragraph from the brief
- `recommendation`: "STRONG_YES", "YES", "CONDITIONAL", "NO", "STRONG_NO"
- `category_scores`: Breakdown by Background, Uniqueness, Responsibilities, Hard Skills, Soft Skills (each 0-100)
- `signal_strength`: Percentage breakdown of evidence types (always sums to 100.0%)
- `potential_dealbreakers`: Array of dealbreaker questions from the brief
- `stories_told`: Integer count of stories referenced in the brief
- `story_ids`: Array of story ID strings referenced throughout the brief
- `cross_cutting_gaps`: Array of cross-cutting gap analyses (not tied to individual skills)
- `skills`: Array of individual skill assessments

**Skill-Level Fields:**
- `importance`, `max_importance`: integers (1-10)
- `direct_experience_score`, `max_experience_score`: integers (1-10) from "Direct experience: X/10"
- `rating`: "Excellent" | "Good" | "Fair" | "Gap"
- `category`: "Responsibility" | "Hard Skill" | "Soft Skill"
- `experience_type`: "Direct" | "Transferable"
- `evidence_type`: "Story + profile" | "Story" | "Profile" | "Resume" | "Gap"
- `our_take`: Full text, never summarized
- `contributing_skills`: Array of skills that contribute to this assessment
- `support[].is_best`: Boolean marking the "Best" supporting story
- `support_note`: Text like "No strong support found" when applicable

## Score Detection

The <YOUR_PRODUCT>_score is extracted from two formats:

1. **Web format** (preferred): `90\nOverall score`
2. **Legacy format**: `Referred 89 ©`

This is stored in:
- `overview.yaml` → `<YOUR_PRODUCT>_score.overall`
- `manifest.yaml` → `<YOUR_PRODUCT>_score`
- `scores_complete.json` → `overall_score`

## Validation

```bash
# Validate single candidate
python3 Skills/<YOUR_PRODUCT>-decomposer/scripts/validate.py hardik-flowfuse

# Validate all
python3 Skills/<YOUR_PRODUCT>-decomposer/scripts/validate.py --all
```

Validation checks:
- Required files present
- scores_complete.json matches canonical schema
- <YOUR_PRODUCT>_score is not null
- "Our Take" narratives are present and substantial

## Key Principles

1. **Zero hallucinations** — If unclear, use null, never guess
2. **Preserve "Our Take" verbatim** — These are the core assessments
3. **Numeric fields are integers** — `importance: 10` not `"10/10"`
4. **Schema-validated outputs** — All outputs pass `assets/canonical_schema.json`
5. **Audit trail** — Every output traceable to source

## Schema Files

- **Canonical output schema**: `Skills/<YOUR_PRODUCT>-decomposer/assets/canonical_schema.json`
- **Structured input schema**: `Skills/<YOUR_PRODUCT>-decomposer/assets/input_schema.json`

Use these for validation in downstream systems.

---

*<YOUR_PRODUCT> Proprietary Skill*
