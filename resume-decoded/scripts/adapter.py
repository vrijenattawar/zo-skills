#!/usr/bin/env python3
"""
Resume:Decoded Adapter v4.3
Maps decomposer output to template data structure.

Key principles:
- Signal > Verdict: Every claim tied to evidence type
- Bold = Story-verified, Regular = everything else
- Screen count (●) = # of <YOUR_PRODUCT> screens validating capability
- No deficit framing: "More signal needed" not "gap"
- LLM for semantic analysis, Python for structural operations

v4.0 Changes:
- Fixed tenure calculation (reads from experience.positions with duration field)
- Fixed screen count (counts positions with <YOUR_PRODUCT> data)
- Extract behavioral signals from "our_take" narratives
- Use actual culture alignment from alignment.yaml
- Add screen_count per skill (dot indicator)
- Changed "interviews" → "screens"
"""
import json
import yaml
import os
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


# === STRUCTURAL OPERATIONS (Python) ===

def load_yaml_file(path: str) -> Dict:
    """Load YAML file, handling multi-document format."""
    with open(path, 'r') as f:
        docs = list(yaml.safe_load_all(f))
        result = {}
        for doc in docs:
            if doc:
                result.update(doc)
        return result


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime."""
    formats = ["%b %Y", "%B %Y", "%Y-%m", "%Y", "%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def calculate_tenure_years(dates_str: str) -> float:
    """Calculate years from date range string like 'Jan 2024 - May 2025'."""
    if not dates_str:
        return 0.0
    
    parts = dates_str.split(" - ")
    if len(parts) != 2:
        # Try alternate separators
        parts = dates_str.split(" – ")  # en-dash
        if len(parts) != 2:
            parts = dates_str.split("—")  # em-dash
            if len(parts) != 2:
                return 0.0
    
    start_str, end_str = parts[0].strip(), parts[1].strip()
    start = parse_date(start_str)
    if not start:
        return 0.0
    
    if end_str.lower() in ["present", "current", "now", "ongoing"]:
        end = datetime.now()
    else:
        end = parse_date(end_str)
    
    if not end:
        return 0.0
    
    months = (end.year - start.year) * 12 + (end.month - start.month)
    return max(0, months / 12)


def classify_skill_signal(skill: Dict) -> str:
    """
    Classify skill signal strength for display formatting.
    Returns: 'story' | 'resume' | 'none'
    """
    evidence_type = skill.get("evidence_type", "").lower()
    experience_type = skill.get("experience_type", "").lower()
    
    if "story" in evidence_type or experience_type == "direct":
        return "story"
    elif "profile" in evidence_type or "resume" in evidence_type or experience_type == "transferable":
        return "resume"
    else:
        return "none"


def count_support_stories(skill: Dict) -> int:
    """Count the number of supporting stories/screens for a skill."""
    support = skill.get("support", [])
    if isinstance(support, list):
        return len([s for s in support if s.get("source")])
    return 0


def load_decomposer_output(input_dir: str) -> Dict[str, Any]:
    """Load all decomposer output files from a directory."""
    input_path = Path(input_dir)
    
    scores_path = input_path / "scores_complete.json"
    if not scores_path.exists():
        raise FileNotFoundError(f"Required file not found: {scores_path}")
    
    with open(scores_path) as f:
        scores = json.load(f)
    
    def load_optional_yaml(filename: str, default: Dict = None) -> Dict:
        path = input_path / filename
        if path.exists():
            return load_yaml_file(str(path))
        return default or {}
    
    return {
        "scores": scores,
        "overview": load_optional_yaml("overview.yaml"),
        "jd": load_optional_yaml("jd.yaml"),
        "profile": load_optional_yaml("profile.yaml"),
        "experience": load_optional_yaml("experience.yaml"),
        "hard_skills": load_optional_yaml("hard_skills.yaml"),
        "tools": load_optional_yaml("tools.yaml"),
        "alignment": load_optional_yaml("alignment.yaml"),
        "culture_signals": load_optional_yaml("culture_signals.yaml"),
    }


def extract_candidate_name(profile: Dict) -> str:
    """Extract candidate name from profile structure."""
    if "candidate" in profile and "name" in profile["candidate"]:
        return profile["candidate"]["name"]
    elif "name" in profile:
        return profile["name"]
    return "Candidate"


def calculate_tenure(exp: Dict, profile: Dict) -> Tuple[str, str, float]:
    """
    Calculate tenure statistics from experience data.
    Returns: (tenure_summary, trajectory_str, avg_tenure)
    
    v4.0: Fixed to read from experience.positions[] with duration field
    """
    # Primary source: experience.positions[]
    positions = exp.get("positions", [])
    
    total_years = 0.0
    ic_years = 0.0
    lead_years = 0.0
    trajectory = []
    tenures = []
    
    for position in positions:
        # Get duration from the 'duration' field
        duration_str = position.get("duration", "")
        years = calculate_tenure_years(duration_str)
        
        if years > 0:
            tenures.append(years)
            total_years += years
            
            role = position.get("title", "").lower()
            # Lead signals
            if any(kw in role for kw in ["lead", "senior", "principal", "staff", "founding", "architect", "manager", "director", "head", "sde-3", "sde3", "l5", "l6"]):
                lead_years += years
            else:
                ic_years += years
            
            company = position.get("company", "Unknown")
            if company not in trajectory:
                trajectory.append(company)
    
    # Fallback: use years_experience from profile if positions didn't yield data
    if total_years == 0 and profile.get("years_experience"):
        total_years = float(profile.get("years_experience", 0))
        # Assume all IC if we can't determine from positions
        ic_years = total_years
    
    tenure_str = f"{total_years:.1f}y exp · {ic_years:.1f}y IC · {lead_years:.1f}y Lead"
    trajectory_str = " → ".join(trajectory[:4]) if trajectory else ""
    avg_tenure = sum(tenures) / len(tenures) if tenures else 0.0
    
    return tenure_str, trajectory_str, avg_tenure


def count_screens(exp: Dict, scores: Dict) -> int:
    """
    Count the number of <YOUR_PRODUCT> screens the candidate completed.
    
    A screen is evidenced by:
    1. Positions in experience.yaml that have detailed accomplishments
    2. Skills in scores_complete.json with "Story + profile" or "Story" evidence
    
    v4.0: Improved detection based on evidence types
    """
    # Count unique positions with substantial accomplishments
    positions = exp.get("positions", [])
    positions_with_stories = 0
    
    for pos in positions:
        accomplishments = pos.get("key_accomplishments", [])
        # Count as a "screen" if the position has quantified accomplishments
        if any(acc.get("quantified", False) for acc in accomplishments):
            positions_with_stories += 1
    
    # Alternative: count from skill evidence
    skills = scores.get("skills", [])
    story_verified_skills = sum(1 for s in skills if "story" in s.get("evidence_type", "").lower())
    
    # Return max of both signals, minimum 1 if there are any story-verified skills
    if story_verified_skills > 0:
        return max(positions_with_stories, min(story_verified_skills // 10 + 1, 3))  # Cap at 3
    
    return positions_with_stories


def extract_spikes(skills: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Extract upward (strengths) and downward (areas to verify) spikes.
    """
    # Separate by rating
    excellent = [s for s in skills if s.get("rating") == "Excellent"]
    good = [s for s in skills if s.get("rating") == "Good"]
    fair = [s for s in skills if s.get("rating") == "Fair"]
    gap = [s for s in skills if s.get("rating") == "Gap"]
    
    # Sort by importance
    excellent.sort(key=lambda x: x.get("importance", 0), reverse=True)
    good.sort(key=lambda x: x.get("importance", 0), reverse=True)
    fair.sort(key=lambda x: x.get("importance", 0), reverse=True)
    gap.sort(key=lambda x: x.get("importance", 0), reverse=True)
    
    # Upward spikes: top excellent + top good (max 5)
    spikes_up = []
    for s in (excellent + good)[:5]:
        signal = classify_skill_signal(s)
        screen_count = count_support_stories(s)
        spikes_up.append({
            "label": s.get("skill_name", "")[:28],
            "story_verified": signal == "story",
            "screen_count": screen_count,
            "years": "",  # Could calculate from experience if needed
            "bar_width": min(s.get("importance", 5) * 10, 100)
        })
    
    # Downward spikes: fair + gap with high importance (max 3)
    spikes_down = []
    for s in (fair + gap)[:3]:
        spikes_down.append({
            "label": s.get("skill_name", "")[:25],
            "story_verified": False,
            "screen_count": 0,
            "action": "verify depth",
            "bar_width": min(s.get("importance", 5) * 10, 100)
        })
    
    return spikes_up, spikes_down


