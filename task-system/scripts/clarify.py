#!/usr/bin/env python3
"""
Clarify what a task is about using LLM semantic understanding.

When you see a task in _TASKS.md and think "what was this about?",
this script gathers all context and asks an LLM to explain it.

Usage:
    python3 clarify.py 123          # Clarify task #123
    python3 clarify.py 123 --brief  # One-line summary only
"""

import argparse
import json
import os
import sqlite3
import requests
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "tasks.db"
CONVERSATIONS_DIR = Path("/home/.z/workspaces")
ZO_API = "https://api.zo.computer/zo/ask"


def get_task(task_id: int) -> dict | None:
    """Fetch task and related data from database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get task with domain name
    cursor.execute("""
        SELECT t.*, d.name as domain_name
        FROM tasks t
        LEFT JOIN domains d ON t.domain_id = d.id
        WHERE t.id = ?
    """, (task_id,))
    
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    
    task = dict(row)
    
    # Get any events for this task
    cursor.execute("""
        SELECT event_type, event_data, timestamp
        FROM task_events
        WHERE task_id = ?
        ORDER BY timestamp DESC
        LIMIT 10
    """, (task_id,))
    task['events'] = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return task


def get_conversation_context(convo_id: str) -> str | None:
    """Try to read conversation content for context."""
    convo_dir = CONVERSATIONS_DIR / convo_id
    
    # Try SESSION_STATE.md first
    state_file = convo_dir / "SESSION_STATE.md"
    if state_file.exists():
        try:
            content = state_file.read_text()
            # Limit to first 2000 chars
            return content[:2000]
        except:
            pass
    
    # Try any markdown files in the conversation
    for md_file in convo_dir.glob("*.md"):
        try:
            content = md_file.read_text()
            return content[:2000]
        except:
            pass
    
    return None


def ask_llm(prompt: str) -> str:
    """Call Zo API for semantic understanding."""
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        return "[Error: ZO_CLIENT_IDENTITY_TOKEN not set]"
    
    try:
        response = requests.post(
            ZO_API,
            headers={
                "authorization": token,
                "content-type": "application/json"
            },
            json={"input": prompt},
            timeout=60
        )
        response.raise_for_status()
        return response.json().get("output", "[No response]")
    except Exception as e:
        return f"[LLM Error: {e}]"


def format_date(timestamp: str | None) -> str:
    """Format timestamp for display."""
    if not timestamp:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime("%b %d, %Y")
    except:
        return timestamp


def clarify_task(task_id: int, brief: bool = False) -> str:
    """Generate clarification for a task."""
    task = get_task(task_id)
    if not task:
        return f"Task #{task_id} not found."
    
    # Gather context
    context_parts = []
    
    # Basic info
    context_parts.append(f"Task ID: #{task['id']}")
    context_parts.append(f"Title: {task['title']}")
    context_parts.append(f"Domain: {task['domain_name'] or 'Unknown'}")
    context_parts.append(f"Status: {task['status']}")
    context_parts.append(f"Priority: {task['priority_bucket']}")
    context_parts.append(f"Created: {format_date(task['created_at'])}")
    
    if task['description']:
        context_parts.append(f"Description: {task['description']}")
    
    if task['source_type'] and task['source_type'] != 'manual':
        context_parts.append(f"Source: {task['source_type']} - {task['source_id'] or 'N/A'}")
    
    if task['due_at']:
        context_parts.append(f"Due: {format_date(task['due_at'])}")
    
    if task['blocked_by']:
        context_parts.append(f"Blocked: {task['blocked_by']} - {task['blocked_reason'] or 'No reason given'}")
    
    # Conversation context if available
    convo_context = None
    if task['source_type'] == 'conversation' and task['source_id']:
        convo_context = get_conversation_context(task['source_id'])
        if convo_context:
            context_parts.append(f"\n--- Source Conversation Context ---\n{convo_context}")
    
    # Event history
    if task['events']:
        events_str = "\n".join([
            f"  - {e['event_type']}: {e['event_data']} ({format_date(e['timestamp'])})"
            for e in task['events'][:5]
        ])
        context_parts.append(f"\nRecent History:\n{events_str}")
    
    context = "\n".join(context_parts)
    
    # Build prompt
    if brief:
        prompt = f"""Given this task information, provide a ONE SENTENCE explanation of what this task is about and why it matters. Be specific and useful.

{context}

One sentence summary:"""
    else:
        prompt = f"""Explain this task concisely:

{context}

Respond in this format:
• **What**: [What V needs to do - be specific]
• **Why**: [Context or goal]  
• **Next step**: [Immediate action to start]

Keep each line to 1-2 sentences max."""
    
    return ask_llm(prompt)


def main():
    parser = argparse.ArgumentParser(description="Clarify what a task is about")
    parser.add_argument("task_id", type=int, help="Task ID to clarify (e.g., 123)")
    parser.add_argument("--brief", action="store_true", help="One-line summary only")
    
    args = parser.parse_args()
    
    result = clarify_task(args.task_id, args.brief)
    print(result)


if __name__ == "__main__":
    main()
