#!/usr/bin/env python3
"""
Meeting Ingestion - Process Script (v2 with Smart Block Selector)

Generates intelligence blocks for staged meetings using LLM-powered block selection.

Usage:
    python3 process.py [meeting_path] [--blocks B01,B05] [--dry-run] [--legacy]
"""

import json
import os
import logging
import requests
from pathlib import Path
from datetime import datetime, UTC
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

INBOX = Path("./Personal/Meetings/Inbox")
PROMPTS_DIR = Path("./Prompts/Blocks")

# Legacy static block lists (kept for --legacy mode)
EXTERNAL_BLOCKS = ["B01", "B02", "B03", "B05", "B08", "B25", "B26"]
EXTERNAL_CONDITIONAL = ["B04", "B06", "B07", "B10", "B13", "B21", "B28"]
INTERNAL_BLOCKS = ["B40", "B41", "B47"]

BLOCK_NAMES = {
    "B00": "B00_ZO_TAKE_HEED",
    "B01": "B01_DETAILED_RECAP",
    "B02": "B02_COMMITMENTS",
    "B02_B05": "B02_B05_COMMITMENTS_AND_ACTIONS",
    "B03": "B03_DECISIONS",
    "B04": "B04_OPEN_QUESTIONS",
    "B05": "B05_ACTION_ITEMS",
    "B06": "B06_BUSINESS_CONTEXT",
    "B07": "B07_WARM_INTRODUCTIONS",
    "B08": "B08_STAKEHOLDER_INTELLIGENCE",
    "B10": "B10_RELATIONSHIP_TRAJECTORY",
    "B13": "B13_PLAN_OF_ACTION",
    "B14": "B14_BLURBS_REQUESTED",
    "B21": "B21_KEY_MOMENTS",
    "B25": "B25_DELIVERABLE_MAP",
    "B26": "B26_MEETING_METADATA",
    "B28": "B28_STRATEGIC_INTELLIGENCE",
    "B32": "B32_THOUGHT_PROVOKING_IDEAS",
    "B33": "B33_DECISION_RATIONALE",
    "B40": "B40_INTERNAL_DECISIONS",
    "B41": "B41_TEAM_COORDINATION",
    "B42": "B42_INTERNAL_ACTIONS",
    "B43": "B43_RESOURCE_ALLOCATION",
    "B44": "B44_PROCESS_IMPROVEMENTS",
    "B45": "B45_TEAM_DYNAMICS",
    "B46": "B46_KNOWLEDGE_TRANSFER",
    "B47": "B47_OPEN_DEBATES",
    "B48": "B48_INTERNAL_SYNTHESIS",
}

BLOCK_DESCRIPTIONS = {
    "B00": "Deferred intents and verbal cues (intro me to, draft a blurb, etc.)",
    "B01": "Comprehensive meeting summary covering all topics discussed, decisions made, and outcomes.",
    "B02": "Explicit commitments made by participants during the meeting.",
    "B02_B05": "Combined commitments and action items with owners and deadlines.",
    "B03": "Key decisions made during the meeting with rationale.",
    "B04": "Unresolved questions that need follow-up.",
    "B05": "Concrete action items with owners and deadlines.",
    "B06": "Business implications and strategic context.",
    "B07": "Draft warm introduction emails for contacts mentioned.",
    "B08": "Insights about stakeholders - their interests, concerns, communication style.",
    "B10": "Relationship trajectory and momentum analysis.",
    "B13": "Coordinated plan of action based on meeting outcomes.",
    "B14": "Draft blurbs for LinkedIn, intros, or other uses.",
    "B21": "Significant moments, quotes, or turning points in the meeting.",
    "B25": "Specific deliverables discussed with owners and timelines.",
    "B26": "Meeting metadata: date, participants, duration, purpose.",
    "B28": "Long-term strategic implications and insights.",
    "B32": "Novel ideas worth capturing for future reference.",
    "B33": "Deep dive into why decisions were made.",
    "B40": "Team decisions with context and rationale.",
    "B41": "Alignment items, handoffs, and cross-team dependencies.",
    "B42": "Internal-only tasks and action items.",
    "B43": "Bandwidth, capacity, and resource discussions.",
    "B44": "Workflow changes and process optimization ideas.",
    "B45": "Interpersonal notes, morale, and team health.",
    "B46": "Training, onboarding, or knowledge sharing moments.",
    "B47": "Unresolved tensions and areas of disagreement.",
    "B48": "Strategic takeaways for leadership review.",
}


