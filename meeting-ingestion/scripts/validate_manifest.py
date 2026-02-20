#!/usr/bin/env python3
"""
Manifest v3 validation script
Validates meeting manifest.json files against the manifest-v3 JSON schema.
"""

import json
import sys
import os
from pathlib import Path
from jsonschema import validate, ValidationError, Draft202012Validator
import argparse
from datetime import datetime


def load_schema():
    """Load the manifest v3 JSON schema"""
    script_dir = Path(__file__).parent
    schema_path = script_dir / "../references/manifest-v3.schema.json"
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path) as f:
        return json.load(f)


def validate_manifest_file(manifest_path, schema):
    """Validate a single manifest file against the schema"""
    try:
        with open(manifest_path) as f:
            manifest_data = json.load(f)
        
        # Validate against schema
        Draft202012Validator(schema).validate(manifest_data)
        
        # Additional business logic validations
        errors = []
        
        # Check status history consistency
        current_status = manifest_data.get("status")
        status_history = manifest_data.get("status_history", [])
        
        if status_history and status_history[-1]["status"] != current_status:
            errors.append("Current status doesn't match latest status history entry")
        
        # Check timestamp progression
        timestamp_fields = ["created_at", "ingested_at", "identified_at", "gated_at", "processed_at", "archived_at"]
        timestamps = manifest_data.get("timestamps", {})
        
        prev_time = None
        for field in timestamp_fields:
            if timestamps.get(field):
                try:
                    current_time = datetime.fromisoformat(timestamps[field].replace('Z', '+00:00'))
                    if prev_time and current_time < prev_time:
                        errors.append(f"Timestamp {field} is before previous timestamp")
                    prev_time = current_time
                except ValueError:
                    errors.append(f"Invalid timestamp format for {field}")
        
        # Check block consistency
        blocks = manifest_data.get("blocks", {})
        if blocks:
            requested = set(blocks.get("requested", []))
            generated = set(blocks.get("generated", []))
            failed = set(blocks.get("failed", []))
            skipped = set(blocks.get("skipped", []))
            
            # No overlaps between generated, failed, skipped
            if generated & failed:
                errors.append("Blocks cannot be both generated and failed")
            if generated & skipped:
                errors.append("Blocks cannot be both generated and skipped")
            if failed & skipped:
                errors.append("Blocks cannot be both failed and skipped")
            
            # All non-generated blocks should be accounted for
            all_processed = generated | failed | skipped
            unaccounted = requested - all_processed
            if unaccounted:
                errors.append(f"Requested blocks not accounted for: {unaccounted}")
        
        return True, errors
        
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    except ValidationError as e:
        return False, [f"Schema validation failed: {e.message}"]
    except Exception as e:
        return False, [f"Validation error: {str(e)}"]


def main():
    parser = argparse.ArgumentParser(description="Validate meeting manifest files")
    parser.add_argument("manifest_path", nargs="?", help="Path to manifest.json file")
    parser.add_argument("--directory", "-d", help="Validate all manifest.json files in directory")
    parser.add_argument("--quiet", "-q", action="store_true", help="Only show errors")
    parser.add_argument("--create-example", action="store_true", help="Create an example manifest file")
    
    args = parser.parse_args()
    
    if args.create_example:
        create_example_manifest()
        return
    
    if not args.manifest_path and not args.directory:
        parser.error("Must specify either a manifest file or directory")
    
    try:
        schema = load_schema()
    except Exception as e:
        print(f"Error loading schema: {e}", file=sys.stderr)
        sys.exit(1)
    
    files_to_validate = []
    
    if args.directory:
        dir_path = Path(args.directory)
        files_to_validate = list(dir_path.rglob("manifest.json"))
    else:
        files_to_validate = [Path(args.manifest_path)]
    
    total_files = len(files_to_validate)
    valid_files = 0
    
    for manifest_path in files_to_validate:
        if not manifest_path.exists():
            print(f"File not found: {manifest_path}", file=sys.stderr)
            continue
        
        is_valid, errors = validate_manifest_file(manifest_path, schema)
        
        if is_valid and not errors:
            valid_files += 1
            if not args.quiet:
                print(f"✓ {manifest_path}")
        else:
            print(f"✗ {manifest_path}")
            for error in errors:
                print(f"  - {error}")
    
    if total_files > 1:
        print(f"\nValidated {valid_files}/{total_files} files successfully")
    
    if valid_files != total_files:
        sys.exit(1)


def create_example_manifest():
    """Create an example manifest file for testing"""
    example = {
        "$schema": "manifest-v3",
        "meeting_id": "2026-02-01_Example-Meeting",
        "status": "identified",
        "status_history": [
            {"status": "raw", "at": "2026-02-01T10:00:00Z"},
            {"status": "ingested", "at": "2026-02-01T10:01:00Z"},
            {"status": "identified", "at": "2026-02-01T10:02:00Z"}
        ],
        "source": {
            "type": "fathom",
            "original_filename": "example_meeting.txt",
            "ingested_at": "2026-02-01T10:01:00Z"
        },
        "meeting": {
            "date": "2026-02-01",
            "time_utc": "15:00:00",
            "duration_minutes": 45,
            "title": "Example Partnership Discussion",
            "type": "external",
            "summary": "Discussion about potential partnership opportunities and next steps for collaboration."
        },
        "participants": {
            "identified": [
                {"name": "V", "email": "<YOUR_EMAIL>", "crm_id": 1, "role": "host"},
                {"name": "John Doe", "email": "<YOUR_EMAIL>", "crm_id": 42, "role": "attendee"}
            ],
            "unidentified": [],
            "confidence": 0.95
        },
        "calendar_match": {
            "event_id": "example_event_123",
            "confidence": 0.9,
            "method": "timestamp+title"
        },
        "quality_gate": {
            "passed": True,
            "checks": {
                "has_transcript": True,
                "participants_identified": True,
                "meeting_type_determined": True,
                "no_hitl_pending": True
            },
            "score": 1.0
        },
        "blocks": {
            "policy": "external_standard",
            "requested": ["B00", "B01", "B03", "B08", "B26"],
            "generated": ["B00", "B01"],
            "failed": [],
            "skipped": ["B03", "B08", "B26"]
        },
        "hitl": {
            "queue_id": None,
            "reason": None,
            "resolved_at": None
        },
        "timestamps": {
            "created_at": "2026-02-01T10:00:00Z",
            "ingested_at": "2026-02-01T10:01:00Z",
            "identified_at": "2026-02-01T10:02:00Z",
            "gated_at": None,
            "processed_at": None,
            "archived_at": None
        }
    }
    
    with open("example_manifest.json", "w") as f:
        json.dump(example, f, indent=2)
    
    print("Created example_manifest.json")


if __name__ == "__main__":
    main()