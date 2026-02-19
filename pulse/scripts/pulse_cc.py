#!/usr/bin/env python3
"""
pulse_cc.py — Pulse discipline adapter for Claude Code.

Brings Pulse's planning structure, quality gates, and deposit tracking
into Claude Code sessions, without requiring /zo/ask or Sentinel agents.

Claude Code executes Drops directly (via Task subagents or sequentially),
but the build folder structure, briefs, deposits, and learnings are identical
to full Pulse — so builds can be reviewed, audited, and even migrated to
full Pulse orchestration later.

Usage:
    python3 Skills/pulse/scripts/pulse_cc.py init <slug> --title "Title" [--type code_build]
    python3 Skills/pulse/scripts/pulse_cc.py plan <slug>
    python3 Skills/pulse/scripts/pulse_cc.py brief <slug> <drop_id> --name "Task name" [--wave W1] [--stream 1] [--depends D1.1]
    python3 Skills/pulse/scripts/pulse_cc.py deposit <slug> <drop_id> --status complete --summary "What was done"
    python3 Skills/pulse/scripts/pulse_cc.py status <slug>
    python3 Skills/pulse/scripts/pulse_cc.py lesson <slug> "Lesson text" [--source D1.1]
    python3 Skills/pulse/scripts/pulse_cc.py finalize <slug>
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Reuse Pulse common paths
sys.path.insert(0, str(Path(__file__).parent))
from pulse_common import PATHS, load_meta, save_meta, parse_drop_id


# ============================================================================
# INIT — Create build folder with CC-aware meta.json
# ============================================================================

def cmd_init(args):
    """Initialize a build workspace for Claude Code execution."""
    slug = args.slug
    title = args.title or slug.replace("-", " ").title()
    build_type = args.type or "code_build"
    build_dir = PATHS.build(slug)

    if build_dir.exists() and not args.force:
        print(f"✗ Build already exists: {build_dir}")
        print("  Use --force to overwrite.")
        return 1

    if build_dir.exists() and args.force:
        import shutil
        shutil.rmtree(build_dir)

    # Create structure
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "drops").mkdir()
    (build_dir / "deposits").mkdir()
    (build_dir / "artifacts").mkdir()

    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now().strftime("%Y-%m-%d")

    # meta.json — v3 schema, CC execution mode
    meta = {
        "schema_version": 3,
        "slug": slug,
        "title": title,
        "build_type": build_type,
        "status": "planning",
        "execution_mode": "claude_code",
        "created": now,
        "model": "claude-opus-4-6",
        "waves": {},
        "drops": {},
        "lineage": {
            "parent_type": "conversation",
            "parent_ref": None,
            "moment": f"Initialized from Claude Code session"
        }
    }
    save_meta(slug, meta)

    # PLAN.md stub
    plan_content = f"""---
created: {today}
last_edited: {today}
version: 1.0
build_slug: {slug}
---

# Plan: {title}

## Objective

[FILL: What is this build accomplishing?]

## Open Questions

- [ ] [Any unresolved questions that affect the plan?]

## Success Criteria

- [ ] [What must be true for this build to be complete?]

## Phases

### Phase 1: [NAME]

**Drops:**
- D1.1: [Task description]
- D1.2: [Task description]

**Gate:** [What must be verified before Phase 2?]

### Phase 2: [NAME]

**Drops:**
- D2.1: [Task description]

## Affected Files

- [List key files this build will create/modify]

## Risks

- [What could go wrong?]
"""
    (build_dir / "PLAN.md").write_text(plan_content)

    # STATUS.md
    status_content = f"""# Build Status: {title}

**Slug:** `{slug}`
**Mode:** Claude Code
**Created:** {today}

## Progress: 0/0 Drops (0%)

| Drop | Name | Wave | Status | Deposit |
|------|------|------|--------|---------|
| — | Planning | — | active | — |

## Learnings