def call_zo_api(prompt: str) -> str:
    """Call Zo API to generate content."""
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        raise RuntimeError("ZO_CLIENT_IDENTITY_TOKEN not set")
    
    response = requests.post(
        "<YOUR_WEBHOOK_URL>",
        headers={
            "authorization": token,
            "content-type": "application/json"
        },
        json={"input": prompt},
        timeout=300
    )
    
    if response.status_code != 200:
        raise RuntimeError(f"Zo API error: {response.status_code} - {response.text}")
    
    return response.json().get("output", "")


def load_prompt_template(block_code: str) -> Optional[str]:
    """Load canonical prompt from Prompts/Blocks/."""
    prompt_path = PROMPTS_DIR / f"Generate_{block_code}.prompt.md"
    if prompt_path.exists():
        return prompt_path.read_text()
    return None


def generate_block(transcript: str, block_code: str, context: dict) -> str:
    """Generate a single intelligence block."""
    full_name = BLOCK_NAMES.get(block_code, block_code)
    description = BLOCK_DESCRIPTIONS.get(block_code, "Meeting intelligence block")
    
    prompt_template = load_prompt_template(block_code)
    
    if prompt_template:
        prompt = f"""{prompt_template}

## Transcript to Analyze
{transcript[:30000]}

## Meeting Context
- Date: {context.get('date', 'Unknown')}
- Participants: {', '.join(context.get('participants', []))}
- Meeting Type: {context.get('meeting_type', 'external')}

## CRITICAL INSTRUCTION
Output ONLY the block content directly as markdown. Start with the heading "# {full_name}" immediately.
Do NOT include meta-commentary about what you're generating.
"""
    else:
        prompt = f"""Generate the {full_name} intelligence block for this meeting transcript.

## Block Definition
{block_code}: {description}

## Meeting Context
- Date: {context.get('date', 'Unknown')}
- Participants: {', '.join(context.get('participants', ['Unknown']))}
- Meeting Type: {context.get('meeting_type', 'external')}

## Transcript
{transcript[:30000]}

## Instructions
1. Analyze the transcript thoroughly
2. Extract information relevant to {block_code}
3. Format as clean markdown starting with "# {full_name}"
4. Be specific and actionable
5. Include direct quotes where relevant

Return ONLY the block content in markdown format."""

    return call_zo_api(prompt)


