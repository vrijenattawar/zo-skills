#!/usr/bin/env python3
"""
Set up the scheduled agent for Claude Code window priming.
Runs daily at 6:30am ET.
"""

import subprocess
import sys

def main():
    # Check for existing agent first
    result = subprocess.run(
        ["python3", "./N5/scripts/agent_conflict_gate.py", "--summary", "--no-cache"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    print("\nTo create the agent, run this in a Zo conversation:")
    print("""
create_agent with:
  - rrule: "FREQ=DAILY;BYHOUR=11;BYMINUTE=30" (6:30am ET = 11:30 UTC)
  - instruction: "Run: python3 ./Skills/claude-code-window-primer/scripts/prime_window.py"
  - delivery_method: "none" (silent)
""")
    
    print("\nOr ask Zo: 'Create a scheduled agent to run the claude-code-window-primer skill daily at 6:30am ET, silent delivery'")

if __name__ == "__main__":
    main()
