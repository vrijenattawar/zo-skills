#!/usr/bin/env python3
"""
Block Generator Orchestrator for Meeting Intelligence System

Spawns /zo/ask per block with retries, graceful failure handling,
and manifest logging. Designed for token-expensive generation.

Usage:
    python3 block_generator.py <meeting_path> [--blocks B01,B02] [--retry-failed] [--dry-run]
    python3 block_generator.py <meeting_path> --retry B01,B03  # Retry specific blocks
    python3 block_generator.py <meeting_path> --status  # Show generation status
    
Examples:
    python3 block_generator.py Personal/Meetings/Inbox/2026-01-26_John_x_Careerspan
    python3 block_generator.py Personal/Meetings/Inbox/2026-01-26_John_x_Careerspan --blocks B01,B08,B26
    python3 block_generator.py Personal/Meetings/Inbox/2026-01-26_John_x_Careerspan --retry B01 --max-retries 3
"""

import json
import os
import sys
import logging
import requests
import time
import argparse
from pathlib import Path
from datetime import datetime, UTC
from typing import Optional
from dataclasses import dataclass, field, asdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

PROMPTS_DIR = Path("./Prompts/Blocks")
BLOCK_INDEX = PROMPTS_DIR / "BLOCK_INDEX.yaml"

# Block name mapping
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


@dataclass
class GenerationResult:
    """Result of a block generation attempt."""
    block_code: str
    full_name: str
    status: str  # success, failed, skipped
    attempts: int = 0
    output_file: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))


@dataclass
class GenerationSession:
    """Track a generation session across multiple blocks."""
    meeting_path: str
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    results: list = field(default_factory=list)
    total_duration_seconds: float = 0.0
    
    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.results if r.status == "success")
    
    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "failed")
    
    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped")


def call_zo_api(prompt: str, timeout: int = 300, retries: int = 2, retry_delay: float = 5.0) -> tuple[str, int]:
    """
    Call Zo API to generate content with retry logic.
    
    Returns:
        tuple: (response_text, attempt_count)
    
    Raises:
        RuntimeError: If all retries exhausted
    """
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        raise RuntimeError("ZO_CLIENT_IDENTITY_TOKEN not set")
    
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"    API call attempt {attempt}/{retries}")
            
            response = requests.post(
                "<YOUR_WEBHOOK_URL>",
                headers={
                    "authorization": token,
                    "content-type": "application/json"
                },
                json={"input": prompt},
                timeout=timeout
            )
            
            if response.status_code == 200:
                output = response.json().get("output", "")
                if output and len(output.strip()) > 50:
                    return output, attempt
                else:
                    last_error = f"Empty or too-short response ({len(output)} chars)"
                    logger.warning(f"    {last_error}, retrying...")
            else:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(f"    {last_error}, retrying...")
                
        except requests.exceptions.Timeout:
            last_error = f"Request timeout after {timeout}s"
            logger.warning(f"    {last_error}, retrying...")
        except requests.exceptions.RequestException as e:
            last_error = f"Request failed: {str(e)}"
            logger.warning(f"    {last_error}, retrying...")
        
        if attempt < retries:
            time.sleep(retry_delay)
    
    raise RuntimeError(f"All {retries} attempts failed. Last error: {last_error}")


def load_prompt_template(block_code: str) -> Optional[str]:
    """Load canonical prompt from Prompts/Blocks/."""
    # Try standard naming
    prompt_path = PROMPTS_DIR / f"Generate_{block_code}.prompt.md"
    if prompt_path.exists():
        return prompt_path.read_text()
    
    # Try with full name suffix (e.g., Generate_B45_TEAM_DYNAMICS.prompt.md)
    full_name = BLOCK_NAMES.get(block_code, block_code)
    if "_" in full_name:
        suffix = "_".join(full_name.split("_")[1:])  # TEAM_DYNAMICS
        prompt_path = PROMPTS_DIR / f"Generate_{block_code}_{suffix}.prompt.md"
        if prompt_path.exists():
            return prompt_path.read_text()
    
    return None


