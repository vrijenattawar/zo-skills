#!/usr/bin/env python3
"""
HITL (Human-In-The-Loop) Queue Management CLI

Manages the meeting processing HITL queue for items requiring V's attention.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid

QUEUE_PATH = Path("./scripts/review/meetings/hitl-queue.jsonl")

def ensure_queue_dir():
    """Ensure the queue directory exists."""
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)

def load_queue() -> List[Dict]:
    """Load all items from the queue."""
    if not QUEUE_PATH.exists():
        return []
    
    items = []
    with open(QUEUE_PATH, 'r') as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items

def save_item(item: Dict):
    """Append a new item to the queue."""
    ensure_queue_dir()
    with open(QUEUE_PATH, 'a') as f:
        f.write(json.dumps(item) + '\n')

def update_queue(items: List[Dict]):
    """Rewrite the entire queue with updated items."""
    ensure_queue_dir()
    with open(QUEUE_PATH, 'w') as f:
        for item in items:
            f.write(json.dumps(item) + '\n')

def generate_hitl_id() -> str:
    """Generate a unique HITL ID."""
    timestamp = datetime.now().strftime("%Y%m%d")
    counter = len([item for item in load_queue() if item['id'].startswith(f"HITL-{timestamp}")]) + 1
    return f"HITL-{timestamp}-{counter:03d}"

def add_hitl_item(meeting_id: str, reason: str, context: Dict) -> str:
    """Add a new HITL item to the queue."""
    item = {
        "id": generate_hitl_id(),
        "meeting_id": meeting_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "context": context,
        "status": "pending",
        "resolved_by": None,
        "resolved_at": None,
        "resolution": None
    }
    
    save_item(item)
    return item["id"]

def resolve_item(hitl_id: str, action: str, parameters: Optional[Dict] = None, resolved_by: str = "manual"):
    """Mark an item as resolved."""
    items = load_queue()
    for item in items:
        if item["id"] == hitl_id:
            item["status"] = "resolved"
            item["resolved_by"] = resolved_by
            item["resolved_at"] = datetime.now(timezone.utc).isoformat()
            item["resolution"] = {
                "action": action,
                "parameters": parameters or {},
                "raw_response": f"Manual resolution: {action}"
            }
            break
    else:
        raise ValueError(f"HITL item {hitl_id} not found")
    
    update_queue(items)

def dismiss_item(hitl_id: str, reason: Optional[str] = None):
    """Mark an item as dismissed."""
    items = load_queue()
    for item in items:
        if item["id"] == hitl_id:
            item["status"] = "dismissed"
            item["resolved_by"] = "manual"
            item["resolved_at"] = datetime.now(timezone.utc).isoformat()
            item["resolution"] = {
                "action": "dismissed",
                "parameters": {"reason": reason or "No reason provided"},
                "raw_response": f"Dismissed: {reason or 'No reason provided'}"
            }
            break
    else:
        raise ValueError(f"HITL item {hitl_id} not found")
    
    update_queue(items)

def get_queue_stats() -> Dict:
    """Get queue statistics."""
    items = load_queue()
    
    stats = {
        "total": len(items),
        "pending": len([i for i in items if i["status"] == "pending"]),
        "resolved": len([i for i in items if i["status"] == "resolved"]), 
        "dismissed": len([i for i in items if i["status"] == "dismissed"]),
        "by_reason": {}
    }
    
    for item in items:
        reason = item["reason"]
        if reason not in stats["by_reason"]:
            stats["by_reason"][reason] = {"total": 0, "pending": 0, "resolved": 0, "dismissed": 0}
        
        stats["by_reason"][reason]["total"] += 1
        stats["by_reason"][reason][item["status"]] += 1
    
    return stats

def process_sms_response(hitl_id: str, sms_text: str) -> Dict:
    """Parse and process an SMS response."""
    # Simple parsing logic - can be enhanced
    text = sms_text.strip()
    
    # Parse common response patterns
    if text.lower().startswith("speaker"):
        # "Speaker 2 = John Smith"
        if "=" in text:
            speaker, name = text.split("=", 1)
            speaker = speaker.strip().replace("Speaker ", "")
            return {
                "action": "identify_speaker",
                "parameters": {"speaker_id": speaker, "name": name.strip()},
                "raw_response": text
            }
    elif text.lower().startswith("topic:"):
        # "Topic: Project Planning"
        topic = text.split(":", 1)[1].strip()
        return {
            "action": "set_topic",
            "parameters": {"topic": topic},
            "raw_response": text
        }
    elif text.lower() in ["skip unknown speakers", "auto-detect topic", "accept quality", "keep both", "keep content", "retry processing"]:
        return {
            "action": text.lower().replace(" ", "_"),
            "parameters": {},
            "raw_response": text
        }
    
    # Default: store as-is for manual review
    return {
        "action": "manual_review",
        "parameters": {"response": text},
        "raw_response": text
    }

def cleanup_resolved(days: int = 30):
    """Remove resolved/dismissed items older than specified days."""
    from datetime import timedelta
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items = load_queue()
    
    filtered_items = []
    removed_count = 0
    
    for item in items:
        if item["status"] in ["resolved", "dismissed"] and item["resolved_at"]:
            resolved_dt = datetime.fromisoformat(item["resolved_at"].replace('Z', '+00:00'))
            if resolved_dt < cutoff:
                removed_count += 1
                continue
        
        filtered_items.append(item)
    
    update_queue(filtered_items)
    return removed_count

# CLI Commands
def cmd_list(args):
    """List HITL items."""
    items = load_queue()
    
    if args.status:
        items = [i for i in items if i["status"] == args.status]
    
    if not items:
        print("No items found.")
        return
    
    print(f"{'ID':<20} {'Meeting ID':<25} {'Reason':<20} {'Status':<10} {'Created':<20}")
    print("-" * 100)
    
    for item in items:
        created = item["created_at"][:16].replace('T', ' ')  # Truncate timestamp
        print(f"{item['id']:<20} {item['meeting_id']:<25} {item['reason']:<20} {item['status']:<10} {created:<20}")

def cmd_show(args):
    """Show specific HITL item."""
    items = load_queue()
    item = next((i for i in items if i["id"] == args.hitl_id), None)
    
    if not item:
        print(f"HITL item {args.hitl_id} not found.")
        sys.exit(1)
    
    print(json.dumps(item, indent=2))

def cmd_resolve(args):
    """Resolve HITL item."""
    try:
        params = json.loads(args.params) if args.params else None
        resolve_item(args.hitl_id, args.action, params)
        print(f"Resolved {args.hitl_id} with action: {args.action}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

def cmd_dismiss(args):
    """Dismiss HITL item."""
    try:
        dismiss_item(args.hitl_id, args.reason)
        print(f"Dismissed {args.hitl_id}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

def cmd_stats(args):
    """Show queue statistics."""
    stats = get_queue_stats()
    
    print(f"Total items: {stats['total']}")
    print(f"Pending: {stats['pending']}")
    print(f"Resolved: {stats['resolved']}")
    print(f"Dismissed: {stats['dismissed']}")
    
    if stats['by_reason']:
        print("\nBy reason:")
        for reason, counts in stats['by_reason'].items():
            print(f"  {reason}: {counts['pending']} pending, {counts['resolved']} resolved, {counts['dismissed']} dismissed")

def cmd_reasons(args):
    """Show reason breakdown."""
    stats = get_queue_stats()
    
    if not stats['by_reason']:
        print("No items in queue.")
        return
    
    print(f"{'Reason':<30} {'Total':<6} {'Pending':<8} {'Resolved':<9} {'Dismissed':<9}")
    print("-" * 70)
    
    for reason, counts in stats['by_reason'].items():
        print(f"{reason:<30} {counts['total']:<6} {counts['pending']:<8} {counts['resolved']:<9} {counts['dismissed']:<9}")

def cmd_cleanup(args):
    """Clean up old resolved items."""
    removed = cleanup_resolved(args.days)
    print(f"Removed {removed} items older than {args.days} days")

def cmd_add_test(args):
    """Add test HITL item."""
    test_contexts = {
        "unidentified_participant": {
            "transcript_excerpt": "So as I was saying, the project needs more focus...",
            "known_participants": ["V"],
            "unknown_speakers": ["Speaker 2"],
            "confidence_scores": {"Speaker 2": 0.3}
        },
        "unclear_meeting_topic": {
            "transcript_excerpt": "Let's discuss the next steps and plan ahead...",
            "extracted_topics": ["Planning", "Discussion", "Review"],
            "confidence": 0.4
        },
        "low_transcript_quality": {
            "quality_score": 0.3,
            "issues": ["Poor audio quality", "Multiple speakers talking"],
            "transcript_excerpt": "[inaudible] ... can you hear me? ... [crosstalk]",
            "suggested_action": "manual_review"
        }
    }
    
    context = test_contexts.get(args.reason, {"note": "Test item"})
    hitl_id = add_hitl_item(args.meeting_id, args.reason, context)
    print(f"Added test item: {hitl_id}")

def cmd_test_sms(args):
    """Test SMS response parsing."""
    resolution = process_sms_response(args.hitl_id, args.response)
    print("Parsed response:")
    print(json.dumps(resolution, indent=2))
    
    # Actually resolve the item
    try:
        items = load_queue()
        for item in items:
            if item["id"] == args.hitl_id:
                item["status"] = "resolved"
                item["resolved_by"] = "sms"
                item["resolved_at"] = datetime.now(timezone.utc).isoformat()
                item["resolution"] = resolution
                break
        else:
            print(f"Warning: HITL item {args.hitl_id} not found for actual resolution")
            return
        
        update_queue(items)
        print(f"Item {args.hitl_id} marked as resolved")
        
    except Exception as e:
        print(f"Error updating item: {e}")

def main():
    parser = argparse.ArgumentParser(description="HITL Queue Management CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List HITL items')
    list_parser.add_argument('--status', choices=['pending', 'resolved', 'dismissed'], help='Filter by status')
    list_parser.set_defaults(func=cmd_list)
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Show specific item')
    show_parser.add_argument('hitl_id', help='HITL item ID')
    show_parser.set_defaults(func=cmd_show)
    
    # Resolve command
    resolve_parser = subparsers.add_parser('resolve', help='Resolve item')
    resolve_parser.add_argument('hitl_id', help='HITL item ID')
    resolve_parser.add_argument('--action', required=True, help='Resolution action')
    resolve_parser.add_argument('--params', help='JSON parameters for action')
    resolve_parser.set_defaults(func=cmd_resolve)
    
    # Dismiss command
    dismiss_parser = subparsers.add_parser('dismiss', help='Dismiss item')
    dismiss_parser.add_argument('hitl_id', help='HITL item ID')
    dismiss_parser.add_argument('--reason', help='Dismissal reason')
    dismiss_parser.set_defaults(func=cmd_dismiss)
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show queue statistics')
    stats_parser.set_defaults(func=cmd_stats)
    
    # Reasons command  
    reasons_parser = subparsers.add_parser('reasons', help='Show reason breakdown')
    reasons_parser.set_defaults(func=cmd_reasons)
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old items')
    cleanup_parser.add_argument('--days', type=int, default=30, help='Remove items older than N days')
    cleanup_parser.set_defaults(func=cmd_cleanup)
    
    # Test commands
    add_test_parser = subparsers.add_parser('add-test', help='Add test item')
    add_test_parser.add_argument('--reason', required=True, help='Test reason')
    add_test_parser.add_argument('--meeting-id', required=True, help='Test meeting ID')
    add_test_parser.set_defaults(func=cmd_add_test)
    
    test_sms_parser = subparsers.add_parser('test-sms', help='Test SMS response')
    test_sms_parser.add_argument('--hitl-id', required=True, help='HITL item ID')
    test_sms_parser.add_argument('--response', required=True, help='SMS response text')
    test_sms_parser.set_defaults(func=cmd_test_sms)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)

if __name__ == "__main__":
    main()