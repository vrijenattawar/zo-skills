# Task System Schema Documentation

## Database Location
`Skills/task-system/data/tasks.db`

## Tables

### domains
Organizational areas that tasks belong to.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| name | TEXT | Unique domain name |
| description | TEXT | Optional description |
| color | TEXT | Hex color for UI (default: #4A90E2) |
| created_at | TIMESTAMP | When domain was created |
| archived | BOOLEAN | Soft-delete flag |

### projects
Containers for related tasks within a domain.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| domain_id | INTEGER | FK to domains |
| name | TEXT | Project name |
| description | TEXT | Optional description |
| project_type | TEXT | ephemeral, permanent, or recurring |
| active | BOOLEAN | Whether project is active |
| archived | BOOLEAN | Soft-delete flag |
| created_at | TIMESTAMP | When project was created |
| archived_at | TIMESTAMP | When project was archived |

**Foreign Keys:**
- `domain_id` → `domains(id)` ON DELETE CASCADE

### tasks
Core task table.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| title | TEXT | Task title |
| description | TEXT | Optional detailed description |
| domain_id | INTEGER | FK to domains |
| project_id | INTEGER | FK to projects (nullable) |
| status | TEXT | pending, in_progress, blocked, complete, abandoned |
| priority_bucket | TEXT | strategic, external, urgent, normal |
| source_type | TEXT | conversation, meeting, manual, email |
| source_id | TEXT | ID from source system (conversation_id, meeting_id, etc.) |
| created_at | TIMESTAMP | When task was created |
| due_at | TIMESTAMP | Optional due date |
| completed_at | TIMESTAMP | When task was completed |
| estimated_minutes | INTEGER | Time estimate |
| actual_minutes | INTEGER | Actual time spent |
| parent_task_id | INTEGER | FK to tasks (for subtasks/milestones) |
| plan_json | TEXT | JSON storing plan of action (adjustable) |
| archived | BOOLEAN | Soft-delete flag |
| archived_at | TIMESTAMP | When task was archived |

**Foreign Keys:**
- `domain_id` → `domains(id)` ON DELETE CASCADE
- `project_id` → `projects(id)` ON DELETE SET NULL
- `parent_task_id` → `tasks(id)` ON DELETE CASCADE

**Indexes:**
- `idx_tasks_status` - on status
- `idx_tasks_priority_bucket` - on priority_bucket
- `idx_tasks_status_priority` - composite (status, priority_bucket)
- `idx_tasks_due_at` - on due_at
- `idx_tasks_due_at_active` - on due_at (filtered: active tasks)
- `idx_tasks_source` - composite (source_type, source_id)
- `idx_tasks_conversation` - conversation tasks (filtered)

### task_events
Audit trail for task lifecycle events.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| task_id | INTEGER | FK to tasks |
| event_type | TEXT | created, started, blocked, unblocked, completed, abandoned, rescheduled, updated |
| event_data | TEXT | JSON with additional context |
| timestamp | TIMESTAMP | When event occurred |

**Foreign Keys:**
- `task_id` → `tasks(id)` ON DELETE CASCADE

**Indexes:**
- `idx_task_events_task_id` - on task_id
- `idx_task_events_timestamp` - on timestamp
- `idx_task_events_task_timestamp` - composite (task_id, timestamp)

### staged_tasks
Holding area for tasks captured from sources before review.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| title | TEXT | Task title |
| description | TEXT | Optional description |
| source_type | TEXT | meeting, conversation, email, manual |
| source_id | TEXT | ID from source system |
| source_context | TEXT | Relevant quote/context from source |
| suggested_domain | TEXT | AI-guessed domain name |
| suggested_project | TEXT | AI-guessed project name |
| suggested_priority | TEXT | AI-guessed priority bucket |
| captured_at | TIMESTAMP | When task was staged |
| status | TEXT | pending_review, promoted, dismissed |
| promoted_task_id | INTEGER | If promoted, links to real task ID |
| dismissed_reason | TEXT | Reason for dismissal |
| dismissed_at | TIMESTAMP | When dismissed |
| promoted_at | TIMESTAMP | When promoted |

**Indexes:**
- `idx_staged_tasks_status` - on status
- `idx_staged_tasks_source` - composite (source_type, source_id)
- `idx_staged_tasks_captured_at` - on captured_at

### day_plans
Daily task selection for focused execution.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| plan_date | TEXT | Date in YYYY-MM-DD format (unique) |
| task_ids | TEXT | Comma-separated task IDs |
| total_tasks | INTEGER | Count of tasks |
| created_at | TIMESTAMP | When plan was created |
| locked_at | TIMESTAMP | When plan was finalized |

## Views

### v_pending_tasks
All active pending/in_progress/blocked tasks with domain/project names.

**Columns:** id, title, description, status, priority_bucket, domain_name, project_name, due_at, created_at, estimated_minutes, source_type, source_id

**Query:** Tasks where status IN ('pending', 'in_progress', 'blocked') AND archived = FALSE

### v_task_latency
Analytics view for task completion metrics.

**Columns:** id, title, due_at, completed_at, created_at, domain_name, project_name, hours_overdue, hours_to_complete

**Query:** Complete tasks with calculated latency metrics

### v_tasks_today
Tasks due today or tomorrow, sorted by priority.

**Columns:** All task columns plus domain_name, project_name

**Sort Order:**
1. Priority bucket (strategic → external → urgent → normal)
2. Due date (ascending)

**Filter:** Status IN ('pending', 'in_progress', 'blocked'), archived = FALSE, due_at IS NULL OR due_at <= date('now', 'localtime', '+1 day')

## Relationships

```
domains (1) ───── (N) projects (1) ───── (N) tasks
                       │
                       └────── tasks (recursive via parent_task_id)

tasks (1) ───── (N) task_events
tasks (1) ───── (1) staged_tasks (upon promotion)
```

## Priority Buckets

1. **strategic** - High-impact, long-term goals
2. **external** - Client/partner commitments with deadlines
3. **urgent** - Time-sensitive, must happen soon
4. **normal** - Standard prioritized tasks

## Status Flow

```
pending → in_progress → complete
   ↓          ↓
 blocked ←─┘
   ↓
abandoned
```
