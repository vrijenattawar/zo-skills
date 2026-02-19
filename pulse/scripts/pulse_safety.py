#!/usr/bin/env python3
"""
Pulse Safety Layer: Pre-build checks, artifact verification, git snapshots.

Functions:
  pre_build_check(slug)     - Run before starting a build
  verify_artifacts(slug)    - Verify all claimed artifacts exist
  create_snapshot(slug)     - Git stash/branch before build
  restore_snapshot(slug)    - Restore from snapshot if build fails
  run_integration_tests(slug) - Run build-specific integration tests
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pulse_common import PATHS, WORKSPACE
BUILDS_DIR = WORKSPACE / "N5" / "builds"


def run_cmd(cmd: str, cwd: str = None) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)"""
    cwd = cwd or str(PATHS.WORKSPACE)
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def pre_build_check(slug: str) -> dict:
    """
    Run pre-build safety checks:
    1. Git status clean (no uncommitted changes that could be lost)
    2. No other active builds that might conflict
    3. Required directories exist
    4. Create git snapshot
    """
    results = {
        "slug": slug,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {},
        "passed": True,
        "snapshot_ref": None
    }
    
    # Check 1: Git status
    code, stdout, stderr = run_cmd("git status --porcelain")
    if stdout.strip():
        results["checks"]["git_clean"] = {
            "passed": False,
            "message": f"Uncommitted changes detected: {len(stdout.strip().splitlines())} files",
            "details": stdout.strip()[:500]
        }
        # Not a hard fail - we'll stash
    else:
        results["checks"]["git_clean"] = {"passed": True, "message": "Working directory clean"}
    
    # Check 2: Build directory exists and is valid
    build_dir = BUILDS_DIR / slug
    meta_path = build_dir / "meta.json"
    
    if not build_dir.exists():
        results["checks"]["build_exists"] = {"passed": False, "message": f"Build directory not found: {build_dir}"}
        results["passed"] = False
        return results
    
    if not meta_path.exists():
        results["checks"]["build_exists"] = {"passed": False, "message": "meta.json not found"}
        results["passed"] = False
        return results
    
    results["checks"]["build_exists"] = {"passed": True, "message": "Build directory valid"}
    
    # Check 3: No conflicting active builds
    active_builds = []
    for d in BUILDS_DIR.iterdir():
        if d.is_dir() and d.name != slug:
            other_meta = d / "meta.json"
            if other_meta.exists():
                with open(other_meta) as f:
                    other = json.load(f)
                if other.get("status") in ["active", "in_progress"]:
                    active_builds.append(d.name)
    
    if active_builds:
        results["checks"]["no_conflicts"] = {
            "passed": True,  # Warning, not failure
            "message": f"Other active builds: {', '.join(active_builds)}",
            "warning": True
        }
    else:
        results["checks"]["no_conflicts"] = {"passed": True, "message": "No conflicting builds"}
    
    # Check 4: Create git snapshot
    snapshot_result = create_snapshot(slug)
    results["checks"]["snapshot"] = snapshot_result
    results["snapshot_ref"] = snapshot_result.get("ref")
    
    if not snapshot_result.get("passed"):
        results["passed"] = False
    
    # Check 5: Required subdirectories
    for subdir in ["drops", "deposits", "artifacts"]:
        subdir_path = build_dir / subdir
        if not subdir_path.exists():
            subdir_path.mkdir(parents=True)
    
    results["checks"]["directories"] = {"passed": True, "message": "Required directories present"}
    
    # Save pre-build report
    report_path = build_dir / "pre_build_check.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    
    return results