def generate_probes_structural(skills: List[Dict]) -> List[Dict]:
    """Fallback structural probe generation when LLM unavailable."""
    weak = [s for s in skills if s.get("rating") in ["Fair", "Gap"]]
    weak.sort(key=lambda x: x.get("importance", 0), reverse=True)
    
    return [
        {
            "area": s.get("skill_name", ""),
            "context": f"{classify_skill_signal(s).title()} signal for {s.get('skill_name', '')}.",
            "prompt": f"Ask for specific example demonstrating {s.get('skill_name', '')}.",
            "signal_type": classify_skill_signal(s)
        }
        for s in weak[:4]
    ]


# === LLM-POWERED SEMANTIC ANALYSIS ===

def call_llm(prompt: str) -> str:
    """
    Call /zo/ask API for semantic analysis.
    Returns raw text response.
    """
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        raise RuntimeError("ZO_CLIENT_IDENTITY_TOKEN not set")
    
    response = requests.post(
        "https://api.zo.computer/zo/ask",
        headers={
            "authorization": token,
            "content-type": "application/json"
        },
        json={"input": prompt},
        timeout=60
    )
    
    if response.status_code != 200:
        raise RuntimeError(f"LLM call failed: {response.status_code} - {response.text}")
    
    result = response.json()
    return result.get("output", "")


def parse_json_from_response(text: str) -> Any:
    """Extract and parse JSON from LLM response text."""
    # Try to find JSON in the response
    text = text.strip()
    
    # If wrapped in code block, extract it
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    
    # Try to parse
    return json.loads(text)


