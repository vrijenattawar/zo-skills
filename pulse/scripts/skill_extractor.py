#!/usr/bin/env python3
"""
Skill Extractor: Transform learnings into skill candidates.

Part of SkillRL integration — bridges experience capture to skill evolution.

Usage:
    python3 skill_extractor.py extract --build <slug>
    python3 skill_extractor.py extract --convo <convo_id>
    python3 skill_extractor.py check-similarity "lesson text"
    python3 skill_extractor.py list-candidates
    python3 skill_extractor.py promote <candidate_id> --name <skill-name>
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

WORKSPACE = Path("/home/workspace")
SKILLS_DIR = WORKSPACE / "Skills"
REVIEW_DIR = WORKSPACE / "N5/review/skills"
BUILDS_DIR = WORKSPACE / "N5/builds"
ZO_API = "https://api.zo.computer/zo/ask"


def get_auth_headers():
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        raise RuntimeError("ZO_CLIENT_IDENTITY_TOKEN not set")
    return {"authorization": token, "content-type": "application/json"}


def zo_ask(prompt: str, output_format: Optional[dict] = None) -> str | dict:
    payload = {"input": prompt}
    if output_format:
        payload["output_format"] = output_format
    resp = requests.post(ZO_API, headers=get_auth_headers(), json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["output"]


def get_existing_skills() -> list[dict]:
    skills = []
    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text()
            name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
            desc_match = re.search(r"^description:\s*\|?\s*\n((?:\s+.+\n)+)", content, re.MULTILINE)
            skills.append({
                "name": name_match.group(1).strip() if name_match else skill_dir.name,
                "description": desc_match.group(1).strip() if desc_match else "",
                "path": str(skill_dir.relative_to(WORKSPACE))
            })
    return skills


def classify_and_extract(lesson: str, source: str) -> dict:
    existing_skills = get_existing_skills()
    skills_summary = "\n".join([f"- {s['name']}: {s['description'][:100]}..." for s in existing_skills[:20]])
    
    prompt = f"""Analyze this lesson/learning and extract a skill candidate.

LESSON:
{lesson}

SOURCE: {source}

EXISTING SKILLS (check for overlap):
{skills_summary}

Classify and extract:

1. SCOPE: Is this lesson...
   - "universal" (applies to all work - reasoning patterns, meta-cognitive strategies)
   - "domain" (applies to a domain like debugging, writing, research, building)
   - "task-specific" (applies to a specific narrow task type)

2. SIMILARITY: Does this significantly overlap with any existing skill listed above?
   - If yes, which skill and how? (this would be a "refinement" not "new")
   - If no, it's a "new skill" candidate

3. EXTRACTION: If this lesson is worth capturing as a skill, extract:
   - name: kebab-case skill name (2-4 words)
   - trigger: When should this skill activate? (1 sentence)
   - procedure: What should be done? (2-5 bullet points)
   - anti_patterns: What should NOT be done? (1-3 bullet points)
   - confidence: 0.0-1.0 how confident are you this is a reusable skill?

4. VERDICT: Should this become a skill candidate?
   - "new" - novel skill worth adding
   - "refinement" - enhances existing skill (specify which)
   - "skip" - too specific, low confidence, or already covered

