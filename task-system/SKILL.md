---
name: task-system
description: |
  ADHD-optimized task management system for Zo. Handles task registry,
  morning/evening briefings, action conversation tracking, and staged task review.
  Uses LLM reasoning for semantic understanding, Python for data operations.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
---

# Task System Skill

## Overview

The task system manages V's work with ADHD-optimized workflows: it tracks tasks, generates morning/evening briefings, detects action conversations, and assesses completion. This skill combines Python scripts (for fast data operations) with AI reasoning (for semantic understanding).

**Core principle:** Scripts gather context, AI reasons semantically.

**When to activate this skill:**
- At conversation start: Check if this is an action conversation
- At conversation close: Assess task completion (via thread-close integration)
- Morning briefing: Generate today's focus and next steps
- Evening accountability: Review what was accomplished
- Meeting processing: Extract action items from B05_ACTION_ITEMS blocks

## Quick Start

```bash
# Task operations
python3 Skills/task-system/scripts/task.py add "Task title" --domain <YOUR_PRODUCT>
python3 Skills/task-system/scripts/task.py list --status pending
python3 Skills/task-system/scripts/task.py complete 5

# Context for AI reasoning
python3 Skills/task-system/scripts/context.py action-check --convo-id con_xxx
python3 Skills/task-system/scripts/context.py completion-check --convo-id con_xxx --task-id 5

# Briefings
python3 Skills/task-system/scripts/briefing.py morning
python3 Skills/task-system/scripts/briefing.py evening
```

## Daily Report Workflow

The task system uses a **single daily markdown file** as the source of truth for each day's work. This provides:
- A file you can open and check off tasks manually
- Automatic sync from checkboxes to the database
- A persistent record of each day's planning and outcomes

**Location:** `N5/reports/daily/tasks/YYYY-MM-DD.md`

### The Daily Flow

1. **Morning (7am)**: Generate today's tasks with checkboxes
   ```bash
   python3 Skills/task-system/scripts/briefing.py morning --save
   ```
   Creates: `N5/reports/daily/tasks/2026-01-26.md`

2. **During Day**: Open the file, check boxes as you complete tasks
   ```markdown
   - [x] #42 **Draft investor memo** (30min) — <YOUR_PRODUCT>
   - [ ] #43 **Review competitor pricing** (20min) — <YOUR_PRODUCT>
   ```

3. **Evening (9pm)**: Sync completions and append accountability report
   ```bash
   python3 Skills/task-system/scripts/briefing.py evening --save
   ```
   - Reads checkboxes → marks checked tasks complete in DB
   - Appends evening summary to the same file

### Checkbox Format

```markdown
- [ ] #ID **Task Title** (estimated_minutes) — Domain/Project
```

- `- [ ]` = unchecked (pending)
- `- [x]` = checked (complete)
- `#ID` = task ID in database (required for sync)
- Time and context are optional but helpful

### CLI Reference

```bash
# Morning briefing
briefing.py morning              # Print to stdout
briefing.py morning --save       # Save to daily report
briefing.py morning --capacity 4 # Limit to 4 tasks

# Evening accountability
briefing.py evening              # Print to stdout (syncs checkboxes first)
briefing.py evening --save       # Append to daily report
briefing.py evening --no-sync    # Skip checkbox sync (just report)

# Staged task review
briefing.py staged               # Show tasks awaiting promotion
```

### Manual Task Addition

You can also add tasks directly to the daily report file:
```markdown
- [ ] #new **Ad-hoc task I need to do** (15min)
```
Note: Tasks with `#new` or without an ID won't sync to DB automatically.
To add them properly, use:
```bash
python3 Skills/task-system/scripts/task.py add "Task title" --domain <YOUR_PRODUCT>
```

## Action Conversation Detection

**When to check:** At conversation start (after SESSION_STATE init)

**How to reason:**

1. Run `context.py action-check --convo-id <id>` to get context about recent conversations and pending tasks
2. Look at the returned context and the current conversation's focus
3. Ask yourself:
   - Does the focus/objective describe doing specific work with a clear deliverable?
   - Is there an existing pending task that matches what V is discussing?
   - Did V explicitly say "this is an action conversation" or "log this as a task"?
4. If YES: Tag with `task.py tag-conversation --convo-id <id> --task-id <id>`
5. If UNSURE: Ask V "Are you working on [task title]?" to confirm

**Signals of action conversation:**
- Focus mentions specific deliverables: "draft", "write", "send", "build", "fix", "create"
- V references a specific task or mentions a deadline/commitment
- Matches an existing pending task in the registry
- V says "let's knock out", "need to get this done", "let's do X"

**NOT action conversations:**
- Research/exploration: "What do you know about X?", "Look into this"
- Planning/strategy discussions: "How should I approach X?", "What are the options?"
- General questions: "How do I do X?", "Explain this concept"
- System maintenance: "Check my calendar", "Review my notes"

## Task Completion Assessment

**When to check:** At conversation close (integrated into thread-close skill)

**How to reason:**

1. Run `context.py completion-check --convo-id <id> --task-id <id>` to get:
   - Task details and milestones
   - Conversation artifacts (files created, emails sent)
   - Conversation content for delivery evidence

2. Compare task milestones against conversation outcomes:
   - Did V complete all milestones?
   - Were there artifacts created that match task intent?
   - Is there clear evidence of delivery?

3. Look for delivery evidence:
   - Files created: Drafts, memos, code, documentation
   - Emails sent: Check for outbound communications
   - Explicit statements: V saying "done", "complete", "finished"
   - External actions: Deployments, submissions, confirmations

4. Assess status:
   - **complete**: All milestones done OR clear delivery evidence
   - **partial**: Some progress, but more work needed
   - **blocked**: Cannot proceed due to external dependency or blocker