def build_generation_prompt(block_code: str, transcript: str, context: dict) -> str:
    """Build the full prompt for block generation."""
    full_name = BLOCK_NAMES.get(block_code, block_code)
    description = BLOCK_DESCRIPTIONS.get(block_code, "Meeting intelligence block")
    
    prompt_template = load_prompt_template(block_code)
    
    # Truncate transcript to avoid token limits (30k chars ~= 7500 tokens)
    truncated_transcript = transcript[:30000]
    if len(transcript) > 30000:
        truncated_transcript += "\n\n[... transcript truncated for token limit ...]"
    
    if prompt_template:
        prompt = f"""{prompt_template}

## Transcript to Analyze
{truncated_transcript}

## Meeting Context
- Date: {context.get('date', 'Unknown')}
- Participants: {', '.join(context.get('participants', []))}
- Meeting Type: {context.get('meeting_type', 'external')}

## CRITICAL INSTRUCTION
Output ONLY the block content directly as markdown. Start with the heading "# {full_name}" immediately.
Do NOT include meta-commentary about what you're generating.
"""
    else:
        # Fallback for blocks without dedicated prompts
        prompt = f"""Generate the {full_name} intelligence block for this meeting transcript.

## Block Definition
{block_code}: {description}

## Meeting Context
- Date: {context.get('date', 'Unknown')}
- Participants: {', '.join(context.get('participants', ['Unknown']))}
- Meeting Type: {context.get('meeting_type', 'external')}

## Transcript
{truncated_transcript}

## Instructions
1. Analyze the transcript thoroughly
2. Extract information relevant to {block_code}
3. Format as clean markdown starting with "# {full_name}"
4. Be specific and actionable
5. Include direct quotes where relevant

Return ONLY the block content in markdown format."""

    return prompt


def generate_single_block(
    block_code: str,
    transcript: str,
    context: dict,
    output_dir: Path,
    max_retries: int = 2,
    timeout: int = 300
) -> GenerationResult:
    """
    Generate a single intelligence block.
    
    Args:
        block_code: Block code (e.g., "B01")
        transcript: Full meeting transcript
        context: Meeting context dict with date, participants, meeting_type
        output_dir: Directory to write output file
        max_retries: Max API retry attempts
        timeout: API timeout in seconds
    
    Returns:
        GenerationResult with status and metadata
    """
    full_name = BLOCK_NAMES.get(block_code, block_code)
    start_time = time.time()
    
    logger.info(f"  Generating {full_name}...")
    
    prompt = build_generation_prompt(block_code, transcript, context)
    
    try:
        content, attempts = call_zo_api(prompt, timeout=timeout, retries=max_retries)
        
        # Write output file
        output_file = output_dir / f"{full_name}.md"
        output_file.write_text(content)
        
        duration = time.time() - start_time
        logger.info(f"    ✓ Written: {full_name}.md ({len(content)} chars, {duration:.1f}s, attempt {attempts})")
        
        return GenerationResult(
            block_code=block_code,
            full_name=full_name,
            status="success",
            attempts=attempts,
            output_file=str(output_file),
            duration_seconds=duration
        )
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        logger.error(f"    ✗ Failed: {error_msg}")
        
        return GenerationResult(
            block_code=block_code,
            full_name=full_name,
            status="failed",
            attempts=max_retries,
            error=error_msg,
            duration_seconds=duration
        )


def load_manifest(meeting_path: Path) -> dict:
    """Load and return manifest.json from meeting folder."""
    manifest_path = meeting_path / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.json at {manifest_path}")
    return json.loads(manifest_path.read_text())


def save_manifest(meeting_path: Path, manifest: dict):
    """Save manifest back to meeting folder."""
    manifest_path = meeting_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))


