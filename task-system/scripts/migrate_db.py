#!/usr/bin/env python3
"""
Migrate N5 task system databases to unified Skill database.

This script:
1. Copies tasks.db (including staged_tasks which is already there)
2. Merges action_conversations.db table data
3. Creates unified Skills/task-system/data/tasks.db
"""

import sqlite3
import shutil
from pathlib import Path

# Paths
N5_TASKS_DB = Path("./N5/task_system/tasks.db")
N5_ACTION_DB = Path("./N5/task_system/action_conversations.db")
UNIFIED_DB = Path("./Skills/task-system/data/tasks.db")


def migrate():
    """Perform migration."""
    print("Starting database migration...")

    # Check source databases exist
    if not N5_TASKS_DB.exists():
        raise FileNotFoundError(f"Source database not found: {N5_TASKS_DB}")

    # Copy main tasks.db (this includes staged_tasks already)
    print(f"Copying tasks.db from {N5_TASKS_DB}")
    shutil.copy2(N5_TASKS_DB, UNIFIED_DB)
    print(f"✓ Copied to {UNIFIED_DB}")

    # Connect to unified database
    conn = sqlite3.connect(UNIFIED_DB)
    cursor = conn.cursor()

    # Create action_conversations table schema if not exists
    # The copy from tasks.db won't have this table since it's in a separate DB
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS action_conversations (
            conversation_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            tagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tag_method TEXT NOT NULL CHECK(tag_method IN ('inferred', 'confirmed', 'manual')),
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'closed'))
        )
    """)

    # Create indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_action_conversations_task_id
        ON action_conversations(task_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_action_conversations_status
        ON action_conversations(status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_action_conversations_convo
        ON action_conversations(conversation_id)
    """)

    print("✓ Created action_conversations table schema")

    # Migrate action_conversations data if source exists
    if N5_ACTION_DB.exists():
        # Read data from source DB
        source_conn = sqlite3.connect(N5_ACTION_DB)
        source_conn.row_factory = sqlite3.Row
        source_cursor = source_conn.cursor()

        source_cursor.execute("SELECT * FROM action_conversations")
        rows = source_cursor.fetchall()

        source_conn.close()

        # Insert into unified DB
        for row in rows:
            cursor.execute("""
                INSERT OR REPLACE INTO action_conversations
                (conversation_id, task_id, tagged_at, tag_method, status)
                VALUES (?, ?, ?, ?, ?)
            """, (row["conversation_id"], row["task_id"], row["tagged_at"], row["tag_method"], row["status"]))

        conn.commit()
        print(f"✓ Migrated {len(rows)} action_conversation records")
    else:
        print("⚠ No action_conversations.db found, skipping that migration")

    # Verify schema
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\nUnified database tables: {tables}")

    conn.commit()
    conn.close()

    print(f"\n✓ Migration complete! Unified database at: {UNIFIED_DB}")
    return UNIFIED_DB


if __name__ == "__main__":
    migrate()
