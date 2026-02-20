#!/usr/bin/env python3
"""
Meeting Ingestion - Processor Script

Orchestrates the meeting processing pipeline:
1. Manifest generation (which intelligence blocks to create)
2. Block generation (detailed analysis via LLM)
3. CRM sync (update stakeholder records)

Usage:
    python3 processor.py [meeting_path] [--blocks B01,B05,B08] [--skip-crm] [--dry-run]
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, UTC
from typing import List, Optional, Dict, Any

# Add scripts/scripts to path for imports
sys.path.insert(0, "./scripts/scripts")

from meeting_manifest_generator import generate_manifest, detect_meeting_type
from meeting_registry import MeetingRegistry
from meeting_orchestrator import MeetingOrchestrator
from meeting_normalizer import parse_folder_name
from meeting_config import MEETINGS_PATH, STAGING_PATH, LOG_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)sZ %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
MEETINGS_DIR = Path(MEETINGS_PATH)
STAGING_DIR = Path(STAGING_PATH)
LOG_FILE = Path(LOG_PATH)

# Block definitions for prompting
BLOCK_DEFINITIONS = {
    "B01_DETAILED_RECAP": "Comprehensive meeting summary covering all topics discussed, decisions made, and outcomes.",
    "B02_COMMITMENTS": "Explicit commitments made by participants during the meeting.",
    "B03_DECISIONS": "Key decisions made during the meeting with rationale.",
    "B04_OPEN_QUESTIONS": "Unresolved questions that need follow-up.",
    "B05_ACTION_ITEMS": "Concrete action items with owners and deadlines.",
    "B06_BUSINESS_CONTEXT": "Business implications and strategic context.",
    "B07_TONE_AND_CONTEXT": "Emotional tone, relationship dynamics, and interpersonal context.",
    "B08_STAKEHOLDER_INTELLIGENCE": "Insights about stakeholders - their interests, concerns, communication style, decision-making patterns.",
    "B10_RISKS_AND_FLAGS": "Potential risks, concerns, and red flags identified.",
    "B13_PLAN_OF_ACTION": "Coordinated plan of action based on meeting outcomes.",
    "B21_KEY_MOMENTS": "Significant moments, quotes, or turning points in the meeting.",
    "B25_DELIVERABLES": "Specific deliverables discussed or committed to.",
    "B26_MEETING_METADATA": "Meeting metadata: date, participants, duration, purpose.",
    "B28_STRATEGIC_INTELLIGENCE": "Long-term strategic implications and insights."
}

# Mapping from short codes to full block names
BLOCK_SHORT_TO_FULL = {
    "B01": "B01_DETAILED_RECAP",
    "B02": "B02_COMMITMENTS",
    "B03": "B03_DECISIONS",
    "B04": "B04_OPEN_QUESTIONS",
    "B05": "B05_ACTION_ITEMS",
    "B06": "B06_BUSINESS_CONTEXT",
    "B07": "B07_TONE_AND_CONTEXT",
    "B08": "B08_STAKEHOLDER_INTELLIGENCE",
    "B10": "B10_RISKS_AND_FLAGS",
    "B13": "B13_PLAN_OF_ACTION",
    "B21": "B21_KEY_MOMENTS",
    "B25": "B25_DELIVERABLES",
    "B26": "B26_MEETING_METADATA",
    "B28": "B28_STRATEGIC_INTELLIGENCE"
}

def normalize_block_code(code: str) -> str:
    """Convert short block code (B01) to full name (B01_DETAILED_RECAP) if needed."""
    code = code.strip().upper()
    if code in BLOCK_SHORT_TO_FULL:
        return BLOCK_SHORT_TO_FULL[code]
    return code


def load_prompt_file(block_code: str) -> Optional[str]:
    """Load canonical prompt from Prompts/Blocks/."""
    # Extract short block code (B01, B05) from full code (B01_DETAILED_RECAP)
    short_code = block_code.split('_')[0] if '_' in block_code else block_code
    prompt_path = Path(f"./Prompts/Blocks/Generate_{short_code}.prompt.md")
    if prompt_path.exists():
        return prompt_path.read_text()
    return None


def call_zo_api(prompt: str, output_format: Optional[dict] = None) -> Any:
    """
    Call Zo API to execute a task.
    """
    import requests
    
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        raise RuntimeError("ZO_CLIENT_IDENTITY_TOKEN not set")
    
    payload = {"input": prompt}
    if output_format:
        payload["output_format"] = output_format
    
    response = requests.post(
        "<YOUR_WEBHOOK_URL>",
        headers={
            "authorization": token,
            "content-type": "application/json"
        },
        json=payload,
        timeout=300  # Longer timeout for block generation
    )
    
    if response.status_code != 200:
        raise RuntimeError(f"Zo API error: {response.status_code} - {response.text}")
    
    return response.json().get("output", "")


def find_transcript(meeting_path: Path) -> Optional[Path]:
    """
    Find the transcript file in a meeting directory.
    Looks for .md or .txt files that look like transcripts.
    """
    if meeting_path.is_file():
        return meeting_path
    
    # Look for transcript files
    transcript_patterns = [
        "*transcript*.md",
        "*transcript*.txt",
        "*.normalized.md",
        "*.md"
    ]
    
    for pattern in transcript_patterns:
        files = list(meeting_path.glob(pattern))
        if files:
            # Prefer normalized versions
            normalized = [f for f in files if "normalized" in f.name.lower()]
            if normalized:
                return normalized[0]
            return files[0]
    
    return None


def generate_block(
    transcript_text: str,
    block_code: str,
    meeting_context: dict
) -> str:
    """
    Generate a single intelligence block using Zo API.
    
    Args:
        transcript_text: Full meeting transcript
        block_code: Block identifier (e.g., "B01_DETAILED_RECAP")
        meeting_context: Dict with date, participants, meeting_type
    
    Returns:
        Generated block content as markdown
    """
    # Try to load canonical prompt
    prompt_template = load_prompt_file(block_code)
    
    if prompt_template:
        # Inject transcript and context into the prompt template
        prompt = f"""{prompt_template}

