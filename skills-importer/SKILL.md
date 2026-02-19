---
name: skills-importer
description: Import skills from skills.sh and GitHub-hosted agentskills.io repositories into N5 OS. Transforms frontmatter, validates structure, and installs to Skills/ directory.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
created: 2026-02-07
last_edited: 2026-02-07
version: 1.0
provenance: skills-importer-build
---

# Skills Importer

Import high-quality skills from the skills.sh ecosystem and GitHub-hosted agentskills.io repositories into your N5 OS Skills/ directory. Automatically handles frontmatter transformation, file structure validation, and installation.

---

## Triggers

| Trigger | Description |
|---------|-------------|
| User wants to add skills from skills.sh | Import specific skill by name |
| User wants to browse available skills | List skills in a repository |
| User mentions obra/superpowers, vercel-labs, anthropics skills | Import from well-known high-quality repos |
| User wants to bulk import | Import all skills from a multi-skill repository |
| User references a GitHub repo with SKILL.md files | Import skills from any agentskills.io-compliant repo |

---

## Quick Start

### Import a specific skill
```bash
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/frontend-design
```

### List available skills in a repository
```bash
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills --list
```

### Preview what would be imported (dry run)
```bash
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/brainstorming --dry-run
```

### Import all skills from a repository
```bash
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers --all
```

---

## CLI Reference

### Command Structure
```bash
python3 Skills/skills-importer/scripts/import_skill.py <source> [options]
```

### Arguments
- **source**: GitHub reference in format:
  - `owner/repo/skill-name` - Import specific skill
  - `owner/repo` - Use with --list or --all for repository operations

### Options
- `--list` - List all available skills in the repository
- `--all` - Import all skills from the repository 
- `--dry-run` - Show transformation preview without writing files
- `--force` - Overwrite existing skills (default: skip if exists)
- `--dest <name>` - Custom destination directory name (default: skill name)

### Examples

**Import from different repository structures:**
```bash
# Repository with skills/ subdirectory (like vercel-labs)
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills/react-best-practices

# Repository with skills at root (like anthropics)
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/frontend-design

# Import with custom name to avoid conflicts
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/frontend-design --dest my-frontend-guide
```

**Bulk operations:**
```bash
# See what's available first
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers --list

# Import everything (be selective - only import what you need)
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers --all --dry-run
```

---

## Frontmatter Transformation

The importer automatically transforms skills.sh frontmatter to N5 format:

<details>
<summary>View transformation rules</summary>

**Input (skills.sh format):**
```yaml
---
name: frontend-design
description: Create distinctive frontend interfaces...
license: Complete terms in LICENSE.txt
---
```

**Output (N5 format):**
```yaml
---
name: frontend-design
description: Create distinctive frontend interfaces...
compatibility: Imported from skills.sh
metadata:
  author: anthropics (imported)
  source: anthropics/skills/frontend-design
  imported_at: 2026-02-07
created: 2026-02-07
last_edited: 2026-02-07
version: 1.0
provenance: skills-importer
---
```

**Key transformations:**
- Preserves original `name` and `description`
- Adds N5-required fields (`created`, `last_edited`, `version`, `provenance`)
- Sets `compatibility` if not present
- Tracks import lineage in `metadata.source`
- Attributes to original author in `metadata.author`

</details>

---

## Curated Skills

High-value skills from the skills.sh ecosystem organized by category. Use these as starting points for importing skills that match your workflow needs.

### Frontend & Development
```bash
# React best practices (19K+ installs)
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills/react-best-practices

# Web design guidelines
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills/web-design-guidelines

# Frontend design patterns
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/frontend-design
```

### Development Practices
```bash
# Systematic debugging (6.5K installs)
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/systematic-debugging

# Test-driven development (5.7K installs)
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/test-driven-development

# Writing plans methodology (5.6K installs)
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/writing-plans
```

### Thinking & Brainstorming
```bash
# Brainstorming techniques (11.5K installs)
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/brainstorming
```

### Document Handling
```bash
# PDF processing
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/pdf

# Word document handling
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/docx

# Excel/spreadsheet processing  
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/xlsx
```

### Database & Backend
```bash
# Supabase PostgreSQL best practices (12.4K installs)
python3 Skills/skills-importer/scripts/import_skill.py supabase/agent-skills/supabase-postgres-best-practices
```

### Import Popular Collections
```bash
# Browse obra's superpowers collection
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers --list

# Browse Anthropic's skills
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills --list

# Browse Vercel's agent skills
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills --list
```

---

## Validation & Safety

The importer includes several safety checks:

- **Existence check**: Verifies SKILL.md exists at source before importing
- **Name validation**: Ensures `name` field is present in frontmatter
- **Collision prevention**: Won't overwrite existing skills without `--force`
- **Structure validation**: Warns if expected directories (scripts/) are missing
- **Dry run mode**: Always test with `--dry-run` before committing to imports

### Verification Checklist

After import, verify your new skill:

- [ ] `Skills/<skill-name>/SKILL.md` exists with valid N5 frontmatter
- [ ] `Skills/<skill-name>/scripts/` contains executable tools (if applicable)
- [ ] Skill documentation is readable and actionable
- [ ] Tool references work with N5 OS (Zo adapts automatically)
- [ ] No conflicts with existing skill names

---

## Troubleshooting

**"Skill not found" errors:**
- Verify the GitHub path is correct (check repository structure)
- Try both main and master branch (auto-detected)
- Some skills may be in a `skills/` subdirectory

**Tool compatibility issues:**
- Skills reference tools by name (e.g., "Claude Code") 
- Zo automatically adapts tool calls to available N5 tools at runtime
- Check skill documentation for N5-specific usage notes

**Import conflicts:**
- Use `--dest <custom-name>` to avoid name collisions
- Use `--force` to overwrite (be careful!)
- Check `Skills/` directory for existing skills with similar names

**Large imports:**
- Use `--dry-run` first to preview bulk imports
- Import selectively rather than using `--all` on large repositories
- Skills.sh install counts indicate quality and popularity

---

## Advanced Usage

### Custom Repository Support

Import from any GitHub repository with agentskills.io-compliant structure:

```bash
# Import from your own skills repo
python3 Skills/skills-importer/scripts/import_skill.py your-username/my-skills/custom-skill

# Import from organization repos
python3 Skills/skills-importer/scripts/import_skill.py acme-corp/ai-skills/data-analysis
```

### Batch Import Scripts

Create shell scripts for importing curated skill sets:

```bash
#!/bin/bash
# Import my essential development skills

echo "Importing development essentials..."

python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/systematic-debugging
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/writing-plans  
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills/react-best-practices

echo "Import complete!"
```

---

## References

| Document | Content |
|----------|---------|
| [format-mapping.md](references/format-mapping.md) | Detailed frontmatter transformation rules |
| [curated-skills.md](references/curated-skills.md) | Expanded list of high-value skills by category |