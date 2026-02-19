#!/usr/bin/env python3
"""
Task System Database Layer

Pure database operations for the Task System Skill.
This module provides CRUD operations for tasks, domains, projects, staging,
and action conversation tracking. NO inference logic - all intelligence comes
from LLM reasoning.

Usage:
    from Skills.task_system.scripts.db import (
        create_task, get_task, update_task, complete_task, list_tasks,
        get_or_create_domain, get_or_create_project,
        stage_task, get_staged_tasks, promote_staged_task, dismiss_staged_task,
        tag_action_conversation, get_task_for_conversation, close_action_conversation,
        calculate_latency_stats, get_completion_rate
    )
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "tasks.db"

# Constants
STATUS_OPTIONS = ["pending", "in_progress", "blocked", "complete", "abandoned"]
PRIORITY_BUCKETS = ["strategic", "external", "urgent", "normal"]
PROJECT_TYPES = ["ephemeral", "permanent", "recurring"]
SOURCE_TYPES = ["conversation", "meeting", "manual", "email"]
STAGING_STATUS = ["pending_review", "promoted", "dismissed"]
TAG_METHODS = ["inferred", "confirmed", "manual"]


def get_connection() -> sqlite3.Connection:
    """Get database connection with row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _log_event(conn: sqlite3.Connection, task_id: int, event_type: str, event_data: Optional[Dict] = None):
    """Log a task event."""
    conn.execute(
        """INSERT INTO task_events (task_id, event_type, event_data, timestamp)
           VALUES (?, ?, ?, ?)""",
        (task_id, event_type, json.dumps(event_data) if event_data else None, datetime.now().isoformat())
    )


# ============================================================================
# Task Operations
# ============================================================================

