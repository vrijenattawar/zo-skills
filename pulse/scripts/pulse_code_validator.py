#!/usr/bin/env python3
"""Pulse Code Validator — Detects stubs, TODOs, and non-functional code.

This runs as part of deposit filtering. Code with critical issues is REJECTED.

Usage:
  pulse_code_validator.py check <slug> <drop_id>
  pulse_code_validator.py scan <path>
  pulse_code_validator.py report <slug>
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

from pulse_common import PATHS, WORKSPACE

# Patterns that indicate non-functional code
CRITICAL_PATTERNS = [
    (r'^\s*pass\s*$', 'empty_pass', 'Function body is just `pass`'),
    (r'^\s*\.\.\.\s*$', 'ellipsis_stub', 'Function body is just `...`'),
    (r'raise NotImplementedError', 'not_implemented', 'Raises NotImplementedError'),
    (r'TODO:\s*implement', 'todo_implement', 'TODO: implement marker'),
    (r'STUB', 'stub_marker', 'STUB marker in code'),
    (r'FIXME:\s*critical', 'fixme_critical', 'Critical FIXME'),
]

# Patterns that are warnings but not blockers
WARNING_PATTERNS = [
    (r'TODO(?!:)', 'todo_generic', 'Generic TODO comment'),
    (r'HACK', 'hack_marker', 'HACK marker'),
    (r'XXX', 'xxx_marker', 'XXX marker'),
    (r'FIXME', 'fixme_generic', 'Generic FIXME'),
    (r'#.*placeholder', 'placeholder_comment', 'Placeholder comment'),
]


def scan_file(filepath: Path) -> Dict:
    """Scan a single file for issues."""
    issues = {
        'critical': [],
        'warnings': [],
        'stats': {
            'lines': 0,
            'functions': 0,
            'empty_functions': 0
        }
    }
    
    if not filepath.exists():
        return issues
    
    try:
        content = filepath.read_text()
        lines = content.split('\n')
        issues['stats']['lines'] = len(lines)
    except Exception as e:
        issues['critical'].append({
            'type': 'read_error',
            'message': str(e),
            'line': 0
        })
        return issues
    
    # Scan line by line
    for i, line in enumerate(lines, 1):
        # Critical patterns
        for pattern, issue_type, message in CRITICAL_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                issues['critical'].append({
                    'type': issue_type,
                    'message': message,
                    'line': i,
                    'content': line.strip()[:100]
                })
        
        # Warning patterns
        for pattern, issue_type, message in WARNING_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                issues['warnings'].append({
                    'type': issue_type,
                    'message': message,
                    'line': i,
                    'content': line.strip()[:100]
                })
    
    # Check for empty functions (Python)
    if filepath.suffix == '.py':
        func_pattern = r'^(async\s+)?def\s+\w+\([^)]*\):'
        in_function = False
        func_start = 0
        func_indent = 0
        
        for i, line in enumerate(lines, 1):
            if re.match(func_pattern, line.strip()):
                issues['stats']['functions'] += 1
                in_function = True
                func_start = i
                func_indent = len(line) - len(line.lstrip())
            elif in_function:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent <= func_indent and stripped:
                        in_function = False
                    elif stripped in ['pass', '...']:
                        # Check if this is the only statement
                        issues['stats']['empty_functions'] += 1
    
    return issues


def scan_directory(dirpath: Path, extensions: List[str] = None) -> Dict[str, Dict]:
    """Scan all files in a directory."""
    if extensions is None:
        extensions = ['.py', '.ts', '.js', '.md']
    
    results = {}
    for ext in extensions:
        for filepath in dirpath.rglob(f'*{ext}'):
            if '__pycache__' in str(filepath):
                continue
            rel_path = str(filepath.relative_to(dirpath))
            results[rel_path] = scan_file(filepath)
    
    return results


def check_drop_artifacts(slug: str, drop_id: str) -> Tuple[bool, Dict]:
    """Check artifacts created by a Drop for issues.
    
    Returns: (passed, report)
    """
    deposit_path = PATHS.BUILDS / slug / "deposits" / f"{drop_id}.json"
    if not deposit_path.exists():
        return False, {'error': 'Deposit not found'}
    
    deposit = json.loads(deposit_path.read_text())
    artifacts = deposit.get('artifacts', [])
    
    report = {
        'drop_id': drop_id,
        'build_slug': slug,
        'timestamp': datetime.utcnow().isoformat(),
        'files_checked': 0,
        'critical_count': 0,
        'warning_count': 0,
        'issues': {}
    }
    
    for artifact in artifacts:
        artifact_path = Path(artifact)
        if not artifact_path.is_absolute():
            artifact_path = PATHS.WORKSPACE / artifact
        
        if artifact_path.exists() and artifact_path.is_file():
            issues = scan_file(artifact_path)
            report['files_checked'] += 1
            report['critical_count'] += len(issues['critical'])
            report['warning_count'] += len(issues['warnings'])
            
            if issues['critical'] or issues['warnings']:
                report['issues'][str(artifact_path)] = issues
    
    passed = report['critical_count'] == 0
    
    # Log lesson if failed
    if not passed:
        log_lesson(slug, drop_id, report)
    
    return passed, report


def log_lesson(slug: str, drop_id: str, report: Dict):
    """Log validation failure as a lesson."""
    PATHS.SYSTEM_LEARNINGS.parent.mkdir(parents=True, exist_ok=True)
    
    lesson = {
        'timestamp': datetime.utcnow().isoformat(),
        'build_slug': slug,
        'drop_id': drop_id,
        'category': 'stub_code',
        'severity': 'critical',
        'summary': f"Drop {drop_id} produced code with {report['critical_count']} critical issues",
        'details': report,
        'resolution': 'pending'
    }
    
    with open(PATHS.SYSTEM_LEARNINGS, 'a') as f:
        f.write(json.dumps(lesson) + '\n')
    
    print(f"[LESSON] Logged validation failure for {drop_id}")


def generate_report(slug: str) -> Dict:
    """Generate full validation report for a build."""
    build_dir = PATHS.BUILDS / slug
    deposits_dir = build_dir / "deposits"
    
    report = {
        'build_slug': slug,
        'timestamp': datetime.utcnow().isoformat(),
        'drops': {},
        'total_critical': 0,
        'total_warnings': 0,
        'passed': True
    }
    
    for deposit_file in sorted(deposits_dir.glob("D*.json")):
        if '_filter' in deposit_file.name or '_forensics' in deposit_file.name:
            continue
        
        drop_id = deposit_file.stem
        passed, drop_report = check_drop_artifacts(slug, drop_id)
        report['drops'][drop_id] = drop_report
        report['total_critical'] += drop_report.get('critical_count', 0)
        report['total_warnings'] += drop_report.get('warning_count', 0)
        
        if not passed:
            report['passed'] = False
    
    return report


def main():
    parser = argparse.ArgumentParser(description='Pulse Code Validator')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # check command
    check_parser = subparsers.add_parser('check', help='Check a Drop\'s artifacts')
    check_parser.add_argument('slug', help='Build slug')
    check_parser.add_argument('drop_id', help='Drop ID')
    
    # scan command
    scan_parser = subparsers.add_parser('scan', help='Scan a path for issues')
    scan_parser.add_argument('path', help='File or directory path')
    
    # report command
    report_parser = subparsers.add_parser('report', help='Generate build report')
    report_parser.add_argument('slug', help='Build slug')
    
    args = parser.parse_args()
    
    if args.command == 'check':
        passed, report = check_drop_artifacts(args.slug, args.drop_id)
        print(json.dumps(report, indent=2))
        sys.exit(0 if passed else 1)
    
    elif args.command == 'scan':
        path = Path(args.path)
        if path.is_file():
            issues = scan_file(path)
            print(json.dumps({str(path): issues}, indent=2))
            sys.exit(0 if not issues['critical'] else 1)
        else:
            results = scan_directory(path)
            total_critical = sum(r['critical'].__len__() for r in results.values())
            print(json.dumps(results, indent=2))
            sys.exit(0 if total_critical == 0 else 1)
    
    elif args.command == 'report':
        report = generate_report(args.slug)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
