#!/usr/bin/env python3
"""
Text-to-Diagram Analysis Script

Analyzes a corpus of text to identify visualizable concepts and recommend diagram types.
Outputs a structured analysis for the Socratic dialogue phase.

Usage:
    python3 analyze.py --input <file_or_text> [--output <dir>]
    python3 analyze.py --help
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Diagram type definitions
DIAGRAM_TYPES = {
    "flowchart": {
        "name": "Flowchart",
        "signals": ["step", "process", "workflow", "procedure", "first", "then", "finally", "next"],
        "format": "mermaid",
        "description": "Sequential steps or processes"
    },
    "decision_tree": {
        "name": "Decision Tree",
        "signals": ["if", "decide", "choice", "option", "depends", "condition", "either", "or"],
        "format": "mermaid",
        "description": "Branching logic or choices"
    },
    "hierarchy": {
        "name": "Hierarchy / Tree",
        "signals": ["consists of", "contains", "includes", "subdivided", "parent", "child", "category"],
        "format": "excalidraw",
        "description": "Parent-child relationships"
    },
    "mindmap": {
        "name": "Mindmap",
        "signals": ["concept", "idea", "theme", "aspect", "related to", "associated"],
        "format": "excalidraw",
        "description": "Central concept with radiating ideas"
    },
    "comparison": {
        "name": "Comparison Matrix",
        "signals": ["vs", "versus", "compared to", "unlike", "similar", "difference", "pros", "cons"],
        "format": "excalidraw",
        "description": "Comparing options against criteria"
    },
    "timeline": {
        "name": "Timeline",
        "signals": ["in 2020", "before", "after", "during", "history", "roadmap", "phase"],
        "format": "excalidraw",
        "description": "Events over time"
    },
    "state": {
        "name": "State Diagram",
        "signals": ["state", "transition", "enters", "mode", "status", "changes to"],
        "format": "excalidraw",
        "description": "States and transitions"
    },
    "relationship": {
        "name": "Relationship Diagram",
        "signals": ["has many", "belongs to", "owns", "references", "connects to", "linked"],
        "format": "excalidraw",
        "description": "Entity relationships"
    },
    "quadrant": {
        "name": "Quadrant Chart",
        "signals": ["high/low", "priority", "impact", "effort", "risk", "reward", "tradeoff"],
        "format": "excalidraw",
        "description": "2-axis positioning"
    },
    "architecture": {
        "name": "Architecture Diagram",
        "signals": ["system", "component", "service", "api", "database", "layer", "module"],
        "format": "excalidraw",
        "description": "System components and connections"
    }
}


def detect_diagram_candidates(text: str) -> list[dict]:
    """
    Analyze text to detect potential diagram types.
    Returns a list of candidates with confidence scores.
    """
    text_lower = text.lower()
    candidates = []
    
    for dtype, info in DIAGRAM_TYPES.items():
        # Count signal matches
        matches = sum(1 for signal in info["signals"] if signal in text_lower)
        if matches > 0:
            confidence = min(matches / len(info["signals"]), 1.0)
            candidates.append({
                "type": dtype,
                "name": info["name"],
                "format": info["format"],
                "description": info["description"],
                "confidence": round(confidence, 2),
                "signal_matches": matches
            })
    
    # Sort by confidence
    candidates.sort(key=lambda x: x["confidence"], reverse=True)
    return candidates


def extract_entities(text: str) -> list[str]:
    """
    Extract potential entities (nouns, concepts) from text.
    Simple heuristic: capitalized words and quoted phrases.
    """
    import re
    
    entities = set()
    
    # Capitalized words (not at sentence start)
    caps = re.findall(r'(?<=[.!?]\s)[A-Z][a-z]+|(?<=\s)[A-Z][a-z]+(?:\s[A-Z][a-z]+)*', text)
    entities.update(caps)
    
    # Quoted phrases
    quoted = re.findall(r'"([^"]+)"', text)
    entities.update(quoted)
    
    # Bullet point items (if any)
    bullets = re.findall(r'^\s*[-*•]\s*(.+)$', text, re.MULTILINE)
    for bullet in bullets:
        # Take first few words
        words = bullet.split()[:4]
        entities.add(' '.join(words).strip('.,;:'))
    
    return list(entities)[:20]  # Limit to 20


def count_sections(text: str) -> int:
    """Count number of distinct sections/headers."""
    import re
    headers = re.findall(r'^#+\s|^\*\*[^*]+\*\*|^[A-Z][^.!?]*:$', text, re.MULTILINE)
    return len(headers)


def analyze_structure(text: str) -> dict:
    """Analyze the structural properties of the text."""
    import re
    
    return {
        "word_count": len(text.split()),
        "paragraph_count": len([p for p in text.split('\n\n') if p.strip()]),
        "section_count": count_sections(text),
        "has_bullets": bool(re.search(r'^\s*[-*•]\s', text, re.MULTILINE)),
        "has_numbers": bool(re.search(r'^\s*\d+[.)]\s', text, re.MULTILINE)),
        "has_headers": bool(re.search(r'^#+\s', text, re.MULTILINE)),
    }


def generate_analysis(text: str, source: str = "unknown") -> dict:
    """
    Generate a complete analysis of the text for diagram generation.
    """
    candidates = detect_diagram_candidates(text)
    entities = extract_entities(text)
    structure = analyze_structure(text)
    
    # Generate clarifying questions based on candidates
    questions = []
    
    if len(candidates) >= 2:
        questions.append(f"I detected both '{candidates[0]['name']}' and '{candidates[1]['name']}' potential. Which feels more aligned with your intent?")
    
    if any(c["type"] == "comparison" for c in candidates):
        questions.append("For the comparison: what criteria matter most? What dimensions should we compare against?")
    
    if any(c["type"] in ["flowchart", "decision_tree"] for c in candidates):
        questions.append("Should the diagram show just the 'happy path', or include error cases and exceptions?")
    
    if structure["section_count"] > 3:
        questions.append(f"The text has {structure['section_count']} sections. Should each section become a separate diagram, or one unified view?")
    
    if len(entities) > 10:
        questions.append(f"I found {len(entities)} potential concepts. Should we focus on the top-level ones, or show the full detail?")
    
    # Default questions
    questions.extend([
        "What's the primary audience for this diagram?",
        "What level of detail do you want — high-level overview or granular steps?"
    ])
    
    return {
        "meta": {
            "source": source,
            "analyzed_at": datetime.utcnow().isoformat(),
            "text_preview": text[:200] + "..." if len(text) > 200 else text
        },
        "structure": structure,
        "diagram_candidates": candidates[:5],  # Top 5
        "entities_detected": entities,
        "clarifying_questions": questions[:5],  # Top 5 questions
        "recommended_format": candidates[0]["format"] if candidates else "excalidraw",
        "recommended_type": candidates[0]["type"] if candidates else "mindmap"
    }


def main():
    parser = argparse.ArgumentParser(
        description="Analyze text for diagram generation opportunities"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input file path or '-' for stdin"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory for analysis JSON (default: stdout)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "markdown"],
        default="json",
        help="Output format"
    )
    
    args = parser.parse_args()
    
    # Read input
    if args.input == "-":
        text = sys.stdin.read()
        source = "stdin"
    elif os.path.isfile(args.input):
        with open(args.input, "r") as f:
            text = f.read()
        source = args.input
    else:
        # Treat as literal text
        text = args.input
        source = "literal"
    
    # Generate analysis
    analysis = generate_analysis(text, source)
    
    # Output
    if args.format == "json":
        output = json.dumps(analysis, indent=2)
    else:
        # Markdown format
        output = f"""# Diagram Analysis

**Source:** {analysis['meta']['source']}
**Analyzed:** {analysis['meta']['analyzed_at']}

## Structure
- Words: {analysis['structure']['word_count']}
- Paragraphs: {analysis['structure']['paragraph_count']}
- Sections: {analysis['structure']['section_count']}

## Diagram Candidates

| Type | Format | Confidence | Description |
|------|--------|------------|-------------|
"""
        for c in analysis['diagram_candidates']:
            output += f"| {c['name']} | {c['format']} | {c['confidence']} | {c['description']} |\n"
        
        output += f"""
## Detected Entities
{', '.join(analysis['entities_detected'][:10])}

## Clarifying Questions
"""
        for i, q in enumerate(analysis['clarifying_questions'], 1):
            output += f"{i}. {q}\n"
        
        output += f"""
## Recommendation
**Type:** {analysis['recommended_type']}
**Format:** {analysis['recommended_format']}
"""
    
    if args.output:
        os.makedirs(args.output, exist_ok=True)
        out_path = Path(args.output) / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{'json' if args.format == 'json' else 'md'}"
        with open(out_path, "w") as f:
            f.write(output)
        print(f"Analysis written to: {out_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
