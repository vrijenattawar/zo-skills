#!/usr/bin/env python3
"""
Pulse Common: Shared paths, config, and utilities for all Pulse scripts.

This module centralizes:
- Path constants (no more hardcoding across scripts)
- Config loading/saving
- Common utilities

Import in other Pulse scripts:
    from pulse_common import PATHS, load_config, save_config
"""

import json
from pathlib import Path
from typing import Any, Optional
import os

# Environment-based workspace path (defaults to hardcoded for backward compatibility)
WORKSPACE = Path(os.environ.get("ZO_WORKSPACE", "/home/workspace"))


# ============================================================================
# PATH CONSTANTS
# ============================================================================

class PulsePaths:
    """Centralized path constants for Pulse system."""
    
    # Root paths
    WORKSPACE = WORKSPACE
    
    # N5 paths (pre-build lifecycle + builds)
    N5 = WORKSPACE / "N5"
    BUILDS = N5 / "builds"
    LEARNINGS = N5 / "learnings"
    SYSTEM_LEARNINGS = LEARNINGS / "SYSTEM_LEARNINGS.json"
    
    # Pulse lifecycle scripts (pre-build)
    PULSE_LIFECYCLE = N5 / "pulse"
    
    # Skills/pulse (orchestration)
    SKILL = WORKSPACE / "Skills" / "pulse"
    SCRIPTS = SKILL / "scripts"
    CONFIG = SKILL / "config"
    DROPS = SKILL / "drops"
    REFERENCES = SKILL / "references"
    
    # Config files
    CONFIG_FILE = CONFIG / "pulse_v2_config.json"
    CONTROL_FILE = N5 / "config" / "pulse_control.json"
    
    # Templates
    DROP_TEMPLATES = DROPS
    CHECKPOINT_TEMPLATE = DROPS / "checkpoint-template.md"
    TIDYING_TEMPLATES = DROPS / "tidying"
    
    @classmethod
    def build(cls, slug: str) -> Path:
        """Get path to a specific build directory."""
        return cls.BUILDS / slug
    
    @classmethod
    def build_meta(cls, slug: str) -> Path:
        """Get path to a build's meta.json."""
        return cls.BUILDS / slug / "meta.json"
    
    @classmethod
    def build_drops(cls, slug: str) -> Path:
        """Get path to a build's drops directory."""
        return cls.BUILDS / slug / "drops"
    
    @classmethod
    def build_deposits(cls, slug: str) -> Path:
        """Get path to a build's deposits directory."""
        return cls.BUILDS / slug / "deposits"
    
    @classmethod
    def build_artifacts(cls, slug: str) -> Path:
        """Get path to a build's artifacts directory."""
        return cls.BUILDS / slug / "artifacts"
    
    @classmethod
    def build_lessons(cls, slug: str) -> Path:
        """Get path to a build's BUILD_LESSONS.json."""
        return cls.BUILDS / slug / "BUILD_LESSONS.json"


# Convenience alias
PATHS = PulsePaths


# ============================================================================
# CONFIG MANAGEMENT
# ============================================================================

RECOVERY_DEFAULTS = {
    "max_auto_retries": 2,
    "dead_threshold_seconds": 900,
    "stale_threshold_hours": 4,
    "stale_no_progress_minutes": 60,
    "enable_ai_judgment": True,
}

DEFAULT_CONFIG = {
    "validation": {
        "enabled": True,
        "code_validator_enabled": True,
        "llm_filter_enabled": True,
        "llm_filter_timeout_seconds": 120,
        "code_validator_timeout_seconds": 60,
        "auto_pass_on_validator_error": True
    },
    "auto_fix": {
        "enabled": True,
        "confidence_threshold": 0.9
    },
    "sentinel": {
        "default_delivery": "email",  # email or sms
        "poll_interval_minutes": 5,
        "max_polls": 288,  # 24 hours at 5 min intervals
        "auto_create": True
    },
    "interview": {
        "confidence_threshold": 0.8,
        "max_questions": 10,
        "quiet_hours_start": 22,  # 10pm
        "quiet_hours_end": 7      # 7am
    },
    "checkpoints": {
        "enabled": True,
        "auto_pause_on_critical": True
    }
}


