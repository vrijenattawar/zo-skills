# Hiring POV Generation Prompt

Generate a Hiring POV (Point of View) document analyzing what this employer truly values in candidates.

## Input Context

**Employer:** {{employer_name}}
**Role:** {{role_title}}
**Company Context:** {{company_context}}

## Job Description

{{jd_text}}

## Task

Analyze this JD deeply and extract the employer's true hiring criteria — not just what's stated, but what's implied. Return structured data that helps match candidates effectively.

## Output Schema

Return ONLY a valid JSON object matching this schema:

```json
{
  "explicit_requirements": ["List of stated requirements from the JD"],
  "implicit_filters": ["What the JD is really filtering for — read between the lines"],
  "trait_signals": ["Personality/work style traits they're selecting for"],
  "red_flags": ["What would immediately disqualify a candidate"],
  "story_types_valued": ["What kinds of experiences/stories would resonate most"],
  "validation_questions": ["Questions to ask candidates to validate fit"],
  "culture_markers": ["Cultural signals from the JD language and requirements"],
  "role_summary": "2-3 sentence summary of what this role is really about",
  "missing_info": ["What's unclear or missing from the JD"]
}
```

## Guidelines

- **Explicit requirements**: What they literally wrote (skills, years of experience, etc.)
- **Implicit filters**: The unstated criteria (e.g., "fast-paced" = tolerance for ambiguity)
- **Trait signals**: Behavioral patterns they value (ownership, collaboration, etc.)
- **Red flags**: Deal-breakers based on the JD language
- **Story types**: What experiences prove the right fit (e.g., "0→1 building", "cross-functional leadership")
- **Validation questions**: Specific questions to probe for fit
- **Culture markers**: Language that signals culture ("scrappy", "enterprise", "move fast")
- **Role summary**: The essence of the role in plain language
- **Missing info**: Gaps that need employer clarification

Be specific and insightful. This is for internal use to match candidates effectively.
