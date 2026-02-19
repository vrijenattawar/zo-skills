#!/usr/bin/env python3
"""Scaffold a new skill directory structure."""

import argparse
import os
import re
from pathlib import Path

SKILL_TEMPLATE = '''---
name: {name}
description: |
  TODO: Describe what this skill does and when to use it.
---

# {title}

## Overview

TODO: What this skill does.

## Quick Start

```bash
python3 Skills/{name}/scripts/main.py --help
```

## Usage

TODO: Detailed usage instructions.
'''

def scaffold_skill(name: str, base_path: str = "Skills"):
    """Create skill directory structure."""
    skill_dir = Path(base_path) / name
    
    if skill_dir.exists():
        print(f"Error: {skill_dir} already exists")
        return False
    
    # Create directories
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "references").mkdir()
    (skill_dir / "assets").mkdir()
    
    # Create SKILL.md
    title = name.replace('-', ' ').title()
    (skill_dir / "SKILL.md").write_text(
        SKILL_TEMPLATE.format(name=name, title=title)
    )
    
    # Create placeholder files
    (skill_dir / "scripts" / ".gitkeep").touch()
    (skill_dir / "references" / ".gitkeep").touch()
    (skill_dir / "assets" / ".gitkeep").touch()
    
    print(f"✓ Created {skill_dir}/")
    print(f"  - SKILL.md")
    print(f"  - scripts/")
    print(f"  - references/")
    print(f"  - assets/")
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Scaffold a new skill')
    parser.add_argument('name', help='Skill name (slug format, e.g. my-skill)')
    parser.add_argument('--base', default='Skills', help='Base directory')
    args = parser.parse_args()
    
    # Validate name
    if not re.match(r'^[a-z][a-z0-9-]*$', args.name):
        print("Error: Name must be lowercase letters, numbers, hyphens only")
        return 1
    
    if scaffold_skill(args.name, args.base):
        return 0
    return 1

if __name__ == '__main__':
    exit(main())