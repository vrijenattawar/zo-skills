#!/usr/bin/env python3
"""Pulse LLM Filter — Uses LLM judgment to validate deposits.

Mechanical checks (pulse_code_validator.py) catch obvious stubs.
This filter uses LLM to catch:
- Code that passes syntax but doesn't actually work
- Incomplete implementations that appear complete
- Mismatches between brief requirements and delivery
- Subtle hallucinations (fake imports, nonexistent APIs)

Usage:
  pulse_llm_filter.py validate <slug> <drop_id>
  pulse_llm_filter.py batch <slug>  # Validate all pending deposits
"""

import argparse
import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple, Optional

from pulse_common import PATHS, WORKSPACE

BUILDS_DIR = PATHS.BUILDS
ZO_API_URL = "https://api.zo.computer/zo/ask"
LESSONS_FILE = PATHS.SYSTEM_LEARNINGS


def load_drop_brief(slug: str, drop_id: str) -> Optional[str]:
    """Load Drop brief."""
    drops_dir = BUILDS_DIR / slug / "drops"
    for f in drops_dir.glob("*.md"):
        if f.stem.startswith(drop_id):
            return f.read_text()
    return None


def load_deposit(slug: str, drop_id: str) -> Optional[Dict]:
    """Load deposit JSON."""
    deposit_path = BUILDS_DIR / slug / "deposits" / f"{drop_id}.json"
    if deposit_path.exists():
        return json.loads(deposit_path.read_text())
    return None


def load_artifact_contents(artifacts: list, max_lines: int = 200) -> Dict[str, str]:
    """Load artifact file contents for LLM review."""
    contents = {}
    for artifact in artifacts:
        path = Path(artifact)
        if not path.is_absolute():
            path = PATHS.WORKSPACE / artifact
        
        if path.exists() and path.is_file():
            try:
                text = path.read_text()
                lines = text.split('\n')
                if len(lines) > max_lines:
                    text = '\n'.join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
                contents[str(artifact)] = text
            except Exception as e:
                contents[str(artifact)] = f"[Error reading: {e}]"
        else:
            contents[str(artifact)] = "[FILE NOT FOUND]"
    
    return contents


async def llm_validate(slug: str, drop_id: str) -> Tuple[bool, Dict]:
    """Use LLM to validate a deposit against its brief."""
    
    brief = load_drop_brief(slug, drop_id)
    deposit = load_deposit(slug, drop_id)
    
    if not brief:
        return False, {'error': 'Brief not found', 'pass': False}
    if not deposit:
        return False, {'error': 'Deposit not found', 'pass': False}
    
    # Load artifact contents
    artifacts = deposit.get('artifacts', [])
    artifact_contents = load_artifact_contents(artifacts)
    
    # Build validation prompt
    prompt = f"""You are a code reviewer validating that a build Drop completed its work correctly.

## Drop Brief (What Was Requested)
```markdown
{brief}
```

## Deposit (What Was Claimed)
```json
{json.dumps(deposit, indent=2)}
```

## Artifact Contents
{chr(10).join(f"### {path}{chr(10)}```{chr(10)}{content}{chr(10)}```" for path, content in artifact_contents.items())}

## Validation Checklist

Evaluate each criterion (PASS/FAIL with brief reason):

1. **Artifacts Exist**: Do all claimed artifacts actually exist?
2. **Requirements Met**: Does the code fulfill the brief's requirements?
3. **Functional Code**: Is the code actually functional (not stubs, not incomplete)?
4. **No Hallucinations**: Are all imports, APIs, file paths real and correct?
5. **Scope Compliance**: Did the Drop stay within its defined scope?
6. **Quality Bar**: Would this code work if deployed right now?

## Your Response

Respond with ONLY valid JSON:
{{
  "pass": true/false,
  "confidence": 0.0-1.0,
  "checklist": {{
    "artifacts_exist": {{"pass": bool, "reason": "..."}},
    "requirements_met": {{"pass": bool, "reason": "..."}},
    "functional_code": {{"pass": bool, "reason": "..."}},
    "no_hallucinations": {{"pass": bool, "reason": "..."}},
    "scope_compliance": {{"pass": bool, "reason": "..."}},
    "quality_bar": {{"pass": bool, "reason": "..."}}
  }},
  "critical_issues": ["issue1", "issue2"],
  "recommendations": ["rec1", "rec2"],
  "summary": "One sentence overall assessment"
}}
"""

    # Call LLM
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        return False, {'error': 'ZO_CLIENT_IDENTITY_TOKEN not set', 'pass': False}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                ZO_API_URL,
                headers={
                    "authorization": token,
                    "content-type": "application/json"
                },
                json={
                    "input": prompt
                    # No output_format - let LLM return text, we'll parse JSON from it
                },
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return False, {'error': f'API error: {resp.status} - {error_text}', 'pass': False}
                
                result = await resp.json()
                output = result.get('output', '')
                
                # Parse JSON from output (may be wrapped in markdown code block)
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', output, re.DOTALL)
                if json_match:
                    validation = json.loads(json_match.group(1))
                else:
                    # Try parsing the whole output as JSON
                    try:
                        validation = json.loads(output)
                    except json.JSONDecodeError:
                        return False, {'error': 'Could not parse LLM response as JSON', 'raw': output[:500], 'pass': False}
                
                validation['drop_id'] = drop_id
                validation['build_slug'] = slug
                validation['validated_at'] = datetime.now(timezone.utc).isoformat()
                
                passed = validation.get('pass', False)
                
                # Log lesson if failed
                if not passed:
                    log_validation_failure(slug, drop_id, validation)
                
                return passed, validation
                
        except asyncio.TimeoutError:
            return False, {'error': 'LLM validation timeout', 'pass': False}
        except Exception as e:
            return False, {'error': str(e), 'pass': False}


