#!/usr/bin/env python3
"""
Resume:Decoded Generator
Generates 2-page signal-based candidate briefs using branded-pdf skill.
"""
import argparse
import sys
from pathlib import Path

# Add branded-pdf to path
sys.path.insert(0, str(Path('./Skills/branded-pdf/scripts')))

from adapter import load_decomposer_output, map_to_resume_decoded


def make_bar(percentage: int, width: int = 20) -> str:
    """Create ASCII bar for signal strength."""
    filled = int((percentage / 100) * width)
    return '█' * filled + '░' * (width - filled)


def generate_markdown(resume_data: dict) -> str:
    """Generate branded-pdf compatible markdown."""
    
    md = f"""# {resume_data['candidate_name']}
## {resume_data['candidate_role']}

{resume_data['tenure']['total_years']}y exp · {resume_data['tenure']['ic_years']}y IC · {resume_data['tenure']['management_years']}y Lead · {resume_data['tenure']['trajectory']} trajectory
{resume_data['company_progression']}

---

## At A Glance
*[bold = story-verified · italic = more signal needed]*

### Upward Signals
"""
    
    # Up spikes
    for spike in resume_data['spikes_up']:
        bar = make_bar(80)  # Importance visual
        md += f"▲ {spike}\n{bar}\n\n"
    
    md += "\n### Areas to Verify\n"
    
    # Down spikes
    for spike in resume_data['spikes_down']:
        bar = make_bar(40)
        md += f"▼ {spike}\n{bar} [more signal needed]\n\n"
    
    md += f"""
---

## Verdict

### {'👍' if resume_data['confidence_score'] >= 70 else '🤔'} TAKE THIS MEETING — {resume_data['confidence_score']}/100

{resume_data['verdict']}

"""
    
    # Dealbreakers section (conditional)
    if resume_data['dealbreakers']:
        md += "**Dealbreakers to Verify:**\n"
        for db in resume_data['dealbreakers']:
            md += f"- {db}\n"
        md += "\n"
    
    md += f"""---

## What to Verify

### Areas Requiring More Signal

"""
    
    # Questions become areas to verify
    for q in resume_data['questions'][:4]:
        signal_type = q.get('signal_type', 'missing')
        prefix = "**" if signal_type == 'low' else "*"
        suffix = "**" if signal_type == 'low' else "*"
        md += f"- {prefix}{q['topic']}{suffix}: {q['question']}\n"
    
    md += f"""
---

## Why The Signal Is Strong

{resume_data['overall_strengths']}

---

## Signal Composition

{make_bar(resume_data['signal_strength']['story_verified'])} {resume_data['signal_strength']['story_verified']}% story-verified

{make_bar(resume_data['signal_strength']['resume_only'])} {resume_data['signal_strength']['resume_only']}% resume-backed

{make_bar(resume_data['signal_strength']['inferred'])} {resume_data['signal_strength']['inferred']}% inferred

{resume_data['skills_assessed']} skills assessed · {resume_data['interviews_count']} structured interviews · {resume_data['date']}

---

## Behavioral Evidence

"""
    
    for signal in resume_data['behavioral_signals']:
        md += f"**{signal['title']}**\n"
        md += f"{signal['description']}\n"
        if signal.get('quote'):
            md += f'\n> "{signal["quote"]}"\n'
            md += f"> — {signal.get('source', 'Interview')}\n"
        md += "\n"
    
    md += f"""---

## Questions That Matter

"""
    
    for q in resume_data['questions']:
        md += f"**{q['topic']}**\n"
        md += f"→ {q['question']}\n"
        md += f"(Verifies: {q['verifies']})\n\n"
    
    md += f"""---

## Your Priorities → Fit

| If You Need | Then He Is |
|-------------|------------|
"""
    
    # Generate trade-offs from strengths/weaknesses
    md += f"| Founding engineer with 0→1 experience | **Strong fit** — proven at Keysight, AmEx |\n"
    md += f"| Rapid MVP iteration | *Verify in meeting* — enterprise rigor may need calibration |\n"
    md += f"| Deep Node.js expertise | *More signal needed* — Java/Python background |\n"
    
    if resume_data['tenure']['avg_tenure'] < 3:
        md += f"| Long-tenure team anchor | *Verify in meeting* — {resume_data['tenure']['avg_tenure']:.1f}y avg tenure |\n"
    
    md += f"""
---

*Resume:Decoded by <YOUR_PRODUCT> × <YOUR_PARTNER> · {resume_data['company_name']} · {resume_data['date']}*
"""
    
    return md


def main():
    parser = argparse.ArgumentParser(description='Generate Resume:Decoded PDF')
    parser.add_argument('--input', required=True, help='Decomposer output directory')
    parser.add_argument('--output', required=True, help='Output directory for PDF')
    args = parser.parse_args()
    
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Loading decomposer output from: {input_dir}")
    data = load_decomposer_output(input_dir)
    
    print("Mapping to Resume:Decoded format...")
    resume_data = map_to_resume_decoded(data)
    
    # Generate markdown
    md_content = generate_markdown(resume_data)
    candidate_slug = resume_data['candidate_name'].lower().replace(' ', '-')
    md_path = output_dir / f"{candidate_slug}-decoded.md"
    
    with open(md_path, 'w') as f:
        f.write(md_content)
    print(f"✓ Markdown saved: {md_path}")
    
    # Generate PDF using branded-pdf
    pdf_path = output_dir / f"{candidate_slug}-decoded.pdf"
    
    try:
        from generate_pdf import generate_pdf
        
        generate_pdf(
            input_path=str(md_path),
            output_path=str(pdf_path),
            title=f"Resume:Decoded — {resume_data['candidate_name']}",
            subtitle=f"{resume_data['company_name']} · {resume_data['confidence_score']}/100"
        )
        print(f"✓ PDF generated: {pdf_path}")
        
    except Exception as e:
        print(f"⚠ PDF generation failed: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n  Markdown is ready at: {md_path}")
        print(f"  You can generate PDF manually with:")
        print(f"    python3 Skills/branded-pdf/scripts/generate_pdf.py --input {md_path} --output {pdf_path}")


if __name__ == '__main__':
    main()