def create_task(
    title: str,
    domain_id: int,
    description: Optional[str] = None,
    project_id: Optional[int] = None,
    priority_bucket: str = "normal",
    source_type: str = "manual",
    source_id: Optional[str] = None,
    due_at: Optional[str] = None,
    estimated_minutes: Optional[int] = None,
    parent_task_id: Optional[int] = None,
    plan_json: Optional[Dict] = None
) -> int:
    """
    Create a new task.

    Args:
        title: Task title
        domain_id: Domain ID (must exist)
        description: Optional description
        project_id: Optional project ID
        priority_bucket: One of 'strategic', 'external', 'urgent', 'normal'
        source_type: Where this task came from
        source_id: Source identifier (conversation_id, meeting_id, etc.)
        due_at: ISO format datetime or None
        estimated_minutes: Time estimate in minutes
        parent_task_id: Parent task for subtasks
        plan_json: Plan of action data

    Returns:
        Task ID
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO tasks (title, description, domain_id, project_id, status,
               priority_bucket, source_type, source_id, due_at, estimated_minutes,
               parent_task_id, plan_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                title, description, domain_id, project_id, "pending",
                priority_bucket, source_type, source_id, due_at,
                estimated_minutes, parent_task_id,
                json.dumps(plan_json) if plan_json else None
            )
        )
        task_id = cursor.lastrowid

        # Log creation event
        _log_event(conn, task_id, "created", {"title": title, "source_type": source_type, "source_id": source_id})

        conn.commit()
        return task_id

    finally:
        conn.close()


def get_task(task_id: int) -> Optional[Dict]:
    """
    Get a single task by ID with full details.

    Args:
        task_id: Task ID

    Returns:
        Task dict with domain_name and project_name, or None if not found
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT t.*, d.name AS domain_name, p.name AS project_name
               FROM tasks t
               JOIN domains d ON t.domain_id = d.id
               LEFT JOIN projects p ON t.project_id = p.id
               WHERE t.id = ?""",
            (task_id,)
        ).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def get_task_by_source(source_type: str, source_id: str) -> Optional[Dict]:
    """
    Find a task by its source reference.

    Args:
        source_type: Type of source (conversation, meeting, email, manual)
        source_id: Source identifier

    Returns:
        Task dict or None if not found
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT t.*, d.name AS domain_name, p.name AS project_name
               FROM tasks t
               JOIN domains d ON t.domain_id = d.id
               LEFT JOIN projects p ON t.project_id = p.id
               WHERE t.source_type = ? AND t.source_id = ?""",
            (source_type, source_id)
        ).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def update_task(task_id: int, **fields) -> bool:
    """
    Update task fields.

    Args:
        task_id: Task to update
        **fields: Fields to update (title, description, status, priority_bucket, etc.)

    Returns:
        True if updated, False if not found
    """
    if not fields:
        return False

    conn = get_connection()
    try:
        valid_fields = {k: v for k, v in fields.items() if v is not None}
        if not valid_fields:
            return False

        set_clause = ", ".join([f"{k} = ?" for k in valid_fields.keys()])
        values = list(valid_fields.values()) + [task_id]

        cursor = conn.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = ?",
            values
        )

        if cursor.rowcount > 0:
            # Log update event
            _log_event(conn, task_id, "updated", {"fields": list(valid_fields.keys())})
            conn.commit()
            return True
        return False

    finally:
        conn.close()


def complete_task(task_id: int, actual_minutes: Optional[int] = None) -> bool:
    """
    Mark a task as complete.

    Args:
        task_id: Task to complete
        actual_minutes: Actual time spent (optional)

    Returns:
        True if completed, False if not found
    """
    conn = get_connection()
    try:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return False

        now = datetime.now().isoformat()

        cursor = conn.execute(
            """UPDATE tasks SET status = ?, completed_at = ?, actual_minutes = ?
               WHERE id = ?""",
            ("complete", now, actual_minutes, task_id)
        )

        if cursor.rowcount > 0:
            # Log completion event
            event_data = {
                "due_at": task["due_at"],
                "completed_at": now
            }
            if actual_minutes:
                event_data["actual_minutes"] = actual_minutes

            _log_event(conn, task_id, "completed", event_data)
            conn.commit()
            return True
        return False

    finally:
        conn.close()


def list_tasks(
    status: Optional[str] = None,
    domain: Optional[str] = None,
    due_date: Optional[str] = None,
    project: Optional[str] = None,
    priority_bucket: Optional[str] = None,
    days_ahead: int = None
) -> List[Dict]:
    """
    List tasks with optional filters.

    Args:
        status: Filter by status (pending, in_progress, blocked, complete, abandoned)
        domain: Filter by domain name
        due_date: Filter by specific due date (YYYY-MM-DD)
        project: Filter by project name
        priority_bucket: Filter by priority bucket
        days_ahead: Include tasks due within this many days (overrides due_date)

    Returns:
        List of task dictionaries
    """
    conn = get_connection()
    try:
        where_clauses = ["t.archived = FALSE"]
        params = []

        if status:
            where_clauses.append("t.status = ?")
            params.append(status)

        if domain:
            where_clauses.append("d.name = ?")
            params.append(domain)

        if project:
            where_clauses.append("p.name = ?")
            params.append(project)

        if priority_bucket:
            where_clauses.append("t.priority_bucket = ?")
            params.append(priority_bucket)

        if due_date:
            where_clauses.append("date(t.due_at) = ?")
            params.append(due_date)
        elif days_ahead:
            where_clauses.append("(t.due_at IS NULL OR date(t.due_at) >= date('now', 'localtime') OR date(t.due_at) <= date('now', 'localtime', '+' || ? || ' day'))")
            params.append(days_ahead)

        where_sql = " AND ".join(where_clauses)

        query = f"""
            SELECT
                t.*,
                d.name AS domain_name,
                p.name AS project_name
            FROM tasks t
            JOIN domains d ON t.domain_id = d.id
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE {where_sql}
            ORDER BY
                CASE t.priority_bucket
                    WHEN 'urgent' THEN 1
                    WHEN 'strategic' THEN 2
                    WHEN 'external' THEN 3
                    WHEN 'normal' THEN 4
                    ELSE 5
                END,
                t.due_at ASC,
                t.created_at ASC
        """

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    finally:
        conn.close()


def get_task_history(task_id: int) -> List[Dict]:
    """
    Get event history for a task.

    Args:
        task_id: Task ID

    Returns:
        List of event dictionaries
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM task_events WHERE task_id = ? ORDER BY timestamp ASC",
            (task_id,)
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


