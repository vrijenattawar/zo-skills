#!/usr/bin/env python3
"""
Context CLI - Gather context for LLM reasoning about tasks.

This module REPLACES regex-based inference in action_tagger.py, close_hooks.py,
and b05_parser.py. Instead of trying to infer meaning with patterns, we gather
context and return it for AI to reason about semantically.

Key principle: NO INFERENCE - only gather and format context.
The AI does all reasoning.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import database layer
# Add parent directory to path for imports (same pattern as briefing.py)
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

# Import from db module (same directory)
from db import (
    get_task, get_task_history, list_tasks,
    get_task_for_conversation
)

# Paths
CONVO_WORKSPACE_ROOT = Path("/home/.z/workspaces")


# ============================================================================
# Helper Functions
# ============================================================================

def load_session_state(convo_id: str) -> Optional[Dict[str, Any]]:
    """
    Read SESSION_STATE.md from conversation workspace.

    Returns:
        Dict with focus, type, artifacts_created, or None if not found
    """
    session_state_path = CONVO_WORKSPACE_ROOT / convo_id / "SESSION_STATE.md"
    
    if not session_state_path.exists():
        return None
    
    try:
        content = session_state_path.read_text()
        
        # Parse frontmatter and sections
        result = {
            "focus": None,
            "type": None,
            "artifacts_created": []
        }
        
        # Extract focus from frontmatter
        focus_match = re.search(r'^focus:\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if focus_match:
            result["focus"] = focus_match.group(1).strip()
        
        # Extract type
        type_match = re.search(r'^type:\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if type_match:
            result["type"] = type_match.group(1).strip()
        
        # Extract artifacts from Artifacts section
        artifacts_section = re.search(r'## Artifacts\s*\n(.*?)(?=##|$)', content, re.DOTALL)
        if artifacts_section:
            artifact_lines = artifacts_section.group(1).strip().split('\n')
            for line in artifact_lines:
                line = line.strip()
                if line and line.startswith('-'):
                    # Extract file path from markdown link or plain text
                    path_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)|^-\s*(.+)$', line)
                    if path_match:
                        result["artifacts_created"].append(
                            path_match.group(2) if path_match.group(2) else path_match.group(3).strip()
                        )
        
        return result
        
    except Exception as e:
        return {"error": f"Failed to read SESSION_STATE: {str(e)}"}


def get_conversation_summary(convo_id: str) -> str:
    """
    Generate a summary of conversation content by reading markdown files.

    Returns:
        String summary or error message
    """
    convo_path = CONVO_WORKSPACE_ROOT / convo_id
    
    if not convo_path.exists():
        return "Conversation workspace not found"
    
    try:
        # Find main conversation file (usually the first .md file)
        md_files = list(convo_path.glob("*.md"))
        
        if not md_files:
            return "No markdown files found"
        
        # Read first markdown file (likely conversation transcript)
        main_file = md_files[0]
        content = main_file.read_text()
        
        # Extract first few exchanges for context (limit to 2000 chars)
        lines = content.split('\n')
        summary_lines = []
        char_count = 0
        
        for line in lines:
            if char_count > 2000:
                break
            summary_lines.append(line)
            char_count += len(line)
        
        summary = '\n'.join(summary_lines)
        
        # Add note if truncated
        if len(content) > char_count:
            summary += f"\n\n[... {len(content) - char_count} more characters ...]"
        
        return summary
        
    except Exception as e:
        return f"Error reading conversation: {str(e)}"


def scan_for_deliveries(convo_id: str) -> Dict[str, Any]:
    """
    Scan conversation for delivery indicators: files created, messages sent, etc.

    Returns:
        Dict with files_created, emails_sent, explicit_completion_statement
    """
    convo_path = CONVO_WORKSPACE_ROOT / convo_id
    
    result = {
        "files_created": [],
        "emails_sent": False,
        "explicit_completion_statement": False,
        "delivery_keywords_found": []
    }
    
    if not convo_path.exists():
        return result
    
    try:
        # Scan all markdown files
        for md_file in convo_path.glob("*.md"):
            content = md_file.read_text().lower()
            
            # Check for file creation patterns
            file_patterns = [
                r'file (?:created|saved|written|drafted)',
                r'(?:memo|report|document|proposal|email|letter|blurb) (?:created|written|drafted)',
                r'saved (?:the )?(?:file|document|memo)',
                r'created (?:the )?(?:file|document)',
            ]
            
            for pattern in file_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    result["delivery_keywords_found"].extend(matches)
            
            # Check for email sent patterns
            email_patterns = [
                r'sent (?:an )?(?:email|message)',
                r'email (?:sent|drafted|written)',
            ]
            
            for pattern in email_patterns:
                if re.search(pattern, content):
                    result["emails_sent"] = True
                    result["delivery_keywords_found"].append("email_sent")
                    break
            
            # Check for explicit completion statements
            completion_patterns = [
                r'\b(done|completed|finished|wrapped up)!\b',
                r'\b(that.s|this is) (done|complete|finished)\b',
                r'\btask (?:is )?complete\b',
            ]
            
            for pattern in completion_patterns:
                if re.search(pattern, content):
                    result["explicit_completion_statement"] = True
                    result["delivery_keywords_found"].append("completion_statement")
                    break
        
        # Extract actual file names from SESSION_STATE artifacts
        session_state = load_session_state(convo_id)
        if session_state and session_state.get("artifacts_created"):
            result["files_created"] = session_state["artifacts_created"]
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        return result


def get_recent_task_activity(task_id: int) -> List[Dict[str, Any]]:
    """
    Get recent task events history.

    Returns:
        List of event dictionaries or empty list
    """
    try:
        events = get_task_history(task_id)
        
        # Format events for AI consumption
        formatted_events = []
        for event in events:
            formatted_events.append({
                "event_type": event["event_type"],
                "timestamp": event["timestamp"],
                "data": json.loads(event["event_data"]) if event["event_data"] else None
            })
        
        return formatted_events
        
    except Exception as e:
        return [{"error": str(e)}]


def extract_first_message(convo_id: str) -> Optional[str]:
    """
    Extract first user message from conversation for action detection.

    Returns:
        First message text or None
    """
    convo_path = CONVO_WORKSPACE_ROOT / convo_id
    
    if not convo_path.exists():
        return None
    
    try:
        md_files = list(convo_path.glob("*.md"))
        if not md_files:
            return None
        
        content = md_files[0].read_text()
        
        # Look for first message after initial metadata
        # Usually pattern is: "### User" or just first substantial paragraph
        lines = content.split('\n')
        
        # Skip empty lines and metadata
        for i, line in enumerate(lines):
            # Skip markdown headers and metadata
            if line.startswith('#') or line.startswith('---') or line.startswith('created:'):
                continue
            
            # Look for message indicator (common in Zo transcripts)
            if '### User' in line or '**User**:' in line:
                # Get next non-empty line
                for j in range(i+1, len(lines)):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith('#'):
                        return next_line
            
            # If no explicit markers, take the first substantial paragraph
            if len(line.strip()) > 20 and not line.startswith('```'):
                return line.strip()
        
        return None
        
    except Exception as e:
        return None


def get_active_tasks(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get currently active tasks for context.

    Returns:
        List of task dictionaries
    """
    try:
        # Get pending and in_progress tasks
        tasks = []
        
        for status in ['pending', 'in_progress']:
            tasks.extend(list_tasks(status=status, days_ahead=14))
        
        # Limit and format
        formatted_tasks = []
        for task in tasks[:limit]:
            formatted_tasks.append({
                "id": task["id"],
                "title": task["title"],
                "status": task["status"],
                "priority_bucket": task["priority_bucket"],
                "domain": task.get("domain_name"),
                "project": task.get("project_name"),
                "due_at": task["due_at"]
            })
        
        return formatted_tasks
        
    except Exception as e:
        return [{"error": str(e)}]


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_action_check(convo_id: str) -> str:
    """
    Returns context for AI to determine if conversation is action-oriented.

    AI then reasons: "This conversation is working on task #X."
    """
    # Gather context
    session_state = load_session_state(convo_id)
    first_message = extract_first_message(convo_id)
    existing_tasks = get_active_tasks(limit=5)
    
    # Build context JSON
    context = {
        "convo_id": convo_id,
        "session_state": session_state or {},
        "first_message_preview": first_message or "Could not extract first message",
        "existing_tasks": existing_tasks,
        "inference_guidance": {
            "action_keywords": [
                "write", "draft", "build", "create", "send", "complete",
                "finish", "implement", "develop", "design", "update", "revise",
                "work on", "get done", "knock out"
            ],
            "task_patterns": [
                "the X for Y",
                "let's work on X",
                "help me write/draft X",
                "complete X task"
            ]
        }
    }
    
    return json.dumps(context, indent=2)


