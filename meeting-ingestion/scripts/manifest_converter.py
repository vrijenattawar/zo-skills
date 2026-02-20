#!/usr/bin/env python3
"""
Legacy Manifest Converter for Meeting System v3

Converts legacy manifest.json files (v1.0, v2.0) to v3 schema.
Handles various legacy shapes, missing fields, and edge cases.
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
import re

def infer_meeting_type(legacy: dict, folder_path: Path) -> str:
    """Infer meeting type from legacy manifest or folder name."""
    
    # Check if meeting_type already exists
    if "meeting_type" in legacy:
        return legacy["meeting_type"]
    
    # Check participants for internal team members
    participants = legacy.get("participants", [])
    if participants:
        internal_keywords = ["<name1>", "<name2>", "<name3>", "<name4>", "<user>"]
        for participant in participants:
            participant_str = str(participant).lower()
            if any(keyword in participant_str for keyword in internal_keywords):
                return "internal"
    
    # Check folder name for patterns
    folder_name = folder_path.name.lower()
    internal_patterns = ["[p]", "_p", "standup", "daily", "internal", "team"]
    external_patterns = ["external", "x-", "_x_"]
    
    if any(pattern in folder_name for pattern in internal_patterns):
        return "internal"
    elif any(pattern in folder_name for pattern in external_patterns):
        return "external"
    
    # Default to external for safety
    return "external"

def extract_date_from_folder(folder_path: Path) -> Optional[str]:
    """Extract date from folder name if not in manifest."""
    folder_name = folder_path.name
    
    # Try to match YYYY-MM-DD pattern
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", folder_name)
    if date_match:
        return date_match.group(1)
    
    return None

def extract_participants(legacy: dict, folder_path: Path) -> Dict[str, Any]:
    """Extract and normalize participants."""
    result = {
        "identified": [],
        "unidentified": [],
        "confidence": 1.0
    }
    
    # Handle v2 participants array
    if "participants" in legacy and isinstance(legacy["participants"], list):
        for p in legacy["participants"]:
            if isinstance(p, str):
                result["identified"].append({
                    "name": p,
                    "email": None,
                    "crm_id": None,
                    "role": "attendee"
                })
            elif isinstance(p, dict):
                result["identified"].append({
                    "name": p.get("name", "Unknown"),
                    "email": p.get("email"),
                    "crm_id": p.get("crm_id"),
                    "role": p.get("role", "attendee")
                })
    
    # If no participants, try to infer from folder name
    if not result["identified"]:
        folder_name = folder_path.name
        
        # Look for names in folder (simplistic approach)
        name_patterns = ["<user>", "<name1>", "<name2>", "<name3>", "<name4>", "<name5>"]
        found_names = []
        
        for pattern in name_patterns:
            if pattern in folder_name.lower():
                found_names.append({
                    "name": pattern.capitalize(),
                    "email": None,
                    "crm_id": None,
                    "role": "attendee"
                })
        
        if found_names:
            result["identified"] = found_names
            result["confidence"] = 0.5  # Low confidence for inferred participants
        else:
            # Mark for HITL if no participants can be identified
            result["confidence"] = 0.0
    
    return result

def generate_meeting_id(legacy: dict, folder_path: Path) -> str:
    """Generate meeting_id following v3 convention."""
    
    # Use meeting_folder if available
    if "meeting_folder" in legacy:
        return legacy["meeting_folder"]
    
    # Use meeting_id if available
    if "meeting_id" in legacy:
        return legacy["meeting_id"]
    
    # Use folder name
    return folder_path.name

def generate_status_history(legacy: dict) -> List[Dict[str, str]]:
    """Generate status_history from legacy status."""
    
    current_time = datetime.now(UTC).isoformat().replace('+00:00', 'Z')
    status = legacy.get("status", "unknown")
    
    # Map legacy statuses to v3 statuses
    status_mapping = {
        "manifest_generated": "ingested", 
        "pending_processing": "ingested",
        "processed": "processed",
        "processing": "identified",
        "completed": "processed",
        "ready": "ready"
    }
    
    v3_status = status_mapping.get(status, "ingested")
    
    history = [
        {"status": "raw", "at": legacy.get("generated_at", current_time)}
    ]
    
    if v3_status != "raw":
        history.append({
            "status": v3_status,
            "at": legacy.get("last_updated", legacy.get("generated_at", current_time))
        })
    
    return history

def convert_blocks_section(legacy: dict) -> Dict[str, Any]:
    """Convert legacy blocks_generated to v3 blocks format."""
    
    blocks_gen = legacy.get("blocks_generated", {})
    
    # Handle case where blocks_generated is a list instead of dict
    if isinstance(blocks_gen, list):
        # Convert list of block names to generated status
        requested = ["B00", "B26"]  # Always include these
        generated = []
        
        for block_name in blocks_gen:
            if "B01" in block_name or "RECAP" in block_name:
                requested.append("B01")
                generated.append("B01")
            elif "B08" in block_name or "STAKEHOLDER" in block_name:
                requested.append("B08")
                generated.append("B08")
            elif "B03" in block_name or "DECISIONS" in block_name:
                requested.append("B03")
                generated.append("B03")
            elif "B21" in block_name or "KEY_MOMENTS" in block_name:
                requested.append("B21")
                generated.append("B21")
            elif "B26" in block_name or "METADATA" in block_name:
                generated.append("B26")
        
        # Include B00 if any blocks were processed
        if generated:
            generated.append("B00")
        
        return {
            "policy": "external_standard",
            "requested": list(set(requested)),
            "generated": list(set(generated)),
            "failed": [],
            "skipped": []
        }
    
    # Map legacy block indicators to actual block codes
    requested = []
    generated = []
    
    if blocks_gen.get("brief"):
        requested.extend(["B01"])  # Detailed Recap
        generated.extend(["B01"])
    
    if blocks_gen.get("stakeholder_intelligence"):
        requested.extend(["B08"])  # Stakeholder Intelligence
        generated.extend(["B08"])
    
    if blocks_gen.get("decisions"):
        requested.extend(["B03"])  # Decisions
        generated.extend(["B03"])
    
    if blocks_gen.get("tone_and_context"):
        requested.extend(["B21"])  # Key Moments
        generated.extend(["B21"])
    
    # Always include B00 (Zo Take Heed) and B26 (Meeting Metadata)
    requested.extend(["B00", "B26"])
    if legacy.get("status") in ["processed", "completed"]:
        generated.extend(["B00", "B26"])
    
    return {
        "policy": "external_standard",  # Will be adjusted based on meeting_type
        "requested": list(set(requested)),
        "generated": list(set(generated)),
        "failed": [],
        "skipped": []
    }

def generate_quality_gate(legacy: dict, participants: dict) -> Dict[str, Any]:
    """Generate quality gate section."""
    
    blocks_gen = legacy.get("blocks_generated", {})
    
    # Handle case where blocks_generated is a list
    if isinstance(blocks_gen, list):
        has_transcript = len(blocks_gen) > 0
    else:
        has_transcript = blocks_gen.get("transcript_processed", False)
    
    participants_identified = participants["confidence"] > 0.5
    meeting_type_determined = True  # We always determine this
    
    checks = {
        "has_transcript": has_transcript,
        "participants_identified": participants_identified,
        "meeting_type_determined": meeting_type_determined,
        "no_hitl_pending": participants["confidence"] > 0.7
    }
    
    score = sum(checks.values()) / len(checks)
    passed = score >= 0.75
    
    return {
        "passed": passed,
        "checks": checks,
        "score": score
    }

def convert_to_v3(legacy: dict, folder_path: Path) -> dict:
    """Convert legacy manifest to v3 schema."""
    
    meeting_date = legacy.get("meeting_date") or legacy.get("date") or extract_date_from_folder(folder_path)
    meeting_type = infer_meeting_type(legacy, folder_path)
    participants = extract_participants(legacy, folder_path)
    meeting_id = generate_meeting_id(legacy, folder_path)
    
    # Extract meeting title
    meeting_title = legacy.get("meeting_title", legacy.get("meeting_folder", folder_path.name))
    
    # Remove date prefix from title if present
    if meeting_title and meeting_date:
        meeting_title = re.sub(f"^{re.escape(meeting_date)}_", "", meeting_title)
    
    # Generate current timestamp
    current_time = datetime.now(UTC).isoformat().replace('+00:00', 'Z')
    
    v3_manifest = {
        "$schema": "manifest-v3",
        "meeting_id": meeting_id,
        "status": legacy.get("status", "ingested"),
        "status_history": generate_status_history(legacy),
        
        "source": {
            "type": "legacy_migration", 
            "original_filename": f"{meeting_id}.legacy",
            "ingested_at": legacy.get("generated_at", current_time)
        },
        
        "meeting": {
            "date": meeting_date,
            "time_utc": None,  # Not available in legacy
            "duration_minutes": legacy.get("recording_duration_seconds", 0) // 60 if legacy.get("recording_duration_seconds") else None,
            "title": meeting_title,
            "type": meeting_type,
            "summary": "Legacy meeting - summary not available"
        },
        
        "participants": participants,
        
        "calendar_match": {
            "event_id": None,
            "confidence": 0.0,
            "method": "none"
        },
        
        "quality_gate": generate_quality_gate(legacy, participants),
        
        "blocks": convert_blocks_section(legacy),
        
        "hitl": {
            "queue_id": None,
            "reason": "Low participant confidence" if participants["confidence"] < 0.5 else None,
            "resolved_at": None
        },
        
        "timestamps": {
            "created_at": legacy.get("generated_at", current_time),
            "ingested_at": legacy.get("generated_at", current_time),
            "identified_at": legacy.get("transition_timestamp", legacy.get("generated_at")),
            "gated_at": legacy.get("last_updated", current_time) if legacy.get("status") == "processed" else None,
            "processed_at": legacy.get("processed_at", legacy.get("last_updated")) if legacy.get("status") == "processed" else None,
            "archived_at": None
        }
    }
    
    # Adjust blocks policy based on meeting type
    if meeting_type == "internal":
        v3_manifest["blocks"]["policy"] = "internal_standard"
    
    return v3_manifest

def main():
    parser = argparse.ArgumentParser(description="Convert legacy manifest to v3 schema")
    parser.add_argument("folder_path", type=Path, help="Path to meeting folder")
    parser.add_argument("--dry-run", action="store_true", help="Show diff without modifying")
    parser.add_argument("--output", type=Path, help="Output file (default: folder_path/manifest.json)")
    
    args = parser.parse_args()
    
    if not args.folder_path.exists():
        print(f"Error: Folder {args.folder_path} does not exist")
        return 1
    
    manifest_path = args.folder_path / "manifest.json"
    if not manifest_path.exists():
        print(f"Error: No manifest.json found in {args.folder_path}")
        return 1
    
    try:
        with open(manifest_path, 'r') as f:
            legacy_manifest = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {manifest_path}: {e}")
        return 1
    
    # Check if already v3
    if legacy_manifest.get("$schema") == "manifest-v3":
        print(f"Manifest is already v3 schema: {manifest_path}")
        return 0
    
    # Check if it's an unknown format that we shouldn't convert
    manifest_version = legacy_manifest.get("manifest_version")
    if not manifest_version and not any(key in legacy_manifest for key in ["blocks_generated", "meeting_date", "date"]):
        print(f"Warning: Unknown manifest format, skipping: {manifest_path}")
        return 0
    
    # Convert to v3
    v3_manifest = convert_to_v3(legacy_manifest, args.folder_path)
    
    # Output handling
    if args.dry_run:
        print(f"=== LEGACY MANIFEST ({manifest_path}) ===")
        print(json.dumps(legacy_manifest, indent=2))
        print(f"\n=== CONVERTED V3 MANIFEST ===")
        print(json.dumps(v3_manifest, indent=2))
        print(f"\n=== SUMMARY ===")
        print(f"Version: {manifest_version or 'unknown'} → v3")
        print(f"Meeting Type: {v3_manifest['meeting']['type']}")
        print(f"Participants: {len(v3_manifest['participants']['identified'])}")
        print(f"Quality Gate: {'PASS' if v3_manifest['quality_gate']['passed'] else 'FAIL'}")
        print(f"HITL Required: {'YES' if v3_manifest['hitl']['reason'] else 'NO'}")
    else:
        output_path = args.output or manifest_path
        
        # Backup original
        backup_path = output_path.with_suffix('.json.legacy')
        if not backup_path.exists():
            import shutil
            shutil.copy2(output_path, backup_path)
            print(f"Backed up original to: {backup_path}")
        
        # Write new manifest
        with open(output_path, 'w') as f:
            json.dump(v3_manifest, f, indent=2)
        
        print(f"Converted {output_path} to v3 schema")
        
        if v3_manifest['hitl']['reason']:
            print(f"⚠️  HITL required: {v3_manifest['hitl']['reason']}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())