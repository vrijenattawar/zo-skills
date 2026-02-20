---
name: meeting-ingestion
description: Unified skill for ingesting meeting transcripts from Google Drive and orchestrating the processing pipeline (recap, blocks). Replaces legacy MG-1 through MG-6 agent sequence.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_DOMAIN>
  version: "2.0.0"
  created: 2026-01-26
  rebuilt: 2026-01-27
---

# Meeting Ingestion Skill

Unified meeting transcript processing: download from Google Drive, stage, generate intelligence blocks, archive to weekly folders.

## Quick Start

```bash
# Check current status
python3 Skills/meeting-ingestion/scripts/meeting_cli.py status

# Full pipeline
python3 Skills/meeting-ingestion/scripts/meeting_cli.py pull          # Get from Drive
python3 Skills/meeting-ingestion/scripts/meeting_cli.py stage         # Wrap in folders
python3 Skills/meeting-ingestion/scripts/meeting_cli.py process       # Generate blocks
python3 Skills/meeting-ingestion/scripts/meeting_cli.py archive --execute  # Move to weeks
```

## Processing Pipeline

```
Google Drive
     │
     ▼ (pull)
┌──────────────────────────────────────────┐
│ INBOX (Personal/Meetings/Inbox/)         │
│                                          │
│  Raw .md files → (stage) → Folders       │
│                                          │
│  2026-01-26_David-x-Careerspan/          │
│    ├── transcript.md                     │
│    ├── manifest.json  {status: staged}   │
│    │                                     │
│    │ (process)                           │
│    ▼                                     │
│    ├── B01_DETAILED_RECAP.md             │
│    ├── B05_ACTION_ITEMS.md               │
│    └── manifest.json  {status: complete} │
└──────────────────────────────────────────┘
     │
     ▼ (archive)
┌──────────────────────────────────────────┐
│ WEEKLY ARCHIVE                           │
│  Week-of-2026-01-20/                     │
│    └── 2026-01-26_David-x-Careerspan/    │
└──────────────────────────────────────────┘
```

## Commands

### `status`
Show current queue status.

```bash
python3 scripts/meeting_cli.py status
```

Output shows:
- Raw files needing staging
- Staged meetings ready for processing
- Complete meetings ready for archival
- Total archived meetings

### `pull`
Download transcripts from Google Drive.

```bash
python3 scripts/meeting_cli.py pull [--dry-run] [--batch-size N]
```

### `stage`
Prepare raw transcripts for processing.

```bash
python3 scripts/meeting_cli.py stage [--dry-run]
```

**What it does:**
1. Finds raw `.md` files in Inbox
2. Creates meeting folder with clean name
3. Moves transcript to `transcript.md`
4. Creates `manifest.json` with status: "staged"
5. Quarantines orphaned block files

### `process`
Generate intelligence blocks for meetings.

```bash
# Process queue (all staged meetings)
python3 scripts/meeting_cli.py process [--batch-size N]

# Process specific meeting
python3 scripts/meeting_cli.py process /path/to/meeting [--blocks B01,B05,B08]
```

**Options:**
- `--blocks B01,B05` - Generate specific blocks only
- `--batch-size N` - Max meetings to process (default: 5)
- `--dry-run` - Preview without generating

### `archive`
Move completed meetings to weekly folders.

```bash
# Preview (default)
python3 scripts/meeting_cli.py archive

# Execute
python3 scripts/meeting_cli.py archive --execute
```

### `fix`
Repair malformed Inbox state.

```bash
python3 scripts/meeting_cli.py fix [--dry-run]
```

Quarantines orphaned files and stages any raw transcripts.

## Block Selection (LLM-Powered)

The `block_selector.py` script uses LLM analysis to intelligently determine which blocks to generate based on transcript content.

### How It Works

