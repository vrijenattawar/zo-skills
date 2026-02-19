#!/usr/bin/env python3
"""
Pulse File Routing: Defines where different artifact types should be stored.

This module codifies routing rules for all Pulse-generated artifacts.
Rules are enforced during build execution and tidying.

Usage:
    # Get destination for an artifact
    python3 pulse_file_routing.py route "research" --build-slug my-build --name "competitor-analysis.md"
    
    # Validate a file is in correct location
    python3 pulse_file_routing.py validate /path/to/file.md
    
    # List all routing rules
    python3 pulse_file_routing.py rules

Part of Pulse v3.
"""

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from pulse_common import PATHS, WORKSPACE


# =============================================================================
# PATHS
# =============================================================================

class Destinations:
    """Canonical destinations for all artifact types."""
    
    # Build artifacts - stay with build
    BUILDS = WORKSPACE / "N5" / "builds"
    
    # Research - staging area, NOT auto-indexed
    RESEARCH = WORKSPACE / "Research"
    RESEARCH_BUILDS = RESEARCH / "builds"      # Research tied to builds
    RESEARCH_TOPICS = RESEARCH / "topics"      # Topic-based research
    RESEARCH_INTEL = RESEARCH / "intel"        # Market/competitor intel
    RESEARCH_ARCHIVE = RESEARCH / "archive"    # Completed research
    
    # Reports - internal
    REPORTS = WORKSPACE / "Reports" / "Internal"
    
    # Skills - reusable functionality
    SKILLS = WORKSPACE / "Skills"
    
    # Knowledge - GATED, requires explicit promotion
    KNOWLEDGE = WORKSPACE / "Knowledge"
    CONTENT_LIBRARY = KNOWLEDGE / "content-library"
    SEMANTIC_MEMORY = KNOWLEDGE / "semantic-memory"
    
    # Content drafts
    DRAFTS = WORKSPACE / "Drafts"


# =============================================================================
# ROUTING RULES
# =============================================================================

class ArtifactType(Enum):
    """Types of artifacts Pulse can generate."""
    BUILD_ARTIFACT = "build_artifact"      # Code, configs, schemas
    BUILD_DEPOSIT = "build_deposit"        # Worker completion reports
    BUILD_PLAN = "build_plan"              # PLAN.md and briefs
    RESEARCH = "research"                  # Research outputs
    RESEARCH_INTEL = "research_intel"      # Market/competitor intel
    REPORT = "report"                      # Ad-hoc reports
    SKILL = "skill"                        # Reusable skill
    CONTENT_DRAFT = "content_draft"        # Content for review
    CHECKPOINT_REPORT = "checkpoint_report" # Checkpoint findings


@dataclass
class RoutingRule:
    """A routing rule for an artifact type."""
    artifact_type: ArtifactType
    destination_base: Path
    subdirectory_pattern: Optional[str] = None  # e.g., "{build_slug}" or "{topic}"
    filename_pattern: Optional[str] = None       # e.g., "{name}.md"
    auto_index: bool = False                     # Whether it gets indexed
    description: str = ""


