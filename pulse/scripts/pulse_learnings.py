#!/usr/bin/env python3
"""
Pulse Learnings: Capture and propagate learnings at build and system level.

Two tiers:
1. Build-local learnings  → N5/builds/<slug>/BUILD_LESSONS.json
2. System-wide learnings  → N5/learnings/SYSTEM_LEARNINGS.json

Usage:
  pulse_learnings.py add <slug> "learning text" [--system]
  pulse_learnings.py list <slug>
  pulse_learnings.py list-system
  pulse_learnings.py promote <slug> <index>  # Promote build learning to system
  pulse_learnings.py inject <slug>           # Inject relevant system learnings into build briefs
"""

import argparse
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from pulse_common import PATHS, WORKSPACE


def load_build_learnings(slug: str) -> dict:
    """Load build-specific learnings"""
    path = PATHS.BUILDS / slug / "BUILD_LESSONS.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"slug": slug, "learnings": []}


def save_build_learnings(slug: str, data: dict):
    """Save build-specific learnings"""
    path = PATHS.BUILDS / slug / "BUILD_LESSONS.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_system_learnings() -> dict:
    """Load system-wide learnings, applying defaults for missing v2 fields"""
    if PATHS.SYSTEM_LEARNINGS.exists():
        with open(PATHS.SYSTEM_LEARNINGS) as f:
            data = json.load(f)
        
        # Backward compatibility: fill missing v2 fields with defaults
        for learning in data.get("learnings", []):
            if "confidence" not in learning:
                learning["confidence"] = 0.7
            if "validated_count" not in learning:
                learning["validated_count"] = 0
            if "last_validated" not in learning:
                learning["last_validated"] = None
            if "decay_days" not in learning:
                learning["decay_days"] = 30
            if "expires_at" not in learning:
                learning["expires_at"] = None
            if "status" not in learning:
                learning["status"] = "active"
            if "disputed_by" not in learning:
                learning["disputed_by"] = None
            if "dispute_reason" not in learning:
                learning["dispute_reason"] = None
        
        return data
    return {"meta": {"description": "System-wide learnings", "version": "2.0"}, "learnings": []}


def save_system_learnings(data: dict):
    """Save system-wide learnings"""
    with open(PATHS.SYSTEM_LEARNINGS, "w") as f:
        json.dump(data, f, indent=2)


def add_learning(slug: str, text: str, source: str = "manual", system: bool = False, tags: list = None, confidence: float = None, decay_days: int = None, expires_at: str = None, force: bool = False):
    """Add a learning to build or system level with optional v2 confidence tracking"""
    
    # NEW: Check for contradictions first (Watts Principles)
    if not force:
        try:
            from N5.scripts.contradiction_detector import check_before_adding
            check = check_before_adding(text)
            if not check["can_add"]:
                print(f"⚠️ Potential contradiction with existing learning:")
                for c in check.get("contradictions", []):
                    print(f"  - {c['learning'][:70]}...")
                    print(f"    Confidence: {c['contradiction_confidence']}, Similarity: {c['similarity']:.2f}")
                print(f"\nReason: {check.get('reason', 'Unknown')}")
                print("\nUse --force to add anyway, or resolve contradiction first")
                return False
        except ImportError:
            print("[Contradiction check] Detector not available, skipping check")
        except Exception as e:
            print(f"[Contradiction check] Error: {e}, skipping")
    
    # NEW: Deduplication check
    if system:
        existing = load_system_learnings().get("learnings", [])
    else:
        existing = load_build_learnings(slug).get("learnings", [])
    
    # Check for exact or near-exact duplicates
    text_normalized = text.strip().lower()
    for ex in existing:
        ex_normalized = ex.get("text", "").strip().lower()
        if text_normalized == ex_normalized:
            print(f"[SKIP] Duplicate learning already exists: {text[:60]}...")
            return False
        # Also check for high similarity (>90% character overlap)
        if len(text_normalized) > 20 and len(ex_normalized) > 20:
            # Simple similarity: shared words ratio
            words_new = set(text_normalized.split())
            words_ex = set(ex_normalized.split())
            if words_new and words_ex:
                overlap = len(words_new & words_ex) / max(len(words_new), len(words_ex))
                if overlap > 0.9:
                    print(f"[SKIP] Very similar learning already exists ({overlap:.0%} overlap): {ex.get('text', '')[:60]}...")
                    return False
    
    learning = {
        "text": text,
        "source": source,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "tags": tags or []
    }
    
    # Add v2 fields if system-level learning
    if system:
        learning["origin_build"] = slug
        # v2 fields
        learning["confidence"] = confidence if confidence is not None else 0.7
        learning["validated_count"] = 0
        learning["last_validated"] = None
        learning["decay_days"] = decay_days if decay_days is not None else 30
        learning["expires_at"] = expires_at
        learning["status"] = "active"
        learning["disputed_by"] = None
        learning["dispute_reason"] = None
        
        data = load_system_learnings()
        data["learnings"].append(learning)
        save_system_learnings(data)
        print(f"[SYSTEM] Added learning: {text[:60]}... (confidence: {learning['confidence']})")
    else:
        data = load_build_learnings(slug)
        data["learnings"].append(learning)
        save_build_learnings(slug, data)
        print(f"[{slug}] Added learning: {text[:60]}...")


