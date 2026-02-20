---
created: 2026-02-10
last_edited: 2026-02-10
version: 1.0
provenance: con_XXXXXXXXXX
---

# Advised File Structure (with Fuzzy Install)

This package assumes a **Zo‑native** workspace. The bootloader **does not assume the exact same structure**, and instead proposes a mapping after scanning the system.

## Recommended structure (ideal)

```
./
  Documents/
    System/
      persona-routing-contract.md
      persona-learnings.md
  Build Exports/
    n5-os-zo-persona-optimization/
```

## How fuzzy install works

1. **Scan** the workspace for likely equivalents (e.g., `Documents/`, `System/`)
2. **Propose** concrete install paths in `INSTALL_PROPOSAL.md`
3. **Ask** you to approve or edit the mapping in `templates/personalize.md`
4. **Apply** the install using your approved mapping

If `Documents/System` does not exist, the installer will suggest the closest match (e.g., `Documents/`, `System/`, `Docs/`, `Notes/`).

## You control the mapping

The installer does **not** apply changes until you confirm.

In `templates/personalize.md` you can override:
- `documents_system_path`
- `learning_ledger_path`
- persona names and rule prefixes

This allows the install to be **adaptive** without being fragile.
