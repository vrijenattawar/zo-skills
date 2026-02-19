---
name: prompt-to-skill
description: |
  Convert complex prompts into reusable skills. Assesses prompts for conversion eligibility
  and scaffolds new skill directory structures. Use when prompts have grown complex with
  multiple phases, script references, or structured output requirements.
---

# Prompt to Skill

## Overview

This skill converts complex prompts into reusable skills, helping maintain a clean prompt library while promoting reusable, well-structured workflows. It provides assessment tools to determine conversion eligibility and scaffolding tools to create proper skill structures.

## Quick Start

```bash
# Assess a prompt for conversion eligibility
python3 Skills/prompt-to-skill/scripts/assess.py "Prompts/MyPrompt.prompt.md"

# Create a new skill structure
python3 Skills/prompt-to-skill/scripts/scaffold.py my-new-skill
```

## When to Use This Skill

Use this skill when you encounter prompts that:
- Have grown to 200+ lines
- Reference multiple scripts or external tools
- Contain multiple phases or steps
- Require structured output (JSON/YAML schemas)
- Reference other prompts or skills
- Have complex file manipulation requirements

## Eligibility Criteria

The assessment script evaluates prompts based on:

- **Length**: 200+ lines indicates complexity
- **Script references**: Use of `python3`, `bun`, or `N5/scripts/`
- **Phase structure**: Multi-step workflows with phases
- **Schema requirements**: JSON/YAML output specifications
- **Prompt references**: Dependencies on other prompts
- **File operations**: Multiple file manipulations
- **Code blocks**: Extensive embedded code samples

**Scoring thresholds:**
- ≥15: Strong conversion candidate
- 8-14: Consider conversion based on context
- <8: Keep as prompt

## Conversion Process

1. **Assess**: Run assessment to get eligibility score
2. **Plan**: Determine what scripts, assets, and documentation are needed
3. **Scaffold**: Create the skill directory structure
4. **Extract**: Move reusable logic from prompt to skill scripts
5. **Document**: Write comprehensive SKILL.md with examples
6. **Test**: Verify the skill works as expected
7. **Update**: Replace original prompt with skill reference

## Usage

### Assessment

```bash
# Basic assessment
python3 Skills/prompt-to-skill/scripts/assess.py "Prompts/MyPrompt.prompt.md"

# JSON output for scripting
python3 Skills/prompt-to-skill/scripts/assess.py "Prompts/MyPrompt.prompt.md" --json
```

### Scaffolding

```bash
# Create new skill in default Skills/ directory
python3 Skills/prompt-to-skill/scripts/scaffold.py my-skill-name

# Create in custom location
python3 Skills/prompt-to-skill/scripts/scaffold.py my-skill-name --base /path/to/directory
```

## Implementation Notes

- Skill names must be lowercase with hyphens only
- The scaffold creates a complete directory structure with placeholders
- The assessment uses weighted scoring to prioritize complexity indicators
- All created skills follow the Agent Skills specification