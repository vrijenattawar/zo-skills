#!/usr/bin/env bun
/**
 * Resume:Decoded PDF Renderer v3.5
 * 
 * Renders Resume:Decoded data to pixel-perfect 2-page PDF using Puppeteer.
 * 
 * Usage:
 *   bun run render.ts <input.json> <output.pdf>
 *   bun run render.ts --from-decomposer <decomposer_dir> <output.pdf>
 */
import puppeteer from "puppeteer";
import Handlebars from "handlebars";
import { readFileSync, writeFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { execSync } from "child_process";

// === TYPE DEFINITIONS ===
interface Spike {
  label: string;
  years: string;
  bar_width: number;
  story_verified: boolean;
  screen_count?: number;  // Number of screens validating this capability
  action?: string;
}

interface Probe {
  area: string;
  context: string;
  prompt: string;
  signal_type: string;
}

interface WhySignal {
  title: string;
  story: string;
  story_verified: boolean;
}

interface BehavioralSignal {
  title: string;
  description: string;
  quote?: string;
  citation?: string;
}

interface Question {
  topic: string;
  question: string;
  verifies: string;
  signal_type: string;
  category: string;
}

interface Tradeoff {
  need: string;
  verdict: string;
  reason: string;
}

interface ResumeDecodedData {
  // Header
  candidate_name: string;
  role: string;
  partner: string;
  company: string;
  date: string;
  
  // Tenure
  tenure_summary: string;
  trajectory: string;
  trajectory_type: string;
  avg_tenure: number;
  
  // Verdict
  verdict_emoji: string;
  verdict: string;
  confidence_score: number;
  verdict_summary: string;
  
  // Signal composition
  signal_story: number;
  signal_resume: number;
  signal_inferred: number;
  skills_assessed: number;
  screens_count: number;  // v4.0: renamed from interviews_count
  
  // Page 1: Spikes
  spikes_up: Spike[];
  spikes_down: Spike[];
  
  // Page 1: What to Verify
  dealbreakers: string[];
  probes: Probe[];
  watch_for: string[];
  
  // Page 1: Why Signal Is Strong
  why_signal: WhySignal[];
  
  // Page 1: Preferences
  preferences: string[];
  
  // Page 2: Behavioral Evidence
  behavioral_signals: BehavioralSignal[];
  
  // Page 2: Questions
  questions_evidence: Question[];
  questions_verify: Question[];
  
  // Page 2: Trade-offs
  tradeoffs: Tradeoff[];
  
  // Metadata
  overall_strengths: string;
  overall_weaknesses: string;
}

// === HANDLEBARS HELPERS ===
function registerHelpers() {
  // Equality comparison helper
  Handlebars.registerHelper("eq", function(a: any, b: any) {
    return a === b;
  });
  
  // Greater than helper
  Handlebars.registerHelper("gt", function(a: number, b: number) {
    return a > b;
  });
  
  // Length check helper
  Handlebars.registerHelper("hasItems", function(arr: any[]) {
    return arr && arr.length > 0;
  });
  
  // Truncate helper
  Handlebars.registerHelper("truncate", function(str: string, len: number) {
    if (!str) return "";
    if (str.length <= len) return str;
    return str.substring(0, len) + "...";
  });
}

// === MAIN RENDER FUNCTION ===
async function renderPDF(data: ResumeDecodedData, outputPath: string): Promise<void> {
  registerHelpers();
  
  const scriptDir = dirname(import.meta.path);
  const templatePath = join(scriptDir, "..", "templates", "template.html");
  
  if (!existsSync(templatePath)) {
    throw new Error(`Template not found: ${templatePath}`);
  }
  
  const templateHtml = readFileSync(templatePath, "utf-8");
  const template = Handlebars.compile(templateHtml);
  const html = template(data);
  
  // Save HTML for debugging
  const htmlPath = outputPath.replace(".pdf", ".html");
  writeFileSync(htmlPath, html);
  console.log(`✓ HTML saved: ${htmlPath}`);
  
  // Launch Puppeteer
  const browser = await puppeteer.launch({
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--font-render-hinting=none"
    ]
  });
  
  try {
    const page = await browser.newPage();
    
    // Set content and wait for fonts to load
    await page.setContent(html, { 
      waitUntil: ["networkidle0", "domcontentloaded"]
    });
    
    // Wait a bit more for web fonts
    await page.evaluate(() => document.fonts.ready);
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Generate PDF
    await page.pdf({
      path: outputPath,
      format: "Letter",
      printBackground: true,
      margin: { top: "0", bottom: "0", left: "0", right: "0" },
      preferCSSPageSize: true
    });
    
    console.log(`✓ PDF saved: ${outputPath}`);
  } finally {
    await browser.close();
  }
}

