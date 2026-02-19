#!/usr/bin/env python3
"""
Zo Substrate — Skill bundling and validation.

Creates tarball bundles of skills with metadata and checksums.
Validates received bundles before installation.
"""

import argparse
import hashlib
import json
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from config import (
    WORKSPACE_ROOT, compute_checksum, discover_skills,
    get_workspace_git_sha, load_config, now_iso,
)

SKIP_PATTERNS = {"__pycache__", ".git", ".pyc", "node_modules", ".DS_Store"}


def collect_files(skill_path: Path) -> List[Path]:
    """Collect all files in a skill directory, skipping junk."""
    files = []
    for item in skill_path.rglob("*"):
        if item.is_file() and not any(p in str(item) for p in SKIP_PATTERNS):
            files.append(item)
    return sorted(files)


def create_metadata(
    skill_name: str,
    skill_path: Path,
    files: List[Path],
    identity_name: str,
    version: str = "1.0.0",
    notes: str = "",
) -> Dict:
    """Create metadata.json content for a skill bundle."""
    checksums = {}
    file_list = []

    for f in files:
        rel = str(f.relative_to(skill_path))
        file_list.append(rel)
        checksums[rel] = compute_checksum(f)

    return {
        "schema_version": "1.0",
        "name": skill_name,
        "version": version,
        "exported_from": identity_name,
        "exported_at": now_iso(),
        "git_sha": get_workspace_git_sha(),
        "files": file_list,
        "checksums": checksums,
        "notes": notes,
    }


def create_bundle(
    skill_name: str,
    identity_name: str,
    output_dir: Path,
    version: str = "1.0.0",
    notes: str = "",
    dry_run: bool = False,
) -> Dict:
    """
    Create a skill bundle tarball.

    Returns dict with bundle info: {skill, version, path, size_bytes, files, checksum, metadata}.
    """
    skill_path = WORKSPACE_ROOT / "Skills" / skill_name

    if not skill_path.exists():
        raise ValueError(f"Skill not found: {skill_path}")
    if not (skill_path / "SKILL.md").exists():
        raise ValueError(f"Skill missing SKILL.md: {skill_path}")

    files = collect_files(skill_path)
    if not files:
        raise ValueError(f"No files found in skill: {skill_path}")

    metadata = create_metadata(skill_name, skill_path, files, identity_name, version, notes)

    if dry_run:
        return {
            "skill": skill_name,
            "version": version,
            "files": len(files),
            "metadata": metadata,
            "dry_run": True,
        }

    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    tarball_name = f"{skill_name}-v{version}-{timestamp}.tar.gz"
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / tarball_name

    with tempfile.TemporaryDirectory() as tmpdir:
        meta_path = Path(tmpdir) / "metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2))

        with tarfile.open(final_path, "w:gz") as tar:
            for f in files:
                tar.add(f, arcname=str(f.relative_to(skill_path)))
            tar.add(meta_path, arcname="metadata.json")

    bundle_checksum = compute_checksum(final_path)

    return {
        "skill": skill_name,
        "version": version,
        "path": str(final_path),
        "size_bytes": final_path.stat().st_size,
        "files": len(files),
        "checksum": bundle_checksum,
        "metadata": metadata,
    }


def validate_bundle(bundle_path: Path) -> Dict:
    """
    Validate a skill bundle tarball.

    Returns dict with {valid, skill_name, errors, warnings}.
    """
    errors = []
    warnings = []
    skill_name = None

    if not bundle_path.exists():
        return {"valid": False, "skill_name": None, "errors": ["Bundle file not found"], "warnings": []}

    try:
        with tarfile.open(bundle_path, "r:gz") as tar:
            members = tar.getnames()

            if "metadata.json" not in members:
                errors.append("Missing metadata.json in bundle")
            else:
                meta_file = tar.extractfile("metadata.json")
                if meta_file:
                    metadata = json.loads(meta_file.read().decode("utf-8"))
                    skill_name = metadata.get("name")

                    if not skill_name:
                        errors.append("metadata.json missing 'name' field")
                    if metadata.get("schema_version") != "1.0":
                        warnings.append(f"Unexpected schema version: {metadata.get('schema_version')}")
                    if not metadata.get("checksums"):
                        warnings.append("No checksums in metadata — cannot verify integrity")

            if "SKILL.md" not in members:
                warnings.append("No SKILL.md in bundle root")

            for member in members:
                if member.startswith("/") or ".." in member:
                    errors.append(f"Dangerous path in archive: {member}")

    except tarfile.TarError as e:
        errors.append(f"Invalid tarball: {e}")
    except Exception as e:
        errors.append(f"Validation error: {e}")

    return {
        "valid": len(errors) == 0,
        "skill_name": skill_name,
        "errors": errors,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description="Zo Substrate — Skill bundling")
    sub = parser.add_subparsers(dest="command")

    c = sub.add_parser("create", help="Create a skill bundle")
    c.add_argument("skill", help="Skill slug to bundle")
    c.add_argument("--output", default="/tmp/zo-substrate-bundles", help="Output directory")
    c.add_argument("--version", default="1.0.0")
    c.add_argument("--notes", default="")
    c.add_argument("--dry-run", action="store_true")

    v = sub.add_parser("validate", help="Validate a skill bundle")
    v.add_argument("path", help="Path to bundle .tar.gz")

    l = sub.add_parser("list", help="List discoverable skills")

    args = parser.parse_args()

    if args.command == "create":
        cfg = load_config()
        try:
            result = create_bundle(
                args.skill,
                cfg["identity"]["name"],
                Path(args.output),
                args.version,
                args.notes,
                args.dry_run,
            )
        except (ValueError, FileNotFoundError) as e:
            print(f"Error: {e}")
            return 1
        if args.dry_run:
            print(f"[DRY RUN] Would bundle: {args.skill} ({result['files']} files)")
        else:
            print(f"Created: {result['path']} ({result['size_bytes']} bytes, {result['files']} files)")
        return 0

    elif args.command == "validate":
        result = validate_bundle(Path(args.path))
        print(f"Valid: {result['valid']}")
        if result["skill_name"]:
            print(f"Skill: {result['skill_name']}")
        for e in result["errors"]:
            print(f"  ERROR: {e}")
        for w in result["warnings"]:
            print(f"  WARN: {w}")
        return 0 if result["valid"] else 1

    elif args.command == "list":
        cfg = load_config()
        skills = discover_skills(cfg)
        print(f"{'Skill':<30} {'Scripts':<10} {'Path'}")
        print("-" * 70)
        for s in skills:
            print(f"{s['name']:<30} {'yes' if s['has_scripts'] else 'no':<10} {s['path']}")
        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