# The routing table
ROUTING_RULES: dict[ArtifactType, RoutingRule] = {
    ArtifactType.BUILD_ARTIFACT: RoutingRule(
        artifact_type=ArtifactType.BUILD_ARTIFACT,
        destination_base=Destinations.BUILDS,
        subdirectory_pattern="{build_slug}/artifacts",
        auto_index=False,
        description="Code, configs, schemas created during build"
    ),
    
    ArtifactType.BUILD_DEPOSIT: RoutingRule(
        artifact_type=ArtifactType.BUILD_DEPOSIT,
        destination_base=Destinations.BUILDS,
        subdirectory_pattern="{build_slug}/deposits",
        filename_pattern="{drop_id}.json",
        auto_index=False,
        description="Worker completion reports"
    ),
    
    ArtifactType.BUILD_PLAN: RoutingRule(
        artifact_type=ArtifactType.BUILD_PLAN,
        destination_base=Destinations.BUILDS,
        subdirectory_pattern="{build_slug}",
        auto_index=False,
        description="PLAN.md and worker briefs"
    ),
    
    ArtifactType.RESEARCH: RoutingRule(
        artifact_type=ArtifactType.RESEARCH,
        destination_base=Destinations.RESEARCH_BUILDS,
        subdirectory_pattern="{build_slug}",
        auto_index=False,
        description="Research outputs tied to a build (NOT auto-indexed)"
    ),
    
    ArtifactType.RESEARCH_INTEL: RoutingRule(
        artifact_type=ArtifactType.RESEARCH_INTEL,
        destination_base=Destinations.RESEARCH_INTEL,
        subdirectory_pattern="{topic}",
        auto_index=False,
        description="Market/competitor intelligence (NOT auto-indexed)"
    ),
    
    ArtifactType.REPORT: RoutingRule(
        artifact_type=ArtifactType.REPORT,
        destination_base=Destinations.REPORTS,
        subdirectory_pattern="{date}",
        filename_pattern="{name}.md",
        auto_index=False,
        description="Ad-hoc internal reports"
    ),
    
    ArtifactType.SKILL: RoutingRule(
        artifact_type=ArtifactType.SKILL,
        destination_base=Destinations.SKILLS,
        subdirectory_pattern="{skill_slug}",
        auto_index=False,
        description="Reusable skills (SKILL.md + scripts)"
    ),
    
    ArtifactType.CONTENT_DRAFT: RoutingRule(
        artifact_type=ArtifactType.CONTENT_DRAFT,
        destination_base=Destinations.DRAFTS,
        subdirectory_pattern="{content_type}",
        auto_index=False,
        description="Content drafts awaiting review"
    ),
    
    ArtifactType.CHECKPOINT_REPORT: RoutingRule(
        artifact_type=ArtifactType.CHECKPOINT_REPORT,
        destination_base=Destinations.BUILDS,
        subdirectory_pattern="{build_slug}/checkpoints",
        filename_pattern="{checkpoint_id}.json",
        auto_index=False,
        description="Checkpoint verification reports"
    ),
}


# =============================================================================
# ROUTING FUNCTIONS
# =============================================================================

def get_destination(
    artifact_type: str | ArtifactType,
    build_slug: Optional[str] = None,
    name: Optional[str] = None,
    topic: Optional[str] = None,
    drop_id: Optional[str] = None,
    checkpoint_id: Optional[str] = None,
    skill_slug: Optional[str] = None,
    content_type: Optional[str] = None,
) -> Path:
    """
    Get the canonical destination path for an artifact.
    
    Args:
        artifact_type: Type of artifact (string or enum)
        build_slug: Build identifier (for build-related artifacts)
        name: Filename (without extension for some types)
        topic: Topic name (for research/intel)
        drop_id: Drop ID (for deposits)
        checkpoint_id: Checkpoint ID (for checkpoint reports)
        skill_slug: Skill slug (for skills)
        content_type: Content type (for drafts)
    
    Returns:
        Full path where artifact should be stored
    """
    if isinstance(artifact_type, str):
        artifact_type = ArtifactType(artifact_type)
    
    rule = ROUTING_RULES.get(artifact_type)
    if not rule:
        raise ValueError(f"Unknown artifact type: {artifact_type}")
    
    # Build the path
    dest = rule.destination_base
    
    if rule.subdirectory_pattern:
        subdir = rule.subdirectory_pattern.format(
            build_slug=build_slug or "unknown",
            topic=topic or "general",
            date=datetime.now().strftime("%Y-%m-%d"),
            skill_slug=skill_slug or "unknown",
            content_type=content_type or "misc",
            checkpoint_id=checkpoint_id or "unknown",
        )
        dest = dest / subdir
    
    if rule.filename_pattern and name:
        filename = rule.filename_pattern.format(
            name=name,
            drop_id=drop_id or "unknown",
            checkpoint_id=checkpoint_id or "unknown",
        )
        dest = dest / filename
    elif name:
        dest = dest / name
    
    return dest


