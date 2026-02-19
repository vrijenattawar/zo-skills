#!/usr/bin/env python3
"""Test script to verify validator wiring in pulse.py tick loop.

This script:
1. Creates a test build with a stub-containing deposit
2. Runs the tick loop
3. Verifies the deposit is rejected by validators
4. Cleans up
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BUILDS_DIR = Path("./N5/builds")
TEST_SLUG = "test-validator-wiring"


def setup_test_build():
    """Create a test build with a bad deposit."""
    build_dir = BUILDS_DIR / TEST_SLUG
    
    # Clean up any previous test
    if build_dir.exists():
        shutil.rmtree(build_dir)
    
    # Create directory structure
    (build_dir / "drops").mkdir(parents=True)
    (build_dir / "deposits").mkdir(parents=True)
    (build_dir / "artifacts").mkdir(parents=True)
    
    # Create meta.json
    meta = {
        "slug": TEST_SLUG,
        "title": "Validator Wiring Test",
        "status": "active",
        "current_stream": 1,
        "total_streams": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "drops": {
            "D1.1": {
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "conversation_id": "test_convo_001"
            }
        }
    }
    (build_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    
    # Create a drop brief
    brief = """---
drop_id: D1.1
build_slug: test-validator-wiring
stream: 1
title: "Test Drop"
---

# D1.1: Test Drop

## Objective
Create a function that adds two numbers.

## Deliverables
1. Create `test.py` with an add function

## Success Criteria
- [ ] Function actually implements addition
"""
    (build_dir / "drops" / "D1.1-test-drop.md").write_text(brief)
    
    # Create a deposit claiming completion
    deposit = {
        "drop_id": "D1.1",
        "status": "complete",
        "summary": "Created add function",
        "artifacts": [f"N5/builds/{TEST_SLUG}/artifacts/test.py"]
    }
    (build_dir / "deposits" / "D1.1.json").write_text(json.dumps(deposit, indent=2))
    
    # Create artifact with stub code (should fail validation)
    stub_code = '''def add(a, b):
    pass  # TODO: implement
'''
    (build_dir / "artifacts" / "test.py").write_text(stub_code)
    
    print(f"✓ Created test build at {build_dir}")
    return build_dir


def run_tick():
    """Run pulse tick on test build."""
    print("\n[TEST] Running pulse tick...")
    result = subprocess.run(
        ["python3", "./Skills/pulse/scripts/pulse.py", "tick", TEST_SLUG],
        capture_output=True, text=True, cwd="/home/workspace"
    )
    print(f"STDOUT:\n{result.stdout}")
    if result.stderr:
        print(f"STDERR:\n{result.stderr}")
    return result.returncode


def check_results():
    """Check if validation worked correctly."""
    build_dir = BUILDS_DIR / TEST_SLUG
    
    # Check meta.json
    meta = json.loads((build_dir / "meta.json").read_text())
    drop_status = meta.get("drops", {}).get("D1.1", {}).get("status")
    
    # Check for validation result file
    validation_path = build_dir / "deposits" / "D1.1_validation.json"
    validation_exists = validation_path.exists()
    
    print(f"\n[RESULTS]")
    print(f"  Drop D1.1 status: {drop_status}")
    print(f"  Validation file exists: {validation_exists}")
    
    if validation_exists:
        validation = json.loads(validation_path.read_text())
        print(f"  Validation verdict: {validation.get('verdict')}")
        print(f"  Validation reason: {validation.get('reason')}")
        print(f"  Mechanical check: {validation.get('mechanical')}")
    
    # Success = Drop failed validation (because it has stub code)
    success = drop_status == "failed"
    
    if success:
        print("\n✅ TEST PASSED: Validator correctly rejected stub code")
    else:
        print(f"\n❌ TEST FAILED: Expected status 'failed', got '{drop_status}'")
        if drop_status == "complete":
            print("   Validation may not be running or stub detection failed")
    
    return success


def cleanup():
    """Remove test build."""
    build_dir = BUILDS_DIR / TEST_SLUG
    if build_dir.exists():
        shutil.rmtree(build_dir)
        print(f"\n✓ Cleaned up test build")


def main():
    """Run the full test."""
    print("=" * 60)
    print("VALIDATOR WIRING TEST")
    print("=" * 60)
    
    try:
        setup_test_build()
        run_tick()
        success = check_results()
        
        # Optionally leave artifacts for inspection
        if "--keep" not in sys.argv:
            cleanup()
        else:
            print(f"\n[KEEP] Test artifacts preserved at {BUILDS_DIR / TEST_SLUG}")
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        cleanup()
        return 1


if __name__ == "__main__":
    sys.exit(main())
