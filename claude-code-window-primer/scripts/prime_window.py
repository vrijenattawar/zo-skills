#!/usr/bin/env python3
"""
Claude Code Window Primer

Primes the Claude Code 5-hour usage window with a trivial Opus request.
Returns 0 or 1 at random — minimal tokens, starts the window.

Usage:
    python3 prime_window.py [--help]

Requires:
    ZO_CLIENT_IDENTITY_TOKEN environment variable (auto-set on Zo)
"""

import os
import sys

def prime_window() -> int:
    """Make a trivial Opus request to start the 5-hour window."""
    
    # Import here to fail gracefully if requests not installed
    try:
        import requests
    except ImportError:
        print("ERROR: requests library required. Run: pip install requests")
        return 1
    
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        print("ERROR: ZO_CLIENT_IDENTITY_TOKEN not set")
        print("This script must run on Zo Computer.")
        return 1
    
    try:
        response = requests.post(
            "https://api.zo.computer/zo/ask",
            headers={
                "authorization": token,
                "content-type": "application/json"
            },
            json={
                "input": "Return either 0 or 1 at random. Nothing else.",
                "model_name": "claude-opus-4-5-20251101"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json().get("output", "").strip()
            print(f"Window primed. Opus returned: {result}")
            return 0
        else:
            print(f"ERROR: {response.status_code} - {response.text}")
            return 1
            
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out")
        return 1
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed - {e}")
        return 1


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0
    return prime_window()


if __name__ == "__main__":
    sys.exit(main())
