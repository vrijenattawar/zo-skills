#!/usr/bin/env bun

import { appendFileSync } from "fs";

const LOG_FILE = "/tmp/vapi-debug.log";
function log(...args: any[]) {
  const msg = `[${new Date().toISOString()}] MIGRATION: ${args.map(a => typeof a === 'object' ? JSON.stringify(a, null, 2) : a).join(' ')}\n`;
  console.log(...args);
  try { appendFileSync(LOG_FILE, msg); } catch {}
}

// Configuration from environment variables
const DB_PATH = process.env.VAPI_DB_PATH || "./Datasets/vapi-calls/data.duckdb";

async function runMigration() {
  log("Starting database schema migration v2...");

  try {
    // Create the new tables and view in DuckDB
    const migrationSQL = `
      -- Table to store extracted questions from call transcripts
      CREATE TABLE IF NOT EXISTS call_questions (
          id VARCHAR PRIMARY KEY,           -- UUID
          call_id VARCHAR NOT NULL,         -- FK to calls.id
          question_text VARCHAR NOT NULL,   -- The question as asked
          normalized_question VARCHAR,      -- LLM-normalized version (for dedup/counting)
          answer_text VARCHAR,              -- Frank's response (if captured)
          answer_quality VARCHAR,           -- 'strong', 'weak', 'missing', 'redirect'
          category VARCHAR,                 -- 'investment', 'product', 'technical', 'personal', 'pricing', 'other'
          extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
      
      -- Index for performance
      CREATE INDEX IF NOT EXISTS idx_cq_call ON call_questions(call_id);
      CREATE INDEX IF NOT EXISTS idx_cq_category ON call_questions(category);
      CREATE INDEX IF NOT EXISTS idx_cq_normalized ON call_questions(normalized_question);
      
      -- Table for auto-generated prefab answers
      CREATE TABLE IF NOT EXISTS prefab_answers (
          id VARCHAR PRIMARY KEY,
          normalized_question VARCHAR NOT NULL UNIQUE,
          answer_text VARCHAR NOT NULL,
          occurrence_count INTEGER DEFAULT 0,
          auto_generated BOOLEAN DEFAULT TRUE,
          manually_approved BOOLEAN DEFAULT FALSE,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );

      -- Add analysis column to calls table for storing LLM analysis
      ALTER TABLE calls ADD COLUMN IF NOT EXISTS analysis JSON;
      
      -- View for question statistics
      CREATE OR REPLACE VIEW question_stats AS
      SELECT 
          cq.normalized_question,
          COUNT(*) as ask_count,
          COUNT(DISTINCT cq.call_id) as unique_calls,
          MODE(category) as primary_category,
          MODE(answer_quality) as typical_quality,
          MAX(extracted_at) as last_asked,
          pa.answer_text as prefab_answer
      FROM call_questions cq
      LEFT JOIN prefab_answers pa ON cq.normalized_question = pa.normalized_question
      GROUP BY cq.normalized_question, pa.answer_text
      ORDER BY ask_count DESC;
    `;

    const proc = Bun.spawn(["duckdb", DB_PATH, "-c", migrationSQL]);
    await proc.exited;

    if (proc.exitCode === 0) {
      log("Database schema migration completed successfully");
      
      // Verify tables were created
      const verifyProc = Bun.spawn(["duckdb", DB_PATH, "-c", "SHOW TABLES"]);
      const verifyOutput = await new Response(verifyProc.stdout).text();
      await verifyProc.exited;
      
      log("Tables after migration:", verifyOutput.trim());
      return true;
    } else {
      log("Migration failed with exit code:", proc.exitCode);
      return false;
    }
  } catch (error) {
    log("Migration error:", error);
    return false;
  }
}

// Run the migration if called directly
if (import.meta.main) {
  const success = await runMigration();
  process.exit(success ? 0 : 1);
}

export { runMigration };