_None yet._
"""
    (build_dir / "STATUS.md").write_text(status_content)

    # BUILD_LESSONS.json
    (build_dir / "BUILD_LESSONS.json").write_text("[]")

    # .n5protected
    (build_dir / ".n5protected").write_text(f"Build workspace: {slug}\nCreated: {today}\n")

    print(f"✓ Build initialized: {build_dir}/")
    print(f"  ├── PLAN.md       (fill this first)")
    print(f"  ├── STATUS.md     (auto-updated)")
    print(f"  ├── meta.json     (build state)")
    print(f"  ├── drops/        (briefs go here)")
    print(f"  ├── deposits/     (completion reports)")
    print(f"  ├── artifacts/    (build outputs)")
    print(f"  └── BUILD_LESSONS.json")
    print()
    print(f"Next: Fill PLAN.md, then run `pulse_cc.py brief` for each Drop.")
    return 0


# ============================================================================
# BRIEF — Create a Drop brief
# ============================================================================

def cmd_brief(args):
    """Create a Drop brief file and register it in meta.json."""
    slug = args.slug
    drop_id = args.drop_id
    meta = load_meta(slug)
    if not meta:
        print(f"✗ Build not found: {slug}")
        return 1

    name = args.name or f"Drop {drop_id}"
    wave = args.wave or "W1"
    stream, order = parse_drop_id(drop_id)
    depends = args.depends or []

    # Register in meta.json
    if "drops" not in meta:
        meta["drops"] = {}
    meta["drops"][drop_id] = {
        "name": name,
        "stream": stream,
        "order": order,
        "wave": wave,
        "depends_on": depends,
        "spawn_mode": "claude_code",
        "blocking": True,
        "status": "pending"
    }

    # Ensure wave exists
    if "waves" not in meta:
        meta["waves"] = {}
    if wave not in meta["waves"]:
        meta["waves"][wave] = []
    if drop_id not in meta["waves"][wave]:
        meta["waves"][wave].append(drop_id)

    save_meta(slug, meta)

    # Create brief file
    today = datetime.now().strftime("%Y-%m-%d")
    brief_filename = f"{drop_id}-{name.lower().replace(' ', '-')[:40]}.md"
    brief_path = PATHS.build_drops(slug) / brief_filename

    # Collect broadcasts from completed drops
    broadcasts = _collect_broadcasts(slug, meta)
    broadcast_section = ""
    if broadcasts:
        broadcast_section = "\n## Broadcasts from Prior Drops\n\n"
        for bid, msg in broadcasts:
            broadcast_section += f"- **{bid}:** {msg}\n"
        broadcast_section += "\n"

    # Collect learnings
    lessons = _load_lessons(slug)
    lessons_section = ""
    if lessons:
        lessons_section = "\n## Build Learnings (apply these)\n\n"
        for l in lessons[-5:]:  # Last 5 lessons
            lessons_section += f"- {l.get('lesson', '')}\n"
        lessons_section += "\n"

    brief_content = f"""---
drop_id: {drop_id}
build_slug: {slug}
wave: {wave}
depends_on: {json.dumps(depends)}
created: {today}
---

# {drop_id}: {name}

## Mission

[FILL: What exactly should this Drop accomplish?]

## Context

[FILL: What does the Drop need to know? File paths, prior decisions, constraints.]
{broadcast_section}{lessons_section}
## Affected Files

- [List files this Drop will create/modify]

## Success Criteria

- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] [Criterion 3]

## Deposit Instructions

When complete, write deposit:
```
python3 Skills/pulse/scripts/pulse_cc.py deposit {slug} {drop_id} --status complete --summary "What was done"
```
"""
    brief_path.write_text(brief_content)

    print(f"✓ Brief created: {brief_path}")
    print(f"  Drop {drop_id} registered in {wave}")
    if depends:
        print(f"  Depends on: {', '.join(depends)}")
    return 0


# ============================================================================
# DEPOSIT — Record Drop completion
# ============================================================================

def cmd_deposit(args):
    """Record a Drop's completion deposit."""
    slug = args.slug
    drop_id = args.drop_id
    meta = load_meta(slug)
    if not meta:
        print(f"✗ Build not found: {slug}")
        return 1

    if drop_id not in meta.get("drops", {}):
        print(f"✗ Drop {drop_id} not registered in {slug}")
        return 1

    now = datetime.now(timezone.utc).isoformat()
    deposit = {
        "drop_id": drop_id,
        "build_slug": slug,
        "status": args.status,
        "summary": args.summary or "",
        "broadcast": args.broadcast or "",
        "artifacts": args.artifacts.split(",") if args.artifacts else [],
        "timestamp": now,
        "execution_mode": "claude_code"
    }

    # Write deposit file
    deposit_path = PATHS.build_deposits(slug) / f"{drop_id}.json"
    with open(deposit_path, "w") as f:
        json.dump(deposit, f, indent=2)

    # Update meta.json
    meta["drops"][drop_id]["status"] = args.status
    meta["drops"][drop_id]["completed_at"] = now
    save_meta(slug, meta)

    # Update STATUS.md
    _refresh_status(slug, meta)

    status_icon = "✓" if args.status == "complete" else "✗" if args.status == "failed" else "?"
    print(f"{status_icon} Deposit written: {deposit_path}")
    print(f"  Drop {drop_id}: {args.status}")
    if args.broadcast:
        print(f"  Broadcast: {args.broadcast}")

    # Check if wave/build is complete
    _check_completion(slug, meta)
    return 0


