#!/usr/bin/env python3
"""
Skills Importer - Import skills from GitHub repos into N5 Skills/ directory

Usage:
    python3 Skills/skills-importer/scripts/import_skill.py owner/repo/skill-name
    python3 Skills/skills-importer/scripts/import_skill.py owner/repo --list
    python3 Skills/skills-importer/scripts/import_skill.py owner/repo --all
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import yaml


class SkillImporter:
    def __init__(self):
        self.base_url = "https://raw.githubusercontent.com"
        self.skills_dir = Path("Skills")
        self.skills_dir.mkdir(exist_ok=True)
        
    def parse_source(self, source: str) -> Tuple[str, str, Optional[str]]:
        """Parse source into owner, repo, and optional skill_name"""
        parts = source.split('/')
        if len(parts) < 2:
            raise ValueError(f"Invalid source format: {source}. Expected owner/repo or owner/repo/skill-name")
        
        owner = parts[0]
        repo = parts[1]
        skill_name = parts[2] if len(parts) > 2 else None
        
        return owner, repo, skill_name
    
    def fetch_url(self, url: str) -> Optional[str]:
        """Fetch content from URL, return None if not found"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            return None
    
    def detect_repo_structure(self, owner: str, repo: str) -> str:
        """Detect if skills are in root or skills/ subdirectory"""
        # Try skills/ subdirectory first (most common)
        skills_subdir_url = f"{self.base_url}/{owner}/{repo}/main/skills"
        if self.fetch_url(f"{skills_subdir_url}/README.md") or self.fetch_url(f"{skills_subdir_url}/index.md"):
            return "skills"
        
        # Check for SKILL.md directly in root
        root_skill_url = f"{self.base_url}/{owner}/{repo}/main/SKILL.md"
        if self.fetch_url(root_skill_url):
            return "root"
        
        # Default to skills/ subdirectory
        return "skills"
    
    def get_branch(self, owner: str, repo: str) -> str:
        """Try main branch first, fall back to master"""
        main_url = f"{self.base_url}/{owner}/{repo}/main/README.md"
        if self.fetch_url(main_url):
            return "main"
        
        master_url = f"{self.base_url}/{owner}/{repo}/master/README.md"
        if self.fetch_url(master_url):
            return "master"
        
        # Default to main
        return "main"
    
    def list_skills(self, owner: str, repo: str) -> List[str]:
        """List all skills in a repository using GitHub API"""
        branch = self.get_branch(owner, repo)
        structure = self.detect_repo_structure(owner, repo)
        
        if structure == "root":
            # Single skill at root
            skill_url = f"{self.base_url}/{owner}/{repo}/{branch}/SKILL.md"
            if self.fetch_url(skill_url):
                return [repo]  # Use repo name as skill name
            return []
        
        # Use GitHub API to list directory contents
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/skills?ref={branch}"
        try:
            response = requests.get(api_url, timeout=30, headers={"Accept": "application/vnd.github.v3+json"})
            response.raise_for_status()
            contents = response.json()
            
            # Filter to directories that contain SKILL.md
            skills = []
            for item in contents:
                if item.get("type") == "dir":
                    skill_name = item["name"]
                    # Verify it has SKILL.md
                    skill_url = f"{self.base_url}/{owner}/{repo}/{branch}/skills/{skill_name}/SKILL.md"
                    if self.fetch_url(skill_url):
                        skills.append(skill_name)
            
            return sorted(skills)
            
        except requests.RequestException:
            # Fallback to checking common skill names if API fails
            skills = []
            skills_base_url = f"{self.base_url}/{owner}/{repo}/{branch}/skills"
            common_skills = [
                "frontend-design", "brainstorming", "systematic-debugging",
                "test-driven-development", "writing-plans", "verification-before-completion"
            ]
            for skill_name in common_skills:
                skill_url = f"{skills_base_url}/{skill_name}/SKILL.md"
                if self.fetch_url(skill_url):
                    skills.append(skill_name)
            return skills
    
    def fetch_skill_content(self, owner: str, repo: str, skill_name: str) -> Dict[str, str]:
        """Fetch all content for a skill (SKILL.md + supporting files)"""
        branch = self.get_branch(owner, repo)
        structure = self.detect_repo_structure(owner, repo)
        
        content = {}
        
        if structure == "root":
            base_path = ""
        else:
            base_path = f"skills/{skill_name}"
        
        # Fetch SKILL.md (required)
        skill_url = f"{self.base_url}/{owner}/{repo}/{branch}/{base_path}/SKILL.md"
        skill_content = self.fetch_url(skill_url)
        if not skill_content:
            raise ValueError(f"SKILL.md not found at {skill_url}")
        
        content["SKILL.md"] = skill_content
        
        # Try to fetch supporting directories
        for subdir in ["scripts", "references", "assets"]:
            subdir_path = f"{base_path}/{subdir}" if base_path else subdir
            
            # Try to fetch common files in each subdirectory
            files_found = []
            
            if subdir == "scripts":
                common_files = ["main.py", "index.js", "run.sh", "cli.py", "script.py"]
            elif subdir == "references":
                common_files = ["README.md", "api.md", "docs.md", "examples.md"]
            elif subdir == "assets":
                common_files = ["template.md", "config.json", "style.css"]
            else:
                common_files = []
            
            for filename in common_files:
                file_url = f"{self.base_url}/{owner}/{repo}/{branch}/{subdir_path}/{filename}"
                file_content = self.fetch_url(file_url)
                if file_content:
                    files_found.append((filename, file_content))
            
            if files_found:
                content[subdir] = dict(files_found)
        
        return content
    
    def parse_frontmatter(self, content: str) -> Tuple[Dict, str]:
        """Parse frontmatter and body from SKILL.md content"""
        if not content.startswith("---"):
            raise ValueError("SKILL.md must have YAML frontmatter")
        
        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError("Invalid frontmatter format")
        
        frontmatter_text = parts[1].strip()
        body = parts[2].strip()
        
        frontmatter = yaml.safe_load(frontmatter_text)
        return frontmatter, body
    
    def transform_frontmatter(self, original: Dict, owner: str, repo: str, skill_name: str) -> Dict:
        """Transform frontmatter from skills.sh format to N5 format"""
        if "name" not in original:
            raise ValueError("SKILL.md frontmatter must contain 'name' field")
        
        transformed = {
            "name": original["name"],
            "description": original.get("description", ""),
            "compatibility": original.get("compatibility", "Imported from skills.sh"),
            "created": datetime.now().strftime("%Y-%m-%d"),
            "last_edited": datetime.now().strftime("%Y-%m-%d"),
            "version": "1.0",
            "provenance": "skills-importer"
        }
        
        # Handle metadata
        metadata = original.get("metadata", {}).copy()
        metadata.update({
            "author": f"{owner} (imported)",
            "source": f"{owner}/{repo}/{skill_name}",
            "imported_at": datetime.now().strftime("%Y-%m-%d")
        })
        transformed["metadata"] = metadata
        
        return transformed
    
    def validate_skill(self, frontmatter: Dict, skill_name: str, force: bool = False) -> None:
        """Validate skill before installation"""
        if "name" not in frontmatter:
            raise ValueError("Frontmatter must contain 'name' field")
        
        dest_path = self.skills_dir / skill_name
        if dest_path.exists() and not force:
            raise ValueError(f"Skill '{skill_name}' already exists. Use --force to overwrite")
    
    def install_skill(self, skill_name: str, content: Dict[str, str], 
                     transformed_frontmatter: Dict, original_body: str) -> List[str]:
        """Install skill to Skills/ directory"""
        dest_path = self.skills_dir / skill_name
        dest_path.mkdir(exist_ok=True)
        
        installed_files = []
        
        # Write SKILL.md with transformed frontmatter
        skill_content = "---\n" + yaml.dump(transformed_frontmatter, default_flow_style=False) + "---\n\n" + original_body
        skill_file = dest_path / "SKILL.md"
        skill_file.write_text(skill_content)
        installed_files.append(str(skill_file))
        
        # Install supporting directories
        for subdir, files in content.items():
            if subdir == "SKILL.md":
                continue
            
            subdir_path = dest_path / subdir
            subdir_path.mkdir(exist_ok=True)
            
            for filename, file_content in files.items():
                file_path = subdir_path / filename
                file_path.write_text(file_content)
                installed_files.append(str(file_path))
        
        return installed_files
    
    def dry_run_report(self, owner: str, repo: str, skill_name: str, 
                      content: Dict[str, str], transformed_frontmatter: Dict, 
                      original_frontmatter: Dict) -> None:
        """Print dry run report"""
        structure = self.detect_repo_structure(owner, repo)
        branch = self.get_branch(owner, repo)
        
        if structure == "root":
            base_path = ""
        else:
            base_path = f"skills/{skill_name}"
        
        source_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{base_path}/SKILL.md"
        
        print(f"Fetching: {owner}/{repo}/{skill_name}")
        print(f"Source: {source_url}")
        print()
        print("--- Frontmatter Transformation ---")
        
        # Show changes
        for key in ["created", "last_edited", "version", "provenance"]:
            if key not in original_frontmatter:
                print(f"+ {key}: {transformed_frontmatter[key]}")
        
        new_metadata = transformed_frontmatter.get("metadata", {})
        orig_metadata = original_frontmatter.get("metadata", {})
        for key in ["author", "source", "imported_at"]:
            if key not in orig_metadata:
                print(f"+ metadata.{key}: {new_metadata[key]}")
        
        print()
        print("Files to copy:")
        print("  - SKILL.md (transformed)")
        
        for subdir in ["scripts", "references", "assets"]:
            if subdir in content:
                print(f"  - {subdir}/ ({len(content[subdir])} files)")
        
        print()
        print(f"Destination: Skills/{skill_name}/")
        print()
        print("[DRY RUN - no files written]")
    
    def import_skill(self, source: str, dry_run: bool = False, force: bool = False, 
                    dest: Optional[str] = None) -> Dict:
        """Import a single skill"""
        owner, repo, skill_name = self.parse_source(source)
        
        if not skill_name:
            raise ValueError("Must specify skill name for single import")
        
        dest_name = dest or skill_name
        
        # Fetch skill content
        content = self.fetch_skill_content(owner, repo, skill_name)
        
        # Parse and transform frontmatter
        original_frontmatter, body = self.parse_frontmatter(content["SKILL.md"])
        transformed_frontmatter = self.transform_frontmatter(original_frontmatter, owner, repo, skill_name)
        
        # Validate
        self.validate_skill(transformed_frontmatter, dest_name, force)
        
        if dry_run:
            self.dry_run_report(owner, repo, skill_name, content, 
                              transformed_frontmatter, original_frontmatter)
            return {"status": "dry_run", "skill": dest_name}
        
        # Install
        installed_files = self.install_skill(dest_name, content, transformed_frontmatter, body)
        
        print(f"✓ Imported {owner}/{repo}/{skill_name} to Skills/{dest_name}/")
        print(f"  Files installed: {len(installed_files)}")
        
        return {"status": "complete", "skill": dest_name, "files": installed_files}
    
    def import_all_skills(self, source: str, dry_run: bool = False, force: bool = False) -> Dict:
        """Import all skills from a repository"""
        owner, repo, _ = self.parse_source(source)
        
        skills = self.list_skills(owner, repo)
        if not skills:
            print(f"No skills found in {owner}/{repo}")
            return {"status": "complete", "skills": []}
        
        results = []
        for skill_name in skills:
            try:
                full_source = f"{owner}/{repo}/{skill_name}"
                result = self.import_skill(full_source, dry_run, force)
                results.append(result)
            except Exception as e:
                print(f"✗ Failed to import {skill_name}: {e}")
                results.append({"status": "error", "skill": skill_name, "error": str(e)})
        
        return {"status": "complete", "results": results}


