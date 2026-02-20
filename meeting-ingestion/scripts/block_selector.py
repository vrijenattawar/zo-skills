#!/usr/bin/env python3
"""
Smart Block Selector - LLM-powered block selection for meetings.

Uses /zo/ask for semantic transcript analysis to determine which blocks
should be generated based on content, triggers, and V's priorities.

Usage:
    python3 block_selector.py <meeting_folder> [--dry-run]
    python3 block_selector.py --transcript <path> --type external [--dry-run]
    python3 block_selector.py --help
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import requests
import yaml

BLOCK_INDEX_PATH = Path("./Prompts/Blocks/BLOCK_INDEX.yaml")
PRIORITIES_PATH = Path("./Personal/config/priorities.yaml")


def load_block_index() -> dict:
    """Load the canonical block index."""
    with open(BLOCK_INDEX_PATH) as f:
        content = f.read()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]
        return yaml.safe_load(content)


def load_priorities() -> dict:
    """Load V's priorities config."""
    with open(PRIORITIES_PATH) as f:
        content = f.read()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]
        return yaml.safe_load(content)


def get_current_focus(priorities: dict) -> list[str]:
    """Extract current focus items from priorities."""
    focus = []
    for p in priorities.get("priorities", []):
        if "current_focus" in p:
            focus.extend(p["current_focus"])
    return focus


def get_recipe(block_index: dict, meeting_type: str, participants: list[str]) -> str:
    """Determine the recipe to use based on meeting type and participants."""
    recipes = block_index.get("recipes", {})
    
    if meeting_type == "internal":
        if any("standup" in p.lower() for p in participants):
            return "internal_standup"
        return "internal_strategy"
    
    participant_str = " ".join(participants).lower()
    if any(term in participant_str for term in ["investor", "vc", "fund"]):
        return "external_investor"
    if any(term in participant_str for term in ["sales", "partnership", "deal"]):
        return "external_sales"
    
    return "external_standard"


def build_conditional_blocks_description(block_index: dict, meeting_type: str) -> str:
    """Build description of conditional blocks for LLM prompt."""
    blocks = block_index.get("blocks", {}).get(meeting_type, {})
    descriptions = []
    
    for code, block in blocks.items():
        if block.get("when") == "conditional":
            trigger = block.get("trigger_conditions", "When relevant content exists")
            descriptions.append(f"- {code} ({block['name']}): {block['purpose']}. Trigger: {trigger}")
    
    return "\n".join(descriptions)


def build_triggers_description(block_index: dict) -> str:
    """Build description of Zo Take Heed triggers."""
    triggers = block_index.get("triggers", {})
    descriptions = []
    
    for name, trigger in triggers.items():
        patterns = ", ".join(f'"{p}"' for p in trigger.get("patterns", []))
        descriptions.append(f"- {trigger['block']}: Patterns: {patterns}")
    
    return "\n".join(descriptions)


def call_zo_ask(prompt: str, max_retries: int = 2) -> dict:
    """Call /zo/ask API for semantic analysis with retry logic."""
    import time
    
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        raise ValueError("ZO_CLIENT_IDENTITY_TOKEN not set")
    
    output_format = {
        "type": "object",
        "properties": {
            "conditional_generate": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "block": {"type": "string"},
                        "reason": {"type": "string"}
                    },
                    "required": ["block", "reason"]
                }
            },
            "conditional_skip": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "block": {"type": "string"},
                        "reason": {"type": "string"}
                    },
                    "required": ["block", "reason"]
                }
            },
            "triggers_detected": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "block": {"type": "string"},
                        "trigger_phrase": {"type": "string"},
                        "context": {"type": "string"}
                    },
                    "required": ["block", "trigger_phrase"]
                }
            }
        },
        "required": ["conditional_generate", "conditional_skip", "triggers_detected"]
    }
    
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                "<YOUR_WEBHOOK_URL>",
                headers={
                    "authorization": token,
                    "content-type": "application/json"
                },
                json={
                    "input": prompt,
                    "output_format": output_format
                },
                timeout=300
            )
            response.raise_for_status()
            return response.json()["output"]
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise
    
    raise last_error


