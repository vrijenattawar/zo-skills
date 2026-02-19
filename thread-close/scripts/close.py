#!/usr/bin/env python3
"""Thread close CLI — wrapper around N5/lib/close with fail-safes."""

import argparse
import sys
from pathlib import Path
import json

# Add N5 to path
sys.path.insert(0, '/home/workspace')

from N5.lib.close import guards, core

def main():
    parser = argparse.ArgumentParser(
        description='Close interactive conversation threads',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --convo-id con_XXXXX
  %(prog)s --convo-id con_XXXXX --tier 3
  %(prog)s --convo-id con_XXXXX --dry-run
        """
    )
    parser.add_argument('--convo-id', required=True, help='Conversation ID')
    parser.add_argument('--tier', type=int, choices=[1, 2, 3], help='Force tier')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--force', action='store_true', help='Bypass guards')
    parser.add_argument('--skip-positions', action='store_true', help='Skip position extraction')
    
    args = parser.parse_args()
    
    # Load session state
    state = guards.load_session_state(args.convo_id)
    
    # FAIL-SAFE: Check context (unless --force)
    if not args.force:
        valid, reason = guards.validate_thread_context(state)
        if not valid:
            suggested = 'drop-close' if 'drop' in reason.lower() else 'build-close'
            guards.warn_wrong_skill(
                called='thread-close',
                suggested=suggested,
                reason=reason
            )
            return 1
    
    # Gather thread context (includes task_info if action conversation)
    context = core.gather_thread_context(args.convo_id)
    
    # Add is_action_conversation flag at top level for LLM
    if 'task_info' in context:
        context['is_action_conversation'] = True
    
    # Dry run preview
    if args.dry_run:
        print(f"[DRY RUN] Thread Close for {args.convo_id}")
        print(f"  Tier: {context.get('tier', 1)}")
        print(f"  Artifacts: {context.get('artifact_count', 0)}")
        if 'task_info' in context:
            print(f"  Task ID: {context['task_info'].get('task_id')}")
        return 0
    
    # Output context as JSON for LLM to process
    print(json.dumps(context, indent=2, default=core.json_serial))
    return 0

if __name__ == '__main__':
    sys.exit(main())
