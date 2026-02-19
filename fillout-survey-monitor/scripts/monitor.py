#!/usr/bin/env python3
"""
Fillout Survey Monitor

Watches for new survey submissions and triggers refresh workflows when
meaningful changes occur.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def check_submissions(form_id, account):
    """Fetch current submissions from Fillout API."""
    fillout_client = Path("./Skills/dynamic-survey-analyzer/scripts/fillout_client.py")
    
    if not fillout_client.exists():
        print(f"❌ fillout_client.py not found at {fillout_client}")
        sys.exit(1)
    
    cmd = [
        "python3",
        str(fillout_client),
        "--submissions", form_id,
        "--account", account
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Failed to fetch submissions: {result.stderr}")
        sys.exit(1)
    
    try:
        data = json.loads(result.stdout)
        return data.get("totalResponses", 0), data.get("responses", [])
    except json.JSONDecodeError:
        print(f"❌ Failed to parse response from fillout_client")
        sys.exit(1)


def read_meta(form_id):
    """Read existing meta.json if it exists."""
    meta_path = Path(f"./Datasets/survey-analyses/{form_id}/meta.json")
    
    if not meta_path.exists():
        return None
    
    with open(meta_path) as f:
        return json.load(f)


def count_eligible_responses(responses, screening_question, screening_exclude):
    """Count responses that pass screening criteria."""
    eligible = 0
    ineligible = 0
    
    for response in responses:
        questions = response.get("questions", [])
        attending = None
        
        for q in questions:
            if q.get("id") == screening_question:
                attending = q.get("value")
                break
        
        if attending == screening_exclude:
            ineligible += 1
        else:
            eligible += 1
    
    return eligible, ineligible


def trigger_refresh(form_id, account, screening_question, screening_exclude):
    """Run full refresh workflow."""
    analysis_dir = Path(f"./Datasets/survey-analyses/{form_id}")
    
    print(f"  → Updating data cache...")
    fillout_client = Path("./Skills/dynamic-survey-analyzer/scripts/fillout_client.py")
    data_file = analysis_dir / "data.json"
    
    cmd = [
        "python3",
        str(fillout_client),
        "--submissions", form_id,
        "--account", account
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  ❌ Failed to update data cache: {result.stderr}")
        return False
    
    # Save filtered data (exclude ineligible responses)
    try:
        data = json.loads(result.stdout)
        responses = data.get("responses", [])
        
        eligible_responses = [
            r for r in responses
            if any(
                q.get("id") == screening_question and q.get("value") != screening_exclude
                for q in r.get("questions", [])
            )
        ]
        
        # Update with eligible responses only
        data["responses"] = eligible_responses
        data["totalResponses"] = len(eligible_responses)
        
        with open(data_file, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"  ✓ Data cache updated ({len(eligible_responses)} eligible responses)")
    except (json.JSONDecodeError, IOError) as e:
        print(f"  ❌ Failed to save filtered data: {e}")
        return False
    
    # Trigger analysis regeneration
    print(f"  → Regenerating analysis...")
    # This is a placeholder - actual analysis happens via dynamic-survey-analyzer
    # For now, we'll update the analysis file with new counts
    analysis_file = analysis_dir / "analysis.md"
    
    if analysis_file.exists():
        # In a full implementation, this would call the analysis workflow
        # For now, just note that analysis needs regeneration
        print(f"  ⚠ Analysis file exists - regenerate via dynamic-survey-analyzer")
    
    # Regenerate dashboard
    print(f"  → Regenerating dashboard...")
    dashboard_script = Path("./Skills/dynamic-survey-analyzer/scripts/generate_dashboard.py")
    
    if dashboard_script.exists():
        cmd = ["python3", str(dashboard_script), form_id]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"  ✓ Dashboard updated")
        else:
            print(f"  ⚠ Dashboard generation failed: {result.stderr}")
    
    return True


def update_meta(form_id, total_submissions, eligible_submissions, ineligible_submissions):
    """Update meta.json with new counts."""
    meta_path = Path(f"./Datasets/survey-analyses/{form_id}/meta.json")
    
    if not meta_path.exists():
        print(f"  ⚠ meta.json does not exist, skipping update")
        return
    
    with open(meta_path) as f:
        meta = json.load(f)
    
    meta["total_submissions"] = total_submissions
    meta["eligible_submissions"] = eligible_submissions
    meta["ineligible_submissions"] = ineligible_submissions
    meta["last_updated"] = datetime.now(timezone.utc).isoformat()
    meta["metadata"]["refresh_count"] = meta["metadata"].get("refresh_count", 0) + 1
    
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    
    print(f"  ✓ Meta updated: total={total_submissions}, eligible={eligible_submissions}")


def send_notification(total_eligible, previous_eligible, insight):
    """Send SMS notification with survey update."""
    # Check if SMS is available via zo ask API
    max_chars = 400
    
    if previous_eligible is None:
        prev_text = "first run"
    else:
        prev_text = f"was {previous_eligible}"
    
    msg = f"📊 Survey update: {total_eligible} responses now ({prev_text}). Key change: {insight}"
    
    # Truncate if needed
    if len(msg) > max_chars:
        msg = msg[:max_chars-3] + "..."
    
    print(f"\n[NOTIFICATION] {msg}")
    
    # In a full implementation, this would use the Zo SMS API
    # For now, print the message
    print("  (SMS notification would be sent here)")


def main():
    parser = argparse.ArgumentParser(description="Monitor Fillout survey for changes")
    parser.add_argument("--form-id", required=True, help="Fillout form ID")
    parser.add_argument("--account", required=True, help="Fillout account name")
    parser.add_argument("--refresh-threshold", type=int, default=2,
                       help="Minimum new responses to trigger refresh (default: 2)")
    parser.add_argument("--screening-question", default="dGZw",
                       help="Question ID for screening (default: dGZw)")
    parser.add_argument("--screening-exclude", default="No",
                       help="Value that excludes response (default: 'No')")
    parser.add_argument("--check-only", action="store_true",
                       help="Check only, don't trigger refresh")
    parser.add_argument("--force-refresh", action="store_true",
                       help="Skip threshold check and force refresh")
    
    args = parser.parse_args()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}] Survey Monitor: {args.form_id}")
    
    # Step 1: Check for new submissions
    total_responses, responses = check_submissions(args.form_id, args.account)
    print(f"  Current total responses: {total_responses}")
    
    # Step 2: Count eligible responses
    eligible_count, ineligible_count = count_eligible_responses(
        responses, args.screening_question, args.screening_exclude
    )
    print(f"  Eligible responses: {eligible_count} (excluding {ineligible_count} non-attending)")
    
    # Step 3: Compare to previous
    meta = read_meta(args.form_id)
    
    if meta:
        previous_eligible = meta.get("eligible_submissions", 0)
        previous_total = meta.get("total_submissions", 0)
        print(f"  Previous eligible: {previous_eligible} (from meta.json)")
        
        net_new = eligible_count - previous_eligible
        print(f"  Net new responses: {net_new}")
    else:
        print(f"  ⚠ No existing meta.json found (first run?)")
        previous_eligible = None
        net_new = 0
    
    # Step 4: Determine if refresh is needed
    if args.force_refresh:
        print(f"\n  ✓ Force refresh requested, triggering workflow...")
        should_refresh = True
    elif args.check_only:
        print(f"\n  Check-only mode, skipping refresh")
        should_refresh = False
    elif previous_eligible is None:
        print(f"\n  First run, triggering refresh to establish baseline...")
        should_refresh = True
    elif net_new >= args.refresh_threshold:
        print(f"\n  ✓ Threshold met (≥{args.refresh_threshold}), triggering refresh...")
        should_refresh = True
    else:
        print(f"\n  → Threshold not met (need {args.refresh_threshold}, got {net_new})")
        print(f"  No refresh needed")
        should_refresh = False
    
    # Step 5: Refresh if needed
    if should_refresh and not args.check_only:
        success = trigger_refresh(
            args.form_id, args.account,
            args.screening_question, args.screening_exclude
        )
        
        if success:
            # Update meta
            update_meta(
                args.form_id,
                total_responses,
                eligible_count,
                ineligible_count
            )
            
            # Send notification if meaningful change
            if net_new >= args.refresh_threshold and not args.force_refresh:
                insight = f"{net_new} new attendee(s) joined"
                send_notification(eligible_count, previous_eligible, insight)
    
    print(f"\n[{timestamp}] ✓ Monitor complete\n")


if __name__ == "__main__":
    main()