def log_validation_failure(slug: str, drop_id: str, validation: Dict):
    """Log validation failure as a lesson."""
    LESSONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Determine category from checklist
    checklist = validation.get('checklist', {})
    if checklist.get('functional_code', {}).get('pass') == False:
        category = 'stub_code'
    elif checklist.get('no_hallucinations', {}).get('pass') == False:
        category = 'llm_hallucination'
    elif checklist.get('artifacts_exist', {}).get('pass') == False:
        category = 'missing_artifact'
    elif checklist.get('scope_compliance', {}).get('pass') == False:
        category = 'scope_creep'
    else:
        category = 'other'
    
    lesson = {
        'id': f"L{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'category': category,
        'severity': 'critical' if validation.get('confidence', 0) > 0.8 else 'high',
        'summary': validation.get('summary', 'LLM validation failed'),
        'build_slug': slug,
        'drop_id': drop_id,
        'details': {
            'checklist': checklist,
            'critical_issues': validation.get('critical_issues', []),
            'recommendations': validation.get('recommendations', [])
        },
        'resolution': 'pending'
    }
    
    with open(LESSONS_FILE, 'a') as f:
        f.write(json.dumps(lesson) + '\n')
    
    print(f"[LESSON] Logged: {lesson['id']} - {category}")


def save_filter_result(slug: str, drop_id: str, result: Dict):
    """Save filter result."""
    filter_path = BUILDS_DIR / slug / "deposits" / f"{drop_id}_llm_filter.json"
    filter_path.write_text(json.dumps(result, indent=2))


async def validate_drop(slug: str, drop_id: str) -> Tuple[bool, Dict]:
    """Full validation: mechanical + LLM."""
    print(f"[FILTER] Validating {drop_id}...")
    
    # Step 1: Mechanical check
    from pulse_code_validator import check_drop_artifacts
    mech_passed, mech_report = check_drop_artifacts(slug, drop_id)
    
    if not mech_passed:
        print(f"[FILTER] {drop_id} FAILED mechanical check ({mech_report.get('critical_count', 0)} critical issues)")
        result = {
            'pass': False,
            'stage': 'mechanical',
            'mechanical': mech_report,
            'llm': None
        }
        save_filter_result(slug, drop_id, result)
        return False, result
    
    # Step 2: LLM validation
    llm_passed, llm_result = await llm_validate(slug, drop_id)
    
    result = {
        'pass': llm_passed,
        'stage': 'llm',
        'mechanical': mech_report,
        'llm': llm_result
    }
    save_filter_result(slug, drop_id, result)
    
    if llm_passed:
        print(f"[FILTER] {drop_id} PASSED (confidence: {llm_result.get('confidence', 'N/A')})")
    else:
        print(f"[FILTER] {drop_id} FAILED LLM validation: {llm_result.get('summary', 'Unknown')}")
    
    return llm_passed, result


async def validate_batch(slug: str):
    """Validate all pending deposits."""
    deposits_dir = BUILDS_DIR / slug / "deposits"
    
    results = {}
    for deposit_file in sorted(deposits_dir.glob("D*.json")):
        # Skip filter results
        if '_filter' in deposit_file.name or '_llm_filter' in deposit_file.name or '_forensics' in deposit_file.name:
            continue
        
        drop_id = deposit_file.stem
        
        # Skip if already validated
        llm_filter_path = deposits_dir / f"{drop_id}_llm_filter.json"
        if llm_filter_path.exists():
            print(f"[FILTER] {drop_id} already validated, skipping")
            continue
        
        passed, result = await validate_drop(slug, drop_id)
        results[drop_id] = result
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Pulse LLM Filter')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # validate single
    val_parser = subparsers.add_parser('validate', help='Validate a single deposit')
    val_parser.add_argument('slug', help='Build slug')
    val_parser.add_argument('drop_id', help='Drop ID')
    
    # batch
    batch_parser = subparsers.add_parser('batch', help='Validate all pending deposits')
    batch_parser.add_argument('slug', help='Build slug')
    
    args = parser.parse_args()
    
    if args.command == 'validate':
        passed, result = asyncio.run(validate_drop(args.slug, args.drop_id))
        print(json.dumps(result, indent=2))
        sys.exit(0 if passed else 1)
    
    elif args.command == 'batch':
        results = asyncio.run(validate_batch(args.slug))
        passed = all(r.get('pass', False) for r in results.values())
        print(json.dumps(results, indent=2))
        sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
