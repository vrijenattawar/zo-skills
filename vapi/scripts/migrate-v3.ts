#!/usr/bin/env bun

// Migration v3: Add caller_mode column for investor/user mode tracking

const DB_PATH = process.env.VAPI_DB_PATH || "./Datasets/vapi-calls/data.duckdb";

async function runMigration() {
  console.log("Running migration v3: Adding caller_mode column...");
  
  const migrationScript = `
import duckdb
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "${DB_PATH}"
con = duckdb.connect(db_path)

try:
    # Add caller_mode column if it doesn't exist
    con.execute('ALTER TABLE calls ADD COLUMN IF NOT EXISTS caller_mode VARCHAR DEFAULT \\'UNKNOWN\\'')
    print("✅ Added caller_mode column to calls table")
    
    # Create index for better query performance on caller_mode
    con.execute('CREATE INDEX IF NOT EXISTS idx_calls_caller_mode ON calls(caller_mode)')
    print("✅ Created index on caller_mode column")
    
    # Show current schema
    schema = con.execute('DESCRIBE calls').fetchall()
    print("\\n📋 Updated calls table schema:")
    for col in schema:
        print(f"  - {col[0]}: {col[1]} {col[2] if col[2] else ''}")
        
except Exception as e:
    print(f"❌ Migration failed: {e}")
    exit(1)
finally:
    con.close()

print("\\n✅ Migration v3 completed successfully")
`;

  const proc = Bun.spawn(["python3", "-c", migrationScript, DB_PATH]);
  const result = await proc.exited;
  
  if (result === 0) {
    console.log("Migration v3 completed successfully");
  } else {
    console.error("Migration v3 failed");
    process.exit(1);
  }
}

await runMigration();