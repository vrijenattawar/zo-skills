#!/usr/bin/env bun

/**
 * Gamma API CLI - Comprehensive integration for presentations, documents, webpages, and social posts
 * API Docs: https://developers.gamma.app/docs/getting-started
 */

const API_BASE = "https://public-api.gamma.app/v1.0";
const API_KEY = process.env.GAMMA_API_KEY;

if (!API_KEY) {
  console.error("Error: GAMMA_API_KEY environment variable not set");
  console.error("Add your API key at Settings > Developers");
  process.exit(1);
}

const headers = {
  "Content-Type": "application/json",
  "X-API-KEY": API_KEY,
};

// ============ Types ============

interface GenerateOptions {
  inputText: string;
  textMode: "generate" | "condense" | "preserve";
  format?: "presentation" | "document" | "webpage" | "social";
  themeId?: string;
  numCards?: number;
  cardSplit?: "auto" | "inputTextBreaks";
  additionalInstructions?: string;
  folderIds?: string[];
  exportAs?: "pdf" | "pptx";
  textOptions?: {
    language?: string;
    tone?: string;
    audience?: string;
    amount?: "brief" | "medium" | "detailed" | "extensive";
  };
  imageOptions?: {
    source?: "aiGenerated" | "webSearch" | "none";
    model?: string;
    style?: string;
  };
  cardOptions?: {
    dimensions?: "fluid" | "16x9" | "4x3" | "1x1" | "4x5" | "9x16" | "3x4" | "2x3" | "5x4" | "21x9";
  };
  sharingOptions?: {
    visibility?: "private" | "public" | "unlisted";
    allowCopy?: boolean;
    allowDuplication?: boolean;
  };
}

interface FromTemplateOptions {
  gammaId: string;
  prompt: string;
  themeId?: string;
  folderIds?: string[];
  exportAs?: "pdf" | "pptx";
  imageOptions?: {
    source?: "aiGenerated" | "webSearch" | "none";
    model?: string;
    style?: string;
  };
  sharingOptions?: {
    visibility?: "private" | "public" | "unlisted";
    allowCopy?: boolean;
    allowDuplication?: boolean;
  };
}

interface GenerationStatus {
  generationId: string;
  status: "pending" | "completed" | "failed";
  gammaUrl?: string;
  pdfUrl?: string;
  pptxUrl?: string;
  warnings?: string[];
  error?: string;
}

// ============ API Functions ============

async function generate(options: GenerateOptions): Promise<{ generationId: string }> {
  const body: any = {
    inputText: options.inputText,
    textMode: options.textMode,
  };

  if (options.format) body.format = options.format;
  if (options.themeId) body.themeId = options.themeId;
  if (options.numCards) body.numCards = options.numCards;
  if (options.cardSplit) body.cardSplit = options.cardSplit;
  if (options.additionalInstructions) body.additionalInstructions = options.additionalInstructions;
  if (options.folderIds?.length) body.folderIds = options.folderIds;
  if (options.exportAs) body.exportAs = options.exportAs;

  if (options.textOptions) {
    body.textOptions = {};
    if (options.textOptions.language) body.textOptions.language = options.textOptions.language;
    if (options.textOptions.tone) body.textOptions.tone = options.textOptions.tone;
    if (options.textOptions.audience) body.textOptions.audience = options.textOptions.audience;
    if (options.textOptions.amount) body.textOptions.amount = options.textOptions.amount;
  }

  if (options.imageOptions) {
    body.imageOptions = {};
    if (options.imageOptions.source) body.imageOptions.source = options.imageOptions.source;
    if (options.imageOptions.model) body.imageOptions.model = options.imageOptions.model;
    if (options.imageOptions.style) body.imageOptions.style = options.imageOptions.style;
  }

  if (options.cardOptions?.dimensions) {
    body.cardOptions = { dimensions: options.cardOptions.dimensions };
  }

  if (options.sharingOptions) {
    body.sharingOptions = {};
    if (options.sharingOptions.visibility) body.sharingOptions.visibility = options.sharingOptions.visibility;
    if (options.sharingOptions.allowCopy !== undefined) body.sharingOptions.allowCopy = options.sharingOptions.allowCopy;
    if (options.sharingOptions.allowDuplication !== undefined) body.sharingOptions.allowDuplication = options.sharingOptions.allowDuplication;
  }

  const response = await fetch(`${API_BASE}/generations`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(`API Error ${response.status}: ${JSON.stringify(error)}`);
  }

  return response.json();
}

