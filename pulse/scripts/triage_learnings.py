#!/usr/bin/env python3
"""
Triage build learnings for promotion.

Scans all BUILD_LESSONS.json files, deduplicates via LLM semantic clustering,
scores for system-worthiness, classifies as system vs personal, and generates
two HITL review batches.

Usage:
    python3 Skills/pulse/scripts/triage_learnings.py [--threshold 0.6] [--dry-run]
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

BUILDS_DIR = Path("./N5/builds")
SYSTEM_LEARNINGS_PATH = Path("./N5/learnings/SYSTEM_LEARNINGS.json")
REVIEW_DIR = Path("./N5/review/learnings")


def load_all_build_learnings() -> list[dict[str, Any]]:
    """Load all learnings from all builds."""
    all_learnings = []
    
    for build_dir in BUILDS_DIR.iterdir():
        if not build_dir.is_dir():
            continue
        
        lessons_file = build_dir / "BUILD_LESSONS.json"
        if not lessons_file.exists():
            continue
        
        try:
            with open(lessons_file) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse {lessons_file}: {e}", file=sys.stderr)
            continue
        
        learnings = data.get("learnings", [])
        for i, learning in enumerate(learnings):
            all_learnings.append({
                "text": learning.get("text", ""),
                "build_slug": data.get("slug", build_dir.name),
                "source": learning.get("source", "unknown"),
                "added_at": learning.get("added_at", ""),
                "tags": learning.get("tags", []),
                "index": i,
            })
    
    return all_learnings


def load_existing_system_learnings() -> list[str]:
    """Load existing system learnings to avoid duplicates."""
    if not SYSTEM_LEARNINGS_PATH.exists():
        return []
    
    try:
        with open(SYSTEM_LEARNINGS_PATH) as f:
            data = json.load(f)
        return [l.get("text", "") for l in data.get("learnings", [])]
    except (json.JSONDecodeError, KeyError):
        return []


def call_zo_ask(prompt: str, timeout: int = 120) -> str:
    """Call /zo/ask API."""
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        raise RuntimeError("ZO_CLIENT_IDENTITY_TOKEN not set")
    
    response = requests.post(
        "https://api.zo.computer/zo/ask",
        headers={
            "authorization": token,
            "content-type": "application/json"
        },
        json={"input": prompt},
        timeout=timeout
    )
    response.raise_for_status()
    return response.json().get("output", "")


def dedupe_and_score_batch(learnings_batch: list[dict], batch_offset: int, existing_system: list[str], threshold: float) -> list[dict]:
    """Process a batch of learnings via LLM."""
    if not learnings_batch:
        return []
    
    learnings_text = "\n".join([
        f"[{i}] ({l['build_slug']}) {l['text']}"
        for i, l in enumerate(learnings_batch)
    ])
    
    existing_text = "\n".join([f"- {t}" for t in existing_system]) if existing_system else "(none)"
    
    prompt = f"""You are analyzing build learnings to identify which should be promoted.

EXISTING SYSTEM LEARNINGS (do not recommend duplicates of these):
{existing_text}

BUILD LEARNINGS TO ANALYZE:
{learnings_text}

TASK:
1. Cluster semantically similar learnings (same insight, different wording)
2. Score each UNIQUE learning for promotion-worthiness (0.0-1.0)
3. Classify each as SYSTEM or PERSONAL

CLASSIFICATION CRITERIA:
SYSTEM (infrastructure/tooling - goes to SYSTEM_LEARNINGS.json):
- Zo APIs, /zo/ask behavior, tool quirks
- Pulse/build system patterns
- Database patterns (SQLite, Airtable, etc.)
- Error handling for infrastructure
- Integration behaviors (Gmail, Drive, etc.)
- Channel constraints (SMS limits, etc.)
- Parsing/data format handling

PERSONAL (domain knowledge - goes to V's Knowledge base):
- Product design insights
- UX principles
- Research findings about human behavior
- Assessment frameworks
- Business logic patterns
- Domain expertise (ADHD, hiring, etc.)
- Strategic/philosophical insights

SCORING CRITERIA:
- Generalizable (applies beyond this specific build): +0.3
- Actionable (clear "do this" or "avoid that"): +0.2
- Novel (not already known): +0.2
- Insight quality (tool/API or domain expertise): +0.2
- Process/architecture pattern: +0.1

DISQUALIFIERS (score 0.0):
- Build-specific facts ("processed 20 items", "D1.3 completed")
- Test artifacts ("test v2 learning")
- Already covered by existing system learnings

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "clusters": [
    {{
      "representative_text": "The best/clearest wording of this insight",
      "score": 0.85,
      "category": "system",
      "reasoning": "Brief explanation of score and category",
      "member_indices": [0, 5, 12],
      "occurrence_count": 3,
      "source_builds": ["build-a", "build-b", "build-c"],
      "suggested_tags": ["api", "parsing"]
    }}
  ]
}}

