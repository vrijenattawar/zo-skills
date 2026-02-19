#!/usr/bin/env python3
"""
Branded PDF Generator
Generate clean, professional PDFs with customizable logos and styling.
"""

import argparse
import re
import sys
from pathlib import Path

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, KeepTogether
    from reportlab.lib.colors import HexColor
except ImportError:
    print("Error: reportlab not installed. Run: pip install reportlab")
    sys.exit(1)


def parse_markdown(md_content: str) -> dict:
    """Parse markdown into structured content."""
    lines = md_content.strip().split('\n')
    
    result = {
        'title': None,
        'sections': []
    }
    
    current_section = None
    current_subsection = None
    current_paragraphs = []
    
    def flush_paragraphs():
        nonlocal current_paragraphs
        if current_paragraphs:
            text = '\n'.join(current_paragraphs).strip()
            if text:
                if current_subsection is not None:
                    current_section['subsections'][-1]['paragraphs'].append(text)
                elif current_section is not None:
                    current_section['paragraphs'].append(text)
            current_paragraphs = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip YAML frontmatter
        if i == 0 and line.strip() == '---':
            i += 1
            while i < len(lines) and lines[i].strip() != '---':
                i += 1
            i += 1
            continue
        
        # H1 - Title
        if line.startswith('# ') and not line.startswith('## '):
            flush_paragraphs()
            if result['title'] is None:
                result['title'] = line[2:].strip()
            i += 1
            continue
        
        # H2 - Section
        if line.startswith('## '):
            flush_paragraphs()
            current_subsection = None
            current_section = {
                'heading': line[3:].strip(),
                'paragraphs': [],
                'subsections': []
            }
            result['sections'].append(current_section)
            i += 1
            continue
        
        # H3 - Subsection
        if line.startswith('### '):
            flush_paragraphs()
            if current_section is not None:
                current_subsection = {
                    'heading': line[4:].strip(),
                    'paragraphs': []
                }
                current_section['subsections'].append(current_subsection)
            i += 1
            continue
        
        # Empty line - paragraph break
        if line.strip() == '':
            flush_paragraphs()
            i += 1
            continue
        
        # Regular text - accumulate
        current_paragraphs.append(line)
        i += 1
    
    flush_paragraphs()
    return result


def convert_markdown_formatting(text: str) -> str:
    """Convert markdown bold/italic to reportlab tags."""
    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    # Italic: *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)
    # Escape special characters
    text = text.replace('—', '–')  # em-dash to en-dash for compatibility
    return text


