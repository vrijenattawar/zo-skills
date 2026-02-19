#!/usr/bin/env python3
"""
Task system CLI - main entry point.
Provides add, list, complete, defer, search operations.
"""

import argparse
import sys
import json
from datetime import datetime, date
from pathlib import Path

# Add parent directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from db import (
    create_task,
    get_task,
    list_tasks,
    update_task,
    complete_task,
    get_or_create_domain,
    get_or_create_project,
    tag_action_conversation,
)


def cmd_add(args):
    """Add a new task."""
    # Always need a domain - default to "Inbox" if not specified
    domain_name = args.domain or "Inbox"
    domain_id = get_or_create_domain(domain_name)
    
    project_id = None
    if args.project:
        project_id = get_or_create_project(args.project, domain_id)
    
    # Parse due date
    due_at = None
    if args.due:
        try:
            due_at = datetime.strptime(args.due, "%Y-%m-%d").isoformat()
        except ValueError:
            print(f"Error: Invalid date format '{args.due}'. Use YYYY-MM-DD.")
            sys.exit(1)
    
    # Build kwargs - only include non-None values
    kwargs = {
        'title': args.title,
        'domain_id': domain_id,
        'priority_bucket': args.priority,
    }
    
    if args.description:
        kwargs['description'] = args.description
    if project_id:
        kwargs['project_id'] = project_id
    if due_at:
        kwargs['due_at'] = due_at
    if args.estimate:
        kwargs['estimated_minutes'] = args.estimate
    if args.source_type:
        kwargs['source_type'] = args.source_type
    if args.source_id:
        kwargs['source_id'] = args.source_id
    
    # Create the task
    task_id = create_task(**kwargs)
    
    print(f"✓ Created task #{task_id}: {args.title}")
    return task_id


def cmd_list(args):
    """List tasks."""
    tasks = list_tasks(
        status=args.status,
        priority_bucket=args.priority,
        domain=args.domain,
        project=args.project,
    )
    # Apply limit manually since list_tasks doesn't support it
    if args.limit:
        tasks = tasks[:args.limit]
    
    if args.format == "json":
        print(json.dumps(tasks, indent=2, default=str))
        return
    
    if not tasks:
        print("No tasks found.")
        return
    
    # Group by status for readability
    for task in tasks:
        status_icon = {
            'pending': '⬜',
            'in_progress': '🔄',
            'blocked': '🚫',
            'complete': '✅',
            'abandoned': '❌'
        }.get(task['status'], '?')
        
        priority_icon = {
            'strategic': '🔴',
            'external': '🟠',
            'urgent': '🟡',
            'normal': '⚪'
        }.get(task['priority_bucket'], '⚪')
        
        domain_str = f" [{task['domain_name']}]" if task.get('domain_name') else ""
        due_str = f" (due: {task['due_at'][:10]})" if task.get('due_at') else ""
        
        print(f"{status_icon} #{task['id']} {priority_icon} {task['title']}{domain_str}{due_str}")


def cmd_complete(args):
    """Mark task as complete."""
    task = get_task(args.task_id)
    if not task:
        print(f"Error: Task #{args.task_id} not found.")
        sys.exit(1)
    
    success = complete_task(args.task_id, actual_minutes=args.actual)
    if success:
        print(f"✓ Completed task #{args.task_id}: {task['title']}")
    else:
        print(f"Error: Failed to complete task #{args.task_id}")
        sys.exit(1)


def cmd_update(args):
    """Update task."""
    task = get_task(args.task_id)
    if not task:
        print(f"Error: Task #{args.task_id} not found.")
        sys.exit(1)
    
    updates = {}
    if args.status:
        updates['status'] = args.status
    if args.description:
        updates['description'] = args.description
    if args.priority:
        updates['priority_bucket'] = args.priority
    if args.due:
        try:
            updates['due_at'] = datetime.strptime(args.due, "%Y-%m-%d").isoformat()
        except ValueError:
            print(f"Error: Invalid date format '{args.due}'. Use YYYY-MM-DD.")
            sys.exit(1)
    
    if not updates:
        print("No updates specified.")
        return
    
    success = update_task(args.task_id, **updates)
    if success:
        print(f"✓ Updated task #{args.task_id}")
    else:
        print(f"Error: Failed to update task #{args.task_id}")
        sys.exit(1)


def cmd_tag_conversation(args):
    """Tag a conversation as working on a task."""
    task = get_task(args.task_id)
    if not task:
        print(f"Error: Task #{args.task_id} not found.")
        sys.exit(1)
    
    success = tag_action_conversation(
        convo_id=args.convo_id,
        task_id=args.task_id,
        method=args.method or 'manual'
    )
    
    if success:
        print(f"✓ Tagged conversation {args.convo_id} → task #{args.task_id}")
    else:
        print(f"Error: Failed to tag conversation")
        sys.exit(1)