# ============================================================================
# Domain & Project Operations
# ============================================================================

def get_or_create_domain(name: str, description: Optional[str] = None, color: str = '#4A90E2') -> int:
    """
    Get an existing domain by name, or create it if it doesn't exist.

    Args:
        name: Domain name
        description: Optional description
        color: Domain color (default blue)

    Returns:
        Domain ID
    """
    conn = get_connection()
    try:
        domain_row = conn.execute("SELECT id FROM domains WHERE name = ?", (name,)).fetchone()
        if domain_row:
            return domain_row["id"]

        cursor = conn.execute(
            "INSERT INTO domains (name, description, color) VALUES (?, ?, ?)",
            (name, description or f"Domain for {name}", color)
        )
        conn.commit()
        return cursor.lastrowid

    finally:
        conn.close()


def get_or_create_project(name: str, domain_id: int, project_type: str = "ephemeral",
                          description: Optional[str] = None) -> int:
    """
    Get an existing project by name within a domain, or create it if it doesn't exist.

    Args:
        name: Project name
        domain_id: Domain ID
        project_type: One of 'ephemeral', 'permanent', 'recurring'
        description: Optional description

    Returns:
        Project ID
    """
    conn = get_connection()
    try:
        project_row = conn.execute(
            "SELECT id FROM projects WHERE domain_id = ? AND name = ?",
            (domain_id, name)
        ).fetchone()
        if project_row:
            return project_row["id"]

        cursor = conn.execute(
            """INSERT INTO projects (domain_id, name, description, project_type)
               VALUES (?, ?, ?, ?)""",
            (domain_id, name, description or f"Project for {name}", project_type)
        )
        conn.commit()
        return cursor.lastrowid

    finally:
        conn.close()


