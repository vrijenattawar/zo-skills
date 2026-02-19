---
created: 2026-01-29
last_edited: 2026-01-29
version: 1.0
provenance: con_JTGSUg7MJeBHzmdq
---

# <YOUR_PRODUCT> Data Quality Methodology

## Overview

This document captures the discrete steps required to transform raw <YOUR_PRODUCT> Intelligence Brief data into employer-ready, verified output. Zero hallucinations and zero areas of doubt are non-negotiable.

---

## Input Modes

The decomposer supports two input modes:

### Mode A: Manual Extraction (Current — Temporary)
- **Input:** Google Doc export, PDF with screenshots
- **Requires:** Phases 1-3 (Source Acquisition, Extraction, Cleaning)
- **Status:** Active but will be deprecated when API is available
- **Use when:** <YOUR_PRODUCT> data comes as documents (next 2 days)

### Mode B: Structured API Data (Target State)
- **Input:** JSON/YAML from <YOUR_PRODUCT> API endpoint
- **Requires:** Skip directly to Phase 4 (Structuring)
- **Status:** Pending API availability
- **Use when:** Receiving data programmatically from <YOUR_PRODUCT> platform

**Detection:** If input is already valid YAML/JSON with expected schema (skills array, ratings, our_take fields), skip to Phase 4. Otherwise, run full pipeline.

---

## Phase 1: Source Acquisition *(Mode A Only — Temporary)*

### Step 1.1: Identify Primary Source
- <YOUR_PRODUCT> Intelligence Brief (Google Doc format)
- Contains: Profile overview, elevator pitch, strengths/weaknesses, experience, skills assessments, "Our Take" narratives

### Step 1.2: Export Full Document
- Export as PDF to preserve embedded screenshots
- Screenshots contain skill assessments with ratings that may not be in text

### Step 1.3: Verify Completeness
- Check page count matches expected (e.g., 56 pages for full brief)
- Verify all tabs/sections are captured (Overview, Experience, Resume, Deep Dive)

---

## Phase 2: Extraction

### Step 2.1: PDF → Image Conversion
```bash
pdftoppm input.pdf output_dir/page -png -r 300
```
- 300 DPI for OCR accuracy
- PNG format preserves quality

### Step 2.2: OCR All Pages
```bash
for f in output_dir/*.png; do
  tesseract "$f" "${f%.png}" 2>/dev/null
done
cat output_dir/*.txt > full_ocr.txt
```

### Step 2.3: Initial Quality Check
- Count "Our Take" occurrences (should match skill count)
- Verify section headers captured
- Check for obvious OCR failures

---

## Phase 3: Cleaning

### Step 3.1: Fix Known OCR Artifacts
| Artifact | Correct | Reason |
|----------|---------|--------|
| Al | AI | Common OCR misread |
| Saa$ | SaaS | $ confused for S |
| Ul | UI | l confused for I |
| € | ← | Euro symbol for back arrow |
| pROFGle | Profile | Lowercase/uppercase confusion |

### Step 3.2: Standardize Identifiers
- Story IDs: Preserve exact alphanumeric sequences
- Skill names: Match to canonical list from JD
- Rating terms: Excellent, Good, Fair (not synonyms)

### Step 3.3: Flag Uncertainties
- Use `[?]` marker for any unclear text
- Document uncertainty in dedicated section
- Never guess or interpolate

---

## Phase 4: Structuring

### Step 4.1: Create Canonical Score File
- YAML or JSON format
- One entry per skill with:
  - skill_name
  - category (Responsibility, Soft Skill, Hard Skill)
  - rating (Excellent, Good, Fair)
  - required_level (Intermediate, Advanced, Expert)
  - importance (1-10)
  - evidence_type (Story+Profile, Profile, Resume, Gap)
  - our_take (full text)
  - support (array of story/resume matches with scores)

### Step 4.2: Create Flat Export
- CSV for spreadsheet analysis
- Truncate long text fields
- Preserve all numeric scores

### Step 4.3: Cross-Reference Validation
- Every skill in JD has corresponding assessment
- Every assessment has evidence source
- No orphan data

---

## Phase 5: Verification

### Step 5.1: Count Validation
| Check | Expected | Tolerance |
|-------|----------|-----------|
| Total skills | Per JD requirements | 0 |
| Excellent ratings | From OCR count | 0 |
| Good ratings | From OCR count | 0 |
| Fair ratings | From OCR count | 0 |
| Gaps | Explicit in source | 0 |

### Step 5.2: Content Spot-Check
- Sample 3-5 "Our Take" narratives
- Compare OCR output to PDF screenshot
- Verify key metrics (scores, percentages) are accurate

### Step 5.3: Uncertainty Resolution
- Review all `[?]` markers
- Attempt resolution via:
  1. Context clues in surrounding text
  2. Cross-reference with other sections
  3. If unresolvable → Flag for candidate/source verification

---

## Phase 6: Output Generation

### Step 6.1: Clean Markdown Document
- Structured sections matching source
- All assessments with full "Our Take" text
- Uncertainty log at end

### Step 6.2: Canonical Data Files
- `scores_complete.json` — Full structured data
- `scores_complete.csv` — Flat export
- `manifest.yaml` — Metadata and file inventory

### Step 6.3: Final Quality Gate
- [ ] All skills have assessments
- [ ] All assessments have ratings
- [ ] All ratings have evidence
- [ ] No placeholder text
- [ ] No hallucinated content
- [ ] Uncertainties flagged, not guessed

---

## Anti-Patterns (Never Do)

| Anti-Pattern | Why It's Wrong |
|--------------|----------------|
| Guessing unclear text | Zero hallucination policy |
| Interpolating missing data | May misrepresent candidate |
| Using synonyms for ratings | "Great" ≠ "Excellent" |
| Omitting low scores | Misleads employer |
| Summarizing "Our Take" | Loses precision and nuance |
| Ignoring OCR artifacts | Propagates errors |

---

## Audit Trail

Every decomposition should produce:
1. `<YOUR_PRODUCT>_full_ocr.txt` — Raw OCR output
2. `<YOUR_PRODUCT>_cleaned.md` — Cleaned, structured document
3. `scores_complete.json` — Canonical data file
4. `manifest.yaml` — Processing metadata

This ensures traceability from source to output.

---

*<YOUR_PRODUCT> Proprietary Methodology*