## Transcript to Analyze
{transcript_text[:30000]}

## Meeting Context
- Date: {meeting_context.get('date')}
- Participants: {', '.join(meeting_context.get('participants', []))}
- Meeting Type: {meeting_context.get('meeting_type', 'external')}

## CRITICAL INSTRUCTION
You MUST output the actual block content directly. Do NOT describe what you would generate. Do NOT output meta-commentary like "Generated B01 block..." or "The recap synthesizes...". 
Output ONLY the block content itself, starting with the YAML frontmatter (---) and then the markdown body. Begin your response with "---" immediately.
"""
    else:
        # Fallback to inline definition
        block_description = BLOCK_DEFINITIONS.get(block_code, "Meeting intelligence block")
        prompt = f"""Generate the {block_code} intelligence block for this meeting transcript.

## Block Definition
{block_code}: {block_description}

## Meeting Context
- Date: {meeting_context.get('date', 'Unknown')}
- Participants: {', '.join(meeting_context.get('participants', ['Unknown']))}
- Meeting Type: {meeting_context.get('meeting_type', 'external')}

## Transcript
{transcript_text[:30000]}  # Truncate very long transcripts

## Instructions
1. Analyze the transcript thoroughly
2. Extract information relevant to {block_code}
3. Format the output as clean markdown
4. Be specific and actionable
5. Include direct quotes where relevant
6. For stakeholder intelligence, focus on individual behaviors and patterns

