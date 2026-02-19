# Thread-Close + Task System Integration Test Scenario

## Overview
This document describes the full flow of integrating thread-close with the new task-system Skill, demonstrating how action conversation detection and task completion assessment work end-to-end.

## Test Scenario

### 1. Conversation Start: Action Detection

**Scenario:** User starts a conversation with clear action intent

**User Message:** "Let's draft the investor memo for Q4 review"

**Expected Flow:**
1. `SESSION_STATE.md` initialized at conversation start
2. At start, run: `python3 Skills/task-system/scripts/context.py action-check --convo-id con_TEST001`
3. Context script returns matching tasks (if any exist) or indicates potential new task
4. AI reasons: "This is an action conversation - drafting specific deliverable"
5. If task exists: `python3 Skills/task-system/scripts/task.py tag-conversation --convo-id con_TEST001 --task-id 42`
6. Add to SESSION_STATE.md: `task_id: 42`

---

### 2. Conversation End: Thread-Close Execution

**Scenario:** User finishes work and thread-close is invoked

**Step 1: Gather Context**
```bash
python3 Skills/thread-close/scripts/close.py --convo-id con_TEST001
```

**Expected Output (from `gather_thread_context()`):**
```json
{
  "convo_id": "con_TEST001",
  "tier": 2,
  "artifacts": [
    {
      "path": "/home/.z/workspaces/con_TEST001/investor-memo-v1.md",
      "name": "investor-memo-v1.md",
      "size": 4532
    }
  ],
  "task_info": {
    "task_id": 42,
    "matching_tasks": [{"id": "42", "title": "Draft Q4 investor memo"}],
    "completion_context": null,
    "next_step": null,
    "suggested_action": null
  }
}
```

---

### 3. Get Completion Context

**Action:** AI calls context script to gather task completion data

```bash
python3 Skills/task-system/scripts/context.py completion-check --convo-id con_TEST001 --task-id 42
```

**Expected Output:**
```json
{
  "task": {
    "id": 42,
    "title": "Draft Q4 investor memo",
    "status": "in_progress",
    "plan": {
      "milestones": [
        {"description": "Research Q4 metrics"},
        {"description": "Draft memo structure"},
        {"description": "Write full draft"},
        {"description": "Review and polish"}
      ]
    }
    }
  },
  "conversation_artifacts": [
    {
      "name": "investor-memo-v1.md",
      "path": "/home/.z/workspaces/con_TEST001/investor-memo-v1.md",
      "content_preview": "Q4 Update for Investors..."
    }
  ],
  "delivery_evidence": [
    "File created: investor-memo-v1.md",
    "Draft appears complete (4,532 bytes)"
  ]
}
```

---

### 4. AI Reasons About Completion

**Input:** Completion context from step 3

**AI Analysis:**
1. Review task milestones:
   - ✅ Research Q4 metrics (evidence in conversation)
   - ✅ Draft memo structure (file created)
   - ✅ Write full draft (investor-memo-v1.md exists)
   - ❌ Review and polish (no explicit confirmation)

2. Check delivery evidence:
   - File `investor-memo-v1.md` created (4.5KB)
   - Content preview shows substantial draft
   - No "sent" or "finalized" keywords found

3. **Assessment:** `PARTIAL`

---

### 5. Show Assessment to User

**Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK: Draft Q4 investor memo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Status: 🟡 PARTIAL

Milestones Completed:
  ✅ Research Q4 metrics
  ✅ Draft memo structure
  ✅ Write full draft

Milestones Remaining:
  ⬜ Review and polish

Evidence:
  • File created: investor-memo-v1.md (4.5KB)
  • Draft content appears substantial
  • No explicit "review complete" confirmation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mark as:
  [complete]    Draft is ready
  [partial]     Needs review before complete
  [blocked]      Cannot proceed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 6. User Chooses Action