def main():
    parser = argparse.ArgumentParser(description="Import skills from GitHub repos")
    parser.add_argument("source", help="Source in format owner/repo or owner/repo/skill-name")
    parser.add_argument("--list", action="store_true", help="List skills in repository")
    parser.add_argument("--all", action="store_true", help="Import all skills from repository")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--force", action="store_true", help="Overwrite existing skills")
    parser.add_argument("--dest", help="Custom destination name")
    
    args = parser.parse_args()
    
    importer = SkillImporter()
    
    try:
        if args.list:
            owner, repo, _ = importer.parse_source(args.source)
            skills = importer.list_skills(owner, repo)
            
            if skills:
                print(f"Skills in {owner}/{repo}:")
                for i, skill in enumerate(skills, 1):
                    print(f"  {i}. {skill}")
                print()
                print(f"To import: python3 Skills/skills-importer/scripts/import_skill.py {owner}/{repo}/<skill-name>")
                print(f"To import all: python3 Skills/skills-importer/scripts/import_skill.py {owner}/{repo} --all")
            else:
                print(f"No skills found in {owner}/{repo}")
        
        elif args.all:
            importer.import_all_skills(args.source, args.dry_run, args.force)
        
        else:
            importer.import_skill(args.source, args.dry_run, args.force, args.dest)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()