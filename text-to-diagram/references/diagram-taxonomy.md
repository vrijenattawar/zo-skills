---
created: 2026-02-06
last_edited: 2026-02-06
version: 1.0
provenance: con_A6c99gs3C9tU3S2O
---

# Diagram Type Taxonomy

A classification of diagram types, their use cases, and recommended output formats for Excalidraw.

## Category 1: Flow & Process

### Flowchart
**Use when:** Sequential steps, processes, algorithms, workflows
**Content signals:** "first... then... finally", "step 1, step 2", numbered lists, procedures
**Format:** Mermaid (native rendering)
```
flowchart TD
  A[Start] --> B[Process] --> C[End]
```

### Decision Tree
**Use when:** Branching logic, if/then scenarios, choices with consequences
**Content signals:** "if X then Y", "depends on", "in case of", conditional language
**Format:** Mermaid (native rendering)
```
flowchart TD
  A{Decision} -->|Yes| B[Outcome 1]
  A -->|No| C[Outcome 2]
```

### Swimlane / Cross-functional
**Use when:** Multiple actors/departments in a process
**Content signals:** Role assignments, handoffs, "team A does X, team B does Y"
**Format:** Mermaid with subgraphs OR Excalidraw JSON for custom layouts

## Category 2: Hierarchy & Structure

### Tree / Org Chart
**Use when:** Parent-child relationships, taxonomies, org structures
**Content signals:** "consists of", "includes", "subdivided into", nested bullets
**Format:** Excalidraw JSON (Mermaid mindmap renders as image)

### Mindmap
**Use when:** Brainstorming, concept exploration, non-linear relationships
**Content signals:** Central topic with radiating ideas, associations, themes
**Format:** Excalidraw JSON

## Category 3: Relationships & Networks

### Entity-Relationship
**Use when:** Data models, domain models, how things connect
**Content signals:** "X has many Y", "belongs to", cardinality language
**Format:** Excalidraw JSON (Mermaid ER renders as image)

### Network / Graph
**Use when:** Interconnected entities without hierarchy
**Content signals:** Peer relationships, connections, "linked to", "associated with"
**Format:** Excalidraw JSON

### Venn Diagram
**Use when:** Overlapping categories, shared characteristics
**Content signals:** "both X and Y", "unlike X, Y also", intersection language
**Format:** Excalidraw JSON

## Category 4: Comparison & Analysis

### Comparison Matrix
**Use when:** Evaluating options against criteria
**Content signals:** "option A vs option B", pros/cons, feature comparison
**Format:** Excalidraw JSON (table-like layout)

### Quadrant Chart
**Use when:** 2-axis positioning, priority matrices, risk assessment
**Content signals:** High/low language, 2D trade-offs, "more X but less Y"
**Format:** Excalidraw JSON

### Tradeoff Diagram
**Use when:** Mutually exclusive choices, opportunity costs
**Content signals:** "either/or", "at the expense of", constraints
**Format:** Excalidraw JSON

## Category 5: Temporal & Sequential

### Timeline
**Use when:** Events over time, history, roadmaps
**Content signals:** Dates, "in 2020", "before/after", chronological narrative
**Format:** Excalidraw JSON (Mermaid timeline renders as image)

### Sequence Diagram
**Use when:** Interactions over time, message passing, API calls
**Content signals:** "A sends to B", "request/response", ordered interactions
**Format:** Excalidraw JSON (Mermaid sequence renders as image)

### Gantt Chart
**Use when:** Project timelines, task durations, dependencies
**Content signals:** Start/end dates, "takes 2 weeks", parallel tracks
**Format:** Excalidraw JSON or defer to specialized tool

## Category 6: State & Behavior

### State Diagram
**Use when:** System states, transitions, lifecycle
**Content signals:** "enters state X", "transitions to", "when in state Y"
**Format:** Excalidraw JSON (Mermaid state renders as image)

### Finite State Machine
**Use when:** Formal state modeling, input-driven transitions
**Content signals:** Events trigger transitions, guard conditions
**Format:** Excalidraw JSON

## Category 7: Architecture & Systems

### System Architecture
**Use when:** Components, services, infrastructure
**Content signals:** "service A calls service B", "database", "API layer"
**Format:** Excalidraw JSON

### C4 Diagram
**Use when:** Software architecture at multiple zoom levels
**Content signals:** Context, containers, components, code
**Format:** Excalidraw JSON

### Data Flow
**Use when:** How data moves through a system
**Content signals:** "data flows from", "transformed by", "stored in"
**Format:** Mermaid flowchart OR Excalidraw JSON

## Detection Heuristics

When analyzing text, look for these signals:

| Signal | Likely Diagram Type |
|--------|---------------------|
| Numbered steps | Flowchart |
| If/then/else | Decision tree |
| Hierarchy words (contains, consists of) | Tree |
| Comparison words (vs, unlike, similar) | Matrix or Venn |
| Time words (before, after, in 2020) | Timeline |
| State words (enters, transitions, mode) | State diagram |
| Relationship words (has many, belongs to) | ER diagram |
| Options with tradeoffs | Quadrant or tradeoff |

## Compound Diagrams

Sometimes content needs multiple diagram types:
- An article might have both a **process flow** and a **concept hierarchy**
- A decision might need a **decision tree** AND a **comparison matrix**

The skill should identify ALL visualizable concepts and propose multiple diagrams when appropriate.
