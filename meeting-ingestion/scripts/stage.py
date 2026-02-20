#!/usr/bin/env python3
"""
Meeting Ingestion - Stage Script

Prepares raw transcripts for processing by:
1. Wrapping standalone .md files in properly-named folders
2. Normalizing folder names
3. Creating initial manifest.json

Usage:
    python3 stage.py [--dry-run]
"""

import json
import re
import logging
import shutil
from pathlib import Path
from datetime import datetime, UTC
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

INBOX = Path("./Personal/Meetings/Inbox")


def extract_date(text: str) -> Optional[str]:
    """Extract YYYY-MM-DD date from text."""
    patterns = [
        r'(\d{4}-\d{2}-\d{2})',
        r'(\d{4})\D?(\d{2})\D?(\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            if len(match.groups()) == 1:
                return match.group(1)
            else:
                return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def extract_participants(text: str) -> list[str]:
    """Extract participant names from filename."""
    text = re.sub(r'\d{4}-\d{2}-\d{2}', '', text)
    text = re.sub(r'-transcript.*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\.(md|txt|docx)$', '', text, flags=re.IGNORECASE)
    
    for sep in ['_x_', ' x ', '_and_', ' and ', '_&_', ' & ']:
        if sep in text.lower():
            parts = re.split(re.escape(sep), text, flags=re.IGNORECASE)
            return [clean_name(p) for p in parts if clean_name(p)]
    
    parts = re.split(r'[_\-\s]+', text)
    names = []
    for part in parts:
        cleaned = clean_name(part)
        if cleaned and len(cleaned) > 2:
            names.append(cleaned)
    return names[:3]


def clean_name(name: str) -> str:
    """Clean a participant name."""
    name = name.strip()
    name = re.sub(r'(gmailcom|mycareerspancom|theapplyai|com|ai|org)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[^a-zA-Z\s]', '', name)
    name = name.strip()
    if name:
        return name.title()
    return ""


def generate_folder_name(date: str, participants: list[str], original: str) -> str:
    """Generate a clean folder name."""
    if not date:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
    
    if participants:
        name_part = "-".join(p.replace(" ", "") for p in participants[:2])
    else:
        cleaned = re.sub(r'\d{4}-\d{2}-\d{2}', '', original)
        cleaned = re.sub(r'-transcript.*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\.(md|txt)$', '', cleaned)
        cleaned = re.sub(r'[_\s]+', '-', cleaned)
        cleaned = re.sub(r'-+', '-', cleaned)
        cleaned = cleaned.strip('-')
        name_part = cleaned[:40] if cleaned else "meeting"
    
    return f"{date}_{name_part}"


def create_manifest(folder: Path, date: str, participants: list[str], 
                   transcript_file: str, meeting_type: str = "external") -> dict:
    """Create initial manifest.json."""
    manifest = {
        "meeting_id": folder.name,
        "date": date or "unknown",
        "participants": participants,
        "meeting_type": meeting_type,
        "status": "staged",
        "transcript_file": transcript_file,
        "blocks_requested": [],
        "blocks_generated": [],
        "blocks_failed": [],
        "staged_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "processed_at": None,
        "archived_at": None,
        "error": None
    }
    return manifest


def detect_meeting_type(name: str, participants: list[str]) -> str:
    """Detect if meeting is internal or external."""
    internal_keywords = ['standup', 'internal', 'sync', 'team', 'planning', 'retro']
    careerspan_people = ['<team_member_1>', '<team_member_2>', '<team_member_3>', '<team_member_4>', '<user>']
    
    name_lower = name.lower()
    for keyword in internal_keywords:
        if keyword in name_lower:
            return "internal"
    
    if participants:
        participant_lower = [p.lower() for p in participants]
        if all(any(cp in pl for cp in careerspan_people) for pl in participant_lower):
            return "internal"
    
    return "external"


def stage_file(file_path: Path, dry_run: bool = False) -> dict:
    """Stage a single transcript file into a folder."""
    logger.info(f"Staging: {file_path.name}")
    
    date = extract_date(file_path.name)
    participants = extract_participants(file_path.name)
    folder_name = generate_folder_name(date, participants, file_path.stem)
    
    target_folder = INBOX / folder_name
    
    result = {
        "original": file_path.name,
        "folder": folder_name,
        "date": date,
        "participants": participants,
        "action": "create_folder"
    }
    
    if target_folder.exists():
        counter = 2
        while (INBOX / f"{folder_name}-{counter}").exists():
            counter += 1
        folder_name = f"{folder_name}-{counter}"
        target_folder = INBOX / folder_name
        result["folder"] = folder_name
        result["note"] = "renamed to avoid conflict"
    
    if dry_run:
        result["dry_run"] = True
        logger.info(f"  Would create: {folder_name}/")
        logger.info(f"  Would move transcript to: {folder_name}/transcript.md")
        return result
    
    target_folder.mkdir(parents=True, exist_ok=True)
    
    transcript_dest = target_folder / "transcript.md"
    shutil.move(str(file_path), str(transcript_dest))
    logger.info(f"  Moved to: {transcript_dest}")
    
    meeting_type = detect_meeting_type(folder_name, participants)
    manifest = create_manifest(target_folder, date, participants, "transcript.md", meeting_type)
    manifest_path = target_folder / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info(f"  Created manifest.json (status: staged)")
    
    result["success"] = True
    return result


def stage_folder(folder_path: Path, dry_run: bool = False) -> dict:
    """Ensure an existing folder has proper structure."""
    logger.info(f"Checking folder: {folder_path.name}")
    
    result = {
        "folder": folder_path.name,
        "action": "verify_folder"
    }
    
    transcript = None
    for pattern in ["transcript.md", "*.md", "*.txt"]:
        files = list(folder_path.glob(pattern))
        # Filter out block files when looking for transcript
        files = [f for f in files if not re.match(r'^B\d{2}_', f.name)]
        if files:
            transcript = files[0]
            break
    
    if not transcript:
        result["error"] = "no transcript found"
        result["success"] = False
        return result
    
    manifest_path = folder_path / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("status") in ["staged", "processing", "complete"]:
                result["action"] = "already_staged"
                result["status"] = manifest.get("status")
                result["success"] = True
                logger.info(f"  Already staged (status: {manifest.get('status')})")
                return result
        except json.JSONDecodeError:
            pass
    
    if transcript.name != "transcript.md":
        if not dry_run:
            new_path = folder_path / "transcript.md"
            if not new_path.exists():
                transcript.rename(new_path)
                logger.info(f"  Renamed {transcript.name} → transcript.md")
            result["renamed_transcript"] = True
    
    date = extract_date(folder_path.name)
    participants = extract_participants(folder_path.name)
    meeting_type = detect_meeting_type(folder_path.name, participants)
    
    # Detect existing block files
    existing_blocks = []
    block_pattern = re.compile(r'^(B\d{2}_[A-Z_]+)\.md$')
    for f in folder_path.iterdir():
        if f.is_file():
            match = block_pattern.match(f.name)
            if match:
                existing_blocks.append(match.group(1))
    
    # Determine status based on existing blocks
    status = "staged"
    if existing_blocks:
        status = "complete"
        logger.info(f"  Found {len(existing_blocks)} existing blocks, marking as complete")
    
    if not dry_run:
        manifest = create_manifest(folder_path, date, participants, "transcript.md", meeting_type)
        manifest["status"] = status
        manifest["blocks_generated"] = existing_blocks
        if existing_blocks:
            manifest["processed_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        manifest_path.write_text(json.dumps(manifest, indent=2))
        logger.info(f"  Created manifest.json (status: {status})")
    
    result["success"] = True
    result["existing_blocks"] = len(existing_blocks)
    return result


def fix_inbox_mess(dry_run: bool = False) -> dict:
    """Fix orphaned block files in Inbox root."""
    logger.info("Checking for orphaned files in Inbox root...")
    
    block_pattern = re.compile(r'^B\d{2}_.*\.md$')
    orphaned_files = []
    
    for item in INBOX.iterdir():
        if item.is_file() and block_pattern.match(item.name):
            orphaned_files.append(item)
    
    orphan_manifest = INBOX / "manifest.json"
    if orphan_manifest.exists():
        try:
            data = json.loads(orphan_manifest.read_text())
            if data.get("meeting_id") == "Inbox":
                orphaned_files.append(orphan_manifest)
        except:
            pass
    
    if not orphaned_files:
        return {"orphaned_files": 0, "action": "none_found"}
    
    logger.info(f"Found {len(orphaned_files)} orphaned files")
    
    quarantine = INBOX / "_orphaned_blocks"
    if not dry_run:
        quarantine.mkdir(exist_ok=True)
        for f in orphaned_files:
            dest = quarantine / f.name
            shutil.move(str(f), str(dest))
            logger.info(f"  Moved to _orphaned_blocks/: {f.name}")
    else:
        for f in orphaned_files:
            logger.info(f"  Would quarantine: {f.name}")
    
    return {
        "orphaned_files": len(orphaned_files),
        "action": "quarantined",
        "dry_run": dry_run
    }


def is_orphaned_block(filename: str) -> bool:
    """Check if a file is an orphaned block file (not a transcript)."""
    block_pattern = re.compile(r'^B\d{2}_.*\.md$')
    return bool(block_pattern.match(filename)) or filename == "manifest.json"


def is_transcript_file(filename: str) -> bool:
    """Check if a file looks like a transcript (not a block or manifest)."""
    if is_orphaned_block(filename):
        return False
    lower = filename.lower()
    return (lower.endswith(('.md', '.txt')) and 
            ('transcript' in lower or 
             re.search(r'\d{4}-\d{2}-\d{2}', filename)))


def stage_all(dry_run: bool = False) -> dict:
    """Stage all items in Inbox."""
    if not INBOX.exists():
        logger.error(f"Inbox not found: {INBOX}")
        return {"error": "inbox_not_found"}
    
    # FIRST: Quarantine orphaned blocks before staging
    fix_result = fix_inbox_mess(dry_run)
    
    results = {
        "fix_result": fix_result,
        "staged": [],
        "skipped": [],
        "errors": []
    }
    
    # Re-scan after quarantine (files may have been moved)
    for item in sorted(INBOX.iterdir()):
        if item.name.startswith((".", "_")):
            continue
        
        # Skip orphaned blocks (should already be quarantined, but safety check)
        if item.is_file() and is_orphaned_block(item.name):
            logger.info(f"Skipping orphaned block: {item.name}")
            continue
        
        if item.is_file() and item.suffix in [".md", ".txt"]:
            # Only stage files that look like transcripts
            if not is_transcript_file(item.name):
                logger.info(f"Skipping non-transcript file: {item.name}")
                continue
                
            try:
                result = stage_file(item, dry_run)
                if result.get("success") or result.get("dry_run"):
                    results["staged"].append(result)
                else:
                    results["errors"].append(result)
            except Exception as e:
                logger.error(f"  Error staging {item.name}: {e}")
                results["errors"].append({"file": item.name, "error": str(e)})
        
        elif item.is_dir():
            try:
                result = stage_folder(item, dry_run)
                if result.get("action") == "already_staged":
                    results["skipped"].append(result)
                elif result.get("success") or result.get("dry_run"):
                    results["staged"].append(result)
                else:
                    results["errors"].append(result)
            except Exception as e:
                logger.error(f"  Error checking {item.name}: {e}")
                results["errors"].append({"folder": item.name, "error": str(e)})
    
    logger.info(f"\nStaging complete: {len(results['staged'])} staged, "
                f"{len(results['skipped'])} skipped, {len(results['errors'])} errors")
    
    return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Stage transcripts for processing")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    results = stage_all(dry_run=args.dry_run)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Staging Results:")
        print(f"  Staged:  {len(results.get('staged', []))}")
        print(f"  Skipped: {len(results.get('skipped', []))}")
        print(f"  Errors:  {len(results.get('errors', []))}")
        
        if results.get('fix_result', {}).get('orphaned_files', 0) > 0:
            print(f"\n  Fixed orphaned files: {results['fix_result']['orphaned_files']}")


if __name__ == "__main__":
    main()
