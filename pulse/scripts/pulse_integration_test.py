#!/usr/bin/env python3
"""
Pulse Integration Tests: Post-build verification that everything works together.

Each build can define integration tests in:
  N5/builds/<slug>/INTEGRATION_TESTS.json

Format:
{
  "tests": [
    {
      "name": "API responds",
      "type": "http",
      "config": {"url": "http://localhost:3000/health", "expected_status": 200}
    },
    {
      "name": "File exists",
      "type": "file_exists",
      "config": {"path": "Sites/mysite/dist/index.html"}
    },
    {
      "name": "Command succeeds",
      "type": "command",
      "config": {"cmd": "cd Sites/mysite && bun run build", "expected_exit": 0}
    },
    {
      "name": "File contains",
      "type": "file_contains",
      "config": {"path": "Sites/mysite/package.json", "contains": "\"name\": \"mysite\""}
    }
  ]
}

Usage:
  pulse_integration_test.py run <slug>
  pulse_integration_test.py generate <slug>  # Auto-generate from artifacts
  pulse_integration_test.py add <slug> --type <type> --config <json>
"""

import argparse
import json
import os
import subprocess
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from pulse_common import PATHS, WORKSPACE
import sys

BUILDS_DIR = WORKSPACE / "N5" / "builds"


def load_tests(slug: str) -> dict:
    """Load integration tests for a build"""
    path = BUILDS_DIR / slug / "INTEGRATION_TESTS.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"tests": []}


def save_tests(slug: str, data: dict):
    """Save integration tests"""
    path = BUILDS_DIR / slug / "INTEGRATION_TESTS.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def run_test_file_exists(config: dict) -> tuple[bool, str]:
    """Test that a file exists"""
    path = WORKSPACE / config["path"]
    if path.exists():
        return True, f"File exists: {config['path']}"
    return False, f"File missing: {config['path']}"


def run_test_file_contains(config: dict) -> tuple[bool, str]:
    """Test that a file contains expected content"""
    path = WORKSPACE / config["path"]
    if not path.exists():
        return False, f"File missing: {config['path']}"
    
    with open(path) as f:
        content = f.read()
    
    # Support both "pattern" and "contains" for backward compatibility
    search_text = config.get("pattern", config.get("contains"))
    if not search_text:
        return False, "No search pattern specified (missing 'pattern' or 'contains' key)"
    
    if search_text in content:
        return True, f"File contains expected content"
    return False, f"File missing expected content: {search_text[:50]}..."


def run_test_command(config: dict) -> tuple[bool, str]:
    """Test that a command succeeds"""
    try:
        result = subprocess.run(
            config["cmd"],
            shell=True,
            capture_output=True,
            text=True,
            timeout=config.get("timeout", 60),
            cwd=str(WORKSPACE)
        )
        expected = config.get("expected_exit", 0)
        if result.returncode == expected:
            return True, f"Command succeeded (exit {result.returncode})"
        return False, f"Command failed (exit {result.returncode}, expected {expected}): {result.stderr[:100]}"
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {config.get('timeout', 60)}s"
    except Exception as e:
        return False, f"Command error: {str(e)}"


def run_test_http(config: dict) -> tuple[bool, str]:
    """Test HTTP endpoint"""
    try:
        resp = requests.request(
            config.get("method", "GET"),
            config["url"],
            timeout=config.get("timeout", 10),
            headers=config.get("headers", {}),
            json=config.get("body")
        )
        expected = config.get("expected_status", 200)
        if resp.status_code == expected:
            # Optional: check response body
            if "expected_body_contains" in config:
                if config["expected_body_contains"] not in resp.text:
                    return False, f"Response missing expected content"
            return True, f"HTTP {resp.status_code} OK"
        return False, f"HTTP {resp.status_code} (expected {expected})"
    except requests.exceptions.ConnectionError:
        return False, "Connection refused"
    except requests.exceptions.Timeout:
        return False, "Request timed out"
    except Exception as e:
        return False, f"HTTP error: {str(e)}"


