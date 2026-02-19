#!/usr/bin/env python3
"""
Pulse Smart Sentinel: Monitor and recover active builds.

Designed to run as a scheduled agent every 3-5 minutes.
- If no active builds: exits immediately (cheap)
- If active builds: runs pulse tick, then assess_and_recover for each
- Checks for pause/stop signals before running

Control signals (set via N5/config/pulse_control.json):
  - "active": normal operation
  - "paused": skip ticks, stay alive
  - "stopped": exit, agent should be deleted

Recovery Rules:
  R1: dead + retry_count < max → auto-retry
  R2: failed + spawn_error + retry_count < max → auto-retry
  R3: failed + content_error → needs AI judgment
  R4: all blocking drops in wave dead/failed → build BLOCKED
  R5: build active >4h with no progress → stale escalation
"""

import json
import sys
import argparse
import asyncio
from pathlib import Path
from datetime import datetime, timezone
import os
from pulse_common import PATHS, WORKSPACE

BUILDS_DIR = PATHS.BUILDS
CONTROL_FILE = PATHS.WORKSPACE / "N5" / "config" / "pulse_control.json"
DEFAULT_TICK_TIMEOUT_SECONDS = 120


def get_control_state() -> dict:
    """Read control state, create default if missing."""
    if not CONTROL_FILE.exists():
        CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)
        default = {"state": "active", "updated_at": datetime.now(timezone.utc).isoformat()}
        with open(CONTROL_FILE, 'w') as f:
            json.dump(default, f, indent=2)
        return default

    with open(CONTROL_FILE) as f:
        return json.load(f)


def find_active_builds() -> list[str]:
    """Find all builds with status=active."""
    active = []
    if not BUILDS_DIR.exists():
        return active

    for meta_path in BUILDS_DIR.glob("*/meta.json"):
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            if meta.get("status") == "active":
                active.append(meta.get("slug", meta_path.parent.name))
        except (json.JSONDecodeError, KeyError):
            continue

    return active


def format_recovery_summary(actions: list[dict]) -> str:
    """Format recovery actions into a human-readable summary."""
    if not actions:
        return ""

    retries = [a for a in actions if a.get("action") == "auto_retry"]
    escalations = [a for a in actions if a.get("action") == "escalate"]
    judgments = [a for a in actions if a.get("action") == "needs_judgment"]

    lines = []
    if retries:
        lines.append(f"  🔄 Auto-retried: {', '.join(a['drop_id'] for a in retries)}")
    if judgments:
        lines.append(f"  🔍 Needs judgment: {', '.join(a['drop_id'] for a in judgments)}")
    if escalations:
        for a in escalations:
            lines.append(f"  ⚠️  Escalation: {a['drop_id']} — {a.get('reason', '?')}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Pulse Smart Sentinel")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be ticked/recovered without mutating builds")
    parser.add_argument("--check-token", action="store_true",
                        help="Check if ZO_CLIENT_IDENTITY_TOKEN is available")
    args = parser.parse_args()

    if args.check_token:
        token_present = bool(os.environ.get("ZO_CLIENT_IDENTITY_TOKEN"))
        print(f"[SENTINEL] Token present: {token_present}")
        sys.exit(0 if token_present else 1)

    control = get_control_state()
    state = control.get("state", "active")

    if state == "stopped":
        print("[SENTINEL] Stop signal detected. Agent should be deleted.")
        sys.exit(0)

    if state == "paused":
        print("[SENTINEL] Paused. Skipping tick.")
        sys.exit(0)

    active_builds = find_active_builds()

    if not active_builds:
        print("[SENTINEL] No active builds. Idle.")
        sys.exit(0)

    token_present = bool(os.environ.get("ZO_CLIENT_IDENTITY_TOKEN"))
    print(f"[SENTINEL] Found {len(active_builds)} active build(s): {', '.join(active_builds)}")
    print(f"[SENTINEL] Token present: {token_present}")

    if args.dry_run:
        print("[SENTINEL] Dry-run mode: reporting without mutations.")

    from pulse import tick, assess_and_recover, load_meta

    all_actions = {}

    for slug in active_builds:
        print(f"\n[SENTINEL] === {slug} ===")
        try:
            meta = load_meta(slug)
            lease = meta.get("tick_lease", {})
            circuit = meta.get("spawn_circuit", {})
            if lease:
                print(f"[SENTINEL] Lease: holder={lease.get('holder')} expires={lease.get('expires_at')}")
            if circuit.get("open"):
                print(f"[SENTINEL] Circuit: open until {circuit.get('open_until')} ({circuit.get('open_reason', '?')})")
        except Exception as e:
            print(f"[SENTINEL] Warning: could not read meta for {slug}: {e}")

        # Phase 1: Tick (existing orchestration cycle)
        if not args.dry_run:
            print(f"[SENTINEL] Ticking {slug}...")
            try:
                asyncio.run(asyncio.wait_for(tick(slug), timeout=DEFAULT_TICK_TIMEOUT_SECONDS))
            except asyncio.TimeoutError:
                print(f"[SENTINEL] Tick timeout for {slug} after {DEFAULT_TICK_TIMEOUT_SECONDS}s")
            except Exception as e:
                print(f"[SENTINEL] Error ticking {slug}: {e}")
        else:
            print(f"[SENTINEL] Dry-run: would tick {slug}")

        # Phase 2: Assess and recover
        print(f"[SENTINEL] Assessing recovery for {slug}...")
        try:
            actions = assess_and_recover(slug, dry_run=args.dry_run)
            if actions:
                all_actions[slug] = actions
                summary = format_recovery_summary(actions)
                print(f"[SENTINEL] Recovery actions for {slug}:")
                print(summary)
            else:
                print(f"[SENTINEL] No recovery needed for {slug}")
        except Exception as e:
            print(f"[SENTINEL] Error assessing {slug}: {e}")

    # Summary
    total_actions = sum(len(a) for a in all_actions.values())
    if total_actions > 0:
        print(f"\n[SENTINEL] Total recovery actions: {total_actions}")
        for slug, actions in all_actions.items():
            retries = sum(1 for a in actions if a.get("action") == "auto_retry")
            escalations = sum(1 for a in actions if a.get("action") == "escalate")
            judgments = sum(1 for a in actions if a.get("action") == "needs_judgment")
            parts = []
            if retries:
                parts.append(f"{retries} retries")
            if escalations:
                parts.append(f"{escalations} escalations")
            if judgments:
                parts.append(f"{judgments} need judgment")
            print(f"  {slug}: {', '.join(parts)}")
    else:
        print("\n[SENTINEL] All builds healthy. No recovery needed.")

    print(f"\n[SENTINEL] Tick cycle complete.")


if __name__ == "__main__":
    main()