# ============================================================================
# STATUS — Show build progress
# ============================================================================

def cmd_status(args):
    """Show build status."""
    slug = args.slug
    meta = load_meta(slug)
    if not meta:
        print(f"✗ Build not found: {slug}")
        return 1

    drops = meta.get("drops", {})
    waves = meta.get("waves", {})
    total = len(drops)
    complete = sum(1 for d in drops.values() if d.get("status") == "complete")
    failed = sum(1 for d in drops.values() if d.get("status") == "failed")
    in_progress = sum(1 for d in drops.values() if d.get("status") == "in_progress")
    pending = sum(1 for d in drops.values() if d.get("status") == "pending")

    pct = int((complete / total) * 100) if total > 0 else 0

    print(f"Build: {meta.get('title', slug)} [{meta.get('status', '?')}]")
    print(f"Mode:  Claude Code")
    print(f"Progress: {complete}/{total} ({pct}%)")
    if failed:
        print(f"Failed: {failed}")
    print()

    for wave_key in sorted(waves.keys()):
        drop_ids = waves[wave_key]
        wave_drops = {did: drops.get(did, {}) for did in drop_ids}
        wave_complete = all(d.get("status") == "complete" for d in wave_drops.values())
        wave_icon = "✓" if wave_complete else "▸"
        print(f"  {wave_icon} {wave_key}:")
        for did in drop_ids:
            d = drops.get(did, {})
            st = d.get("status", "?")
            icon = {"complete": "✓", "failed": "✗", "in_progress": "▸", "pending": "○"}.get(st, "?")
            name = d.get("name", did)
            deps = d.get("depends_on", [])
            dep_str = f" (depends: {', '.join(deps)})" if deps else ""
            print(f"    {icon} {did}: {name} [{st}]{dep_str}")
    print()

    # Show learnings count
    lessons = _load_lessons(slug)
    if lessons:
        print(f"Learnings: {len(lessons)} recorded")

    if args.json:
        print(json.dumps(meta, indent=2))

    return 0


# ============================================================================
# LESSON — Record a build learning
# ============================================================================

def cmd_lesson(args):
    """Record a build learning."""
    slug = args.slug
    lessons = _load_lessons(slug)

    now = datetime.now(timezone.utc).isoformat()
    lesson = {
        "lesson": args.text,
        "source": args.source or "orchestrator",
        "timestamp": now
    }
    lessons.append(lesson)
    _save_lessons(slug, lessons)

    print(f"✓ Lesson #{len(lessons)} recorded for {slug}")
    print(f"  \"{args.text}\"")
    return 0


# ============================================================================
# PLAN — Show/validate plan readiness
# ============================================================================

def cmd_plan(args):
    """Validate plan readiness."""
    slug = args.slug
    build_dir = PATHS.build(slug)
    plan_path = build_dir / "PLAN.md"

    if not plan_path.exists():
        print(f"✗ No PLAN.md found for {slug}")
        return 1

    content = plan_path.read_text()
    issues = []

    # Check for unfilled placeholders
    placeholders = ["[FILL:", "[TO BE FILLED", "[NAME]", "TODO:"]
    for p in placeholders:
        if p in content:
            issues.append(f"Unfilled placeholder: {p}")

    # Check for required sections
    required = ["Objective", "Success Criteria"]
    for section in required:
        if f"## {section}" not in content and f"# {section}" not in content:
            issues.append(f"Missing section: {section}")

    # Check for drops registered
    meta = load_meta(slug)
    drop_count = len(meta.get("drops", {})) if meta else 0

    if issues:
        print(f"⚠ Plan for {slug} has {len(issues)} issue(s):")
        for issue in issues:
            print(f"  - {issue}")
        print()
    else:
        print(f"✓ Plan for {slug} looks ready")

    print(f"  Drops registered: {drop_count}")
    if drop_count == 0:
        print(f"  → Run `pulse_cc.py brief {slug} D1.1 --name 'Task'` to add Drops")
    return 1 if issues else 0


# ============================================================================
# EXECUTE — Identify ready Drops for parallel dispatch
# ============================================================================

