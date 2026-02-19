#!/usr/bin/env python3
"""
Zo Substrate — Unified CLI for Zo-to-Zo skill exchange.

A generalized system for bidirectional skill/content synchronization
between any two Zo Computer instances, using a shared GitHub repo as substrate.

Usage:
    substrate.py setup check                    # Verify prerequisites
    substrate.py setup init --identity va ...   # Create config + optional repo
    substrate.py push [--skills x,y] [--dry-run]  # Push skills to substrate
    substrate.py pull [--skills x,y] [--dry-run]  # Pull skills from substrate
    substrate.py status                         # Show sync status
    substrate.py bundle create <skill>          # Create a skill bundle
    substrate.py bundle validate <path>         # Validate a bundle
    substrate.py bundle list                    # List discoverable skills
    substrate.py context refresh                # Refresh local context snapshot
    substrate.py context query [--what ...]     # Query context
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


def cmd_push(args):
    from push import push
    from config import load_config
    cfg = load_config()
    skills = [s.strip() for s in args.skills.split(",")] if args.skills else None
    result = push(cfg, filter_skills=skills, dry_run=args.dry_run)
    return 0 if result.get("success") else 1


def cmd_pull(args):
    from pull import pull
    from config import load_config
    cfg = load_config()
    skills = [s.strip() for s in args.skills.split(",")] if args.skills else None
    result = pull(cfg, filter_skills=skills, dry_run=args.dry_run, verbose=args.verbose)
    return 0 if result.get("success") else 1


def cmd_status(args):
    from config import load_config, load_state, discover_skills
    cfg = load_config()

    print(f"=== Zo Substrate Status ===")
    print(f"  Identity: {cfg['identity']['name']}")
    print(f"  Partner:  {cfg['partner']['name']}")
    print(f"  Repo:     {cfg['substrate']['repo']}")
    print()

    last_push = load_state(cfg, "last_push.json")
    if last_push:
        print(f"Last push: {last_push.get('last_push', 'never')}")
        pushed = last_push.get("pushed_skills", [])
        print(f"  Skills: {', '.join(pushed) if pushed else 'none'}")
    else:
        print("Last push: never")

    last_pull = load_state(cfg, "last_pull.json")
    if last_pull:
        print(f"Last pull: {last_pull.get('last_pull', 'never')}")
        pulled = last_pull.get("pulled_skills", [])
        print(f"  Skills: {', '.join(pulled) if pulled else 'none'}")
        print(f"  Source: {last_pull.get('source', 'unknown')}")
    else:
        print("Last pull: never")

    print()
    skills = discover_skills(cfg)
    print(f"Discoverable skills: {len(skills)}")
    for s in skills:
        print(f"  - {s['name']}")

    return 0


def cmd_setup(args):
    from setup import main as setup_main
    sys.argv = ["setup"] + args.setup_args
    setup_main()
    return 0


def cmd_bundle(args):
    from bundle import main as bundle_main
    sys.argv = ["bundle"] + args.bundle_args
    bundle_main()
    return 0


def cmd_context(args):
    from context import main as context_main
    sys.argv = ["context"] + args.context_args
    context_main()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Zo Substrate — Zo-to-Zo skill exchange",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    # push
    p = sub.add_parser("push", help="Push skills to substrate repo")
    p.add_argument("--skills", help="Comma-separated skill slugs (default: all)")
    p.add_argument("--dry-run", action="store_true")

    # pull
    pl = sub.add_parser("pull", help="Pull skills from substrate repo")
    pl.add_argument("--skills", help="Comma-separated skill slugs (default: all)")
    pl.add_argument("--dry-run", action="store_true")
    pl.add_argument("--verbose", action="store_true")

    # status
    sub.add_parser("status", help="Show sync status")

    # setup (pass-through)
    s = sub.add_parser("setup", help="Setup and configuration")
    s.add_argument("setup_args", nargs=argparse.REMAINDER, default=[])

    # bundle (pass-through)
    b = sub.add_parser("bundle", help="Skill bundling and validation")
    b.add_argument("bundle_args", nargs=argparse.REMAINDER, default=[])

    # context (pass-through)
    c = sub.add_parser("context", help="Local context awareness")
    c.add_argument("context_args", nargs=argparse.REMAINDER, default=[])

    args = parser.parse_args()

    handlers = {
        "push": cmd_push,
        "pull": cmd_pull,
        "status": cmd_status,
        "setup": cmd_setup,
        "bundle": cmd_bundle,
        "context": cmd_context,
    }

    if args.command in handlers:
        try:
            sys.exit(handlers[args.command](args))
        except FileNotFoundError as e:
            print(f"Config error: {e}")
            sys.exit(1)
        except ValueError as e:
            print(f"Validation error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
