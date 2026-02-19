#!/usr/bin/env python3
"""
Pulse Dashboard Sync Script (v2)

Scans N5/builds/ for Pulse and legacy build formats, generating
dashboard-compatible JSON for Sites/build-tracker/data/builds.json

v2 Enhancements:
- Sentinel tracking (active agent, next run time)
- Drop conversation IDs for headless worker tracking
- Better status detection for running/dead drops
- Started timestamps for drops
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from pulse_common import PATHS, WORKSPACE


BUILD_DIR = PATHS.BUILDS
DEFAULT_OUTPUT = PATHS.WORKSPACE / "Sites/build-tracker/data/builds.json"
AGENTS_API_CACHE = Path("/home/.z/workspaces/_cache/agents_list.json")


def parse_timestamp(ts: str | None) -> datetime | None:
    """Parse various timestamp formats to UTC datetime."""
    if not ts:
        return None

    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]:
        try:
            result = datetime.strptime(ts, fmt)
            if result.tzinfo is None:
                result = result.replace(tzinfo=timezone.utc)
            return result
        except ValueError:
            continue

    return None


def get_agents_from_api() -> list[dict]:
    """
    Get scheduled agents. 
    This would need to be called via Zo API in practice.
    For now, we cache the result if available.
    """
    if AGENTS_API_CACHE.exists():
        try:
            cache_stat = AGENTS_API_CACHE.stat()
            cache_age = datetime.now().timestamp() - cache_stat.st_mtime
            if cache_age < 300:
                with open(AGENTS_API_CACHE) as f:
                    return json.load(f)
        except:
            pass
    return []


def find_sentinel_for_build(slug: str, agents: list[dict]) -> dict | None:
    """Find the Pulse Sentinel agent for a specific build."""
    for agent in agents:
        instruction = agent.get("instruction", "")
        title = agent.get("title", "")
        
        if not agent.get("active", False):
            continue
            
        if f"build: {slug}" in instruction or f"<slug>/{slug}" in instruction:
            return {
                "agent_id": agent.get("id"),
                "title": title,
                "next_run": agent.get("next_run"),
                "rrule": agent.get("rrule"),
                "active": agent.get("active", False),
            }
        
        if "Pulse Sentinel" in title and slug in instruction:
            return {
                "agent_id": agent.get("id"),
                "title": title,
                "next_run": agent.get("next_run"),
                "rrule": agent.get("rrule"),
                "active": agent.get("active", False),
            }
    
    return None


def count_pulse_drops(drops: dict) -> dict:
    """Count drops by status from Pulse meta.json."""
    counts = {"complete": 0, "running": 0, "pending": 0, "dead": 0, "failed": 0, "blocked": 0}
    
    for drop_id, drop_data in drops.items():
        status = drop_data.get("status", "pending").lower()
        if status in counts:
            counts[status] += 1
        elif status == "active":
            counts["running"] += 1
        elif status in ("error", "cancelled"):
            counts["failed"] += 1
        elif status == "awaiting_manual":
            counts["pending"] += 1
        else:
            counts["pending"] += 1
    
    counts["total"] = sum(counts.values())
    return counts


def extract_drop_details(drops: dict, build_path: Path) -> list[dict]:
    """Extract detailed information about each drop."""
    drop_details = []
    deposits_dir = build_path / "deposits"
    
    for drop_id, drop_data in sorted(drops.items()):
        detail = {
            "id": drop_id,
            "name": drop_data.get("name", drop_id),
            "status": drop_data.get("status", "pending"),
            "stream": drop_data.get("stream", 1),
            "depends_on": drop_data.get("depends_on", []),
            "spawn_mode": drop_data.get("spawn_mode", "auto"),
            "conversation_id": drop_data.get("conversation_id"),
            "started_at": drop_data.get("started_at"),
            "completed_at": drop_data.get("completed_at"),
        }
        
        deposit_file = deposits_dir / f"{drop_id}.json"
        if deposit_file.exists():
            try:
                with open(deposit_file) as f:
                    deposit = json.load(f)
                    detail["has_deposit"] = True
                    detail["deposit_status"] = deposit.get("status")
                    detail["artifacts"] = deposit.get("artifacts", [])
            except:
                detail["has_deposit"] = False
        else:
            detail["has_deposit"] = False
        
        filter_file = deposits_dir / f"{drop_id}_filter.json"
        if filter_file.exists():
            try:
                with open(filter_file) as f:
                    filter_result = json.load(f)
                    detail["filter_verdict"] = filter_result.get("verdict")
            except:
                pass
        
        drop_details.append(detail)
    
    return drop_details


def detect_dead_drops(drops: dict, dead_threshold_seconds: int = 900) -> list[str]:
    """Detect drops that have been running too long (likely dead)."""
    now = datetime.now(timezone.utc)
    dead_drops = []
    
    for drop_id, drop_data in drops.items():
        if drop_data.get("status") != "running":
            continue
        
        started_at = drop_data.get("started_at")
        if not started_at:
            continue
        
        started = parse_timestamp(started_at)
        if started and (now - started).total_seconds() > dead_threshold_seconds:
            dead_drops.append(drop_id)
    
    return dead_drops


def read_pulse_meta(build_path: Path, agents: list[dict]) -> dict | None:
    """Read and parse Pulse format meta.json."""
    meta_file = build_path / "meta.json"
    
    if not meta_file.exists():
        return None
    
    try:
        with open(meta_file, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to parse {meta_file}: {e}", file=sys.stderr)
        return None
    
    if "drops" not in data:
        return None
    
    slug = data.get("slug", build_path.name)
    drops_data = data.get("drops", {})
    drop_counts = count_pulse_drops(drops_data)
    
    total = drop_counts["total"]
    complete = drop_counts["complete"]
    progress_pct = int((complete / total * 100)) if total > 0 else 0
    
    last_activity = None
    for drop_id, drop_data in drops_data.items():
        for ts_field in ("completed_at", "started_at", "failed_at"):
            ts = drop_data.get(ts_field)
            if ts:
                parsed = parse_timestamp(ts)
                if parsed and (last_activity is None or parsed > last_activity):
                    last_activity = parsed
                    break
    
    if not last_activity:
        for field in ("started_at", "created_at"):
            ts = data.get(field)
            if ts:
                parsed = parse_timestamp(ts)
                if parsed and (last_activity is None or parsed > last_activity):
                    last_activity = parsed
                    break
    
    created_at = None
    for field in ("created_at", "created", "started_at"):
        ts = data.get(field)
        if ts:
            created_at = parse_timestamp(ts)
            if created_at:
                break
    
    last_activity_str = last_activity.isoformat() if last_activity else None
    created_at_str = created_at.isoformat() if created_at else None
    
    status = data.get("status", "pending").lower()
    if status in ("pending", "active", "building"):
        if drop_counts["running"] > 0:
            status = "active"
        elif drop_counts["complete"] > 0 and drop_counts["pending"] > 0:
            status = "active"
        elif drop_counts["complete"] == total and total > 0:
            status = "complete"
        else:
            status = "pending"
    elif status == "tidying":
        status = "active"
    elif status not in ("complete", "failed"):
        status = "pending"
    
    dead_drops = detect_dead_drops(drops_data)
    drop_details = extract_drop_details(drops_data, build_path)
    
    sentinel = find_sentinel_for_build(slug, agents)
    
    return {
        "slug": slug,
        "title": data.get("title", build_path.name.replace("-", " ").title()),
        "status": status,
        "format": "pulse",
        "build_type": data.get("build_type", "code_build"),
        "streams": {
            "current": data.get("current_stream", 1),
            "total": data.get("total_streams", 1),
        },
        "drops": drop_counts,
        "drop_details": drop_details,
        "dead_drops": dead_drops,
        "progress_pct": progress_pct,
        "created_at": created_at_str,
        "last_activity": last_activity_str,
        "path": str(build_path.relative_to(str(PATHS.WORKSPACE))),
        "orchestrator_convo": data.get("orchestrator_convo"),
        "model": data.get("model"),
        "sentinel": sentinel,
    }


def read_legacy_build(build_path: Path) -> dict | None:
    """Read legacy build format (workers/ directory)."""
    workers_dir = build_path / "workers"
    
    if not workers_dir.exists() or not workers_dir.is_dir():
        return None
    
    created_at = None
    try:
        stat = build_path.stat()
        created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        pass
    
    status = "pending"
    status_file = None
    for name in ("STATUS.md", "BUILD_STATUS.md"):
        if (build_path / name).exists():
            status_file = build_path / name
            break
    
    if status_file:
        try:
            with open(status_file, "r") as f:
                content = f.read().lower()
                if "complete" in content:
                    status = "complete"
                elif "active" in content or "in progress" in content:
                    status = "active"
                elif "failed" in content or "blocked" in content:
                    status = "failed"
        except IOError:
            pass
    
    return {
        "slug": build_path.name,
        "title": build_path.name.replace("-", " ").title(),
        "status": status,
        "format": "legacy",
        "build_type": "unknown",
        "streams": {"current": 1, "total": 1},
        "drops": {
            "complete": 0,
            "running": 0,
            "pending": 1,
            "dead": 0,
            "failed": 0,
            "blocked": 0,
            "total": 1,
        },
        "drop_details": [],
        "dead_drops": [],
        "progress_pct": 0,
        "created_at": created_at,
        "last_activity": created_at,
        "path": str(build_path.relative_to(str(PATHS.WORKSPACE))),
        "orchestrator_convo": None,
        "model": None,
        "sentinel": None,
    }


def scan_builds(build_dir: Path, agents: list[dict]) -> list[dict]:
    """Scan build directory for Pulse and legacy builds."""
    builds = []
    
    if not build_dir.exists():
        print(f"Warning: Build directory not found: {build_dir}", file=sys.stderr)
        return builds
    
    for entry in build_dir.iterdir():
        if not entry.is_dir():
            continue
        
        if entry.name.startswith("."):
            continue
        
        build_data = read_pulse_meta(entry, agents)
        if build_data:
            builds.append(build_data)
            continue
        
        build_data = read_legacy_build(entry)
        if build_data:
            builds.append(build_data)
    
    return builds


def sort_builds(builds: list[dict]) -> list[dict]:
    """Sort builds: active first, then by last_activity descending."""
    def sort_key(build: dict) -> tuple:
        is_active = build["status"] == "active"
        has_dead = len(build.get("dead_drops", [])) > 0
        
        last_activity = build.get("last_activity")
        if last_activity:
            try:
                activity_ts = datetime.fromisoformat(last_activity).timestamp()
            except ValueError:
                activity_ts = 0
        else:
            activity_ts = 0
        
        return (0 if is_active else 1, 0 if has_dead else 1, -activity_ts)
    
    return sorted(builds, key=sort_key)


def generate_summary(builds: list[dict]) -> dict:
    """Generate summary statistics."""
    summary = {
        "total": len(builds),
        "active": 0,
        "complete": 0,
        "pending": 0,
        "failed": 0,
        "with_sentinel": 0,
        "with_dead_drops": 0,
        "pulse_format": 0,
        "legacy_format": 0,
        "total_drops_running": 0,
        "total_drops_complete": 0,
        "total_drops": 0,
    }
    
    for build in builds:
        status = build.get("status", "pending")
        if status == "active":
            summary["active"] += 1
        elif status == "complete":
            summary["complete"] += 1
        elif status == "failed":
            summary["failed"] += 1
        else:
            summary["pending"] += 1
        
        if build.get("sentinel"):
            summary["with_sentinel"] += 1
        
        if len(build.get("dead_drops", [])) > 0:
            summary["with_dead_drops"] += 1
        
        if build.get("format") == "pulse":
            summary["pulse_format"] += 1
            drops = build.get("drops", {})
            summary["total_drops_running"] += drops.get("running", 0)
            summary["total_drops_complete"] += drops.get("complete", 0)
            summary["total_drops"] += drops.get("total", 0)
        else:
            summary["legacy_format"] += 1
    
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Sync Pulse builds to Build Tracker dashboard JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Output to default location
  %(prog)s --output /tmp/builds.json    # Custom output path
  %(prog)s --dry-run                    # Print JSON to stdout
  %(prog)s --agents-json /path/to.json  # Use cached agents list
        """,
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON to stdout instead of writing to file",
    )
    parser.add_argument(
        "--agents-json",
        type=Path,
        help="Path to agents list JSON (for Sentinel tracking)",
    )
    
    args = parser.parse_args()
    
    agents = []
    if args.agents_json and args.agents_json.exists():
        try:
            with open(args.agents_json) as f:
                agents = json.load(f)
        except:
            pass
    else:
        agents = get_agents_from_api()
    
    builds = scan_builds(BUILD_DIR, agents)
    
    builds = sort_builds(builds)
    
    summary = generate_summary(builds)
    
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "builds": builds,
    }
    
    if args.dry_run:
        print(json.dumps(output, indent=2))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        
        print(f"✓ Synced {len(builds)} builds to {args.output}")
        if builds:
            print(f"  Active: {summary['active']}, Complete: {summary['complete']}, Pending: {summary['pending']}")
            print(f"  Pulse: {summary['pulse_format']}, Legacy: {summary['legacy_format']}")
            if summary['with_sentinel'] > 0:
                print(f"  With Sentinel: {summary['with_sentinel']}")
            if summary['with_dead_drops'] > 0:
                print(f"  ⚠️  With dead drops: {summary['with_dead_drops']}")


if __name__ == "__main__":
    main()