def list_learnings(slug: str) -> list:
    """List build learnings"""
    data = load_build_learnings(slug)
    return data.get("learnings", [])


def list_system_learnings() -> list:
    """List system learnings"""
    data = load_system_learnings()
    return data.get("learnings", [])


def promote_learning(slug: str, index: int):
    """Promote a build learning to system level"""
    build_data = load_build_learnings(slug)
    learnings = build_data.get("learnings", [])
    
    if index < 0 or index >= len(learnings):
        print(f"Invalid index {index}. Build has {len(learnings)} learnings.")
        return False
    
    learning = learnings[index].copy()
    learning["origin_build"] = slug
    learning["promoted_at"] = datetime.now(timezone.utc).isoformat()
    
    system_data = load_system_learnings()
    system_data["learnings"].append(learning)
    save_system_learnings(system_data)
    
    print(f"Promoted to system: {learning['text'][:60]}...")
    return True


def get_relevant_learnings(slug: str, tags: list = None) -> list:
    """Get system learnings relevant to a build (by tags or all)"""
    system = load_system_learnings()
    learnings = system.get("learnings", [])
    
    if not tags:
        return learnings
    
    return [l for l in learnings if any(t in l.get("tags", []) for t in tags)]


def inject_learnings_into_brief(brief_path: Path, learnings: list) -> str:
    """Inject relevant learnings into a Drop brief"""
    if not learnings:
        return None
    
    with open(brief_path) as f:
        content = f.read()
    
    # Check if already has learnings section
    if "## System Learnings" in content:
        return None  # Already injected
    
    learnings_section = "\n\n## System Learnings (Auto-Injected)\n\n"
    learnings_section += "Review these before starting:\n\n"
    for i, l in enumerate(learnings[:5]):  # Max 5
        learnings_section += f"- {l['text']}\n"
    
    # Insert before "## Requirements" or at end
    if "## Requirements" in content:
        content = content.replace("## Requirements", learnings_section + "## Requirements")
    else:
        content += learnings_section
    
    with open(brief_path, "w") as f:
        f.write(content)
    
    return brief_path


def inject_all_briefs(slug: str, tags: list = None):
    """Inject relevant system learnings into all Drop briefs for a build"""
    learnings = get_relevant_learnings(slug, tags)
    if not learnings:
        print("No relevant system learnings to inject.")
        return
    
    drops_dir = PATHS.BUILDS / slug / "drops"
    if not drops_dir.exists():
        print(f"No drops directory for {slug}")
        return
    
    injected = 0
    for brief_path in drops_dir.glob("*.md"):
        result = inject_learnings_into_brief(brief_path, learnings)
        if result:
            injected += 1
            print(f"Injected learnings into {brief_path.name}")
    
    print(f"Injected into {injected} briefs.")