def analyze_transcript(transcript: str, meeting_type: str, block_index: dict, priorities: dict) -> dict:
    """Use LLM to analyze transcript for block selection."""
    current_focus = get_current_focus(priorities)
    conditional_desc = build_conditional_blocks_description(block_index, meeting_type)
    triggers_desc = build_triggers_description(block_index)
    
    transcript_excerpt = transcript[:12000] if len(transcript) > 12000 else transcript
    
    prompt = f"""Analyze this meeting transcript to determine which conditional blocks should be generated and detect any trigger phrases.

TRANSCRIPT:
{transcript_excerpt}

MEETING TYPE: {meeting_type}

CONDITIONAL BLOCKS AVAILABLE (decide GENERATE or SKIP for each):
{conditional_desc}

ZO TAKE HEED TRIGGERS (scan for these exact or similar phrases):
{triggers_desc}

V'S CURRENT PRIORITIES:
{chr(10).join(f"- {f}" for f in current_focus) if current_focus else "- General business and career growth"}

INSTRUCTIONS:
1. For each conditional block, decide GENERATE (with reason based on transcript content) or SKIP (with reason why not relevant)
2. Scan for trigger phrases that activate B07 (warm introductions) or B14 (blurbs) - these are verbal cues where V says things like "Zo, intro me to..." or "Zo, draft a blurb..."
3. Weight your decisions toward V's current priorities - blocks related to "Careerspan recruiting revenue" should be favored
4. Be selective - only generate blocks that have clear supporting content in the transcript

Return your analysis in the required JSON format."""

    return call_zo_ask(prompt)


def select_blocks(transcript: str, meeting_type: str, participants: list[str]) -> dict:
    """
    Select blocks to generate based on transcript content.
    
    Uses /zo/ask for semantic analysis of:
    - Topics discussed (maps to conditional blocks)
    - Zo Take Heed triggers (B07, B14)
    - Priority relevance (V's current focus)
    
    Returns:
        {
            "recipe": "external_standard",
            "always": ["B00", "B01", ...],
            "conditional_selected": ["B06", "B28"],
            "conditional_skipped": ["B04", "B10"],
            "triggered": ["B14"],
            "reasoning": {
                "B06": "Business context discussed - partnership terms",
                "B28": "Strategic implications for market positioning",
                "B14": "V said 'Zo, draft a blurb about David'"
            },
            "total_blocks": 10
        }
    """
    block_index = load_block_index()
    priorities = load_priorities()
    
    recipe_name = get_recipe(block_index, meeting_type, participants)
    recipe = block_index.get("recipes", {}).get(recipe_name, {})
    
    always_blocks = recipe.get("always", [])
    conditional_pool = recipe.get("conditional", [])
    
    analysis = analyze_transcript(transcript, meeting_type, block_index, priorities)
    
    conditional_selected = []
    conditional_skipped = []
    triggered = []
    reasoning = {}
    
    for item in analysis.get("conditional_generate", []):
        block = item["block"]
        if block in conditional_pool:
            conditional_selected.append(block)
            reasoning[block] = item["reason"]
    
    for item in analysis.get("conditional_skip", []):
        block = item["block"]
        if block in conditional_pool and block not in conditional_selected:
            conditional_skipped.append(block)
            reasoning[block] = f"Skipped: {item['reason']}"
    
    for item in analysis.get("triggers_detected", []):
        block = item["block"]
        if block not in triggered:
            triggered.append(block)
            context = item.get("context", "")
            reasoning[block] = f"Triggered: '{item['trigger_phrase']}'" + (f" - {context}" if context else "")
            if block in conditional_skipped:
                conditional_skipped.remove(block)
            if block not in conditional_selected:
                conditional_selected.append(block)
    
    total_blocks = len(set(always_blocks + conditional_selected))
    
    return {
        "recipe": recipe_name,
        "always": always_blocks,
        "conditional_selected": conditional_selected,
        "conditional_skipped": conditional_skipped,
        "triggered": triggered,
        "reasoning": reasoning,
        "total_blocks": total_blocks,
        "all_blocks": list(set(always_blocks + conditional_selected))
    }