def list_domains(archived: bool = False) -> List[Dict]:
    """
    List all domains.

    Args:
        archived: Include archived domains (default False)

    Returns:
        List of domain dictionaries
    """
    conn = get_connection()
    try:
        if archived:
            rows = conn.execute("SELECT * FROM domains ORDER BY name").fetchall()
        else:
            rows = conn.execute("SELECT * FROM domains WHERE archived = FALSE ORDER BY name").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_projects(domain_name: Optional[str] = None, archived: bool = False) -> List[Dict]:
    """
    List projects, optionally filtered by domain.

    Args:
        domain_name: Filter by domain name (optional)
        archived: Include archived projects (default False)

    Returns:
        List of project dictionaries with domain_name
    """
    conn = get_connection()
    try:
        if domain_name:
            if archived:
                rows = conn.execute(
                    """SELECT p.*, d.name AS domain_name
                       FROM projects p
                       JOIN domains d ON p.domain_id = d.id
                       WHERE d.name = ?
                       ORDER BY p.name""",
                    (domain_name,)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT p.*, d.name AS domain_name
                       FROM projects p
                       JOIN domains d ON p.domain_id = d.id
                       WHERE d.name = ? AND p.archived = FALSE
                       ORDER BY p.name""",
                    (domain_name,)
                ).fetchall()
        else:
            if archived:
                rows = conn.execute(
                    """SELECT p.*, d.name AS domain_name
                       FROM projects p
                       JOIN domains d ON p.domain_id = d.id
                       ORDER BY d.name, p.name"""
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT p.*, d.name AS domain_name
                       FROM projects p
                       JOIN domains d ON p.domain_id = d.id
                       WHERE p.archived = FALSE
                       ORDER BY d.name, p.name"""
                ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ============================================================================
# Staging Operations
# ============================================================================

def stage_task(
    title: str,
    source_type: str,
    source_id: str,
    source_context: Optional[str] = None,
    description: Optional[str] = None,
    suggested_domain: Optional[str] = None,
    suggested_project: Optional[str] = None,
    suggested_priority: str = "normal"
) -> int:
    """
    Stage a potential task for review.

    Args:
        title: Task title
        source_type: Type of source (meeting, conversation, email, manual)
        source_id: Source identifier
        source_context: Relevant quote or context from source
        description: Full description
        suggested_domain: AI-guessed domain name
        suggested_project: AI-guessed project name
        suggested_priority: AI-guessed priority bucket

    Returns:
        Staged task ID
    """
    conn = get_connection()
    try:
        cursor = conn.execute("""
            INSERT INTO staged_tasks (
                title, description, source_type, source_id, source_context,
                suggested_domain, suggested_project, suggested_priority
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            description or "",
            source_type,
            source_id,
            source_context or "",
            suggested_domain or "",
            suggested_project or "",
            suggested_priority
        ))
        conn.commit()
        return cursor.lastrowid

    finally:
        conn.close()


def get_staged_tasks(status: str = 'pending_review') -> List[Dict]:
    """
    Get staged tasks by status.

    Args:
        status: Status filter (default 'pending_review')

    Returns:
        List of staged task dictionaries
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM staged_tasks
            WHERE status = ?
            ORDER BY captured_at DESC
        """, (status,)).fetchall()
        return [dict(row) for row in rows]

    finally:
        conn.close()


def get_staged_task_by_id(staged_id: int) -> Optional[Dict]:
    """
    Get a specific staged task by ID.

    Args:
        staged_id: Staged task ID

    Returns:
        Task dict or None if not found
    """
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM staged_tasks WHERE id = ?", (staged_id,)).fetchone()
        return dict(row) if row else None

    finally:
        conn.close()


def get_staged_tasks_by_source(source_type: str, source_id: str) -> List[Dict]:
    """
    Get all staged tasks from a specific source.

    Args:
        source_type: Type of source (meeting, conversation, email, manual)
        source_id: Source identifier

    Returns:
        List of staged task dictionaries
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM staged_tasks
            WHERE source_type = ? AND source_id = ?
            ORDER BY captured_at DESC
        """, (source_type, source_id)).fetchall()
        return [dict(row) for row in rows]

    finally:
        conn.close()


def promote_staged_task(staged_id: int, task_data: Dict) -> int:
    """
    Promote a staged task to the official task registry.

    Args:
        staged_id: Staged task ID
        task_data: Dict with task fields (title, domain_id, priority_bucket, etc.)

    Returns:
        Created task ID
    """
    staged = get_staged_task_by_id(staged_id)
    if not staged:
        raise ValueError(f"Staged task {staged_id} not found")

    # Create the actual task
    task_id = create_task(
        title=task_data.get("title", staged["title"]),
        domain_id=task_data["domain_id"],
        description=task_data.get("description", staged["description"]),
        project_id=task_data.get("project_id"),
        priority_bucket=task_data.get("priority_bucket", staged["suggested_priority"]),
        source_type=staged["source_type"],
        source_id=staged["source_id"],
        due_at=task_data.get("due_at"),
        estimated_minutes=task_data.get("estimated_minutes"),
        plan_json=task_data.get("plan_json")
    )

    # Update staged task
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE staged_tasks
            SET status = 'promoted', promoted_task_id = ?, promoted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (task_id, staged_id))
        conn.commit()
    finally:
        conn.close()

    return task_id


def dismiss_staged_task(staged_id: int, reason: str) -> bool:
    """
    Dismiss a staged task.

    Args:
        staged_id: Staged task ID
        reason: Reason for dismissal

    Returns:
        True if successful, False if not found
    """
    conn = get_connection()
    try:
        cursor = conn.execute("""
            UPDATE staged_tasks
            SET status = 'dismissed', dismissed_reason = ?, dismissed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (reason, staged_id))
        conn.commit()
        return cursor.rowcount > 0

    finally:
        conn.close()


def cleanup_old_staged_tasks(days_old: int = 30) -> int:
    """
    Clean up old dismissed or promoted staged tasks.

    Args:
        days_old: Delete tasks older than this many days

    Returns:
        Number of tasks deleted
    """
    conn = get_connection()
    try:
        cursor = conn.execute("""
            DELETE FROM staged_tasks
            WHERE status IN ('dismissed', 'promoted')
            AND (
                (dismissed_at < datetime('now', '-' || ? || ' days'))
                OR (promoted_at < datetime('now', '-' || ? || ' days'))
            )
        """, (days_old, days_old))
        conn.commit()
        return cursor.rowcount

    finally:
        conn.close()


# ============================================================================
# Action Conversation Operations
# ============================================================================

def tag_action_conversation(convo_id: str, task_id: int, method: str = 'manual') -> bool:
    """
    Tag a conversation as an action conversation for a specific task.

    Args:
        convo_id: Conversation ID (string)
        task_id: Task ID (int)
        method: Tagging method - 'inferred', 'confirmed', or 'manual'

    Returns:
        True if successful, False otherwise
    """
    if method not in TAG_METHODS:
        raise ValueError(f"Invalid tag_method: {method}")

    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO action_conversations
            (conversation_id, task_id, tag_method, status)
            VALUES (?, ?, ?, 'active')
        """, (convo_id, str(task_id), method))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error tagging conversation: {e}")
        return False
    finally:
        conn.close()


def get_task_for_conversation(convo_id: str) -> Optional[int]:
    """
    Get the task ID associated with a conversation.

    Args:
        convo_id: Conversation ID

    Returns:
        Task ID if found and active, None otherwise
    """
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT task_id FROM action_conversations
            WHERE conversation_id = ? AND status = 'active'
        """, (convo_id,)).fetchone()
        return int(row["task_id"]) if row else None
    finally:
        conn.close()


