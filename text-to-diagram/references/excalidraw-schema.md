---
created: 2026-02-06
last_edited: 2026-02-06
version: 1.0
provenance: con_A6c99gs3C9tU3S2O
---

# Excalidraw JSON Schema Reference

For generating raw Excalidraw files that render with the hand-drawn aesthetic.

## Top-Level Structure

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://va.zo.space",
  "elements": [...],
  "appState": {
    "viewBackgroundColor": "#000000",
    "theme": "dark",
    "gridSize": null
  },
  "files": {}
}
```

## Element Types

### Rectangle
```json
{
  "id": "unique-id-1",
  "type": "rectangle",
  "x": 100,
  "y": 100,
  "width": 200,
  "height": 100,
  "angle": 0,
  "strokeColor": "#ffffff",
  "backgroundColor": "transparent",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "groupIds": [],
  "roundness": { "type": 3 },
  "seed": 12345,
  "version": 1,
  "versionNonce": 12345,
  "isDeleted": false,
  "boundElements": null,
  "updated": 1700000000000,
  "link": null,
  "locked": false
}
```

### Ellipse (Circle)
```json
{
  "id": "unique-id-2",
  "type": "ellipse",
  "x": 100,
  "y": 100,
  "width": 100,
  "height": 100,
  ...
}
```

### Diamond
```json
{
  "id": "unique-id-3",
  "type": "diamond",
  "x": 100,
  "y": 100,
  "width": 100,
  "height": 100,
  ...
}
```

### Text
```json
{
  "id": "unique-id-4",
  "type": "text",
  "x": 100,
  "y": 100,
  "width": 150,
  "height": 25,
  "text": "Hello World",
  "fontSize": 20,
  "fontFamily": 1,
  "textAlign": "center",
  "verticalAlign": "middle",
  "baseline": 18,
  "containerId": null,
  "originalText": "Hello World",
  "lineHeight": 1.25,
  ...
}
```

**fontFamily values:**
- `1` = Virgil (hand-drawn, default)
- `2` = Helvetica
- `3` = Cascadia (monospace)

### Arrow
```json
{
  "id": "unique-id-5",
  "type": "arrow",
  "x": 300,
  "y": 150,
  "width": 100,
  "height": 0,
  "points": [[0, 0], [100, 0]],
  "startBinding": {
    "elementId": "source-element-id",
    "focus": 0,
    "gap": 5
  },
  "endBinding": {
    "elementId": "target-element-id",
    "focus": 0,
    "gap": 5
  },
  "startArrowhead": null,
  "endArrowhead": "arrow",
  ...
}
```

**Arrowhead values:**
- `null` = no arrowhead
- `"arrow"` = standard arrow
- `"bar"` = flat bar
- `"dot"` = circle
- `"triangle"` = filled triangle

### Line
```json
{
  "id": "unique-id-6",
  "type": "line",
  "x": 100,
  "y": 100,
  "width": 200,
  "height": 100,
  "points": [[0, 0], [100, 50], [200, 100]],
  "startBinding": null,
  "endBinding": null,
  "startArrowhead": null,
  "endArrowhead": null,
  ...
}
```

## Common Properties

### Stroke Styles
- `"solid"` = continuous line
- `"dashed"` = dashed line
- `"dotted"` = dotted line

### Fill Styles
- `"solid"` = filled
- `"hachure"` = hatched lines (hand-drawn feel)
- `"cross-hatch"` = cross-hatched
- `"zigzag"` = zigzag pattern
- `"zigzag-line"` = zigzag line pattern

### Roughness
- `0` = smooth, clean lines
- `1` = slight wobble (default, good balance)
- `2` = very sketchy, hand-drawn

### Colors (Dark Theme)
```
Background: #000000 or transparent
Stroke white: #ffffff
Stroke gray: #a1a1aa
Stroke muted: #71717a
Accent blue: #3b82f6
Accent green: #22c55e
Accent red: #ef4444
Accent yellow: #eab308
```

## Bound Text (Labels Inside Shapes)

To put text inside a shape:

1. Create the shape with `boundElements`:
```json
{
  "id": "rect-1",
  "type": "rectangle",
  ...
  "boundElements": [
    { "id": "text-1", "type": "text" }
  ]
}
```

2. Create the text with `containerId`:
```json
{
  "id": "text-1",
  "type": "text",
  "containerId": "rect-1",
  "text": "Label",
  ...
}
```

## Groups

To group elements together (for compound shapes):
```json
{
  "id": "elem-1",
  ...
  "groupIds": ["group-1"]
},
{
  "id": "elem-2",
  ...
  "groupIds": ["group-1"]
}
```

## Layout Strategies

### Grid Layout
For matrices and tables:
- Calculate cell positions based on column width and row height
- Add padding between cells

### Tree Layout
For hierarchies:
- Calculate level depths
- Distribute children horizontally
- Connect with arrows

### Radial Layout
For mindmaps:
- Center node at origin
- Children arranged in a circle
- Use line connections (not arrows)

### Force-Directed Layout
For networks:
- Start with random positions
- Iterate to minimize edge crossings (complex, may simplify)

## ID Generation

Use UUIDs or random strings:
```python
import uuid
element_id = str(uuid.uuid4())[:8]  # Short form
```

Or use descriptive IDs:
```
"node-decision-1"
"arrow-decision-to-yes"
"label-step-3"
```

## Seed Values

`seed` affects the randomness of the hand-drawn rendering. Same seed = same wobble pattern.

```python
import random
seed = random.randint(1, 999999999)
```

## Example: Simple Flowchart

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://va.zo.space",
  "elements": [
    {
      "id": "start",
      "type": "rectangle",
      "x": 100,
      "y": 100,
      "width": 120,
      "height": 60,
      "strokeColor": "#ffffff",
      "backgroundColor": "transparent",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "boundElements": [{"id": "start-text", "type": "text"}]
    },
    {
      "id": "start-text",
      "type": "text",
      "x": 130,
      "y": 115,
      "text": "Start",
      "fontSize": 20,
      "fontFamily": 1,
      "containerId": "start",
      "strokeColor": "#ffffff"
    },
    {
      "id": "arrow-1",
      "type": "arrow",
      "x": 160,
      "y": 160,
      "width": 0,
      "height": 60,
      "points": [[0, 0], [0, 60]],
      "strokeColor": "#ffffff",
      "endArrowhead": "arrow",
      "startBinding": {"elementId": "start", "focus": 0, "gap": 5},
      "endBinding": {"elementId": "end", "focus": 0, "gap": 5}
    },
    {
      "id": "end",
      "type": "rectangle",
      "x": 100,
      "y": 220,
      "width": 120,
      "height": 60,
      "strokeColor": "#ffffff",
      "backgroundColor": "transparent",
      "boundElements": [{"id": "end-text", "type": "text"}]
    },
    {
      "id": "end-text",
      "type": "text",
      "x": 140,
      "y": 235,
      "text": "End",
      "fontSize": 20,
      "fontFamily": 1,
      "containerId": "end",
      "strokeColor": "#ffffff"
    }
  ],
  "appState": {
    "viewBackgroundColor": "#000000",
    "theme": "dark"
  },
  "files": {}
}
```