Respond in this exact JSON format:
{{
  "scope": "universal|domain|task-specific",
  "domain": "domain name if scope is domain, else null",
  "similar_to": "existing skill name or null",
  "similarity_reason": "why similar or null",
  "verdict": "new|refinement|skip",
  "skip_reason": "if skip, why",
  "skill": {{
    "name": "skill-name",
    "trigger": "when to activate",
    "procedure": ["step 1", "step 2"],
    "anti_patterns": ["don't do X"],
    "confidence": 0.8
  }}
}}"""

    result = zo_ask(prompt, output_format={
        "type": "object",
        "properties": {
            "scope": {"type": "string"},
            "domain": {"type": ["string", "null"]},
            "similar_to": {"type": ["string", "null"]},
            "similarity_reason": {"type": ["string", "null"]},
            "verdict": {"type": "string"},
            "skip_reason": {"type": ["string", "null"]},
            "skill": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "trigger": {"type": "string"},
                    "procedure": {"type": "array", "items": {"type": "string"}},
                    "anti_patterns": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"}
                }
            }
        },
        "required": ["scope", "verdict", "skill"]
    })
    
    result["source_lesson"] = lesson
    result["provenance"] = source
    return result


def load_build_lessons(slug: str) -> list[str]:
    lessons_file = BUILDS_DIR / slug / "BUILD_LESSONS.json"
    if not lessons_file.exists():
        return []
    data = json.loads(lessons_file.read_text())
    return [entry.get("lesson", entry.get("text", "")) for entry in data if isinstance(entry, dict)]


def load_thread_learnings(convo_id: str) -> list[str]:
    workspaces_dir = Path("/home/.z/workspaces")
    convo_dir = workspaces_dir / convo_id
    
    for filename in ["THREAD_CLOSE.md", "SESSION_STATE.md"]:
        filepath = convo_dir / filename
        if filepath.exists():
            content = filepath.read_text()
            learnings_match = re.search(r"## Learnings?\n((?:- .+\n)+)", content)
            if learnings_match:
                return [line.strip("- \n") for line in learnings_match.group(1).split("\n") if line.strip()]
    return []


def generate_candidate_id(existing_candidates: list) -> str:
    max_id = 0
    for c in existing_candidates:
        match = re.search(r"\[C(\d+)\]", c.get("id", ""))
        if match:
            max_id = max(max_id, int(match.group(1)))
    return f"C{max_id + 1:03d}"


def write_candidates_to_review(candidates: list[dict], date_str: str = None):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    review_file = REVIEW_DIR / f"{date_str}_candidates.md"
    
    new_skills = [c for c in candidates if c["verdict"] == "new"]
    refinements = [c for c in candidates if c["verdict"] == "refinement"]
    
    content = f"""---
created: {date_str}
type: skill-candidates
status: pending_review
---

# Skill Candidates: {date_str}

## New Skills ({len(new_skills)})

"""
    
    for i, c in enumerate(new_skills, 1):
        skill = c["skill"]
        content += f"""### [C{i:03d}] {skill['name']}
- **Scope:** {c['scope']}{f" ({c['domain']})" if c.get('domain') else ""}
- **Trigger:** {skill['trigger']}
- **Procedure:**
{chr(10).join(f"  - {p}" for p in skill['procedure'])}
- **Anti-patterns:**
{chr(10).join(f"  - {a}" for a in skill['anti_patterns'])}
- **Confidence:** {skill['confidence']}
- **Source:** {c['provenance']}
- **Original lesson:** {c['source_lesson'][:200]}...
- **Action:** [ ] Approve → `skill_extractor.py promote C{i:03d} --name {skill['name']}`

"""
    
    if refinements:
        content += f"\n## Refinements ({len(refinements)})\n\n"
        for i, c in enumerate(refinements, 1):
            content += f"""### [R{i:03d}] Enhance: {c['similar_to']}
- **Existing skill:** Skills/{c['similar_to']}/
- **Proposed addition:** {c['skill']['trigger']}
- **Reason:** {c['similarity_reason']}
- **Source:** {c['provenance']}
- **Action:** [ ] Approve refinement