def create_snapshot(slug: str) -> dict:
    """Create a git snapshot before build starts"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    branch_name = f"pre-build-{slug}-{timestamp}"
    
    # Check if we have uncommitted changes
    code, stdout, _ = run_cmd("git status --porcelain")
    has_changes = bool(stdout.strip())
    
    if has_changes:
        # Stash changes
        stash_msg = f"pulse-pre-build-{slug}-{timestamp}"
        code, stdout, stderr = run_cmd(f'git stash push -m "{stash_msg}"')
        if code != 0:
            return {"passed": False, "message": f"Failed to stash: {stderr}", "ref": None}
        
        # Get stash ref
        code, stdout, _ = run_cmd("git stash list -1")
        stash_ref = stdout.strip().split(":")[0] if stdout.strip() else "stash@{0}"
        
        return {
            "passed": True, 
            "message": f"Stashed uncommitted changes",
            "ref": stash_ref,
            "type": "stash",
            "stash_message": stash_msg
        }
    else:
        # Just record current commit
        code, stdout, _ = run_cmd("git rev-parse HEAD")
        commit = stdout.strip()[:8]
        
        return {
            "passed": True,
            "message": f"Snapshot at commit {commit}",
            "ref": commit,
            "type": "commit"
        }


def restore_snapshot(slug: str) -> dict:
    """Restore from pre-build snapshot if build fails"""
    build_dir = BUILDS_DIR / slug
    check_path = build_dir / "pre_build_check.json"
    
    if not check_path.exists():
        return {"success": False, "message": "No pre-build check found"}
    
    with open(check_path) as f:
        check = json.load(f)
    
    snapshot = check.get("checks", {}).get("snapshot", {})
    snapshot_type = snapshot.get("type")
    ref = snapshot.get("ref")
    
    if not ref:
        return {"success": False, "message": "No snapshot reference found"}
    
    if snapshot_type == "stash":
        # Pop the stash
        code, stdout, stderr = run_cmd(f"git stash pop {ref}")
        if code != 0:
            return {"success": False, "message": f"Failed to restore stash: {stderr}"}
        return {"success": True, "message": f"Restored from stash {ref}"}
    
    elif snapshot_type == "commit":
        # Hard reset to commit (dangerous - only if build truly failed)
        code, stdout, stderr = run_cmd(f"git reset --hard {ref}")
        if code != 0:
            return {"success": False, "message": f"Failed to reset: {stderr}"}
        return {"success": True, "message": f"Reset to commit {ref}"}
    
    return {"success": False, "message": f"Unknown snapshot type: {snapshot_type}"}


def verify_artifacts(slug: str) -> dict:
    """
    Verify all artifacts claimed in deposits actually exist.
    Returns detailed report of what's present vs missing.
    """
    build_dir = BUILDS_DIR / slug
    deposits_dir = build_dir / "deposits"
    
    results = {
        "slug": slug,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "drops": {},
        "summary": {
            "total_artifacts": 0,
            "verified": 0,
            "missing": 0,
            "errors": 0
        },
        "passed": True
    }
    
    if not deposits_dir.exists():
        results["passed"] = False
        results["error"] = "Deposits directory not found"
        return results
    
    # Check each deposit
    for deposit_file in deposits_dir.glob("D*.json"):
        if "_filter" in deposit_file.name or "_forensics" in deposit_file.name:
            continue
        
        drop_id = deposit_file.stem
        
        try:
            with open(deposit_file) as f:
                deposit = json.load(f)
        except Exception as e:
            results["drops"][drop_id] = {"error": str(e)}
            results["summary"]["errors"] += 1
            continue
        
        # Extract artifacts from deposit
        artifacts = deposit.get("artifacts", [])
        if isinstance(artifacts, dict):
            artifacts = list(artifacts.values())
        
        drop_result = {
            "claimed": [],
            "verified": [],
            "missing": []
        }
        
        for artifact in artifacts:
            # Normalize path
            if isinstance(artifact, str):
                path = artifact
            elif isinstance(artifact, dict):
                path = artifact.get("path") or artifact.get("file")
            else:
                continue
            
            if not path:
                continue
            
            # Make path absolute if relative
            if not path.startswith("/"):
                # Try relative to build artifacts dir
                full_path = build_dir / "artifacts" / path
                if not full_path.exists():
                    # Try relative to workspace
                    full_path = WORKSPACE / path
                if not full_path.exists():
                    # Try as-is from build dir
                    full_path = build_dir / path
            else:
                full_path = Path(path)
            
            drop_result["claimed"].append(str(path))
            results["summary"]["total_artifacts"] += 1
            
            if full_path.exists():
                drop_result["verified"].append(str(path))
                results["summary"]["verified"] += 1
            else:
                drop_result["missing"].append(str(path))
                results["summary"]["missing"] += 1
                results["passed"] = False
        
        results["drops"][drop_id] = drop_result
    
    # Save verification report
    report_path = build_dir / "artifact_verification.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    
    return results


def run_integration_tests(slug: str) -> dict:
    """
    Run integration tests for the build.
    Looks for:
    1. N5/builds/<slug>/tests/ directory with test scripts
    2. package.json with test script
    3. pytest files
    """
    build_dir = BUILDS_DIR / slug
    results = {
        "slug": slug,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tests_found": [],
        "tests_run": [],
        "passed": True,
        "details": {}
    }
    
    # Check for test directory in build
    test_dir = build_dir / "tests"
    if test_dir.exists():
        for test_file in test_dir.glob("*.py"):
            results["tests_found"].append(str(test_file))
            code, stdout, stderr = run_cmd(f"python3 {test_file}")
            test_result = {
                "file": str(test_file),
                "passed": code == 0,
                "stdout": stdout[:1000],
                "stderr": stderr[:1000]
            }
            results["tests_run"].append(test_result)
            results["details"][test_file.name] = test_result
            if code != 0:
                results["passed"] = False
        
        for test_file in test_dir.glob("*.sh"):
            results["tests_found"].append(str(test_file))
            code, stdout, stderr = run_cmd(f"bash {test_file}")
            test_result = {
                "file": str(test_file),
                "passed": code == 0,
                "stdout": stdout[:1000],
                "stderr": stderr[:1000]
            }
            results["tests_run"].append(test_result)
            results["details"][test_file.name] = test_result
            if code != 0:
                results["passed"] = False
    
    # Check for integration test config in meta
    meta_path = build_dir / "meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        
        test_config = meta.get("integration_tests", {})
        for test_name, test_cmd in test_config.items():
            results["tests_found"].append(test_name)
            code, stdout, stderr = run_cmd(test_cmd)
            test_result = {
                "name": test_name,
                "command": test_cmd,
                "passed": code == 0,
                "stdout": stdout[:1000],
                "stderr": stderr[:1000]
            }
            results["tests_run"].append(test_result)
            results["details"][test_name] = test_result
            if code != 0:
                results["passed"] = False
    
    if not results["tests_found"]:
        results["message"] = "No integration tests defined"
    
    # Save test results
    report_path = build_dir / "integration_test_results.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pulse Safety Layer")
    parser.add_argument("command", choices=["pre-check", "verify", "snapshot", "restore", "test"])
    parser.add_argument("slug", help="Build slug")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    
    args = parser.parse_args()
    
    if args.command == "pre-check":
        result = pre_build_check(args.slug)
    elif args.command == "verify":
        result = verify_artifacts(args.slug)
    elif args.command == "snapshot":
        result = create_snapshot(args.slug)
    elif args.command == "restore":
        result = restore_snapshot(args.slug)
    elif args.command == "test":
        result = run_integration_tests(args.slug)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("passed", result.get("success", True)):
            print(f"✅ {args.command} passed for {args.slug}")
        else:
            print(f"❌ {args.command} failed for {args.slug}")
            if "message" in result:
                print(f"   {result['message']}")
        
        # Print details for verify
        if args.command == "verify":
            s = result["summary"]
            print(f"   Artifacts: {s['verified']}/{s['total_artifacts']} verified, {s['missing']} missing")


if __name__ == "__main__":
    main()
