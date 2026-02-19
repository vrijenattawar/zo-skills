#!/usr/bin/env python3
"""Drop close CLI — wrapper around N5/lib/close for Pulse workers."""

import argparse
import sys
from pathlib import Path

# Add N5 to path
sys.path.insert(0, '/home/workspace')

from N5.lib.close import guards, core

def main():
    parser = argparse.ArgumentParser(
        description='Close Pulse Drop worker threads',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This writes a structured deposit for orchestrator review.
Does NOT commit - orchestrator handles commits.

Example:
  %(prog)s --convo-id con_XXXXX
        """
    )
    parser.add_argument('--convo-id', required=True, help='Conversation ID')
    parser.add_argument('--force', action='store_true', help='Bypass guards')
    parser.add_argument('--status', default='complete',
                       choices=['complete', 'partial', 'failed', 'blocked'],
                       help='Override status')
    
    args = parser.parse_args()
    
    # Load session state
    state = guards.load_session_state(args.convo_id)
    
    # FAIL-SAFE: Check context (unless --force)
    if not args.force:
        valid, reason = guards.validate_drop_context(state)
        if not valid:
            guards.warn_wrong_skill(
                called='drop-close',
                suggested='thread-close',
                reason=reason
            )
            return 1
    
    # Extract drop context
    drop_id = state.get('drop_id') or state.get('worker_id')
    build_slug = state.get('build_slug')
    
    if not drop_id or not build_slug:
        print("Error: Missing drop_id or build_slug in SESSION_STATE", file=sys.stderr)
        print("Ensure SESSION_STATE.md has frontmatter with drop_id and build_slug", file=sys.stderr)
        return 1
    
    # Run drop close
    return core.run_drop_close(
        convo_id=args.convo_id,
        drop_id=drop_id,
        build_slug=build_slug
    )

if __name__ == '__main__':
    sys.exit(main())