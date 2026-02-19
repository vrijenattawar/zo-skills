---
created: 2026-01-26
last_edited: 2026-01-26
version: 1.0
provenance: con_E0NCRSN3cUWQINKM
---

# Reasoning Examples for Task System

This document provides detailed examples of how to reason about tasks, action conversations, completion assessment, and next steps.

## Action Conversation Detection

### Example 1: Clear Action Signal

**Conversation:**
```
V: Let's draft that investor email today. Need to get it out by Friday.
```

**Reasoning:**
1. Focus: "draft investor email" → Clear deliverable (email draft)
2. Deadline: "by Friday" → Time constraint, urgency signal
3. V says "Let's draft" → Action verb, not exploration
4. Action-check returns: No matching tasks found

**Decision:** This IS an action conversation
**Action:** Create new task + tag conversation

---

### Example 2: Ambiguous - Ask for Confirmation

**Conversation:**
```
V: I've been thinking about the thought leadership post. What do you think?
```

**Reasoning:**
1. Focus: "thinking about thought leadership post" → Exploration, not doing
2. Question: "What do you think?" → Seeking input, not delivering
3. V says "thinking about" → Mental activity, not action
4. Action-check returns: Pending task "Write thought leadership post" exists

**Decision:** UNCLEAR - Could be action or exploration
**Action:** Ask "Are you working on the thought leadership post today, or just exploring ideas?"

---

### Example 3: NOT an Action Conversation

**Conversation:**
```
V: Can you explain how the task system works again?
```

**Reasoning:**
1. Focus: "explain how task system works" → Information request
2. No deliverable mentioned
3. Question format: "Can you explain?" → Not "Let's do X"
4. V is asking for understanding, not executing

**Decision:** NOT an action conversation
**Action:** No tagging, provide explanation

---

### Example 4: Explicit Action Declaration

**Conversation:**
```
V: This is an action conversation. I need to finalize the Q3 financial projections.
```

**Reasoning:**
1. V says "This is an action conversation" → Explicit declaration (non-negotiable)
2. Focus: "finalize Q3 financial projections" → Clear deliverable
3. No reasoning needed when V declares explicitly

**Decision:** IS an action conversation (by declaration)
**Action:** Tag conversation with matching task or create new task

---

## Task Completion Assessment

### Example 1: Complete - All Milestones Done

**Task:** "Draft investor email template"
**Milestones:** [1) Draft template, 2) Review with V, 3] Finalize]

**Conversation context:**
- File created: `Documents/email-drafts/investor-template.md`
- V says: "Looks good, let's use this going forward"
- Email: Sent test to self, confirmed working

**Reasoning:**
1. Milestone 1 (Draft): Template file exists ✓
2. Milestone 2 (Review): V said "Looks good" ✓
3. Milestone 3 (Finalize): Test sent and working ✓

**Assessment:** COMPLETE
**Action:** Mark task complete, log timestamp

---

### Example 2: Partial - Draft Exists, Not Finalized

**Task:** "Draft investor email template"
**Milestones:** [1) Draft template, 2) Review with V, 3) Finalize]

**Conversation context:**
- File created: `Documents/email-drafts/investor-template.md`
- No review comments from V
- No email sent

**Reasoning:**
1. Milestone 1 (Draft): Template file exists ✓
2. Milestone 2 (Review): No evidence of review ✗
3. Milestone 3 (Finalize): No email sent ✗

**Assessment:** PARTIAL
**Action:** Show assessment, ask "Mark complete or leave in-progress?"

---

### Example 3: Complete - No Milestones, Clear Delivery

**Task:** "Reply to investor email" (No milestones defined)

**Conversation context:**
- V says: "Just sent the reply, they should have it now"
- Check email log: Outbound email to investor@example.com at 2:34pm

**Reasoning:**
1. No milestones to check
2. V explicitly says "sent the reply"
3. Email log confirms delivery
4. Clear evidence of completion

**Assessment:** COMPLETE
**Action:** Mark task complete, log timestamp

---

### Example 4: Blocked - External Dependency

**Task:** "Submit proposal to client"
**Milestones:** [1) Draft proposal, 2) Internal review, 3) Submit]

**Conversation context:**
- File created: Draft proposal exists
- Internal review: Done, feedback incorporated
- V says: "Can't submit until client provides the budget spreadsheet"
- Task notes: "Waiting for client budget info"

**Reasoning:**
1. Milestone 1 (Draft): Done ✓
2. Milestone 2 (Review): Done ✓
3. Milestone 3 (Submit): Blocked by external dependency ✗
4. V cannot proceed without client input

**Assessment:** BLOCKED
**Action:** Update task status to blocked, log blocker, ask "Should I follow up with client?"