def extract_learnings_from_deposit(slug: str, drop_id: str) -> list:
    """Extract learnings from a Drop's deposit"""
    deposit_path = PATHS.BUILDS / slug / "deposits" / f"{drop_id}.json"
    if not deposit_path.exists():
        return []
    
    try:
        with open(deposit_path) as f:
            deposit = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"Warning: Could not parse {deposit_path.name} - {e}")
        return []
    
    # Look for learnings field
    learnings_data = deposit.get("learnings", [])
    if not learnings_data:
        return []
    
    # Handle different formats:
    # 1. List of objects with "text" field: [{"text": "...", "tags": [...]}]
    # 2. List of strings: ["learning1", "learning2"]
    # 3. Single string: "single learning"
    result = []
    
    if isinstance(learnings_data, str):
        # Single string
        result.append(learnings_data)
    elif isinstance(learnings_data, list):
        for item in learnings_data:
            if isinstance(item, dict) and "text" in item:
                # Object with text field
                result.append(item["text"])
            elif isinstance(item, str):
                # Simple string
                result.append(item)
    
    return result


def harvest_build_learnings(slug: str, verbose: bool = False):
    """Harvest all learnings from completed deposits"""
    deposits_dir = PATHS.BUILDS / slug / "deposits"
    if not deposits_dir.exists():
        print(f"No deposits for {slug}")
        return
    
    harvested = 0
    processed_files = 0
    skipped_files = 0
    
    for deposit_path in deposits_dir.glob("*.json"):
        if "_filter" in deposit_path.name:
            if verbose:
                print(f"Skipping filter file: {deposit_path.name}")
            continue  # Skip filter results
        
        processed_files += 1
        drop_id = deposit_path.stem
        learnings = extract_learnings_from_deposit(slug, drop_id)
        
        if verbose:
            if learnings:
                print(f"Found {len(learnings)} learning(s) in {deposit_path.name}")
                for learning in learnings:
                    print(f"  - {learning[:80]}...")
            else:
                print(f"No learnings in {deposit_path.name}")
        
        for learning_text in learnings:
            add_learning(slug, learning_text, source=f"Drop:{drop_id}")
            harvested += 1
    
    if verbose:
        print(f"\nProcessed {processed_files} deposits, harvested {harvested} learnings from {slug}")
    else:
        print(f"Harvested {harvested} learnings from {slug}")


# ===== V2 Functions: Confidence, Validation, Status Tracking =====

def validate_learning(index: int, boost: float = 0.05) -> bool:
    """Validate a system learning, incrementing validated_count and boosting confidence
    
    Args:
        index: Index of learning in system learnings list
        boost: Amount to boost confidence by (default 0.05)
    
    Returns:
        True if validated successfully, False otherwise
    """
    data = load_system_learnings()
    learnings = data.get("learnings", [])
    
    if index < 0 or index >= len(learnings):
        print(f"Invalid index {index}. System has {len(learnings)} learnings.")
        return False
    
    learning = learnings[index]
    now = datetime.now(timezone.utc).isoformat()
    
    # Update fields
    learning["validated_count"] = learning.get("validated_count", 0) + 1
    learning["last_validated"] = now
    # Boost confidence, capped at 1.0
    current_confidence = learning.get("confidence", 0.7)
    learning["confidence"] = min(1.0, current_confidence + boost)
    # Ensure status is active
    learning["status"] = "active"
    
    save_system_learnings(data)
    print(f"Validated learning #{index}: {learning['text'][:60]}...")
    print(f"  Confidence: {current_confidence:.2f} → {learning['confidence']:.2f} (validated {learning['validated_count']} times)")
    return True


