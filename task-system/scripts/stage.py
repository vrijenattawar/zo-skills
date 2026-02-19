#!/usr/bin/env python3
"""
Stage CLI - staged task management.
Provides list, promote, dismiss, add, and review operations for the staging area.

Staged tasks are tasks extracted from meetings, emails, or conversations
that need human review before becoming official tasks.
"""

import argparse
import sys
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from db import (
    stage_task,
    get_staged_tasks,
    get_staged_task_by_id,
    promote_staged_task,
    dismiss_staged_task,
    get_or_create_domain,
    get_or_create_project,
)


def cmd_list(args):
    """List staged tasks."""
    tasks = get_staged_tasks(status=args.status or 'pending_review')
    
    # Filter by source if specified
    if args.source:
        tasks = [t for t in tasks if t.get('source_type') == args.source]
    
    # Apply limit
    tasks = tasks[:args.limit]
    
    if args.format == "json":
        print(json.dumps(tasks, indent=2, default=str))
        return
    
    if not tasks:
        print("No staged tasks found.")
        return
    
    print(f"Staged tasks ({len(tasks)}):\n")
    
    for task in tasks:
        priority = task.get('suggested_priority', 'normal')
        priority_icon = {
            'strategic': '🔴',
            'external': '🟠', 
            'urgent': '🟡',
            'normal': '⚪'
        }.get(priority, '⚪')
        
        source_str = f"[{task['source_type']}]" if task.get('source_type') else ""
        est_str = f"({task['estimated_minutes']}min)" if task.get('estimated_minutes') else ""
        
        print(f"  {priority_icon} #{task['id']} {task['title']} {est_str} {source_str}")
        
        if task.get('description'):
            desc = task['description']
            if len(desc) > 60:
                desc = desc[:57] + "..."
            print(f"      {desc}")
        
        if task.get('first_step'):
            print(f"      → First step: {task['first_step']}")
        
        print()


def cmd_add(args):
    """Add a task to the staging area."""
    staged_id = stage_task(
        title=args.title,
        source_type=args.source_type or 'manual',
        source_id=args.source_id or '',
        source_context=args.first_step,  # Use first_step as context
        description=args.description,
        suggested_priority=args.priority or 'normal',
        suggested_domain=args.domain,
    )
    
    print(f"✓ Staged task #{staged_id}: {args.title}")
    print("  Run 'stage.py review' to promote or dismiss")


def cmd_promote(args):
    """Promote a staged task to a real task."""
    staged = get_staged_task_by_id(args.staged_id)
    if not staged:
        print(f"Error: Staged task #{args.staged_id} not found.")
        sys.exit(1)
    
    # Get domain (use override or suggested or default)
    domain_name = args.domain or staged.get('suggested_domain') or 'Inbox'
    domain_id = get_or_create_domain(domain_name)
    
    # Get project if specified
    project_id = None
    if args.project:
        project_id = get_or_create_project(args.project, domain_id)
    
    # Parse due date if provided
    due_at = None
    if args.due:
        try:
            due_at = datetime.strptime(args.due, "%Y-%m-%d").isoformat()
        except ValueError:
            print(f"Error: Invalid date format '{args.due}'. Use YYYY-MM-DD.")
            sys.exit(1)
    
    # Build task data
    task_data = {
        'title': staged['title'],
        'description': staged.get('description'),
        'domain_id': domain_id,
        'project_id': project_id,
        'priority_bucket': args.priority or staged.get('suggested_priority') or 'normal',
        'estimated_minutes': staged.get('estimated_minutes'),
        'due_at': due_at,
        'source_type': staged.get('source_type'),
        'source_id': staged.get('source_id'),
    }
    
    # Remove None values
    task_data = {k: v for k, v in task_data.items() if v is not None}
    
    task_id = promote_staged_task(args.staged_id, task_data)
    
    if task_id:
        print(f"✓ Promoted staged #{args.staged_id} → task #{task_id}: {staged['title']}")
    else:
        print(f"Error: Failed to promote staged task #{args.staged_id}")
        sys.exit(1)


def cmd_dismiss(args):
    """Dismiss a staged task."""
    staged = get_staged_task_by_id(args.staged_id)
    if not staged:
        print(f"Error: Staged task #{args.staged_id} not found.")
        sys.exit(1)
    
    success = dismiss_staged_task(args.staged_id, reason=args.reason)
    
    if success:
        print(f"✓ Dismissed staged #{args.staged_id}: {staged['title']}")
        if args.reason:
            print(f"  Reason: {args.reason}")
    else:
        print(f"Error: Failed to dismiss staged task #{args.staged_id}")
        sys.exit(1)