"""
    
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    review_file.write_text(content)
    print(f"✓ Wrote {len(candidates)} candidates to {review_file.relative_to(WORKSPACE)}")
    return review_file


def extract_from_build(slug: str) -> Path:
    lessons = load_build_lessons(slug)
    if not lessons:
        print(f"No lessons found in build {slug}")
        return None
    
    print(f"Extracting from {len(lessons)} lessons in build {slug}...")
    candidates = []
    for lesson in lessons:
        if len(lesson.strip()) < 20:
            continue
        result = classify_and_extract(lesson, f"build:{slug}")
        if result["verdict"] != "skip":
            candidates.append(result)
        else:
            print(f"  Skipped: {result.get('skip_reason', 'low value')}")
    
    if candidates:
        return write_candidates_to_review(candidates)
    print("No candidates extracted")
    return None


def extract_from_thread(convo_id: str, learnings: list[str] = None) -> Path:
    if learnings is None:
        learnings = load_thread_learnings(convo_id)
    
    if not learnings:
        print(f"No learnings found for thread {convo_id}")
        return None
    
    print(f"Extracting from {len(learnings)} learnings in thread {convo_id}...")
    candidates = []
    for learning in learnings:
        if len(learning.strip()) < 20:
            continue
        result = classify_and_extract(learning, f"convo:{convo_id}")
        if result["verdict"] != "skip":
            candidates.append(result)
    
    if candidates:
        return write_candidates_to_review(candidates)
    print("No candidates extracted")
    return None


def check_similarity(lesson_text: str):
    result = classify_and_extract(lesson_text, "manual-check")
    
    print(f"\nScope: {result['scope']}")
    if result.get("domain"):
        print(f"Domain: {result['domain']}")
    
    if result.get("similar_to"):
        print(f"\n⚠️  Similar to existing skill: {result['similar_to']}")
        print(f"   Reason: {result['similarity_reason']}")
    else:
        print("\n✓ No significant overlap with existing skills")
    
    print(f"\nVerdict: {result['verdict']}")
    if result["verdict"] == "skip":
        print(f"Skip reason: {result.get('skip_reason')}")
    else:
        skill = result["skill"]
        print(f"\nProposed skill: {skill['name']}")
        print(f"Trigger: {skill['trigger']}")
        print(f"Confidence: {skill['confidence']}")


def list_candidates():
    candidates_files = sorted(REVIEW_DIR.glob("*_candidates.md"), reverse=True)
    if not candidates_files:
        print("No candidate files found in N5/review/skills/")
        return
    
    for f in candidates_files[:5]:
        content = f.read_text()
        new_count = content.count("### [C")
        ref_count = content.count("### [R")
        status = "pending" if "status: pending_review" in content else "reviewed"
        print(f"{f.name}: {new_count} new, {ref_count} refinements ({status})")


def promote_candidate(candidate_id: str, skill_name: str):
    candidates_files = sorted(REVIEW_DIR.glob("*_candidates.md"), reverse=True)
    
    for f in candidates_files:
        content = f.read_text()
        pattern = rf"\[{candidate_id}\]\s+(\S+)\n((?:- .+\n)+)"
        match = re.search(pattern, content)
        if match:
            print(f"Found {candidate_id} in {f.name}")
            
            skill_dir = SKILLS_DIR / skill_name
            skill_dir.mkdir(exist_ok=True)
            
            skill_md = skill_dir / "SKILL.md"
            skill_content = f"""---
name: {skill_name}
description: |
  Auto-extracted skill from experience distillation.
  Review and enhance the description.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  extracted_from: {candidate_id}
  extraction_date: {datetime.now().strftime("%Y-%m-%d")}
---

# {skill_name.replace('-', ' ').title()}

## TODO: Review and enhance this auto-generated skill

{match.group(2)}
"""
            skill_md.write_text(skill_content)
            print(f"✓ Created {skill_dir.relative_to(WORKSPACE)}/SKILL.md")
            print("  → Review and enhance the generated SKILL.md")
            return
    
    print(f"Candidate {candidate_id} not found in recent candidate files")


def main():
    parser = argparse.ArgumentParser(description="Skill Extractor")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    extract_parser = subparsers.add_parser("extract", help="Extract skills from build or thread")
    extract_parser.add_argument("--build", help="Build slug")
    extract_parser.add_argument("--convo", help="Conversation ID")
    
    check_parser = subparsers.add_parser("check-similarity", help="Check if lesson overlaps existing skills")
    check_parser.add_argument("lesson", help="Lesson text to check")
    
    subparsers.add_parser("list-candidates", help="List pending skill candidates")
    
    promote_parser = subparsers.add_parser("promote", help="Promote candidate to skill")
    promote_parser.add_argument("candidate_id", help="Candidate ID (e.g., C001)")
    promote_parser.add_argument("--name", required=True, help="Skill name (kebab-case)")
    
    args = parser.parse_args()
    
    if args.command == "extract":
        if args.build:
            extract_from_build(args.build)
        elif args.convo:
            extract_from_thread(args.convo)
        else:
            print("Specify --build or --convo")
            sys.exit(1)
    elif args.command == "check-similarity":
        check_similarity(args.lesson)
    elif args.command == "list-candidates":
        list_candidates()
    elif args.command == "promote":
        promote_candidate(args.candidate_id, args.name)


if __name__ == "__main__":
    main()