def dispute_learning(index: int, reason: str, source: str = None) -> bool:
    """Mark a system learning as disputed
    
    Args:
        index: Index of learning in system learnings list
        reason: Explanation of why this learning is disputed
        source: Reference to the source contradicting this learning
    
    Returns:
        True if disputed successfully, False otherwise
    """
    data = load_system_learnings()
    learnings = data.get("learnings", [])
    
    if index < 0 or index >= len(learnings):
        print(f"Invalid index {index}. System has {len(learnings)} learnings.")
        return False
    
    learning = learnings[index]
    
    # Set dispute fields
    learning["status"] = "disputed"
    learning["disputed_by"] = source
    learning["dispute_reason"] = reason
    
    save_system_learnings(data)
    print(f"Disputed learning #{index}: {learning['text'][:60]}...")
    print(f"  Reason: {reason}")
    if source:
        print(f"  Source: {source}")
    return True


def invalidate_learning(index: int) -> bool:
    """Mark a system learning as invalidated (confirmed false)
    
    Args:
        index: Index of learning in system learnings list
    
    Returns:
        True if invalidated successfully, False otherwise
    """
    data = load_system_learnings()
    learnings = data.get("learnings", [])
    
    if index < 0 or index >= len(learnings):
        print(f"Invalid index {index}. System has {len(learnings)} learnings.")
        return False
    
    learning = learnings[index]
    learning["status"] = "invalidated"
    learning["confidence"] = 0.0
    
    save_system_learnings(data)
    print(f"Invalidated learning #{index}: {learning['text'][:60]}...")
    return True


def expire_stale_learnings(verbose: bool = False) -> int:
    """Check all system learnings and mark stale ones as expired
    
    A learning is stale if:
    1. It has expires_at set and now > expires_at, OR
    2. It has no expires_at, has decay_days set, and:
       - If never validated: now > added_at + decay_days
       - If validated: now > last_validated + decay_days
    
    Args:
        verbose: If True, print details of each expired learning
    
    Returns:
        Number of learnings marked as expired
    """
    data = load_system_learnings()
    learnings = data.get("learnings", [])
    now = datetime.now(timezone.utc)
    expired_count = 0
    
    for i, learning in enumerate(learnings):
        # Skip if already not active
        if learning.get("status") in ("disputed", "invalidated", "expired"):
            continue
        
        # Check explicit expiration
        expires_at = learning.get("expires_at")
        if expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at)
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                if now > expires_dt:
                    learning["status"] = "expired"
                    expired_count += 1
                    if verbose:
                        print(f"Expired #{i} (expires_at): {learning['text'][:50]}...")
                    continue
            except (ValueError, TypeError):
                pass  # Invalid date format, skip
        
        # Check decay
        decay_days = learning.get("decay_days", 30)
        last_validated = learning.get("last_validated")
        added_at = learning.get("added_at")
        
        # Determine to reference date (last_validated or added_at)
        ref_date = None
        if last_validated:
            try:
                ref_date = datetime.fromisoformat(last_validated)
            except (ValueError, TypeError):
                pass
        elif added_at:
            try:
                ref_date = datetime.fromisoformat(added_at)
            except (ValueError, TypeError):
                pass
        
        # Add timezone if missing
        if ref_date and ref_date.tzinfo is None:
            ref_date = ref_date.replace(tzinfo=timezone.utc)
        
        # Check if decay period has passed
        if ref_date:
            expiry_date = ref_date + timedelta(days=decay_days)
            if now > expiry_date:
                learning["status"] = "expired"
                expired_count += 1
                if verbose:
                    print(f"Expired #{i} (decay {decay_days}d): {learning['text'][:50]}...")
    
    if expired_count > 0:
        save_system_learnings(data)
        print(f"Marked {expired_count} learnings as expired.")
    elif verbose:
        print("No learnings expired.")
    
    return expired_count