1. **Recipe Selection**: Determines base recipe from meeting type + participants
2. **LLM Analysis**: Calls `/zo/ask` to analyze transcript for:
   - Conditional block triggers (business context, strategic content, etc.)
   - Zo Take Heed patterns ("Zo, intro me to...", "Zo, draft a blurb...")
   - Priority relevance (weighs toward V's current focus)
3. **Block Assembly**: Combines always-on blocks + selected conditionals

### Usage

```bash
# From meeting folder (uses manifest.json for type/participants)
python3 Skills/meeting-ingestion/scripts/block_selector.py /path/to/meeting

# Direct transcript with explicit type
python3 Skills/meeting-ingestion/scripts/block_selector.py \
    --transcript /path/to/transcript.md \
    --type external

# Dry run (shows recipe without LLM call)
python3 Skills/meeting-ingestion/scripts/block_selector.py /path/to/meeting --dry-run

# JSON output (for programmatic use)
python3 Skills/meeting-ingestion/scripts/block_selector.py /path/to/meeting --json
```

### Output Structure

```json
{
  "recipe": "external_standard",
  "always": ["B00", "B01", "B02_B05", "B03", "B08", "B21", "B26"],
  "conditional_selected": ["B06", "B28"],
  "conditional_skipped": ["B04", "B10", "B13", "B25", "B32", "B33"],
  "triggered": ["B14"],
  "reasoning": {
    "B06": "Business context discussed - partnership terms",
    "B28": "Strategic implications for market positioning",
    "B14": "Triggered: 'Zo, draft a blurb about David'"
  },
  "total_blocks": 10,
  "all_blocks": ["B00", "B01", "B02_B05", "B03", "B06", "B08", "B14", "B21", "B26", "B28"]
}
```

### Recipes

| Recipe | Use When | Always Blocks | Conditional Pool |
|--------|----------|---------------|------------------|
| `external_standard` | Default external | 7 | 10 |
| `external_sales` | Sales/partnership | 8 | 8 |
| `external_investor` | Investor meetings | 9 | 6 |
| `internal_standup` | Team standups | 5 | 4 |
| `internal_strategy` | Strategy sessions | 7 | 3 |

### Integration

The block selector is called by the processing pipeline to determine which blocks to generate:

```python
from block_selector import select_blocks

result = select_blocks(transcript, meeting_type, participants)
blocks_to_generate = result["all_blocks"]
```

## Quality Gate

The `quality_gate.py` script validates meeting readiness before block generation using comprehensive quality checks defined in the quality harness specification. It ensures transcript quality, participant identification, and calendar matching meet required thresholds.

### Purpose

The quality gate performs 16 distinct quality checks across 4 pipeline stages:

1. **Pre-processing**: Transcript validation (length, format, encoding, duration consistency)
2. **Identification**: Participant and calendar matching validation  
3. **Block Generation**: Ready for when blocks are generated (placeholder for D3.5-D3.6)
4. **Post-processing**: Pipeline completion validation

### Usage

```bash
# Basic execution (requires manifest.json)
python3 Skills/meeting-ingestion/scripts/quality_gate.py /path/to/meeting/manifest.json --transcript /path/to/transcript.md

# With custom config
python3 Skills/meeting-ingestion/scripts/quality_gate.py /path/to/meeting/manifest.json --transcript /path/to/transcript.md --config /path/to/config.yaml

# Verbose output
python3 Skills/meeting-ingestion/scripts/quality_gate.py /path/to/meeting/manifest.json --transcript /path/to/transcript.md --verbose

# JSON output (for programmatic use)
python3 Skills/meeting-ingestion/scripts/quality_gate.py /path/to/meeting/manifest.json --transcript /path/to/transcript.md --json
```

### Quality Checks

The quality gate implements these checks from the quality harness specification:

**Pre-processing Stage:**
- `transcript_length`: ≥300 characters of actual content
- `transcript_format`: Valid UTF-8, readable text with speaker indicators  
- `meeting_duration_consistency`: Word count within 50% of expected based on duration
- `transcript_encoding`: UTF-8 compliant, no encoding artifacts

**Identification Stage:**
- `participant_confidence`: Overall confidence ≥0.7
- `host_identified`: At least one participant has role "host"
- `external_participant_verification`: External meetings have ≥1 non-V participant
- `calendar_match_score`: Match confidence ≥0.6 or manual override
- `meeting_type_consistency`: Type aligns with participant roster

### Pass/Fail Logic

- **PASS**: Overall score ≥0.8, no critical failures, no HITL escalations
- **FAIL + HITL**: Participant identification <0.5, encoding corruption, critical failures  
- **FAIL + RETRY**: Transcript too short, temporary API failures
- **PASS with WARNING**: Optional checks fail but core requirements met

### HITL Escalation

Failed checks trigger escalation to the HITL queue (`scripts/review/meetings/hitl-queue.jsonl`) with priority levels:

- **P0 (Immediate)**: Encoding corruption, system errors, critical stakeholder ID failures
- **P1 (Standard)**: Low participant confidence, calendar match failures  
- **P2 (Batch)**: Minor validation failures, borderline scores

### Manifest Integration

Updates the manifest `quality_gate` object with results:

```json
{
  "quality_gate": {
    "passed": true,
    "checks": {
      "has_transcript": true,
      "participants_identified": true, 
      "meeting_type_determined": true,
      "no_hitl_pending": true
    },
    "score": 0.85,
    "executed_at": "2026-02-01T18:45:00Z",
    "check_results": [...]
  }
}
```

On success, advances meeting status from "identified" → "gated" to proceed to block generation.

## State Machine

| Status | Meaning |
|--------|---------|
| `staged` | Folder created, ready for processing |
| `processing` | Block generation in progress |
| `complete` | All blocks generated, ready for archive |
| `archived` | Moved to Week-of folder |

State is tracked in `manifest.json`, NOT in folder name suffixes.

## Folder Naming

**Pattern:** `YYYY-MM-DD_Descriptive-Name`

Examples:
- `2026-01-26_David-x-Careerspan`
- `2026-01-22_Peter-Weddle`
- `2026-01-20_Trio-Standup`

**No longer used:**
- `_[P]`, `_[M]`, `_[B]` suffixes (state in manifest instead)
- Concatenated emails
- Google Meet codes as sole identifier

## manifest.json Schema

```json
{
  "meeting_id": "2026-01-26_David-x-Careerspan",
  "date": "2026-01-26",
  "participants": ["David", "V"],
  "meeting_type": "external",
  "status": "staged",
  "transcript_file": "transcript.md",
  "blocks_requested": [],
  "blocks_generated": ["B01_DETAILED_RECAP"],
  "blocks_failed": [],
  "staged_at": "2026-01-27T10:00:00Z",
  "processed_at": null,
  "archived_at": null,
  "error": null
}
```

## Intelligence Blocks

### External Meetings (Standard)
| Block | Description |
|-------|-------------|
| B01 | Detailed recap |
| B02 | Commitments made |
| B03 | Decisions with rationale |
| B05 | Action items |
| B08 | Stakeholder intelligence |
| B25 | Deliverables |
| B26 | Meeting metadata |

### Conditional (Added When Relevant)
- B04 - Open questions
- B06 - Business context
- B07 - Tone and context
- B10 - Risks and flags
- B13 - Plan of action
- B21 - Key moments
- B28 - Strategic intelligence

### Internal Meetings
- B40 - Internal decisions
- B41 - Team coordination
- B47 - Open debates

## Directory Structure

```
Skills/meeting-ingestion/
├── SKILL.md                 # This file
├── scripts/
│   ├── meeting_cli.py       # Unified CLI
│   ├── pull.py              # Google Drive download
│   ├── stage.py             # Folder preparation
│   ├── process.py           # Block generation
│   └── archive.py           # Weekly archival
├── references/
│   └── legacy_prompts.md    # Migration notes
└── assets/
```

## Configuration

Drive folder ID stored in: `scripts/config/drive_locations.yaml`

```yaml
meetings:
  transcripts_inbox: "YOUR_FOLDER_ID"
```

## Typical Workflow

### Daily Processing
```bash
# Morning pull + full process
cd .
python3 Skills/meeting-ingestion/scripts/meeting_cli.py pull --batch-size 5
python3 Skills/meeting-ingestion/scripts/meeting_cli.py stage
python3 Skills/meeting-ingestion/scripts/meeting_cli.py process --batch-size 5
python3 Skills/meeting-ingestion/scripts/meeting_cli.py archive --execute
```

### Single Meeting
```bash
python3 Skills/meeting-ingestion/scripts/meeting_cli.py process \
    "./Personal/Meetings/Inbox/2026-01-26_David-x-Careerspan" \
    --blocks B01,B05,B08
```

## Troubleshooting

### "No transcript found"
- Ensure folder contains `.md` or `.txt` file
- Run `stage` first if raw file in Inbox root

### Orphaned blocks in Inbox
- Run `fix` to quarantine them to `_orphaned_blocks/`

### Processing fails
- Check transcript length (minimum ~100 chars)
- Verify `ZO_CLIENT_IDENTITY_TOKEN` is set

### Meeting stuck in "processing"
- Check `manifest.json` for errors
- Re-run `process` on that specific folder

## Migration Notes

This v2.0 rebuild replaces the v1.0 system that:
- Used folder name suffixes (`_[P]`, `_[B]`) for state
- Could dump blocks in Inbox root
- Had inconsistent folder structure

All state now lives in `manifest.json`.
