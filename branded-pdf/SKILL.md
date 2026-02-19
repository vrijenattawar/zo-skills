---
name: branded-pdf
description: Generate clean, professional PDFs with dual-logo headers, customizable styling, and well-spaced typography. Ideal for technical briefs, partnership documents, proposals, and branded memos. Takes markdown content and outputs polished PDFs.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  created: 2026-02-02
  version: 1.0
---

# Branded PDF Generator

Generate professional PDFs with dual-logo headers and clean typography.

## Quick Start

```bash
python3 Skills/branded-pdf/scripts/generate_pdf.py \
  --input content.md \
  --output document.pdf \
  --left-logo logo1.png \
  --right-logo logo2.png \
  --title "Document Title"
```

## Features

- **Dual-logo header**: Left and right logos for partnership/co-branded documents
- **Single-logo mode**: Use `--logo` for centered single logo
- **Markdown input**: Supports headers (##, ###), bold, italic, paragraphs
- **Customizable styling**: Colors, font sizes, margins
- **Smart pagination**: Headers stay with their content (no orphans)

## Usage

### Basic (markdown file input)

```bash
python3 Skills/branded-pdf/scripts/generate_pdf.py \
  --input brief.md \
  --output brief.pdf
```

### With logos and title override

```bash
python3 Skills/branded-pdf/scripts/generate_pdf.py \
  --input brief.md \
  --output brief.pdf \
  --left-logo company-a.png \
  --right-logo company-b.png \
  --title "Company A × Company B" \
  --subtitle "Technical Brief"
```

### Single centered logo

```bash
python3 Skills/branded-pdf/scripts/generate_pdf.py \
  --input memo.md \
  --output memo.pdf \
  --logo company.png
```

### Custom styling

```bash
python3 Skills/branded-pdf/scripts/generate_pdf.py \
  --input doc.md \
  --output doc.pdf \
  --primary-color "#2563eb" \
  --text-color "#1f2937" \
  --body-size 11 \
  --heading-size 16
```

## CLI Reference

| Argument | Description | Default |
|----------|-------------|---------|
| `--input` | Input markdown file (required) | - |
| `--output` | Output PDF path (required) | - |
| `--left-logo` | Left header logo (PNG/JPG) | None |
| `--right-logo` | Right header logo (PNG/JPG) | None |
| `--logo` | Single centered logo | None |
| `--title` | Document title (overrides markdown) | From markdown H1 |
| `--subtitle` | Subtitle below title | None |
| `--author` | Author line | None |
| `--author-detail` | Second author line (credentials) | None |
| `--primary-color` | Heading color (hex) | #1a1a1a |
| `--text-color` | Body text color (hex) | #333333 |
| `--body-size` | Body font size (pt) | 12 |
| `--heading-size` | H2 font size (pt) | 15 |
| `--margin` | Page margins (inches) | 0.75 |

## Input Format

The input markdown should use:
- `## Section Title` for major sections (H2)
- `### Subsection` for subsections (H3)
- `**bold**` for emphasis
- Regular paragraphs separated by blank lines

The first `# Title` in the markdown becomes the document title unless `--title` is specified.

## Examples

See `assets/example-input.md` for a sample input file.
