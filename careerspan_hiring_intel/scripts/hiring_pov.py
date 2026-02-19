#!/usr/bin/env python3
"""
Canonical Hiring POV Generator
------------------------------
Shared module for generating Hiring POVs across all <YOUR_PRODUCT> skills.
Ensures consistent input/output schema regardless of calling context.

Used by:
- <YOUR_PRODUCT>-jd-intake: Primary POV generation when JDs come in
- candidate-synthesis: Fallback when POV doesn't exist for a candidate
- Any future skills requiring POV generation
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

import requests


# Default output schema for structured POV data
HIRING_POV_SCHEMA = {
    "type": "object",
    "properties": {
        "explicit_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Stated requirements from the JD"
        },
        "implicit_filters": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Unstated criteria inferred from JD language"
        },
        "trait_signals": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Personality/work style traits being selected for"
        },
        "red_flags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Deal-breakers that would disqualify candidates"
        },
        "story_types_valued": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Types of experiences that prove fit"
        },
        "validation_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Questions to validate candidate fit"
        },
        "culture_markers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Cultural signals from JD language"
        },
        "role_summary": {
            "type": "string",
            "description": "2-3 sentence essence of the role"
        },
        "missing_info": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Gaps or unclear information in the JD"
        }
    },
    "required": [
        "explicit_requirements",
        "implicit_filters",
        "trait_signals",
        "red_flags",
        "story_types_valued",
        "role_summary"
    ]
}


def load_prompt_template() -> str:
    """Load the canonical Hiring POV generation prompt template."""
    prompt_path = Path(__file__).parent.parent / "assets" / "prompts" / "hiring_pov_generation.md"
    return prompt_path.read_text()


def call_zo_ask(prompt: str, output_schema: Optional[dict] = None, timeout: int = 120) -> dict:
    """
    Call /zo/ask API for LLM inference.
    
    Args:
        prompt: The prompt text to send
        output_schema: Optional JSON schema for structured output
        timeout: Request timeout in seconds
        
    Returns:
        Parsed response (dict if schema provided, else string)
    """
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        raise RuntimeError("ZO_CLIENT_IDENTITY_TOKEN environment variable not set")
    
    payload = {"input": prompt}
    if output_schema:
        payload["output_format"] = output_schema
    
    response = requests.post(
        "https://api.zo.computer/zo/ask",
        headers={
            "authorization": token,
            "content-type": "application/json"
        },
        json=payload,
        timeout=timeout
    )
    response.raise_for_status()
    
    result = response.json()
    output = result.get("output", "")
    
    # If schema was provided, ensure we return a dict
    if output_schema:
        if isinstance(output, dict):
            return output
        # Try to parse JSON from text response
        try:
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        # Return raw in error field if parsing fails
        return {"_error": "Failed to parse structured output", "_raw": output}
    
    return output


def generate_hiring_pov(
    jd_text: str,
    employer_name: str,
    role_title: str,
    company_context: str = "",
    max_jd_length: int = 8000
) -> dict:
    """
    Generate a structured Hiring POV from job description text.
    
    This is the canonical function used across all <YOUR_PRODUCT> skills.
    
    Args:
        jd_text: The full job description text
        employer_name: Company/employer name
        role_title: Role/position title
        company_context: Optional additional context about the company
        max_jd_length: Max characters of JD to include (truncates if longer)
        
    Returns:
        Structured Hiring POV dict matching HIRING_POV_SCHEMA
    """
    prompt_template = load_prompt_template()
    
    # Truncate JD if too long
    truncated_jd = jd_text[:max_jd_length]
    if len(jd_text) > max_jd_length:
        truncated_jd += "\n\n[JD truncated due to length]"
    
    # Fill in template
    prompt = prompt_template.replace("{{employer_name}}", employer_name)
    prompt = prompt.replace("{{role_title}}", role_title)
    prompt = prompt.replace("{{company_context}}", company_context or "No additional context provided.")
    prompt = prompt.replace("{{jd_text}}", truncated_jd)
    
    # Call LLM with structured output
    result = call_zo_ask(prompt, output_schema=HIRING_POV_SCHEMA)
    
    # Ensure all required fields exist (correct types)
    props = HIRING_POV_SCHEMA.get("properties", {})
    for field in HIRING_POV_SCHEMA["required"]:
        if field in result:
            continue
        field_type = (props.get(field) or {}).get("type")
        if field_type == "array":
            result[field] = []
        else:
            result[field] = ""
    
    # Add metadata
    result["_meta"] = {
        "employer_name": employer_name,
        "role_title": role_title,
        "source": "<YOUR_PRODUCT>_hiring_intel.scripts.hiring_pov.generate_hiring_pov",
        "jd_length": len(jd_text)
    }
    
    return result


def format_pov_markdown(pov: dict, employer_name: str, role_title: str) -> str:
    """
    Format a structured Hiring POV as markdown for storage/display.
    
    Args:
        pov: Structured POV dict from generate_hiring_pov()
        employer_name: Company/employer name
        role_title: Role/position title
        
    Returns:
        Markdown-formatted Hiring POV document
    """
    from datetime import datetime
    
    def list_to_bullets(items: list) -> str:
        if not items:
            return "- *None specified*"
        return "\n".join(f"- {item}" for item in items)
    
    md = f"""# Hiring POV: {role_title} @ {employer_name}