def extract_behavioral_signals_from_our_take(skills: List[Dict], exp: Dict = None) -> List[Dict]:
    """
    Extract behavioral signals from "our_take" narratives in skills.
    Uses LLM to identify patterns across the narratives.
    
    v4.1: Improved to extract story CONTEXT for citations, not just paraphrased quotes.
    The citation should frame WHERE/WHEN the behavior happened, not repeat WHAT they did.
    """
    # Gather our_take narratives that have substantial content
    narratives = []
    for skill in skills:
        our_take = skill.get("our_take", "")
        if our_take and len(our_take) > 200:  # Substantial narrative
            narratives.append({
                "skill": skill.get("skill_name", ""),
                "rating": skill.get("rating", ""),
                "our_take": our_take[:1500]  # Limit for prompt size
            })
    
    if not narratives:
        return []
    
    # Get company context from experience
    companies = []
    if exp:
        positions = exp.get("positions", [])
        for pos in positions:
            company = pos.get("company", "")
            summary = pos.get("summary", "")
            if company:
                companies.append(f"{company}: {summary[:100]}" if summary else company)
    
    companies_context = "\n".join(companies[:3]) if companies else "No company context available"
    
    # Take top narratives (by rating quality)
    narratives.sort(key=lambda x: {"Excellent": 3, "Good": 2, "Fair": 1, "Gap": 0}.get(x["rating"], 0), reverse=True)
    top_narratives = narratives[:6]
    
    narratives_text = ""
    for n in top_narratives:
        narratives_text += f"\n--- {n['skill']} ({n['rating']}) ---\n{n['our_take']}\n"
    
    prompt = f"""Analyze these candidate assessment narratives and extract 3-4 distinct BEHAVIORAL patterns.

COMPANIES/ROLES:
{companies_context}

ASSESSMENT NARRATIVES:
{narratives_text}

For EACH pattern, provide:
1. pattern_name: A specific, behavioral title (not generic like "Problem Solver" - more like "Zero-To-One Platform Builder")
2. quote: A SHORT phrase (max 15 words) showing WHAT they did - the specific action
3. story_context: The BROADER CONTEXT of the story - WHERE and WHEN this happened, what was at stake. This should NOT repeat the quote. Examples:
   - "While scaling Embibe's education platform to serve 10M+ learners"
   - "During Quince's critical migration off Shopify to handle $15M/day in transactions"
   - "Building Embibe's Assignment product from initial PoC through production launch"

The quote and story_context together should tell a complete picture:
- Quote = WHAT they did (the action)
- Story_context = WHERE/WHEN/WHY it mattered (the situation and stakes)

Respond with ONLY valid JSON (no other text):
[
  {{"pattern_name": "Specific Behavioral Pattern", "quote": "short action phrase", "story_context": "broader situational context with company and stakes"}}
]"""

    try:
        response = call_llm(prompt)
        patterns = parse_json_from_response(response)
        
        behavioral_signals = []
        seen_patterns = set()
        
        for p in patterns[:4]:
            pattern_name = p.get("pattern_name", "").title()
            if pattern_name.lower() in seen_patterns:
                continue
            seen_patterns.add(pattern_name.lower())
            
            behavioral_signals.append({
                "title": pattern_name,
                "description": "",  # Not used in current template
                "quote": p.get("quote", "")[:100] if p.get("quote") else None,
                "citation": p.get("story_context", "")[:150]  # Story context, not paraphrase
            })
        
        return behavioral_signals
        
    except Exception as e:
        print(f"Warning: LLM behavioral extraction failed: {e}")
        return []


def generate_interview_questions_llm(
    strong_skills: List[Dict],
    weak_skills: List[Dict],
    jd: Dict
) -> Tuple[List[Dict], List[Dict]]:
    """
    Use LLM to generate targeted interview questions.
    """
    jd_title = jd.get("title", "the role")
    responsibilities = jd.get("responsibilities", [])[:5]
    
    strong_summary = "\n".join([
        f"- {s.get('skill_name')}: {s.get('rating')}"
        for s in strong_skills[:3]
    ])
    
    weak_summary = "\n".join([
        f"- {s.get('skill_name')}: {s.get('rating', 'Unknown')} - {classify_skill_signal(s)} signal"
        for s in weak_skills[:4]
    ])
    
    prompt = f"""Identify the most important areas to explore in an interview for a {jd_title} candidate.

RESPONSIBILITIES: {', '.join(responsibilities[:3]) if responsibilities else 'Not specified'}

STRENGTHS (screen-verified):
{strong_summary}

WEAK/UNVERIFIED SIGNALS:
{weak_summary}

For each area, write ONE sentence (max 20 words) explaining why it matters for this role. Be direct and specific. No filler.

RULES:
- Max 20 words per rationale — this is a hard limit
- Use "we" voice (e.g., "Strong signal but depth unverified" not "We flagged this because the Excellent signal...")
- Do NOT start with "We flagged this because" — just state the insight
- No literal interview questions

Generate 2-3 evidence areas (strengths worth exploring deeper) and 3-4 verification areas (weak or unverified signal).

Respond with ONLY valid JSON:
{{
  "evidence_areas": [{{"topic": "X", "rationale": "Strong signal but depth unverified.", "verifies": "Y"}}],
  "verify_areas": [{{"topic": "X", "rationale": "Resume-only signal; no screen evidence.", "verifies": "Y"}}]
}}"""

    try:
        response = call_llm(prompt)
        result = parse_json_from_response(response)
        
        questions_evidence = [
            {"topic": q.get("topic", ""), "rationale": q.get("rationale", ""), "verifies": q.get("verifies", "")}
            for q in result.get("evidence_areas", result.get("evidence_questions", []))[:3]
        ]

        questions_verify = [
            {"topic": q.get("topic", ""), "rationale": q.get("rationale", ""), "verifies": q.get("verifies", "")}
            for q in result.get("verify_areas", result.get("verify_questions", []))[:4]
        ]
        
        return questions_evidence, questions_verify
        
    except Exception as e:
        print(f"Warning: LLM question generation failed: {e}")
        return (
            [{"topic": s.get("skill_name", ""), "rationale": f"We identified strong signal here but want to understand depth and recency.", "verifies": s.get("skill_name", "")} for s in strong_skills[:3]],
            [{"topic": s.get("skill_name", ""), "rationale": f"Signal for this area is unverified — relevant to role requirements but not confirmed in screens.", "verifies": s.get("skill_name", "")} for s in weak_skills[:3]]
        )