def load_meeting_transcript(meeting_folder: Path) -> tuple[str, str, list[str]]:
    """Load transcript and metadata from a meeting folder."""
    manifest_path = meeting_folder / "manifest.json"
    
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        meeting_type = manifest.get("meeting_type", "external")
        participants = manifest.get("participants", [])
        if isinstance(participants, list) and participants:
            if isinstance(participants[0], dict):
                participants = [p.get("name", str(p)) for p in participants]
    else:
        meeting_type = "external"
        participants = []
    
    transcript_path = None
    for ext in [".md", ".txt"]:
        for name in ["transcript", "Transcript", "meeting_transcript"]:
            p = meeting_folder / f"{name}{ext}"
            if p.exists():
                transcript_path = p
                break
        if transcript_path:
            break
    
    if not transcript_path:
        md_files = list(meeting_folder.glob("*.md"))
        if md_files:
            largest = max(md_files, key=lambda p: p.stat().st_size)
            transcript_path = largest
    
    if not transcript_path:
        raise FileNotFoundError(f"No transcript found in {meeting_folder}")
    
    with open(transcript_path) as f:
        transcript = f.read()
    
    return transcript, meeting_type, participants


def main():
    parser = argparse.ArgumentParser(
        description="Smart Block Selector - LLM-powered block selection for meetings"
    )
    parser.add_argument(
        "meeting_folder",
        nargs="?",
        help="Path to meeting folder containing transcript and manifest"
    )
    parser.add_argument(
        "--transcript",
        help="Direct path to transcript file"
    )
    parser.add_argument(
        "--type",
        choices=["external", "internal"],
        default="external",
        help="Meeting type (default: external)"
    )
    parser.add_argument(
        "--participants",
        nargs="*",
        default=[],
        help="Participant names or roles"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be selected without calling LLM"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    
    args = parser.parse_args()
    
    if not args.meeting_folder and not args.transcript:
        parser.error("Either meeting_folder or --transcript is required")
    
    if args.meeting_folder:
        folder = Path(args.meeting_folder)
        transcript, meeting_type, participants = load_meeting_transcript(folder)
    else:
        with open(args.transcript) as f:
            transcript = f.read()
        meeting_type = args.type
        participants = args.participants
    
    if args.dry_run:
        block_index = load_block_index()
        recipe_name = get_recipe(block_index, meeting_type, participants)
        recipe = block_index.get("recipes", {}).get(recipe_name, {})
        
        result = {
            "recipe": recipe_name,
            "always": recipe.get("always", []),
            "conditional_pool": recipe.get("conditional", []),
            "note": "Dry run - conditional blocks would be selected by LLM analysis",
            "total_always": len(recipe.get("always", []))
        }
    else:
        result = select_blocks(transcript, meeting_type, participants)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"BLOCK SELECTION RESULTS")
        print(f"{'='*60}")
        print(f"\nRecipe: {result['recipe']}")
        print(f"\nAlways ({len(result.get('always', []))}):")
        for b in result.get("always", []):
            print(f"  • {b}")
        
        if args.dry_run:
            print(f"\nConditional Pool ({len(result.get('conditional_pool', []))}):")
            for b in result.get("conditional_pool", []):
                print(f"  ? {b}")
            print(f"\n⚠️  {result.get('note', '')}")
        else:
            if result.get("conditional_selected"):
                print(f"\nConditional Selected ({len(result['conditional_selected'])}):")
                for b in result["conditional_selected"]:
                    reason = result.get("reasoning", {}).get(b, "")
                    print(f"  ✓ {b}: {reason}")
            
            if result.get("triggered"):
                print(f"\nTriggered ({len(result['triggered'])}):")
                for b in result["triggered"]:
                    reason = result.get("reasoning", {}).get(b, "")
                    print(f"  ⚡ {b}: {reason}")
            
            if result.get("conditional_skipped"):
                print(f"\nSkipped ({len(result['conditional_skipped'])}):")
                for b in result["conditional_skipped"]:
                    reason = result.get("reasoning", {}).get(b, "")
                    print(f"  ✗ {b}: {reason}")
            
            print(f"\n{'='*60}")
            print(f"Total Blocks to Generate: {result.get('total_blocks', 0)}")
            print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