**Case A: User selects "partial"**
```bash
python3 Skills/task-system/scripts/task.py update 42 --status in_progress
```

**Then get next step:**
```bash
python3 Skills/task-system/scripts/context.py next-step --task-id 42
```

**Output to user:**
```
NEXT STEP: Review and polish the investor memo

Estimated time: 30-45 minutes
Energy level: Medium (review work, attention to detail)
```

**Thread-close writes CLOSE_OUTPUT.json with task status noted.**

---

**Case B: User selects "complete"**
```bash
python3 Skills/task-system/scripts/task.py complete 42 --actual 90
```

**Thread-close writes CLOSE_OUTPUT.json, marks task complete.**

---

### 7. Thread Close Finalizes

**Step 1: Write CLOSE_OUTPUT.json**
```json
{
  "convo_id": "con_TEST001",
  "tier": 2,
  "title": "Jan 26 | ✅ 📌 ✍️ [Investor Work] Q4 Memo Draft",
  "summary": "Drafted Q4 investor memo with metrics and projections. File created but pending final review.",
  "decisions": [
    {
      "decision": "Mark task as partial, schedule review",
      "rationale": "Draft exists but milestone for review/polish not completed"
    }
  ],
  "next_steps": [
    "Review investor-memo-v1.md for polish",
    "Add executive summary section",
    "Schedule follow-up conversation for final review"
  ],
  "task_status_update": {
    "task_id": 42,
    "old_status": "in_progress",
    "new_status": "in_progress",
    "action": "update"
  }
}
```

**Step 2: Run PII audit**
- `pii.audit_conversation("con_TEST001")` called automatically

**Step 3: Close reported:**
```
✓ Title: Jan 26 | ✅ 📌 ✍️ Q4 Memo Draft
✓ Decisions extracted: 1
✓ Next steps: 3
✓ Task #42 updated to: in_progress
✓ PII audit complete

Thread close complete (Tier 2)
```

---

## Key Differences from Old System

| Aspect | Old (close_hooks.py) | New (task-system Skill) |
|---------|----------------------|------------------------|
| **Detection** | Regex pattern matching | `context.py` gathers data + AI reasoning |
| **Assessment** | Regex patterns for delivery evidence | `context.py completion-check` + semantic reasoning |
| **Next Steps** | Inferred from task patterns | `context.py next-step` + AI reasoning |
| **Integration** | Direct function calls | Subprocess calls to skill scripts |
| **Accuracy** | Brittle, false positives | Flexible, understands context |

---

## Error Handling

### Scenario: Task Not Found

```bash
python3 Skills/task-system/scripts/context.py completion-check --convo-id con_TEST001 --task-id 999
```

**Expected Output:**
```json
{
  "error": "Task not found",
  "task_id": 999
}
```

**Fallback:** AI continues thread-close without task integration, adds note to CLOSE_OUTPUT.json.

---

### Scenario: Task System Unavailable

```python
# In gather_thread_context():
try:
    result = subprocess.run(['python3', './Skills/task-system/scripts/context.py', ...])
except Exception as e:
    return {'is_action_conversation': False, 'error': str(e)}
```

**Behavior:** Thread-close proceeds normally, logs warning in CLOSE_OUTPUT.json:
```json
{
  "warnings": [
    "Task system unavailable: context.py failed to execute"
  ]
}
```

---

## Testing Checklist

- [ ] Start action conversation, verify context script returns matching tasks
- [ ] Tag conversation to task via `task.py tag-conversation`
- [ ] Run thread-close, verify task_info in context
- [ ] Get completion context, verify artifacts returned
- [ ] Show assessment, verify milestone tracking
- [ ] Test "complete" flow, verify task marked complete
- [ ] Test "partial" flow, verify next step returned
- [ ] Test error scenarios (not found, unavailable)
- [ ] Verify CLOSE_OUTPUT.json includes task_status_update
- [ ] Verify PII audit runs successfully
