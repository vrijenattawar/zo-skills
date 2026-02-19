#!/usr/bin/env python3
"""
Zo Substrate — Push skills to the shared substrate repository.

Copies discovered/configured skills into a clean clone of the substrate repo,
commits, and pushes. Tracks sync state for incremental updates.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

from config import (
    WORKSPACE_ROOT, discover_skills, get_workspace_git_sha,
    load_config, load_state, log_event, now_iso, repo_url,
    run_git, save_state, tmp_repo_path,
)


def clone_fresh(cfg: Dict) -> bool:
    """Clone a fresh copy of the substrate repo."""
    tmp = tmp_repo_path(cfg)
    if tmp.exists():
        shutil.rmtree(tmp)

    url = repo_url(cfg)
    branch = cfg["substrate"]["branch"]
    print(f"  Cloning {cfg['substrate']['repo']} (branch: {branch})...")

    try:
        code, out, err = run_git(
            ["git", "clone", "--branch", branch, "--single-branch", url, str(tmp)],
            cwd=Path("/tmp"),
        )
        print("  Clone OK")
        return True
    except Exception as e:
        print(f"  Clone failed: {e}")
        return False


def copy_skills(cfg: Dict, skills: List[Dict], tmp: Path) -> List[str]:
    """Copy skills into the substrate repo clone."""
    skills_dir = tmp / "Skills"
    skills_dir.mkdir(exist_ok=True)
    copied = []

    skip_patterns = {"__pycache__", ".git", "node_modules", ".DS_Store", ".pyc"}

    def ignore_fn(directory, contents):
        return [c for c in contents if c in skip_patterns]

    for skill in skills:
        src = Path(skill["abs_path"])
        dest = skills_dir / skill["name"]

        if not src.exists():
            print(f"  SKIP {skill['name']}: source not found")
            continue

        if dest.exists():
            shutil.rmtree(dest)

        shutil.copytree(src, dest, ignore=ignore_fn)
        copied.append(skill["name"])
        print(f"  Copied: {skill['name']}")

    return copied


def update_manifest(cfg: Dict, copied: List[str], tmp: Path) -> None:
    """Write MANIFEST.json to the repo root."""
    manifest = {
        "generated_at": now_iso(),
        "source": cfg["identity"]["name"],
        "source_handle": cfg["identity"].get("handle", ""),
        "git_sha": get_workspace_git_sha(),
        "exported_skills": sorted(copied),
        "skill_count": len(copied),
        "schema_version": "1.0",
    }
    (tmp / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))


def commit_and_push(cfg: Dict, copied: List[str], tmp: Path) -> bool:
    """Commit and push changes."""
    identity = cfg["identity"]["name"]
    run_git(["git", "config", "user.email", f"{identity}@zo.computer"], tmp, check=False)
    run_git(["git", "config", "user.name", identity], tmp, check=False)

    code, status, _ = run_git(["git", "status", "--porcelain"], tmp)
    if not status.strip():
        print("  No changes to commit")
        return True

    run_git(["git", "add", "-A"], tmp)

    msg = f"Sync from {identity}: {', '.join(copied[:5])}"
    if len(copied) > 5:
        msg += f" (+{len(copied) - 5} more)"
    run_git(["git", "commit", "-m", msg], tmp)

    branch = cfg["substrate"]["branch"]
    print(f"  Pushing to origin/{branch}...")
    try:
        run_git(["git", "push", "origin", branch], tmp)
        print("  Push OK")
        return True
    except Exception as e:
        print(f"  Push failed: {e}")
        return False


def push(
    cfg: Dict,
    filter_skills: Optional[List[str]] = None,
    dry_run: bool = False,
) -> Dict:
    """
    Main push operation.

    Returns dict: {success, copied, skipped, error}.
    """
    print(f"=== Zo Substrate Push ===")
    print(f"  From: {cfg['identity']['name']}")
    print(f"  Repo: {cfg['substrate']['repo']}")

    skills = discover_skills(cfg)
    if filter_skills:
        skills = [s for s in skills if s["name"] in filter_skills]
        if not skills:
            available = [s["name"] for s in discover_skills(cfg)]
            print(f"  ⚠ No matching skills found for filter: {', '.join(filter_skills)}")
            print(f"  Available: {', '.join(available) if available else 'none'}")
            return {"success": False, "copied": [], "error": "no_match"}

    if not skills:
        print("  No skills to export")
        return {"success": True, "copied": [], "skipped": []}

    print(f"  Skills to sync: {len(skills)}")

    if dry_run:
        print("\n  [DRY RUN] Would push:")
        for s in skills:
            print(f"    - {s['name']}")
        return {"success": True, "copied": [s["name"] for s in skills], "dry_run": True}

    tmp = tmp_repo_path(cfg)

    try:
        if not clone_fresh(cfg):
            return {"success": False, "error": "clone_failed"}

        copied = copy_skills(cfg, skills, tmp)
        if not copied:
            return {"success": True, "copied": [], "note": "nothing_to_copy"}

        update_manifest(cfg, copied, tmp)

        if not commit_and_push(cfg, copied, tmp):
            return {"success": False, "copied": copied, "error": "push_failed"}

        sync_state = {
            "last_push": now_iso(),
            "pushed_skills": copied,
            "git_sha": get_workspace_git_sha(),
        }
        save_state(cfg, "last_push.json", sync_state)
        log_event(cfg, "push", {"skills": copied})

        print(f"\n✓ Push complete: {len(copied)} skills synced")
        return {"success": True, "copied": copied}

    finally:
        if tmp.exists():
            shutil.rmtree(tmp)


def main():
    parser = argparse.ArgumentParser(description="Zo Substrate — Push skills")
    parser.add_argument("--skills", help="Comma-separated skill slugs to push (default: all configured)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be pushed")
    args = parser.parse_args()

    cfg = load_config()
    filter_skills = [s.strip() for s in args.skills.split(",")] if args.skills else None
    result = push(cfg, filter_skills=filter_skills, dry_run=args.dry_run)
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