def run_test_service_running(config: dict) -> tuple[bool, str]:
    """Test that a service is running"""
    try:
        result = subprocess.run(
            f"pgrep -f '{config['process_name']}'",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return True, f"Service running: {config['process_name']}"
        return False, f"Service not running: {config['process_name']}"
    except Exception as e:
        return False, f"Check failed: {str(e)}"


def run_test_broadcast_injection(config: dict) -> tuple[bool, str]:
    """Test that broadcast injection works correctly"""
    try:
        import tempfile
        import shutil
        from pulse_common import WORKSPACE
        
        # Import the functions we need to test
        sys.path.insert(0, str(WORKSPACE / "Skills" / "pulse" / "scripts"))
        from pulse import collect_broadcasts, inject_broadcasts
        
        # Create a temporary build directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            build_path = temp_path / "test_build"
            deposits_path = build_path / "deposits"
            deposits_path.mkdir(parents=True)
            
            # Create a mock deposit with broadcast
            deposit_data = {
                "drop_id": "TEST1",
                "status": "complete",
                "broadcast": config.get("test_broadcast", "Test broadcast message")
            }
            
            with open(deposits_path / "TEST1.json", "w") as f:
                json.dump(deposit_data, f)
            
            # Test collect_broadcasts
            # Temporarily patch BUILDS_DIR to point to our temp directory
            original_builds_dir = sys.modules['pulse'].BUILDS_DIR
            sys.modules['pulse'].BUILDS_DIR = temp_path
            
            broadcasts = collect_broadcasts("test_build")
            
            # Restore original path
            sys.modules['pulse'].BUILDS_DIR = original_builds_dir
            
            if not broadcasts:
                return False, "collect_broadcasts returned empty list"
            
            if len(broadcasts) != 1:
                return False, f"Expected 1 broadcast, got {len(broadcasts)}"
            
            if broadcasts[0]["broadcast"] != deposit_data["broadcast"]:
                return False, "Broadcast content mismatch"
            
            # Test inject_broadcasts
            sample_brief = "# Test Brief\n\n## Requirements\n\nSome requirements here."
            injected_brief = inject_broadcasts(sample_brief, broadcasts)
            
            expect_section = config.get("expect_in_brief", "## Broadcasts from Prior Drops")
            if expect_section not in injected_brief:
                return False, f"Expected section '{expect_section}' not found in injected brief"
            
            # Look for the broadcast content (be flexible about format)
            broadcast_text = deposit_data["broadcast"]
            if "TEST1" not in injected_brief or broadcast_text not in injected_brief:
                return False, f"Broadcast content not properly injected. Expected 'TEST1' and '{broadcast_text}' in: {injected_brief}"
            
            return True, "Broadcast injection working correctly"
            
    except Exception as e:
        return False, f"Broadcast injection test failed: {str(e)}"


def run_test_first_wins(config: dict) -> tuple[bool, str]:
    """Test that first-wins hypothesis racing works correctly"""
    try:
        import tempfile
        from pulse_common import WORKSPACE
        
        # Import the functions we need to test
        sys.path.insert(0, str(WORKSPACE / "Skills" / "pulse" / "scripts"))
        from pulse import check_first_wins, get_deposit, save_meta
        
        # Create a temporary build directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            build_path = temp_path / "test_build"
            deposits_path = build_path / "deposits"
            deposits_path.mkdir(parents=True)
            
            # Create mock meta.json with first_wins enabled
            meta = {
                "first_wins": True,
                "hypothesis_group": ["H1", "H2", "H3"],
                "drops": {
                    "H1": {"status": "pending"},
                    "H2": {"status": "running"}, 
                    "H3": {"status": "pending"}
                }
            }
            
            with open(build_path / "meta.json", "w") as f:
                json.dump(meta, f, indent=2)
            
            # Create a deposit with confirmed verdict for H2
            deposit_data = {
                "drop_id": "H2",
                "status": "complete",
                "verdict": "confirmed"
            }
            
            with open(deposits_path / "H2.json", "w") as f:
                json.dump(deposit_data, f)
            
            # Temporarily patch BUILDS_DIR
            original_builds_dir = sys.modules['pulse'].BUILDS_DIR
            sys.modules['pulse'].BUILDS_DIR = temp_path
            
            # Test check_first_wins
            result = check_first_wins("test_build", meta)
            
            # Restore original path
            sys.modules['pulse'].BUILDS_DIR = original_builds_dir
            
            if not result:
                return False, "check_first_wins should have returned True"
            
            # Read updated meta to verify superseding worked
            with open(build_path / "meta.json") as f:
                updated_meta = json.load(f)
            
            # Verify H1 and H3 were superseded
            if updated_meta["drops"]["H1"]["status"] != "superseded":
                return False, "H1 should be superseded"
            
            if updated_meta["drops"]["H3"]["status"] != "superseded":
                return False, "H3 should be superseded"
            
            if updated_meta["drops"]["H2"]["status"] != "running":
                return False, "H2 should remain running (winner)"
            
            # Verify superseded_by field
            if updated_meta["drops"]["H1"].get("superseded_by") != "H2":
                return False, "H1 should be superseded by H2"
            
            return True, "First-wins hypothesis racing working correctly"
            
    except Exception as e:
        return False, f"First-wins test failed: {str(e)}"


def run_test_task_pool_claim(config: dict) -> tuple[bool, str]:
    """Test that task pool claiming works correctly"""
    try:
        import tempfile
        from pulse_common import WORKSPACE
        
        # Import the functions we need to test
        sys.path.insert(0, str(WORKSPACE / "Skills" / "pulse" / "scripts"))
        from pulse import claim_task
        
        # Create a temporary build directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            build_path = temp_path / "test_build"
            build_path.mkdir(parents=True)
            
            # Create mock meta.json with task pool
            pool_size = config.get("pool_size", 5)
            tasks = []
            for i in range(pool_size):
                tasks.append({
                    "id": f"task_{i}",
                    "description": f"Test task {i}",
                    "status": "pending"
                })
            
            meta = {
                "task_pool": {
                    "enabled": True,
                    "tasks": tasks
                }
            }
            
            with open(build_path / "meta.json", "w") as f:
                json.dump(meta, f, indent=2)
            
            # Temporarily patch BUILDS_DIR
            original_builds_dir = sys.modules['pulse'].BUILDS_DIR
            sys.modules['pulse'].BUILDS_DIR = temp_path
            
            # Test claiming a task
            claimed_task = claim_task("test_build", "DROP1")
            
            if not claimed_task:
                return False, "claim_task should have returned a task"
            
            if claimed_task["status"] != "claimed":
                return False, f"Task status should be 'claimed', got '{claimed_task['status']}'"
            
            if claimed_task["claimed_by"] != "DROP1":
                return False, f"Task should be claimed by DROP1, got '{claimed_task['claimed_by']}'"
            
            # Test claiming another task
            claimed_task2 = claim_task("test_build", "DROP2")
            
            if not claimed_task2:
                return False, "Second claim_task should have returned a task"
            
            if claimed_task2["id"] == claimed_task["id"]:
                return False, "Second claim should return a different task"
            
            if claimed_task2["claimed_by"] != "DROP2":
                return False, f"Second task should be claimed by DROP2, got '{claimed_task2['claimed_by']}'"
            
            # Verify meta.json was updated
            with open(build_path / "meta.json") as f:
                updated_meta = json.load(f)
            
            claimed_count = 0
            for task in updated_meta["task_pool"]["tasks"]:
                if task["status"] == "claimed":
                    claimed_count += 1
            
            if claimed_count != 2:
                return False, f"Expected 2 claimed tasks, got {claimed_count}"
            
            # Restore original path
            sys.modules['pulse'].BUILDS_DIR = original_builds_dir
            
            return True, "Task pool claiming working correctly"
            
    except Exception as e:
        return False, f"Task pool claiming test failed: {str(e)}"


TEST_RUNNERS = {
    "file_exists": run_test_file_exists,
    "file_contains": run_test_file_contains,
    "command": run_test_command,
    "http": run_test_http,
    "service_running": run_test_service_running,
    "broadcast_injection": run_test_broadcast_injection,
    "first_wins": run_test_first_wins,
    "task_pool_claim": run_test_task_pool_claim,
}


def run_single_test(test: dict) -> dict:
    """Run a single test and return result"""
    test_type = test.get("type")
    config = test.get("config", {})
    
    if test_type not in TEST_RUNNERS:
        return {
            "name": test.get("name", "unnamed"),
            "type": test_type,
            "passed": False,
            "message": f"Unknown test type: {test_type}"
        }
    
    runner = TEST_RUNNERS[test_type]
    passed, message = runner(config)
    
    return {
        "name": test.get("name", "unnamed"),
        "type": test_type,
        "passed": passed,
        "message": message
    }


def run_all_tests(slug: str) -> dict:
    """Run all integration tests for a build"""
    data = load_tests(slug)
    tests = data.get("tests", [])
    
    if not tests:
        return {
            "slug": slug,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": 0,
            "passed": 0,
            "failed": 0,
            "results": [],
            "all_passed": True,
            "message": "No integration tests defined"
        }
    
    results = []
    passed = 0
    failed = 0
    
    for test in tests:
        result = run_single_test(test)
        results.append(result)
        if result["passed"]:
            passed += 1
        else:
            failed += 1
    
    return {
        "slug": slug,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(tests),
        "passed": passed,
        "failed": failed,
        "results": results,
        "all_passed": failed == 0
    }


def generate_tests_from_artifacts(slug: str) -> list:
    """Auto-generate basic tests from build artifacts"""
    tests = []
    deposits_dir = BUILDS_DIR / slug / "deposits"
    
    if not deposits_dir.exists():
        return tests
    
    # Collect all artifacts from deposits
    artifacts = set()
    for deposit_path in deposits_dir.glob("*.json"):
        if "_filter" in deposit_path.name:
            continue
        with open(deposit_path) as f:
            deposit = json.load(f)
        for artifact in deposit.get("artifacts", []):
            if isinstance(artifact, str):
                artifacts.add(artifact)
            elif isinstance(artifact, dict):
                artifacts.add(artifact.get("path", ""))
    
    # Generate file_exists tests for each artifact
    for artifact in artifacts:
        if artifact and not artifact.startswith("/"):
            # Relative path - prepend build artifacts dir or assume workspace-relative
            tests.append({
                "name": f"Artifact exists: {Path(artifact).name}",
                "type": "file_exists",
                "config": {"path": artifact}
            })
    
    return tests


def add_test(slug: str, test_type: str, name: str, config: dict):
    """Add a test to a build"""
    data = load_tests(slug)
    data["tests"].append({
        "name": name,
        "type": test_type,
        "config": config
    })
    save_tests(slug, data)
    print(f"Added test: {name}")


def main():
    parser = argparse.ArgumentParser(description="Pulse Integration Tests")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # run
    run_parser = subparsers.add_parser("run", help="Run integration tests")
    run_parser.add_argument("slug", help="Build slug")
    run_parser.add_argument("--verbose", "-v", action="store_true")
    
    # generate
    gen_parser = subparsers.add_parser("generate", help="Auto-generate tests from artifacts")
    gen_parser.add_argument("slug", help="Build slug")
    
    # add
    add_parser = subparsers.add_parser("add", help="Add a test")
    add_parser.add_argument("slug", help="Build slug")
    add_parser.add_argument("--type", required=True, choices=list(TEST_RUNNERS.keys()))
    add_parser.add_argument("--name", required=True, help="Test name")
    add_parser.add_argument("--config", required=True, help="Config as JSON string")
    
    args = parser.parse_args()
    
    if args.command == "run":
        results = run_all_tests(args.slug)
        
        print(f"\n{'='*50}")
        print(f"Integration Tests: {args.slug}")
        print(f"{'='*50}\n")
        
        if results["total"] == 0:
            print("No tests defined. Run 'generate' to auto-create from artifacts.")
        else:
            for r in results["results"]:
                status = "✅" if r["passed"] else "❌"
                print(f"{status} {r['name']}")
                if args.verbose or not r["passed"]:
                    print(f"   {r['message']}")
            
            print(f"\n{'='*50}")
            print(f"Results: {results['passed']}/{results['total']} passed")
            
            if results["all_passed"]:
                print("✅ ALL TESTS PASSED")
            else:
                print(f"❌ {results['failed']} TESTS FAILED")
        
        # Save results
        results_path = BUILDS_DIR / args.slug / "INTEGRATION_RESULTS.json"
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {results_path}")
        
        # Exit with error if tests failed
        if not results["all_passed"]:
            exit(1)
    
    elif args.command == "generate":
        tests = generate_tests_from_artifacts(args.slug)
        if not tests:
            print("No artifacts found to generate tests from.")
        else:
            data = load_tests(args.slug)
            data["tests"].extend(tests)
            save_tests(args.slug, data)
            print(f"Generated {len(tests)} tests:")
            for t in tests:
                print(f"  - {t['name']}")
    
    elif args.command == "add":
        config = json.loads(args.config)
        add_test(args.slug, args.type, args.name, config)


if __name__ == "__main__":
    main()
