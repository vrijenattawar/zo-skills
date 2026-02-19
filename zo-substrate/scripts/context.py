#!/usr/bin/env python3
"""
Zo Substrate — Local context awareness.

Scans the local workspace to build an awareness snapshot of what skills,
scripts, and content are installed. Useful for the receiving Zo to know
what capabilities it has after pulling from the substrate.
"""

import argparse
import json
import sys
from pathlib import Path

from config import WORKSPACE_ROOT, load_config, now_iso, state_dir


def scan_skills() -> list[dict]:
    """Find all installed skills."""
    skills = []
    skills_dir = WORKSPACE_ROOT / "Skills"
    if not skills_dir.exists():
        return skills

    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir():
            continue
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            continue

        dir_name = d.name
        frontmatter_name = None
        content = skill_md.read_text()
        for line in content.split("\n"):
            if line.strip().startswith("name:"):
                frontmatter_name = line.split(":", 1)[1].strip().strip("'\"")
                break

        entry = {"name": dir_name, "path": str(d.relative_to(WORKSPACE_ROOT)), "scripts": []}
        if frontmatter_name and frontmatter_name != dir_name:
            entry["frontmatter_name"] = frontmatter_name

        scripts_dir = d / "scripts"
        if scripts_dir.exists():
            entry["scripts"] = [f.name for f in scripts_dir.iterdir() if f.is_file()]

        skills.append(entry)

    return skills


def scan_folder_structure() -> dict:
    """Get top-level folder structure."""
    structure = {}
    for item in sorted(WORKSPACE_ROOT.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            children = []
            try:
                for child in sorted(item.iterdir())[:10]:
                    children.append(child.name + ("/" if child.is_dir() else ""))
            except PermissionError:
                pass
            structure[item.name + "/"] = children
    return structure


def refresh(cfg: dict) -> dict:
    """Build a full context snapshot."""
    skills = scan_skills()
    structure = scan_folder_structure()

    context = {
        "last_refresh": now_iso(),
        "identity": cfg["identity"]["name"],
        "skills": [s["name"] for s in skills],
        "skills_detail": skills,
        "folder_structure": structure,
    }

    output = state_dir(cfg) / "context.json"
    output.write_text(json.dumps(context, indent=2))
    return context


def query(cfg: dict, what: str = "summary", detail: bool = False) -> None:
    """Query the current context snapshot."""
    ctx_file = state_dir(cfg) / "context.json"
    if not ctx_file.exists():
        print("No context snapshot found. Run: substrate.py context refresh")
        return

    ctx = json.loads(ctx_file.read_text())

    if what == "summary":
        print(f"Identity: {ctx.get('identity', '?')}")
        print(f"Last refresh: {ctx.get('last_refresh', '?')}")
        print(f"Skills: {len(ctx.get('skills', []))}")
        for name in ctx.get("skills", []):
            print(f"  - {name}")

    elif what == "skills":
        if detail:
            for s in ctx.get("skills_detail", []):
                print(f"- {s['name']} ({s['path']})")
                if s.get("scripts"):
                    print(f"  Scripts: {', '.join(s['scripts'])}")
        else:
            for name in ctx.get("skills", []):
                print(f"- {name}")

    elif what == "structure":
        for folder, children in ctx.get("folder_structure", {}).items():
            print(f"- {folder}")
            for c in children[:5]:
                print(f"  - {c}")

    elif what == "json":
        print(json.dumps(ctx, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Zo Substrate — Context awareness")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("refresh", help="Refresh the local context snapshot")

    q = sub.add_parser("query", help="Query the context snapshot")
    q.add_argument("--what", choices=["summary", "skills", "structure", "json"], default="summary")
    q.add_argument("--detail", action="store_true")

    args = parser.parse_args()
    cfg = load_config()

    if args.command == "refresh":
        ctx = refresh(cfg)
        print(f"✓ Context refreshed: {len(ctx['skills'])} skills found")

    elif args.command == "query":
        query(cfg, args.what, getattr(args, "detail", False))

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
