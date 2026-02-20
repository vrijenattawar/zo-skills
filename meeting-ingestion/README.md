# Meeting Ingestion

A Zo Computer skill for processing meeting transcripts into structured intelligence blocks.

## What It Does

This skill automates the entire meeting transcript pipeline:

1. **Pull** — Downloads transcripts from Google Drive
2. **Stage** — Organizes raw files into processing folders
3. **Process** — Generates intelligence blocks (recaps, action items, stakeholder intel, decisions, etc.)
4. **Archive** — Moves completed meetings to weekly folders

```
Google Drive → Inbox → Processed Folders → Weekly Archive
```

## Intelligence Blocks Generated

| Block | Description |
|-------|-------------|
| B01 | Detailed recap |
| B02 | Commitments made |
| B03 | Decisions with rationale |
| B05 | Action items |
| B08 | Stakeholder intelligence |
| B21 | Key moments |
| B26 | Meeting metadata |
| + more | Conditional blocks based on content |

## Installation

### Prerequisites

- [Zo Computer](https://zo.computer) account
- Google Drive integration connected in Zo
- A Drive folder where your transcripts land (from Tactiq, Otter, Fireflies, etc.)

### Setup

```bash
# Clone into your Skills folder
cd ./Skills
git clone https://github.com/<YOUR_GITHUB_USER>/meeting-ingestion.git

# Run the bootloader (surveys your environment first)
python3 meeting-ingestion/bootloader.py
```

The bootloader will:
- Survey your existing folder structure and conventions
- Check for conflicts with existing meeting systems
- Propose an integration plan for your review
- Only make changes after you approve

### Quick Start (after installation)

```bash
# Check status
python3 Skills/meeting-ingestion/scripts/meeting_cli.py status

# Run the full pipeline
python3 Skills/meeting-ingestion/scripts/meeting_cli.py pull
python3 Skills/meeting-ingestion/scripts/meeting_cli.py stage
python3 Skills/meeting-ingestion/scripts/meeting_cli.py process
python3 Skills/meeting-ingestion/scripts/meeting_cli.py archive --execute
```

## Configuration

After running the bootloader, you'll need to provide:

1. **Google Drive folder ID** — The folder where transcripts are deposited
2. **Meeting archive location** — Where processed meetings should live (default: `Personal/Meetings/`)

## How It Works

### Folder Structure

```
Personal/Meetings/
├── Inbox/                              # Processing queue
│   └── 2026-02-05_John-x-Acme/
│       ├── transcript.md
│       ├── manifest.json               # Tracks processing state
│       ├── B01_DETAILED_RECAP.md
│       └── B05_ACTION_ITEMS.md
└── Week-of-2026-02-03/                 # Archived meetings
    └── 2026-02-05_John-x-Acme/
```

### Processing States

| Status | Meaning |
|--------|---------|
| `staged` | Ready for processing |
| `processing` | Block generation in progress |
| `complete` | All blocks generated |
| `archived` | Moved to weekly folder |

### LLM-Powered Block Selection

The skill uses LLM analysis to intelligently select which blocks to generate based on transcript content:

- Detects meeting type (external, internal, sales, investor)
- Identifies relevant conditional blocks
- Catches "Zo Take Heed" patterns (e.g., "Zo, draft a blurb about...")

## Commands

| Command | Description |
|---------|-------------|
| `status` | Show queue status |
| `pull` | Download from Google Drive |
| `stage` | Prepare transcripts for processing |
| `process` | Generate intelligence blocks |
| `archive` | Move completed meetings to weekly folders |
| `fix` | Repair malformed inbox state |

All commands support `--dry-run` to preview changes.

## License

MIT

## Credits

Built for [Zo Computer](https://zo.computer). Originally developed by [@<YOUR_GITHUB_USER>](https://github.com/<YOUR_GITHUB_USER>).