def load_config() -> dict:
    """Load Pulse config with defaults for missing fields."""
    config = DEFAULT_CONFIG.copy()
    
    if PATHS.CONFIG_FILE.exists():
        try:
            with open(PATHS.CONFIG_FILE) as f:
                user_config = json.load(f)
            # Deep merge user config into defaults
            _deep_merge(config, user_config)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load config: {e}")
    
    return config


def save_config(config: dict) -> None:
    """Save Pulse config."""
    PATHS.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PATHS.CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def load_control() -> dict:
    """Load Pulse control state (for Sentinel)."""
    if PATHS.CONTROL_FILE.exists():
        with open(PATHS.CONTROL_FILE) as f:
            return json.load(f)
    return {"state": "stopped", "active_build": None}


def save_control(control: dict) -> None:
    """Save Pulse control state."""
    PATHS.CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PATHS.CONTROL_FILE, "w") as f:
        json.dump(control, f, indent=2)


def _deep_merge(base: dict, override: dict) -> None:
    """Deep merge override into base dict, modifying base in place."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


# ============================================================================
# COMMON UTILITIES
# ============================================================================

def load_meta(slug: str) -> Optional[dict]:
    """Load a build's meta.json."""
    path = PATHS.build_meta(slug)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def save_meta(slug: str, meta: dict) -> None:
    """Save a build's meta.json."""
    path = PATHS.build_meta(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)


def list_builds(status: str = None) -> list[str]:
    """List all builds, optionally filtered by status."""
    builds = []
    if not PATHS.BUILDS.exists():
        return builds
    
    for build_dir in PATHS.BUILDS.iterdir():
        if not build_dir.is_dir():
            continue
        meta_path = build_dir / "meta.json"
        if not meta_path.exists():
            continue
        
        if status:
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                if meta.get("status") != status:
                    continue
            except (json.JSONDecodeError, IOError):
                continue
        
        builds.append(build_dir.name)
    
    return sorted(builds)


def parse_drop_id(drop_id: str) -> tuple[int, int]:
    """Parse drop ID into stream and order, supporting multi-digit streams and orders.
    
    Returns (0, 0) for invalid/unparseable IDs (e.g., checkpoints, malformed).
    """
    if not drop_id or not drop_id.startswith("D"):
        return (0, 0)
    parts = drop_id.split(".")
    if len(parts) != 2:
        return (0, 0)
    try:
        stream = int(parts[0][1:])
        order = int(parts[1])
        return (stream, order)
    except (ValueError, IndexError):
        return (0, 0)


def parse_wave_key(wave_key: str) -> int:
    """Parse wave key into index, supporting W<index>."""
    if not wave_key.startswith("W"):
        raise ValueError(f"Invalid wave key format: {wave_key}")
    try:
        index = int(wave_key[1:])
    except ValueError:
        raise ValueError(f"Invalid wave key format: {wave_key}")
    return index


def sort_wave_keys(keys: list[str]) -> list[str]:
    """Sort wave keys in ascending order."""
    return sorted(keys, key=lambda k: parse_wave_key(k))


def get_drop_stream_order(drop_id: str, info: dict) -> tuple[int, int]:
    """Get drop stream and order from info['stream']/info['order'] if present else parse_drop_id."""
    if "stream" in info and "order" in info:
        try:
            stream = int(info["stream"])
            order = int(info["order"])
        except (ValueError, TypeError):
            stream, order = parse_drop_id(drop_id)
    else:
        stream, order = parse_drop_id(drop_id)
    return stream, order


if __name__ == "__main__":
    # Quick test / info
    print("Pulse Common Module")
    print("=" * 40)
    print(f"Workspace:     {PATHS.WORKSPACE}")
    print(f"Builds:        {PATHS.BUILDS}")
    print(f"Config:        {PATHS.CONFIG_FILE}")
    print(f"Control:       {PATHS.CONTROL_FILE}")
    print(f"Skill:         {PATHS.SKILL}")
    print()
    print(f"Active builds: {list_builds('active')}")
    print(f"All builds:    {len(list_builds())} total")