**Show V the assessment and ask for confirmation before updating.**

Example assessment:
```
Task: "Draft investor email template"
Status: PARTIAL

Milestones completed:
✓ Draft template created
✗ Review with V

Delivery evidence:
- Created: file 'Documents/email-drafts/investor-template.md'
- No explicit confirmation of final approval

Assessment: Draft exists but needs review before marking complete.

Should I mark as complete or leave as in-progress?
```

## Next Step Inference

**When to use:**
- Morning briefing: Generate next steps for today's focus
- After partial completion: What's the next action?
- "What next?" queries: V asks for guidance on a task

**How to reason:**

1. Run `context.py next-step --task-id <id>` to get task context
2. If milestones defined: The next incomplete milestone is the next step
3. If no milestones: Reason about task type and current state:
   - Email task → "Review draft, then send"
   - Memo task → "Polish draft, get feedback, finalize"
   - Build task → "Test current state, identify gaps"
   - Research task → "Synthesize findings, extract key points"

4. Consider context factors:
   - How long since last activity? (If stale, may need fresh start)
   - Are there blockers logged in the task?
   - What's V's current energy/capacity? (Match step size to energy)

Example next steps:
```
Task: "Write thought leadership post on career transitions"
Status: Draft started
Next step: Review draft, add examples from client work, finalize intro

Estimated time: 30-45 min
Energy level: Medium (creative thinking + writing)
```

## Task Extraction from Meetings

**When to use:**
- Processing B05_ACTION_ITEMS blocks from meeting-ingestion skill
- Converting meeting notes into actionable tasks

**How to reason:**

1. Run `context.py extract-tasks --file <B05 path>` to get action items
2. For each action item, extract and structure:
   - **title**: Clear, actionable task name (2-6 words max)
   - **first_step**: The immediate next action (2-5 min to start)
   - **priority_bucket**: strategic|external|urgent|normal
   - **domain**: Infer from meeting context (<YOUR_PRODUCT>, zo, personal)
   - **owner**: V or someone else? (Only extract V's tasks)
   - **estimated_minutes**: Reasonable estimate (be generous)

3. Quality checks:
   - Is it actionable? (Not "think about X", but "Draft X")
   - Is it specific? (Not "prep for meeting", but "Create agenda for investor meeting")
   - Is it for V? (Skip tasks for other attendees)
   - Is it worth tracking? (Don't capture minor items like "follow up via Slack")

4. Stage tasks for review: Don't auto-create. Show V the extracted tasks and ask for confirmation.

Example extraction:
```
Action Item: "Draft follow-up email to investors"
Extracted task:
  title: "Draft investor follow-up email"
  first_step: "Open email template and customize for Q3 update"
  priority_bucket: external
  domain: <YOUR_PRODUCT>
  owner: V
  estimated_minutes: 20
```

## Priority Buckets

| Bucket | When to use | Examples |
|--------|-------------|----------|
| strategic | Long-term value, aligns with V's goals | "Write thought leadership post", "Build lead magnet" |
| external | Someone else waiting, has deadline | "Reply to investor email", "Submit proposal by Friday" |
| urgent | Time-sensitive, blocking other work | "Client deliverable due tomorrow", "Fix broken production issue" |
| normal | Everything else, steady progress | "Organize notes", "Review calendar", "Update CRM" |

**Priority drives briefings:**
- External/urgent tasks appear at top of morning briefing
- Strategic tasks get spotlight for deep work sessions
- Normal tasks fill in gaps

## Integration Points

### thread-close Integration
- When conversation closes, thread-close skill calls completion-check
- Shows assessment to V with "Mark complete?" confirmation
- If confirmed: Updates task status, logs completion timestamp

### meeting-ingestion Integration
- When processing meeting transcripts, looks for B05_ACTION_ITEMS blocks
- Calls extract-tasks to convert action items into structured tasks
- Stages extracted tasks for review (not auto-created)

### Morning Briefing
- Runs `briefing.py morning` at scheduled time
- Shows: Today's focus (3-5 tasks), next steps for each, blocked items
- Pulls from: External/urgent (always), Strategic (if deep work time), Normal (gaps)

### Evening Accountability
- Runs `briefing.py evening` at scheduled time
- Shows: Tasks completed today, incomplete tasks, blockers
- Asks V to rate progress and identify tomorrow's focus

### Scheduled Agents
- Morning agent: Runs briefing.py, sends to V via SMS/email
- Evening agent: Runs briefing.py, logs accountability data
- Follow-up agent: Checks on tasks stuck in "partial" for > 3 days

## Scripts Reference

- `scripts/task.py`: CRUD operations, status updates, conversation tagging
- `scripts/context.py`: Context gathering for AI reasoning (action-check, completion-check, etc.)
- `scripts/briefing.py`: Morning/evening briefing generation
- `scripts/db.py`: Database operations (usually called by other scripts)
- `scripts/stage.py`: Stage tasks for review (meeting extraction, manual entry)

## Reasoning Discipline

This skill relies on semantic understanding, not regex patterns. The scripts provide data (task records, milestones, artifacts), but YOU provide the intelligence:

- **Action detection**: Use semantic understanding of conversation focus, not keyword matching
- **Completion assessment**: Look for evidence of delivery, not just keywords
- **Next steps**: Reason about task type, current state, and V's capacity
- **Task extraction**: Convert vague action items into structured, actionable tasks

**Always ask:** "What does V actually need to do to make progress here?" - that's the next step.

## References

- `references/schema.md`: Database schema and task structure
- `references/reasoning.md`: Detailed examples and edge cases
- `references/integration.md`: Integration patterns with other skills
