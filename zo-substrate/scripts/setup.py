#!/usr/bin/env python3
"""
Zo Substrate — Setup helper.

Validates the environment and creates the substrate configuration
from command-line arguments. Non-interactive (Zo-friendly).
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml")
    sys.exit(1)

from config import CONFIG_EXAMPLE, CONFIG_FILE, WORKSPACE_ROOT


def check_prerequisites() -> list[str]:
    """Check that required tools are available."""
    issues = []

    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except Exception:
        issues.append("git is not installed or not in PATH")

    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
    except Exception:
        issues.append("GitHub CLI (gh) is not installed — needed for repo creation")

    if not os.environ.get("GITHUB_TOKEN"):
        try:
            result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
            if result.returncode != 0:
                issues.append("No GITHUB_TOKEN and gh not authenticated — need one or the other")
        except Exception:
            issues.append("Cannot verify GitHub authentication")

    return issues


def create_config(
    identity_name: str,
    partner_name: str,
    repo: str,
    identity_handle: str = "",
    partner_handle: str = "",
    clone_method: str = "https",
    skills: list[str] | None = None,
    auto_detect: bool = True,
) -> Path:
    """Create substrate.yaml from parameters."""
    if CONFIG_FILE.exists():
        backup = CONFIG_FILE.with_suffix(".yaml.backup")
        CONFIG_FILE.rename(backup)
        print(f"  Backed up existing config to {backup.name}")

    with open(CONFIG_EXAMPLE) as f:
        cfg = yaml.safe_load(f)

    cfg["identity"]["name"] = identity_name
    cfg["identity"]["handle"] = identity_handle
    cfg["partner"]["name"] = partner_name
    cfg["partner"]["handle"] = partner_handle
    cfg["substrate"]["repo"] = repo
    cfg["substrate"]["clone_method"] = clone_method
    cfg["export"]["auto_detect"] = auto_detect

    if skills:
        cfg["export"]["skills"] = skills

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

    print(f"✓ Config written: {CONFIG_FILE}")
    return CONFIG_FILE


def create_repo(repo: str, private: bool = True, dry_run: bool = False) -> bool:
    """Create the GitHub substrate repository if it doesn't exist."""
    result = subprocess.run(
        ["gh", "repo", "view", repo, "--json", "name"],
        capture_output=True,
    )
    if result.returncode == 0:
        print(f"  Repo {repo} already exists")
        return True

    visibility = "--private" if private else "--public"
    desc = "Zo-to-Zo substrate for skill exchange"

    if dry_run:
        print(f"  [DRY RUN] Would create repo: {repo} ({visibility})")
        return True

    result = subprocess.run(
        ["gh", "repo", "create", repo, visibility, "--description", desc],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"  ✓ Created repo: {repo}")

        init_repo(repo)
        return True
    else:
        print(f"  ✗ Failed to create repo: {result.stderr}")
        return False


def init_repo(repo: str) -> None:
    """Initialize the substrate repo with base structure."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "repo"
        subprocess.run(["git", "clone", f"https://github.com/{repo}.git", str(tmp)],
                       capture_output=True, check=True)

        readme = tmp / "README.md"
        readme.write_text(
            "# Zo Substrate\n\n"
            "Shared substrate repository for Zo-to-Zo skill exchange.\n\n"
            "This repo is managed by [zo-substrate](https://github.com/<YOUR_GITHUB>/zo-substrate).\n\n"
            "## Structure\n\n"
            "```\n"
            "Skills/          # Synced skills\n"
            "MANIFEST.json    # Auto-generated sync manifest\n"
            "```\n"
        )

        (tmp / "Skills").mkdir(exist_ok=True)
        (tmp / "Skills" / ".gitkeep").touch()

        manifest = {
            "generated_at": "",
            "source": "",
            "exported_skills": [],
            "skill_count": 0,
            "schema_version": "1.0",
        }
        (tmp / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))

        subprocess.run(["git", "add", "-A"], cwd=tmp, capture_output=True)
        subprocess.run(["git", "config", "user.email", "zo@zo.computer"], cwd=tmp, capture_output=True)
        subprocess.run(["git", "config", "user.name", "zo-substrate"], cwd=tmp, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initialize substrate repo"], cwd=tmp, capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=tmp, capture_output=True, check=False)
        subprocess.run(["git", "push", "origin", "master:main"], cwd=tmp, capture_output=True, check=False)

    print("  ✓ Repo initialized with base structure")


def main():
    parser = argparse.ArgumentParser(description="Zo Substrate — Setup")
    sub = parser.add_subparsers(dest="command")

    ch = sub.add_parser("check", help="Check prerequisites")

    init = sub.add_parser("init", help="Create config and optionally create repo")
    init.add_argument("--identity", required=True, help="This Zo's name (e.g., 'va')")
    init.add_argument("--partner", required=True, help="Partner Zo's name (e.g., '<YOUR_INSTANCE>')")
    init.add_argument("--repo", required=True, help="GitHub repo (e.g., 'user/substrate-repo')")
    init.add_argument("--identity-handle", default="", help="This Zo's handle (e.g., '<YOUR_HANDLE>.zo.computer')")
    init.add_argument("--partner-handle", default="", help="Partner's handle")
    init.add_argument("--clone-method", default="https", choices=["https", "ssh"])
    init.add_argument("--skills", help="Comma-separated skill slugs to export (default: auto-detect)")
    init.add_argument("--create-repo", action="store_true", help="Also create the GitHub repo")
    init.add_argument("--private", action="store_true", default=True, help="Make repo private (default)")
    init.add_argument("--public", action="store_true", help="Make repo public")
    init.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "check":
        issues = check_prerequisites()
        if issues:
            print("Prerequisites check FAILED:")
            for i in issues:
                print(f"  ✗ {i}")
            sys.exit(1)
        else:
            print("✓ All prerequisites met")
            sys.exit(0)

    elif args.command == "init":
        issues = check_prerequisites()
        if issues:
            print("Prerequisites check:")
            for i in issues:
                print(f"  ⚠ {i}")

        skills = [s.strip() for s in args.skills.split(",")] if args.skills else None
        private = not args.public

        if args.create_repo:
            create_repo(args.repo, private=private, dry_run=args.dry_run)

        if not args.dry_run:
            create_config(
                identity_name=args.identity,
                partner_name=args.partner,
                repo=args.repo,
                identity_handle=args.identity_handle,
                partner_handle=args.partner_handle,
                clone_method=args.clone_method,
                skills=skills,
            )
        else:
            print(f"[DRY RUN] Would create config for {args.identity} ↔ {args.partner} via {args.repo}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
