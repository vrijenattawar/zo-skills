#!/usr/bin/env python3
"""
Bidirectional sync between _TASKS.md and the task database.

Reads:
- Checkbox states (checked = complete)
- Due dates (Due: YYYY-MM-DD or Due: ___)
- Blocked status and reasons

Updates:
- Database with changes from file
- Regenerates file from database

Usage:
    python3 sync_tasks.py           # Full sync (read file, update DB, regenerate)
    python3 sync_tasks.py --read    # Just read file and update DB
    python3 sync_tasks.py --write   # Just regenerate file from DB
"""

import re
import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path

TASKS_FILE = Path("./_TASKS.md")
DB_PATH = Path("./Skills/task-system/data/tasks.db")

DOMAIN_EMOJI = {
    "<YOUR_PRODUCT>": "🧭",
    "zo": "🪽",
    "personal": "🌀",
    "system": "⚙️",
}

EMOJI_TO_DOMAIN = {v: k for k, v in DOMAIN_EMOJI.items()}


def get_db():
    return sqlite3.connect(DB_PATH)


def parse_task_line(line: str) -> dict | None:
    """Parse a task line like: - [ ] #123 🧭 Task title | Due: 2026-01-30"""
    pattern = r"^- \[([ xX])\] #(\d+) ([🧭🪽🌀⚙️]) (.+?)(?:\s*\|\s*Due:\s*(\S+))?$"
    match = re.match(pattern, line.strip())
    if not match:
        return None
    
    checked, task_id, emoji, title, due = match.groups()
    
    due_date = None
    if due and due not in ("___", "—", "-"):
        try:
            due_date = datetime.strptime(due, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    return {
        "id": int(task_id),
        "checked": checked.lower() == "x",
        "domain_emoji": emoji,
        "title": title.strip(),
        "due_date": due_date,
    }


def parse_blocked_line(line: str) -> dict | None:
    """Parse a blocked task line like: - [ ] #123 🧭 Task [ext] Waiting on Bob | Due: ___"""
    pattern = r"^- \[([ xX])\] #(\d+) ([🧭🪽🌀⚙️]) (.+?) \[(ext|int)\] (.+?)(?:\s*\|\s*Due:\s*(\S+))?$"
    match = re.match(pattern, line.strip())
    if not match:
        return None
    
    checked, task_id, emoji, title, blocked_by, reason, due = match.groups()
    
    due_date = None
    if due and due not in ("___", "—", "-"):
        try:
            due_date = datetime.strptime(due, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    return {
        "id": int(task_id),
        "checked": checked.lower() == "x",
        "domain_emoji": emoji,
        "title": title.strip(),
        "blocked_by": "external" if blocked_by == "ext" else "internal",
        "blocked_reason": reason.strip(),
        "due_date": due_date,
    }


def read_tasks_file() -> list[dict]:
    """Read _TASKS.md and extract all task states."""
    if not TASKS_FILE.exists():
        return []
    
    content = TASKS_FILE.read_text()
    tasks = []
    in_blocked_section = False
    
    for line in content.split("\n"):
        if "## 🚧 Blocked" in line:
            in_blocked_section = True
            continue
        elif line.startswith("## ") and in_blocked_section:
            in_blocked_section = False
        
        if in_blocked_section:
            parsed = parse_blocked_line(line)
            if parsed:
                parsed["is_blocked"] = True
                tasks.append(parsed)
        else:
            parsed = parse_task_line(line)
            if parsed:
                parsed["is_blocked"] = False
                tasks.append(parsed)
    
    return tasks


def sync_to_db(tasks: list[dict]):
    """Update database with changes from file."""
    conn = get_db()
    cursor = conn.cursor()
    
    for task in tasks:
        updates = []
        params = []
        
        # Handle completion
        if task["checked"]:
            updates.append("status = 'complete'")
            updates.append("completed_at = ?")
            params.append(datetime.now().isoformat())
        elif task.get("is_blocked"):
            updates.append("status = 'blocked'")
            updates.append("blocked_by = ?")
            updates.append("blocked_reason = ?")
            params.extend([task.get("blocked_by"), task.get("blocked_reason")])
        else:
            # Only reset to pending if currently blocked (don't override in_progress)
            cursor.execute("SELECT status FROM tasks WHERE id = ?", (task["id"],))
            row = cursor.fetchone()
            if row and row[0] == "blocked":
                updates.append("status = 'pending'")
                updates.append("blocked_by = NULL")
                updates.append("blocked_reason = NULL")
        
        # Handle due date
        if task["due_date"]:
            updates.append("due_at = ?")
            params.append(task["due_date"].isoformat())
        
        if updates:
            params.append(task["id"])
            query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
    
    conn.commit()
    conn.close()
    print(f"✓ Synced {len(tasks)} tasks to database")


def get_time_bucket(due_date, today) -> str:
    """Determine which time bucket a due date falls into."""
    if due_date is None:
        return "uncategorized"
    
    if isinstance(due_date, str):
        due_date = datetime.fromisoformat(due_date).date()
    
    if due_date <= today:
        return "today"
    
    # This week = through Sunday of current week
    days_until_sunday = 6 - today.weekday()  # Monday=0, Sunday=6
    end_of_week = today + timedelta(days=days_until_sunday)
    if due_date <= end_of_week:
        return "this_week"
    
    # This month
    if due_date.month == today.month and due_date.year == today.year:
        return "this_month"
    
    return "later"


def generate_tasks_file():
    """Regenerate _TASKS.md from database."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    today = datetime.now().date()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M ET")
    
    # Get all active tasks
    cursor.execute("""
        SELECT t.id, t.title, d.name as domain, t.priority_bucket, t.status, 
               t.due_at, t.blocked_by, t.blocked_reason
        FROM tasks t 
        LEFT JOIN domains d ON t.domain_id = d.id 
        WHERE t.status IN ('pending', 'in_progress', 'blocked')
        ORDER BY t.due_at NULLS LAST, t.priority_bucket, t.id
    """)
    active_tasks = cursor.fetchall()
    
    # Get recently completed
    cursor.execute("""
        SELECT t.id, t.title, d.name as domain, t.completed_at
        FROM tasks t 
        LEFT JOIN domains d ON t.domain_id = d.id 
        WHERE t.status = 'complete'
        ORDER BY t.completed_at DESC
        LIMIT 10
    """)
    completed_tasks = cursor.fetchall()
    conn.close()
    
    # Organize by bucket
    buckets = {
        "today": [],
        "this_week": [],
        "this_month": [],
        "later": [],
        "blocked": [],
        "uncategorized": {"urgent": [], "external": [], "strategic": [], "normal": []},
    }
    
    for task in active_tasks:
        domain = (task["domain"] or "personal").lower()
        emoji = DOMAIN_EMOJI.get(domain, "🌀")
        due_str = task["due_at"][:10] if task["due_at"] else "___"
        
        if task["status"] == "blocked":
            blocked_type = "ext" if task["blocked_by"] == "external" else "int"
            reason = task["blocked_reason"] or "No reason specified"
            line = f"- [ ] #{task['id']} {emoji} {task['title']} [{blocked_type}] {reason} | Due: {due_str}"
            buckets["blocked"].append(line)
        else:
            line = f"- [ ] #{task['id']} {emoji} {task['title']} | Due: {due_str}"
            bucket = get_time_bucket(task["due_at"][:10] if task["due_at"] else None, today)
            
            if bucket == "uncategorized":
                priority = task["priority_bucket"] or "normal"
                buckets["uncategorized"][priority].append(line)
            else:
                buckets[bucket].append(line)
    
    # Format completed tasks
    completed_lines = []
    for task in completed_tasks:
        domain = (task["domain"] or "personal").lower()
        emoji = DOMAIN_EMOJI.get(domain, "🌀")
        date_str = task["completed_at"][:10] if task["completed_at"] else "?"
        # Format date nicely
        try:
            d = datetime.fromisoformat(date_str)
            date_display = d.strftime("%b %d")
        except:
            date_display = date_str
        completed_lines.append(f"- [x] #{task['id']} {emoji} {task['title']} *({date_display})*")
    
    # Calculate week range
    days_until_sunday = 6 - today.weekday()
    end_of_week = today + timedelta(days=days_until_sunday)
    week_range = f"{today.strftime('%b %d')} – {end_of_week.strftime('%b %d')}"
    
    # Build file content
    content = f"""# 📋 Tasks

Last synced: {now_str}

**Legend:** 🧭 <YOUR_PRODUCT> | 🪽 Zo | 🌀 Personal

---

## 🔴 Due Today ({today.strftime('%a %b %d')})

{chr(10).join(buckets['today']) if buckets['today'] else '*No tasks due today*'}

---

## 📅 Due This Week ({week_range})

{chr(10).join(buckets['this_week']) if buckets['this_week'] else '*No tasks due this week*'}

---

## 📆 Due This Month ({today.strftime('%B')})

{chr(10).join(buckets['this_month']) if buckets['this_month'] else '*No tasks due this month*'}

---

## 🗓️ Due Later

{chr(10).join(buckets['later']) if buckets['later'] else '*No tasks with future due dates*'}

---

## 🚧 Blocked

*Format: `[ext]` = waiting on someone else | `[int]` = waiting on yourself*

{chr(10).join(buckets['blocked']) if buckets['blocked'] else '*No blocked tasks*'}

---

## 📥 Uncategorized (No Due Date)

### Urgent
{chr(10).join(buckets['uncategorized']['urgent']) if buckets['uncategorized']['urgent'] else '*None*'}

### External (Someone Waiting)
{chr(10).join(buckets['uncategorized']['external']) if buckets['uncategorized']['external'] else '*None*'}

### Strategic
{chr(10).join(buckets['uncategorized']['strategic']) if buckets['uncategorized']['strategic'] else '*None*'}

### Normal
{chr(10).join(buckets['uncategorized']['normal']) if buckets['uncategorized']['normal'] else '*None*'}

---

## ✅ Recently Completed

{chr(10).join(completed_lines) if completed_lines else '*No recent completions*'}

---

## ⚡ Quick Capture

*Jot raw ideas here — they'll get staged for proper entry*

- 

---

**To sync:** `python3 Skills/task-system/scripts/sync_tasks.py`
"""
    
    TASKS_FILE.write_text(content)
    print(f"✓ Regenerated {TASKS_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Sync _TASKS.md with task database")
    parser.add_argument("--read", action="store_true", help="Only read file and update DB")
    parser.add_argument("--write", action="store_true", help="Only regenerate file from DB")
    args = parser.parse_args()
    
    if args.read:
        tasks = read_tasks_file()
        sync_to_db(tasks)
    elif args.write:
        generate_tasks_file()
    else:
        # Full sync: read file, update DB, then regenerate
        tasks = read_tasks_file()
        if tasks:
            sync_to_db(tasks)
        generate_tasks_file()


if __name__ == "__main__":
    main()
