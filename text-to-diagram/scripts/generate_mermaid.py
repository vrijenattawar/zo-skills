#!/usr/bin/env python3
"""
Mermaid Diagram Generator

Takes structured diagram specification (from Socratic dialogue output)
and generates Mermaid syntax ready for Excalidraw import.

Supports: flowchart, decision_tree, sequence (rendered as image in Excalidraw)

Usage:
    python3 generate_mermaid.py --spec <spec.yaml> [--output <file.mmd>] [--dry-run]
    echo '<yaml>' | python3 generate_mermaid.py --spec - [--output <file.mmd>]
    python3 generate_mermaid.py --help

Spec format (YAML):
    diagram_type: flowchart | decision_tree | causal_flow
    title: "My Diagram"
    direction: TD | LR | BT | RL
    nodes:
      - id: A
        label: "Start here"
        shape: rectangle | rounded | diamond | circle | stadium
      - id: B
        label: "Decision point"
        shape: diamond
    edges:
      - from: A
        to: B
        label: "proceeds to"
    subgraphs:
      - id: sg1
        label: "Phase 1"
        members: [A, B]
"""

import argparse
import json
import sys
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    yaml = None

SHAPE_MAP = {
    "rectangle": ("[", "]"),
    "rounded": ("(", ")"),
    "diamond": ("{", "}"),
    "circle": ("((", "))"),
    "stadium": ("([", "])"),
    "hexagon": ("{{", "}}"),
    "parallelogram": ("[/", "/]"),
    "trapezoid": ("[/", "\\]"),
    "subroutine": ("[[", "]]"),
    "database": ("[(", ")]"),
}

EDGE_STYLES = {
    "solid": "-->",
    "dotted": "-.->",
    "thick": "==>",
    "invisible": "~~~",
}


def parse_spec(raw: str) -> dict:
    """Parse YAML or JSON spec into dict."""
    if yaml:
        return yaml.safe_load(raw)
    return json.loads(raw)


def escape_label(label: str) -> str:
    """Escape special Mermaid characters in labels."""
    return label.replace('"', "'").replace("\n", "<br/>")


def node_to_mermaid(node: dict) -> str:
    """Convert a node dict to Mermaid node syntax."""
    nid = node["id"]
    label = escape_label(node.get("label", nid))
    shape = node.get("shape", "rectangle")
    left, right = SHAPE_MAP.get(shape, ("[", "]"))
    return f'    {nid}{left}"{label}"{right}'


def edge_to_mermaid(edge: dict) -> str:
    """Convert an edge dict to Mermaid edge syntax."""
    src = edge["from"]
    dst = edge["to"]
    label = edge.get("label", "")
    style = edge.get("style", "solid")
    arrow = EDGE_STYLES.get(style, "-->")

    if label:
        return f'    {src} {arrow}|{escape_label(label)}| {dst}'
    return f'    {src} {arrow} {dst}'


def generate_flowchart(spec: dict) -> str:
    """Generate a Mermaid flowchart from spec."""
    direction = spec.get("direction", "TD")
    lines = [f"flowchart {direction}"]

    subgraphs = spec.get("subgraphs", [])
    sg_members = {}
    for sg in subgraphs:
        for m in sg.get("members", []):
            sg_members[m] = sg["id"]

    sg_open = set()
    nodes = spec.get("nodes", [])
    for sg in subgraphs:
        lines.append(f'    subgraph {sg["id"]}["{escape_label(sg.get("label", sg["id"]))}"]')
        for node in nodes:
            if node["id"] in sg.get("members", []):
                lines.append(f"    {node_to_mermaid(node)}")
        lines.append("    end")
        sg_open.add(sg["id"])

    for node in nodes:
        if node["id"] not in sg_members:
            lines.append(node_to_mermaid(node))

    for edge in spec.get("edges", []):
        lines.append(edge_to_mermaid(edge))

    styling = spec.get("styling", {})
    for node_id, style_str in styling.items():
        lines.append(f"    style {node_id} {style_str}")

    return "\n".join(lines)


def generate_decision_tree(spec: dict) -> str:
    """Generate a decision tree as a Mermaid flowchart with diamonds."""
    for node in spec.get("nodes", []):
        if node.get("is_decision") or "?" in node.get("label", ""):
            node["shape"] = "diamond"
    return generate_flowchart(spec)


def generate(spec: dict) -> str:
    """Route to the correct generator based on diagram_type."""
    dtype = spec.get("diagram_type", "flowchart")

    generators = {
        "flowchart": generate_flowchart,
        "decision_tree": generate_decision_tree,
        "causal_flow": generate_flowchart,
    }

    gen = generators.get(dtype)
    if not gen:
        log.error(f"Unsupported diagram type: {dtype}. Supported: {list(generators.keys())}")
        sys.exit(1)

    title = spec.get("title", "")
    mermaid = gen(spec)

    if title:
        mermaid = f"---\ntitle: {title}\n---\n{mermaid}"

    return mermaid


def main():
    parser = argparse.ArgumentParser(
        description="Generate Mermaid diagram syntax from a structured spec"
    )
    parser.add_argument(
        "--spec", "-s",
        required=True,
        help="Path to spec YAML/JSON file, or '-' for stdin"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (.mmd). Default: stdout"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing"
    )
    args = parser.parse_args()

    if args.spec == "-":
        raw = sys.stdin.read()
    elif os.path.isfile(args.spec):
        with open(args.spec, "r") as f:
            raw = f.read()
    else:
        log.error(f"Spec file not found: {args.spec}")
        sys.exit(1)

    spec = parse_spec(raw)
    mermaid = generate(spec)

    if args.dry_run:
        log.info("[DRY RUN] Would generate:")
        print(mermaid)
        return

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(mermaid, encoding="utf-8")
        log.info(f"Mermaid written to: {out}")
        print(str(out))
    else:
        print(mermaid)


if __name__ == "__main__":
    main()
