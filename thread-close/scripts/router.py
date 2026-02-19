#!/usr/bin/env python3
"""Smart router for close operations — auto-detects context and routes to correct skill."""

import argparse
import os
import sys
from pathlib import Path

# Add N5 to path
sys.path.insert(0, '/home/workspace')

from N5.lib.close import guards

def get_current_convo_id() -> str:
    """Try to detect current conversation ID from environment."""
    # Check common env vars
    for var in ['CONVO_ID', 'ZO_CONVERSATION_ID', 'CONVERSATION_ID']:
        if os.environ.get(var):
            return os.environ[var]
    return None

def main():
    parser = argparse.ArgumentParser(
        description='Auto-routing close — detects context and calls correct skill',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Routes to:
  • thread-close — Normal interactive threads
  • drop-close   — Pulse Drop workers  
  • build-close  — Post-build synthesis (needs --slug)

Examples:
  %(prog)s --convo-id con_XXX           # Auto-detect and route
  %(prog)s --convo-id con_XXX --dry-run # Preview what would happen
  %(prog)s --slug my-build              # Force build-close mode
        """
    )
    parser.add_argument('--convo-id', help='Conversation ID (auto-detected if not provided)')
    parser.add_argument('--slug', help='Build slug (forces build-close mode)')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--tier', type=int, choices=[1, 2, 3], help='Force tier (thread-close only)')
    parser.add_argument('--force', action='store_true', help='Bypass guards')
    
    args = parser.parse_args()
    
    # If --slug provided, go directly to build-close
    if args.slug:
        print(f"🏗️  Build close mode (--slug provided)")
        cmd = f"python3 ./Skills/build-close/scripts/close.py --slug {args.slug}"
        if args.dry_run:
            cmd += " --dry-run"
        if args.force:
            cmd += " --force"
        print(f"→ {cmd}\n")
        return os.system(cmd) >> 8
    
    # Need convo_id for thread/drop routing
    convo_id = args.convo_id or get_current_convo_id()
    if not convo_id:
        print("ERROR: --convo-id required (could not auto-detect)")
        print("Tip: Pass the conversation ID, or use --slug for build-close")
        return 1
    
    # Load state and detect context
    state = guards.load_session_state(convo_id)
    context = guards.detect_context(state)
    
    print(f"📍 Detected context: {context}")
    print(f"   convo_id: {convo_id}")
    if state.get('drop_id'):
        print(f"   drop_id: {state['drop_id']}")
    if state.get('build_slug'):
        print(f"   build_slug: {state['build_slug']}")
    print()
    
    # Route to appropriate skill
    if context == "drop":
        print("🔹 Routing to drop-close...")
        cmd = f"python3 ./Skills/drop-close/scripts/close.py --convo-id {convo_id}"
        if args.force:
            cmd += " --force"
            
    elif context == "build":
        slug = state.get('build_slug')
        if not slug:
            print("ERROR: Build context detected but no build_slug in SESSION_STATE")
            print("Use --slug to specify the build explicitly")
            return 1
        print(f"🏗️  Routing to build-close (slug: {slug})...")
        cmd = f"python3 ./Skills/build-close/scripts/close.py --slug {slug}"
        if args.dry_run:
            cmd += " --dry-run"
        if args.force:
            cmd += " --force"
            
    else:  # thread
        print("💬 Routing to thread-close...")
        cmd = f"python3 ./Skills/thread-close/scripts/close.py --convo-id {convo_id}"
        if args.tier:
            cmd += f" --tier {args.tier}"
        if args.dry_run:
            cmd += " --dry-run"
        if args.force:
            cmd += " --force"
    
    print(f"→ {cmd}\n")
    return os.system(cmd) >> 8

if __name__ == '__main__':
    sys.exit(main())
