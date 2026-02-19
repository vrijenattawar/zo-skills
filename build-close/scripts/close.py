#!/usr/bin/env python3
"""Build close CLI — post-build synthesis for Pulse builds."""

import argparse
import sys
from pathlib import Path

# Add N5 to path
sys.path.insert(0, '/home/workspace')

from N5.lib.close import guards, core

def main():
    parser = argparse.ArgumentParser(
        description='Post-build synthesis for Pulse builds',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Aggregates all deposits and generates build-level synthesis.
Run after pulse finalize completes.

Example:
  %(prog)s --slug my-build
  %(prog)s --slug my-build --dry-run
        """
    )
    parser.add_argument('--slug', required=True, help='Build slug')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--force', action='store_true', help='Bypass guards')
    parser.add_argument('--skip-positions', action='store_true', 
                       help='Skip position extraction')
    
    args = parser.parse_args()
    
    # FAIL-SAFE: Check build context (unless --force)
    if not args.force:
        valid, reason = guards.validate_build_context(args.slug)
        if not valid:
            # Determine suggestion
            if 'not found' in reason.lower():
                suggested = 'thread-close (build does not exist)'
            elif 'not finished' in reason.lower():
                suggested = 'wait for build to complete, or use --force'
            else:
                suggested = 'check build status'
            
            guards.warn_wrong_skill(
                called='build-close',
                suggested=suggested,
                reason=reason
            )
            return 1
    
    # Run build close
    return core.run_build_close(
        slug=args.slug,
        dry_run=args.dry_run
    )

if __name__ == '__main__':
    sys.exit(main())