def cmd_review(args):
    """Interactive review of pending staged tasks."""
    tasks = get_staged_tasks(status='pending_review')[:args.limit]
    
    if not tasks:
        print("No staged tasks pending review.")
        return
    
    print(f"STAGED TASKS FOR REVIEW ({len(tasks)} items)\n")
    print("-" * 60)
    
    for i, task in enumerate(tasks, 1):
        priority = task.get('suggested_priority', 'normal')
        priority_icon = {
            'strategic': '🔴',
            'external': '🟠',
            'urgent': '🟡', 
            'normal': '⚪'
        }.get(priority, '⚪')
        
        source_str = f"[from: {task['source_type']}]" if task.get('source_type') else ""
        est_str = f"({task['estimated_minutes']}min)" if task.get('estimated_minutes') else ""
        
        print(f"\n{i}. {priority_icon} #{task['id']} {task['title']} {est_str}")
        print(f"   {source_str}")
        
        if task.get('description'):
            desc = task['description']
            if len(desc) > 80:
                desc = desc[:77] + "..."
            print(f"   {desc}")
        
        if task.get('first_step'):
            print(f"   → First step: {task['first_step']}")
        
        if task.get('suggested_domain'):
            print(f"   Suggested domain: {task['suggested_domain']}")
    
    print("\n" + "-" * 60)
    print("Commands:")
    print("  promote <id>              — Promote to real task")
    print("  promote <id> --due DATE   — Promote with due date")
    print("  dismiss <id> [reason]     — Dismiss task")
    print("  promote-all               — Promote all pending")
    print()


def cmd_promote_all(args):
    """Promote all pending staged tasks."""
    tasks = get_staged_tasks(status='pending_review')
    
    if not tasks:
        print("No staged tasks to promote.")
        return
    
    promoted = 0
    failed = 0
    
    for task in tasks:
        domain_name = task.get('suggested_domain') or 'Inbox'
        domain_id = get_or_create_domain(domain_name)
        
        task_data = {
            'title': task['title'],
            'description': task.get('description'),
            'domain_id': domain_id,
            'priority_bucket': task.get('suggested_priority') or 'normal',
            'estimated_minutes': task.get('estimated_minutes'),
            'source_type': task.get('source_type'),
            'source_id': task.get('source_id'),
        }
        task_data = {k: v for k, v in task_data.items() if v is not None}
        
        task_id = promote_staged_task(task['id'], task_data)
        if task_id:
            promoted += 1
            print(f"✓ #{task['id']} → task #{task_id}: {task['title']}")
        else:
            failed += 1
            print(f"✗ Failed: #{task['id']} {task['title']}")
    
    print(f"\nPromoted: {promoted}, Failed: {failed}")


def main():
    parser = argparse.ArgumentParser(
        description="Stage CLI - Staged task management"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List staged tasks
    list_parser = subparsers.add_parser("list", help="List staged tasks")
    list_parser.add_argument("--status", choices=["pending_review", "promoted", "dismissed"], help="Filter by status")
    list_parser.add_argument("--source", help="Filter by source_type")
    list_parser.add_argument("--limit", type=int, default=20, help="Limit results")
    list_parser.add_argument("--format", "-f", choices=["text", "json"], default="text", help="Output format")

    # Add to staging
    add_parser = subparsers.add_parser("add", help="Add task to staging area")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("--description", "-d", help="Task description")
    add_parser.add_argument("--first-step", help="Immediate next action")
    add_parser.add_argument("--domain", help="Suggested domain")
    add_parser.add_argument("--priority", "-p", choices=["strategic", "external", "urgent", "normal"], help="Suggested priority")
    add_parser.add_argument("--estimate", "-e", type=int, help="Estimated minutes")
    add_parser.add_argument("--source-type", help="Source type (meeting, email, conversation)")
    add_parser.add_argument("--source-id", help="Source identifier")

    # Promote staged task
    promote_parser = subparsers.add_parser("promote", help="Promote staged task to real task")
    promote_parser.add_argument("staged_id", type=int, help="Staged task ID")
    promote_parser.add_argument("--domain", help="Override domain")
    promote_parser.add_argument("--project", help="Override project")
    promote_parser.add_argument("--priority", choices=["strategic", "external", "urgent", "normal"], help="Override priority")
    promote_parser.add_argument("--due", help="Set due date (YYYY-MM-DD)")

    # Dismiss staged task
    dismiss_parser = subparsers.add_parser("dismiss", help="Dismiss staged task")
    dismiss_parser.add_argument("staged_id", type=int, help="Staged task ID")
    dismiss_parser.add_argument("--reason", "-r", help="Reason for dismissal")

    # Review staged tasks (batch mode)
    review_parser = subparsers.add_parser("review", help="Review pending staged tasks")
    review_parser.add_argument("--limit", type=int, default=10, help="Max tasks to review")

    # Promote all
    promote_all_parser = subparsers.add_parser("promote-all", help="Promote all pending staged tasks")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to command handler
    handlers = {
        'list': cmd_list,
        'add': cmd_add,
        'promote': cmd_promote,
        'dismiss': cmd_dismiss,
        'review': cmd_review,
        'promote-all': cmd_promote_all,
    }
    
    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
