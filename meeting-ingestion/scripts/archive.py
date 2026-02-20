#!/usr/bin/env python3
"""
Meeting Ingestion - Archive Script

Moves completed meetings from Inbox to weekly folders.

Usage:
    python3 archive.py [--dry-run] [--execute]
"""

import json
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

INBOX = Path("./Personal/Meetings/Inbox")
MEETINGS = Path("./Personal/Meetings")


def get_week_folder(date_str: str) -> str:
    """Get Week-of-YYYY-MM-DD folder name (Monday of that week)."""
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        monday = date - timedelta(days=date.weekday())
        return f"Week-of-{monday.strftime('%Y-%m-%d')}"
    except:
        return "Week-of-Unknown"


def clean_folder_name(name: str) -> str:
    """Clean a meeting folder name for archival."""
    for suffix in ["_[P]", "_[M]", "_[B]", "_[C]"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    
    name = name.replace("_", "-")
    name = "-".join(part for part in name.split("-") if part)
    
    return name


def find_complete_meetings() -> list[dict]:
    """Find all meetings with status=complete in Inbox."""
    complete = []
    
    if not INBOX.exists():
        return complete
    
    for folder in INBOX.iterdir():
        if not folder.is_dir() or folder.name.startswith((".", "_")):
            continue
        
        manifest_path = folder / "manifest.json"
        if not manifest_path.exists():
            continue
        
        try:
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("status") == "complete":
                complete.append({
                    "path": folder,
                    "name": folder.name,
                    "date": manifest.get("date", "unknown"),
                    "manifest": manifest
                })
        except Exception as e:
            logger.warning(f"Could not read manifest for {folder.name}: {e}")
    
    return complete


def archive_meeting(meeting: dict, dry_run: bool = False) -> dict:
    """Archive a single meeting to its weekly folder."""
    folder = meeting["path"]
    date_str = meeting["date"]
    
    week_name = get_week_folder(date_str)
    week_dir = MEETINGS / week_name
    
    clean_name = clean_folder_name(folder.name)
    target_path = week_dir / clean_name
    
    result = {
        "from": str(folder),
        "to": str(target_path),
        "week": week_name
    }
    
    if dry_run:
        result["dry_run"] = True
        logger.info(f"  Would move: {folder.name}")
        logger.info(f"    → {week_name}/{clean_name}")
        return result
    
    week_dir.mkdir(parents=True, exist_ok=True)
    
    if target_path.exists():
        logger.info(f"  Target exists, merging: {target_path.name}")
        merged = 0
        for item in folder.iterdir():
            dest = target_path / item.name
            if not dest.exists():
                if item.is_file():
                    shutil.copy2(str(item), str(dest))
                else:
                    shutil.copytree(str(item), str(dest))
                merged += 1
            elif item.is_file() and dest.is_file():
                if item.stat().st_size > dest.stat().st_size:
                    shutil.copy2(str(item), str(dest))
        
        shutil.rmtree(folder)
        result["merged"] = True
        result["merged_count"] = merged
        logger.info(f"  Merged {merged} items, removed source")
    else:
        shutil.move(str(folder), str(target_path))
        logger.info(f"  Moved to: {target_path}")
    
    manifest_path = target_path / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            manifest["status"] = "archived"
            manifest["archived_at"] = datetime.utcnow().isoformat() + "Z"
            manifest_path.write_text(json.dumps(manifest, indent=2))
        except:
            pass
    
    result["success"] = True
    return result


def archive_all(dry_run: bool = True) -> dict:
    """Archive all complete meetings."""
    print(f"\n{'='*60}")
    print(f"MEETING ARCHIVAL {'(DRY RUN)' if dry_run else '(EXECUTING)'}")
    print(f"{'='*60}\n")
    
    complete = find_complete_meetings()
    
    print(f"Found {len(complete)} complete meetings in Inbox\n")
    
    if not complete:
        return {"archived": 0, "results": []}
    
    by_week = defaultdict(list)
    for meeting in complete:
        week = get_week_folder(meeting["date"])
        by_week[week].append(meeting)
    
    results = []
    
    for week in sorted(by_week.keys()):
        meetings = by_week[week]
        print(f"--- {week} ({len(meetings)} meetings) ---")
        
        for meeting in meetings:
            result = archive_meeting(meeting, dry_run=dry_run)
            results.append(result)
        
        print()
    
    succeeded = len([r for r in results if r.get("success") or r.get("dry_run")])
    failed = len([r for r in results if not r.get("success") and not r.get("dry_run")])
    
    print(f"{'='*60}")
    print(f"SUMMARY:")
    print(f"  Archived: {succeeded}")
    print(f"  Failed:   {failed}")
    print(f"{'='*60}\n")
    
    return {
        "archived": succeeded,
        "failed": failed,
        "results": results
    }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Archive completed meetings")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="Preview without executing (default)")
    parser.add_argument("--execute", action="store_true",
                       help="Actually perform archival")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    results = archive_all(dry_run=dry_run)
    
    if args.json:
        print(json.dumps(results, indent=2))
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
