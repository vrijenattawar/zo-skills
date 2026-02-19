#!/usr/bin/env python3
"""
Validate <YOUR_PRODUCT> decomposer outputs against canonical schema.

Usage:
    python3 validate.py <inbox_path>
    python3 validate.py <YOUR_PRODUCT>/meta-resumes/inbox/hardik-flowfuse
    python3 validate.py --all  # Validate all in inbox
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema")
    sys.exit(1)

INBOX_PATH = Path("./<YOUR_PRODUCT>/meta-resumes/inbox")
SCHEMA_PATH = Path(__file__).parent.parent / "assets" / "canonical_schema.json"


def load_schema():
    """Load the canonical schema."""
    if not SCHEMA_PATH.exists():
        print(f"ERROR: Schema not found at {SCHEMA_PATH}")
        sys.exit(1)
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def validate_candidate(candidate_dir: Path, schema: dict) -> dict:
    """Validate a single candidate's outputs."""
    results = {
        "path": str(candidate_dir),
        "valid": True,
        "errors": [],
        "warnings": [],
        "stats": {}
    }
    
    # Check required files
    required_files = ["manifest.yaml", "overview.yaml", "scores_complete.json"]
    for f in required_files:
        if not (candidate_dir / f).exists():
            results["errors"].append(f"Missing required file: {f}")
            results["valid"] = False
    
    # Validate scores_complete.json
    scores_path = candidate_dir / "scores_complete.json"
    if scores_path.exists():
        try:
            with open(scores_path) as f:
                scores = json.load(f)
            
            # Handle both wrapped structure (new) and flat array (legacy)
            if isinstance(scores, dict) and "skills" in scores:
                # New wrapped structure
                skills_array = scores.get("skills", [])
                results["stats"]["overall_score"] = scores.get("overall_score")
                results["stats"]["bottom_line"] = scores.get("bottom_line", "")[:100] if scores.get("bottom_line") else None
                results["stats"]["signal_strength"] = scores.get("signal_strength", {})
                
                # Check top-level required fields
                if scores.get("overall_score") is None:
                    results["warnings"].append("overall_score is null/missing in scores_complete.json")
                if not scores.get("bottom_line"):
                    results["warnings"].append("bottom_line is empty/missing in scores_complete.json")
                if not scores.get("category_scores"):
                    results["warnings"].append("category_scores missing in scores_complete.json")
            else:
                # Legacy flat array structure
                skills_array = scores if isinstance(scores, list) else []
                results["warnings"].append("Using legacy flat array format - should migrate to wrapped structure")
            
            results["stats"]["skill_count"] = len(skills_array)
            
            # Schema validation
            try:
                jsonschema.validate(scores, schema)
            except jsonschema.ValidationError as e:
                results["errors"].append(f"Schema validation: {e.message}")
                results["valid"] = False
            
            # Content checks
            ratings = {}
            missing_our_take = 0
            for skill in skills_array:
                if isinstance(skill, dict):
                    r = skill.get("rating", "Unknown")
                    ratings[r] = ratings.get(r, 0) + 1
                    if not skill.get("our_take") or len(skill.get("our_take", "")) < 50:
                        missing_our_take += 1
            
            results["stats"]["ratings"] = ratings
            
            if missing_our_take > 0:
                results["warnings"].append(f"{missing_our_take} skills have short/missing Our Take")
            
        except json.JSONDecodeError as e:
            results["errors"].append(f"Invalid JSON in scores_complete.json: {e}")
            results["valid"] = False
    
    # Check overview for score
    overview_path = candidate_dir / "overview.yaml"
    if overview_path.exists():
        import yaml
        try:
            with open(overview_path) as f:
                overview = yaml.safe_load(f.read())
            
            score = None
            if isinstance(overview, dict):
                cs = overview.get("<YOUR_PRODUCT>_score", {})
                if isinstance(cs, dict):
                    score = cs.get("overall")
                elif isinstance(cs, (int, float)):
                    score = cs
            
            if score is None:
                results["warnings"].append("<YOUR_PRODUCT>_score.overall is null/missing")
            else:
                results["stats"]["<YOUR_PRODUCT>_score"] = score
                
        except Exception as e:
            results["warnings"].append(f"Could not parse overview.yaml: {e}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Validate decomposer outputs")
    parser.add_argument("path", nargs="?", help="Path to candidate folder")
    parser.add_argument("--all", action="store_true", help="Validate all candidates in inbox")
    parser.add_argument("--source", help="Source document for provenance verification")
    
    args = parser.parse_args()
    
    schema = load_schema()
    
    if args.all:
        candidates = [d for d in INBOX_PATH.iterdir() if d.is_dir()]
    elif args.path:
        candidates = [Path(args.path)]
        if not candidates[0].is_absolute():
            candidates = [INBOX_PATH / args.path]
    else:
        parser.print_help()
        sys.exit(1)
    
    all_valid = True
    for candidate_dir in sorted(candidates):
        if not candidate_dir.exists():
            print(f"ERROR: {candidate_dir} not found")
            continue
        
        results = validate_candidate(candidate_dir, schema)
        
        status = "✓" if results["valid"] else "✗"
        print(f"\n{status} {candidate_dir.name}")
        
        if results["stats"]:
            score = results["stats"].get("<YOUR_PRODUCT>_score", "?")
            skills = results["stats"].get("skill_count", "?")
            ratings = results["stats"].get("ratings", {})
            print(f"  Score: {score}/100 | Skills: {skills} | Ratings: {ratings}")
        
        if results["errors"]:
            all_valid = False
            for e in results["errors"]:
                print(f"  ERROR: {e}")
        
        if results["warnings"]:
            for w in results["warnings"]:
                print(f"  WARN: {w}")
        
        # Provenance verification if source document provided
        if args.source:
            try:
                from verify import verify_our_takes, verify_story_ids
                
                source_path = Path(args.source)
                scores_path = candidate_dir / "scores_complete.json"
                
                print(f"  PROVENANCE CHECK:")
                
                # Verify our_take fields
                our_take_results = verify_our_takes(scores_path, source_path)
                if "error" in our_take_results:
                    print(f"    ERROR: {our_take_results['error']}")
                    all_valid = False
                else:
                    total_takes = len(our_take_results)
                    passed_takes = sum(1 for r in our_take_results.values() if r.get("found", False))
                    if passed_takes == total_takes:
                        print(f"    ✓ Our Take: {passed_takes}/{total_takes} verified")
                    else:
                        print(f"    ✗ Our Take: {passed_takes}/{total_takes} verified ({total_takes - passed_takes} failed)")
                        all_valid = False
                
                # Verify story IDs
                story_id_results = verify_story_ids(scores_path, source_path)
                if "error" in story_id_results:
                    print(f"    ERROR: {story_id_results['error']}")
                    all_valid = False
                else:
                    total_story_ids = sum(len(stories) for stories in story_id_results.values())
                    passed_story_ids = sum(sum(1 for found in stories.values() if found) for stories in story_id_results.values())
                    if passed_story_ids == total_story_ids:
                        print(f"    ✓ Story IDs: {passed_story_ids}/{total_story_ids} verified")
                    else:
                        print(f"    ✗ Story IDs: {passed_story_ids}/{total_story_ids} verified ({total_story_ids - passed_story_ids} failed)")
                        all_valid = False
                        
            except ImportError:
                print(f"    ERROR: Could not import verify.py (ensure it exists in same directory)")
                all_valid = False
            except Exception as e:
                print(f"    ERROR: Verification failed: {e}")
                all_valid = False
    
    print()
    if all_valid:
        print("✓ All validations passed")
        sys.exit(0)
    else:
        print("✗ Some validations failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
