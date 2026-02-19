---
name: text-to-diagram
description: |
  Transform text corpora (articles, docs, ideas, decisions) into Excalidraw-ready diagrams 
  through a Socratic dialogue process. Analyzes content for visualizable concepts, engages 
  in clarifying dialogue, then generates hybrid output (Mermaid for flowcharts, raw 
  Excalidraw JSON for other diagram types). Designed for V's visual thinking and 
  communication needs.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  version: "1.0"
  created: "2026-02-06"
---

# Text-to-Diagram Skill

Transform text into Excalidraw diagrams through structured Socratic dialogue.

## Philosophy

This skill treats diagram generation as a **collaborative sense-making process**, not a one-shot transformation. The AI:
1. Studies the corpus to identify what's visualizable
2. Engages in Socratic dialogue to clarify your intent
3. Surfaces conceptual gaps or ambiguities
4. Only generates output after systematic completion

## When to Use

- **Articles/docs** → Visual summaries or concept breakdowns
- **Your ideas** → Sketched-out thinking aids
- **Difficult decisions** → Decision trees, tradeoff matrices, comparison charts
- **Meeting notes** → Process flows, relationship maps
- **Complex systems** → Architecture diagrams, state machines

## Workflow Phases

### Phase 1: Analysis
AI reads the corpus and identifies:
- Visualizable concepts (processes, hierarchies, relationships, comparisons, timelines)
- Diagram type recommendations
- Entities, relationships, and flows

**Output:** Analysis summary + diagram candidates

### Phase 2: Socratic Clarification
AI asks clarifying questions:
- "What's the primary audience for this diagram?"
- "Should X be shown as a process or a hierarchy?"
- "I see A and B as related — is that causal, temporal, or categorical?"
- "What level of detail do you want?"

**Goal:** Ensure the diagram serves your actual intent

### Phase 3: Gap Filling
AI surfaces uncertainties:
- "The text doesn't specify whether X happens before or after Y"
- "There are three possible interpretations of this relationship"
- "This concept is mentioned but never defined — should we include it?"

**Goal:** Fill conceptual holes before rendering

### Phase 4: Generation
Only after phases 1-3 are complete:
- Generate Mermaid code (for flowcharts — native Excalidraw rendering)
- Generate Excalidraw JSON (for other diagram types — full hand-drawn aesthetic)
- Provide import instructions

## Invocation

### Interactive Mode (Recommended)
Simply tell Zo:
```
"Run the text-to-diagram skill on this document"
"Diagram this article for me"
"Turn these meeting notes into a visual"
```

Zo will:
1. Read the corpus (file, pasted text, or URL)
2. Run analysis
3. Begin Socratic dialogue
4. Generate output after completion

### Script Mode
For batch processing or automation:
```bash
python3 Skills/text-to-diagram/scripts/analyze.py --input <file> --output <dir>
```

## Output Formats

### Mermaid (.mmd)
Best for: **Flowcharts only** (native hand-drawn rendering in Excalidraw)
```
flowchart TD
  A[Input] --> B{Decision}
  B -->|Yes| C[Action 1]
  B -->|No| D[Action 2]
```

**To use:** Paste into Excalidraw's Mermaid tab

### Excalidraw JSON (.excalidraw)
Best for: **Everything else** (mindmaps, ER diagrams, custom layouts, comparisons)
- Full control over positioning, styling, colors
- Native hand-drawn aesthetic for all shapes
- Direct import into Excalidraw

**To use:** File → Open in Excalidraw

## Diagram Type Selection

| Content Pattern | Diagram Type | Format |
|-----------------|--------------|--------|
| Steps, processes, workflows | Flowchart | Mermaid |
| Decisions with branches | Decision Tree | Mermaid |
| Cause → Effect chains | Causal Flow | Mermaid |
| Hierarchies, taxonomies | Tree / Mindmap | Excalidraw JSON |
| Entity relationships | ER-style | Excalidraw JSON |
| Comparisons, tradeoffs | Matrix / Quadrant | Excalidraw JSON |
| Timelines, sequences | Timeline | Excalidraw JSON |
| System components | Architecture | Excalidraw JSON |
| States and transitions | State Diagram | Excalidraw JSON |

## Aesthetic Defaults

All diagrams target the **<YOUR_GITHUB>.com dark aesthetic**:
- Background: `#000000` (or transparent)
- Stroke: `#ffffff` or muted grays
- Fill: Minimal, dark tones
- Font: Excalidraw hand-drawn (Virgil)
- Theme: Dark mode

## Examples

### Example 1: Article → Concept Map
**Input:** A long article about AI agents
**Analysis:** "I found 4 key concepts: autonomy, tool use, memory, and planning. They form a hierarchy with 'agent' at the root."
**Socratic:** "Should this emphasize the relationships between concepts, or the hierarchy?"
**Output:** Excalidraw JSON mindmap

### Example 2: Decision → Tradeoff Matrix
**Input:** "I'm deciding between staying at my job, starting a company, or joining a startup"
**Analysis:** "This is a comparison of 3 options across multiple criteria"
**Socratic:** "What criteria matter most? Risk tolerance? Financial upside? Learning?"
**Output:** Excalidraw JSON quadrant chart or comparison matrix

### Example 3: Process Doc → Flowchart
**Input:** A document describing an onboarding workflow
**Analysis:** "I found a 7-step sequential process with 2 decision points"
**Socratic:** "Should exceptions and error cases be shown, or just the happy path?"
**Output:** Mermaid flowchart

## Technical Notes

### Mermaid Limitations in Excalidraw
Only **flowcharts** render natively. Other Mermaid types (sequence, class, ER, gantt) become rasterized images — defeating the hand-drawn aesthetic. That's why we use raw Excalidraw JSON for non-flowchart diagrams.

### Excalidraw JSON Schema
Elements include: `rectangle`, `ellipse`, `diamond`, `arrow`, `line`, `text`, `freedraw`

Each element has:
- `id`, `type`, `x`, `y`, `width`, `height`
- `strokeColor`, `fillColor`, `backgroundColor`
- `strokeWidth`, `roughness` (0=smooth, 2=sketchy)
- For arrows: `startBinding`, `endBinding` (to connect shapes)

### References
- Mermaid syntax: `references/mermaid-syntax.md`
- Excalidraw JSON schema: `references/excalidraw-schema.md`
- Diagram type taxonomy: `references/diagram-taxonomy.md`
