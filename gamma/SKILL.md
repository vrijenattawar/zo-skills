---
name: gamma
description: Generate presentations, documents, social posts, and websites using Gamma's AI API. Supports full generation from prompts or creation from existing templates.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  api_version: v1.0
---

# Gamma API Integration

Generate professional presentations, documents, webpages, and social posts using Gamma's AI.

## Quick Start

```bash
# Verify API key is set
bun run Skills/gamma/scripts/gamma.ts themes

# Generate a presentation
bun run Skills/gamma/scripts/gamma.ts generate "Q4 2024 Sales Report" --mode generate --format presentation --wait

# Generate a document
bun run Skills/gamma/scripts/gamma.ts generate "AI in Healthcare" --mode generate --format document --wait
```

## Commands

### `generate` — Create from scratch

Generate a new gamma from AI using text input.

```bash
bun run Skills/gamma/scripts/gamma.ts generate "<inputText>" --mode <mode> [options]
```

**Required:**
- `<inputText>` — Content to generate from (supports text and image URLs, max 100k tokens)
- `--mode <mode>` — How to handle input text:
  - `generate` — AI creates new content based on your input (most common)
  - `condense` — AI summarizes/shortens your input
  - `preserve` — Keep your input text exactly as-is

**Content Options:**
- `--format <type>` — Output type: `presentation` | `document` | `webpage` | `social`
- `--cards <n>` — Number of cards/slides (1-60 Pro, 1-75 Ultra)
- `--card-split <mode>` — Content splitting: `auto` | `inputTextBreaks`
- `--instructions <text>` — Additional instructions (max 2000 chars)

**Text Options:**
- `--language <code>` — Output language (default: `en`)
- `--tone <description>` — Writing tone (e.g., "professional", "casual", "academic")
- `--audience <description>` — Target audience (e.g., "executives", "students", "developers")
- `--amount <level>` — Detail level: `brief` | `medium` | `detailed` | `extensive`

**Image Options:**
- `--images <source>` — Image source: `aiGenerated` | `webSearch` | `none`
- `--image-model <model>` — AI model for image generation (see models below)
- `--image-style <description>` — Visual style (e.g., "minimalist", "vibrant", "corporate")

**Layout Options:**
- `--dimensions <size>` — Card dimensions: `fluid` | `16x9` | `4x3` | `1x1` | `4x5` | `9x16` | `3x4` | `2x3` | `5x4` | `21x9`

**Organization:**
- `--theme <id>` — Theme ID (use `themes` command to list available)
- `--folders <id1,id2>` — Folder IDs for storage (comma-separated)
- `--export <format>` — Also export as: `pdf` | `pptx`

**Sharing:**
- `--visibility <level>` — Access level: `private` | `public` | `unlisted`
- `--allow-copy` — Allow viewers to copy content
- `--allow-duplication` — Allow viewers to duplicate the gamma

**Behavior:**
- `--wait` — Poll until generation completes, then return final URLs
- `--timeout <seconds>` — Max wait time (default: 300)

### `from-template` — Create from existing gamma

Create a new gamma by adapting an existing template.

```bash
bun run Skills/gamma/scripts/gamma.ts from-template <gammaId> "<prompt>" [options]
```

**Required:**
- `<gammaId>` — Template gamma ID (find in Gamma app: ⋮ > Copy gammaId for API)
- `<prompt>` — Instructions for adapting the template (max 100k tokens)

**Available Options:**
Same as `generate` except these are NOT available: `--mode`, `--format`, `--cards`, `--card-split`, `--language`, `--tone`, `--audience`, `--amount`, `--dimensions`

### `status` — Check generation status

```bash
bun run Skills/gamma/scripts/gamma.ts status <generationId>
```

Returns status (`pending` | `completed` | `failed`), gamma URL, and export URLs if ready.

### `themes` — List available themes

```bash
bun run Skills/gamma/scripts/gamma.ts themes
```

