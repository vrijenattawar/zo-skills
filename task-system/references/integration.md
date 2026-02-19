---
created: 2026-01-26
last_edited: 2026-01-26
version: 1.0
provenance: con_E0NCRSN3cUWQINKM
---

# Integration Patterns for Task System

This document documents how the task system integrates with other skills, scheduled agents, and Zo workflows.

## thread-close Integration

### Flow
1. Conversation closes (V says "done", "that's it", or timeout)
2. thread-close skill calls:
   ```bash
   python3 Skills/task-system/scripts/context.py completion-check --convo-id con_xxx
   ```
3. Returns: Task details, milestones, conversation artifacts, content summary
4. thread-close (AI) assesses completion status:
   - complete: All milestones done OR clear delivery evidence
   - partial: Some progress, more work needed
   - blocked: External dependency
5. thread-close shows assessment to V with confirmation prompt
6. If V confirms complete: thread-close calls:
   ```bash
   python3 Skills/task-system/scripts/task.py complete <task-id>
   ```

### Example Integration

**thread-close skill logic:**
```python
# Check if conversation is tagged as action conversation
action_check_result = run_action_check(convo_id)

if action_check_result["is_action_conversation"]:
    task_id = action_check_result["task_id"]

    # Get completion context
    completion_context = run_completion_check(convo_id, task_id)

    # AI assesses completion
    assessment = assess_completion(completion_context)

    # Show to V
    show_assessment(assessment)

    # If confirmed
    if v_confirms_complete():
        mark_task_complete(task_id)
```

### Edge Cases
- No task found: Skip completion check
- Multiple tasks: Ask V which task(s) were addressed
- Task already complete: Show confirmation, skip update
- Partial work: Ask "Mark complete or keep in-progress?"

---

## meeting-ingestion Integration

### Flow
1. meeting-ingestion processes meeting transcript
2. Looks for B05_ACTION_ITEMS blocks in processed meeting files
3. For each B05 block, calls:
   ```bash
   python3 Skills/task-system/scripts/context.py extract-tasks --file <B05 path>
   ```
4. Returns: List of extracted tasks with structured fields
5. meeting-ingestion (AI) reviews extracted tasks
6. Stages tasks in review queue (not auto-created)
7. Shows V the staged tasks with "Create these?" confirmation

### Example Integration

**meeting-ingestion skill logic:**
```python
# After processing meeting files
for b05_file in find_b05_blocks(meeting_dir):
    extracted_tasks = run_extract_tasks(b05_file)

    # Review and filter
    filtered_tasks = review_for_v(extracted_tasks)

    # Stage for review
    stage_tasks_for_review(filtered_tasks)

    # Show to V
    show_staged_tasks()
```

### B05 Block Format
```markdown
## B05_ACTION_ITEMS
- Draft follow-up email to investors
- Prepare for investor meeting next week
- Think about thought leadership topics (vague)
- Sarah to send budget (not for V)
```

### Edge Cases
- Vague items: Filter out or ask for clarification
- Non-V tasks: Skip in extraction
- Duplicate tasks: Check existing tasks before creating
- Too many tasks: Group into "Prepare for meeting" meta-task

---

## Morning Briefing Integration

### Flow
1. Scheduled agent triggers at V's preferred time (e.g., 8:30am)
2. Agent runs:
   ```bash
   python3 Skills/task-system/scripts/briefing.py morning
   ```
3. Returns: Today's focus, next steps, blocked items, overview
4. Agent sends briefing to V via SMS/email
5. V reviews and sets priorities for the day

### Example Scheduled Agent

**Agent configuration:**
```yaml
name: Morning Briefing
schedule: "0 8 * * *"  # 8am daily
delivery_method: email
instruction: |
  Run morning briefing and send to V. Format:
  - Today's Focus (3-5 tasks)
  - Next Steps for each
  - Blocked items
  - Energy-based task suggestions
```

**Agent logic:**
```python
# Generate briefing
briefing = run_morning_briefing()

# Send to V
send_email_to_user(
    subject=f"Morning Briefing - {date}",
    markdown_body=format_briefing(briefing)
)
```

### Briefing Format
```markdown
# Morning Briefing - Jan 26

## Today's Focus

### External (Urgent)
- **Reply to investor email** [20m]
  Next: Draft covering Q3 update points
  Energy: Medium

### Strategic (Deep Work)
- **Write thought leadership post** [45m]
  Next: Add client examples, polish intro
  Energy: High

### Normal (Fill gaps)
- **Organize notes** [30m]
  Next: File client meeting notes into proper folders
  Energy: Low

## Blocked Items
- Submit Q3 financial projections
  Blocker: Waiting for client budget spreadsheet
  Action: Follow up with client

## Overview
5 pending tasks, 1 blocked
Yesterday completed: 3 tasks
```