def generate_tradeoffs_llm(jd: Dict, skills: List[Dict], overall_score: int) -> List[Dict]:
    """
    Use LLM to generate balanced trade-off analysis.
    """
    responsibilities = jd.get("responsibilities", [])[:6]
    tech_stack = jd.get("tech_stack", [])[:5]
    
    strong = [s for s in skills if s.get("rating") in ["Excellent", "Good"] and classify_skill_signal(s) == "story"]
    weak = [s for s in skills if s.get("rating") in ["Fair", "Gap"]]
    
    prompt = f"""Analyze candidate fit for this role and generate a BALANCED trade-off framework.

JOB: {', '.join(responsibilities[:4]) if responsibilities else 'Backend Engineer'}
TECH: {', '.join(tech_stack) if tech_stack else 'Not specified'}
SCORE: {overall_score}/100

STRONG: {', '.join([s.get('skill_name', '') for s in strong[:5]])}
WEAK/GAP: {', '.join([s.get('skill_name', '') for s in weak[:5]])}

Generate 5-6 trade-offs. Be OBJECTIVE - include at least 2 that are NOT "Strong fit".
Use verdicts: "Strong fit", "Verify in meeting", "More signal needed", "Gap"

Respond with ONLY valid JSON:
[
  {{"need": "requirement", "verdict": "Strong fit|Verify in meeting|More signal needed|Gap", "reason": "brief reason", "verdict_class": "strong|verify|signal-needed|gap"}}
]"""

    try:
        response = call_llm(prompt)
        tradeoffs = parse_json_from_response(response)
        
        for t in tradeoffs:
            verdict_lower = t.get("verdict", "").lower()
            if "strong" in verdict_lower:
                t["verdict_class"] = "strong"
            elif "verify" in verdict_lower:
                t["verdict_class"] = "verify"
            elif "signal" in verdict_lower:
                t["verdict_class"] = "signal-needed"
            else:
                t["verdict_class"] = "gap"
        
        return tradeoffs[:6]
        
    except Exception as e:
        print(f"Warning: LLM tradeoff generation failed: {e}")
        return [{"need": "See detailed assessment", "verdict": "Mixed signal", "reason": "review scores", "verdict_class": "verify"}]


def generate_probes_llm(weak_skills: List[Dict], jd: Dict) -> List[Dict]:
    """
    Use LLM to generate probe areas for weak signals.
    """
    if not weak_skills:
        return []
    
    jd_title = jd.get("title", "the role")
    
    skills_info = "\n".join([
        f"- {s.get('skill_name')}: {s.get('rating', 'Unknown')} rating, {classify_skill_signal(s)} signal"
        for s in weak_skills[:5]
    ])
    
    prompt = f"""For a {jd_title} candidate, generate probe areas for these weak signals:

{skills_info}

Use signal-based language (not deficit language):
- "Resume-only signal" not "Gap"
- "Verify depth" not "Test if they know"

Respond with ONLY valid JSON:
[
  {{"area": "skill name", "context": "1 sentence context", "prompt": "what to ask", "signal_type": "resume|none"}}
]"""

    try:
        response = call_llm(prompt)
        probes = parse_json_from_response(response)
        return probes[:4]
    except Exception as e:
        print(f"Warning: LLM probe generation failed: {e}")
        return [
            {
                "area": s.get("skill_name", ""),
                "context": f"{classify_skill_signal(s).title()} signal for {s.get('skill_name', '')}.",
                "prompt": f"Ask for specific example demonstrating {s.get('skill_name', '')}.",
                "signal_type": classify_skill_signal(s)
            }
            for s in weak_skills[:4]
        ]


def _cap_text(text: str, max_chars: int = 75) -> str:
    """Cut at clean boundary, never trail off or end on a conjunction."""
    text = text.strip()
    bad_endings = ("and", "or", "but", "the", "a", "an", "of", "to", "in", "for", "with")
    if len(text) <= max_chars:
        words = text.split()
        while len(words) > 3 and words[-1].lower().rstrip(",.;:-") in bad_endings:
            words.pop()
        result = " ".join(words).rstrip(" ,;:-")
        return result + "." if not result.endswith(".") else result
    # Prefer cutting at sentence boundary
    cut = text[:max_chars]
    last_period = cut.rfind(".")
    # Also try dash/semicolon as natural break points
    last_dash = max(cut.rfind(" — "), cut.rfind(" - "))
    last_semi = cut.rfind(";")
    best_break = max(last_period, last_dash, last_semi)
    if best_break > 25:
        result = cut[:best_break].rstrip()
        if not result.endswith("."):
            result += "."
        return result
    # Word boundary fallback — strip dangling conjunctions
    trimmed = cut.rsplit(" ", 1)[0]
    bad_endings = ("and", "or", "but", "the", "a", "an", "of", "to", "in", "for", "with")
    while trimmed.split()[-1].lower().rstrip(",.;:-") in bad_endings and len(trimmed.split()) > 3:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return trimmed.rstrip(" ,;:-—") + "."


