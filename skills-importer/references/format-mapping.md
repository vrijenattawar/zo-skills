---
created: 2026-02-07
last_edited: 2026-02-07
version: 1.0
provenance: skills-importer-build
---

# Frontmatter Format Mapping

## Skills.sh → N5 Transformation Rules

This document details how the skills-importer transforms frontmatter from skills.sh format to N5 OS format.

### Core Field Mapping

| Skills.sh Field | N5 Field | Transformation Rule |
|----------------|----------|-------------------|
| `name` | `name` | **Preserved exactly** - Used as skill directory name |
| `description` | `description` | **Preserved exactly** - Core skill description |
| `license` | *(removed)* | Dropped - N5 uses global licensing |
| `compatibility` | `compatibility` | Set to "Imported from skills.sh" if not present |
| `metadata` | `metadata` | **Enhanced** - Original preserved + import tracking |

### N5-Required Fields (Added)

| Field | Value | Purpose |
|-------|--------|---------|
| `created` | Current date (YYYY-MM-DD) | N5 standard - marks creation date |
| `last_edited` | Current date (YYYY-MM-DD) | N5 standard - tracks modifications |
| `version` | "1.0" | N5 standard - reset for imported skills |
| `provenance` | "skills-importer" | N5 standard - tracks generation source |

### Metadata Enhancement

The `metadata` object is enhanced with import tracking:

```yaml
# Original skills.sh metadata (if present)
metadata:
  tags: ["frontend", "react"]
  difficulty: "intermediate"

# N5 enhanced metadata  
metadata:
  tags: ["frontend", "react"]        # preserved
  difficulty: "intermediate"         # preserved
  author: "anthropics (imported)"    # added - from GitHub owner
  source: "anthropics/skills/frontend-design"  # added - full lineage
  imported_at: "2026-02-07"         # added - import timestamp
```

### Author Attribution Rules

| Source Pattern | Author Field Value |
|----------------|-------------------|
| `anthropics/skills/skill-name` | "anthropics (imported)" |
| `vercel-labs/agent-skills/skill-name` | "vercel-labs (imported)" |
| `obra/superpowers/skill-name` | "obra (imported)" |
| `any-owner/repo/skill-name` | "any-owner (imported)" |

### Complete Transformation Example

**Input (skills.sh):**
```yaml
---
name: frontend-design
description: Create distinctive frontend interfaces with modern design principles
license: MIT
compatibility: Claude Projects
metadata:
  tags: ["design", "frontend", "ui"]
  difficulty: "intermediate"
---
```

**Output (N5):**
```yaml
---
name: frontend-design
description: Create distinctive frontend interfaces with modern design principles
compatibility: Imported from skills.sh
metadata:
  tags: ["design", "frontend", "ui"]
  difficulty: "intermediate"
  author: "anthropics (imported)"
  source: "anthropics/skills/frontend-design"
  imported_at: "2026-02-07"
created: 2026-02-07
last_edited: 2026-02-07
version: 1.0
provenance: skills-importer
---
```

## Tool Reference Handling

**Strategy: Runtime Adaptation (No Transformation)**

Skills.sh skills may reference tools not directly available in N5 OS. Rather than attempting complex mapping during import, we preserve original tool references and let Zo adapt them at runtime.

### Common Tool References

| Skills.sh Reference | N5 Adaptation | Notes |
|-------------------|---------------|-------|
| "Claude Code" | Zo's coding tools | Zo maps to available coding capabilities |
| "Web Search" | `web_search` tool | Direct mapping |
| "File Management" | N5 file tools | Zo uses `read_file`, `edit_file`, etc. |
| "Image Generation" | `generate_image` | Direct mapping |

### Runtime Adaptation Benefits

1. **Simplicity** - No complex mapping logic during import
2. **Flexibility** - Zo can use best available tool for the task
3. **Maintainability** - No need to update mappings as tools evolve
4. **Accuracy** - Context-aware tool selection vs. static mapping

### Skill Documentation Notes

Imported skills include a note about tool adaptation:

```markdown
**Note:** This skill was imported from skills.sh. Tool references are automatically 
adapted to N5 OS tools by Zo at runtime. No manual modification required.
```

## Edge Cases & Special Handling

### Missing Required Fields

| Missing Field | Default Value | Behavior |
|---------------|---------------|----------|
| `name` | *(none)* | **Import fails** - Name is mandatory |
| `description` | *(none)* | **Import fails** - Description is mandatory |
| `compatibility` | "Imported from skills.sh" | Auto-set if missing |
| `metadata` | `{}` | Empty object created |

### Invalid YAML Frontmatter

- **Malformed YAML**: Import fails with clear error message
- **Missing frontmatter**: Import fails - requires valid YAML header
- **No closing `---`**: Attempts to parse, fails gracefully if invalid

### Name Conflicts

- **Existing skill**: Import skipped unless `--force` used
- **Invalid characters**: Name sanitized (spaces→hyphens, special chars removed)
- **Reserved names**: No restrictions - user responsibility

### Large Metadata Objects

- **Preservation**: All original metadata preserved regardless of size
- **Merge strategy**: Original fields + import tracking fields
- **Conflicts**: Import fields take precedence if naming conflicts exist

## Source Lineage Tracking

Every imported skill maintains complete lineage in `metadata.source`:

### Source Format
```
{github_owner}/{repository_name}/{skill_path}
```

### Examples
- `anthropics/skills/frontend-design`
- `vercel-labs/agent-skills/react-best-practices`
- `obra/superpowers/systematic-debugging`
- `custom-org/private-skills/data-analysis`

### Benefits
- **Updates**: Can check original source for updates
- **Attribution**: Clear credit to original authors
- **Debugging**: Trace issues back to source
- **Community**: Enable contribution back to upstream

## Repository Structure Detection

The importer handles different GitHub repository structures automatically:

### Pattern 1: Root-level Skills
```
repo/
├── skill-name/
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
```
**Source format**: `owner/repo/skill-name`

### Pattern 2: Skills Subdirectory  
```
repo/
├── skills/
│   ├── skill-name/
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   └── references/
```
**Source format**: `owner/repo/skill-name` (auto-detects `skills/` prefix)

### Pattern 3: Mixed Structure
Some repositories use both patterns - importer tries root first, then `skills/` subdirectory.

## Validation Rules

### Pre-Import Validation
- [ ] SKILL.md exists at source URL
- [ ] SKILL.md contains valid YAML frontmatter
- [ ] `name` field present and non-empty
- [ ] `description` field present and non-empty
- [ ] Destination directory doesn't exist (unless `--force`)

### Post-Import Validation  
- [ ] All source files copied successfully
- [ ] Frontmatter transformation completed
- [ ] N5 required fields present
- [ ] No YAML syntax errors in output

### Warning Conditions
- Missing `scripts/` directory (skill may be documentation-only)
- Very large skill size (>50MB total)
- Unusual file extensions in scripts/ (may need manual review)

This comprehensive mapping ensures imported skills integrate seamlessly with N5 OS while preserving their original functionality and attribution.