Returns standard themes and your custom themes with their IDs.

### `folders` — List your folders

```bash
bun run Skills/gamma/scripts/gamma.ts folders
```

Returns your Gamma folders with their IDs.

## Image Models

### Budget (2 credits/image)
| Model | String |
|-------|--------|
| Flux Fast 1.1 | `flux-1-quick` |
| Flux Kontext Fast | `flux-kontext-fast` |
| Imagen 3 Fast | `imagen-3-flash` |
| Luma Photon Flash | `luma-photon-flash-1` |

### Standard (8-15 credits/image)
| Model | String | Credits |
|-------|--------|---------|
| Flux Pro | `flux-1-pro` | 8 |
| Imagen 3 | `imagen-3-pro` | 8 |
| Ideogram 3 Turbo | `ideogram-v3-turbo` | 10 |
| Luma Photon | `luma-photon-1` | 10 |
| Leonardo Phoenix | `leonardo-phoenix` | 15 |

### Premium (20-33 credits/image)
| Model | String | Credits |
|-------|--------|---------|
| Flux Kontext Pro | `flux-kontext-pro` | 20 |
| Gemini 2.5 Flash | `gemini-2.5-flash-image` | 20 |
| Ideogram 3 | `ideogram-v3` | 20 |
| Imagen 4 | `imagen-4-pro` | 20 |
| Recraft | `recraft-v3` | 20 |
| GPT Image | `gpt-image-1-medium` | 30 |
| Dall-E 3 | `dall-e-3` | 33 |

### Ultra-only (30-120 credits/image)
| Model | String | Credits |
|-------|--------|---------|
| Flux Ultra | `flux-1-ultra` | 30 |
| Imagen 4 Ultra | `imagen-4-ultra` | 30 |
| Flux Kontext Max | `flux-kontext-max` | 40 |
| Recraft Vector | `recraft-v3-svg` | 40 |
| Ideogram 3 Quality | `ideogram-v3-quality` | 45 |
| GPT Image Detailed | `gpt-image-1-high` | 120 |

## Languages

### English Variants
- `en` — English (US) — default
- `en-gb` — English (UK)
- `en-in` — English (India)

### Spanish Variants
- `es` — Spanish (general)
- `es-es` — Spanish (Spain)
- `es-mx` — Spanish (Mexico)
- `es-419` — Spanish (Latin America)

### Chinese
- `zh-cn` — Simplified Chinese
- `zh-tw` — Traditional Chinese

### Japanese
- `ja` — Japanese (です/ます polite style)
- `ja-da` — Japanese (だ/である plain style)

### Other Major Languages
`fr` (French), `de` (German), `it` (Italian), `pt-br` (Portuguese Brazil), `pt-pt` (Portuguese Portugal), `ko` (Korean), `ar` (Arabic), `hi` (Hindi), `ru` (Russian), `nl` (Dutch), `pl` (Polish), `tr` (Turkish), `vi` (Vietnamese), `th` (Thai), `id` (Indonesian)

### Full List
60+ languages supported including: `af`, `sq`, `ar-sa`, `bn`, `bs`, `bg`, `ca`, `hr`, `cs`, `da`, `et`, `fi`, `el`, `gu`, `ha`, `he`, `hu`, `is`, `kn`, `kk`, `lv`, `lt`, `mk`, `ms`, `ml`, `mr`, `nb`, `fa`, `ro`, `sr`, `sl`, `sw`, `sv`, `tl`, `ta`, `te`, `uk`, `ur`, `uz`, `cy`, `yo`

## Examples

### Basic Presentation
```bash
bun run Skills/gamma/scripts/gamma.ts generate "Quarterly sales report for Q4 2024. Include revenue growth, key wins, and 2025 outlook." \
  --mode generate \
  --format presentation \
  --wait
```