def cmd_completion_check(convo_id: str, task_id: int) -> str:
    """
    Returns context for AI to assess task completion.

    AI then reasons: "Draft completed, but not yet sent. Status: partial."
    """
    # Get task details
    task = get_task(task_id)
    
    if not task:
        return json.dumps({
            "error": f"Task {task_id} not found",
            "convo_id": convo_id
        }, indent=2)
    
    # Parse plan JSON
    plan = json.loads(task["plan_json"]) if task.get("plan_json") else {}
    milestones = plan.get("milestones", [])
    
    # Gather conversation context
    convo_summary = get_conversation_summary(convo_id)
    deliveries = scan_for_deliveries(convo_id)
    
    # Build context JSON
    context = {
        "task": {
            "id": task["id"],
            "title": task["title"],
            "description": task.get("description"),
            "status": task["status"],
            "milestones": milestones,
            "priority_bucket": task["priority_bucket"]
        },
        "conversation_summary": convo_summary[:500] + "..." if len(convo_summary) > 500 else convo_summary,
        "artifacts_created": deliveries.get("files_created", []),
        "delivery_indicators": {
            "files_created": deliveries.get("files_created", []),
            "emails_sent": deliveries.get("emails_sent", False),
            "explicit_completion_statement": deliveries.get("explicit_completion_statement", False),
            "keywords_found": deliveries.get("delivery_keywords_found", [])
        },
        "inference_guidance": {
            "completion_signals": [
                "Files created match task description",
                "Explicit completion statement in conversation",
                "Email sent if task involves communication",
                "All milestones (if defined) appear complete"
            ],
            "partial_signals": [
                "Draft created but not sent/finalized",
                "Some milestones completed but not all",
                "Work in progress without completion statement"
            ]
        }
    }
    
    return json.dumps(context, indent=2)


