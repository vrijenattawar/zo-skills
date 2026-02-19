---
created: 2026-02-06
last_edited: 2026-02-06
version: 1.0
provenance: con_A6c99gs3C9tU3S2O
---

# Mermaid Syntax Reference

For generating flowcharts that render natively in Excalidraw with hand-drawn aesthetic.

## Why Only Flowcharts?

Excalidraw's Mermaid integration only renders **flowcharts** as native hand-drawn elements. All other Mermaid diagram types (sequence, class, ER, gantt, etc.) are rendered as rasterized images — defeating the aesthetic purpose.

**For non-flowchart diagrams, use raw Excalidraw JSON instead.**

## Flowchart Basics

### Direction
```
flowchart TB   %% Top to Bottom (default)
flowchart TD   %% Top Down (same as TB)
flowchart BT   %% Bottom to Top
flowchart LR   %% Left to Right
flowchart RL   %% Right to Left
```

### Node Shapes (Excalidraw-supported)

```mermaid
flowchart TD
    A[Rectangle]           %% Standard box
    B(Rounded Rectangle)   %% Rounded corners
    C{Diamond}             %% Decision
    D((Circle))            %% Circle/ellipse
```

**Note:** Other Mermaid shapes (hexagon, parallelogram, etc.) fall back to rectangles in Excalidraw.

### Connections

```mermaid
flowchart TD
    A --> B          %% Arrow
    A --- B          %% Line (no arrow)
    A -.- B          %% Dotted line
    A -.-> B         %% Dotted arrow
    A ==> B          %% Thick arrow
    A --text--> B    %% Arrow with label
    A -->|text| B    %% Alternative label syntax
```

### Labels on Nodes

```mermaid
flowchart TD
    A["Text with special chars: (parentheses)"]
    B["Multi-line
    text"]
```

## Common Patterns

### Linear Process
```mermaid
flowchart TD
    A[Start] --> B[Step 1]
    B --> C[Step 2]
    C --> D[Step 3]
    D --> E[End]
```

### Decision Tree
```mermaid
flowchart TD
    A[Start] --> B{Decision?}
    B -->|Yes| C[Path A]
    B -->|No| D[Path B]
    C --> E[End]
    D --> E
```

### Parallel Branches
```mermaid
flowchart TD
    A[Start] --> B[Fork]
    B --> C[Branch 1]
    B --> D[Branch 2]
    C --> E[Join]
    D --> E
    E --> F[End]
```

### Loop / Cycle
```mermaid
flowchart TD
    A[Start] --> B[Process]
    B --> C{Done?}
    C -->|No| B
    C -->|Yes| D[End]
```

### Subgraphs (Grouped Sections)
```mermaid
flowchart TB
    subgraph Phase1[Phase 1]
        A[Step 1] --> B[Step 2]
    end
    subgraph Phase2[Phase 2]
        C[Step 3] --> D[Step 4]
    end
    B --> C
```

## Style Tips for Dark Theme

Excalidraw applies its own styling, but you can influence structure:

1. **Keep labels short** — Long text wraps awkwardly
2. **Use decision diamonds sparingly** — They take up space
3. **Prefer TD for vertical processes** — Reads naturally
4. **Use LR for timelines** — Horizontal flow
5. **Group related steps** — Use subgraphs for visual chunking

## Syntax Gotchas

### Reserved Words
Wrap in quotes:
```mermaid
flowchart TD
    A["end"]         %% "end" is reserved
    B["subgraph"]    %% "subgraph" is reserved
```

### Special Characters
Use quotes for parentheses, brackets, etc.:
```mermaid
flowchart TD
    A["Process (optional)"]
    B["Config [v2.0]"]
```

### Multi-line Labels
Use `<br>` or actual line breaks in quotes:
```mermaid
flowchart TD
    A["Line 1<br>Line 2"]
    B["Line 1
    Line 2"]
```

## Examples for Common Use Cases

### Simple Process
```mermaid
flowchart TD
    A[Receive Input] --> B[Validate]
    B --> C{Valid?}
    C -->|Yes| D[Process]
    C -->|No| E[Return Error]
    D --> F[Return Result]
```

### Decision with Multiple Options
```mermaid
flowchart TD
    A[Start] --> B{Choose Action}
    B -->|Option A| C[Do A]
    B -->|Option B| D[Do B]
    B -->|Option C| E[Do C]
    C --> F[End]
    D --> F
    E --> F
```

### Pipeline with Stages
```mermaid
flowchart LR
    subgraph Input
        A[Raw Data]
    end
    subgraph Processing
        B[Transform] --> C[Validate] --> D[Enrich]
    end
    subgraph Output
        E[Store]
    end
    A --> B
    D --> E
```

## When NOT to Use Mermaid

Use Excalidraw JSON instead when you need:
- **Mindmaps** — Mermaid mindmaps render as images
- **Custom layouts** — Precise positioning control
- **ER diagrams** — Render as images in Excalidraw
- **Timelines** — Render as images
- **Sequence diagrams** — Render as images
- **State diagrams** — Render as images
- **Non-standard shapes** — Custom styling
- **Mixed diagram types** — Combining different visuals
