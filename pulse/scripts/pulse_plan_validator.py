#!/usr/bin/env python3
"""
Pulse Plan Validator

Validates that a build plan is complete before allowing build start.
Based on Theo's lesson: Plans are context vehicles, not spec documents.
An unfilled plan means the model will guess — and guessing compounds errors.

Usage:
    python3 pulse_plan_validator.py <slug>
    python3 pulse_plan_validator.py <slug> --fix  # Interactive mode to fill placeholders

Exit codes:
    0 = Plan is valid
    1 = Plan has issues (unfilled placeholders, missing sections)
"""

import argparse
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

BUILDS_DIR = Path("./N5/builds")

# Patterns that indicate unfilled template content
PLACEHOLDER_PATTERNS = [
    r'\{\{[A-Z_]+\}\}',           # {{PLACEHOLDER}}
    r'\[\[.+?\]\]',               # [[placeholder]]
    r'<[A-Z_]+>',                 # <PLACEHOLDER> (but not HTML tags)
    r'TODO:?\s',                  # TODO or TODO:
    r'FIXME:?\s',                 # FIXME
    r'XXX',                       # XXX marker
]

# Required sections in a valid plan
REQUIRED_SECTIONS = [
    "Objective",
    "Open Questions",
    "Phase 1",  # At least one phase
    "Success Criteria",
]

# Sections that should have content (not just headers)
CONTENT_REQUIRED = [
    "Objective",
    "Success Criteria",
]


def find_placeholders(content: str) -> list[tuple[int, str, str]]:
    """Find unfilled placeholders in content.
    
    Returns: [(line_number, placeholder, context)]
    """
    issues = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        for pattern in PLACEHOLDER_PATTERNS:
            matches = re.finditer(pattern, line)
            for match in matches:
                # Skip if it's in a code block showing the template itself
                if '```' in line or 'template' in line.lower():
                    continue
                # Skip HTML-like tags that are legitimate
                if pattern == r'<[A-Z_]+>' and match.group() in ['<URL>', '<ISO>']:
                    continue
                issues.append((i, match.group(), line.strip()[:60]))
    
    return issues


def check_required_sections(content: str) -> list[str]:
    """Check that required sections exist.
    
    Looks for both section headers (## Objective) and inline bold format (**Objective:**)
    """
    missing = []
    for section in REQUIRED_SECTIONS:
        # Look for markdown headers with the section name
        header_pattern = rf'^#+\s*.*{re.escape(section)}.*$'
        # Also look for bold inline format: **Objective:** followed by content
        inline_pattern = rf'\*\*{re.escape(section)}:\*\*\s*\S'
        
        has_header = re.search(header_pattern, content, re.MULTILINE | re.IGNORECASE)
        has_inline = re.search(inline_pattern, content, re.MULTILINE | re.IGNORECASE)
        
        if not has_header and not has_inline:
            missing.append(section)
    return missing


def check_section_content(content: str) -> list[str]:
    """Check that key sections have actual content, not just headers."""
    empty_sections = []
    
    for section in CONTENT_REQUIRED:
        # Find the section header
        pattern = rf'^(#+)\s*.*{re.escape(section)}.*$'
        match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        if not match:
            continue
        
        # Get the header level
        header_level = len(match.group(1))
        start = match.end()
        
        # Find the next section of same or higher level
        next_section = re.search(rf'^#{{{1},{header_level}}}\s', content[start:], re.MULTILINE)
        if next_section:
            section_content = content[start:start + next_section.start()]
        else:
            section_content = content[start:]
        
        # Check if there's actual content (not just whitespace and placeholders)
        cleaned = re.sub(r'\{\{[^}]+\}\}', '', section_content)
        cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)
        cleaned = cleaned.strip()
        
        if len(cleaned) < 20:  # Less than 20 chars of real content
            empty_sections.append(section)
    
    return empty_sections


