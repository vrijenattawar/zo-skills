#!/usr/bin/env python3
"""
Pulse: Automated Build Orchestration System

Commands:
  start <slug>     - Begin automated orchestration
  status <slug>    - Show current build status
  stop <slug>      - Gracefully stop orchestration
  resume <slug>    - Resume a stopped build
  tick <slug>      - Run single orchestration cycle (for scheduled tasks)
  finalize <slug>  - Run post-build finalization (safety, tests, learnings)
  rush <slug>      - Override learning mode to auto-spawn (per-Drop, per-Wave, or entire build)
"""

import argparse
import asyncio
import aiohttp
import json
import os
import sys
import sqlite3
import subprocess
import fcntl
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from pulse_common import (
    PATHS,
    WORKSPACE,
    parse_drop_id,
    sort_wave_keys,
    get_drop_stream_order,
    RECOVERY_DEFAULTS,
    load_config,
)

# Paths
# WORKSPACE = Path("/home/workspace")  # Now imported from pulse_common
BUILDS_DIR = PATHS.BUILDS
CONVERSATIONS_DB = PATHS.WORKSPACE / "N5" / "data" / "conversations.db"
SKILLS_DIR = PATHS.SCRIPTS

# Config
DEFAULT_POLL_INTERVAL = 180  # 3 minutes
DEFAULT_DEAD_THRESHOLD = 900  # 15 minutes
DEFAULT_SPAWN_TIMEOUT = 1200  # 20 minutes max for /zo/ask drop execution
DEFAULT_SPAWN_WORKER_TIMEOUT = 180  # pre-running handshake timeout for legacy spawning states
DEFAULT_TICK_LEASE_SECONDS = 180
DEFAULT_CIRCUIT_FAILURE_THRESHOLD = 3
DEFAULT_CIRCUIT_COOLDOWN_SECONDS = 300
ZO_API_URL = "https://api.zo.computer/zo/ask"


def get_build_mode(meta: dict) -> str:
    """Get build mode from meta.json, defaulting to 'standard' for backward compatibility.
    Builds created with learning-engaged init will have 'learning' set explicitly."""
    return meta.get("build_mode", "standard")


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