def update_manifest_with_session(manifest: dict, session: GenerationSession):
    """Update manifest with generation session results."""
    # Ensure blocks_generated list exists
    if "blocks_generated" not in manifest:
        manifest["blocks_generated"] = []
    
    # Ensure blocks_failed list exists
    if "blocks_failed" not in manifest:
        manifest["blocks_failed"] = []
    
    # Track generation history
    if "generation_history" not in manifest:
        manifest["generation_history"] = []
    
    session_record = {
        "started_at": session.started_at,
        "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "total_duration_seconds": session.total_duration_seconds,
        "succeeded": session.succeeded,
        "failed": session.failed,
        "skipped": session.skipped,
        "results": [asdict(r) for r in session.results]
    }
    manifest["generation_history"].append(session_record)
    
    # Update blocks_generated and blocks_failed
    for result in session.results:
        if result.status == "success":
            if result.full_name not in manifest["blocks_generated"]:
                manifest["blocks_generated"].append(result.full_name)
            # Remove from failed if was there
            manifest["blocks_failed"] = [
                f for f in manifest["blocks_failed"]
                if not (isinstance(f, dict) and f.get("block") == result.full_name)
            ]
        elif result.status == "failed":
            # Only add if not already in failed list
            failed_blocks = [f.get("block") if isinstance(f, dict) else f for f in manifest["blocks_failed"]]
            if result.full_name not in failed_blocks:
                manifest["blocks_failed"].append({
                    "block": result.full_name,
                    "error": result.error,
                    "last_attempt": result.timestamp
                })
    
    # Update status
    if session.failed == 0 and session.succeeded > 0:
        manifest["status"] = "complete"
        manifest["processed_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    elif session.failed > 0:
        manifest["status"] = "partial"
    
    return manifest


def get_blocks_to_generate(
    manifest: dict,
    blocks_override: Optional[list[str]] = None,
    retry_failed: bool = False,
    retry_specific: Optional[list[str]] = None
) -> list[str]:
    """
    Determine which blocks to generate.
    
    Args:
        manifest: Meeting manifest
        blocks_override: Explicit block list (overrides selection)
        retry_failed: If True, regenerate all previously failed blocks
        retry_specific: Specific blocks to retry (regenerates even if already done)
    
    Returns:
        List of block codes to generate
    """
    already_generated = set()
    for name in manifest.get("blocks_generated", []):
        # Extract block code from full name (B01_DETAILED_RECAP -> B01)
        if "_" in name:
            code = name.split("_")[0]
            already_generated.add(code)
            # Handle B02_B05 special case
            if name.startswith("B02_B05"):
                already_generated.add("B02_B05")
    
    # Get failed blocks
    failed_blocks = set()
    for f in manifest.get("blocks_failed", []):
        name = f.get("block") if isinstance(f, dict) else f
        if "_" in name:
            code = name.split("_")[0]
            failed_blocks.add(code)
            if name.startswith("B02_B05"):
                failed_blocks.add("B02_B05")
    
    # Determine what to generate
    if retry_specific:
        # Retry specific blocks regardless of status
        return retry_specific
    
    if blocks_override:
        # Use explicit override list, skip already generated unless retrying
        return [b for b in blocks_override if b not in already_generated or retry_failed]
    
    # Use selection from block_selection if available
    selection = manifest.get("block_selection", {})
    if selection.get("method") in ["smart_selector_v2", "manual_override"]:
        all_blocks = []
        for b in selection.get("always_blocks", []):
            all_blocks.append(b)
        for b in selection.get("conditional_selected", []):
            all_blocks.append(b)
        for b in selection.get("triggered", []):
            all_blocks.append(b)
        
        if not all_blocks:
            # Fallback: check if there's an all_blocks list
            all_blocks = manifest.get("block_selection", {}).get("blocks", [])
    else:
        # No smart selection - use what's in the selection
        all_blocks = manifest.get("block_selection", {}).get("blocks", [])
    
    if retry_failed:
        # Include failed blocks for retry
        blocks_to_generate = [b for b in all_blocks if b not in already_generated or b in failed_blocks]
    else:
        # Skip already generated
        blocks_to_generate = [b for b in all_blocks if b not in already_generated]
    
    return blocks_to_generate


def show_status(meeting_path: Path):
    """Show generation status for a meeting."""
    manifest = load_manifest(meeting_path)
    
    print(f"\n=== Generation Status: {meeting_path.name} ===\n")
    
    print(f"Status: {manifest.get('status', 'unknown')}")
    
    selection = manifest.get("block_selection", {})
    if selection:
        print(f"\nBlock Selection:")
        print(f"  Method: {selection.get('method', 'unknown')}")
        if selection.get("recipe"):
            print(f"  Recipe: {selection['recipe']}")
        if selection.get("always_blocks"):
            print(f"  Always: {', '.join(selection['always_blocks'])}")
        if selection.get("conditional_selected"):
            print(f"  Conditional: {', '.join(selection['conditional_selected'])}")
        if selection.get("triggered"):
            print(f"  Triggered: {', '.join(selection['triggered'])}")
    
    generated = manifest.get("blocks_generated", [])
    failed = manifest.get("blocks_failed", [])
    
    print(f"\nGenerated ({len(generated)}):")
    for b in generated:
        print(f"  ✓ {b}")
    
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for f in failed:
            if isinstance(f, dict):
                print(f"  ✗ {f['block']}: {f.get('error', 'unknown error')[:50]}")
            else:
                print(f"  ✗ {f}")
    
    # Show generation history summary
    history = manifest.get("generation_history", [])
    if history:
        print(f"\nGeneration History ({len(history)} sessions):")
        for i, h in enumerate(history[-3:], 1):  # Show last 3
            print(f"  Session {i}: {h.get('succeeded', 0)} succeeded, {h.get('failed', 0)} failed ({h.get('total_duration_seconds', 0):.1f}s)")


def generate_blocks(
    meeting_path: Path,
    blocks: Optional[list[str]] = None,
    retry_failed: bool = False,
    retry_specific: Optional[list[str]] = None,
    max_retries: int = 2,
    timeout: int = 300,
    dry_run: bool = False
) -> GenerationSession:
    """
    Generate blocks for a meeting.
    
    Args:
        meeting_path: Path to meeting folder
        blocks: Explicit block list (overrides smart selection)
        retry_failed: If True, retry all previously failed blocks
        retry_specific: Specific block codes to retry
        max_retries: Max API retries per block
        timeout: API timeout in seconds
        dry_run: If True, show what would be done without generating
    
    Returns:
        GenerationSession with results
    """
    session = GenerationSession(meeting_path=str(meeting_path))
    
    # Load manifest
    manifest = load_manifest(meeting_path)
    
    # Load transcript
    transcript_file = meeting_path / manifest.get("transcript_file", "transcript.md")
    if not transcript_file.exists():
        # Try to find any transcript file
        for pattern in ["*.md", "*.txt"]:
            files = list(meeting_path.glob(pattern))
            transcript_files = [f for f in files if "transcript" in f.name.lower() or f.suffix in [".md", ".txt"]]
            if transcript_files:
                transcript_file = transcript_files[0]
                break
    
    if not transcript_file.exists():
        raise FileNotFoundError(f"No transcript found in {meeting_path}")
    
    transcript = transcript_file.read_text()
    if len(transcript.strip()) < 100:
        raise ValueError(f"Transcript too short ({len(transcript)} chars)")
    
    # Determine blocks to generate
    blocks_to_generate = get_blocks_to_generate(
        manifest,
        blocks_override=blocks,
        retry_failed=retry_failed,
        retry_specific=retry_specific
    )
    
    if not blocks_to_generate:
        logger.info("No blocks to generate (all complete or no selection)")
        return session
    
    # Build context
    participants = manifest.get("participants", [])
    if participants and isinstance(participants[0], dict):
        participants = [p.get("name", str(p)) for p in participants]
    
    context = {
        "date": manifest.get("date"),
        "participants": participants,
        "meeting_type": manifest.get("meeting_type", "external")
    }
    
    logger.info(f"Processing: {meeting_path.name}")
    logger.info(f"Blocks to generate: {', '.join(blocks_to_generate)}")
    
    if dry_run:
        logger.info("[DRY RUN] Would generate the above blocks")
        for b in blocks_to_generate:
            session.results.append(GenerationResult(
                block_code=b,
                full_name=BLOCK_NAMES.get(b, b),
                status="skipped"
            ))
        return session
    
    # Update manifest status
    manifest["status"] = "processing"
    save_manifest(meeting_path, manifest)
    
    # Generate each block
    start_time = time.time()
    for block_code in blocks_to_generate:
        result = generate_single_block(
            block_code=block_code,
            transcript=transcript,
            context=context,
            output_dir=meeting_path,
            max_retries=max_retries,
            timeout=timeout
        )
        session.results.append(result)
    
    session.total_duration_seconds = time.time() - start_time
    
    # Update manifest with results
    manifest = update_manifest_with_session(manifest, session)
    save_manifest(meeting_path, manifest)
    
    logger.info(f"\nGeneration complete: {session.succeeded}/{len(session.results)} succeeded in {session.total_duration_seconds:.1f}s")
    
    return session


def main():
    parser = argparse.ArgumentParser(
        description="Block Generator Orchestrator - spawns /zo/ask per block with retries"
    )
    parser.add_argument("meeting_path", help="Path to meeting folder")
    parser.add_argument("--blocks", type=str, help="Comma-separated block codes (B01,B08) - overrides smart selection")
    parser.add_argument("--retry-failed", action="store_true", help="Retry all previously failed blocks")
    parser.add_argument("--retry", type=str, help="Comma-separated blocks to retry (regenerates even if done)")
    parser.add_argument("--max-retries", type=int, default=2, help="Max API retries per block (default: 2)")
    parser.add_argument("--timeout", type=int, default=300, help="API timeout in seconds (default: 300)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without doing it")
    parser.add_argument("--status", action="store_true", help="Show generation status and exit")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    meeting_path = Path(args.meeting_path)
    if not meeting_path.is_absolute():
        meeting_path = Path(".") / meeting_path
    
    if not meeting_path.exists():
        print(f"Error: Path not found: {meeting_path}")
        return 1
    
    if args.status:
        show_status(meeting_path)
        return 0
    
    blocks = None
    if args.blocks:
        blocks = [b.strip().upper() for b in args.blocks.split(",")]
    
    retry_specific = None
    if args.retry:
        retry_specific = [b.strip().upper() for b in args.retry.split(",")]
    
    try:
        session = generate_blocks(
            meeting_path=meeting_path,
            blocks=blocks,
            retry_failed=args.retry_failed,
            retry_specific=retry_specific,
            max_retries=args.max_retries,
            timeout=args.timeout,
            dry_run=args.dry_run
        )
        
        if args.json:
            output = {
                "meeting_path": str(meeting_path),
                "started_at": session.started_at,
                "total_duration_seconds": session.total_duration_seconds,
                "succeeded": session.succeeded,
                "failed": session.failed,
                "skipped": session.skipped,
                "results": [asdict(r) for r in session.results]
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Generation Summary:")
            print(f"  Path: {meeting_path}")
            print(f"  Succeeded: {session.succeeded}")
            print(f"  Failed: {session.failed}")
            print(f"  Duration: {session.total_duration_seconds:.1f}s")
            
            if session.failed > 0:
                print(f"\nFailed blocks:")
                for r in session.results:
                    if r.status == "failed":
                        print(f"  ✗ {r.full_name}: {r.error[:60] if r.error else 'unknown'}")
        
        return 0 if session.failed == 0 else 1
        
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        if args.json:
            print(json.dumps({"error": str(e)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
