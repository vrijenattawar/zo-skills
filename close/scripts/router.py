#!/usr/bin/env python3
"""
Close router — reads SESSION_STATE.md and determines which close skill to invoke.

Usage:
    python3 router.py --convo-id <conversation_id> [--dry-run]
"""

import argparse
import os
import re
import sys


DEFAULT_WORKSPACE_ROOT = "/home/.z/workspaces"


def find_session_state(convo_id: str) -> str | None:
    workspace = os.path.join(DEFAULT_WORKSPACE_ROOT, convo_id)
    path = os.path.join(workspace, "SESSION_STATE.md")
    if os.path.isfile(path):
        return path
    return None


def parse_session_state(path: str) -> dict:
    with open(path, "r") as f:
        content = f.read()

    state: dict = {
        "drop_id": None,
        "build_slug": None,
        "conversation_type": None,
        "status": None,
    }

    for line in content.splitlines():
        line_stripped = line.strip()

        match = re.match(r"^drop_id:\s*(.+)$", line_stripped)
        if match:
            val = match.group(1).strip().strip('"').strip("'")
            if val and val.lower() not in ("null", "none", "~", ""):
                state["drop_id"] = val

        match = re.match(r"^build_slug:\s*(.+)$", line_stripped)
        if match:
            val = match.group(1).strip().strip('"').strip("'")
            if val and val.lower() not in ("null", "none", "~", ""):
                state["build_slug"] = val

        match = re.match(r"^type:\s*(.+)$", line_stripped)
        if match:
            state["conversation_type"] = match.group(1).strip()

        match = re.match(r"^status:\s*(.+)$", line_stripped)
        if match:
            state["status"] = match.group(1).strip()

    return state


def determine_close_skill(state: dict) -> str:
    if state.get("drop_id"):
        return "drop-close"
    if state.get("build_slug"):
        return "build-close"
    return "thread-close"


def main():
    parser = argparse.ArgumentParser(
        description="Determine which close skill to invoke based on SESSION_STATE context."
    )
    parser.add_argument(
        "--convo-id",
        required=True,
        help="Conversation ID (used to locate the workspace)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print which close skill would be invoked without executing anything",
    )
    args = parser.parse_args()

    session_path = find_session_state(args.convo_id)

    if not session_path:
        print(f"SESSION_STATE.md not found for conversation {args.convo_id}")
        print("Defaulting to: thread-close")
        if not args.dry_run:
            print("ACTION: invoke thread-close")
        sys.exit(0)

    state = parse_session_state(session_path)
    skill = determine_close_skill(state)

    print(f"Session state: {session_path}")
    print(f"  drop_id:     {state.get('drop_id', '—')}")
    print(f"  build_slug:  {state.get('build_slug', '—')}")
    print(f"  type:        {state.get('conversation_type', '—')}")
    print(f"  status:      {state.get('status', '—')}")
    print(f"")
    print(f"Routed to: {skill}")

    if args.dry_run:
        print("(dry run — no action taken)")
    else:
        print(f"ACTION: invoke {skill}")


if __name__ == "__main__":
    main()
