#!/usr/bin/env python3
"""
Resume:Decoded Generator v2 (Puppeteer-based)
Decomposer output → JSON → PDF with exact layout control
"""

import json
import subprocess
import sys
from pathlib import Path

# Import adapter functions
sys.path.insert(0, str(Path(__file__).parent))
from adapter import load_decomposer_output, map_to_template_data

def generate_pdf(input_dir: str, output_dir: str) -> str:
    """Generate PDF from decomposer output"""
    
    # Load and map data
    print(f"Loading decomposer output from: {input_dir}")
    data = load_decomposer_output(input_dir)
    template_data = map_to_template_data(data)
    
    # Save JSON for renderer
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    candidate_name = template_data['candidate_name'].lower().replace(' ', '-')
    json_path = output_path / f"{candidate_name}-data.json"
    pdf_path = output_path / f"{candidate_name}-decoded.pdf"
    
    with open(json_path, 'w') as f:
        json.dump(template_data, f, indent=2)
    print(f"JSON saved: {json_path}")
    
    # Render PDF via Puppeteer
    script_dir = Path(__file__).parent
    render_script = script_dir / "render.ts"
    
    result = subprocess.run(
        ["bun", "run", str(render_script), str(json_path), str(pdf_path)],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Error rendering PDF: {result.stderr}")
        raise RuntimeError(f"PDF generation failed: {result.stderr}")
    
    print(result.stdout)
    return str(pdf_path)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate Resume:Decoded PDF")
    parser.add_argument("--input", required=True, help="Path to decomposer output directory")
    parser.add_argument("--output", required=True, help="Path to output directory")
    args = parser.parse_args()
    
    pdf_path = generate_pdf(args.input, args.output)
    print(f"\n✓ Generated: {pdf_path}")

if __name__ == "__main__":
    main()