def validate_plan(slug: str) -> dict:
    """Validate a build plan.
    
    Returns: {
        "valid": bool,
        "placeholders": [(line, placeholder, context)],
        "missing_sections": [str],
        "empty_sections": [str],
        "warnings": [str]
    }
    """
    plan_path = BUILDS_DIR / slug / "PLAN.md"
    
    if not plan_path.exists():
        return {
            "valid": False,
            "error": f"Plan not found: {plan_path}",
            "placeholders": [],
            "missing_sections": [],
            "empty_sections": [],
            "warnings": []
        }
    
    content = plan_path.read_text()
    
    placeholders = find_placeholders(content)
    missing_sections = check_required_sections(content)
    empty_sections = check_section_content(content)
    
    warnings = []
    
    # Check if Open Questions has unchecked items
    if re.search(r'^\s*-\s*\[\s*\]', content, re.MULTILINE):
        open_questions = re.findall(r'^\s*-\s*\[\s*\]\s*(.+)$', content, re.MULTILINE)
        if open_questions:
            warnings.append(f"{len(open_questions)} open questions still unchecked")
    
    # Check plan age
    try:
        # Look for created date in frontmatter
        created_match = re.search(r'^created:\s*(\d{4}-\d{2}-\d{2})', content, re.MULTILINE)
        if created_match:
            created = datetime.strptime(created_match.group(1), '%Y-%m-%d')
            age_days = (datetime.now() - created).days
            if age_days > 14:
                warnings.append(f"Plan is {age_days} days old — may need refresh")
    except:
        pass
    
    valid = (
        len(placeholders) == 0 and
        len(missing_sections) == 0 and
        len(empty_sections) == 0
    )
    
    return {
        "valid": valid,
        "placeholders": placeholders,
        "missing_sections": missing_sections,
        "empty_sections": empty_sections,
        "warnings": warnings
    }


def print_report(slug: str, result: dict):
    """Print validation report."""
    if result.get("error"):
        print(f"❌ {result['error']}")
        return
    
    print(f"\n{'='*60}")
    print(f"Plan Validation: {slug}")
    print(f"{'='*60}\n")
    
    if result["valid"]:
        print("✅ Plan is VALID — ready for build\n")
    else:
        print("❌ Plan has ISSUES — fix before starting build\n")
    
    if result["placeholders"]:
        print(f"📝 Unfilled Placeholders ({len(result['placeholders'])}):")
        for line, placeholder, context in result["placeholders"][:10]:
            print(f"   Line {line}: {placeholder}")
            print(f"      → {context}...")
        if len(result["placeholders"]) > 10:
            print(f"   ... and {len(result['placeholders']) - 10} more")
        print()
    
    if result["missing_sections"]:
        print(f"📋 Missing Required Sections:")
        for section in result["missing_sections"]:
            print(f"   - {section}")
        print()
    
    if result["empty_sections"]:
        print(f"📭 Empty Sections (need content):")
        for section in result["empty_sections"]:
            print(f"   - {section}")
        print()
    
    if result["warnings"]:
        print(f"⚠️  Warnings:")
        for warning in result["warnings"]:
            print(f"   - {warning}")
        print()
    
    if not result["valid"]:
        print("💡 Fix these issues before running: pulse start " + slug)
        print("   Or use: python3 pulse_plan_validator.py " + slug + " --fix")


def main():
    parser = argparse.ArgumentParser(description="Validate Pulse build plan")
    parser.add_argument("slug", help="Build slug")
    parser.add_argument("--fix", action="store_true", help="Interactive mode to fix placeholders")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Only output exit code")
    
    args = parser.parse_args()
    
    result = validate_plan(args.slug)
    
    if args.json:
        import json
        # Convert tuples to lists for JSON
        result["placeholders"] = [list(p) for p in result["placeholders"]]
        print(json.dumps(result, indent=2))
    elif args.quiet:
        pass
    else:
        print_report(args.slug, result)
    
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