Return ONLY the block content in markdown format, starting with a header."""

    result = call_zo_api(prompt)
    return result


def process_meeting(
    meeting_path: Path,
    blocks: Optional[List[str]] = None,
    skip_crm: bool = False,
    dry_run: bool = False
) -> dict:
    """
    Process a single meeting through the full pipeline.
    
    Args:
        meeting_path: Path to meeting folder or transcript file
        blocks: List of block codes to generate (None = auto-detect)
        skip_crm: Skip CRM sync step
        dry_run: Only show what would be done
    
    Returns:
        Dict with processing results
    """
    logger.info(f"Processing meeting: {meeting_path}")
    
    meeting_dir = meeting_path if meeting_path.is_dir() else meeting_path.parent
    
    # Find transcript
    transcript_path = find_transcript(meeting_path)
    if not transcript_path:
        raise FileNotFoundError(f"No transcript found in {meeting_path}")
    
    logger.info(f"Using transcript: {transcript_path}")
    
    # Read transcript
    transcript_text = transcript_path.read_text()
    if len(transcript_text.strip()) < 100:
        raise ValueError(f"Transcript too short ({len(transcript_text)} chars)")
    
    # Detect meeting type and generate manifest if needed
    meeting_type = detect_meeting_type(meeting_dir.name)
    logger.info(f"Meeting type: {meeting_type}")
    
    if blocks:
        manifest = blocks
    else:
        manifest = generate_manifest(transcript_path, meeting_dir)
    
    logger.info(f"Manifest: {', '.join(manifest)}")
    
    # Extract context
    parsed = parse_folder_name(meeting_dir.name)
    context = {
        "date": parsed.get("date") if parsed else "Unknown",
        "participants": parsed.get("participants", []) if parsed else [],
        "meeting_type": meeting_type
    }
    
    results = {
        "meeting_path": str(meeting_path),
        "transcript": str(transcript_path),
        "meeting_type": meeting_type,
        "manifest": manifest,
        "blocks_generated": [],
        "blocks_failed": [],
        "crm_synced": False
    }
    
    if dry_run:
        logger.info("Dry run - would generate blocks:")
        for block in manifest:
            logger.info(f"  - {block}")
        results["dry_run"] = True
        return results
    
    # Generate blocks
    for block_code in manifest:
        # Normalize to full name (B01 -> B01_DETAILED_RECAP)
        full_block_code = normalize_block_code(block_code)
        logger.info(f"Generating {full_block_code}...")
        
        try:
            block_content = generate_block(transcript_text, full_block_code, context)
            
            # Write block to file using FULL name
            block_file = meeting_dir / f"{full_block_code}.md"
            block_file.write_text(block_content)
            logger.info(f"  Written: {block_file}")
            
            results["blocks_generated"].append(full_block_code)
            
        except Exception as e:
            logger.error(f"  Failed: {e}")
            results["blocks_failed"].append({
                "block": full_block_code,
                "error": str(e)
            })
    
    # Write manifest
    manifest_file = meeting_dir / "manifest.json"
    manifest_data = {
        "meeting_id": meeting_dir.name,
        "date": context["date"],
        "participants": context["participants"],
        "meeting_type": meeting_type,
        "blocks_generated": results["blocks_generated"],
        "processed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z")
    }
    manifest_file.write_text(json.dumps(manifest_data, indent=2))
    logger.info(f"Manifest written: {manifest_file}")
    
    # CRM sync removed - implement your own integration
    
    # Update meeting folder name with status suffix if needed
    # e.g., _[M] for manifested, _[B] for blocked, _[C] for complete
    if not meeting_dir.name.endswith("_[C]") and not meeting_dir.name.endswith("_[B]"):
        new_name = meeting_dir.name + "_[B]"  # Blocked = intelligence blocks generated
        new_path = meeting_dir.parent / new_name
        if not new_path.exists():
            meeting_dir.rename(new_path)
            logger.info(f"Renamed to: {new_name}")
            results["renamed_to"] = str(new_path)
    
    return results


def process_queue(
    batch_size: int = 5,
    blocks: Optional[List[str]] = None,
    skip_crm: bool = False,
    dry_run: bool = False
) -> dict:
    """
    Process all meetings in the staging queue.
    
    Args:
        batch_size: Maximum meetings to process
        blocks: Block list to generate (None = auto-detect per meeting)
        skip_crm: Skip CRM sync
        dry_run: Only show what would be done
    
    Returns:
        Dict with overall results
    """
    logger.info(f"Processing staging queue (batch_size={batch_size})")
    
    if not STAGING_DIR.exists():
        logger.info("Staging directory does not exist")
        return {"processed": 0, "meetings": []}
    
    # Find meetings to process
    # Look for .md files directly or folders
    candidates = []
    
    # Direct transcript files
    for md_file in STAGING_DIR.glob("*.md"):
        candidates.append(md_file)
    
    # Meeting folders (with transcripts inside)
    for folder in STAGING_DIR.iterdir():
        if folder.is_dir() and not folder.name.startswith("."):
            transcript = find_transcript(folder)
            if transcript:
                candidates.append(folder)
    
    logger.info(f"Found {len(candidates)} candidates in staging")
    
    results = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "meetings": []
    }
    
    for candidate in candidates[:batch_size]:
        try:
            meeting_result = process_meeting(
                candidate,
                blocks=blocks,
                skip_crm=skip_crm,
                dry_run=dry_run
            )
            results["meetings"].append(meeting_result)
            results["processed"] += 1
            if not meeting_result.get("blocks_failed"):
                results["succeeded"] += 1
            else:
                results["failed"] += 1
                
        except Exception as e:
            logger.error(f"Failed to process {candidate}: {e}")
            results["meetings"].append({
                "meeting_path": str(candidate),
                "error": str(e)
            })
            results["processed"] += 1
            results["failed"] += 1
    
    logger.info(f"Queue processing complete: {results['succeeded']}/{results['processed']} succeeded")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Process meeting transcripts through intelligence pipeline"
    )
    parser.add_argument(
        "meeting_path",
        nargs="?",
        help="Path to meeting folder or transcript (omit to process staging queue)"
    )
    parser.add_argument(
        "--blocks",
        type=str,
        help="Comma-separated list of blocks to generate (e.g., B01,B05,B08)"
    )
    parser.add_argument(
        "--skip-crm",
        action="store_true",
        help="Skip CRM synchronization"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Max meetings to process from queue (default: 5)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without doing it"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    # Parse blocks
    blocks = None
    if args.blocks:
        blocks = [normalize_block_code(b) for b in args.blocks.split(",")]
        # Validate blocks
        for b in blocks:
            if b not in BLOCK_DEFINITIONS:
                logger.warning(f"Unknown block: {b}")
    
    try:
        if args.meeting_path:
            # Process specific meeting
            meeting_path = Path(args.meeting_path)
            if not meeting_path.exists():
                raise FileNotFoundError(f"Meeting path not found: {meeting_path}")
            
            results = process_meeting(
                meeting_path,
                blocks=blocks,
                skip_crm=args.skip_crm,
                dry_run=args.dry_run
            )
        else:
            # Process staging queue
            results = process_queue(
                batch_size=args.batch_size,
                blocks=blocks,
                skip_crm=args.skip_crm,
                dry_run=args.dry_run
            )
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            if "meetings" in results:
                # Queue mode
                print(f"\nProcessed: {results['processed']}")
                print(f"Succeeded: {results['succeeded']}")
                print(f"Failed:    {results['failed']}")
            else:
                # Single meeting mode
                print(f"\nMeeting: {results.get('meeting_path')}")
                print(f"Type:    {results.get('meeting_type')}")
                print(f"Blocks:  {len(results.get('blocks_generated', []))}")
                if results.get('blocks_failed'):
                    print(f"Failed:  {len(results.get('blocks_failed'))}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