async function fromTemplate(options: FromTemplateOptions): Promise<{ generationId: string }> {
  const body: any = {
    gammaId: options.gammaId,
    prompt: options.prompt,
  };

  if (options.themeId) body.themeId = options.themeId;
  if (options.folderIds?.length) body.folderIds = options.folderIds;
  if (options.exportAs) body.exportAs = options.exportAs;

  if (options.imageOptions) {
    body.imageOptions = {};
    if (options.imageOptions.source) body.imageOptions.source = options.imageOptions.source;
    if (options.imageOptions.model) body.imageOptions.model = options.imageOptions.model;
    if (options.imageOptions.style) body.imageOptions.style = options.imageOptions.style;
  }

  if (options.sharingOptions) {
    body.sharingOptions = {};
    if (options.sharingOptions.visibility) body.sharingOptions.visibility = options.sharingOptions.visibility;
    if (options.sharingOptions.allowCopy !== undefined) body.sharingOptions.allowCopy = options.sharingOptions.allowCopy;
    if (options.sharingOptions.allowDuplication !== undefined) body.sharingOptions.allowDuplication = options.sharingOptions.allowDuplication;
  }

  const response = await fetch(`${API_BASE}/generations/from-template`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(`API Error ${response.status}: ${JSON.stringify(error)}`);
  }

  return response.json();
}

