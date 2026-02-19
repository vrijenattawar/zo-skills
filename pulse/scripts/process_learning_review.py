#!/usr/bin/env python3
"""
Process a learning promotion review batch.

Reads a review markdown file, extracts marked learnings, and promotes them
to the appropriate destination based on category:
- system → N5/learnings/SYSTEM_LEARNINGS.json
- personal → Personal/Knowledge/Learnings/*.md (then indexed to N5 Brain)

Usage:
    python3 Skills/pulse/scripts/process_learning_review.py <review_file.md> [--dry-run]
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SYSTEM_LEARNINGS_PATH = Path("./N5/learnings/SYSTEM_LEARNINGS.json")
PERSONAL_LEARNINGS_DIR = Path("./Personal/Knowledge/Learnings")


def parse_review_file(filepath: Path) -> tuple[str, list[dict]]:
    """
    Parse review markdown file.
    Returns (category, list of marked learnings).
    """
    with open(filepath) as f:
        content = f.read()
    
    # Extract category from frontmatter
    category_match = re.search(r'^category:\s*(\w+)', content, re.MULTILINE)
    category = category_match.group(1) if category_match else "system"
    
    # Find all marked learnings [x]
    # Pattern: - [x] **build#index** (score: X.XX ×N)
    #            > Learning text
    #            - Sources: ...
    #            - Tags: ...
    pattern = r'- \[x\] \*\*([^*]+)\*\* \(score: ([\d.]+)(?:\s*×(\d+))?\)\s*\n\s*> ([^\n]+)\s*\n\s*- Sources: ([^\n]+)\s*\n\s*- Tags: ([^\n]+)'
    
    matches = re.findall(pattern, content, re.IGNORECASE)
    
    learnings = []
    for match in matches:
        ref, score, occurrence, text, sources, tags = match
        learnings.append({
            "ref": ref.strip(),
            "score": float(score),
            "occurrence_count": int(occurrence) if occurrence else 1,
            "text": text.strip(),
            "sources": [s.strip() for s in sources.split(",")],
            "tags": [t.strip() for t in tags.split(",") if t.strip() and t.strip() != "untagged"],
        })
    
    return category, learnings


def promote_to_system(learning: dict) -> bool:
    """Add learning to SYSTEM_LEARNINGS.json."""
    # Load existing
    if SYSTEM_LEARNINGS_PATH.exists():
        with open(SYSTEM_LEARNINGS_PATH) as f:
            data = json.load(f)
    else:
        data = {
            "meta": {
                "description": "System-wide learnings that apply across all builds",
                "created": datetime.now().strftime("%Y-%m-%d"),
                "version": "2.0"
            },
            "learnings": []
        }
    
    # Check for duplicates
    existing_texts = {l.get("text", "").lower() for l in data.get("learnings", [])}
    if learning["text"].lower() in existing_texts:
        return False
    
    # Add new learning
    new_entry = {
        "text": learning["text"],
        "source": "promotion",
        "added_at": datetime.now().isoformat(),
        "tags": learning["tags"],
        "origin_build": learning["sources"][0] if learning["sources"] else "unknown",
        "confidence": learning["score"],
        "validated_count": learning["occurrence_count"],
        "last_validated": None,
        "decay_days": 30,
        "expires_at": None,
        "status": "active",
        "disputed_by": None,
        "dispute_reason": None
    }
    
    data["learnings"].append(new_entry)
    
    with open(SYSTEM_LEARNINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)
    
    return True


def promote_to_personal(learning: dict) -> Path:
    """
    Create a markdown file in Personal/Knowledge/Learnings/ and return its path.
    File will be indexed to N5 Brain afterward.
    """
    PERSONAL_LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate filename from first few words + timestamp
    slug_words = re.sub(r'[^a-z0-9\s]', '', learning["text"].lower()).split()[:5]
    slug = "-".join(slug_words)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{slug}-{timestamp}.md"
    filepath = PERSONAL_LEARNINGS_DIR / filename
    
    # Determine domain from tags or sources
    domain = "general"
    domain_tags = ["adhd", "hiring", "<YOUR_PRODUCT>", "product", "ux", "assessment", "research"]
    for tag in learning["tags"]:
        if tag.lower() in domain_tags:
            domain = tag.lower()
            break
    
    # Create markdown content
    content = f"""---