def validate_location(file_path: Path | str) -> dict:
    """
    Validate if a file is in its correct canonical location.
    
    Returns:
        {
            "valid": bool,
            "current_path": str,
            "expected_path": str or None,
            "artifact_type": str or None,
            "issue": str or None
        }
    """
    file_path = Path(file_path)
    
    # Try to detect artifact type from path
    path_str = str(file_path)
    
    detected_type = None
    expected_base = None
    
    # Check against known patterns
    if "/N5/builds/" in path_str and "/deposits/" in path_str:
        detected_type = ArtifactType.BUILD_DEPOSIT
        expected_base = Destinations.BUILDS
    elif "/N5/builds/" in path_str and "/artifacts/" in path_str:
        detected_type = ArtifactType.BUILD_ARTIFACT
        expected_base = Destinations.BUILDS
    elif "/N5/builds/" in path_str and "/checkpoints/" in path_str:
        detected_type = ArtifactType.CHECKPOINT_REPORT
        expected_base = Destinations.BUILDS
    elif "/Research/builds/" in path_str:
        detected_type = ArtifactType.RESEARCH
        expected_base = Destinations.RESEARCH_BUILDS
    elif "/Research/intel/" in path_str:
        detected_type = ArtifactType.RESEARCH_INTEL
        expected_base = Destinations.RESEARCH_INTEL
    elif "/Reports/Internal/" in path_str:
        detected_type = ArtifactType.REPORT
        expected_base = Destinations.REPORTS
    elif "/Skills/" in path_str:
        detected_type = ArtifactType.SKILL
        expected_base = Destinations.SKILLS
    
    if detected_type and expected_base:
        is_under_expected = str(file_path).startswith(str(expected_base))
        return {
            "valid": is_under_expected,
            "current_path": str(file_path),
            "expected_base": str(expected_base),
            "artifact_type": detected_type.value,
            "issue": None if is_under_expected else f"File should be under {expected_base}"
        }
    
    return {
        "valid": True,  # Can't validate unknown types
        "current_path": str(file_path),
        "expected_base": None,
        "artifact_type": None,
        "issue": "Could not detect artifact type"
    }


def list_rules() -> list[dict]:
    """List all routing rules."""
    return [
        {
            "type": rule.artifact_type.value,
            "destination": str(rule.destination_base),
            "subdirectory_pattern": rule.subdirectory_pattern,
            "filename_pattern": rule.filename_pattern,
            "auto_index": rule.auto_index,
            "description": rule.description,
        }
        for rule in ROUTING_RULES.values()
    ]


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Pulse file routing")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # route command
    route_parser = subparsers.add_parser("route", help="Get destination for artifact")
    route_parser.add_argument("artifact_type", help="Type of artifact")
    route_parser.add_argument("--build-slug", help="Build slug")
    route_parser.add_argument("--name", help="Filename")
    route_parser.add_argument("--topic", help="Topic name")
    route_parser.add_argument("--drop-id", help="Drop ID")
    route_parser.add_argument("--checkpoint-id", help="Checkpoint ID")
    route_parser.add_argument("--skill-slug", help="Skill slug")
    route_parser.add_argument("--content-type", help="Content type")
    
    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate file location")
    validate_parser.add_argument("file_path", help="Path to file")
    
    # rules command
    subparsers.add_parser("rules", help="List all routing rules")
    
    args = parser.parse_args()
    
    if args.command == "route":
        dest = get_destination(
            artifact_type=args.artifact_type,
            build_slug=args.build_slug,
            name=args.name,
            topic=args.topic,
            drop_id=args.drop_id,
            checkpoint_id=args.checkpoint_id,
            skill_slug=args.skill_slug,
            content_type=args.content_type,
        )
        print(dest)
    
    elif args.command == "validate":
        result = validate_location(args.file_path)
        print(json.dumps(result, indent=2))
    
    elif args.command == "rules":
        rules = list_rules()
        print(json.dumps(rules, indent=2))


if __name__ == "__main__":
    main()