### Detailed Document
```bash
bun run Skills/gamma/scripts/gamma.ts generate "The impact of artificial intelligence on healthcare delivery" \
  --mode generate \
  --format document \
  --tone "academic" \
  --audience "medical professionals" \
  --amount detailed \
  --images aiGenerated \
  --image-model imagen-4-pro \
  --wait
```

### Startup Pitch Deck
```bash
bun run Skills/gamma/scripts/gamma.ts generate "TechStartup is revolutionizing supply chain with AI. Founded 2023, $2M ARR, seeking Series A." \
  --mode generate \
  --format presentation \
  --cards 12 \
  --tone "confident and compelling" \
  --audience "venture capitalists" \
  --images aiGenerated \
  --image-style "modern tech aesthetic" \
  --wait
```

### Webpage
```bash
bun run Skills/gamma/scripts/gamma.ts generate "Our company story: from garage startup to industry leader" \
  --mode generate \
  --format webpage \
  --images aiGenerated \
  --image-model flux-1-pro \
  --image-style "professional corporate photography" \
  --visibility public \
  --wait
```

### Social Post
```bash
bun run Skills/gamma/scripts/gamma.ts generate "Announcing our new product launch! Revolutionary features that will change how teams collaborate." \
  --mode generate \
  --format social \
  --tone "exciting and engaging" \
  --wait
```

### From Existing Content (Preserve Text)
```bash
# When you have exact content you want to use
bun run Skills/gamma/scripts/gamma.ts generate "$(cat my-prepared-content.md)" \
  --mode preserve \
  --format presentation \
  --wait
```

### Condense Long Content
```bash
# Summarize a long document into a short presentation
bun run Skills/gamma/scripts/gamma.ts generate "$(cat long-report.txt)" \
  --mode condense \
  --format presentation \
  --cards 5 \
  --instructions "Focus on key findings and recommendations only" \
  --wait
```

### Adapt a Template
```bash
# Use an existing gamma as a template
bun run Skills/gamma/scripts/gamma.ts from-template g_xo2yqze5mj8z62g \
  "Adapt this pitch deck for a healthcare AI startup instead of fintech" \
  --images aiGenerated \
  --wait
```

### Non-English Output
```bash
# Japanese presentation
bun run Skills/gamma/scripts/gamma.ts generate "Company introduction and services overview" \
  --mode generate \
  --format presentation \
  --language ja \
  --wait

# Spanish document
bun run Skills/gamma/scripts/gamma.ts generate "Quarterly financial report" \
  --mode generate \
  --format document \
  --language es-mx \
  --wait
```

### Export to PDF/PPTX
```bash
bun run Skills/gamma/scripts/gamma.ts generate "Team training materials" \
  --mode generate \
  --format presentation \
  --export pdf \
  --wait
```

## Tips

1. **Text Mode Selection:**
   - Use `generate` for most cases — AI creates content from your brief
   - Use `preserve` when you have exact content already written
   - Use `condense` to summarize long documents

2. **Image Quality vs. Cost:**
   - Start with budget models (`flux-1-quick`, `imagen-3-flash`) for drafts
   - Use premium models for final versions

3. **Finding Template IDs:**
   - In Gamma app: Open template → ⋮ menu → "Copy gammaId for API"

4. **Finding Theme IDs:**
   - Run `bun run Skills/gamma/scripts/gamma.ts themes`
   - Or in Gamma app: Themes → ⋮ menu → "Copy themeId for API"

5. **Polling Behavior:**
   - Without `--wait`: Returns immediately with generationId
   - With `--wait`: Polls every 5 seconds until complete (default timeout: 5 minutes)

## References

- [Gamma API Overview](https://developers.gamma.app/docs/getting-started)
- [Generate API Parameters](https://developers.gamma.app/docs/generate-api-parameters-explained)
- [Template API Parameters](https://developers.gamma.app/docs/create-from-template-parameters-explained)
- [Image Models](https://developers.gamma.app/reference/image-model-accepted-values)
- [Languages](https://developers.gamma.app/reference/output-language-accepted-values)
