---
created: 2026-02-10
last_edited: 2026-02-12
version: 2.0
provenance: con_XXXXXXXXXX
---
# Personalization

Fill in the values below before running the bootloader. These control persona names,
file paths, and the rule prefix used to avoid collisions with other rules.

## Persona Names
operator_name: "Operator"
builder_name: "Builder"
debugger_name: "Debugger"
strategist_name: "Strategist"
writer_name: "Writer"
researcher_name: "Researcher"
teacher_name: "Teacher"
architect_name: "Architect"
librarian_name: "Librarian"

## Rule Configuration
rule_prefix: "persona"

## Paths (scanned by --scan, override here if needed)
documents_system_path: "./Documents/System"
learning_ledger_path: ""

## Approval Gate
approve_install: false

## Socratic Questions (answer these before setting approve_install: true)
1. Which personas are you installing, and why those?
2. Where will the routing contract and learning ledger live?
3. What rule prefix avoids collisions with your existing rules?
4. What would break if these rules mis-route a request?
5. How will you verify the personas are switching correctly?