def use_smart_selector(transcript: str, meeting_type: str, participants: list[str]) -> dict:
    """
    Use the LLM-powered block selector from D0.4.
    
    Returns selection result with reasoning and logging info.
    """
    try:
        # Import the block selector
        import sys
        sys.path.insert(0, str(Path("./Skills/meeting-ingestion/scripts")))
        from block_selector import select_blocks
        
        result = select_blocks(transcript, meeting_type, participants)
        return {
            "success": True,
            "selection": result
        }
    except Exception as e:
        logger.error(f"Smart selector failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def determine_blocks_legacy(manifest: dict, transcript: str) -> list[str]:
    """Legacy static block selection (kept for --legacy mode)."""
    meeting_type = manifest.get("meeting_type", "external")
    
    if meeting_type == "internal":
        return INTERNAL_BLOCKS.copy()
    
    blocks = EXTERNAL_BLOCKS.copy()
    
    transcript_lower = transcript.lower()
    if "?" in transcript and len(transcript) > 500:
        if "B04" not in blocks:
            blocks.append("B04")
    if any(word in transcript_lower for word in ["risk", "concern", "worry", "problem"]):
        if "B10" not in blocks:
            blocks.append("B10")
    
    return blocks


def determine_blocks(manifest: dict, transcript: str, use_legacy: bool = False) -> tuple[list[str], dict]:
    """
    Determine which blocks to generate using smart selector (default) or legacy mode.
    
    Returns:
        tuple: (blocks_list, selection_metadata)
    """
    if use_legacy:
        blocks = determine_blocks_legacy(manifest, transcript)
        return blocks, {"method": "legacy_static", "reasoning": {}}
    
    meeting_type = manifest.get("meeting_type", "external")
    participants = manifest.get("participants", [])
    
    # Normalize participants to list of strings
    if participants and isinstance(participants[0], dict):
        participants = [p.get("name", str(p)) for p in participants]
    
    result = use_smart_selector(transcript, meeting_type, participants)
    
    if not result["success"]:
        logger.warning(f"Smart selector failed, falling back to legacy: {result['error']}")
        blocks = determine_blocks_legacy(manifest, transcript)
        return blocks, {
            "method": "legacy_fallback",
            "fallback_reason": result["error"],
            "reasoning": {}
        }
    
    selection = result["selection"]
    
    return selection["all_blocks"], {
        "method": "smart_selector_v2",
        "recipe": selection["recipe"],
        "always_blocks": selection["always"],
        "conditional_selected": selection["conditional_selected"],
        "conditional_skipped": selection["conditional_skipped"],
        "triggered": selection["triggered"],
        "reasoning": selection["reasoning"],
        "total_blocks": selection["total_blocks"]
    }


def process_meeting(meeting_path: Path, blocks: Optional[list[str]] = None, 
                   dry_run: bool = False, use_legacy: bool = False) -> dict:
    """Process a single meeting folder."""
    logger.info(f"Processing: {meeting_path.name}")
    
    manifest_path = meeting_path / "manifest.json"
    if not manifest_path.exists():
        return {"error": "no manifest.json - run stage first", "path": str(meeting_path)}
    
    manifest = json.loads(manifest_path.read_text())
    
    if manifest.get("status") == "complete":
        logger.info(f"  Already complete, skipping")
        return {"status": "already_complete", "path": str(meeting_path)}
    
    transcript_file = meeting_path / manifest.get("transcript_file", "transcript.md")
    if not transcript_file.exists():
        for pattern in ["*.md", "*.txt"]:
            files = list(meeting_path.glob(pattern))
            if files:
                transcript_file = files[0]
                break
    
    if not transcript_file.exists():
        return {"error": "no transcript found", "path": str(meeting_path)}
    
    transcript = transcript_file.read_text()
    if len(transcript.strip()) < 100:
        return {"error": f"transcript too short ({len(transcript)} chars)", "path": str(meeting_path)}
    
    # Determine blocks using smart selector or override
    selection_metadata = {}
    if blocks:
        blocks_to_generate = blocks
        selection_metadata = {"method": "manual_override", "blocks": blocks}
    else:
        blocks_to_generate, selection_metadata = determine_blocks(manifest, transcript, use_legacy)
    
    # Log selection to manifest
    manifest["block_selection"] = {
        "selected_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        **selection_metadata
    }
    
    already_generated = set(manifest.get("blocks_generated", []))
    blocks_to_generate = [b for b in blocks_to_generate if BLOCK_NAMES.get(b, b) not in already_generated]
    
    if not blocks_to_generate:
        logger.info(f"  All blocks already generated")
        manifest["status"] = "complete"
        manifest["processed_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        if not dry_run:
            manifest_path.write_text(json.dumps(manifest, indent=2))
        return {"status": "already_complete", "path": str(meeting_path)}
    
    logger.info(f"  Selection method: {selection_metadata.get('method', 'unknown')}")
    logger.info(f"  Blocks to generate: {', '.join(blocks_to_generate)}")
    
    if selection_metadata.get("reasoning"):
        logger.info(f"  Selection reasoning:")
        for block, reason in selection_metadata["reasoning"].items():
            logger.info(f"    {block}: {reason}")
    
    if dry_run:
        return {
            "dry_run": True,
            "path": str(meeting_path),
            "blocks": blocks_to_generate,
            "selection_metadata": selection_metadata
        }
    
    manifest["status"] = "processing"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    
    context = {
        "date": manifest.get("date"),
        "participants": manifest.get("participants", []),
        "meeting_type": manifest.get("meeting_type", "external")
    }
    
    result = {
        "path": str(meeting_path),
        "blocks_generated": [],
        "blocks_failed": [],
        "selection_metadata": selection_metadata
    }
    
    for block_code in blocks_to_generate:
        full_name = BLOCK_NAMES.get(block_code, block_code)
        logger.info(f"  Generating {full_name}...")
        
        try:
            content = generate_block(transcript, block_code, context)
            
            block_file = meeting_path / f"{full_name}.md"
            block_file.write_text(content)
            
            # Initialize blocks_generated if needed
            if "blocks_generated" not in manifest:
                manifest["blocks_generated"] = []
            manifest["blocks_generated"].append(full_name)
            result["blocks_generated"].append(full_name)
            logger.info(f"    ✓ Written: {full_name}.md")
            
        except Exception as e:
            logger.error(f"    ✗ Failed: {e}")
            if "blocks_failed" not in manifest:
                manifest["blocks_failed"] = []
            manifest["blocks_failed"].append({"block": full_name, "error": str(e)})
            result["blocks_failed"].append({"block": full_name, "error": str(e)})
    
    manifest["status"] = "complete"
    manifest["processed_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    manifest_path.write_text(json.dumps(manifest, indent=2))
    
    logger.info(f"  Complete: {len(result['blocks_generated'])} generated, {len(result['blocks_failed'])} failed")
    
    return result


def process_queue(batch_size: int = 5, blocks: Optional[list[str]] = None,
                 dry_run: bool = False, use_legacy: bool = False) -> dict:
    """Process all staged meetings in queue."""
    logger.info(f"Processing queue (batch_size={batch_size})")
    
    if not INBOX.exists():
        return {"error": "inbox not found"}
    
    candidates = []
    for folder in sorted(INBOX.iterdir()):
        if not folder.is_dir() or folder.name.startswith((".", "_")):
            continue
        
        manifest_path = folder / "manifest.json"
        if not manifest_path.exists():
            continue
        
        try:
            manifest = json.loads(manifest_path.read_text())
            status = manifest.get("status")
            if status in ["staged", "processing"]:
                candidates.append(folder)
        except:
            continue
    
    logger.info(f"Found {len(candidates)} meetings ready for processing")
    
    results = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "meetings": []
    }
    
    for folder in candidates[:batch_size]:
        try:
            result = process_meeting(folder, blocks=blocks, dry_run=dry_run, use_legacy=use_legacy)
            results["meetings"].append(result)
            results["processed"] += 1
            
            if result.get("blocks_failed"):
                results["failed"] += 1
            else:
                results["succeeded"] += 1
                
        except Exception as e:
            logger.error(f"Error processing {folder.name}: {e}")
            results["meetings"].append({"path": str(folder), "error": str(e)})
            results["processed"] += 1
            results["failed"] += 1
    
    logger.info(f"Queue complete: {results['succeeded']}/{results['processed']} succeeded")
    return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Process meeting transcripts with smart block selection")
    parser.add_argument("meeting_path", nargs="?", help="Specific meeting folder")
    parser.add_argument("--blocks", type=str, help="Comma-separated block codes (B01,B05) - overrides smart selector")
    parser.add_argument("--batch-size", type=int, default=5, help="Max meetings from queue")
    parser.add_argument("--dry-run", action="store_true", help="Preview without processing")
    parser.add_argument("--legacy", action="store_true", help="Use legacy static block selection (not smart selector)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    blocks = None
    if args.blocks:
        blocks = [b.strip().upper() for b in args.blocks.split(",")]
    
    if args.meeting_path:
        meeting_path = Path(args.meeting_path)
        if not meeting_path.exists():
            print(f"Error: Path not found: {meeting_path}")
            return 1
        results = process_meeting(meeting_path, blocks=blocks, dry_run=args.dry_run, use_legacy=args.legacy)
    else:
        results = process_queue(batch_size=args.batch_size, blocks=blocks, dry_run=args.dry_run, use_legacy=args.legacy)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if "meetings" in results:
            print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Queue Processing:")
            print(f"  Processed: {results['processed']}")
            print(f"  Succeeded: {results['succeeded']}")
            print(f"  Failed:    {results['failed']}")
            
            for m in results.get("meetings", []):
                meta = m.get("selection_metadata", {})
                method = meta.get("method", "unknown")
                print(f"\n  {m.get('path', 'unknown').split('/')[-1]}:")
                print(f"    Method: {method}")
                if meta.get("recipe"):
                    print(f"    Recipe: {meta['recipe']}")
                if m.get("blocks"):
                    print(f"    Blocks: {', '.join(m['blocks'])}")
        else:
            print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Meeting Processed:")
            print(f"  Path: {results.get('path')}")
            
            meta = results.get("selection_metadata", {})
            if meta:
                print(f"  Selection Method: {meta.get('method', 'unknown')}")
                if meta.get("recipe"):
                    print(f"  Recipe: {meta['recipe']}")
                if meta.get("reasoning"):
                    print(f"  Selection Reasoning:")
                    for block, reason in meta["reasoning"].items():
                        print(f"    {block}: {reason}")
            
            if results.get('blocks_generated'):
                print(f"  Blocks Generated: {len(results['blocks_generated'])}")
            if results.get('blocks'):
                print(f"  Blocks to Generate: {', '.join(results['blocks'])}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
