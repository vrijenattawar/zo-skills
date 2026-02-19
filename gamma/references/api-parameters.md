---
created: 2026-01-25
last_edited: 2026-01-25
version: 1.0
provenance: con_8niRcrOEmKFqImvb
---

# Gamma API Parameters Reference

Complete parameter reference for the Gamma API.

## Generate Endpoint

`POST https://public-api.gamma.app/v1.0/generations`

### Top-Level Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `inputText` | Yes | - | Content to generate from. Supports text, markdown, and image URLs. Max ~100k tokens. |
| `textMode` | Yes | - | `generate` (expand), `condense` (summarize), `preserve` (keep exact) |
| `format` | No | `presentation` | `presentation`, `document`, `social`, `webpage` |
| `themeId` | No | workspace default | Theme ID from themes endpoint |
| `numCards` | No | 10 | 1-60 (Pro) or 1-75 (Ultra) |
| `cardSplit` | No | `auto` | `auto` (use numCards) or `inputTextBreaks` (split on `\n---\n`) |
| `additionalInstructions` | No | - | Extra instructions (1-2000 chars) |
| `folderIds` | No | - | Array of folder IDs |
| `exportAs` | No | - | `pdf` or `pptx` |

### textOptions

| Parameter | Default | Values | Description |
|-----------|---------|--------|-------------|
| `amount` | `medium` | `brief`, `medium`, `detailed`, `extensive` | Text density per card |
| `tone` | - | Free text (1-500 chars) | Voice/mood: "professional, inspiring" |
| `audience` | - | Free text (1-500 chars) | Target readers |
| `language` | `en` | Language code | Output language |

### imageOptions

| Parameter | Default | Values | Description |
|-----------|---------|--------|-------------|
| `source` | `aiGenerated` | See below | Image source |
| `model` | auto-selected | See image models | AI model (only with aiGenerated) |
| `style` | - | Free text (1-500 chars) | Visual style |

**Image Sources:**
- `aiGenerated` — AI-generated images
- `pictographic` — Pictographic icons
- `unsplash` — Unsplash photos
- `giphy` — Giphy GIFs
- `webAllImages` — Web images (any license)
- `webFreeToUse` — Personal use licensed
- `webFreeToUseCommercially` — Commercial use licensed
- `placeholder` — Empty placeholders
- `noImages` — No images (use with custom URLs in input)

### cardOptions

| Parameter | Default | Values | Description |
|-----------|---------|--------|-------------|
| `dimensions` | format-dependent | See below | Card aspect ratio |
| `headerFooter` | - | Object | Header/footer configuration |

**Dimensions by Format:**
- `presentation`: `fluid` (default), `16x9`, `4x3`
- `document`: `fluid` (default), `pageless`, `letter`, `a4`
- `social`: `1x1`, `4x5` (default), `9x16`

**headerFooter Object:**
```json
{
  "topLeft": { "type": "text", "value": "Company Name" },
  "topRight": { "type": "image", "source": "themeLogo", "size": "sm" },
  "bottomRight": { "type": "cardNumber" },
  "hideFromFirstCard": true,
  "hideFromLastCard": false
}
```

Positions: `topLeft`, `topRight`, `topCenter`, `bottomLeft`, `bottomRight`, `bottomCenter`
Types: `text` (needs `value`), `image` (needs `source`, optional `size`, `src`), `cardNumber`
Image sources: `themeLogo`, `custom` (needs `src` URL)
Image sizes: `sm`, `md`, `lg`, `xl`

### sharingOptions

| Parameter | Default | Values |
|-----------|---------|--------|
| `workspaceAccess` | workspace setting | `noAccess`, `view`, `comment`, `edit`, `fullAccess` |
| `externalAccess` | workspace setting | `noAccess`, `view`, `comment`, `edit` |
| `emailOptions.recipients` | - | Array of email addresses |
| `emailOptions.access` | - | `view`, `comment`, `edit`, `fullAccess` |

## Create from Template Endpoint

`POST https://public-api.gamma.app/v1.0/generations/from-template`

| Parameter | Required | Description |
|-----------|----------|-------------|
| `gammaId` | Yes | Template gamma ID |
| `prompt` | Yes | Instructions for adaptation |
| `exportAs` | No | `pdf` or `pptx` |
| `imageOptions` | No | Same as generate |
| `sharingOptions` | No | Same as generate |

## Get Generation Status

`GET https://public-api.gamma.app/v1.0/generations/{generationId}`

Response:
```json
{
  "generationId": "xxx",
  "status": "pending|completed|failed",
  "gammaUrl": "https://gamma.app/docs/xxx",
  "credits": { "deducted": 150, "remaining": 3000 }
}
```

## Get Export URLs

`GET https://public-api.gamma.app/v1.0/generations/{generationId}/export-urls`

## List Themes

`GET https://public-api.gamma.app/v1.0/themes`

## List Folders

`GET https://public-api.gamma.app/v1.0/folders`

## Image Models

| Model | String | Credits/Image |
|-------|--------|---------------|
| Flux Fast 1.1 | `flux-1-quick` | 2 |
| Flux Kontext Fast | `flux-kontext-fast` | 2 |
| Imagen 3 Fast | `imagen-3-flash` | 2 |
| Luma Photon Flash | `luma-photon-flash-1` | 2 |
| Flux Pro | `flux-1-pro` | 8 |
| Imagen 3 | `imagen-3-pro` | 8 |
| Ideogram 3 Turbo | `ideogram-v3-turbo` | 10 |
| Luma Photon | `luma-photon-1` | 10 |
| Leonardo Phoenix | `leonardo-phoenix` | 15 |
| Flux Kontext Pro | `flux-kontext-pro` | 20 |
| Gemini 2.5 Flash | `gemini-2.5-flash-image` | 20 |
| Ideogram 3 | `ideogram-v3` | 20 |
| Imagen 4 | `imagen-4-pro` | 20 |
| Recraft | `recraft-v3` | 20 |
| GPT Image | `gpt-image-1-medium` | 30 |

## Language Codes

| Language | Code | Language | Code |
|----------|------|----------|------|
| English (US) | `en` | Japanese | `ja` |
| English (UK) | `en-gb` | Korean | `ko` |
| English (India) | `en-in` | Portuguese | `pt` |
| Spanish | `es` | Portuguese (BR) | `pt-br` |
| French | `fr` | Arabic | `ar` |
| German | `de` | Hindi | `hi` |
| Italian | `it` | Thai | `th` |
| Dutch | `nl` | Vietnamese | `vi` |
| Chinese (Simplified) | `zh` | Indonesian | `id` |
| Chinese (Traditional) | `zh-tw` | Russian | `ru` |

Full list: https://developers.gamma.app/reference/output-language-accepted-values

## Error Codes

| Code | Meaning |
|------|---------|
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid API key |
| 403 | Forbidden - No credits remaining |
| 404 | Not Found - Invalid generation ID |