Only include clusters with score >= {threshold}. Return valid JSON only."""

    response = call_zo_ask(prompt)
    
    json_match = re.search(r'\{[\s\S]*\}', response)
    if not json_match:
        print(f"Warning: Could not parse LLM response as JSON", file=sys.stderr)
        print(f"Response: {response[:500]}", file=sys.stderr)
        return []
    
    try:
        result = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        print(f"Warning: JSON parse error: {e}", file=sys.stderr)
        return []
    
    enriched = []
    for cluster in result.get("clusters", []):
        indices = cluster.get("member_indices", [])
        if not indices:
            continue
            
        first_idx = indices[0]
        if first_idx >= len(learnings_batch):
            continue
            
        original = learnings_batch[first_idx]
        
        enriched.append({
            "text": cluster.get("representative_text", original["text"]),
            "score": cluster.get("score", 0.0),
            "category": cluster.get("category", "system"),
            "reasoning": cluster.get("reasoning", ""),
            "occurrence_count": cluster.get("occurrence_count", len(indices)),
            "source_builds": cluster.get("source_builds", [original["build_slug"]]),
            "suggested_tags": cluster.get("suggested_tags", []),
            "member_indices": [i + batch_offset for i in indices],
            "primary_build": original["build_slug"],
            "primary_index": original["index"],
        })
    
    return enriched


def final_dedup_pass(candidates: list[dict], threshold: float) -> list[dict]:
    """Merge semantically similar clusters from different batches."""
    if len(candidates) <= 5:
        return candidates
    
    texts = "\n".join([f"[{i}] ({c['category']}) {c['text']}" for i, c in enumerate(candidates)])
    
    prompt = f"""These are candidate learnings that may have duplicates (same insight, different wording).

CANDIDATES:
{texts}

TASK: Identify which indices are duplicates and should be merged.
When merging, preserve the category of the first (representative) index.

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "merge_groups": [
    [0, 5, 12],
    [3, 8]
  ],
  "keep_as_is": [1, 2, 4, 6, 7, 9, 10, 11]
}}

merge_groups: Arrays of indices to merge (first index is the representative)
keep_as_is: Indices that are unique

Return valid JSON only."""

    response = call_zo_ask(prompt)
    
    json_match = re.search(r'\{[\s\S]*\}', response)
    if not json_match:
        return candidates
    
    try:
        result = json.loads(json_match.group())
    except json.JSONDecodeError:
        return candidates
    
    merged = []
    used_indices = set()
    
    for group in result.get("merge_groups", []):
        if not group:
            continue
        representative_idx = group[0]
        if representative_idx >= len(candidates):
            continue
        
        rep = candidates[representative_idx].copy()
        total_occurrences = rep.get("occurrence_count", 1)
        all_sources = set(rep.get("source_builds", []))
        
        for idx in group[1:]:
            if idx < len(candidates):
                total_occurrences += candidates[idx].get("occurrence_count", 1)
                all_sources.update(candidates[idx].get("source_builds", []))
                used_indices.add(idx)
        
        rep["occurrence_count"] = total_occurrences
        rep["source_builds"] = list(all_sources)
        merged.append(rep)
        used_indices.add(representative_idx)
    
    for idx in result.get("keep_as_is", []):
        if idx < len(candidates) and idx not in used_indices:
            merged.append(candidates[idx])
            used_indices.add(idx)
    
    for i, c in enumerate(candidates):
        if i not in used_indices:
            merged.append(c)
    
    return merged


def dedupe_and_score_learnings(learnings: list[dict], existing_system: list[str], threshold: float) -> list[dict]:
    """Dedupe, score, and classify learnings. Returns sorted list."""
    if not learnings:
        return []
    
    BATCH_SIZE = 40
    all_results = []
    
    for i in range(0, len(learnings), BATCH_SIZE):
        batch = learnings[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (len(learnings) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} learnings)...", file=sys.stderr)
        
        batch_results = dedupe_and_score_batch(batch, i, existing_system, threshold)
        all_results.extend(batch_results)
    
    if len(all_results) > 1:
        print(f"  Running final cross-batch dedup on {len(all_results)} candidates...", file=sys.stderr)
        all_results = final_dedup_pass(all_results, threshold)
    
    all_results.sort(key=lambda x: x["score"], reverse=True)
    
    return all_results


def generate_review_batch(scored_learnings: list[dict], category: str, threshold: float) -> str:
    """Generate markdown review batch for a specific category."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    if category == "system":
        title = "System Learning Promotion Review"
        description = "Infrastructure, tooling, and API learnings → `SYSTEM_LEARNINGS.json`"
        destination = "`N5/learnings/SYSTEM_LEARNINGS.json`"
        process_cmd = f"python3 Skills/pulse/scripts/process_learning_review.py N5/review/learnings/{date_str}_system-learnings-review.md"
    else:
        title = "Personal Knowledge Promotion Review"
        description = "Domain expertise, frameworks, and insights → V's Knowledge Base"
        destination = "`Personal/Knowledge/Learnings/` (indexed to N5 Brain)"
        process_cmd = f"python3 Skills/pulse/scripts/process_learning_review.py N5/review/learnings/{date_str}_personal-learnings-review.md"
    
    high_confidence = [l for l in scored_learnings if l["score"] >= 0.8]
    medium_confidence = [l for l in scored_learnings if 0.6 <= l["score"] < 0.8]
    
    lines = [
        "---",
        f"created: {date_str}",
        f"last_edited: {date_str}",
        "version: 1.0",
        "provenance: triage_learnings.py",
        f"category: {category}",
        "---",
        "",
        f"# {title} — {date_str}",
        "",
        "## Instructions",
        "",
        f"{description}",
        "",
        "Mark learnings to promote with `[x]`. Leave `[ ]` to skip.",
        "",
        "When done, run:",
        "```bash",
        process_cmd,
        "```",
        "",
        f"**Destination:** {destination}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Total unique learnings:** {len(scored_learnings)}",
        f"- **Threshold:** {threshold}",
        f"- **Generated:** {datetime.now().isoformat()}",
        "",
    ]
    
    if high_confidence:
        lines.append(f"## High Confidence (0.8+) — {len(high_confidence)} learnings")
        lines.append("")
        for l in high_confidence:
            lines.extend(_format_learning_entry(l))
    
    if medium_confidence:
        lines.append(f"## Medium Confidence (0.6–0.8) — {len(medium_confidence)} learnings")
        lines.append("")
        for l in medium_confidence:
            lines.extend(_format_learning_entry(l))
    
    return "\n".join(lines)