def get_conversation_details(convo_id: str) -> Optional[Dict]:
    """
    Get full details for an action conversation including task info.

    Args:
        convo_id: Conversation ID

    Returns:
        Dict with conversation and task details, or None if not found
    """
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT ac.* FROM action_conversations ac
            WHERE ac.conversation_id = ?
        """, (convo_id,)).fetchone()

        if not row:
            return None

        result = dict(row)

        # Get task details
        task_id = int(result["task_id"])
        task = get_task(task_id)
        if task:
            result["task_title"] = task["title"]
            result["task_status"] = task["status"]

        return result
    finally:
        conn.close()


def close_action_conversation(convo_id: str) -> bool:
    """
    Mark an action conversation as closed.

    Args:
        convo_id: Conversation ID

    Returns:
        True if successful, False otherwise
    """
    conn = get_connection()
    try:
        cursor = conn.execute("""
            UPDATE action_conversations
            SET status = 'closed'
            WHERE conversation_id = ?
        """, (convo_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error closing action conversation: {e}")
        return False
    finally:
        conn.close()


def retag_conversation(convo_id: str, new_task_id: int, method: str = 'manual') -> bool:
    """
    Change the task associated with an action conversation.

    Args:
        convo_id: Conversation ID
        new_task_id: New task ID
        method: Tagging method

    Returns:
        True if successful, False otherwise
    """
    if method not in TAG_METHODS:
        raise ValueError(f"Invalid tag_method: {method}")

    conn = get_connection()
    try:
        cursor = conn.execute("""
            UPDATE action_conversations
            SET task_id = ?, tag_method = ?, status = 'active'
            WHERE conversation_id = ?
        """, (str(new_task_id), method, convo_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error retagging conversation: {e}")
        return False
    finally:
        conn.close()


def get_action_conversations_for_task(task_id: int) -> List[Dict]:
    """
    Get all action conversations for a specific task.

    Args:
        task_id: Task ID

    Returns:
        List of conversation dictionaries
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT conversation_id, tagged_at, tag_method, status
            FROM action_conversations
            WHERE task_id = ?
            ORDER BY tagged_at DESC
        """, (str(task_id),)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_active_action_conversations() -> List[Dict]:
    """
    Get all active action conversations.

    Returns:
        List of dicts with conversation_id, task_id, tagged_at, tag_method
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT conversation_id, task_id, tagged_at, tag_method
            FROM action_conversations
            WHERE status = 'active'
            ORDER BY tagged_at DESC
        """).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ============================================================================
# Analytics Operations
# ============================================================================

def calculate_latency_stats(
    days_back: int = 30,
    domain: Optional[str] = None,
    project: Optional[str] = None,
    task_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Calculate latency statistics for completed tasks.

    Args:
        days_back: How many days back to analyze
        domain: Filter by domain name
        project: Filter by project name
        task_id: Filter by specific task

    Returns:
        Dictionary with stats:
        - avg_hours_overdue: Average hours past due date
        - avg_hours_to_complete: Average hours from creation to completion
        - total_tasks: Number of tasks analyzed
        - overdue_count: Tasks completed past due date
        - on_time_count: Tasks completed on or before due date
    """
    conn = get_connection()
    try:
        where_clauses = ["t.status = 'complete'", "t.completed_at IS NOT NULL"]
        params = []

        if task_id:
            where_clauses.append("t.id = ?")
            params.append(task_id)
        else:
            if days_back:
                where_clauses.append("t.completed_at >= datetime('now', ? || ' days')")
                params.append(f"-{days_back}")

            if domain:
                where_clauses.append("d.name = ?")
                params.append(domain)

            if project:
                where_clauses.append("p.name = ?")
                params.append(project)

        where_sql = " AND ".join(where_clauses)

        query = f"""
            SELECT
                t.due_at,
                t.completed_at,
                t.created_at,
                julianday(t.completed_at) - julianday(t.due_at) AS days_overdue,
                julianday(t.completed_at) - julianday(t.created_at) AS days_to_complete
            FROM tasks t
            JOIN domains d ON t.domain_id = d.id
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE {where_sql}
        """

        rows = conn.execute(query, params).fetchall()

        if not rows:
            return {
                "avg_hours_overdue": None,
                "avg_hours_to_complete": None,
                "total_tasks": 0,
                "overdue_count": 0,
                "on_time_count": 0
            }

        hours_overdue = [r["days_overdue"] * 24 if r["due_at"] and r["days_overdue"] > 0 else 0 for r in rows]
        hours_to_complete = [r["days_to_complete"] * 24 for r in rows if r["days_to_complete"]]
        overdue_count = sum(1 for h in hours_overdue if h > 0)

        return {
            "avg_hours_overdue": sum(hours_overdue) / len(hours_overdue) if hours_overdue else 0,
            "avg_hours_to_complete": sum(hours_to_complete) / len(hours_to_complete) if hours_to_complete else None,
            "total_tasks": len(rows),
            "overdue_count": overdue_count,
            "on_time_count": len(rows) - overdue_count,
            "days_analyzed": days_back
        }

    finally:
        conn.close()