## Role Overview
{pov.get('role_summary', '*No summary generated*')}

## Explicit Requirements
{list_to_bullets(pov.get('explicit_requirements', []))}

## Implicit Filters
{list_to_bullets(pov.get('implicit_filters', []))}

## Trait Signals
{list_to_bullets(pov.get('trait_signals', []))}

## Red Flags
{list_to_bullets(pov.get('red_flags', []))}

## Story Types Valued
{list_to_bullets(pov.get('story_types_valued', []))}

## Validation Questions
{list_to_bullets(pov.get('validation_questions', []))}

## Culture Markers
{list_to_bullets(pov.get('culture_markers', []))}

## Missing Information
{list_to_bullets(pov.get('missing_info', []))}

---
*Generated by Zo for <YOUR_PRODUCT> pipeline*
*{datetime.now().strftime('%Y-%m-%d %H:%M')} ET*
"""
    return md


def generate_hiring_pov_with_markdown(
    jd_text: str,
    employer_name: str,
    role_title: str,
    company_context: str = "",
    max_jd_length: int = 8000
) -> tuple[dict, str]:
    """
    Generate both structured POV and markdown in one call.
    
    Args:
        jd_text: The full job description text
        employer_name: Company/employer name
        role_title: Role/position title
        company_context: Optional additional context
        max_jd_length: Max characters of JD to include
        
    Returns:
        Tuple of (structured_pov_dict, markdown_string)
    """
    pov = generate_hiring_pov(jd_text, employer_name, role_title, company_context, max_jd_length)
    markdown = format_pov_markdown(pov, employer_name, role_title)
    return pov, markdown


# CLI for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate Hiring POV from JD text")
    parser.add_argument("--jd-file", required=True, help="Path to file containing JD text")
    parser.add_argument("--employer", required=True, help="Employer/company name")
    parser.add_argument("--role", required=True, help="Role/position title")
    parser.add_argument("--context", default="", help="Optional company context")
    parser.add_argument("--output-json", help="Path to save structured JSON output")
    parser.add_argument("--output-md", help="Path to save markdown output")
    
    args = parser.parse_args()
    
    # Read JD
    jd_text = Path(args.jd_file).read_text()
    
    # Generate
    print(f"Generating Hiring POV for {args.role} @ {args.employer}...")
    pov, markdown = generate_hiring_pov_with_markdown(
        jd_text=jd_text,
        employer_name=args.employer,
        role_title=args.role,
        company_context=args.context
    )
    
    # Save outputs
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(pov, indent=2))
        print(f"Structured POV saved to: {args.output_json}")
    
    if args.output_md:
        Path(args.output_md).write_text(markdown)
        print(f"Markdown POV saved to: {args.output_md}")
    
    # Also print markdown to stdout
    print("\n" + "=" * 60)
    print("GENERATED HIRING POV")
    print("=" * 60)
    print(markdown)