// === LOAD FROM DECOMPOSER ===
async function loadFromDecomposer(decomposerDir: string): Promise<ResumeDecodedData> {
  const scriptDir = dirname(import.meta.path);
  const adapterPath = join(scriptDir, "adapter.py");
  
  // Run adapter.py to get template data
  const tempJsonPath = `/tmp/resume-decoded-${Date.now()}.json`;
  
  try {
    console.log(`Running adapter on: ${decomposerDir}`);
    execSync(`python3 "${adapterPath}" "${decomposerDir}" "${tempJsonPath}"`, {
      stdio: ["pipe", "pipe", "pipe"]
    });
    
    const data = JSON.parse(readFileSync(tempJsonPath, "utf-8"));
    return data as ResumeDecodedData;
  } finally {
    // Cleanup temp file
    try {
      execSync(`rm -f "${tempJsonPath}"`);
    } catch {}
  }
}

// === VALIDATE DATA ===
function validateData(data: ResumeDecodedData): string[] {
  const warnings: string[] = [];
  
  if (!data.candidate_name || data.candidate_name === "Candidate") {
    warnings.push("candidate_name not set");
  }
  if (!data.verdict_summary) {
    warnings.push("verdict_summary is empty");
  }
  if (!data.spikes_up || data.spikes_up.length === 0) {
    warnings.push("No upward spikes (strengths)");
  }
  if (!data.why_signal || data.why_signal.length === 0) {
    warnings.push("No 'why signal is strong' entries");
  }
  if (!data.tradeoffs || data.tradeoffs.length === 0) {
    warnings.push("No trade-offs defined");
  }
  
  return warnings;
}

// === CLI ===
async function main() {
  const args = process.argv.slice(2);
  
  if (args.length < 2) {
    console.log(`
Resume:Decoded PDF Renderer v3.5

Usage:
  bun run render.ts <input.json> <output.pdf>
  bun run render.ts --from-decomposer <decomposer_dir> <output.pdf>

Options:
  --from-decomposer    Load data from decomposer output directory
  --validate-only      Validate data without rendering

Examples:
  bun run render.ts hardik-data.json hardik-decoded.pdf
  bun run render.ts --from-decomposer /path/to/hardik-docsum/ hardik-decoded.pdf
`);
    process.exit(1);
  }
  
  let data: ResumeDecodedData;
  let outputPath: string;
  
  if (args[0] === "--from-decomposer") {
    if (args.length < 3) {
      console.error("Error: --from-decomposer requires <decomposer_dir> and <output.pdf>");
      process.exit(1);
    }
    data = await loadFromDecomposer(args[1]);
    outputPath = args[2];
  } else if (args[0] === "--validate-only") {
    const inputPath = args[1];
    data = JSON.parse(readFileSync(inputPath, "utf-8"));
    const warnings = validateData(data);
    if (warnings.length > 0) {
      console.log("Validation warnings:");
      warnings.forEach(w => console.log(`  ⚠ ${w}`));
    } else {
      console.log("✓ Data validation passed");
    }
    process.exit(warnings.length > 0 ? 1 : 0);
  } else {
    const inputPath = args[0];
    outputPath = args[1];
    data = JSON.parse(readFileSync(inputPath, "utf-8"));
  }
  
  // Validate
  const warnings = validateData(data);
  if (warnings.length > 0) {
    console.log("Warnings:");
    warnings.forEach(w => console.log(`  ⚠ ${w}`));
  }
  
  // Render
  await renderPDF(data, outputPath);
  console.log("\n✓ Resume:Decoded generation complete");
}

main().catch(err => {
  console.error("Error:", err.message);
  process.exit(1);
});

export { renderPDF, loadFromDecomposer, ResumeDecodedData };
