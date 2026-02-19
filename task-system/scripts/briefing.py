#!/usr/bin/env python3
"""
Briefing CLI - Morning & Evening Check-ins

Provides daily task briefings, accountability reports, and staged task review.
Pure data + formatting - no AI calls (that's for the scheduled agent layer).

Usage:
    briefing.py morning [--capacity N] [--format text|json]
    briefing.py evening [--format text|json]
    briefing.py staged [--format text|json]
"""

import argparse
import sys
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import re

# Add parent directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from db import (
    list_tasks,
    get_staged_tasks,
    calculate_latency_stats,
    get_completion_rate,
    complete_task,
    get_task
)

# Constants
PRIORITY_BUCKETS = ["strategic", "external", "urgent", "normal"]
PRIORITY_EMOJIS = {
    "strategic": "🔴",
    "external": "🟠",
    "urgent": "🟡",
    "normal": "⚪"
}
DEFAULT_CAPACITY = 6

# Default report output directory
REPORTS_DIR = Path("./N5/reports/daily/tasks")


def get_daily_report_path(for_date: date = None) -> Path:
    """Get the path for today's daily task report."""
    if for_date is None:
        for_date = date.today()
    return REPORTS_DIR / f"{for_date.strftime('%Y-%m-%d')}.md"


def write_report_section(
    content: str,
    report_path: Path,
    section_header: str,
    append: bool = False
) -> None:
    """
    Write or append a section to a daily report file.
    """
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%I:%M %p")
    section = f"\n\n## {section_header} ({timestamp})\n\n{content}\n"
    
    if append and report_path.exists():
        with open(report_path, 'a') as f:
            f.write(section)
    else:
        # Create new file with frontmatter
        today = date.today()
        header = f"""---
created: {today.strftime('%Y-%m-%d')}
type: daily-task-report
---

# Daily Task Report: {today.strftime('%Y-%m-%d')} ({today.strftime('%A')})
"""
        with open(report_path, 'w') as f:
            f.write(header)
            f.write(section)


def get_todays_tasks(capacity: int = DEFAULT_CAPACITY, days_ahead: int = 1) -> List[Dict[str, Any]]:
    """
    Get today's tasks with priority ordering.

    Args:
        capacity: Maximum number of tasks to return
        days_ahead: Include tasks due within this many days

    Returns:
        List of task dictionaries
    """
    # Get pending/in-progress/blocked tasks due today or soon
    all_tasks = list_tasks(
        status=None,  # All active statuses
        days_ahead=days_ahead
    )

    # Filter out completed tasks
    active_tasks = [t for t in all_tasks if t['status'] not in ['complete', 'abandoned']]

    # Apply capacity limit
    return active_tasks[:capacity]


