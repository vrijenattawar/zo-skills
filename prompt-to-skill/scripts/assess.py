#!/usr/bin/env python3
"""Assess a prompt for skill conversion eligibility."""

import argparse
import re
from pathlib import Path

def score_prompt(path: str) -> dict:
    """Score a prompt file for skill eligibility.
    
    Returns dict with:
      - score: int (total)
      - breakdown: dict of factor scores
      - recommendation: str ("convert" | "maybe" | "keep_as_prompt")
    """
    content = Path(path).read_text()
    
    factors = {
        'lines': len(content.splitlines()),
        'script_refs': len(re.findall(r'N5/scripts/|python3|bun ', content)),
        'phase_refs': len(re.findall(r'[Pp]hase|[Ss]tep \d', content)),
        'schema_refs': len(re.findall(r'schema|JSON|YAML|structured', content, re.I)),
        'prompt_refs': len(re.findall(r"file 'Prompts/", content)),
        'file_refs': len(re.findall(r"file '", content)),
        'headers': len(re.findall(r'^#+\s', content, re.M)),
        'code_blocks': len(re.findall(r'```', content)) // 2,
    }
    
    # Weighted scoring
    score = (
        (1 if factors['lines'] > 200 else 0) * 3 +
        min(factors['script_refs'], 10) +
        min(factors['phase_refs'], 10) +
        min(factors['schema_refs'], 5) +
        min(factors['prompt_refs'], 5) * 2 +
        min(factors['file_refs'], 5) +
        (1 if factors['headers'] > 10 else 0) * 2 +
        (1 if factors['code_blocks'] > 5 else 0) * 2
    )
    
    if score >= 15:
        recommendation = "convert"
    elif score >= 8:
        recommendation = "maybe"
    else:
        recommendation = "keep_as_prompt"
    
    return {
        'score': score,
        'breakdown': factors,
        'recommendation': recommendation
    }

def main():
    parser = argparse.ArgumentParser(description='Assess prompt for skill eligibility')
    parser.add_argument('path', help='Path to .prompt.md file')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()
    
    result = score_prompt(args.path)
    
    if args.json:
        import json
        print(json.dumps(result, indent=2))
    else:
        print(f"Score: {result['score']}")
        print(f"Recommendation: {result['recommendation'].upper()}")
        print(f"\nBreakdown:")
        for k, v in result['breakdown'].items():
            print(f"  {k}: {v}")

if __name__ == '__main__':
    main()