---

### Example 5: Complete - Implicit Completion

**Task:** "Organize notes from client meeting"

**Conversation context:**
- Files created: `Personal/Meetings/2026-01-25-client-meeting/notes.md`
- Files created: `Personal/Meetings/2026-01-25-client-meeting/action-items.md`
- V says: "Got the notes organized, everything filed away"

**Reasoning:**
1. V says "Got the notes organized" → Clear completion statement
2. Evidence: Meeting folder with structured notes exists
3. No explicit "done" but clear from context

**Assessment:** COMPLETE
**Action:** Mark task complete

---

## Next Step Inference

### Example 1: Task with Milestones

**Task:** "Launch <YOUR_PRODUCT> newsletter"
**Status:** Draft created
**Milestones:** [1) Write 3 articles, 2) Design template, 3) Test send, 4) Launch]

**Reasoning:**
1. Current progress: Draft created (likely milestone 1)
2. Next incomplete milestone: Milestone 2 (Design template)
3. Task type: Creative + technical

**Next Step:** Design email template using the drafted content

**Estimated:** 45-60 min (design work)
**Energy:** High (creative + technical)

---

### Example 2: Email Task, No Milestones

**Task:** "Reply to investor email"
**Status:** New, no work done

**Reasoning:**
1. Task type: Email communication
2. Current state: Not started
3. Context: Needs professional tone, specific points to address

**Next Step:** Draft reply covering the 3 key points from original email

**Estimated:** 20 min (writing)
**Energy:** Medium (requires focus, not too complex)

---

### Example 3: Stale Task, Needs Refresh

**Task:** "Update CRM with new leads"
**Status:** In-progress, last activity 7 days ago

**Reasoning:**
1. Current state: Partially done, but stale
2. Context: 7 days without progress
3. Task type: Data entry, not high-cognitive

**Next Step:** Quick review of what's done, continue with remaining 15 leads

**Estimated:** 30 min (finish the batch)
**Energy:** Low (can do during energy dips)

---

### Example 4: Blocked Task

**Task:** "Submit Q3 financial projections"
**Status:** Blocked, waiting for client budget

**Reasoning:**
1. Current state: Blocked by external dependency
2. Context: Cannot proceed without client input
3. Actionable next: Follow up with client or work around blocker

**Next Step:** Send follow-up email to client requesting budget spreadsheet

**Estimated:** 10 min (short email)
**Energy:** Low (quick admin task)

---

### Example 5: Writing Task, Needs Polish

**Task:** "Write thought leadership post on career transitions"
**Status:** Draft started, 800 words

**Reasoning:**
1. Current state: Draft exists but needs polish
2. Task type: Creative writing
3. Context: 800 words is solid start, needs editing + examples

**Next Step:** Review draft, add 2 client examples, polish intro/conclusion

**Estimated:** 45 min (editing + examples)
**Energy:** High (creative, needs good focus)

---

## Task Extraction from Meetings

### Example 1: Clear Action Item

**Action Item:** "Draft follow-up email to investors regarding Q3 update"

**Extraction:**
- title: "Draft investor follow-up email"
- first_step: "Open email template and customize for Q3 update"
- priority_bucket: external (investors waiting)
- domain: <YOUR_PRODUCT>
- owner: V
- estimated_minutes: 20

**Quality Check:** Actionable? Yes. Specific? Yes. For V? Yes. Worth tracking? Yes.

---

### Example 2: Vague Action Item

**Action Item:** "Think about thought leadership topics"

**Extraction:**
- Problem: "Think about" is not actionable
- Refinement: "Brainstorm 5 thought leadership topics" or "Outline next post"
- If can't clarify: Skip or ask V for clarification

---

### Example 3: Multi-Step Action Item

**Action Item:** "Prepare for investor meeting next week: agenda, data deck, financial projections"

**Extraction:**
- title: "Prepare for investor meeting"
- first_step: "Create meeting agenda with key discussion points"
- priority_bucket: external (scheduled meeting)
- domain: <YOUR_PRODUCT>
- owner: V
- estimated_minutes: 180 (multi-step task)

**Note:** Break into sub-tasks later if needed, but keep as one task for now.

---

### Example 4: Not for V

**Action Item:** "Sarah to send over the marketing budget"

**Extraction:**
- owner: Sarah (not V)
- Decision: Skip extraction (only track V's tasks)

---

### Example 5: Minor Item, Not Worth Tracking

**Action Item:** "Reply to Dave's Slack message"

**Extraction:**
- Low priority, quick task
- Decision: Skip (not worth tracking in task system)

**Alternative:** Just do it immediately if it takes < 2 minutes.
