#!/usr/bin/env python3
"""
Zo Substrate — Pull skills from the shared substrate repository.

Clones the substrate repo, reads MANIFEST.json, and installs
new/updated skills into the local workspace.
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config import (
    WORKSPACE_ROOT, load_config, load_state, log_event,
    now_iso, repo_url, run_git, save_state, tmp_repo_path,
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
        run_git(
            ["git", "clone", "--branch", branch, "--single-branch", url, str(tmp)],
            cwd=Path("/tmp"),
        )
        print("  Clone OK")
        return True
    except Exception as e:
        print(f"  Clone failed: {e}")
        return False


def read_manifest(tmp: Path) -> Optional[Dict]:
    """Read MANIFEST.json from the cloned repo."""
    manifest_path = tmp / "MANIFEST.json"
    if not manifest_path.exists():
        print("  WARNING: No MANIFEST.json found in substrate repo")
        return None

    try:
        return json.loads(manifest_path.read_text())
    except Exception as e:
        print(f"  ERROR reading MANIFEST.json: {e}")
        return None


def detect_changes(
    cfg: Dict,
    manifest: Dict,
    tmp: Path,
) -> List[Dict]:
    """
    Compare substrate skills with local state to find what's new/changed.

    Returns list of dicts: [{name, reason}, ...]
    """
    last_pull = load_state(cfg, "last_pull.json")
    last_skills = {s: True for s in last_pull.get("pulled_skills", [])}
    last_sha = last_pull.get("substrate_sha", "")

    skills_dir = tmp / "Skills"
    if not skills_dir.exists():
        return []

    changes = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        name = skill_dir.name

        if name not in last_skills:
            changes.append({"name": name, "reason": "new"})
        else:
            changes.append({"name": name, "reason": "update_check"})

    return changes


def install_skill(
    skill_name: str,
    source: Path,
    cfg: Dict,
    backup: bool = True,
) -> bool:
    """Install a skill from the substrate clone into the local workspace."""
    install_dir = WORKSPACE_ROOT / cfg["pull"]["install_dir"]
    install_dir.mkdir(parents=True, exist_ok=True)
    dest = install_dir / skill_name

    skip_patterns = {"__pycache__", ".git", "node_modules", ".DS_Store", ".pyc"}

    def ignore_fn(directory, contents):
        return [c for c in contents if c in skip_patterns]

    if dest.exists() and backup:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = install_dir / ".backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{skill_name}.{ts}"
        shutil.move(str(dest), str(backup_path))
        print(f"    Backed up: .backups/{skill_name}.{ts}")

    elif dest.exists():
        shutil.rmtree(dest)

    shutil.copytree(source, dest, ignore=ignore_fn)
    return True


def pull(
    cfg: Dict,
    filter_skills: Optional[List[str]] = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> Dict:
    """
    Main pull operation.

    Returns dict: {success, installed, skipped, error}.
    """
    print(f"=== Zo Substrate Pull ===")
    print(f"  To: {cfg['identity']['name']}")
    print(f"  Repo: {cfg['substrate']['repo']}")

    tmp = tmp_repo_path(cfg)

    try:
        if not clone_fresh(cfg):
            return {"success": False, "error": "clone_failed"}

        manifest = read_manifest(tmp)
        if manifest and verbose:
            print(f"  Manifest source: {manifest.get('source', 'unknown')}")
            print(f"  Skills in repo: {manifest.get('skill_count', '?')}")

        skills_dir = tmp / "Skills"
        if not skills_dir.exists():
            print("  No Skills/ directory in substrate repo")
            return {"success": True, "installed": []}

        available = [d.name for d in skills_dir.iterdir() if d.is_dir()]
        if filter_skills:
            to_install = [s for s in available if s in filter_skills]
            if not to_install:
                print(f"  ⚠ No matching skills found for filter: {', '.join(filter_skills)}")
                print(f"  Available in repo: {', '.join(available) if available else 'none'}")
                return {"success": False, "installed": [], "error": "no_match"}
        else:
            to_install = available

        if not to_install:
            print("  No skills to pull")
            return {"success": True, "installed": []}

        print(f"  Skills available: {len(available)}")
        print(f"  Skills to install: {len(to_install)}")

        if dry_run:
            print("\n  [DRY RUN] Would install:")
            for name in sorted(to_install):
                local = WORKSPACE_ROOT / cfg["pull"]["install_dir"] / name
                status = "UPDATE" if local.exists() else "NEW"
                print(f"    - {name} [{status}]")
            return {"success": True, "installed": to_install, "dry_run": True}

        installed = []
        backup = cfg["pull"].get("backup_existing", True)

        for name in sorted(to_install):
            source = skills_dir / name
            print(f"  Installing: {name}")
            try:
                install_skill(name, source, cfg, backup=backup)
                installed.append(name)
            except Exception as e:
                print(f"    FAILED: {e}")

        get_sha_cmd = ["git", "rev-parse", "HEAD"]
        _, sha, _ = run_git(get_sha_cmd, tmp, check=False)

        sync_state = {
            "last_pull": now_iso(),
            "pulled_skills": installed,
            "substrate_sha": sha,
            "source": manifest.get("source", "unknown") if manifest else "unknown",
        }
        save_state(cfg, "last_pull.json", sync_state)
        log_event(cfg, "pull", {"skills": installed})

        print(f"\n✓ Pull complete: {len(installed)} skills installed")
        return {"success": True, "installed": installed}

    finally:
        if tmp.exists():
            shutil.rmtree(tmp)


def main():
    parser = argparse.ArgumentParser(description="Zo Substrate — Pull skills")
    parser.add_argument("--skills", help="Comma-separated skill slugs to pull (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be pulled")
    parser.add_argument("--verbose", action="store_true", help="Detailed output")
    args = parser.parse_args()

    cfg = load_config()
    filter_skills = [s.strip() for s in args.skills.split(",")] if args.skills else None
    result = pull(cfg, filter_skills=filter_skills, dry_run=args.dry_run, verbose=args.verbose)
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