def cmd_next_step(task_id: int) -> str:
    """
    Returns context for AI to suggest next step.

    AI then reasons: "Next step is to review with team."
    """
    # Get task details
    task = get_task(task_id)
    
    if not task:
        return json.dumps({
            "error": f"Task {task_id} not found"
        }, indent=2)
    
    # Parse plan JSON
    plan = json.loads(task["plan_json"]) if task.get("plan_json") else {}
    milestones = plan.get("milestones", [])
    
    # Get recent activity
    events = get_recent_task_activity(task_id)
    
    # Calculate time since last activity
    last_activity = None
    time_since_hours = None
    if events:
        last_event = events[-1]
        last_activity = last_event["timestamp"]
        try:
            last_time = datetime.fromisoformat(last_activity)
            hours_ago = (datetime.now() - last_time).total_seconds() / 3600
            time_since_hours = round(hours_ago, 1)
        except:
            pass
    
    # Build context JSON
    context = {
        "task": {
            "id": task["id"],
            "title": task["title"],
            "description": task.get("description"),
            "status": task["status"],
            "milestones": milestones,
            "priority_bucket": task["priority_bucket"]
        },
        "recent_activity": events[-3:] if len(events) > 3 else events,  # Last 3 events
        "last_activity_timestamp": last_activity,
        "time_since_last_activity_hours": time_since_hours,
        "related_tasks": [],  # Could be expanded to find parent/child tasks
        "inference_guidance": {
            "next_step_patterns": [
                "If milestones defined: next uncompleted milestone",
                "If no milestones: infer from task type (draft→review→send, etc.)",
                "Consider priority and due date",
                "Consider time since last activity"
            ],
            "common_next_steps": [
                "Review and polish",
                "Finalize and send",
                "Schedule follow-up",
                "Begin next phase",
                "Test/validate",
                "Document results"
            ]
        }
    }
    
    return json.dumps(context, indent=2)