def _format_learning_entry(l: dict) -> list[str]:
    """Format a single learning entry for the review batch."""
    occurrence = f" ×{l['occurrence_count']}" if l['occurrence_count'] > 1 else ""
    tags = ", ".join(l.get("suggested_tags", [])) or "untagged"
    sources = ", ".join(l.get("source_builds", []))
    
    return [
        f"- [ ] **{l['primary_build']}#{l['primary_index']}** (score: {l['score']:.2f}{occurrence})",
        f"  > {l['text']}",
        f"  - Sources: {sources}",
        f"  - Tags: {tags}",
        f"  - Reasoning: {l['reasoning']}",
        "",
    ]


def main():
    parser = argparse.ArgumentParser(description="Triage build learnings for promotion")
    parser.add_argument("--threshold", type=float, default=0.6, help="Minimum score threshold")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout instead of writing files")
    args = parser.parse_args()
    
    print("Loading build learnings...", file=sys.stderr)
    learnings = load_all_build_learnings()
    print(f"Found {len(learnings)} total learnings across all builds", file=sys.stderr)
    
    if not learnings:
        print("No learnings found.", file=sys.stderr)
        return
    
    print("Loading existing system learnings...", file=sys.stderr)
    existing = load_existing_system_learnings()
    print(f"Found {len(existing)} existing system learnings", file=sys.stderr)
    
    print(f"Deduplicating, scoring, and classifying via LLM (threshold: {args.threshold})...", file=sys.stderr)
    scored = dedupe_and_score_learnings(learnings, existing, args.threshold)
    print(f"Found {len(scored)} unique learnings above threshold", file=sys.stderr)
    
    # Split by category
    system_learnings = [l for l in scored if l.get("category") == "system"]
    personal_learnings = [l for l in scored if l.get("category") == "personal"]
    
    print(f"  → {len(system_learnings)} system learnings", file=sys.stderr)
    print(f"  → {len(personal_learnings)} personal learnings", file=sys.stderr)
    
    print(f"Generating review batches...", file=sys.stderr)
    system_md = generate_review_batch(system_learnings, "system", args.threshold)
    personal_md = generate_review_batch(personal_learnings, "personal", args.threshold)
    
    if args.dry_run:
        print("=== SYSTEM LEARNINGS ===")
        print(system_md)
        print("\n=== PERSONAL LEARNINGS ===")
        print(personal_md)
    else:
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        system_path = REVIEW_DIR / f"{date_str}_system-learnings-review.md"
        personal_path = REVIEW_DIR / f"{date_str}_personal-learnings-review.md"
        
        with open(system_path, "w") as f:
            f.write(system_md)
        
        with open(personal_path, "w") as f:
            f.write(personal_md)
        
        print(f"✓ System review batch: {system_path} ({len(system_learnings)} learnings)", file=sys.stderr)
        print(f"✓ Personal review batch: {personal_path} ({len(personal_learnings)} learnings)", file=sys.stderr)


if __name__ == "__main__":
    main()
