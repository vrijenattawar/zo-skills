#!/usr/bin/env python3
"""
Provenance verification for <YOUR_PRODUCT> decomposer outputs.

Validates that 'our_take' fields and story IDs from scores_complete.json
actually exist in the source document, to prevent hallucination.

Usage:
    python3 verify.py <candidate-slug> --source <source_doc_path>
    python3 verify.py hardik-flowfuse --source /path/to/<YOUR_PRODUCT>_ocr.txt
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Tuple

try:
    from rapidfuzz import fuzz
except ImportError:
    print("ERROR: rapidfuzz not installed. Run: pip install rapidfuzz")
    sys.exit(1)

INBOX_PATH = Path("./<YOUR_PRODUCT>/meta-resumes/inbox")


def fuzzy_substring_match(needle: str, haystack: str, threshold: float = 0.95) -> Tuple[bool, float]:
    """
    Check if needle exists as a substring in haystack with fuzzy tolerance.
    Returns (found, best_similarity_score).
    
    Uses rapidfuzz.fuzz.partial_ratio.
    Threshold of 0.95 allows minor whitespace/encoding differences but rejects paraphrasing.
    """
    # Use partial_ratio which finds the best matching substring
    similarity = fuzz.partial_ratio(needle.strip(), haystack) / 100.0
    return similarity >= threshold, similarity


def verify_our_takes(scores_path: Path, source_path: Path) -> Dict:
    """
    For each skill in scores_complete.json:
    1. Extract our_take text
    2. Check it exists in source doc (fuzzy match)
    3. Return {skill_name: {found: bool, similarity: float, snippet: str}}
    """
    if not scores_path.exists():
        return {"error": f"scores_complete.json not found at {scores_path}"}
    
    if not source_path.exists():
        return {"error": f"Source document not found at {source_path}"}
    
    # Load scores
    try:
        with open(scores_path) as f:
            scores = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return {"error": f"Could not read scores_complete.json: {e}"}
    
    # Load source document
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            source_text = f.read()
    except (IOError, UnicodeDecodeError) as e:
        return {"error": f"Could not read source document: {e}"}
    
    results = {}
    
    for skill in scores:
        if not isinstance(skill, dict):
            continue
            
        skill_name = skill.get("skill_name", "Unknown")
        our_take = skill.get("our_take", "")
        
        if not our_take or len(our_take.strip()) < 10:
            results[skill_name] = {
                "found": False,
                "similarity": 0.0,
                "snippet": "",
                "error": "our_take is empty or too short"
            }
            continue
        
        # Check if our_take exists in source with fuzzy matching
        found, similarity = fuzzy_substring_match(our_take, source_text)
        
        # Extract a snippet from source around the best match for context
        snippet = ""
        if similarity > 0.5:  # Only try to find snippet if there's some match
            # Use a simple approach: find the best matching 100-char window
            words = our_take.split()[:10]  # First 10 words as search terms
            if words:
                search_term = " ".join(words)
                try:
                    idx = source_text.lower().find(search_term.lower())
                    if idx >= 0:
                        start = max(0, idx - 50)
                        end = min(len(source_text), idx + len(search_term) + 50)
                        snippet = source_text[start:end].strip()
                        if start > 0:
                            snippet = "..." + snippet
                        if end < len(source_text):
                            snippet = snippet + "..."
                except:
                    pass
        
        results[skill_name] = {
            "found": found,
            "similarity": similarity,
            "snippet": snippet
        }
    
    return results


def verify_story_ids(scores_path: Path, source_path: Path) -> Dict:
    """
    For each skill's support[].source (story ID):
    1. Check the story ID pattern exists in source doc
    2. Return {skill_name: {story_id: str, found: bool}}
    """
    if not scores_path.exists():
        return {"error": f"scores_complete.json not found at {scores_path}"}
    
    if not source_path.exists():
        return {"error": f"Source document not found at {source_path}"}
    
    # Load scores
    try:
        with open(scores_path) as f:
            scores = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return {"error": f"Could not read scores_complete.json: {e}"}
    
    # Load source document
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            source_text = f.read()
    except (IOError, UnicodeDecodeError) as e:
        return {"error": f"Could not read source document: {e}"}
    
    results = {}
    
    for skill in scores:
        if not isinstance(skill, dict):
            continue
            
        skill_name = skill.get("skill_name", "Unknown")
        support = skill.get("support", [])
        
        story_ids = []
        for item in support:
            if isinstance(item, dict):
                story_id = item.get("source", "")
                if story_id:
                    story_ids.append(story_id)
        
        if not story_ids:
            continue
            
        results[skill_name] = {}
        for story_id in story_ids:
            # Check if story ID exists in source
            found = story_id in source_text
            results[skill_name][story_id] = found
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Verify decomposer outputs against source document")
    parser.add_argument("candidate_slug", help="Candidate folder name (e.g., hardik-flowfuse)")
    parser.add_argument("--source", required=True, help="Path to source document")
    parser.add_argument("--threshold", type=float, default=0.95, help="Fuzzy match threshold (default: 0.95)")
    
    args = parser.parse_args()
    
    # Resolve candidate path
    candidate_path = Path(args.candidate_slug)
    if not candidate_path.is_absolute():
        candidate_path = INBOX_PATH / args.candidate_slug
    
    if not candidate_path.exists() or not candidate_path.is_dir():
        print(f"ERROR: Candidate directory not found: {candidate_path}")
        sys.exit(1)
    
    scores_path = candidate_path / "scores_complete.json"
    source_path = Path(args.source)
    
    print(f"Verifying {args.candidate_slug} against source...")
    print()
    
    # Verify our_take fields
    our_take_results = verify_our_takes(scores_path, source_path)
    
    if "error" in our_take_results:
        print(f"ERROR: {our_take_results['error']}")
        sys.exit(1)
    
    # Count our_take results
    total_our_takes = len(our_take_results)
    passed_our_takes = sum(1 for r in our_take_results.values() if r.get("found", False))
    failed_our_takes = []
    
    for skill_name, result in our_take_results.items():
        if not result.get("found", False):
            similarity = result.get("similarity", 0.0)
            error = result.get("error", "")
            if error:
                failed_our_takes.append(f'  - "{skill_name}": {error}')
            elif similarity < args.threshold:
                failed_our_takes.append(f'  - "{skill_name}": similarity {similarity:.2f} (threshold {args.threshold})')
            else:
                failed_our_takes.append(f'  - "{skill_name}": NOT FOUND in source')
    
    if passed_our_takes == total_our_takes:
        print(f"✓ {passed_our_takes}/{total_our_takes} our_take fields verified")
    else:
        print(f"✓ {passed_our_takes}/{total_our_takes} our_take fields verified")
        print(f"✗ {len(failed_our_takes)} our_take fields FAILED:")
        for failure in failed_our_takes:
            print(failure)
    
    print()
    
    # Verify story IDs
    story_id_results = verify_story_ids(scores_path, source_path)
    
    if "error" in story_id_results:
        print(f"ERROR: {story_id_results['error']}")
        sys.exit(1)
    
    # Count story ID results
    total_story_ids = 0
    passed_story_ids = 0
    failed_story_ids = []
    
    for skill_name, story_results in story_id_results.items():
        for story_id, found in story_results.items():
            total_story_ids += 1
            if found:
                passed_story_ids += 1
            else:
                failed_story_ids.append(f'  - {story_id} (skill: "{skill_name}")')
    
    if passed_story_ids == total_story_ids:
        print(f"✓ {passed_story_ids}/{total_story_ids} story IDs verified")
    else:
        print(f"✓ {passed_story_ids}/{total_story_ids} story IDs verified")
        print(f"✗ {len(failed_story_ids)} story IDs NOT FOUND:")
        for failure in failed_story_ids:
            print(failure)
    
    print()
    
    # Final result
    total_issues = len(failed_our_takes) + len(failed_story_ids)
    
    if total_issues == 0:
        print("✓ VERIFICATION PASSED: All checks successful")
        sys.exit(0)
    else:
        print(f"✗ VERIFICATION FAILED: {total_issues} issues found")
        sys.exit(1)


if __name__ == "__main__":
    main()