def main():
    parser = argparse.ArgumentParser(description="Pulse Learnings Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # add
    add_parser = subparsers.add_parser("add", help="Add a learning")
    add_parser.add_argument("slug", help="Build slug")
    add_parser.add_argument("text", help="Learning text")
    add_parser.add_argument("--system", action="store_true", help="Add to system level")
    add_parser.add_argument("--tags", nargs="*", help="Tags for categorization")
    add_parser.add_argument("--confidence", type=float, help="Initial confidence (0.0-1.0) for system learnings")
    add_parser.add_argument("--decay-days", type=int, help="Days until confidence starts decaying")
    add_parser.add_argument("--expires-at", help="Hard expiration date (ISO8601)")
    add_parser.add_argument("--force", action="store_true", help="Skip contradiction check")
    
    # list
    list_parser = subparsers.add_parser("list", help="List build learnings")
    list_parser.add_argument("slug", help="Build slug")
    
    # list-system
    subparsers.add_parser("list-system", help="List system learnings")
    
    # promote
    promote_parser = subparsers.add_parser("promote", help="Promote build learning to system")
    promote_parser.add_argument("slug", help="Build slug")
    promote_parser.add_argument("index", type=int, help="Learning index")
    
    # inject
    inject_parser = subparsers.add_parser("inject", help="Inject system learnings into briefs")
    inject_parser.add_argument("slug", help="Build slug")
    inject_parser.add_argument("--tags", nargs="*", help="Filter by tags")
    
    # harvest
    harvest_parser = subparsers.add_parser("harvest", help="Harvest learnings from deposits")
    harvest_parser.add_argument("slug", help="Build slug")
    harvest_parser.add_argument("--verbose", action="store_true", help="Show detailed processing info")
    
    # validate (v2)
    validate_parser = subparsers.add_parser("validate", help="Validate a system learning")
    validate_parser.add_argument("index", type=int, help="Learning index")
    validate_parser.add_argument("--boost", type=float, default=0.05, help="Confidence boost amount (default 0.05)")
    
    # dispute (v2)
    dispute_parser = subparsers.add_parser("dispute", help="Dispute a system learning")
    dispute_parser.add_argument("index", type=int, help="Learning index")
    dispute_parser.add_argument("reason", help="Reason for dispute")
    dispute_parser.add_argument("--source", help="Source contradicting this learning")
    
    # invalidate (v2)
    invalidate_parser = subparsers.add_parser("invalidate", help="Invalidate a system learning")
    invalidate_parser.add_argument("index", type=int, help="Learning index")
    
    # expire-stale (v2)
    expire_parser = subparsers.add_parser("expire-stale", help="Mark stale learnings as expired")
    expire_parser.add_argument("--verbose", action="store_true", help="Show details of expired learnings")
    
    args = parser.parse_args()
    
    if args.command == "add":
        add_learning(args.slug, args.text, system=args.system, tags=args.tags, 
                    confidence=args.confidence, decay_days=args.decay_days, expires_at=args.expires_at, force=args.force)
    
    elif args.command == "list":
        learnings = list_learnings(args.slug)
        if not learnings:
            print(f"No learnings for {args.slug}")
        else:
            print(f"\n{args.slug} Learnings ({len(learnings)}):\n")
            for i, l in enumerate(learnings):
                print(f"  [{i}] {l['text'][:80]}")
                print(f"      Source: {l.get('source', 'unknown')} | {l.get('added_at', '')[:10]}")
    
    elif args.command == "list-system":
        learnings = list_system_learnings()
        if not learnings:
            print("No system learnings")
        else:
            print(f"\nSystem Learnings ({len(learnings)}):\n")
            for i, l in enumerate(learnings):
                status = l.get('status', 'active')
                confidence = l.get('confidence', 0.7)
                print(f"  [{i}] {l['text'][:80]}")
                print(f"      Status: {status} | Confidence: {confidence:.2f} | Origin: {l.get('origin_build', 'manual')} | Tags: {l.get('tags', [])}")
    
    elif args.command == "promote":
        promote_learning(args.slug, args.index)
    
    elif args.command == "inject":
        inject_all_briefs(args.slug, args.tags)
    
    elif args.command == "harvest":
        harvest_build_learnings(args.slug, verbose=args.verbose)
    
    elif args.command == "validate":
        validate_learning(args.index, boost=args.boost)
    
    elif args.command == "dispute":
        dispute_learning(args.index, args.reason, args.source)
    
    elif args.command == "invalidate":
        invalidate_learning(args.index)
    
    elif args.command == "expire-stale":
        expire_stale_learnings(verbose=args.verbose)


if __name__ == "__main__":
    main()