def get_day_results(for_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Get completed vs incomplete tasks for a specific date.

    Args:
        for_date: Date to analyze (defaults to today)

    Returns:
        Dict with completed_tasks, incomplete_tasks, total_planned, total_completed
    """
    if for_date is None:
        for_date = date.today()

    # Get all tasks due on or before this date
    date_str = for_date.strftime("%Y-%m-%d")
    all_due_tasks = list_tasks(due_date=date_str)

    # Separate into completed and incomplete
    completed = [t for t in all_due_tasks if t['status'] == 'complete']
    incomplete = [t for t in all_due_tasks if t['status'] != 'complete']

    return {
        "date": date_str,
        "completed_tasks": completed,
        "incomplete_tasks": incomplete,
        "total_planned": len(all_due_tasks),
        "total_completed": len(completed)
    }


def calculate_latency_warnings(threshold_days: int = 3) -> List[Dict[str, Any]]:
    """
    Find tasks that are getting stale (overdue for threshold_days).

    Args:
        threshold_days: Days overdue before warning

    Returns:
        List of tasks with latency warnings
    """
    # Get all active tasks
    all_tasks = list_tasks(status=None, days_ahead=0)

    warnings = []
    today = date.today()

    for task in all_tasks:
        if task['due_at'] and task['status'] not in ['complete', 'abandoned']:
            try:
                due_date = datetime.fromisoformat(task['due_at']).date()
                if due_date < today:
                    days_overdue = (today - due_date).days
                    if days_overdue >= threshold_days:
                        warnings.append({
                            **task,
                            "days_overdue": days_overdue
                        })
            except (ValueError, TypeError):
                continue

    return warnings


def format_task_line(task: Dict[str, Any], show_index: bool = False, index: int = 0) -> str:
    """
    Format a task line consistently across briefings.

    Args:
        task: Task dictionary
        show_index: Whether to show index number
        index: Index number if show_index is True

    Returns:
        Formatted task line
    """
    title = task['title']

    # Add time estimate if available
    time_str = ""
    if task.get('estimated_minutes'):
        time_str = f" ({task['estimated_minutes']} min)"
    elif task.get('actual_minutes'):
        time_str = f" ({task['actual_minutes']} min)"

    # Build line
    prefix = f"{index}. " if show_index else ""
    return f"{prefix}{title}{time_str}"


def format_task_line_with_status(task: Dict[str, Any], index: int) -> str:
    """
    Format a task line with completion status.

    Args:
        task: Task dictionary
        index: Index number

    Returns:
        Formatted task line with status indicator
    """
    title = task['title']

    # Add time spent
    time_str = ""
    if task.get('actual_minutes'):
        time_str = f" ({task['actual_minutes']} min)"

    # Status note for incomplete tasks
    status_note = ""
    if task['status'] != 'complete':
        if task['status'] == 'in_progress':
            status_note = " — Started, not finished"
        elif task['status'] == 'blocked':
            status_note = " — Blocked"
        else:
            status_note = " — Not started"

    return f"• {title}{time_str}{status_note}"


def generate_morning_briefing(capacity: int = DEFAULT_CAPACITY, format: str = "text") -> str:
    """
    Generate morning briefing with checkboxes for daily tracking.

    Args:
        capacity: Number of tasks to show
        format: 'text' or 'json'

    Returns:
        Formatted briefing with checkboxes
    """
    tasks = get_todays_tasks(capacity)
    today = date.today()

    if format == "json":
        return json.dumps({
            "date": today.strftime("%Y-%m-%d"),
            "day_name": today.strftime("%A"),
            "capacity": capacity,
            "tasks": tasks
        }, indent=2)

    # Build text briefing with checkboxes
    lines = [
        f"## Today's Tasks",
        "",
        f"**Capacity:** {len(tasks)} tasks",
        ""
    ]

    if not tasks:
        lines.append("No tasks scheduled for today.")
        lines.append("")
        lines.append("Add tasks via:")
        lines.append("- Text: 'add task: Description'")
        lines.append("- Or add directly to this file")
        return "\n".join(lines)

    # Group by priority bucket
    by_bucket = {bucket: [] for bucket in PRIORITY_BUCKETS}
    for task in tasks:
        bucket = task.get('priority_bucket', 'normal')
        if bucket not in by_bucket:
            bucket = 'normal'
        by_bucket[bucket].append(task)

    # Show tasks by priority order with checkboxes
    for bucket in PRIORITY_BUCKETS:
        bucket_tasks = by_bucket[bucket]
        if not bucket_tasks:
            continue

        emoji = PRIORITY_EMOJIS.get(bucket, "⚪")
        lines.append(f"### {emoji} {bucket.upper()}")
        lines.append("")

        for task in bucket_tasks:
            task_id = task['id']
            title = task['title']
            
            # Time estimate
            time_str = ""
            if task.get('estimated_minutes'):
                time_str = f" ({task['estimated_minutes']}min)"
            
            # Domain/Project context
            context_parts = []
            if task.get('domain_name'):
                context_parts.append(task['domain_name'])
            if task.get('project_name'):
                context_parts.append(task['project_name'])
            context_str = f" — {'/'.join(context_parts)}" if context_parts else ""
            
            # Checkbox format: - [ ] #ID **Title** (time) — context
            lines.append(f"- [ ] #{task_id} **{title}**{time_str}{context_str}")

        lines.append("")

    lines.append("---")
    lines.append("**Check boxes as you complete tasks.** Evening sync will update the system.")
    lines.append("")
    lines.append("Quick actions (text me):")
    lines.append("- 'add task: Description' — add new task")
    lines.append("- 'defer #ID to tomorrow' — push task")
    lines.append("- 'block #ID: reason' — mark blocked")

    return "\n".join(lines)


def parse_daily_report(report_path: Path) -> Dict[int, bool]:
    """
    Parse a daily report file to extract task completion state from checkboxes.
    
    Args:
        report_path: Path to the daily report markdown file
        
    Returns:
        Dict mapping task_id (int) to checked state (bool)
    """
    if not report_path.exists():
        return {}
    
    content = report_path.read_text()
    
    # Match checkbox patterns: - [x] #123 or - [ ] #123
    # Captures: (checked_char, task_id)
    pattern = r'- \[([ xX])\] #(\d+)'
    
    results = {}
    for match in re.finditer(pattern, content):
        checked_char = match.group(1)
        task_id = int(match.group(2))
        is_checked = checked_char.lower() == 'x'
        results[task_id] = is_checked
    
    return results


def sync_completions_from_report(report_path: Path = None, for_date: date = None) -> Dict[str, Any]:
    """
    Sync task completions from daily report checkboxes to database.
    
    Args:
        report_path: Path to report file (auto-detected if not provided)
        for_date: Date of report (defaults to today)
        
    Returns:
        Dict with sync results: {synced: int, already_complete: int, errors: list}
    """
    if for_date is None:
        for_date = date.today()
    
    if report_path is None:
        report_path = get_daily_report_path(for_date)
    
    if not report_path.exists():
        return {"synced": 0, "already_complete": 0, "errors": ["Report file not found"]}
    
    # Parse checkboxes
    checkbox_state = parse_daily_report(report_path)
    
    synced = 0
    already_complete = 0
    errors = []
    
    for task_id, is_checked in checkbox_state.items():
        if is_checked:
            try:
                # Check if already complete
                task = get_task(task_id)
                if task and task['status'] == 'complete':
                    already_complete += 1
                elif task:
                    # Mark as complete
                    complete_task(task_id)
                    synced += 1
                else:
                    errors.append(f"Task #{task_id} not found")
            except Exception as e:
                errors.append(f"Error syncing #{task_id}: {e}")
    
    return {
        "synced": synced,
        "already_complete": already_complete,
        "errors": errors
    }


def generate_evening_accountability(for_date: Optional[date] = None, format: str = "text", auto_sync: bool = True) -> str:
    """
    Generate evening accountability report.

    Args:
        for_date: Date to analyze (defaults to today)
        format: 'text' or 'json'
        auto_sync: If True, sync completions from daily report first

    Returns:
        Formatted accountability report
    """
    if for_date is None:
        for_date = date.today()

    # Auto-sync completions from checkboxes before reporting
    sync_result = None
    if auto_sync:
        sync_result = sync_completions_from_report(for_date=for_date)

    results = get_day_results(for_date)
    total = results['total_planned']
    completed = results['total_completed']
    completion_rate = round((completed / total * 100) if total > 0 else 0)

    if format == "json":
        return json.dumps({
            "date": results["date"],
            "total_planned": total,
            "total_completed": completed,
            "completion_rate": completion_rate,
            "completed_tasks": results["completed_tasks"],
            "incomplete_tasks": results["incomplete_tasks"],
            "sync_result": sync_result
        }, indent=2)

    # Build text report
    lines = []
    
    # Show sync result if any tasks were synced
    if sync_result and sync_result["synced"] > 0:
        lines.append(f"*Synced {sync_result['synced']} completed tasks from checkboxes*")
        lines.append("")

    lines.append("## Evening Check-in")
    lines.append("")

    if total > 0:
        # Score with visual bar
        filled = int(completion_rate / 10)
        bar = "█" * filled + "░" * (10 - filled)
        lines.append(f"**Score:** {completed}/{total} ({completion_rate}%) {bar}")
        lines.append("")
    else:
        lines.append("No tasks were planned for today.")
        lines.append("")
        return "\n".join(lines)

    # Completed tasks
    if results["completed_tasks"]:
        lines.append("### ✅ Completed")
        lines.append("")
        for task in results["completed_tasks"]:
            time_str = f" ({task['actual_minutes']}min)" if task.get('actual_minutes') else ""
            lines.append(f"- [x] #{task['id']} **{task['title']}**{time_str}")
        lines.append("")

    # Incomplete tasks
    if results["incomplete_tasks"]:
        lines.append("### ⬜ Incomplete")
        lines.append("")
        for task in results["incomplete_tasks"]:
            status_note = ""
            if task['status'] == 'in_progress':
                status_note = " *(in progress)*"
            elif task['status'] == 'blocked':
                status_note = " *(blocked)*"
            lines.append(f"- [ ] #{task['id']} **{task['title']}**{status_note}")
        lines.append("")
        lines.append("*What happened with these?*")
        lines.append("")

    # Latency warnings
    warnings = calculate_latency_warnings(threshold_days=3)
    if warnings:
        lines.append("### ⚠️ Latency Warnings")
        lines.append("")
        for task in warnings:
            lines.append(f"- #{task['id']} **{task['title']}** — {task['days_overdue']} days overdue")
        lines.append("")

    return "\n".join(lines)


def generate_staged_review(format: str = "text") -> str:
    """
    Generate staged task review for user approval.

    Args:
        format: 'text' or 'json'

    Returns:
        Formatted staged task review
    """
    staged = get_staged_tasks(status='pending_review')

    if format == "json":
        return json.dumps({
            "total": len(staged),
            "tasks": staged
        }, indent=2)

    if not staged:
        return "No staged tasks for review."

    # Group by source
    by_source = {}
    for task in staged:
        source = f"{task['source_type']}:{task['source_id']}"
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(task)

    # Build text review
    lines = [
        f"STAGED TASKS FOR REVIEW ({len(staged)} items)",
        ""
    ]

    task_num = 1
    for source, tasks in by_source.items():
        source_type, source_id = source.split(":", 1)

        # Format source label
        if source_type == "meeting":
            source_label = f"From: {source_id.replace('_', ' ')} meeting"
        elif source_type == "email":
            source_label = f"From email thread"
        elif source_type == "conversation":
            source_label = f"From conversation {source_id[:8]}..."
        else:
            source_label = f"From: {source_type}"

        lines.append(source_label)

        for task in tasks:
            priority = task.get('suggested_priority', 'normal')
            est_time = task.get('estimated_minutes', '?')

            lines.append(f"{task_num}. [PROMOTE?] \"{task['title']}\"")
            if task.get('description'):
                desc = task['description']
                if len(desc) > 80:
                    desc = desc[:77] + "..."
                lines.append(f"   {desc}")
            lines.append(f"   Priority: {priority} | Est: {est_time} min")
            task_num += 1

        lines.append("")

    lines.append("---")
    lines.append("Reply: 'promote 1', 'dismiss 2 reason', 'promote all'")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Briefing CLI - Morning & Evening Check-ins"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Morning briefing
    morning_parser = subparsers.add_parser("morning", help="Morning briefing")
    morning_parser.add_argument(
        "--capacity",
        type=int,
        default=DEFAULT_CAPACITY,
        help=f"Number of tasks to show (default: {DEFAULT_CAPACITY})"
    )
    morning_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    morning_parser.add_argument(
        "--output",
        type=Path,
        help="Write to file instead of stdout"
    )
    morning_parser.add_argument(
        "--save",
        action="store_true",
        help="Save to default daily report location"
    )

    # Evening accountability
    evening_parser = subparsers.add_parser("evening", help="Evening accountability")
    evening_parser.add_argument(
        "--review-day",
        help="Review specific day (YYYY-MM-DD, defaults to today)"
    )
    evening_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    evening_parser.add_argument(
        "--output",
        type=Path,
        help="Write to file (appends to existing daily report)"
    )
    evening_parser.add_argument(
        "--save",
        action="store_true",
        help="Append to default daily report location (N5/reports/daily/tasks/)"
    )
    evening_parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip auto-sync from checkboxes (just report current state)"
    )

    # Staged review
    staged_parser = subparsers.add_parser("staged", help="Staged task review")
    staged_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "morning":
            output = generate_morning_briefing(capacity=args.capacity, format=args.format)
            
            if args.save or args.output:
                report_path = args.output if args.output else get_daily_report_path()
                write_report_section(output, report_path, "Morning Briefing", append=False)
                print(f"✓ Morning briefing saved to: {report_path}")
            else:
                print(output)
                
        elif args.command == "evening":
            review_date = None
            if args.review_day:
                try:
                    review_date = datetime.strptime(args.review_day, "%Y-%m-%d").date()
                except ValueError:
                    print(f"Error: Invalid date format '{args.review_day}'. Use YYYY-MM-DD.")
                    sys.exit(1)
            auto_sync = not getattr(args, 'no_sync', False)
            output = generate_evening_accountability(for_date=review_date, format=args.format, auto_sync=auto_sync)
            
            if args.save or args.output:
                report_path = args.output if args.output else get_daily_report_path(review_date)
                write_report_section(output, report_path, "Evening Accountability", append=True)
                print(f"✓ Evening accountability appended to: {report_path}")
            else:
                print(output)
        elif args.command == "staged":
            output = generate_staged_review(format=args.format)
        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