def cmd_execute(args):
    """Identify ready Drops and output briefs for Claude Code Task dispatch.

    Reads meta.json, finds Drops whose dependencies are satisfied,
    and outputs brief content for each ready Drop. Independent Drops
    are flagged for parallel execution via Claude Code's Task subagents.
    """
    slug = args.slug
    meta = load_meta(slug)
    if not meta:
        print(f"✗ Build not found: {slug}")
        return 1

    drops = meta.get("drops", {})
    waves = meta.get("waves", {})

    if not drops:
        print(f"✗ No drops registered for {slug}")
        return 1

    # Update status to active if still planning
    if meta.get("status") == "planning":
        meta["status"] = "active"
        save_meta(slug, meta)

    # Find current wave (first with pending/in_progress blocking drops)
    current_wave = None
    for wave_key in sorted(waves.keys()):
        wave_drop_ids = waves[wave_key]
        blocking_statuses = [
            drops.get(did, {}).get("status", "pending")
            for did in wave_drop_ids
            if drops.get(did, {}).get("blocking", True)
        ]
        if any(s in ("pending", "in_progress") for s in blocking_statuses):
            current_wave = wave_key
            break

    if current_wave is None:
        if all(d.get("status") == "complete" for d in drops.values()):
            print(f"🏁 All drops complete. Run: pulse_cc.py finalize {slug}")
        else:
            print(f"✗ No actionable wave. Run: pulse_cc.py status {slug}")
        return 0

    # Find ready drops (pending + deps satisfied)
    ready_drops = []
    wave_drop_ids = waves[current_wave]
    for did in wave_drop_ids:
        info = drops.get(did, {})
        if info.get("status") != "pending":
            continue
        deps = info.get("depends_on", [])
        if all(drops.get(d, {}).get("status") == "complete" for d in deps):
            ready_drops.append(did)

    if not ready_drops:
        print(f"⏳ {current_wave}: Waiting on dependencies")
        for did in wave_drop_ids:
            info = drops.get(did, {})
            if info.get("status") == "pending":
                unmet = [d for d in info.get("depends_on", []) if drops.get(d, {}).get("status") != "complete"]
                if unmet:
                    print(f"  {did}: waiting on {', '.join(unmet)}")
        return 0

    # Classify: independent (parallel) vs sequential
    independent = []
    sequential = []
    for did in ready_drops:
        deps = set(drops.get(did, {}).get("depends_on", []))
        if deps & set(ready_drops):
            sequential.append(did)
        else:
            independent.append(did)

    # Mark as in_progress
    for did in ready_drops:
        meta["drops"][did]["status"] = "in_progress"
    save_meta(slug, meta)
    _refresh_status(slug, meta)

    # Output execution plan
    drops_dir = PATHS.build_drops(slug)
    print(f"═══ {current_wave} — {len(ready_drops)} Drop(s) Ready ═══")
    print()

    if len(independent) > 1:
        print(f"⚡ PARALLEL: {len(independent)} independent drops — launch as simultaneous Task subagents")
        print()

    for did in ready_drops:
        info = drops.get(did, {})
        is_parallel = did in independent and len(independent) > 1
        tag = "⚡" if is_parallel else "→"

        # Find brief file
        brief_file = None
        for f in drops_dir.iterdir():
            if f.name.startswith(did):
                brief_file = f
                break

        print(f"{tag} {did}: {info.get('name', did)}")
        print(f"  Brief: {brief_file or 'NOT FOUND'}")
        deps_str = ', '.join(info.get('depends_on', [])) or 'none'
        print(f"  Depends: {deps_str}")

        if args.show_briefs and brief_file and brief_file.exists():
            print()
            print(brief_file.read_text())

        print()

    # Actionable summary
    print(f"═══ Execution Plan ═══")
    if len(independent) > 1:
        print(f"PARALLEL — launch {len(independent)} Task subagents:")
        for did in independent:
            brief_file = next((f for f in drops_dir.iterdir() if f.name.startswith(did)), None)
            print(f"  Task({did}): {brief_file}")
    elif len(ready_drops) == 1:
        print(f"SINGLE — execute {ready_drops[0]} directly")
    if sequential:
        print(f"THEN SEQUENTIAL: {' → '.join(sequential)}")

    print()
    print(f"After deposits, run again: pulse_cc.py execute {slug}")
    return 0


# ============================================================================
# FINALIZE — Post-build summary
# ============================================================================

