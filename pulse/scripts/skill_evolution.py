#!/usr/bin/env python3
"""
Skill Evolution: Analyze skill health and propose improvements.

Run weekly via scheduled agent to maintain skill library health.

Usage:
    python3 skill_evolution.py analyze [--output digest|json]
    python3 skill_evolution.py archive <skill-name> --reason "why"
    python3 skill_evolution.py suggest-merge <skill1> <skill2>
"""

import argparse
import json
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import requests

WORKSPACE = Path("/home/workspace")
SKILLS_DIR = WORKSPACE / "Skills"
ARCHIVE_DIR = SKILLS_DIR / "_archived"
REVIEW_DIR = WORKSPACE / "N5/review/skills"
USAGE_FILE = WORKSPACE / "N5/cognition/skill_usage.jsonl"
ZO_API = "https://api.zo.computer/zo/ask"


def get_auth_headers():
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        raise RuntimeError("ZO_CLIENT_IDENTITY_TOKEN not set")
    return {"authorization": token, "content-type": "application/json"}


def zo_ask(prompt: str) -> str:
    resp = requests.post(ZO_API, headers=get_auth_headers(), 
                        json={"input": prompt}, timeout=120)
    resp.raise_for_status()
    return resp.json()["output"]


def get_skill_metadata(skill_dir: Path) -> dict:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None
    
    content = skill_md.read_text()
    
    # Parse frontmatter
    frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    metadata = {}
    if frontmatter_match:
        for line in frontmatter_match.group(1).split("\n"):
            if ":" in line and not line.startswith(" "):
                key, val = line.split(":", 1)
                metadata[key.strip()] = val.strip()
    
    # Get file stats
    stat = skill_md.stat()
    metadata["path"] = str(skill_dir.relative_to(WORKSPACE))
    metadata["last_modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
    metadata["size_bytes"] = stat.st_size
    
    return metadata


def load_usage_stats(days: int = 30) -> dict:
    if not USAGE_FILE.exists():
        return {}
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    stats = {}
    
    with open(USAGE_FILE) as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                ts = datetime.fromisoformat(entry["timestamp"].rstrip("Z"))
                skill = entry["skill"]
                
                if skill not in stats:
                    stats[skill] = {"total": 0, "success": 0, "failure": 0, 
                                   "last_used": None, "recent": 0}
                
                stats[skill]["total"] += 1
                stats[skill][entry["outcome"]] += 1
                
                if ts >= cutoff:
                    stats[skill]["recent"] += 1
                
                if not stats[skill]["last_used"] or entry["timestamp"] > stats[skill]["last_used"]:
                    stats[skill]["last_used"] = entry["timestamp"]
    
    return stats


def analyze_skill_health() -> dict:
    usage_stats = load_usage_stats(30)
    
    skills = []
    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        
        metadata = get_skill_metadata(skill_dir)
        if not metadata:
            continue
        
        skill_name = metadata.get("name", skill_dir.name)
        usage = usage_stats.get(skill_name, {})
        
        # Calculate health signals
        last_modified = datetime.fromisoformat(metadata["last_modified"])
        days_since_modified = (datetime.now() - last_modified).days
        
        last_used_str = usage.get("last_used")
        if last_used_str:
            last_used = datetime.fromisoformat(last_used_str.rstrip("Z"))
            days_since_used = (datetime.utcnow() - last_used).days
        else:
            days_since_used = None
        
        total_uses = usage.get("total", 0)
        recent_uses = usage.get("recent", 0)
        success_rate = usage.get("success", 0) / total_uses if total_uses > 0 else None
        
        # Determine health status
        health = "healthy"
        issues = []
        
        if days_since_used is None:
            health = "unused"
            issues.append("Never used in tracked history")
        elif days_since_used > 60:
            health = "stale"
            issues.append(f"Not used in {days_since_used} days")
        
        if success_rate is not None and success_rate < 0.5 and total_uses >= 3:
            health = "failing"
            issues.append(f"Low success rate: {success_rate:.0%}")
        
        if days_since_modified > 180:
            issues.append(f"Not updated in {days_since_modified} days")
        
        skills.append({
            "name": skill_name,
            "path": metadata["path"],
            "health": health,
            "issues": issues,
            "total_uses": total_uses,
            "recent_uses": recent_uses,
            "success_rate": success_rate,
            "days_since_used": days_since_used,
            "days_since_modified": days_since_modified,
            "description": metadata.get("description", "")[:100]
        })
    
    return {
        "analyzed_at": datetime.utcnow().isoformat() + "Z",
        "total_skills": len(skills),
        "healthy": len([s for s in skills if s["health"] == "healthy"]),
        "stale": len([s for s in skills if s["health"] == "stale"]),
        "unused": len([s for s in skills if s["health"] == "unused"]),
        "failing": len([s for s in skills if s["health"] == "failing"]),
        "skills": skills
    }


def generate_digest(analysis: dict) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    stale = [s for s in analysis["skills"] if s["health"] == "stale"]
    unused = [s for s in analysis["skills"] if s["health"] == "unused"]
    failing = [s for s in analysis["skills"] if s["health"] == "failing"]
    top_used = sorted([s for s in analysis["skills"] if s["recent_uses"] > 0], 
                      key=lambda x: -x["recent_uses"])[:5]
    
    digest = f"""# Skill Evolution Digest: {date_str}

## Summary

| Status | Count |
|--------|-------|
| Total Skills | {analysis['total_skills']} |
| Healthy | {analysis['healthy']} |
| Stale | {analysis['stale']} |
| Unused | {analysis['unused']} |
| Failing | {analysis['failing']} |

## Top Used (Last 30 Days)

"""
    
    for s in top_used:
        rate = f"{s['success_rate']:.0%}" if s["success_rate"] is not None else "N/A"
        digest += f"- **{s['name']}**: {s['recent_uses']} uses ({rate} success)\n"
    
    if stale:
        digest += f"\n## Stale Skills ({len(stale)})\n\n"
        digest += "| Skill | Last Used | Action |\n|-------|-----------|--------|\n"
        for s in stale[:10]:
            digest += f"| {s['name']} | {s['days_since_used']} days ago | [ ] Review or archive |\n"
    
    if unused:
        digest += f"\n## Unused Skills ({len(unused)})\n\n"
        for s in unused[:10]:
            digest += f"- `{s['name']}`: {s['description'][:50]}...\n"
        if len(unused) > 10:
            digest += f"- ... and {len(unused) - 10} more\n"
    
    if failing:
        digest += f"\n## Failing Skills ({len(failing)})\n\n"
        for s in failing:
            digest += f"- **{s['name']}**: {s['success_rate']:.0%} success ({s['total_uses']} uses)\n"
            for issue in s["issues"]:
                digest += f"  - {issue}\n"
    
    digest += f"\n## Actions\n\n"
    digest += "- [ ] Review stale skills for archival\n"
    digest += "- [ ] Investigate failing skills\n"
    digest += "- [ ] Check pending candidates: `skill_extractor.py list-candidates`\n"
    
    return digest


def archive_skill(skill_name: str, reason: str):
    skill_dir = SKILLS_DIR / skill_name
    if not skill_dir.exists():
        print(f"Skill {skill_name} not found")
        return
    
    ARCHIVE_DIR.mkdir(exist_ok=True)
    archive_dest = ARCHIVE_DIR / f"{skill_name}_{datetime.now().strftime('%Y%m%d')}"
    
    # Add archive metadata
    skill_md = skill_dir / "SKILL.md"
    content = skill_md.read_text()
    archive_note = f"\n\n<!-- ARCHIVED: {datetime.now().isoformat()} | Reason: {reason} -->\n"
    skill_md.write_text(content + archive_note)
    
    shutil.move(str(skill_dir), str(archive_dest))
    print(f"✓ Archived {skill_name} to {archive_dest.relative_to(WORKSPACE)}")
    print(f"  Reason: {reason}")


def suggest_merge(skill1: str, skill2: str):
    s1_path = SKILLS_DIR / skill1 / "SKILL.md"
    s2_path = SKILLS_DIR / skill2 / "SKILL.md"
    
    if not s1_path.exists() or not s2_path.exists():
        print("One or both skills not found")
        return
    
    s1_content = s1_path.read_text()
    s2_content = s2_path.read_text()
    
    prompt = f"""Analyze these two skills and suggest if/how they should be merged:

SKILL 1: {skill1}
{s1_content[:2000]}

SKILL 2: {skill2}
{s2_content[:2000]}

Questions:
1. Do these skills overlap significantly?
2. Would merging them reduce confusion?
3. If merged, what would the combined skill look like?

Provide a recommendation: MERGE, KEEP SEPARATE, or ONE SUBSUMES OTHER."""

    response = zo_ask(prompt)
    print(f"\n## Merge Analysis: {skill1} + {skill2}\n")
    print(response)


def main():
    parser = argparse.ArgumentParser(description="Skill Evolution")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    analyze_parser = subparsers.add_parser("analyze", help="Analyze skill health")
    analyze_parser.add_argument("--output", choices=["digest", "json"], default="digest")
    
    archive_parser = subparsers.add_parser("archive", help="Archive a skill")
    archive_parser.add_argument("skill", help="Skill name")
    archive_parser.add_argument("--reason", required=True, help="Reason for archival")
    
    merge_parser = subparsers.add_parser("suggest-merge", help="Analyze potential merge")
    merge_parser.add_argument("skill1")
    merge_parser.add_argument("skill2")
    
    args = parser.parse_args()
    
    if args.command == "analyze":
        analysis = analyze_skill_health()
        if args.output == "json":
            print(json.dumps(analysis, indent=2))
        else:
            digest = generate_digest(analysis)
            print(digest)
            
            # Also write to review dir
            digest_file = REVIEW_DIR / f"{datetime.now().strftime('%Y-%m-%d')}_evolution_digest.md"
            REVIEW_DIR.mkdir(parents=True, exist_ok=True)
            digest_file.write_text(digest)
            print(f"\n✓ Saved to {digest_file.relative_to(WORKSPACE)}")
    
    elif args.command == "archive":
        archive_skill(args.skill, args.reason)
    
    elif args.command == "suggest-merge":
        suggest_merge(args.skill1, args.skill2)


if __name__ == "__main__":
    main()