def generate_pdf(
    input_path: str,
    output_path: str,
    left_logo: str = None,
    right_logo: str = None,
    center_logo: str = None,
    title: str = None,
    subtitle: str = None,
    author: str = None,
    author_detail: str = None,
    primary_color: str = "#1a1a1a",
    text_color: str = "#333333",
    body_size: int = 12,
    heading_size: int = 15,
    margin: float = 0.75
):
    """Generate the PDF document."""
    
    # Read and parse markdown
    with open(input_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    parsed = parse_markdown(md_content)
    
    # Use parsed title if not overridden
    if title is None:
        title = parsed.get('title', 'Document')
    
    # Create document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=margin * inch,
        rightMargin=margin * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch
    )
    
    # Define styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=28,
        spaceAfter=6,
        textColor=HexColor(primary_color),
        alignment=TA_CENTER,
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=body_size - 1,
        leading=14,
        spaceAfter=4,
        textColor=HexColor('#555555'),
        alignment=TA_CENTER,
    )
    
    h2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=heading_size,
        leading=heading_size + 5,
        spaceBefore=20,
        spaceAfter=10,
        textColor=HexColor(primary_color),
        keepWithNext=True
    )
    
    h3_style = ParagraphStyle(
        'CustomH3',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=heading_size - 2,
        leading=heading_size + 2,
        spaceBefore=14,
        spaceAfter=6,
        textColor=HexColor(text_color),
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=body_size,
        leading=body_size + 4,
        spaceAfter=10,
        textColor=HexColor(text_color),
    )
    
    story = []
    
    # --- HEADER WITH LOGOS ---
    if left_logo and right_logo:
        left_img = Image(left_logo, height=0.4*inch, width=2*inch, kind='proportional')
        right_img = Image(right_logo, height=0.55*inch, width=1.8*inch, kind='proportional')
        
        header_table = Table(
            [[left_img, "", right_img]],
            colWidths=[2.5*inch, 2*inch, 2.5*inch]
        )
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.4*inch))
    elif center_logo:
        center_img = Image(center_logo, height=0.6*inch, width=2.5*inch, kind='proportional')
        header_table = Table([[center_img]], colWidths=[7*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.4*inch))
    
    # --- TITLE ---
    if title:
        story.append(Paragraph(title, title_style))
    if subtitle:
        story.append(Paragraph(subtitle, title_style))
    
    story.append(Spacer(1, 0.15*inch))
    
    if author:
        story.append(Paragraph(author, subtitle_style))
    if author_detail:
        story.append(Paragraph(author_detail, subtitle_style))
    
    if title or subtitle or author:
        story.append(Spacer(1, 0.3*inch))
    
    # --- CONTENT SECTIONS ---
    for section in parsed['sections']:
        # Section heading
        story.append(Paragraph(section['heading'], h2_style))
        
        # Section paragraphs
        for para in section['paragraphs']:
            formatted = convert_markdown_formatting(para)
            story.append(Paragraph(formatted, body_style))
        
        # Subsections
        for subsection in section.get('subsections', []):
            story.append(Paragraph(subsection['heading'], h3_style))
            for para in subsection['paragraphs']:
                formatted = convert_markdown_formatting(para)
                story.append(Paragraph(formatted, body_style))
    
    # Build PDF
    doc.build(story)
    print(f"PDF generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate clean, professional PDFs with customizable branding.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input brief.md --output brief.pdf
  %(prog)s --input brief.md --output brief.pdf --left-logo a.png --right-logo b.png
  %(prog)s --input memo.md --output memo.pdf --logo company.png --title "Q1 Report"
        """
    )
    
    # Required
    parser.add_argument('--input', '-i', required=True, help='Input markdown file')
    parser.add_argument('--output', '-o', required=True, help='Output PDF path')
    
    # Logos
    logo_group = parser.add_mutually_exclusive_group()
    logo_group.add_argument('--logo', help='Single centered logo')
    parser.add_argument('--left-logo', help='Left header logo (for dual-logo mode)')
    parser.add_argument('--right-logo', help='Right header logo (for dual-logo mode)')
    
    # Title/Author
    parser.add_argument('--title', help='Document title (overrides markdown H1)')
    parser.add_argument('--subtitle', help='Subtitle below title')
    parser.add_argument('--author', help='Author line')
    parser.add_argument('--author-detail', help='Second author line (credentials)')
    
    # Styling
    parser.add_argument('--primary-color', default='#1a1a1a', help='Heading color (hex)')
    parser.add_argument('--text-color', default='#333333', help='Body text color (hex)')
    parser.add_argument('--body-size', type=int, default=12, help='Body font size (pt)')
    parser.add_argument('--heading-size', type=int, default=15, help='H2 font size (pt)')
    parser.add_argument('--margin', type=float, default=0.75, help='Page margins (inches)')
    
    args = parser.parse_args()
    
    # Validate input
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    # Validate logos if specified
    if args.left_logo and not Path(args.left_logo).exists():
        print(f"Error: Left logo not found: {args.left_logo}")
        sys.exit(1)
    if args.right_logo and not Path(args.right_logo).exists():
        print(f"Error: Right logo not found: {args.right_logo}")
        sys.exit(1)
    if args.logo and not Path(args.logo).exists():
        print(f"Error: Logo not found: {args.logo}")
        sys.exit(1)
    
    # Generate
    generate_pdf(
        input_path=args.input,
        output_path=args.output,
        left_logo=args.left_logo,
        right_logo=args.right_logo,
        center_logo=args.logo,
        title=args.title,
        subtitle=args.subtitle,
        author=args.author,
        author_detail=args.author_detail,
        primary_color=args.primary_color,
        text_color=args.text_color,
        body_size=args.body_size,
        heading_size=args.heading_size,
        margin=args.margin
    )


if __name__ == '__main__':
    main()