def cmd_defer(args):
    """Defer a task."""
    task = get_task(args.task_id)
    if not task:
        print(f"Error: Task #{args.task_id} not found.")
        sys.exit(1)
    
    updates = {}
    if args.due:
        try:
            updates['due_at'] = datetime.strptime(args.due, "%Y-%m-%d").isoformat()
        except ValueError:
            print(f"Error: Invalid date format '{args.due}'. Use YYYY-MM-DD.")
            sys.exit(1)
    
    if args.reason:
        current_desc = task.get('description') or ''
        updates['description'] = f"{current_desc}\n\n[Deferred {date.today()}]: {args.reason}".strip()
    
    if updates:
        success = update_task(args.task_id, **updates)
        if success:
            print(f"✓ Deferred task #{args.task_id}")
        else:
            print(f"Error: Failed to defer task")
            sys.exit(1)


def cmd_search(args):
    """Search tasks by title/description."""
    # Get all tasks and filter by search query
    tasks = list_tasks()
    query = args.query.lower()
    tasks = [t for t in tasks if query in t['title'].lower() or (t.get('description') and query in t['description'].lower())]
    tasks = tasks[:args.limit]
    
    if args.format == "json":
        print(json.dumps(tasks, indent=2, default=str))
        return
    
    if not tasks:
        print(f"No tasks matching '{args.query}'")
        return
    
    print(f"Found {len(tasks)} task(s):")
    for task in tasks:
        status_icon = {'pending': '⬜', 'in_progress': '🔄', 'complete': '✅'}.get(task['status'], '?')
        print(f"  {status_icon} #{task['id']} {task['title']}")


def main():
    parser = argparse.ArgumentParser(
        description="Task system CLI - ADHD-optimized task management"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add task
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("--description", "-d", help="Task description")
    add_parser.add_argument("--domain", help="Domain name")
    add_parser.add_argument("--project", help="Project name")
    add_parser.add_argument("--priority", "-p", choices=["strategic", "external", "urgent", "normal"], default="normal", help="Priority bucket")
    add_parser.add_argument("--due", help="Due date (YYYY-MM-DD)")
    add_parser.add_argument("--estimate", "-e", type=int, help="Estimated minutes")
    add_parser.add_argument("--source-type", help="Source type (conversation, meeting, email)")
    add_parser.add_argument("--source-id", help="Source identifier")

    # List tasks
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--status", "-s", choices=["pending", "in_progress", "blocked", "complete", "abandoned"], help="Filter by status")
    list_parser.add_argument("--priority", "-p", choices=["strategic", "external", "urgent", "normal"], help="Filter by priority")
    list_parser.add_argument("--domain", help="Filter by domain")
    list_parser.add_argument("--project", help="Filter by project")
    list_parser.add_argument("--source", help="Filter by source_type")
    list_parser.add_argument("--source-id", help="Filter by source_id")
    list_parser.add_argument("--limit", type=int, default=20, help="Limit results")
    list_parser.add_argument("--format", "-f", choices=["text", "json"], default="text", help="Output format")

    # Complete task
    complete_parser = subparsers.add_parser("complete", help="Mark task as complete")
    complete_parser.add_argument("task_id", type=int, help="Task ID")
    complete_parser.add_argument("--actual", "-a", type=int, help="Actual minutes spent")

    # Update task
    update_parser = subparsers.add_parser("update", help="Update task")
    update_parser.add_argument("task_id", type=int, help="Task ID")
    update_parser.add_argument("--status", "-s", choices=["pending", "in_progress", "blocked", "complete", "abandoned"], help="New status")
    update_parser.add_argument("--description", "-d", help="Update description")
    update_parser.add_argument("--priority", "-p", choices=["strategic", "external", "urgent", "normal"], help="Update priority")
    update_parser.add_argument("--due", help="Update due date (YYYY-MM-DD)")

    # Tag conversation
    tag_parser = subparsers.add_parser("tag-conversation", help="Link a conversation to a task")
    tag_parser.add_argument("--convo-id", required=True, help="Conversation ID")
    tag_parser.add_argument("--task-id", type=int, required=True, help="Task ID")
    tag_parser.add_argument("--method", choices=["manual", "inferred", "confirmed"], default="manual", help="Tag method")

    # Defer task
    defer_parser = subparsers.add_parser("defer", help="Defer task to later")
    defer_parser.add_argument("task_id", type=int, help="Task ID")
    defer_parser.add_argument("--due", help="New due date (YYYY-MM-DD)")
    defer_parser.add_argument("--reason", "-r", help="Deferral reason")

    # Search tasks
    search_parser = subparsers.add_parser("search", help="Search tasks")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=20, help="Limit results")
    search_parser.add_argument("--format", "-f", choices=["text", "json"], default="text", help="Output format")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to command handler
    handlers = {
        'add': cmd_add,
        'list': cmd_list,
        'complete': cmd_complete,
        'update': cmd_update,
        'tag-conversation': cmd_tag_conversation,
        'defer': cmd_defer,
        'search': cmd_search,
    }
    
    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