async function getStatus(generationId: string): Promise<GenerationStatus> {
  const response = await fetch(`${API_BASE}/generations/${generationId}`, {
    method: "GET",
    headers: { "X-API-KEY": API_KEY!, accept: "application/json" },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(`API Error ${response.status}: ${JSON.stringify(error)}`);
  }

  return response.json();
}

async function pollUntilComplete(generationId: string, maxWaitMs = 300000): Promise<GenerationStatus> {
  const startTime = Date.now();
  const pollInterval = 5000; // 5 seconds

  while (Date.now() - startTime < maxWaitMs) {
    const status = await getStatus(generationId);
    
    if (status.status === "completed") {
      return status;
    }
    
    if (status.status === "failed") {
      throw new Error(`Generation failed: ${status.error || "Unknown error"}`);
    }

    console.error(`Status: ${status.status}... waiting ${pollInterval / 1000}s`);
    await new Promise((resolve) => setTimeout(resolve, pollInterval));
  }

  throw new Error(`Timeout: Generation did not complete within ${maxWaitMs / 1000}s`);
}

async function listThemes(): Promise<any> {
  const response = await fetch(`${API_BASE}/themes`, {
    method: "GET",
    headers: { "X-API-KEY": API_KEY!, accept: "application/json" },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(`API Error ${response.status}: ${JSON.stringify(error)}`);
  }

  return response.json();
}

async function listFolders(): Promise<any> {
  const response = await fetch(`${API_BASE}/folders`, {
    method: "GET",
    headers: { "X-API-KEY": API_KEY!, accept: "application/json" },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(`API Error ${response.status}: ${JSON.stringify(error)}`);
  }

  return response.json();
}

// ============ CLI Parsing ============

function parseArgs(args: string[]): Record<string, string | boolean | string[]> {
  const result: Record<string, string | boolean | string[]> = {};
  let i = 0;

  while (i < args.length) {
    const arg = args[i];
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const nextArg = args[i + 1];
      
      if (!nextArg || nextArg.startsWith("--")) {
        result[key] = true;
        i++;
      } else {
        // Handle comma-separated values for arrays
        if (key === "folders") {
          result[key] = nextArg.split(",").map(s => s.trim());
        } else {
          result[key] = nextArg;
        }
        i += 2;
      }
    } else {
      i++;
    }
  }

  return result;
}

function printHelp(): void {
  console.log(`
Gamma API CLI - Generate presentations, documents, webpages, and social posts

COMMANDS:

  generate <inputText> [options]
    Create a new gamma from scratch using AI.
    
    Required:
      <inputText>                 Content to generate from (text, can include image URLs)
      --mode <mode>               How to handle input: generate|condense|preserve
                                  - generate: AI creates content based on input
                                  - condense: AI summarizes/shortens input
                                  - preserve: Keep input text exactly as-is

    Content Options:
      --format <type>             Output type: presentation|document|webpage|social
      --cards <n>                 Number of cards/slides (1-60 Pro, 1-75 Ultra)
      --card-split <mode>         How to split content: auto|inputTextBreaks
      --instructions <text>       Additional instructions (max 2000 chars)

    Text Options:
      --language <code>           Output language (en, es, fr, de, ja, zh-cn, etc.)
      --tone <description>        Writing tone (e.g., "professional", "casual")
      --audience <description>    Target audience (e.g., "executives", "students")
      --amount <level>            Detail level: brief|medium|detailed|extensive

    Image Options:
      --images <source>           Image source: aiGenerated|webSearch|none
      --image-model <model>       AI model for images (see models below)
      --image-style <description> Visual style (e.g., "minimalist", "vibrant")

    Layout Options:
      --dimensions <size>         Card dimensions: fluid|16x9|4x3|1x1|4x5|9x16|...

    Organization:
      --theme <id>                Theme ID (use 'themes' command to list)
      --folders <id1,id2>         Folder IDs (comma-separated)
      --export <format>           Also export as: pdf|pptx

    Sharing:
      --visibility <level>        Access: private|public|unlisted
      --allow-copy                Allow viewers to copy content
      --allow-duplication         Allow viewers to duplicate gamma

    Behavior:
      --wait                      Poll until complete and return final URLs
      --timeout <seconds>         Max wait time (default: 300)

  from-template <gammaId> <prompt> [options]
    Create a new gamma by adapting an existing template.
    
    Required:
      <gammaId>                   Template gamma ID (from Gamma app: ⋮ > Copy gammaId for API)
      <prompt>                    Instructions for adapting the template

    Options:
      Same as generate, except: --mode, --format, --cards, --card-split,
      --language, --tone, --audience, --amount, --dimensions are not available.

  status <generationId>
    Check the status of a generation and get URLs.

  themes
    List available themes (standard + custom).

  folders
    List your folders.

IMAGE MODELS (--image-model):

  Budget (2 credits/image):
    flux-1-quick, flux-kontext-fast, imagen-3-flash, luma-photon-flash-1

  Standard (8-15 credits/image):
    flux-1-pro, imagen-3-pro, ideogram-v3-turbo, luma-photon-1, leonardo-phoenix

  Premium (20-33 credits/image):
    flux-kontext-pro, gemini-2.5-flash-image, ideogram-v3, imagen-4-pro,
    recraft-v3, gpt-image-1-medium, dall-e-3

  Ultra-only (30-120 credits/image):
    flux-1-ultra, imagen-4-ultra, flux-kontext-max, recraft-v3-svg,
    ideogram-v3-quality, gpt-image-1-high

LANGUAGES (--language):
  English: en (US), en-gb (UK), en-in (India)
  Spanish: es, es-es (Spain), es-mx (Mexico), es-419 (Latin America)
  Chinese: zh-cn (Simplified), zh-tw (Traditional)
  Japanese: ja (です/ます), ja-da (だ/である)
  Other: fr, de, it, pt-br, pt-pt, ko, ar, hi, ru, nl, pl, tr, vi, th, id, ...
  (60+ languages supported - see API docs for full list)

EXAMPLES:

  # Simple presentation
  bun run gamma.ts generate "Quarterly sales report for Q4 2024" --mode generate --format presentation --wait

  # Document with specific style
  bun run gamma.ts generate "AI in healthcare" --mode generate --format document \\
    --tone "academic" --audience "medical professionals" --amount detailed --wait

  # Webpage with AI images
  bun run gamma.ts generate "Our startup story" --mode generate --format webpage \\
    --images aiGenerated --image-model imagen-4-pro --image-style "modern minimalist" --wait

  # Social post
  bun run gamma.ts generate "New product launch announcement" --mode generate --format social --wait

  # From existing content (preserve exact text)
  bun run gamma.ts generate "$(cat my-content.md)" --mode preserve --format presentation --wait

  # Summarize long content
  bun run gamma.ts generate "$(cat long-article.txt)" --mode condense --format presentation --cards 5 --wait

  # Create from template
  bun run gamma.ts from-template g_abc123xyz "Adapt for healthcare industry" --wait

  # Non-English output
  bun run gamma.ts generate "Company overview" --mode generate --language ja --wait

  # Check status manually
  bun run gamma.ts status gen_xyz123

  # List available themes
  bun run gamma.ts themes
`);
}

// ============ Main ============

async function main(): Promise<void> {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === "--help" || args[0] === "-h") {
    printHelp();
    process.exit(0);
  }

  const command = args[0];

  try {
    switch (command) {
      case "generate": {
        const inputText = args[1];
        if (!inputText || inputText.startsWith("--")) {
          console.error("Error: inputText is required");
          console.error("Usage: gamma.ts generate <inputText> --mode <mode> [options]");
          process.exit(1);
        }

        const opts = parseArgs(args.slice(2));
        
        if (!opts.mode) {
          console.error("Error: --mode is required (generate|condense|preserve)");
          process.exit(1);
        }

        const options: GenerateOptions = {
          inputText,
          textMode: opts.mode as "generate" | "condense" | "preserve",
        };

        if (opts.format) options.format = opts.format as any;
        if (opts.theme) options.themeId = opts.theme as string;
        if (opts.cards) options.numCards = parseInt(opts.cards as string);
        if (opts["card-split"]) options.cardSplit = opts["card-split"] as any;
        if (opts.instructions) options.additionalInstructions = opts.instructions as string;
        if (opts.folders) options.folderIds = opts.folders as string[];
        if (opts.export) options.exportAs = opts.export as any;

        // Text options
        if (opts.language || opts.tone || opts.audience || opts.amount) {
          options.textOptions = {};
          if (opts.language) options.textOptions.language = opts.language as string;
          if (opts.tone) options.textOptions.tone = opts.tone as string;
          if (opts.audience) options.textOptions.audience = opts.audience as string;
          if (opts.amount) options.textOptions.amount = opts.amount as any;
        }

        // Image options
        if (opts.images || opts["image-model"] || opts["image-style"]) {
          options.imageOptions = {};
          if (opts.images) options.imageOptions.source = opts.images as any;
          if (opts["image-model"]) options.imageOptions.model = opts["image-model"] as string;
          if (opts["image-style"]) options.imageOptions.style = opts["image-style"] as string;
        }

        // Card options
        if (opts.dimensions) {
          options.cardOptions = { dimensions: opts.dimensions as any };
        }

        // Sharing options
        if (opts.visibility || opts["allow-copy"] || opts["allow-duplication"]) {
          options.sharingOptions = {};
          if (opts.visibility) options.sharingOptions.visibility = opts.visibility as any;
          if (opts["allow-copy"]) options.sharingOptions.allowCopy = true;
          if (opts["allow-duplication"]) options.sharingOptions.allowDuplication = true;
        }

        const result = await generate(options);
        console.error(`Generation started: ${result.generationId}`);

        if (opts.wait) {
          const timeout = opts.timeout ? parseInt(opts.timeout as string) * 1000 : 300000;
          const status = await pollUntilComplete(result.generationId, timeout);
          console.log(JSON.stringify(status, null, 2));
        } else {
          console.log(JSON.stringify(result, null, 2));
        }
        break;
      }

      case "from-template": {
        const gammaId = args[1];
        const prompt = args[2];
        
        if (!gammaId || gammaId.startsWith("--")) {
          console.error("Error: gammaId is required");
          console.error("Usage: gamma.ts from-template <gammaId> <prompt> [options]");
          process.exit(1);
        }
        
        if (!prompt || prompt.startsWith("--")) {
          console.error("Error: prompt is required");
          console.error("Usage: gamma.ts from-template <gammaId> <prompt> [options]");
          process.exit(1);
        }

        const opts = parseArgs(args.slice(3));

        const options: FromTemplateOptions = {
          gammaId,
          prompt,
        };

        if (opts.theme) options.themeId = opts.theme as string;
        if (opts.folders) options.folderIds = opts.folders as string[];
        if (opts.export) options.exportAs = opts.export as any;

        // Image options
        if (opts.images || opts["image-model"] || opts["image-style"]) {
          options.imageOptions = {};
          if (opts.images) options.imageOptions.source = opts.images as any;
          if (opts["image-model"]) options.imageOptions.model = opts["image-model"] as string;
          if (opts["image-style"]) options.imageOptions.style = opts["image-style"] as string;
        }

        // Sharing options
        if (opts.visibility || opts["allow-copy"] || opts["allow-duplication"]) {
          options.sharingOptions = {};
          if (opts.visibility) options.sharingOptions.visibility = opts.visibility as any;
          if (opts["allow-copy"]) options.sharingOptions.allowCopy = true;
          if (opts["allow-duplication"]) options.sharingOptions.allowDuplication = true;
        }

        const result = await fromTemplate(options);
        console.error(`Generation started: ${result.generationId}`);

        if (opts.wait) {
          const timeout = opts.timeout ? parseInt(opts.timeout as string) * 1000 : 300000;
          const status = await pollUntilComplete(result.generationId, timeout);
          console.log(JSON.stringify(status, null, 2));
        } else {
          console.log(JSON.stringify(result, null, 2));
        }
        break;
      }

      case "status": {
        const generationId = args[1];
        if (!generationId) {
          console.error("Error: generationId is required");
          console.error("Usage: gamma.ts status <generationId>");
          process.exit(1);
        }

        const status = await getStatus(generationId);
        console.log(JSON.stringify(status, null, 2));
        break;
      }

      case "themes": {
        const themes = await listThemes();
        console.log(JSON.stringify(themes, null, 2));
        break;
      }

      case "folders": {
        const folders = await listFolders();
        console.log(JSON.stringify(folders, null, 2));
        break;
      }

      default:
        console.error(`Unknown command: ${command}`);
        printHelp();
        process.exit(1);
    }
  } catch (err: any) {
    console.error(`Error: ${err.message}`);
    process.exit(1);
  }
}

main();