---

## Evening Accountability Integration

### Flow
1. Scheduled agent triggers at V's preferred time (e.g., 9:30pm)
2. Agent runs:
   ```bash
   python3 Skills/task-system/scripts/briefing.py evening
   ```
3. Returns: Completed tasks, incomplete tasks, blockers, progress summary
4. Agent sends accountability to V via SMS/email
5. V rates progress and identifies tomorrow's focus

### Example Scheduled Agent

**Agent configuration:**
```yaml
name: Evening Accountability
schedule: "0 21 * * *"  # 9pm daily
delivery_method: email
instruction: |
  Run evening accountability and send to V. Ask:
  - Rate progress (1-5)
  - What blocked you today?
  - Top priority for tomorrow?
```

### Accountability Format
```markdown
# Evening Accountability - Jan 26

## Completed Today ✅
- Draft investor email template
- Review thought leadership draft
- Organize meeting notes

## In Progress
- Write thought leadership post (partial: draft done)

## Blocked
- Submit Q3 financial projections
  Blocked: Waiting for client budget

## Progress
3 tasks completed today
5 tasks remain pending

### Rate Your Day
How would you rate today's productivity? (1-5)
What blocked you today?
What's your top priority for tomorrow?
```

---

## Follow-Up Agent Integration

### Flow
1. Scheduled agent runs daily at 10am
2. Checks for tasks stuck in "partial" status for > 3 days
3. For each stale task, prompts V:
   - "Still working on [task]?"
   - "Should I mark complete?"
   - "Should I break into smaller tasks?"

### Example Logic
```python
# Find stale tasks
stale_tasks = find_tasks_in_partial_status(days=3)

# Prompt V for each
for task in stale_tasks:
    prompt = f"""
    Task: {task['title']}
    Status: Partial (since {task['last_updated']})

    Still working on this?
    1. Yes, keep going
    2. Mark complete
    3. Break into smaller tasks
    4. Defer to later
    """

    response = ask_v(prompt)
    handle_response(response, task['id'])
```

---

## Direct CLI Integration

### When V Uses Task System Directly

**Scenario:** V runs commands directly via terminal or prompts Zo to run them

**Example commands:**
```bash
# Add task
python3 Skills/task-system/scripts/task.py add "Write memo on remote work" --domain <YOUR_PRODUCT>

# List tasks
python3 Skills/task-system/scripts/task.py list --status pending

# Complete task
python3 Skills/task-system/scripts/task.py complete 5

# Get next step
python3 Skills/task-system/scripts/context.py next-step --task-id 5
```

**Zo's role:**
- Provide command help when V asks "How do I add a task?"
- Run commands when V says "Mark task 5 complete"
- Interpret results and explain to V in plain language

---

## Calendar Integration (Future)

### Planned Flow
1. Calendar events tagged with "task:" prefix
2. Agent scans calendar for task-tagged events
3. Automatically creates tasks from calendar items
4. Syncs task deadlines with calendar reminders

**Example:**
- Calendar event: "Task: Submit proposal by Friday"
- Auto-creates task with deadline
- Sets calendar reminder for Thursday evening

---

## Error Handling

### Task System Errors

**Error:** Task not found
- Action: Check if task ID is correct, show list of tasks
- User message: "Task 5 not found. Here are your pending tasks:"

**Error:** Database locked
- Action: Retry with backoff, or show "System busy, try again"

**Error:** Invalid domain
- Action: Show valid domains (<YOUR_PRODUCT>, zo, personal)

### Integration Errors

**Error:** Cannot tag conversation (no SESSION_STATE)
- Action: Create SESSION_STATE first, then tag

**Error:** Context script fails
- Action: Show error, fallback to manual assessment

---

## Performance Considerations

### Cache Frequently Used Data
- Morning briefing caches task list for 1 hour
- Context check results cached within conversation

### Batch Operations
- Meeting extraction processes all B05 blocks in one call
- Briefing aggregates all tasks in single DB query

### Async for External APIs
- Calendar integration (future) uses async calls
- Email sending is non-blocking

---

## Future Integrations

### Planned
- **CRM sync**: Update CRM when tasks marked complete
- **Notion integration**: Sync tasks to Notion database
- **GitHub Issues**: Sync dev tasks to GitHub issues
- **Time tracking**: Track actual time spent on tasks

### Extensibility
- New skills can hook into task system via scripts/context.py
- Custom priority buckets can be added
- Custom briefing templates can be created