def cmd_finalize(args):
    """Finalize a completed build."""
    slug = args.slug
    meta = load_meta(slug)
    if not meta:
        print(f"✗ Build not found: {slug}")
        return 1

    drops = meta.get("drops", {})
    total = len(drops)
    complete = sum(1 for d in drops.values() if d.get("status") == "complete")

    if complete < total and not args.force:
        print(f"✗ Build not complete: {complete}/{total} drops done")
        print("  Use --force to finalize anyway.")
        return 1

    now = datetime.now(timezone.utc).isoformat()
    meta["status"] = "complete"
    meta["completed_at"] = now
    save_meta(slug, meta)

    # Collect all deposits
    deposits_dir = PATHS.build_deposits(slug)
    all_deposits = []
    if deposits_dir.exists():
        for f in sorted(deposits_dir.glob("D*.json")):
            try:
                with open(f) as fh:
                    all_deposits.append(json.load(fh))
            except (json.JSONDecodeError, IOError):
                pass

    # Write finalization report
    report = {
        "slug": slug,
        "title": meta.get("title", slug),
        "status": "complete",
        "finalized_at": now,
        "execution_mode": "claude_code",
        "drops_total": total,
        "drops_complete": complete,
        "deposits": all_deposits,
        "learnings": _load_lessons(slug)
    }
    report_path = PATHS.build(slug) / "FINALIZATION.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    _refresh_status(slug, meta)

    print(f"✓ Build {slug} finalized")
    print(f"  {complete}/{total} drops complete")
    print(f"  Report: {report_path}")
    return 0


# ============================================================================
# HELPERS
# ============================================================================

def _collect_broadcasts(slug: str, meta: dict) -> list[tuple[str, str]]:
    """Collect broadcast messages from completed drops."""
    broadcasts = []
    deposits_dir = PATHS.build_deposits(slug)
    if not deposits_dir.exists():
        return broadcasts
    for did, info in meta.get("drops", {}).items():
        if info.get("status") == "complete":
            dep_file = deposits_dir / f"{did}.json"
            if dep_file.exists():
                try:
                    with open(dep_file) as f:
                        dep = json.load(f)
                    bc = dep.get("broadcast", "")
                    if bc:
                        broadcasts.append((did, bc))
                except (json.JSONDecodeError, IOError):
                    pass
    return broadcasts