def cmd_extract_tasks(file_path: str) -> str:
    """
    Returns context for AI to extract tasks from meeting B05 block.

    AI then extracts: structured task objects with title, first_step, priority, etc.
    """
    path = Path(file_path)
    
    if not path.exists():
        return json.dumps({
            "error": f"File not found: {file_path}"
        }, indent=2)
    
    # Read file content
    try:
        content = path.read_text()
    except Exception as e:
        return json.dumps({
            "error": f"Failed to read file: {str(e)}"
        }, indent=2)
    
    # Detect file type from path
    source_type = "meeting" if "B05_ACTION_ITEMS" in path.name or "meeting" in str(path).lower() else "unknown"
    
    # Extract meeting context from path if possible
    meeting_id = None
    meeting_match = re.search(r'/([^/]+?)/B05', str(path))
    if meeting_match:
        meeting_id = meeting_match.group(1)
    
    # Extract attendees if available (look for meeting metadata)
    attendees = []
    attendee_patterns = [
        r'##?\s*Attendees?:?\s*(.+?)(?:\n|$)',
        r'\*\*Attendees?\*\*:\s*(.+?)(?:\n|$)',
    ]
    for pattern in attendee_patterns:
        match = re.search(pattern, content)
        if match:
            attendee_text = match.group(1)
            # Split by comma or "and"
            attendees = [a.strip() for a in re.split(r',|\s+and\s+', attendee_text)]
            break
    
    # Extract existing tasks mentioned in content
    # Look for references like "task #5" or "existing task: ..."
    existing_task_mentions = []
    task_ref_patterns = [
        r'task\s*#?(\d+)',
        r'(?:existing|current)\s+task[:\s]+(.+?)(?:\n|$)',
    ]
    for pattern in task_ref_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        existing_task_mentions.extend(matches)
    
    # Build context JSON
    context = {
        "source_file": str(path),
        "source_type": source_type,
        "meeting_id": meeting_id,
        "raw_content": content,
        "attendees": attendees,
        "existing_tasks_mentioned": existing_task_mentions,
        "inference_guidance": {
            "task_extraction_patterns": [
                "Look for action verbs (send, create, draft, review, etc.)",
                "Identify owners from attendee list or explicit assignments",
                "Extract priority from urgency keywords or explicit markers",
                "Infer domain/project from meeting context",
                "Break down complex items into first step + milestones"
            ],
            "priority_keywords": {
                "urgent": ["asap", "urgent", "immediately", "today", "by end of day"],
                "strategic": ["important", "key", "critical", "strategic"],
                "external": ["client", "partner", "vendor", "external"]
            },
            "domain_mapping": {
                "<YOUR_PRODUCT>": ["client", "career", "coaching", "resume"],
                "Zo": ["zo", "system", "ai", "build", "code"],
                "Personal": ["personal", "health", "admin", "life"]
            }
        }
    }
    
    return json.dumps(context, indent=2)


# ============================================================================
# Main CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Context CLI - Gather context for LLM reasoning about tasks"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Action conversation check (start of conversation)
    action_check_parser = subparsers.add_parser("action-check", help="Check if conversation is an action conversation")
    action_check_parser.add_argument("--convo-id", required=True, help="Conversation ID")

    # Completion check (end of conversation)
    completion_check_parser = subparsers.add_parser("completion-check", help="Check if task completed")
    completion_check_parser.add_argument("--convo-id", required=True, help="Conversation ID")
    completion_check_parser.add_argument("--task-id", required=True, type=int, help="Task ID")

    # Next step guidance
    next_step_parser = subparsers.add_parser("next-step", help="Get next step for task")
    next_step_parser.add_argument("--task-id", required=True, type=int, help="Task ID")

    # Extract tasks from B05
    extract_parser = subparsers.add_parser("extract-tasks", help="Extract tasks from meeting B05 file")
    extract_parser.add_argument("--file", required=True, help="Path to B05 file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    try:
        if args.command == "action-check":
            output = cmd_action_check(args.convo_id)
        elif args.command == "completion-check":
            output = cmd_completion_check(args.convo_id, args.task_id)
        elif args.command == "next-step":
            output = cmd_next_step(args.task_id)
        elif args.command == "extract-tasks":
            output = cmd_extract_tasks(args.file)
        else:
            parser.print_help()
            sys.exit(1)

        # Print JSON output
        print(output)

    except Exception as e:
        error_output = json.dumps({
            "error": str(e),
            "command": args.command
        }, indent=2)
        print(error_output, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