def get_completion_rate(days: int = 7) -> float:
    """
    Calculate task completion rate over recent days.

    Args:
        days: Number of days to look back

    Returns:
        Completion rate as percentage (0-100)
    """
    conn = get_connection()
    try:
        # Get tasks created in the last N days
        rows = conn.execute("""
            SELECT status
            FROM tasks
            WHERE created_at >= datetime('now', ? || ' days')
            AND archived = FALSE
        """, (f"-{days}",)).fetchall()

        if not rows:
            return 0.0

        total = len(rows)
        completed = sum(1 for r in rows if r["status"] == "complete")

        return (completed / total) * 100 if total > 0 else 0.0

    finally:
        conn.close()


# ============================================================================
# Day Plan Operations
# ============================================================================

def get_day_plan(plan_date: str) -> Optional[Dict]:
    """
    Get a day plan for a specific date.

    Args:
        plan_date: Date string (YYYY-MM-DD)

    Returns:
        Day plan dict or None if not found
    """
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT * FROM day_plans WHERE plan_date = ?
        """, (plan_date,)).fetchone()

        if not row:
            return None

        result = dict(row)
        result["task_ids"] = json.loads(result["task_ids"])
        return result

    finally:
        conn.close()


def save_day_plan(plan_date: str, task_ids: List[int]) -> int:
    """
    Save or update a day plan.

    Args:
        plan_date: Date string (YYYY-MM-DD)
        task_ids: List of task IDs

    Returns:
        Plan ID
    """
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO day_plans (plan_date, task_ids, total_tasks)
            VALUES (?, ?, ?)
        """, (plan_date, json.dumps(task_ids), len(task_ids)))
        conn.commit()
        return conn.execute("SELECT id FROM day_plans WHERE plan_date = ?", (plan_date,)).fetchone()["id"]
    finally:
        conn.close()


if __name__ == "__main__":
    # Test database connectivity
    print("Task System Database Layer")
    print(f"Database path: {DB_PATH}")
    print(f"Database exists: {DB_PATH.exists()}")

    if DB_PATH.exists():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        print(f"Tables: {tables}")
        print("✓ Database layer initialized successfully")