@contextmanager
def locked_meta(slug: str):
    """Lock meta.json for safe concurrent updates across tick/spawn workers."""
    meta_path = BUILDS_DIR / slug / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Build not found: {slug}")

    with open(meta_path, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            meta = json.load(f)
            yield meta
            f.seek(0)
            f.truncate()
            json.dump(meta, f, indent=2)
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _acquire_tick_lease(slug: str, lease_seconds: int = DEFAULT_TICK_LEASE_SECONDS) -> tuple[bool, str]:
    """Acquire a short lease so only one tick mutates a build at a time."""
    holder = f"{os.getpid()}:{int(datetime.now(timezone.utc).timestamp())}"
    now = datetime.now(timezone.utc)

    with locked_meta(slug) as meta:
        lease = meta.get("tick_lease", {})
        lease_holder = lease.get("holder")
        lease_expires = _parse_iso(lease.get("expires_at"))

        if lease_holder and lease_expires and lease_expires > now:
            return False, holder

        meta["tick_lease"] = {
            "holder": holder,
            "acquired_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=lease_seconds)).isoformat(),
        }
    return True, holder


def _heartbeat_tick_lease(slug: str, holder: str, lease_seconds: int = DEFAULT_TICK_LEASE_SECONDS) -> None:
    """Refresh lease TTL during longer tick operations."""
    now = datetime.now(timezone.utc)
    with locked_meta(slug) as meta:
        lease = meta.get("tick_lease", {})
        if lease.get("holder") != holder:
            return
        lease["expires_at"] = (now + timedelta(seconds=lease_seconds)).isoformat()
        lease["heartbeat_at"] = now.isoformat()
        meta["tick_lease"] = lease


def _release_tick_lease(slug: str, holder: str) -> None:
    with locked_meta(slug) as meta:
        lease = meta.get("tick_lease", {})
        if lease.get("holder") == holder:
            meta.pop("tick_lease", None)


def _spawn_circuit_open(meta: dict) -> bool:
    circuit = meta.get("spawn_circuit", {})
    if not circuit.get("open"):
        return False
    until = _parse_iso(circuit.get("open_until"))
    if not until:
        return False
    return until > datetime.now(timezone.utc)


def _set_spawn_circuit(meta: dict, reason: str) -> None:
    now = datetime.now(timezone.utc)
    meta["spawn_circuit"] = {
        "open": True,
        "open_reason": reason,
        "opened_at": now.isoformat(),
        "open_until": (now + timedelta(seconds=DEFAULT_CIRCUIT_COOLDOWN_SECONDS)).isoformat(),
    }


def _close_spawn_circuit(meta: dict) -> None:
    if "spawn_circuit" in meta:
        meta["spawn_circuit"] = {"open": False, "closed_at": datetime.now(timezone.utc).isoformat()}


def _increment_spawn_failures(meta: dict, now_iso: str) -> int:
    failures = int(meta.get("spawn_failures_consecutive", 0)) + 1
    meta["spawn_failures_consecutive"] = failures
    meta["last_spawn_failure_at"] = now_iso
    if failures >= DEFAULT_CIRCUIT_FAILURE_THRESHOLD:
        _set_spawn_circuit(meta, f"{failures} consecutive spawn failures")
    return failures


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def claim_task(slug: str, drop_id: str) -> dict | None:
    """Atomically claim a task from the pool."""
    meta_path = BUILDS_DIR / slug / "meta.json"
    
    if not meta_path.exists():
        return None
    
    with open(meta_path, "r+") as f:
        # Acquire exclusive lock
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            meta = json.load(f)
            pool = meta.get("task_pool", {})
            
            if not pool.get("enabled"):
                return None
            
            # Find first pending task
            for task in pool.get("tasks", []):
                if task["status"] == "pending":
                    task["status"] = "claimed"
                    task["claimed_by"] = drop_id
                    task["claimed_at"] = datetime.now(timezone.utc).isoformat()
                    
                    # Write back
                    f.seek(0)
                    f.truncate()
                    json.dump(meta, f, indent=2)
                    
                    return task
            
            return None  # Pool exhausted
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def update_task_status(slug: str, task_id: str, status: str, drop_id: str = None) -> bool:
    """Update a task's status in the pool."""
    meta_path = BUILDS_DIR / slug / "meta.json"
    
    if not meta_path.exists():
        return False
    
    with open(meta_path, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            meta = json.load(f)
            pool = meta.get("task_pool", {})
            
            if not pool.get("enabled"):
                return False
            
            # Find and update task
            for task in pool.get("tasks", []):
                if task["id"] == task_id:
                    old_status = task["status"]
                    task["status"] = status
                    if status in ("complete", "failed"):
                        task["completed_at"] = datetime.now(timezone.utc).isoformat()
                        if drop_id:
                            task["completed_by"] = drop_id
                    
                    # Write back
                    f.seek(0)
                    f.truncate()
                    json.dump(meta, f, indent=2)
                    
                    print(f"[TASK_POOL] Task {task_id}: {old_status} → {status}")
                    return True
            
            return False
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def get_pool_status(meta: dict) -> dict:
    """Get task pool status summary for STATUS.md."""
    pool = meta.get("task_pool", {})
    if not pool.get("enabled"):
        return None
    
    tasks = pool.get("tasks", [])
    status_counts = {
        "pending": 0,
        "claimed": 0,
        "complete": 0,
        "failed": 0
    }
    
    active_claims = []
    
    for task in tasks:
        status = task["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        
        if status == "claimed":
            claimed_at = task.get("claimed_at")
            claimed_by = task.get("claimed_by", "unknown")
            duration = ""
            if claimed_at:
                try:
                    claimed_time = datetime.fromisoformat(claimed_at.replace("Z", "+00:00"))
                    duration_min = int((datetime.now(timezone.utc) - claimed_time).total_seconds() / 60)
                    duration = f"({duration_min} min)"
                except:
                    pass
            
            active_claims.append(f"- {claimed_by} → {task['id']} {duration}")
    
    return {
        "counts": status_counts,
        "active_claims": active_claims,
        "total": len(tasks)
    }


def inject_pool_claim_instructions(brief_content: str, slug: str, drop_id: str = "UNKNOWN") -> str:
    """Inject task pool claiming instructions for pool workers."""
    pool_instructions = f"""

## Task Pool Worker Instructions

You are pool worker **{drop_id}**. Your execution pattern:

1. **Claim a task** by running:
```bash
python3 -c "
import sys; sys.path.insert(0, './Skills/pulse/scripts')
from pulse import claim_task
task = claim_task('{slug}', '{drop_id}')
if task:
    print(f'CLAIMED: {{task[\"id\"]}}')
    print(f'TYPE: {{task.get(\"type\", \"unknown\")}}')
    print(f'TARGET: {{task.get(\"target\", \"unknown\")}}')
else:
    print('POOL_EXHAUSTED')
"
```

2. **Execute the claimed task** according to its type and target
3. **Mark complete** when done by running:
```bash
python3 -c "
import sys; sys.path.insert(0, './Skills/pulse/scripts')
from pulse import update_task_status
update_task_status('{slug}', 'TASK_ID_HERE', 'complete', '{drop_id}')
"
```
4. **Repeat**: Claim another task until pool is exhausted (POOL_EXHAUSTED)
5. **Deposit summary**: Write deposit with summary of ALL completed tasks

## On Pool Exhaustion

When claiming returns POOL_EXHAUSTED, write your final deposit summarizing all work completed.

"""
    
    # Insert after brief frontmatter or at beginning of content
    lines = brief_content.split('\n')
    insert_idx = 0
    
    # Skip frontmatter if present
    if lines[0].strip() == '---':
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                insert_idx = i + 1
                break
    
    lines.insert(insert_idx, pool_instructions)
    return '\n'.join(lines)


def load_meta(slug: str) -> dict:
    """Load build meta.json"""
    meta_path = BUILDS_DIR / slug / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Build not found: {slug}")
    with open(meta_path) as f:
        return json.load(f)


def save_meta(slug: str, meta: dict):
    """Save build meta.json"""
    meta_path = BUILDS_DIR / slug / "meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)


def find_drop_brief_path(slug: str, drop_id: str) -> Path:
    """Find the file path for a Drop brief in the build's drops/ folder."""
    drops_dir = BUILDS_DIR / slug / "drops"

    # Try both D and C prefixes
    for pattern in [f"{drop_id}-*.md", f"C*.md"]:
        for f in drops_dir.glob(pattern):
            if f.stem.startswith(drop_id):
                return f

    # Fallback: exact match
    for f in drops_dir.glob("*.md"):
        if f.stem.split("-")[0] == drop_id:
            return f

    raise FileNotFoundError(f"Brief not found for {drop_id}")


def ensure_launcher(slug: str, drop_id: str) -> Path:
    """Create/update a manual-launcher markdown file for a Drop and return its path."""
    brief_path = find_drop_brief_path(slug, drop_id)
    launchers_dir = BUILDS_DIR / slug / "launchers"
    launchers_dir.mkdir(parents=True, exist_ok=True)

    launcher_path = launchers_dir / f"{drop_id}.md"

    today = datetime.now(timezone.utc).date().isoformat()
    content = f"""---
created: {today}
last_edited: {today}
version: 1.0
provenance: pulse:{slug}
---

# Launcher: {slug} / {drop_id}

## Paste into a new thread

```text
Load and execute: file 'N5/builds/{slug}/drops/{brief_path.name}'

When complete, write deposit to:
file 'N5/builds/{slug}/deposits/{drop_id}.json'
```

## After you finish

- Confirm the deposit exists at the path above.
- Then run:
  - `python3 Skills/pulse/scripts/pulse.py tick {slug}`
  - (or wait for the Sentinel to tick)
"""

    launcher_path.write_text(content)
    return launcher_path


def load_drop_brief(slug: str, drop_id: str) -> str:
    """Load a Drop brief from drops/ folder"""
    return find_drop_brief_path(slug, drop_id).read_text()


def get_deposit(slug: str, drop_id: str) -> Optional[dict]:
    """Get a Drop's deposit if it exists"""
    deposit_path = BUILDS_DIR / slug / "deposits" / f"{drop_id}.json"
    if deposit_path.exists():
        with open(deposit_path) as f:
            return json.load(f)
    return None


def get_filter_result(slug: str, drop_id: str) -> Optional[dict]:
    """Get Filter judgment for a Drop if it exists"""
    filter_path = BUILDS_DIR / slug / "deposits" / f"{drop_id}_filter.json"
    if filter_path.exists():
        with open(filter_path) as f:
            return json.load(f)
    return None


def _extract_json_from_text(text: str) -> Optional[dict]:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            return None
    return None


def _save_validation_result(slug: str, drop_id: str, result: dict) -> None:
    path = BUILDS_DIR / slug / "deposits" / f"{drop_id}_validation.json"
    path.write_text(json.dumps(result, indent=2))


async def run_validators(slug: str, drop_id: str) -> tuple[bool, dict]:
    """Run deposit validators. Mechanical is mandatory; LLM stage is optional by config."""
    config = load_config()
    validation = config.get("validation", {})
    enabled = validation.get("enabled", True)
    if not enabled:
        return True, {
            "drop_id": drop_id,
            "build_slug": slug,
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "PASS",
            "reason": "Validation disabled",
            "mechanical": None,
            "llm": None,
        }

    result = {
        "drop_id": drop_id,
        "build_slug": slug,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "reason": "Passed validators",
        "mechanical": None,
        "llm": None,
    }

    if validation.get("code_validator_enabled", True):
        from pulse_code_validator import check_drop_artifacts

        mech_passed, mech_report = check_drop_artifacts(slug, drop_id)
        result["mechanical"] = mech_report
        if not mech_passed:
            result["verdict"] = "FAIL"
            result["reason"] = f"Code validation: {mech_report.get('critical_count', 0)} critical issues"
            return False, result

    if validation.get("llm_filter_enabled", True) and validation.get("llm_filter_in_tick", False):
        llm_timeout = int(validation.get("llm_filter_timeout_seconds", 120))
        auto_pass = bool(validation.get("auto_pass_on_validator_error", True))
        llm_script = SKILLS_DIR / "pulse_llm_filter.py"
        try:
            llm_proc = subprocess.run(
                ["python3", str(llm_script), "validate", slug, drop_id],
                capture_output=True,
                text=True,
                timeout=llm_timeout,
                cwd=str(WORKSPACE),
            )
        except subprocess.TimeoutExpired:
            if auto_pass:
                result["llm"] = {"error": "timeout", "auto_pass": True}
                result["reason"] = "LLM validator timeout (auto-pass)"
                return True, result
            result["verdict"] = "FAIL"
            result["reason"] = "LLM validator timeout"
            result["llm"] = {"error": "timeout"}
            return False, result

        llm_data = _extract_json_from_text(llm_proc.stdout or "") or _extract_json_from_text(llm_proc.stderr or "")
        if not llm_data:
            if auto_pass:
                result["llm"] = {"error": "parse_error", "auto_pass": True}
                result["reason"] = "LLM validator parse error (auto-pass)"
                return True, result
            result["verdict"] = "FAIL"
            result["reason"] = "LLM validator parse error"
            result["llm"] = {"error": "parse_error"}
            return False, result

        result["llm"] = llm_data
        llm_pass = bool(llm_data.get("pass", False))
        if not llm_pass:
            result["verdict"] = "FAIL"
            result["reason"] = f"LLM validation: {llm_data.get('summary', 'failed')}"
            return False, result

    return True, result


def register_drop_conversation(drop_id: str, slug: str, convo_id: str):
    """Register a Drop's conversation in conversations.db"""
    conn = sqlite3.connect(CONVERSATIONS_DB)
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    # Check if conversations table has the columns we need
    cursor.execute("PRAGMA table_info(conversations)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "build_slug" not in columns:
        cursor.execute("ALTER TABLE conversations ADD COLUMN build_slug TEXT")
    if "drop_id" not in columns:
        cursor.execute("ALTER TABLE conversations ADD COLUMN drop_id TEXT")
    
    # Insert or update
    cursor.execute("""
        INSERT INTO conversations (id, type, status, created_at, updated_at, build_slug, drop_id)
        VALUES (?, 'headless_worker', 'running', ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET build_slug=?, drop_id=?, updated_at=?
    """, (convo_id, now, now, slug, drop_id, slug, drop_id, now))
    
    conn.commit()
    conn.close()


def update_drop_conversation_status(convo_id: str, status: str):
    """Update a Drop conversation's status in conversations.db"""
    if not convo_id or convo_id.startswith("unknown_"):
        return
    conn = sqlite3.connect(CONVERSATIONS_DB)
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
        UPDATE conversations 
        SET status = ?, updated_at = ?, completed_at = ?
        WHERE id = ?
    """, (status, now, now if status == "complete" else None, convo_id))
    conn.commit()
    conn.close()


def update_status_md(slug: str, meta: dict):
    """Update STATUS.md with current progress"""
    status_path = BUILDS_DIR / slug / "STATUS.md"

    drops = meta.get("drops", {})
    complete = [d for d, info in drops.items() if info.get("status") == "complete"]
    running = [d for d, info in drops.items() if info.get("status") == "running"]
    awaiting_manual = [d for d, info in drops.items() if info.get("status") == "awaiting_manual"]
    ready = [d for d, info in drops.items() if info.get("status") == "ready"]
    pending = [d for d, info in drops.items() if info.get("status") == "pending"]
    superseded = [d for d, info in drops.items() if info.get("status") == "superseded"]
    dead = [d for d, info in drops.items() if info.get("status") == "dead"]
    failed = [d for d, info in drops.items() if info.get("status") == "failed"]

    total = len(drops)
    pct = int(len(complete) / total * 100) if total > 0 else 0

    if meta.get("waves"):
        gate_line = f"**Wave:** {meta.get('active_wave', '?')}"
    else:
        gate_line = f"**Legacy Stream Gate:** {meta.get('current_stream', '?')}/{meta.get('total_streams', '?')}"

    gate = meta.get("gate")
    gate_text = ""
    if isinstance(gate, dict) and gate.get("reason"):
        gate_text = f"\n**Gate:** {gate.get('type', 'gate')} — {gate.get('reason')}"

    ready_lines = "\n".join(
        f"- [ ] {d} → run: `python3 Skills/pulse/scripts/pulse.py launch {slug} {d}`"
        for d in sorted(ready)
    )

    awaiting_lines = "\n".join(
        f"- [ ] {d} → run: `python3 Skills/pulse/scripts/pulse.py launch {slug} {d}`"
        for d in sorted(awaiting_manual)
    )

    # Build superseded lines with superseded_by info
    superseded_lines = "\n".join(
        f"- [~] {d} (superseded by {drops[d].get('superseded_by', '?')})"
        for d in sorted(superseded)
    )

    # Add task pool status if enabled
    pool_status = get_pool_status(meta)
    pool_section = ""
    if pool_status:
        counts = pool_status["counts"]
        active_claims = pool_status["active_claims"]
        
        pool_section = f"""
## Task Pool
| Status | Count |
|--------|-------|
| Pending | {counts['pending']} |
| Claimed | {counts['claimed']} |
| Complete | {counts['complete']} |
| Failed | {counts['failed']} |

Active claims:
{chr(10).join(active_claims) if active_claims else '(none)'}

"""

    content = f"""# Build Status: {slug}

**Updated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
**Status:** {meta.get('status', 'unknown')}
{gate_line}{gate_text}
**Progress:** {len(complete)}/{total} Drops ({pct}%)
{pool_section}"""

    recovery_section = ""
    recovery_log_path = BUILDS_DIR / slug / "RECOVERY_LOG.jsonl"
    if recovery_log_path.exists():
        try:
            recent_actions = []
            with open(recovery_log_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        recent_actions.append(json.loads(line))
            last_5 = recent_actions[-5:] if len(recent_actions) > 5 else recent_actions
            if last_5:
                action_lines = []
                for a in last_5:
                    icon = "🔄" if a.get("action") == "auto_retry" else "⚠️" if a.get("action") == "escalate" else "🔍"
                    ts = a.get("timestamp", "")[:16]
                    action_lines.append(f"- {icon} {a.get('drop_id', '?')}: {a.get('reason', '?')} ({ts})")
                recovery_section = f"""
## 🔄 Recovery Actions ({len(recent_actions)} total)
{chr(10).join(action_lines)}
"""
        except Exception:
            pass

    if meta.get("status") == "blocked":
        blocked_reason = meta.get("blocked_reason", "Unknown")
        content += f"""
## 🚫 BUILD BLOCKED
**Reason:** {blocked_reason}
**Action required:** Manual intervention needed.
"""

    content += f"""{recovery_section}
## Awaiting Manual ({len(awaiting_manual)})
{awaiting_lines or '(none)'}

## Ready for Manual Launch ({len(ready)})
{ready_lines or '(none)'}

## Running ({len(running)})
{chr(10).join(f'- [ ] {d} (since {drops[d].get("started_at", "?")[:16]})' for d in sorted(running)) or '(none)'}

## Pending ({len(pending)})
{chr(10).join(f'- [ ] {d}' for d in sorted(pending)) or '(none)'}

## Superseded ({len(superseded)})
{superseded_lines or '(none)'}

## Complete ({len(complete)})
{chr(10).join(f'- [x] {d}' for d in sorted(complete)) or '(none)'}

## Dead ({len(dead)})
{chr(10).join(f'- [!] {d} (retry:{drops[d].get("retry_count", 0)}/{_get_recovery_config(meta).get("max_auto_retries", 2)})' for d in sorted(dead)) or '(none)'}

## Failed ({len(failed)})
{chr(10).join(f'- [!] {d} (retry:{drops[d].get("retry_count", 0)}/{_get_recovery_config(meta).get("max_auto_retries", 2)})' for d in sorted(failed)) or '(none)'}
"""

    status_path.write_text(content)


async def send_sms(message: str):
    """Send SMS via Zo's send_sms_to_user (calls back to Zo)"""
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        print(f"[SMS SKIPPED - no token] {message}")
        return
    
    prompt = f"Send this SMS to V immediately, no commentary: {message}"

    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                ZO_API_URL,
                headers={
                    "authorization": token,
                    "content-type": "application/json"
                },
                json={"input": prompt}
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    print(f"[SMS ERROR] HTTP {resp.status}: {body[:200]}")
                    return None
                result = await resp.json()
                print(f"[SMS SENT] {message}")
                return result
    except Exception as e:
        print(f"[SMS ERROR] {e}")
        return None


def collect_broadcasts(slug: str) -> list[dict]:
    """Collect all broadcasts from completed deposits."""
    broadcasts = []
    deposits_dir = BUILDS_DIR / slug / "deposits"
    
    if not deposits_dir.exists():
        return broadcasts
    
    for deposit_path in deposits_dir.glob("*.json"):
        # Skip filter results
        if "_filter" in deposit_path.name:
            continue
        
        try:
            with open(deposit_path) as f:
                deposit = json.load(f)
            
            # Check if deposit has broadcast field
            if deposit.get("broadcast"):
                broadcasts.append({
                    "drop_id": deposit.get("drop_id", deposit_path.stem),
                    "broadcast": deposit["broadcast"],
                    "timestamp": deposit.get("timestamp")
                })
        except (json.JSONDecodeError, IOError) as e:
            print(f"[BROADCAST] Warning: Could not read {deposit_path.name}: {e}")
    
    return broadcasts


def inject_broadcasts(brief_content: str, broadcasts: list[dict]) -> str:
    """Inject broadcasts section into brief before spawning."""
    if not broadcasts:
        return brief_content
    
    # Create broadcasts section
    section = "\n\n## Broadcasts from Prior Drops\n\n"
    section += "These findings were shared by earlier Drops in this build:\n\n"
    
    for b in broadcasts:
        section += f"- **{b['drop_id']}:** {b['broadcast']}\n"
    
    # Insert before common section markers or at end
    for marker in ["## Requirements", "## Context", "## Files to Read"]:
        if marker in brief_content:
            return brief_content.replace(marker, section + marker, 1)
    
    # If no markers found, append at end
    return brief_content + section


async def spawn_drop(slug: str, drop_id: str, brief: str, model: str = None) -> str:
    """Spawn a Drop via /zo/ask, return conversation_id
    
    Note: The /zo/ask API may not return the actual conversation_id.
    We generate a tracking ID but rely on deposit detection for completion.
    """
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        raise RuntimeError("ZO_CLIENT_IDENTITY_TOKEN not set")
    
    # Collect and inject broadcasts from prior Drops
    broadcasts = collect_broadcasts(slug)
    brief_with_broadcasts = inject_broadcasts(brief, broadcasts)
    
    # Check if this is a pool worker and inject pool instructions
    meta = load_meta(slug)
    pool = meta.get("task_pool", {})
    drops = meta.get("drops", {})
    drop_info = drops.get(drop_id, {})
    
    if pool.get("enabled") and drop_id in pool.get("worker_drops", []):
        print(f"[POOL] Injecting pool claim instructions for {drop_id}")
        brief_with_broadcasts = inject_pool_claim_instructions(brief_with_broadcasts, slug, drop_id)
    
    # Build deposit format as separate string to avoid f-string escaping issues
    deposit_format = '''{\n  \"drop_id\": \"''' + drop_id + '''\",\n  \"status\": \"complete\",\n  \"summary\": \"What you accomplished\",\n  \"artifacts\": [\"list\", \"of\", \"files\", \"created\"],\n  \"learnings\": [\"any lessons for other workers\"],\n  \"errors\": []\n}'''
    
    full_prompt = f"""You are a Pulse Drop executing build \"{slug}\", task \"{drop_id}\".

**YOUR IDENTITY:**
- Build: {slug}
- Drop ID: {drop_id}
- Type: Headless worker (no human in loop)

**EXECUTION PROTOCOL:**
1. Read the brief below carefully
2. Execute the task completely
3. When done, write your deposit JSON to: N5/builds/{slug}/deposits/{drop_id}.json
4. DO NOT commit code (orchestrator handles commits)
5. If blocked, write deposit with status \"blocked\" and explain why

**DEPOSIT FORMAT:**
{deposit_format}

Status can be \"complete\", \"blocked\", or \"partial\".

---
BRIEF:
---
{brief_with_broadcasts}"""
    
    request_body = {"input": full_prompt}
    if model:
        request_body["model_name"] = model
    
    print(f"[SPAWN] Spawning Drop {drop_id} via /zo/ask...")
    
    start = datetime.now()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=DEFAULT_SPAWN_TIMEOUT)) as session:
        async with session.post(
            ZO_API_URL,
            headers={
                "authorization": token,
                "content-type": "application/json"
            },
            json=request_body
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"API returned {resp.status}: {await resp.text()}")
            
            result = await resp.json()
            elapsed = datetime.now() - start
            
            # Generate tracking ID
            tracking_id = f"pulse_{slug}_{drop_id}_{int(start.timestamp())}"
            
            print(f"[SPAWN] Drop {drop_id} spawned (tracking: {tracking_id}, {elapsed.total_seconds():.1f}s)")
            return tracking_id


def launch_spawn_worker(slug: str, drop_id: str, model: str = None) -> int:
    """Launch detached worker process that performs /zo/ask spawn call."""
    artifacts_dir = BUILDS_DIR / slug / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    log_path = artifacts_dir / f"spawn-{drop_id}.log"
    err_path = artifacts_dir / f"spawn-{drop_id}-err.log"

    cmd = [sys.executable, "-u", str(Path(__file__)), "spawn-one", slug, drop_id]
    if model:
        cmd.extend(["--model", model])

    with open(log_path, "a") as out, open(err_path, "a") as err:
        proc = subprocess.Popen(
            cmd,
            cwd=str(WORKSPACE),
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
    return proc.pid


def _record_spawn_success(slug: str, drop_id: str, conversation_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with locked_meta(slug) as meta:
        info = meta.get("drops", {}).get(drop_id)
        if not info:
            raise RuntimeError(f"Unknown drop: {drop_id}")
        if info.get("status") not in ("complete", "failed", "dead", "superseded"):
            info["status"] = "running"
            info["started_at"] = now
        info["conversation_id"] = conversation_id
        info.pop("failure_reason", None)
        info.pop("failed_at", None)
        info.pop("dead_at", None)
        info.pop("dead_reason", None)
        info.pop("spawn_worker_pid", None)
        info.pop("spawn_requested_at", None)
        info["last_progress_at"] = now

        failures = int(meta.get("spawn_failures_consecutive", 0))
        if failures > 0:
            meta["spawn_failures_consecutive"] = 0
            _close_spawn_circuit(meta)
    register_drop_conversation(drop_id, slug, conversation_id)


def _record_spawn_failure(slug: str, drop_id: str, error_message: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with locked_meta(slug) as meta:
        info = meta.get("drops", {}).get(drop_id)
        if not info:
            raise RuntimeError(f"Unknown drop: {drop_id}")
        info["status"] = "failed"
        info["failure_reason"] = f"Spawn error: {error_message}"
        info["failed_at"] = now
        info.pop("spawn_worker_pid", None)
        info.pop("spawn_requested_at", None)

        _increment_spawn_failures(meta, now)


def spawn_one(slug: str, drop_id: str, model: str = None) -> int:
    """Detached spawn worker. Does the blocking /zo/ask call and writes result to meta."""
    try:
        brief = load_drop_brief(slug, drop_id)
        conversation_id = asyncio.run(spawn_drop(slug, drop_id, brief, model))
        _record_spawn_success(slug, drop_id, conversation_id)
        print(f"[SPAWN_WORKER] {drop_id} -> running")
        return 0
    except Exception as e:
        err = str(e).strip() or repr(e)
        _record_spawn_failure(slug, drop_id, err)
        print(f"[SPAWN_WORKER] {drop_id} failed: {err}")
        return 1


def start_build(slug: str):
    """Start a build"""
    meta = load_meta(slug)
    meta["status"] = "active"
    meta["started_at"] = datetime.now(timezone.utc).isoformat()
    save_meta(slug, meta)
    update_status_md(slug, meta)
    print(f"[PULSE] Build {slug} started")


def stop_build(slug: str):
    """Stop a build"""
    meta = load_meta(slug)
    meta["status"] = "stopped"
    meta["stopped_at"] = datetime.now(timezone.utc).isoformat()
    save_meta(slug, meta)
    update_status_md(slug, meta)
    print(f"[PULSE] Build {slug} stopped")


def resume_build(slug: str):
    """Resume a stopped build"""
    meta = load_meta(slug)
    if meta.get("status") != "stopped":
        print(f"[ERROR] Build {slug} is not stopped (current: {meta.get('status')})")
        return
    
    meta["status"] = "active"
    meta["resumed_at"] = datetime.now(timezone.utc).isoformat()
    save_meta(slug, meta)
    update_status_md(slug, meta)
    print(f"[PULSE] Build {slug} resumed")


def _normalize_meta_for_waves(meta: dict) -> None:
    """Normalize legacy meta structure into waves structure in memory."""
    if meta.get("waves"):
        return  # Already using waves
    
    # Build waves from currents or drop stream/order
    waves = {}
    drops = meta.get("drops", {})
    
    if meta.get("currents"):
        # currents = {"chain1": ["D1.1", "D1.2"], "chain2": ["D2.1"]}
        wave_num = 1
        for chain_name, chain_drops in meta["currents"].items():
            for drop_id in chain_drops:
                wave_key = f"W{wave_num}"
                if wave_key not in waves:
                    waves[wave_key] = []
                waves[wave_key].append(drop_id)
            wave_num += 1
    else:
        # Group by stream number
        streams = {}
        for drop_id, info in drops.items():
            try:
                stream_num, order = get_drop_stream_order(drop_id, info)
                if stream_num not in streams:
                    streams[stream_num] = []
                streams[stream_num].append((order, drop_id))
            except Exception:
                # Fallback: put in stream 1
                if 1 not in streams:
                    streams[1] = []
                streams[1].append((1, drop_id))
        
        # Convert streams to waves
        for stream_num in sorted(streams.keys()):
            wave_key = f"W{stream_num}"
            waves[wave_key] = [drop_id for _, drop_id in sorted(streams[stream_num])]
    
    meta["waves"] = waves
    meta["active_wave"] = "W1"


def _get_active_wave(meta: dict) -> str | None:
    """Get the currently active wave."""
    waves = meta.get("waves", {})
    if not waves:
        return None
    
    active = meta.get("active_wave")
    if active and active in waves:
        return active
    
    # Default to first wave
    sorted_waves = sort_wave_keys(list(waves.keys()))
    return sorted_waves[0] if sorted_waves else None


def _can_advance_wave(meta: dict) -> bool:
    """Check if current wave is complete and can advance."""
    waves = meta.get("waves", {})
    active_wave = _get_active_wave(meta)
    
    if not active_wave or active_wave not in waves:
        return False
    
    drops = meta.get("drops", {})
    
    # Check if all blocking Drops in active wave are complete
    for drop_id in waves[active_wave]:
        info = drops.get(drop_id, {})
        if info.get("blocking", True):  # Default to blocking=True
            status = info.get("status", "pending")
            if status not in ("complete", "failed", "dead", "superseded"):
                return False
    
    return True


def _advance_wave(meta: dict) -> bool:
    """Advance to the next wave if possible. Returns True if advanced."""
    if not _can_advance_wave(meta):
        return False
    
    waves = meta.get("waves", {})
    active_wave = meta.get("active_wave")
    
    if not active_wave:
        return False
    
    sorted_waves = sort_wave_keys(list(waves.keys()))
    try:
        current_idx = sorted_waves.index(active_wave)
        if current_idx + 1 < len(sorted_waves):
            next_wave = sorted_waves[current_idx + 1]
            meta["active_wave"] = next_wave
            print(f"[WAVE] Advanced from {active_wave} to {next_wave}")
            return True
    except ValueError:
        pass
    
    return False


def _build_stream_chains(drops: dict) -> dict:
    """Build mapping of stream_num -> [(order, drop_id), ...]"""
    streams = {}
    for drop_id, info in drops.items():
        try:
            stream_num, order = get_drop_stream_order(drop_id, info)
            if stream_num not in streams:
                streams[stream_num] = []
            streams[stream_num].append((order, drop_id))
        except Exception:
            continue
    
    # Sort by order within each stream
    for stream_num in streams:
        streams[stream_num].sort()
    
    return streams


def _can_run_stream_order(drop_id: str, drops: dict, stream_chains: dict, complete: set) -> bool:
    """Check if Drop can run based on stream sequential ordering."""
    try:
        stream_num, order = get_drop_stream_order(drop_id, drops.get(drop_id, {}))
    except Exception:
        return True
    
    if stream_num not in stream_chains:
        return True
    
    chain = stream_chains[stream_num]
    
    for chain_order, chain_drop_id in chain:
        if chain_drop_id == drop_id:
            break
        if chain_order < order and chain_drop_id not in complete:
            return False
    
    return True


def check_build_complete(meta: dict) -> bool:
    """Check if all blocking Drops are complete"""
    drops = meta.get("drops", {})
    
    # Also check for "ready" drops (learning mode drops awaiting manual launch)
    # These block completion just like pending drops
    for drop_id, info in drops.items():
        blocking = info.get("blocking", True)
        if not blocking:
            continue
        
        status = info.get("status", "pending")
        if status not in ("complete", "superseded"):
            return False
    
    return True


def _check_pool_complete(meta: dict) -> bool:
    """Check if task pool is exhausted (no pending tasks)."""
    pool = meta.get("task_pool", {})
    if not pool.get("enabled"):
        return True  # No pool, consider complete
    
    tasks = pool.get("tasks", [])
    for task in tasks:
        if task["status"] == "pending":
            return False
    
    return True


def get_ready_drops(meta: dict) -> list[str]:
    """Get list of Drops ready to spawn.
    
    Rules:
    - waves mode: only drops in active wave, not blocked by dependencies or stream order
    - legacy mode: respects currents, stream sequencing as before
    
    In waves mode:
      - parallel: drops in same wave can run in parallel
      - sequential: within a stream, order k+1 waits for order k to be complete

    legacy mode (no meta.waves):
      - If current_stream is present, only consider drops in that stream
      - Preserve legacy currents sequencing if meta.currents exists
    """
    ready: list[str] = []
    drops = meta.get("drops", {})
    currents = meta.get("currents", {})

    complete = {d for d, info in drops.items() if info.get("status") == "complete"}
    stream_chains = _build_stream_chains(drops)

    allowed: set[str]
    if meta.get("waves"):
        active_wave = _get_active_wave(meta)
        if not active_wave:
            return []
        if isinstance(meta.get("gate"), dict) and meta["gate"].get("type") == "wave_blocked":
            return []
        allowed = set((meta.get("waves") or {}).get(active_wave, []) or [])
    elif meta.get("current_stream") is not None:
        allowed = set()
        try:
            cur = int(meta.get("current_stream"))
        except Exception:
            cur = None
        for drop_id, info in drops.items():
            try:
                stream, _ = get_drop_stream_order(drop_id, info)
            except Exception:
                continue
            if cur is None or stream == cur:
                allowed.add(drop_id)
    else:
        allowed = set(drops.keys())

    for drop_id in sorted(allowed):
        info = drops.get(drop_id, {})
        if info.get("status") not in ("pending",):
            continue

        # Dependencies
        depends_on = info.get("depends_on", [])
        if not all(d in complete for d in depends_on):
            continue

        # Legacy Currents (sequential chains)
        blocked_by_current = False
        for chain in currents.values():
            if drop_id in chain:
                idx = chain.index(drop_id)
                if idx > 0 and chain[idx - 1] not in complete:
                    blocked_by_current = True
                    break
        if blocked_by_current:
            continue

        # Stream sequential ordering
        if not _can_run_stream_order(drop_id, drops, stream_chains, complete):
            continue

        ready.append(drop_id)

    return ready


def get_running_drops(meta: dict) -> list[tuple[str, dict]]:
    """Get list of running Drops with their info"""
    return [
        (drop_id, info)
        for drop_id, info in meta.get("drops", {}).items()
        if info.get("status") == "running"
    ]


def check_stream_complete(meta: dict) -> bool:
    """Legacy: Check if current stream is complete (terminal in that stream)."""
    if meta.get("current_stream") is None:
        return False

    try:
        current_stream = int(meta.get("current_stream", 1))
    except Exception:
        current_stream = 1

    drops = meta.get("drops", {})

    for drop_id, info in drops.items():
        try:
            stream_num, _ = get_drop_stream_order(drop_id, info)
        except Exception:
            continue

        if stream_num == current_stream:
            if info.get("status") not in ["complete", "failed", "dead"]:
                return False

    return True


def advance_stream(meta: dict) -> bool:
    """Legacy: Advance to next stream if current is complete. Returns True if advanced."""
    if not check_stream_complete(meta):
        return False

    current = meta.get("current_stream", 1)
    total = meta.get("total_streams", 1)

    try:
        current = int(current)
    except Exception:
        current = 1
    try:
        total = int(total)
    except Exception:
        total = 1

    if current < total:
        meta["current_stream"] = current + 1
        return True

    return False


def check_first_wins(slug: str, meta: dict) -> bool:
    """Check if a hypothesis was confirmed and supersede others."""
    if not meta.get("first_wins"):
        return False
    
    hypothesis_group = meta.get("hypothesis_group") or list(meta.get("drops", {}).keys())
    
    # Find confirmed hypothesis
    winner = None
    for drop_id in hypothesis_group:
        deposit = get_deposit(slug, drop_id)
        if deposit and deposit.get("verdict") == "confirmed":
            winner = drop_id
            break
    
    if not winner:
        return False
    
    # Supersede others
    drops = meta.get("drops", {})
    superseded_count = 0
    for drop_id in hypothesis_group:
        if drop_id == winner:
            continue
        if drops.get(drop_id, {}).get("status") in ("pending", "running"):
            drops[drop_id]["status"] = "superseded"
            drops[drop_id]["superseded_by"] = winner
            drops[drop_id]["superseded_at"] = datetime.now(timezone.utc).isoformat()
            superseded_count += 1
            print(f"[FIRST_WINS] {drop_id} superseded by {winner}")
    
    if superseded_count > 0:
        save_meta(slug, meta)
        print(f"[FIRST_WINS] {superseded_count} Drops superseded by {winner}")
        return True
    
    return False


async def summarize_build(slug: str, meta: dict) -> str:
    """Generate completion summary"""
    deposits_dir = BUILDS_DIR / slug / "deposits"
    summaries = []
    
    for drop_id in sorted(meta.get("drops", {}).keys()):
        deposit = get_deposit(slug, drop_id)
        if deposit:
            summaries.append(f"**{drop_id}:** {deposit.get('summary', 'No summary')}")
    
    return "\n".join(summaries)


async def tick(slug: str):
    """Run one orchestration cycle"""
    print(f"\n[PULSE TICK] {slug} @ {datetime.now(timezone.utc).isoformat()}")
    acquired, lease_holder = _acquire_tick_lease(slug)
    if not acquired:
        print(f"[LEASE] Tick lease held by another process. Skipping tick for {slug}.")
        return

    try:
        await _tick_inner(slug, lease_holder)
    finally:
        _release_tick_lease(slug, lease_holder)


async def _tick_inner(slug: str, lease_holder: str):
    """Internal tick body with lease already acquired."""
    meta = load_meta(slug)
    
    if meta.get("status") == "complete":
        print(f"[PULSE] Build {slug} already complete")
        return
    
    if meta.get("status") == "stopped":
        print(f"[PULSE] Build {slug} is stopped")
        return

    _heartbeat_tick_lease(slug, lease_holder)
    
    # 1. Check for new deposits from running Drops
    running = get_running_drops(meta)
    broadcasts_updated = False
    
    for drop_id, info in running:
        deposit = get_deposit(slug, drop_id)
        if deposit:
            print(f"[DEPOSIT] Found deposit for {drop_id}: {deposit.get('status', 'unknown')}")
            
            # Update Drop status based on deposit
            old_status = info.get("status", "unknown")
            new_status = deposit.get("status", "complete")

            if new_status == "complete":
                validation_cfg = load_config().get("validation", {})
                auto_pass = bool(validation_cfg.get("auto_pass_on_validator_error", True))
                try:
                    passed, validator_result = await run_validators(slug, drop_id)
                    _save_validation_result(slug, drop_id, validator_result)
                    info["validation"] = validator_result
                    if not passed:
                        info["status"] = "failed"
                        info["failure_reason"] = validator_result.get("reason", "Validation failed")
                        info["failed_at"] = datetime.now(timezone.utc).isoformat()
                        update_drop_conversation_status(info.get("conversation_id"), "failed")
                        print(f"[VALIDATOR FAIL] {drop_id}: {info['failure_reason']}")
                        broadcasts_updated = True
                        continue
                    print(f"[VALIDATOR PASS] {drop_id}")
                except Exception as e:
                    error_msg = f"Validator error: {e}"
                    if auto_pass:
                        info["validation_error"] = str(e)
                        _save_validation_result(
                            slug,
                            drop_id,
                            {
                                "drop_id": drop_id,
                                "build_slug": slug,
                                "validated_at": datetime.now(timezone.utc).isoformat(),
                                "verdict": "PASS",
                                "reason": f"{error_msg} (auto-pass)",
                                "mechanical": None,
                                "llm": None,
                            },
                        )
                        print(f"[VALIDATOR WARN] {drop_id}: {error_msg} (auto-pass)")
                    else:
                        info["status"] = "failed"
                        info["failure_reason"] = error_msg
                        info["failed_at"] = datetime.now(timezone.utc).isoformat()
                        update_drop_conversation_status(info.get("conversation_id"), "failed")
                        print(f"[VALIDATOR ERROR] {drop_id}: {error_msg}")
                        broadcasts_updated = True
                        continue
            
            # For pool workers, check if they completed tasks
            pool = meta.get("task_pool", {})
            if pool.get("enabled") and drop_id in pool.get("worker_drops", []):
                # Update completed tasks in pool
                completed_tasks = deposit.get("completed_tasks", [])
                for task_info in completed_tasks:
                    task_id = task_info.get("id")
                    task_status = task_info.get("status", "complete")
                    if task_id:
                        update_task_status(slug, task_id, task_status, drop_id)
            
            if new_status == "complete":
                info["status"] = "complete"
                info["completed_at"] = datetime.now(timezone.utc).isoformat()
                update_drop_conversation_status(info.get("conversation_id"), "complete")
            elif new_status == "blocked":
                info["status"] = "failed"
                info["failure_reason"] = deposit.get("summary", "Blocked")
                info["failed_at"] = datetime.now(timezone.utc).isoformat()
                update_drop_conversation_status(info.get("conversation_id"), "failed")
            elif new_status == "partial":
                info["status"] = "failed"
                info["failure_reason"] = "Partial completion"
                info["failed_at"] = datetime.now(timezone.utc).isoformat()
                update_drop_conversation_status(info.get("conversation_id"), "failed")
            
            print(f"[STATUS] {drop_id}: {old_status} → {info['status']}")
            broadcasts_updated = True
    
    # 2. Check for dead Drops (running too long)
    now = datetime.now(timezone.utc)
    for drop_id, info in running:
        worker_pid = info.get("spawn_worker_pid")
        requested = _parse_iso(info.get("spawn_requested_at"))
        if worker_pid and requested:
            elapsed_spawn = (now - requested).total_seconds()
            if elapsed_spawn > DEFAULT_SPAWN_TIMEOUT:
                print(f"[SPAWN_TIMEOUT] {drop_id} spawn worker exceeded {int(elapsed_spawn)}s while running")
                if _pid_is_running(worker_pid):
                    try:
                        os.kill(int(worker_pid), 15)
                    except Exception:
                        pass
                info["status"] = "failed"
                info["failure_reason"] = (
                    f"Spawn error: /zo/ask handshake timeout after {int(elapsed_spawn)}s"
                )
                info["failed_at"] = now.isoformat()
                info.pop("spawn_worker_pid", None)
                info.pop("spawn_requested_at", None)
                update_drop_conversation_status(info.get("conversation_id"), "failed")
                _increment_spawn_failures(meta, now.isoformat())
                broadcasts_updated = True
                continue
        if worker_pid and requested and (now - requested).total_seconds() > 5 and not _pid_is_running(worker_pid):
            # Spawn worker died before handing off a healthy worker thread/deposit.
            print(f"[SPAWN_EXIT] {drop_id} spawn worker exited while drop is running")
            info["status"] = "failed"
            info["failure_reason"] = "Spawn error: spawn worker exited unexpectedly"
            info["failed_at"] = now.isoformat()
            info.pop("spawn_worker_pid", None)
            info.pop("spawn_requested_at", None)
            update_drop_conversation_status(info.get("conversation_id"), "failed")
            _increment_spawn_failures(meta, now.isoformat())
            broadcasts_updated = True
            continue
        if worker_pid and requested:
            # While detached spawn is still in-flight, do not apply generic dead-drop timeout.
            continue

        if info.get("status") != "running":
            continue  # Skip if already processed above
        
        started_str = info.get("started_at")
        if not started_str:
            continue
        
        try:
            started = datetime.fromisoformat(started_str.replace("Z", "+00:00"))
            elapsed = now - started
            if elapsed.total_seconds() > DEFAULT_DEAD_THRESHOLD:
                print(f"[DEAD] {drop_id} has been running for {elapsed.total_seconds()/60:.0f} minutes")
                info["status"] = "dead"
                info["dead_at"] = now.isoformat()
                info["dead_reason"] = f"Running for {elapsed.total_seconds()/60:.0f} minutes"
                update_drop_conversation_status(info.get("conversation_id"), "failed")
                broadcasts_updated = True
        except ValueError:
            continue

    # 2b. Check for stuck spawn handshakes
    for drop_id, info in meta.get("drops", {}).items():
        if info.get("status") != "spawning":
            continue
        requested = _parse_iso(info.get("spawn_requested_at"))
        if not requested:
            continue
        elapsed = (now - requested).total_seconds()
        worker_pid = info.get("spawn_worker_pid")
        if worker_pid and elapsed > 5 and not _pid_is_running(worker_pid):
            print(f"[SPAWN_EXIT] {drop_id} spawn worker exited before state transition")
            info["status"] = "failed"
            info["failure_reason"] = "Spawn error: spawn worker exited unexpectedly"
            info["failed_at"] = now.isoformat()
            info.pop("spawn_worker_pid", None)
            info.pop("spawn_requested_at", None)
            broadcasts_updated = True
            continue
        if elapsed > DEFAULT_SPAWN_WORKER_TIMEOUT:
            print(f"[SPAWN_TIMEOUT] {drop_id} stuck in spawning for {int(elapsed)}s")
            info["status"] = "failed"
            info["failure_reason"] = f"Spawn error: spawn handshake timeout after {int(elapsed)}s"
            info["failed_at"] = now.isoformat()
            info.pop("spawn_worker_pid", None)
            info.pop("spawn_requested_at", None)
            broadcasts_updated = True
    
    # 3. Check for first-wins supersession
    if check_first_wins(slug, meta):
        broadcasts_updated = True
    
    # 4. Normalize legacy meta to waves for processing
    _normalize_meta_for_waves(meta)
    
    # 5. Advance wave/stream if current is complete
    wave_advanced = False
    if meta.get("waves"):
        if _advance_wave(meta):
            wave_advanced = True
            broadcasts_updated = True
    else:
        if advance_stream(meta):
            wave_advanced = True
            broadcasts_updated = True
    
    # 6. Spawn ready Drops
    ready = get_ready_drops(meta)
    spawned = []
    
    circuit_open = _spawn_circuit_open(meta)
    if circuit_open:
        circuit = meta.get("spawn_circuit", {})
        print(
            f"[CIRCUIT] Spawn circuit open until {circuit.get('open_until')} "
            f"({circuit.get('open_reason', 'no reason')}). Skipping auto-spawn this tick."
        )

    for drop_id in ready:
        try:
            info = meta["drops"][drop_id]

            # Determine effective spawn mode based on build_mode
            build_mode = get_build_mode(meta)

            if build_mode == "rush":
                effective_spawn = "auto"
            elif info.get("spawn_mode"):
                effective_spawn = info["spawn_mode"]
            elif build_mode == "learning" and info.get("engagement_tag") == "mechanical":
                effective_spawn = "auto"
            elif build_mode == "learning":
                effective_spawn = "manual"
            else:
                effective_spawn = info.get("spawn_mode", "auto")

            if effective_spawn == "manual":
                launcher_path = ensure_launcher(slug, drop_id)
                if build_mode == "learning":
                    info["status"] = "ready"
                    info["ready_at"] = datetime.now(timezone.utc).isoformat()
                    print(f"[LEARNING] {drop_id} ready for manual launch. Launcher generated.")
                else:
                    info["status"] = "awaiting_manual"
                    info["launcher_created_at"] = datetime.now(timezone.utc).isoformat()
                    print(f"[MANUAL] {drop_id} → launcher at {launcher_path}")
                spawned.append(drop_id)
            else:
                if circuit_open:
                    continue
                model = meta.get("model")
                tracking_id = f"spawn_worker_{slug}_{drop_id}_{int(datetime.now(timezone.utc).timestamp())}"
                pid = launch_spawn_worker(slug, drop_id, model)
                info["status"] = "running"
                info["started_at"] = datetime.now(timezone.utc).isoformat()
                info["conversation_id"] = tracking_id
                info["spawn_requested_at"] = info["started_at"]
                info["spawn_worker_pid"] = pid
                info["last_progress_at"] = info["started_at"]
                register_drop_conversation(drop_id, slug, tracking_id)
                spawned.append(drop_id)
                
        except Exception as e:
            print(f"[ERROR] Failed to spawn {drop_id}: {e}")
            meta["drops"][drop_id]["status"] = "failed"
            meta["drops"][drop_id]["failure_reason"] = f"Spawn error: {e}"
            meta["drops"][drop_id]["failed_at"] = datetime.now(timezone.utc).isoformat()
    
    if spawned:
        print(f"[SPAWN] Spawned: {', '.join(spawned)}")
        broadcasts_updated = True
    
    # 7. Check if build is complete
    build_complete = check_build_complete(meta)
    pool_complete = _check_pool_complete(meta)
    
    if build_complete and pool_complete:
        if meta.get("status") != "complete":
            print(f"[COMPLETE] Build {slug} is complete!")
            meta["status"] = "complete"
            meta["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            # Generate summary
            summary = await summarize_build(slug, meta)
            meta["summary"] = summary
            
            await send_sms(f"[PULSE] {slug} COMPLETE ✅")
            broadcasts_updated = True
    
    # 8. Save and update
    if broadcasts_updated:
        meta["last_progress_at"] = datetime.now(timezone.utc).isoformat()
        save_meta(slug, meta)
        update_status_md(slug, meta)
    
    print(f"[PULSE] Tick complete. Ready: {len(ready)}, Spawned: {len(spawned)}")


def show_status(slug: str):
    """Show build status"""
    meta = load_meta(slug)
    drops = meta.get("drops", {})

    complete = sum(1 for d in drops.values() if d.get("status") == "complete")
    running = sum(1 for d in drops.values() if d.get("status") == "running")
    spawning = sum(1 for d in drops.values() if d.get("status") == "spawning")
    awaiting_manual = sum(1 for d in drops.values() if d.get("status") == "awaiting_manual")
    ready_count = sum(1 for d in drops.values() if d.get("status") == "ready")
    pending = sum(1 for d in drops.values() if d.get("status") == "pending")
    superseded = sum(1 for d in drops.values() if d.get("status") == "superseded")
    dead = sum(1 for d in drops.values() if d.get("status") == "dead")
    failed = sum(1 for d in drops.values() if d.get("status") == "failed")

    gate = meta.get("gate")
    gate_line = ""
    if isinstance(gate, dict) and gate.get("reason"):
        gate_line = f"Gate: {gate.get('type', 'gate')} — {gate.get('reason')}\n"

    if meta.get("waves"):
        gate_scope = f"Wave: {meta.get('active_wave', '?')}\n"
    else:
        gate_scope = f"Legacy Stream Gate: {meta.get('current_stream', '?')}/{meta.get('total_streams', '?')}\n"

    # Add pool status if enabled
    pool_status = get_pool_status(meta)
    pool_text = ""
    if pool_status:
        counts = pool_status["counts"]
        pool_text = f"""
Task Pool:
  Pending: {counts['pending']}
  Claimed: {counts['claimed']}
  Complete: {counts['complete']}
  Failed: {counts['failed']}
"""

    print(f"""
Build: {slug}
Status: {meta.get('status', 'unknown')}
{gate_scope}{gate_line}
Drops:
  Complete:        {complete}
  Running:         {running}
  Spawning:        {spawning}
  Awaiting Manual: {awaiting_manual}
  Ready:           {ready_count}
  Pending:         {pending}
  Superseded:      {superseded}
  Dead:            {dead}
  Failed:          {failed}
  Total:           {len(drops)}
{pool_text}
Progress: {complete}/{len(drops)} ({int(complete/len(drops)*100) if drops else 0}%)
""")


def retry_drop(slug: str, drop_id: str, reason: str = None):
    """Reset a Drop to pending, archive old deposit, optionally appends retry reason to brief.
    
    Based on Theo's lesson: If output is bad, don't keep appending corrections.
    Revert and restart with corrected input. This gives the model a clean slate
    with better context rather than compounding errors.
    """
    meta = load_meta(slug)
    
    if drop_id not in meta.get("drops", {}):
        print(f"[ERROR] Drop {drop_id} not found in build {slug}")
        return
    
    drop_info = meta["drops"][drop_id]
    old_status = drop_info.get("status")
    
    # Archive old deposit if exists
    deposit_path = BUILDS_DIR / slug / "deposits" / f"{drop_id}.json"
    if deposit_path.exists():
        archive_dir = BUILDS_DIR / slug / "deposits" / "archived"
        archive_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_path = archive_dir / f"{drop_id}_{timestamp}.json"
        deposit_path.rename(archive_path)
        print(f"[RETRY] Archived old deposit to {archive_path.name}")
    
    # Archive filter result if exists
    filter_path = BUILDS_DIR / slug / "deposits" / f"{drop_id}_filter.json"
    if filter_path.exists():
        archive_dir = BUILDS_DIR / slug / "deposits" / "archived"
        archive_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_path = archive_dir / f"{drop_id}_filter_{timestamp}.json"
        filter_path.rename(archive_path)
    
    # Reset Drop status
    drop_info["status"] = "pending"
    drop_info.pop("started_at", None)
    drop_info.pop("conversation_id", None)
    drop_info.pop("failure_reason", None)
    drop_info["retry_count"] = drop_info.get("retry_count", 0) + 1
    drop_info["last_retry"] = datetime.now(timezone.utc).isoformat()
    
    # Optionally update brief with retry reason
    if reason:
        try:
            brief_path = find_drop_brief_path(slug, drop_id)
            brief_content = brief_path.read_text()
            
            # Append retry context section
            retry_section = f"""

---

## ⚠️ Retry Context (Attempt {drop_info['retry_count'] + 1})

**Previous attempt failed because:** {reason}

**What to do differently:**
- Address the issue described above
- Review the archived deposit to understand what went wrong
- Follow the brief more carefully

"""
            # Insert before "## On Completion" if it exists, otherwise append
            if "## On Completion" in brief_content:
                brief_content = brief_content.replace("## On Completion", retry_section + "## On Completion")
            else:
                brief_content += retry_section
            
            brief_path.write_text(brief_content)
            print(f"[RETRY] Updated brief with retry context")
        except Exception as e:
            print(f"[RETRY] Warning: Could not update brief: {e}")
    
    save_meta(slug, meta)
    update_status_md(slug, meta)
    
    print(f"[RETRY] {drop_id} reset from '{old_status}' to 'pending' (attempt {drop_info['retry_count'] + 1})")
    print(f"[RETRY] Run 'pulse tick {slug}' or wait for Sentinel to re-spawn")


def validate_plan(slug: str):
    """Validate plan completeness before starting a build.
    
    Based on Theo's lesson: Plans are context vehicles. An incomplete plan
    means the model will guess, and guessing compounds errors across Drops.
    """
    validator_path = SKILLS_DIR / "pulse_plan_validator.py"
    
    if not validator_path.exists():
        print(f"[ERROR] Plan validator not found at {validator_path}")
        return
    
    result = subprocess.run(
        ["python3", str(validator_path), slug],
        capture_output=False,
        cwd=str(WORKSPACE)
    )
    
    if result.returncode == 0:
        print(f"\n✅ Plan validation passed. Safe to start build.")
    else:
        print(f"\n❌ Plan validation failed. Fix issues before starting build.")
        print(f"   Run: python3 {validator_path} {slug} --fix")


# ============================================================================
# SMART SENTINEL: RECOVERY ENGINE
# ============================================================================

def _get_recovery_config(meta: dict) -> dict:
    """Get recovery config from meta.json, falling back to RECOVERY_DEFAULTS."""
    config = dict(RECOVERY_DEFAULTS)
    build_overrides = meta.get("recovery", {})
    config.update(build_overrides)
    return config


def _classify_failure(drop_id: str, info: dict, slug: str) -> str:
    """Classify a failure type for recovery rule matching.

    Returns one of: 'dead_timeout', 'spawn_error', 'content_error', 'unknown'
    """
    status = info.get("status", "")

    if status == "dead":
        return "dead_timeout"

    reason = info.get("failure_reason", "") or ""
    reason_lower = reason.lower()

    spawn_signals = ["spawn error", "api returned", "timeout", "connection", "zo_client_identity_token"]
    if any(sig in reason_lower for sig in spawn_signals):
        return "spawn_error"

    deposit = get_deposit(slug, drop_id)
    if deposit:
        dep_status = deposit.get("status", "")
        if dep_status in ("blocked", "partial"):
            return "content_error"

    if reason:
        return "content_error"

    return "unknown"


def _log_recovery_action(slug: str, action: dict) -> None:
    """Append a recovery action to RECOVERY_LOG.jsonl (P39: Audit Everything)."""
    log_path = BUILDS_DIR / slug / "RECOVERY_LOG.jsonl"
    action["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(log_path, "a") as f:
        f.write(json.dumps(action) + "\n")


def _check_build_stale(slug: str, meta: dict, config: dict) -> bool:
    """Check if a build is stale (active too long with no progress)."""
    started_str = meta.get("started_at")
    if not started_str:
        return False

    now = datetime.now(timezone.utc)
    try:
        started = datetime.fromisoformat(started_str.replace("Z", "+00:00"))
    except ValueError:
        return False

    stale_hours = config.get("stale_threshold_hours", 4)
    if (now - started).total_seconds() < stale_hours * 3600:
        return False

    last_progress_str = meta.get("last_progress_at")
    if not last_progress_str:
        return True

    try:
        last_progress = datetime.fromisoformat(last_progress_str.replace("Z", "+00:00"))
    except ValueError:
        return True

    no_progress_minutes = config.get("stale_no_progress_minutes", 60)
    return (now - last_progress).total_seconds() > no_progress_minutes * 60


def _check_wave_death(meta: dict, config: dict) -> bool:
    """Check if all blocking Drops in the current wave are dead/failed with retries exhausted."""
    waves = meta.get("waves", {})
    active_wave = meta.get("active_wave")
    if not waves or not active_wave:
        return False

    wave_drops = waves.get(active_wave, [])
    if not wave_drops:
        return False

    drops = meta.get("drops", {})
    max_retries = config.get("max_auto_retries", 2)
    terminal_statuses = {"dead", "failed"}

    blocking_drops = [d for d in wave_drops if drops.get(d, {}).get("blocking", True)]
    if not blocking_drops:
        return False

    for drop_id in blocking_drops:
        info = drops.get(drop_id, {})
        status = info.get("status", "pending")
        if status not in terminal_statuses:
            return False
        if info.get("retry_count", 0) < max_retries:
            return False

    return True


def assess_and_recover(slug: str, meta: dict = None, dry_run: bool = False) -> list[dict]:
    """Assess build health and execute recovery actions.

    Deterministic rules applied in priority order:
      R1: dead + retry_count < max → auto-retry with timeout context
      R2: failed + spawn_error + retry_count < max → auto-retry
      R3: failed + content_error → needs AI judgment (escalate)
      R4: all blocking drops in wave dead/failed + retries exhausted → build blocked
      R5: build active > threshold with no recent progress → stale escalation

    Returns list of action dicts describing what was done.
    """
    if meta is None:
        meta = load_meta(slug)

    if meta.get("status") not in ("active",):
        return []

    config = _get_recovery_config(meta)
    max_retries = config.get("max_auto_retries", 2)
    actions: list[dict] = []
    drops = meta.get("drops", {})
    now = datetime.now(timezone.utc)

    # Scan for dead/failed drops needing recovery
    for drop_id, info in drops.items():
        status = info.get("status", "")
        if status not in ("dead", "failed"):
            continue

        retry_count = info.get("retry_count", 0)
        failure_type = _classify_failure(drop_id, info, slug)

        # R1: Dead timeout — auto-retry if under limit
        if failure_type == "dead_timeout" and retry_count < max_retries:
            action = {
                "drop_id": drop_id,
                "rule": "R1",
                "action": "auto_retry",
                "failure_type": failure_type,
                "reason": f"Dead (timeout), auto-retry {retry_count + 1}/{max_retries}",
                "retry_number": retry_count + 1,
            }
            if not dry_run:
                retry_reason = (
                    "Previous attempt died (no response within timeout). "
                    "Focus on completing the core requirement first. "
                    "If blocked, write a deposit with status 'blocked' immediately."
                )
                retry_drop(slug, drop_id, reason=retry_reason)
                info["auto_retried_at"] = now.isoformat()
                info["auto_retry_reason"] = action["reason"]
                info["recovery_source"] = "sentinel_auto"
            _log_recovery_action(slug, action)
            actions.append(action)
            print(f"[RECOVERY] R1: {drop_id} auto-retried ({retry_count + 1}/{max_retries})")
            continue

        # R2: Spawn error — auto-retry if under limit
        if failure_type == "spawn_error" and retry_count < max_retries:
            action = {
                "drop_id": drop_id,
                "rule": "R2",
                "action": "auto_retry",
                "failure_type": failure_type,
                "reason": f"Spawn error (transient), auto-retry {retry_count + 1}/{max_retries}",
                "retry_number": retry_count + 1,
            }
            if not dry_run:
                retry_reason = (
                    "Previous attempt failed during spawn (transient API error). "
                    "This is likely a temporary issue. Proceed normally."
                )
                retry_drop(slug, drop_id, reason=retry_reason)
                info["auto_retried_at"] = now.isoformat()
                info["auto_retry_reason"] = action["reason"]
                info["recovery_source"] = "sentinel_auto"
            _log_recovery_action(slug, action)
            actions.append(action)
            print(f"[RECOVERY] R2: {drop_id} auto-retried (spawn error, {retry_count + 1}/{max_retries})")
            continue

        # R3: Content/logic error — escalate for judgment
        if failure_type == "content_error":
            action = {
                "drop_id": drop_id,
                "rule": "R3",
                "action": "needs_judgment",
                "failure_type": failure_type,
                "reason": info.get("failure_reason", "Content/logic failure"),
            }
            _log_recovery_action(slug, action)
            actions.append(action)
            print(f"[RECOVERY] R3: {drop_id} needs AI judgment (content error)")
            continue

        # Retries exhausted — escalate
        if retry_count >= max_retries:
            action = {
                "drop_id": drop_id,
                "rule": "R1/R2_exhausted",
                "action": "escalate",
                "failure_type": failure_type,
                "reason": f"Retries exhausted ({retry_count}/{max_retries})",
            }
            if not dry_run:
                meta["status"] = "blocked"
                meta["blocked_at"] = now.isoformat()
                meta["blocked_reason"] = action["reason"]
            _log_recovery_action(slug, action)
            actions.append(action)
            print(f"[RECOVERY] {drop_id} retries exhausted — escalating")
            continue

        # Unknown failure — escalate
        action = {
            "drop_id": drop_id,
            "rule": "R_unknown",
            "action": "escalate",
            "failure_type": failure_type,
            "reason": info.get("failure_reason", "Unknown failure type"),
        }
        _log_recovery_action(slug, action)
        actions.append(action)

    # R4: Wave death — all blocking drops in current wave failed with retries exhausted
    if _check_wave_death(meta, config):
        action = {
            "drop_id": "*",
            "rule": "R4",
            "action": "escalate",
            "failure_type": "wave_death",
            "reason": f"All blocking drops in {meta.get('active_wave', '?')} are dead/failed with retries exhausted",
        }
        if not dry_run:
            meta["status"] = "blocked"
            meta["blocked_at"] = now.isoformat()
            meta["blocked_reason"] = action["reason"]
        _log_recovery_action(slug, action)
        actions.append(action)
        print(f"[RECOVERY] R4: Build BLOCKED — {action['reason']}")

    # R5: Stale build detection
    if _check_build_stale(slug, meta, config) and meta.get("status") != "blocked":
        action = {
            "drop_id": "*",
            "rule": "R5",
            "action": "escalate",
            "failure_type": "stale",
            "reason": f"Build active >{config.get('stale_threshold_hours', 4)}h with no progress in >{config.get('stale_no_progress_minutes', 60)}min",
        }
        _log_recovery_action(slug, action)
        actions.append(action)
        print(f"[RECOVERY] R5: Build stale — {action['reason']}")

    # Save meta if mutations occurred (non-dry-run)
    if actions and not dry_run:
        save_meta(slug, meta)
        update_status_md(slug, meta)

    return actions


async def finalize_build(slug: str):
    """Run post-build finalization: safety checks, integration tests, harvest learnings"""
    print(f"\n[FINALIZE] {slug}")
    
    meta = load_meta(slug)
    results = {
        "slug": slug,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "verification": None,
        "integration_tests": None,
        "learnings_harvested": 0,
        "success": True
    }
    
    # 1. Verify artifacts
    print("[FINALIZE] Verifying artifacts...")
    try:
        verify_result = subprocess.run(
            ["python3", str(SKILLS_DIR / "pulse_safety.py"), "verify", slug],
            capture_output=True, text=True, cwd=str(WORKSPACE)
        )
        results["verification"] = {
            "passed": verify_result.returncode == 0,
            "output": verify_result.stdout
        }
        if verify_result.returncode == 0:
            print("[FINALIZE] ✅ Artifact verification passed")
        else:
            print(f"[FINALIZE] ❌ Artifact verification failed")
            results["success"] = False
    except Exception as e:
        print(f"[FINALIZE] Verification error: {e}")
        results["verification"] = {"passed": False, "error": str(e)}
        results["success"] = False
    
    # 2. Run integration tests
    print("[FINALIZE] Running integration tests...")
    try:
        test_result = subprocess.run(
            ["python3", str(SKILLS_DIR / "pulse_integration_test.py"), "run", slug],
            capture_output=True, text=True, cwd=str(WORKSPACE)
        )
        results["integration_tests"] = {
            "passed": test_result.returncode == 0,
            "output": test_result.stdout
        }
        if test_result.returncode == 0:
            print("[FINALIZE] ✅ Integration tests passed")
        else:
            print(f"[FINALIZE] ❌ Integration tests failed")
            results["success"] = False
    except Exception as e:
        print(f"[FINALIZE] Test error: {e}")
        results["integration_tests"] = {"passed": False, "error": str(e)}
    
    # 3. Harvest learnings from deposits
    print("[FINALIZE] Harvesting learnings...")
    try:
        harvest_result = subprocess.run(
            ["python3", str(SKILLS_DIR / "pulse_learnings.py"), "harvest", slug],
            capture_output=True, text=True, cwd=str(WORKSPACE)
        )
        # Parse harvested count from output
        output = harvest_result.stdout
        if "Harvested" in output:
            try:
                count = int(output.split("Harvested")[1].split()[0])
                results["learnings_harvested"] = count
            except:
                pass
        print(f"[FINALIZE] Harvested learnings from deposits")
    except Exception as e:
        print(f"[FINALIZE] Harvest error: {e}")
    
    # 4. Save finalization results
    finalize_path = BUILDS_DIR / slug / "FINALIZATION.json"
    with open(finalize_path, "w") as f:
        json.dump(results, f, indent=2)
    
    # 5. Sync drop statuses from deposits
    deposits_dir = BUILDS_DIR / slug / "deposits"
    if deposits_dir.exists():
        for deposit_file in deposits_dir.glob("*.json"):
            try:
                with open(deposit_file) as f:
                    deposit = json.load(f)
                drop_id = deposit.get("drop_id")
                deposit_status = deposit.get("status")
                if drop_id and drop_id in meta.get("drops", {}):
                    current = meta["drops"][drop_id].get("status")
                    # Only update if deposit says complete and meta doesn't
                    if deposit_status == "complete" and current != "complete":
                        meta["drops"][drop_id]["status"] = "complete"
                        meta["drops"][drop_id]["completed_at"] = deposit.get("timestamp", datetime.now(timezone.utc).isoformat())
                        # Clean up failure fields if present
                        meta["drops"][drop_id].pop("failure_reason", None)
                        meta["drops"][drop_id].pop("failed_at", None)
                        print(f"[FINALIZE] Synced {drop_id} → complete from deposit")
            except Exception as e:
                print(f"[FINALIZE] Warning: Could not read deposit {deposit_file.name}: {e}")
    
    # 6. Update meta status
    meta["finalized_at"] = datetime.now(timezone.utc).isoformat()
    meta["finalization_passed"] = results["success"]
    if results["success"]:
        meta["status"] = "finalized"
    save_meta(slug, meta)
    
    # 7. SMS summary
    if results["success"]:
        await send_sms(f"[PULSE] {slug} FINALIZED ✅ Artifacts verified, tests passed.")
    else:
        failures = []
        if not results.get("verification", {}).get("passed", True):
            failures.append("artifacts")
        if not results.get("integration_tests", {}).get("passed", True):
            failures.append("tests")
        await send_sms(f"[PULSE] {slug} FINALIZE ❌ Failed: {', '.join(failures)}. Review needed.")
    
    print(f"[FINALIZE] Complete. Success: {results['success']}")
    return results


def rush_mode(slug: str, drop_id: str = None, wave: str = None):
    """Override learning mode for specified scope."""
    meta = load_meta(slug)

    if not drop_id and not wave:
        meta["build_mode"] = "rush"
        save_meta(slug, meta)
        update_status_md(slug, meta)
        print(f"[RUSH] Build {slug} switched to rush mode. All Drops will auto-spawn.")
        return

    if drop_id:
        if drop_id in meta.get("drops", {}):
            meta["drops"][drop_id]["spawn_mode"] = "auto"
            if meta["drops"][drop_id].get("status") == "ready":
                meta["drops"][drop_id]["status"] = "pending"
            save_meta(slug, meta)
            update_status_md(slug, meta)
            print(f"[RUSH] {drop_id} set to auto-spawn.")
        else:
            print(f"Error: Drop {drop_id} not found in {slug}")
            return

    if wave:
        wave_drops = (meta.get("waves") or {}).get(wave, [])
        if not wave_drops:
            print(f"Error: Wave {wave} not found or empty in {slug}")
            return
        count = 0
        for did in wave_drops:
            if did in meta.get("drops", {}):
                meta["drops"][did]["spawn_mode"] = "auto"
                if meta["drops"][did].get("status") == "ready":
                    meta["drops"][did]["status"] = "pending"
                count += 1
        save_meta(slug, meta)
        update_status_md(slug, meta)
        print(f"[RUSH] Wave {wave}: {count} Drops set to auto-spawn.")


def main():
    parser = argparse.ArgumentParser(description="Pulse Build Orchestration")
    subparsers = parser.add_subparsers(dest="command")
    
    start_parser = subparsers.add_parser("start", help="Begin automated orchestration")
    start_parser.add_argument("slug", help="Build slug")
    
    status_parser = subparsers.add_parser("status", help="Show current build status")
    status_parser.add_argument("slug", help="Build slug")
    
    stop_parser = subparsers.add_parser("stop", help="Gracefully stop orchestration")
    stop_parser.add_argument("slug", help="Build slug")
    
    resume_parser = subparsers.add_parser("resume", help="Resume a stopped build")
    resume_parser.add_argument("slug", help="Build slug")
    
    tick_parser = subparsers.add_parser("tick", help="Run single orchestration cycle (for scheduled tasks)")
    tick_parser.add_argument("slug", help="Build slug")
    
    finalize_parser = subparsers.add_parser("finalize", help="Run post-build finalization (safety, tests, learnings)")
    finalize_parser.add_argument("slug", help="Build slug")

    spawn_one_parser = subparsers.add_parser("spawn-one", help="Internal: spawn one drop via detached worker")
    spawn_one_parser.add_argument("slug", help="Build slug")
    spawn_one_parser.add_argument("drop_id", help="Drop ID")
    spawn_one_parser.add_argument("--model", help="Optional model override")
    
    launch_parser = subparsers.add_parser("launch", help="Print launcher path and paste-prompt contents")
    launch_parser.add_argument("slug", help="Build slug")
    launch_parser.add_argument("drop_id", help="Drop ID")
    
    retry_parser = subparsers.add_parser("retry", help="Reset a failed/bad Drop and re-edit its brief")
    retry_parser.add_argument("slug", help="Build slug")
    retry_parser.add_argument("drop_id", help="Drop ID to retry")
    retry_parser.add_argument("--reason", "-r", help="Why the retry is needed (appended to brief)")
    
    validate_parser = subparsers.add_parser("validate", help="Validate plan completeness before start")
    validate_parser.add_argument("slug", help="Build slug")
    
    rush_parser = subparsers.add_parser("rush", help="Override learning mode to auto-spawn")
    rush_parser.add_argument("slug", help="Build slug")
    rush_parser.add_argument("--drop", help="Auto-spawn specific Drop")
    rush_parser.add_argument("--wave", help="Auto-spawn all Drops in a wave")

    args = parser.parse_args()
    
    if args.command == "start":
        start_build(args.slug)
    elif args.command == "status":
        show_status(args.slug)
    elif args.command == "stop":
        stop_build(args.slug)
    elif args.command == "resume":
        resume_build(args.slug)
    elif args.command == "tick":
        asyncio.run(tick(args.slug))
    elif args.command == "finalize":
        asyncio.run(finalize_build(args.slug))
    elif args.command == "spawn-one":
        raise SystemExit(spawn_one(args.slug, args.drop_id, args.model))
    elif args.command == "launch":
        launcher_path = ensure_launcher(args.slug, args.drop_id)
        print(f"Launcher: {launcher_path}")
        print(launcher_path.read_text())
    elif args.command == "retry":
        retry_drop(args.slug, args.drop_id, args.reason)
    elif args.command == "validate":
        validate_plan(args.slug)
    elif args.command == "rush":
        rush_mode(args.slug, args.drop, args.wave)


if __name__ == "__main__":
    main()
