---
name: zo-substrate
description: |
  Generalized Zo-to-Zo skill exchange system. Push and pull skills between any two Zo Computer
  instances using a shared GitHub repository as the substrate. Includes bundling with checksums,
  local context awareness, setup wizard, and dry-run support. Fully configurable — no hardcoded
  identities or repo URLs.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  version: "1.0.0"
  created: "2026-02-12"
created: 2026-02-12
last_edited: 2026-02-12
version: 1.0
provenance: con_z4YCK2Nb5oZ3tEoZ
---

# Zo Substrate

Bidirectional skill exchange between any two Zo Computer instances, using GitHub as shared substrate.

## Quick Start

```bash
# 1. Check prerequisites
python3 Skills/zo-substrate/scripts/substrate.py setup check

# 2. Initialize config (creates substrate.yaml + optional GitHub repo)
python3 Skills/zo-substrate/scripts/substrate.py setup init \
  --identity my-zo \
  --partner their-zo \
  --repo myuser/our-substrate \
  --create-repo

# 3. Push skills to the substrate
python3 Skills/zo-substrate/scripts/substrate.py push --dry-run
python3 Skills/zo-substrate/scripts/substrate.py push

# 4. Pull skills from the substrate (on the other Zo)
python3 Skills/zo-substrate/scripts/substrate.py pull --dry-run
python3 Skills/zo-substrate/scripts/substrate.py pull

# 5. Check status
python3 Skills/zo-substrate/scripts/substrate.py status
```

## Architecture

```
Zo A                          GitHub Substrate              Zo B
┌──────────┐                 ┌──────────────┐              ┌──────────┐
│ Skills/  │  push           │ repo/Skills/ │  pull        │ Skills/  │
│ skill-x/ │ ──────────────► │  skill-x/    │ ◄─────────── │ skill-x/ │
│ skill-y/ │                 │  skill-y/    │              │ skill-y/ │
│          │                 │  MANIFEST    │              │          │
│ config/  │                 └──────────────┘              │ config/  │
│ substrate│                                               │ substrate│
│ .yaml    │                                               │ .yaml    │
└──────────┘                                               └──────────┘
```

Both Zo instances configure the same GitHub repo. Either can push or pull.

## Commands

### Push — sync skills TO the substrate repo
```bash
substrate.py push                        # Push all configured skills
substrate.py push --skills skill-a,skill-b  # Push specific skills
substrate.py push --dry-run              # Preview what would be pushed
```

### Pull — sync skills FROM the substrate repo
```bash
substrate.py pull                        # Pull all available skills
substrate.py pull --skills skill-a       # Pull specific skills
substrate.py pull --dry-run              # Preview what would be pulled
substrate.py pull --verbose              # Detailed output
```

### Status — view sync state
```bash
substrate.py status                      # Show last push/pull, discoverable skills
```

### Setup — configure the substrate connection
```bash
substrate.py setup check                 # Verify git, gh, auth
substrate.py setup init \
  --identity va \
  --partner <YOUR_INSTANCE> \
  --repo <YOUR_GITHUB>/our-substrate \
  --create-repo                          # Creates repo if it doesn't exist
```

### Bundle — create/validate skill packages
```bash
substrate.py bundle create my-skill      # Create tarball bundle
substrate.py bundle validate /path.tar.gz  # Validate a bundle
substrate.py bundle list                 # List discoverable skills
```

### Context — local awareness snapshot
```bash
substrate.py context refresh             # Scan workspace and save snapshot
substrate.py context query               # Show summary
substrate.py context query --what skills --detail  # Detailed skill list
substrate.py context query --what json   # Raw JSON output
```

## Configuration

Config lives at `Skills/zo-substrate/config/substrate.yaml`. Create from example:

```bash
cp Skills/zo-substrate/config/substrate.yaml.example Skills/zo-substrate/config/substrate.yaml
```

Or use `substrate.py setup init` to generate it from arguments.

### Key Config Fields

| Field | Description |
|-------|-------------|
| `identity.name` | This Zo's short name (used in commits, manifests) |
| `partner.name` | The other Zo's short name |
| `substrate.repo` | GitHub repo (e.g., `user/repo`) |
| `substrate.clone_method` | `https` (default) or `ssh` |
| `export.skills` | Explicit list of skills to push (empty = auto-detect) |
| `export.auto_detect` | If true, discover all skills with SKILL.md |
| `export.exclude` | Skills to never export (default: `zo-substrate`) |
| `pull.install_dir` | Where to install pulled skills (default: `Skills`) |
| `pull.backup_existing` | Back up before overwriting (default: true) |

## Requirements

- Git 2.30+
- GitHub CLI (`gh`) for repo creation
- Python 3.9+
- PyYAML (`pip install pyyaml`)
- `GITHUB_TOKEN` in environment or `gh auth login` completed

## How It Works

1. **Push** clones the substrate repo to `/tmp`, copies configured skills into `Skills/`, updates `MANIFEST.json`, commits, and pushes.
2. **Pull** clones the substrate repo, reads `MANIFEST.json`, and copies skills into the local workspace (with backups).
3. **State** is tracked in `N5/data/zo-substrate/` (configurable) — last push/pull timestamps, skill lists, git SHAs.
4. **Bundles** are tarballs with metadata.json and SHA-256 checksums for offline/manual transfer.
5. **Context** scans the local workspace to build an awareness snapshot of installed capabilities.

## Safety

- Push never modifies the local workspace
- Pull backs up existing skills before overwriting (configurable)
- Dry-run support on all mutating commands
- No hardcoded identities — everything is in config
- MANIFEST.json tracks provenance (who pushed, when, what SHA)
- All operations logged to `substrate.log`
