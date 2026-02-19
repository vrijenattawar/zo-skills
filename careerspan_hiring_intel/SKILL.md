---
name: <YOUR_PRODUCT>-hiring-intel
created: 2026-02-06
last_edited: 2026-02-08
version: 1.1
provenance: con_JYayBp0LOozCjnVT
description: |
  Shared library for <YOUR_PRODUCT> Hiring Intelligence. Contains canonical implementations
  of Hiring POV generation and related employer analysis operations.
  
  Ensures consistent inputs/outputs across all <YOUR_PRODUCT> skills.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
---
# <YOUR_PRODUCT> Hiring Intelligence

## Purpose

This skill provides **canonical implementations** for hiring-related intelligence operations used across the <YOUR_PRODUCT> pipeline:

1. **Hiring POV Generation** — Structured analysis of what employers value
2. **Future**: Employer research, culture analysis, role taxonomy, etc.

## Why This Exists

Multiple skills need to generate Hiring POVs:
- `<YOUR_PRODUCT>-jd-intake`: Primary generation when JDs arrive
- `candidate-synthesis`: Fallback when POV missing for candidate processing

Without a shared module, each skill implements POV generation differently → divergent outputs → inconsistent candidate matching.

## Hiring POV Generation

### Usage

```python
import sys
from pathlib import Path

# Add Skills to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from <YOUR_PRODUCT>_hiring_intel.scripts.hiring_pov import (
    generate_hiring_pov,
    format_pov_markdown,
    generate_hiring_pov_with_markdown
)

# Generate structured POV + markdown
pov, markdown = generate_hiring_pov_with_markdown(
    jd_text="...",
    employer_name="TechCorp",
    role_title="Senior Engineer"
)
```

### Output Schema

```json
{
  "explicit_requirements": ["string"],
  "implicit_filters": ["string"],
  "trait_signals": ["string"],
  "red_flags": ["string"],
  "story_types_valued": ["string"],
  "validation_questions": ["string"],
  "culture_markers": ["string"],
  "role_summary": "string",
  "missing_info": ["string"],
  "_meta": {
    "employer_name": "string",
    "role_title": "string",
    "source": "<YOUR_PRODUCT>_hiring_intel.hiring_pov.generate_hiring_pov",
    "jd_length": 1234
  }
}
```

### CLI Testing

```bash
python3 Skills/<YOUR_PRODUCT>_hiring_intel/scripts/hiring_pov.py \
  --jd-file /path/to/jd.txt \
  --employer "TechCorp" \
  --role "Senior Engineer" \
  --output-json pov.json \
  --output-md pov.md
```

## Files

```
Skills/<YOUR_PRODUCT>_hiring_intel/
├── SKILL.md                          # This file
├── scripts/
│   └── hiring_pov.py                 # Canonical POV generator
└── assets/prompts/
    └── hiring_pov_generation.md      # LLM prompt template
```

## Dependencies

- Python 3.12+
- `/zo/ask` API for LLM calls
- `requests` library

## Integration

Import from any <YOUR_PRODUCT> skill:

```python
import sys
from pathlib import Path

# Add Skills to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from <YOUR_PRODUCT>_hiring_intel.scripts.hiring_pov import generate_hiring_pov_with_markdown
```