created: {datetime.now().strftime("%Y-%m-%d")}
last_edited: {datetime.now().strftime("%Y-%m-%d")}
version: 1.0
provenance: learning-promotion
domain: {domain}
confidence: {learning["score"]}
occurrence_count: {learning["occurrence_count"]}
sources: {", ".join(learning["sources"])}
tags: [{", ".join(learning["tags"])}]
---

# {learning["text"][:80]}{"..." if len(learning["text"]) > 80 else ""}

{learning["text"]}

## Context

This insight emerged from {learning["occurrence_count"]} build{"s" if learning["occurrence_count"] > 1 else ""}: {", ".join(learning["sources"])}.

## Tags

{", ".join([f"`{t}`" for t in learning["tags"]]) if learning["tags"] else "_untagged_"}
"""
    
    with open(filepath, "w") as f:
        f.write(content)
    
    return filepath


def index_to_brain(filepaths: list[Path]) -> bool:
    """Index the created markdown files to the N5 Brain."""
    if not filepaths:
        return True
    
    paths_str = " ".join([str(p) for p in filepaths])
    cmd = f"python3 ./N5/scripts/memory_indexer.py {paths_str}"
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Warning: Brain indexing failed: {result.stderr}", file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"Warning: Brain indexing error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Process learning promotion review batch")
    parser.add_argument("review_file", type=Path, help="Path to review markdown file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be promoted without writing")
    args = parser.parse_args()
    
    if not args.review_file.exists():
        print(f"Error: Review file not found: {args.review_file}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Parsing review file: {args.review_file}", file=sys.stderr)
    category, learnings = parse_review_file(args.review_file)
    
    print(f"Found {len(learnings)} marked learnings (category: {category})", file=sys.stderr)
    
    if not learnings:
        print("No learnings marked for promotion.", file=sys.stderr)
        return
    
    if args.dry_run:
        print(f"\n=== DRY RUN ({category.upper()}) ===", file=sys.stderr)
        for l in learnings:
            print(f"  Would promote: {l['text'][:80]}...", file=sys.stderr)
        return
    
    promoted = 0
    skipped = 0
    personal_files = []
    
    for learning in learnings:
        if category == "system":
            if promote_to_system(learning):
                promoted += 1
                print(f"  ✓ Promoted to SYSTEM_LEARNINGS: {learning['text'][:60]}...", file=sys.stderr)
            else:
                skipped += 1
                print(f"  ⊘ Skipped (duplicate): {learning['text'][:60]}...", file=sys.stderr)
        else:  # personal
            filepath = promote_to_personal(learning)
            personal_files.append(filepath)
            promoted += 1
            print(f"  ✓ Created: {filepath.name}", file=sys.stderr)
    
    # Index personal learnings to brain
    if personal_files:
        print(f"\nIndexing {len(personal_files)} files to N5 Brain...", file=sys.stderr)
        if index_to_brain(personal_files):
            print("  ✓ Brain indexing complete", file=sys.stderr)
        else:
            print("  ⚠ Brain indexing had issues (files still created)", file=sys.stderr)
    
    print(f"\n=== Summary ===", file=sys.stderr)
    print(f"Promoted: {promoted}", file=sys.stderr)
    print(f"Skipped: {skipped}", file=sys.stderr)
    
    if category == "system":
        print(f"Destination: {SYSTEM_LEARNINGS_PATH}", file=sys.stderr)
    else:
        print(f"Destination: {PERSONAL_LEARNINGS_DIR}/", file=sys.stderr)
    
    # Mark review file as processed
    processed_marker = f"\n---\n\n**Processed:** {datetime.now().isoformat()}\n**Promoted:** {promoted}\n**Skipped:** {skipped}\n"
    with open(args.review_file, "a") as f:
        f.write(processed_marker)
    
    print(f"  Review file marked as processed", file=sys.stderr)


if __name__ == "__main__":
    main()