def _load_lessons(slug: str) -> list:
    """Load build lessons."""
    path = PATHS.build_lessons(slug)
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _save_lessons(slug: str, lessons: list):
    """Save build lessons."""
    path = PATHS.build_lessons(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(lessons, f, indent=2)


def _refresh_status(slug: str, meta: dict):
    """Regenerate STATUS.md from meta.json."""
    drops = meta.get("drops", {})
    waves = meta.get("waves", {})
    total = len(drops)
    complete = sum(1 for d in drops.values() if d.get("status") == "complete")
    pct = int((complete / total) * 100) if total > 0 else 0

    lines = [
        f"# Build Status: {meta.get('title', slug)}",
        f"",
        f"**Slug:** `{slug}`",
        f"**Mode:** Claude Code",
        f"**Status:** {meta.get('status', 'unknown')}",
        f"",
        f"## Progress: {complete}/{total} Drops ({pct}%)",
        f"",
        f"| Drop | Name | Wave | Status | Depends |",
        f"|------|------|------|--------|---------|",
    ]

    for wave_key in sorted(waves.keys()):
        for did in waves[wave_key]:
            d = drops.get(did, {})
            name = d.get("name", did)
            st = d.get("status", "?")
            deps = ", ".join(d.get("depends_on", [])) or "—"
            icon = {"complete": "✓", "failed": "✗", "in_progress": "▸", "pending": "○"}.get(st, "?")
            lines.append(f"| {icon} {did} | {name} | {wave_key} | {st} | {deps} |")

    # Learnings section
    lessons = _load_lessons(slug)
    lines.append("")
    lines.append("## Learnings")
    lines.append("")
    if lessons:
        for l in lessons:
            src = l.get("source", "")
            lines.append(f"- [{src}] {l.get('lesson', '')}")
    else:
        lines.append("_None yet._")

    status_path = PATHS.build(slug) / "STATUS.md"
    status_path.write_text("\n".join(lines) + "\n")


def _check_completion(slug: str, meta: dict):
    """Check if all drops in current wave are done, or build is complete."""
    drops = meta.get("drops", {})
    waves = meta.get("waves", {})
    total = len(drops)
    complete = sum(1 for d in drops.values() if d.get("status") == "complete")

    if complete == total and total > 0:
        print(f"\n🏁 All {total} drops complete! Run: pulse_cc.py finalize {slug}")
        return

    # Check wave completion
    for wave_key in sorted(waves.keys()):
        wave_drops = waves[wave_key]
        wave_statuses = [drops.get(did, {}).get("status") for did in wave_drops]
        blocking_statuses = [
            drops.get(did, {}).get("status")
            for did in wave_drops
            if drops.get(did, {}).get("blocking", True)
        ]
        if all(s == "complete" for s in blocking_statuses) and blocking_statuses:
            # Find next wave
            all_waves = sorted(waves.keys())
            idx = all_waves.index(wave_key)
            if idx + 1 < len(all_waves):
                next_wave = all_waves[idx + 1]
                next_drops = waves[next_wave]
                pending_next = [did for did in next_drops if drops.get(did, {}).get("status") == "pending"]
                if pending_next:
                    print(f"\n→ {wave_key} complete. Ready for {next_wave}: {', '.join(pending_next)}")


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Pulse discipline for Claude Code sessions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  init      Create a new build workspace
  plan      Validate plan readiness
  brief     Create a Drop brief
  execute   Find ready Drops for parallel execution
  deposit   Record Drop completion
  status    Show build progress
  lesson    Record a build learning
  finalize  Close out a completed build

Examples:
  pulse_cc.py init my-feature --title "My Feature"
  pulse_cc.py brief my-feature D1.1 --name "Setup database"
  pulse_cc.py brief my-feature D1.2 --name "Build API" --depends D1.1
  pulse_cc.py execute my-feature                          # find ready drops
  pulse_cc.py execute my-feature --show-briefs            # include brief content
  pulse_cc.py deposit my-feature D1.1 --status complete --summary "DB schema created"
  pulse_cc.py status my-feature
  pulse_cc.py lesson my-feature "SQLite needs WAL mode for concurrent access"
  pulse_cc.py finalize my-feature
"""
    )
    subparsers = parser.add_subparsers(dest="command")

    # init
    p_init = subparsers.add_parser("init", help="Initialize build workspace")
    p_init.add_argument("slug")
    p_init.add_argument("--title", "-t")
    p_init.add_argument("--type", choices=["code_build", "content", "research", "general"])
    p_init.add_argument("--force", "-f", action="store_true")

    # plan
    p_plan = subparsers.add_parser("plan", help="Validate plan")
    p_plan.add_argument("slug")

    # brief
    p_brief = subparsers.add_parser("brief", help="Create Drop brief")
    p_brief.add_argument("slug")
    p_brief.add_argument("drop_id")
    p_brief.add_argument("--name", "-n")
    p_brief.add_argument("--wave", "-w", default="W1")
    p_brief.add_argument("--stream", "-s", type=int)
    p_brief.add_argument("--depends", "-d", nargs="*", default=[])

    # deposit
    p_deposit = subparsers.add_parser("deposit", help="Record Drop completion")
    p_deposit.add_argument("slug")
    p_deposit.add_argument("drop_id")
    p_deposit.add_argument("--status", required=True, choices=["complete", "failed", "blocked"])
    p_deposit.add_argument("--summary", "-s")
    p_deposit.add_argument("--broadcast", "-b", help="Message to propagate to later Drops")
    p_deposit.add_argument("--artifacts", "-a", help="Comma-separated list of artifact paths")

    # status
    p_status = subparsers.add_parser("status", help="Show build status")
    p_status.add_argument("slug")
    p_status.add_argument("--json", action="store_true")

    # lesson
    p_lesson = subparsers.add_parser("lesson", help="Record a learning")
    p_lesson.add_argument("slug")
    p_lesson.add_argument("text")
    p_lesson.add_argument("--source", help="Source drop or context")

    # execute
    p_execute = subparsers.add_parser("execute", help="Find ready Drops for parallel execution")
    p_execute.add_argument("slug")
    p_execute.add_argument("--show-briefs", action="store_true", help="Include full brief content in output")

    # finalize
    p_finalize = subparsers.add_parser("finalize", help="Finalize build")
    p_finalize.add_argument("slug")
    p_finalize.add_argument("--force", "-f", action="store_true")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "init": cmd_init,
        "plan": cmd_plan,
        "brief": cmd_brief,
        "execute": cmd_execute,
        "deposit": cmd_deposit,
        "status": cmd_status,
        "lesson": cmd_lesson,
        "finalize": cmd_finalize,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main() or 0)
