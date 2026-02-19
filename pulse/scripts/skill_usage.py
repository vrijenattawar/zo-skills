#!/usr/bin/env python3
"""
Skill Usage Tracker: Logs when skills are activated and tracks usage patterns.

Usage:
    python3 skill_usage.py log <skill-name> [--convo <id>] [--success|--failure]
    python3 skill_usage.py stats [--skill <name>] [--days <n>]
    python3 skill_usage.py stale [--days <n>]
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = Path("/home/workspace")
USAGE_FILE = WORKSPACE / "N5/cognition/skill_usage.jsonl"


def ensure_usage_file():
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not USAGE_FILE.exists():
        USAGE_FILE.touch()


def log_usage(skill_name: str, convo_id: str = None, success: bool = True):
    ensure_usage_file()
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "skill": skill_name,
        "convo_id": convo_id,
        "outcome": "success" if success else "failure"
    }
    with open(USAGE_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"✓ Logged {skill_name} usage ({entry['outcome']})")


def load_usage(days: int = 30) -> list[dict]:
    if not USAGE_FILE.exists():
        return []
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    entries = []
    
    with open(USAGE_FILE) as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                ts = datetime.fromisoformat(entry["timestamp"].rstrip("Z"))
                if ts >= cutoff:
                    entries.append(entry)
    return entries


def get_stats(skill_name: str = None, days: int = 30):
    entries = load_usage(days)
    
    if skill_name:
        entries = [e for e in entries if e["skill"] == skill_name]
    
    stats = {}
    for e in entries:
        skill = e["skill"]
        if skill not in stats:
            stats[skill] = {"total": 0, "success": 0, "failure": 0, "last_used": None}
        stats[skill]["total"] += 1
        stats[skill][e["outcome"]] += 1
        stats[skill]["last_used"] = e["timestamp"]
    
    print(f"\nSkill Usage Stats (last {days} days):\n")
    for skill, s in sorted(stats.items(), key=lambda x: -x[1]["total"]):
        success_rate = s["success"] / s["total"] * 100 if s["total"] > 0 else 0
        print(f"  {skill}: {s['total']} uses ({success_rate:.0f}% success) | last: {s['last_used'][:10]}")


def get_stale_skills(days: int = 30) -> list[str]:
    entries = load_usage(days * 3)  # Look back further to find last usage
    
    last_used = {}
    for e in entries:
        skill = e["skill"]
        ts = datetime.fromisoformat(e["timestamp"].rstrip("Z"))
        if skill not in last_used or ts > last_used[skill]:
            last_used[skill] = ts
    
    # Get all skills from Skills/
    all_skills = []
    for skill_dir in (WORKSPACE / "Skills").iterdir():
        if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
            if (skill_dir / "SKILL.md").exists():
                all_skills.append(skill_dir.name)
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    stale = []
    never_used = []
    
    for skill in all_skills:
        if skill not in last_used:
            never_used.append(skill)
        elif last_used[skill] < cutoff:
            stale.append((skill, last_used[skill]))
    
    print(f"\nStale Skills (not used in {days} days):\n")
    for skill, ts in sorted(stale, key=lambda x: x[1]):
        print(f"  {skill}: last used {ts.strftime('%Y-%m-%d')}")
    
    if never_used:
        print(f"\nNever Used ({len(never_used)}):")
        for skill in sorted(never_used)[:10]:
            print(f"  {skill}")
        if len(never_used) > 10:
            print(f"  ... and {len(never_used) - 10} more")
    
    return [s[0] for s in stale] + never_used


def main():
    parser = argparse.ArgumentParser(description="Skill Usage Tracker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    log_parser = subparsers.add_parser("log", help="Log skill usage")
    log_parser.add_argument("skill", help="Skill name")
    log_parser.add_argument("--convo", help="Conversation ID")
    log_parser.add_argument("--success", action="store_true", default=True)
    log_parser.add_argument("--failure", action="store_true")
    
    stats_parser = subparsers.add_parser("stats", help="Show usage stats")
    stats_parser.add_argument("--skill", help="Filter to specific skill")
    stats_parser.add_argument("--days", type=int, default=30)
    
    stale_parser = subparsers.add_parser("stale", help="Find stale skills")
    stale_parser.add_argument("--days", type=int, default=30)
    
    args = parser.parse_args()
    
    if args.command == "log":
        log_usage(args.skill, args.convo, success=not args.failure)
    elif args.command == "stats":
        get_stats(args.skill, args.days)
    elif args.command == "stale":
        get_stale_skills(args.days)


if __name__ == "__main__":
    main()
