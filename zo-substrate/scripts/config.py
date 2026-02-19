#!/usr/bin/env python3
"""
Zo Substrate — Configuration loader and shared utilities.

Loads substrate.yaml from the skill's config directory
and provides common helpers used across all substrate scripts.
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml")
    sys.exit(1)


WORKSPACE_ROOT = Path(os.environ.get("ZO_WORKSPACE", "/home/workspace"))
SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = SKILL_DIR / "config" / "substrate.yaml"
CONFIG_EXAMPLE = SKILL_DIR / "config" / "substrate.yaml.example"


def load_config() -> Dict[str, Any]:
    """Load and validate substrate configuration."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Config not found: {CONFIG_FILE}\n"
            f"Copy the example and customize:\n"
            f"  cp {CONFIG_EXAMPLE} {CONFIG_FILE}"
        )

    with open(CONFIG_FILE) as f:
        cfg = yaml.safe_load(f) or {}

    errors = []
    if not cfg.get("identity", {}).get("name"):
        errors.append("identity.name is required")
    if not cfg.get("partner", {}).get("name"):
        errors.append("partner.name is required")
    if not cfg.get("substrate", {}).get("repo"):
        errors.append("substrate.repo is required")

    if errors:
        raise ValueError("Config validation failed:\n  " + "\n  ".join(errors))

    cfg.setdefault("substrate", {}).setdefault("branch", "main")
    cfg["substrate"].setdefault("clone_method", "https")
    cfg.setdefault("export", {}).setdefault("skills", [])
    cfg["export"].setdefault("auto_detect", True)
    cfg["export"].setdefault("exclude", ["zo-substrate"])
    cfg.setdefault("pull", {}).setdefault("install_dir", "Skills")
    cfg["pull"].setdefault("backup_existing", True)
    cfg["pull"].setdefault("auto_pull", False)
    cfg.setdefault("notifications", {}).setdefault("enabled", False)
    cfg["notifications"].setdefault("method", "log")
    cfg.setdefault("state", {}).setdefault("dir", "data/zo-substrate")

    return cfg


def state_dir(cfg: Dict) -> Path:
    """Get the state directory path, creating it if needed."""
    d = WORKSPACE_ROOT / cfg["state"]["dir"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_state(cfg: Dict, filename: str) -> Dict:
    """Load a JSON state file."""
    p = state_dir(cfg) / filename
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def save_state(cfg: Dict, filename: str, data: Dict) -> None:
    """Save a JSON state file."""
    p = state_dir(cfg) / filename
    p.write_text(json.dumps(data, indent=2, default=str))


def repo_url(cfg: Dict) -> str:
    """Build the git remote URL for the substrate repo."""
    repo = cfg["substrate"]["repo"]
    method = cfg["substrate"].get("clone_method", "https")
    if method == "ssh":
        return f"git@github.com:{repo}.git"
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return f"https://{token}@github.com/{repo}.git"
    return f"https://github.com/{repo}.git"


def tmp_repo_path(cfg: Dict) -> Path:
    """Temp directory for cloned substrate repo."""
    name = cfg["substrate"]["repo"].replace("/", "_")
    return Path(f"/tmp/zo-substrate-{name}")


def run_git(cmd: List[str], cwd: Path, check: bool = True) -> Tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return e.returncode, e.stdout.strip() if e.stdout else "", e.stderr.strip() if e.stderr else ""


def compute_checksum(filepath: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def now_iso() -> str:
    """Current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def get_workspace_git_sha() -> str:
    """Get the current git SHA of the workspace (if it's a git repo)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=WORKSPACE_ROOT,
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def discover_skills(cfg: Dict) -> List[Dict[str, Any]]:
    """
    Discover skills to export based on config.

    Returns list of dicts: [{name, path, has_scripts}, ...]
    """
    skills_dir = WORKSPACE_ROOT / "Skills"
    if not skills_dir.exists():
        return []

    explicit = cfg["export"].get("skills", [])
    exclude = set(cfg["export"].get("exclude", []))
    auto = cfg["export"].get("auto_detect", True)

    results = []

    if explicit:
        candidates = [(skills_dir / s) for s in explicit]
    elif auto:
        candidates = [d for d in skills_dir.iterdir() if d.is_dir()]
    else:
        return []

    for skill_path in candidates:
        if not skill_path.is_dir():
            continue
        name = skill_path.name
        if name in exclude:
            continue
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            continue

        scripts_dir = skill_path / "scripts"
        has_scripts = scripts_dir.exists() and any(scripts_dir.iterdir())

        results.append({
            "name": name,
            "path": str(skill_path.relative_to(WORKSPACE_ROOT)),
            "abs_path": str(skill_path),
            "has_scripts": has_scripts,
        })

    return results


def log_event(cfg: Dict, event: str, details: Optional[Dict] = None) -> None:
    """Append an event to the substrate log."""
    log_file = state_dir(cfg) / "substrate.log"
    entry = {
        "timestamp": now_iso(),
        "event": event,
        "identity": cfg["identity"]["name"],
    }
    if details:
        entry["details"] = details
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