def generate_culture_alignment(data: Dict[str, Any]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Generate culture alignment signals from alignment.yaml and culture_signals.yaml.

    v4.0: Now uses actual culture alignment data, not skills

    Returns: (culture_match, culture_mismatch, culture_unknown)
    - Match: Culture values where candidate shows strong fit
    - Mismatch: Culture values where there are concerns
    - Unknown: Culture values we can't assess
    """
    alignment = data.get("alignment", {})
    culture_signals = data.get("culture_signals", {})

    # Helper to parse _raw escaped string fields (common in chunked decomposer output)
    def _parse_raw_yaml(obj: dict, label: str) -> dict:
        if "_raw" in obj:
            try:
                import re as _re_raw
                raw_str = obj["_raw"]
                # Strip code fences (```yaml, ```) that break YAML parsing
                raw_str = _re_raw.sub(r'```\w*\n?', '', raw_str).strip()
                # Strip trailing timestamp lines like *2026-02-14 12:40 PM ET*
                raw_str = _re_raw.sub(r'\n\s*\*[\d\-:/ ,\w]+\*\s*$', '', raw_str).strip()
                # Strip YAML document separators (---) that cause multi-doc errors
                raw_str = _re_raw.sub(r'\n---\s*$', '', raw_str, flags=_re_raw.MULTILINE).strip()
                parsed = yaml.safe_load(raw_str)
                if isinstance(parsed, dict):
                    return parsed
            except Exception as e:
                print(f"  Warning: Could not parse {label}._raw: {e}")
        return obj

    # Parse _raw for both alignment and culture_signals
    if "_raw" in alignment and not alignment.get("culture_alignment"):
        alignment = _parse_raw_yaml(alignment, "alignment")
    if "_raw" in culture_signals and not culture_signals.get("explicit_values"):
        culture_signals = _parse_raw_yaml(culture_signals, "culture_signals")
    
    culture_match = []
    culture_mismatch = []
    culture_unknown = []
    
    # Transform culture value names to noun phrases
    def transform_culture_title(title: str) -> str:
        """Convert long culture signal descriptions to short display names."""
        # Static transforms for common patterns
        transforms = {
            "act like an owner": "Ownership Mentality",
            "build together": "Collaborative Mindset",
            "drive innovation": "Drive for Innovation",
            "champion clients": "Client Centricity",
            "embrace learning": "Learning Orientation",
            "move fast": "Bias for Action",
            "think big": "Ambitious Vision",
            "be curious": "Intellectual Curiosity",
            "take risks": "Risk Tolerance",
            "stay humble": "Humility",
            "be transparent": "Transparency",
            "deliver results": "Results Orientation",
        }
        lower = title.lower().strip()
        if lower in transforms:
            return transforms[lower]

        # Keyword-based shortening for longer signals
        keyword_map = [
            (["remote", "async"], "Remote/Async Culture"),
            (["ownership", "shipping", "bias"], "Ownership & Shipping"),
            (["ownership"], "Ownership Mentality"),
            (["shipping", "perfection"], "Ship Over Perfect"),
            (["shipping", "incremental"], "Incremental Shipping"),
            (["written", "communication"], "Written Communication"),
            (["communication"], "Communication Style"),
            (["informal", "personality"], "Informal Culture Fit"),
            (["ambiguity", "comfort"], "Comfort with Ambiguity"),
            (["collaboration", "team"], "Team Collaboration"),
            (["autonomy", "independent"], "Autonomy & Independence"),
            (["feedback", "open"], "Open Feedback Culture"),
            (["innovation", "experiment"], "Innovation Mindset"),
        ]
        for keywords, short_name in keyword_map:
            if all(kw in lower for kw in keywords):
                return short_name

        # Fallback: truncate at word boundary, strip dangling function words
        if len(title) > 25:
            trimmed = title[:25].rsplit(" ", 1)[0]
            dangling = {"that", "the", "a", "an", "and", "or", "but", "of", "to", "in", "for", "with", "is", "are"}
            while trimmed.split()[-1].lower() in dangling and len(trimmed.split()) > 2:
                trimmed = trimmed.rsplit(" ", 1)[0]
            return trimmed
        return title
    
    # Primary source: culture_alignment from alignment.yaml
    culture_alignment = alignment.get("culture_alignment", [])
    
    for item in culture_alignment:
        signal = item.get("signal", "")
        fit = item.get("candidate_fit", "unknown").lower()
        evidence = item.get("evidence", "")
        
        # Extract short name from signal (often "Value Name: description")
        if ":" in signal:
            raw_name = signal.split(":")[0].strip()
        elif " — " in signal:
            raw_name = signal.split(" — ")[0].strip()
        else:
            # Truncate at word boundary, max 30 chars
            raw_name = signal[:30].rsplit(" ", 1)[0] if len(signal) > 30 else signal
        short_name = transform_culture_title(raw_name)
        
        # Truncate evidence cleanly — tighter limit for small culture font
        note = _cap_text(evidence, 60)

        entry = {
            "name": short_name,
            "note": note
        }
        
        if fit == "strong":
            culture_match.append(entry)
        elif fit in ["weak", "gap", "mismatch"]:
            culture_mismatch.append(entry)
        else:  # moderate, unknown
            culture_unknown.append(entry)
    
    # If no culture alignment found, fall back to deriving from explicit_values
    if not culture_alignment and culture_signals.get("explicit_values"):
        for value in culture_signals.get("explicit_values", [])[:5]:
            raw_name = value.get("name", "")[:30]
            culture_unknown.append({
                "name": transform_culture_title(raw_name),
                "note": "Not yet assessed"
            })
    
    return culture_match[:5], culture_mismatch[:5], culture_unknown[:5]


def enhance_bottom_line_with_screening_attribution(
    raw_bottom_line: str,
    overall_score: int,
    role_title: str,
    behavioral_signals: List[Dict],
    strong_skills: List[Dict]
) -> str:
    """Generate a tight, source-bound bottom line in V's required format (v4.3)."""
    quality = "strong" if overall_score >= 80 else "conditional" if overall_score >= 60 else "weak"

    # Build evidence from behavioral signals and strong skills
    evidence_lines: List[str] = []

    for sig in (behavioral_signals or [])[:3]:
        title = (sig.get("title") or "").strip()
        quote = (sig.get("quote") or "").strip()
        if title and quote:
            evidence_lines.append(f"- {title}: \"{quote}\"")
        elif title:
            evidence_lines.append(f"- {title}")

    for s in sorted(strong_skills or [], key=lambda x: x.get("importance", 0), reverse=True)[:3]:
        name = (s.get("skill_name") or "").strip()
        our_take = (s.get("our_take") or "").strip()
        if name and our_take:
            first_sentence = our_take.split(". ")[0] if ". " in our_take else our_take[:100]
            evidence_lines.append(f"- {name}: {first_sentence}")

    evidence_block = "\n".join(evidence_lines) if evidence_lines else "(no evidence provided)"

    prompt = f"""Write 2-3 sentences summarizing this candidate for a hiring manager.

EXACT FORMAT:
"This {{3-4 word descriptor}} is a {quality} fit based on our screens because {{differentiator}}. {{1-2 supporting sentences with specific evidence}}."

RULES:
- Use "we" and "our" (collective voice from the screening team), never "my" or "I"
- Descriptor: 3-4 words capturing their professional identity (e.g., "zero-to-one backend architect", "platform migration specialist")
- Differentiator: what makes them worth meeting, drawn ONLY from EVIDENCE below
- Use "who has" phrasing, never "they" or "he/she"
- Total length: 2-3 complete sentences, 150-250 characters
- Must NOT mention <YOUR_PRODUCT>, screen count, or numbers
- Must NOT restate job requirements
- Every sentence must end with a period — no trailing off

EVIDENCE:
{evidence_block}

Return ONLY the 2-3 sentences (no quotes, no bullets, no commentary)."""

    try:
        response = call_llm(prompt)
        text = " ".join(response.strip().strip('"').strip("'").split())

        if not text.lower().startswith("this "):
            raise ValueError("Bottom line did not start with 'This'")
        if "<YOUR_PRODUCT>" in text.lower():
            raise ValueError("Bottom line mentioned <YOUR_PRODUCT>")

        # Strip parenthetical numeric claims to reduce drift
        import re
        text = re.sub(r"\([^)]*\d[^)]*\)", "", text)
        text = " ".join(text.split())

        # If still contains numbers or currency markers, fail to fallback
        if re.search(r"\d|\$", text):
            raise ValueError("Bottom line contained numbers")

        # Ensure text ends with a period (no trailing off)
        if not text.rstrip().endswith("."):
            # Find last complete sentence
            last_period = text.rfind(".")
            if last_period > 50:
                text = text[:last_period + 1]
            else:
                text = text.rstrip(" ,;:-") + "."

        if len(text) > 300:
            # Cut at last complete sentence within limit
            cut = text[:280]
            last_period = cut.rfind(".")
            if last_period > 80:
                text = cut[:last_period + 1]
            else:
                text = cut.rsplit(" ", 1)[0].rstrip(" ,;:-") + "."

        # Enforce "we/our" voice — LLM sometimes reverts to "my"
        text = text.replace("my screens", "our screens").replace("My screens", "Our screens")
        text = text.replace("based on my ", "based on our ").replace("Based on my ", "Based on our ")

        return text

    except Exception as e:
        print(f"Warning: LLM bottom line enhancement failed: {e}")

        # Structural fallback using top story-verified strong skills
        role_lower = (role_title or "").lower()
        if "backend" in role_lower and ("senior" in role_lower or "sr" in role_lower):
            fallback_descriptor = "senior backend engineer"
        elif "backend" in role_lower:
            fallback_descriptor = "backend engineer"
        elif "frontend" in role_lower:
            fallback_descriptor = "frontend engineer"
        else:
            fallback_descriptor = "software engineer"

        top = []
        for s in sorted(strong_skills or [], key=lambda x: x.get("importance", 0), reverse=True):
            if s.get("rating") in ["Excellent", "Good"] and classify_skill_signal(s) == "story":
                n = (s.get("skill_name") or "").strip()
                if n:
                    top.append(n.lower())
            if len(top) >= 2:
                break

        if len(top) >= 2:
            evidence = f"screens show strength in {top[0]} and {top[1]}"
        elif len(top) == 1:
            evidence = f"screens show strength in {top[0]}"
        else:
            evidence = "screens show relevant execution patterns"

        return f"This {fallback_descriptor} is a {quality} fit based on our screens because {evidence}."


# === MAIN MAPPING FUNCTION ===

def map_to_template_data(data: Dict[str, Any], use_llm: bool = True) -> Dict:
    """
    Map decomposer output to template data structure.
    
    Args:
        data: Loaded decomposer output
        use_llm: Whether to use LLM for semantic analysis (default True)
    """
    scores = data["scores"]
    overview = data.get("overview", {})
    jd = data.get("jd", {})
    profile = data.get("profile", {})
    exp = data.get("experience", {})
    
    # === STRUCTURAL: Extract basic info ===
    candidate_name = extract_candidate_name(profile)
    skills = scores.get("skills", [])
    
    # Calculate tenure (v4.0: fixed to read from positions)
    tenure_summary, trajectory, avg_tenure = calculate_tenure(exp, profile)
    
    # Count screens (v4.0: improved detection)
    screens_count = count_screens(exp, scores)
    
    # Extract spikes
    spikes_up, spikes_down = extract_spikes(skills)
    
    # === LLM-POWERED SEMANTIC ANALYSIS ===
    # Filter skills for LLM calls
    strong_skills = [s for s in skills if s.get("rating") in ["Excellent", "Good"]]
    weak_skills = [s for s in skills if s.get("rating") in ["Fair", "Gap"]]
    overall_score = scores.get("overall_score", 0)
    
    # Extract "why signal is strong" from top-rated skills with good our_take
    why_signal = []
    for skill in sorted(strong_skills, key=lambda x: x.get("importance", 0), reverse=True)[:3]:
        our_take = skill.get("our_take", "")
        if our_take and len(our_take) > 100:
            # Extract first meaningful sentence
            first_sentence = our_take.split(". ")[0] if ". " in our_take else our_take[:150]
            why_signal.append({
                "title": skill.get("skill_name", "")[:45],
                "story": first_sentence[:180] + "..." if len(first_sentence) > 180 else first_sentence,
                "story_verified": True,
                "screen_count": count_support_stories(skill)
            })
    
    if use_llm:
        print("  Running LLM analysis for behavioral signals...")
        behavioral_signals = extract_behavioral_signals_from_our_take(skills, exp)
        
        print("  Running LLM analysis for interview questions...")
        questions_evidence, questions_verify = generate_interview_questions_llm(strong_skills, weak_skills, jd)
        
        print("  Running LLM analysis for trade-offs...")
        tradeoffs = generate_tradeoffs_llm(jd, skills, overall_score)
        
        print("  Running LLM analysis for probes...")
        probes = generate_probes_llm(weak_skills, jd)
        
        print("  Extracting culture alignment...")
        culture_match, culture_mismatch, culture_unknown = generate_culture_alignment(data)
        
        print("  Enhancing bottom line...")
        jd_title_for_bl = jd.get("title", "")
        enhanced_bottom_line = enhance_bottom_line_with_screening_attribution(
            scores.get("bottom_line", ""),
            overall_score,
            jd_title_for_bl,
            behavioral_signals,
            strong_skills
        )
    else:
        # Fallback to structural extraction
        behavioral_signals = []
        questions_evidence = []
        questions_verify = []
        tradeoffs = []
        probes = generate_probes_structural(skills)
        culture_match = []
        culture_mismatch = []
        culture_unknown = []
        enhanced_bottom_line = scores.get("bottom_line", "")
    
    # Limit behavioral signals to 4 for 2x2 grid
    behavioral_signals = behavioral_signals[:4]
    
    # Dedup: remove questions whose topic overlaps with strong-fit tradeoff needs
    _STOPWORDS = {'', 'and', 'the', 'a', 'of', 'for', 'in', 'to', 'with', 'on', 'at'}
    def _tokenize(text: str) -> set:
        return set(text.lower().split()) - _STOPWORDS

    strong_fit_tokens = []
    for t in tradeoffs:
        if t.get("verdict_class") == "strong":
            strong_fit_tokens.append(_tokenize(t.get("need", "")))

    def topic_overlaps_strong_fit(topic: str) -> bool:
        topic_words = _tokenize(topic)
        if not topic_words:
            return False
        for need_words in strong_fit_tokens:
            overlap = topic_words & need_words
            compound_matches = sum(1 for w in overlap if '-' in w)
            effective_overlap = len(overlap) + compound_matches
            if effective_overlap >= 2 or (len(overlap) >= 1 and min(len(topic_words), len(need_words)) <= 2):
                return True
        return False

    questions_evidence = [q for q in questions_evidence if not topic_overlaps_strong_fit(q.get("topic", ""))]
    questions_verify = [q for q in questions_verify if not topic_overlaps_strong_fit(q.get("topic", ""))]

    # Build combined areas list (limit to 6 for 3-column grid)
    questions_all = []
    for q in questions_evidence[:3]:
        questions_all.append({
            "topic": q.get("topic", ""),
            "rationale": _cap_text(q.get("rationale", ""), 90),
        })
    for q in questions_verify[:3]:
        questions_all.append({
            "topic": q.get("topic", ""),
            "rationale": _cap_text(q.get("rationale", ""), 90),
        })
    
    # Handle tenure warning - add to probes if low tenure
    if avg_tenure < 2.5 and avg_tenure > 0:
        tenure_probe = {
            "area": "Retention signal",
            "context": f"{avg_tenure:.1f}y average tenure across roles. For a founding role, understanding what drives long-term engagement is critical.",
            "prompt": "What conditions have kept you at a company longest? What would make you stay 3+ years here?",
            "signal_type": "inferred"
        }
        probes = [tenure_probe] + probes[:3]  # Tenure first, then top 3 probes
    else:
        probes = probes[:4]  # Just top 4 probes
    
    # Get dealbreakers (real ones only, not "none identified")
    dealbreakers = scores.get("potential_dealbreakers", [])
    dealbreakers = [d for d in dealbreakers if d and d.lower() not in ["none", "none identified", "n/a", ""]]
    
    # Signal strength
    signal = scores.get("signal_strength", {})
    signal_story = int(signal.get("story_verified_pct", 0))
    signal_resume = int(signal.get("resume_only_pct", 0))
    signal_inferred = int(signal.get("inferred_pct", 0))
    # Ensure bars sum to 100%
    signal_total = signal_story + signal_resume + signal_inferred
    if signal_total > 0 and signal_total != 100:
        signal_resume = 100 - signal_story - signal_inferred
    
    # Calculate skills count from the full skills list
    all_skills = scores.get("skills", [])
    skills_count = len(all_skills)
    
    # Overall assessment
    overall_score = scores.get("overall_score", 0)
    if overall_score >= 80:
        verdict = "Take This Meeting"
        verdict_emoji = "👍"
    elif overall_score >= 60:
        verdict = "Proceed with Caution"
        verdict_emoji = "🤔"
    else:
        verdict = "Pass"
        verdict_emoji = "👎"
    
    # Extract JD info - handle nested raw_jd structure
    jd_raw = jd.get("raw_jd", "")
    jd_title = "Role"
    jd_company = "Company"
    
    # Try to parse YAML from raw_jd if it exists
    if jd_raw:
        try:
            jd_text = jd_raw.strip()
            if jd_text.startswith("---"):
                parts = jd_text.split("---", 2)
                if len(parts) >= 3:
                    jd_text = parts[2].strip()
            
            jd_parsed = yaml.safe_load(jd_text)
            if isinstance(jd_parsed, dict):
                jd_title = jd_parsed.get("title", jd_title)
                jd_company = jd_parsed.get("company", jd_company)
        except Exception as e:
            print(f"  Warning: Could not parse JD as YAML: {e}")
        
        # Fallback: extract from markdown headings if still defaults
        import re as _re
        if jd_title == "Role":
            # Pattern: "# Title — Company" or "# Title - Company"
            m = _re.search(r'^#\s+(.+?)\s*[—\-–]\s*(.+)$', jd_raw, _re.MULTILINE)
            if m:
                jd_title = m.group(1).strip()
                jd_company = m.group(2).strip()
            else:
                # Pattern: just "# Title" on first heading
                m = _re.search(r'^#\s+(.+)$', jd_raw, _re.MULTILINE)
                if m:
                    jd_title = m.group(1).strip()
        
        if jd_company == "Company":
            # Pattern: "## Company\n\nCompanyName"
            m = _re.search(r'##\s+Company\s*\n+\s*(\S.+?)$', jd_raw, _re.MULTILINE)
            if m:
                jd_company = m.group(1).strip()
    
    # Also check direct jd fields (fallback)
    if jd.get("title"):
        jd_title = jd.get("title")
    if jd.get("company"):
        jd_company = jd.get("company")
    
    return {
        "candidate_name": candidate_name,
        "role": jd_title,
        "partner": "<YOUR_PARTNER>",
        "company": jd_company,
        "date": datetime.now().strftime("%b %Y"),
        "tenure_summary": tenure_summary,
        "trajectory": trajectory,
        "verdict_emoji": verdict_emoji,
        "verdict": verdict,
        "confidence_score": overall_score,
        "verdict_summary": enhanced_bottom_line,
        "signal_story": signal_story,
        "signal_resume": signal_resume,
        "signal_inferred": signal_inferred,
        "skills_assessed": skills_count,
        "screens_count": screens_count,  # v4.0: renamed from interviews_count
        "spikes_up": spikes_up,
        "spikes_down": spikes_down,
        "dealbreakers": dealbreakers,
        "probes": probes,
        "why_signal": why_signal,
        "behavioral_signals": behavioral_signals,
        "questions_evidence": questions_evidence,
        "questions_verify": questions_verify,
        "questions_all": questions_all,
        "tradeoffs": tradeoffs,
        "culture_match": culture_match,
        "culture_mismatch": culture_mismatch,
        "culture_unknown": culture_unknown
    }


def validate_template_data(data: Dict) -> Tuple[bool, List[str]]:
    """Validate template data has required fields."""
    warnings = []
    
    required = ["candidate_name", "role", "company", "verdict", "confidence_score", "verdict_summary"]
    for field in required:
        if not data.get(field):
            warnings.append(f"Missing required field: {field}")
    
    # Check for data quality issues that should trigger alerts
    if data.get("tenure_summary", "").startswith("0.0y"):
        warnings.append("⚠️ Tenure calculation returned 0.0y - check experience.yaml has positions with duration")
    
    if not data.get("spikes_up"):
        warnings.append("No upward spikes (strengths) identified")
    
    if not data.get("behavioral_signals"):
        warnings.append("No behavioral signals extracted")
    
    if not data.get("why_signal"):
        warnings.append("No 'why signal is strong' entries")
    
    if not data.get("tradeoffs"):
        warnings.append("No trade-offs generated")
    
    is_valid = not any("required" in w.lower() for w in warnings)
    return is_valid, warnings


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python adapter.py <decomposer_output_dir> [output.json]")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"Loading decomposer output from: {input_dir}")
    data = load_decomposer_output(input_dir)
    
    print("Mapping to template data (with LLM analysis)...")
    template_data = map_to_template_data(data)
    
    print("Validating...")
    is_valid, warnings = validate_template_data(template_data)
    
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  ⚠ {w}")
    
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(template_data, f, indent=2)
        print(f"\n✓ Template data saved to: {output_path}")
    else:
        print("\nTemplate data preview:")
        print(json.dumps(template_data, indent=2)[:2000] + "...")
    
    if is_valid:
        print("\n✓ Validation passed")
    else:
        print("\n✗ Validation failed")
        sys.exit(1)
