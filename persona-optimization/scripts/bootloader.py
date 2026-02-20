#!/usr/bin/env python3
"""Bootloader for Zo persona optimization.

Flow:
1) --scan writes INSTALL_PROPOSAL.md so you can personalize + approve.
2) --apply installs the personas/rules via /zo/ask.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib import request

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "templates"
PERSONA_TEMPLATES_DIR = TEMPLATES_DIR / "personas"
ROUTING_TEMPLATE_PATH = TEMPLATES_DIR / "routing-contract.md"
PERSONALIZE_PATH = TEMPLATES_DIR / "personalize.md"
WORKSPACE_ROOT = Path("/home/workspace")
INSTALL_PROPOSAL_PATH = REPO_ROOT / "INSTALL_PROPOSAL.md"
INSTALL_RECEIPT_PATH = REPO_ROOT / "INSTALL_RECEIPT.json"
ZO_ASK_URL = "https://api.zo.computer/zo/ask"

HARD_SWITCH_RULES = [
    {
        "key": "builder",
        "name": "builder switch",
        "condition": "When the user asks to build, implement, deploy, automate, or write new systems/scripts/code",
        "instruction_template": "Call set_active_persona('<builder_id>') before substantive work begins. NOT triggered for markdown-only docs, running existing scripts, simple file ops, or quick config tweaks that don't require new coding.",
        "target_role": "builder",
    },
    {
        "key": "debugger",
        "name": "debugger switch",
        "condition": "When the user asks to debug, troubleshoot, test, verify behavior, resolve errors, or repeatedly fix a failing flow",
        "instruction_template": "Call set_active_persona('<debugger_id>') before substantive work begins. NOT triggered for single-line typos, cosmetic edits, or inline build errors that {{builder_name}} can handle without switching.",
        "target_role": "debugger",
    },
    {
        "key": "strategist",
        "name": "strategist switch",
        "condition": "When the user is weighing consequential decisions, needs tradeoff analysis, multi-path options, or structured strategy",
        "instruction_template": "Call set_active_persona('<strategist_id>') before substantive work begins. NOT triggered for simple preferences, obvious yes/no questions, or implementation choices within an already-decided direction.",
        "target_role": "strategist",
    },
    {
        "key": "writer",
        "name": "writer switch",
        "condition": "When the user needs external-facing communication longer than two sentences, polished drafts, or public messaging",
        "instruction_template": "Call set_active_persona('<writer_id>') before substantive work begins. NOT triggered for internal notes, code comments, short confirmations, or private chat responses.",
        "target_role": "writer",
    },
    {
        "key": "architect",
        "name": "architect switch",
        "condition": "When the request is a major build/refactor (>50 lines, multi-file, schema change, new system, persona/prompt design) requiring a plan",
        "instruction_template": "Call set_active_persona('<architect_id>') before planning starts. NOT triggered for tiny edits or single-file tweaks under 50 lines.",
        "target_role": "architect",
    },
]

METHODOLOGY_RULES_CONFIG = [
    {
        "key": "researcher",
        "name": "researcher methodology",
        "condition": "When the user asks for multi-source research",
        "template": "researcher.md",
    },
    {
        "key": "teacher",
        "name": "teacher methodology",
        "condition": "When the user asks for deep explanation or learning support",
        "template": "teacher.md",
    },
]

RETURN_TO_OPERATOR_RULE = {
    "name": "return to operator",
    "condition": "After completing work as Builder, Debugger, Strategist, Writer, Architect, Librarian, or any other specialist persona",
    "instruction": "Call set_active_persona('<operator_id>') with a short summary before continuing. This keeps {{operator_name}} in control and tracks progress.",
    "target_role": "operator",
}


def timestamped(message: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}")


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def strip_frontmatter(text: str) -> str:
    match = re.match(r"^---\n.*?\n---\n", text, flags=re.DOTALL)
    return text[match.end():] if match else text


def parse_simple_kv(text: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"')
        if key:
            data[key] = value
    return data


def parse_personalize() -> Dict[str, str]:
    raw = load_text(PERSONALIZE_PATH)
    if raw.startswith("---"):
        match = re.match(r"^---\n.*?\n---\n", raw, flags=re.DOTALL)
        if match:
            raw = raw[match.end():]
    return parse_simple_kv(raw)


def find_candidates() -> Dict[str, List[str]]:
    candidates = {"documents_system": []}
    for root, dirs, _ in os.walk(WORKSPACE_ROOT):
        depth = Path(root).relative_to(WORKSPACE_ROOT).parts
        if len(depth) > 3:
            dirs[:] = []
            continue
        if Path(root).name.lower() == "system" and Path(root).parent.name.lower() in {"documents", "docs"}:
            candidates["documents_system"].append(root)
    preferred = WORKSPACE_ROOT / "Documents" / "System"
    if preferred.exists():
        candidates["documents_system"].insert(0, str(preferred))
    return candidates


def propose_mapping(candidates: Dict[str, List[str]]) -> Dict[str, str]:
    doc_candidates = candidates.get("documents_system", [])
    doc_system = doc_candidates[0] if doc_candidates else str(WORKSPACE_ROOT / "Documents" / "System")
    return {
        "documents_system_path": doc_system,
        "learning_ledger_path": str(Path(doc_system) / "persona-learnings.md"),
    }


def apply_placeholders(text: str, mapping: Dict[str, str]) -> str:
    for key, value in mapping.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def learning_block(ledger_path: str) -> str:
    if not ledger_path:
        return ""
    return (
        "## Learning Ledger\n\n"
        "If you learn something that should persist beyond this task, append a brief note to:\n"
        f"{ledger_path}\n"
    )


def build_persona_manifest(persona_names: Dict[str, str], ledger_path: str) -> List[Dict[str, Any]]:
    ledger_text = learning_block(ledger_path)
    manifests: List[Dict[str, Any]] = []
    for role, template_path in {
        "operator": PERSONA_TEMPLATES_DIR / "operator.md",
        "builder": PERSONA_TEMPLATES_DIR / "builder.md",
        "debugger": PERSONA_TEMPLATES_DIR / "debugger.md",
        "strategist": PERSONA_TEMPLATES_DIR / "strategist.md",
        "writer": PERSONA_TEMPLATES_DIR / "writer.md",
        "researcher": PERSONA_TEMPLATES_DIR / "researcher.md",
        "teacher": PERSONA_TEMPLATES_DIR / "teacher.md",
        "architect": PERSONA_TEMPLATES_DIR / "architect.md",
        "librarian": PERSONA_TEMPLATES_DIR / "librarian.md",
    }.items():
        raw_prompt = strip_frontmatter(load_text(template_path))
        placeholders = {f"{r}_name": persona_names[r] for r in persona_names}
        prompt = apply_placeholders(raw_prompt, placeholders)
        if "{{LEARNING_LEDGER_BLOCK}}" in prompt:
            prompt = prompt.replace("{{LEARNING_LEDGER_BLOCK}}", ledger_text)
        elif ledger_text:
            prompt = prompt + "\n\n" + ledger_text
        manifests.append({
            "role": role,
            "name": persona_names[role],
            "prompt": prompt,
            "template_path": str(template_path),
        })
    return manifests


def load_methodology_text(template_name: str) -> str:
    template_path = PERSONA_TEMPLATES_DIR / template_name
    return strip_frontmatter(load_text(template_path))


def build_rule_manifest(rule_prefix: str, persona_names: Dict[str, str], ledger_path: str) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    placeholder_map = {f"{role}_name": name for role, name in persona_names.items()}
    ledger_block = learning_block(ledger_path)
    for rule in HARD_SWITCH_RULES:
        rules.append({
            "name": f"{rule_prefix}: {rule['name']}",
            "condition": rule["condition"],
            "instruction": apply_placeholders(rule["instruction_template"], placeholder_map),
            "target_role": rule["target_role"],
        })
    for rule in METHODOLOGY_RULES_CONFIG:
        instruction = apply_placeholders(load_methodology_text(rule["template"]), placeholder_map)
        if "{{LEARNING_LEDGER_BLOCK}}" in instruction:
            instruction = instruction.replace("{{LEARNING_LEDGER_BLOCK}}", ledger_block)
        rules.append({
            "name": f"{rule_prefix}: {rule['name']}",
            "condition": rule["condition"],
            "instruction": instruction,
        })
    rules.append({
        "name": f"{rule_prefix}: {RETURN_TO_OPERATOR_RULE['name']}",
        "condition": RETURN_TO_OPERATOR_RULE["condition"],
        "instruction": apply_placeholders(RETURN_TO_OPERATOR_RULE["instruction"], placeholder_map),
        "target_role": RETURN_TO_OPERATOR_RULE["target_role"],
    })
    return rules


def send_zo_prompt(prompt: str) -> Dict[str, Any]:
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN", "")
    if not token:
        raise RuntimeError("ZO_CLIENT_IDENTITY_TOKEN missing; run inside Zo or export the token.")
    payload = {"input": prompt}
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(ZO_ASK_URL, data=data, method="POST")
    req.add_header("content-type", "application/json")
    req.add_header("authorization", f"Bearer {token}")
    with request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_json_summary(output: str) -> Dict[str, Any]:
    decoder = json.JSONDecoder()
    start = output.find("{")
    if start == -1:
        return {"error": "No JSON in response", "output": output}
    try:
        summary, _ = decoder.raw_decode(output[start:])
        return summary
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON", "output": output[start:]}


def build_install_prompt(personas: List[Dict[str, Any]], rules: List[Dict[str, Any]]) -> str:
    persona_block = json.dumps([{"name": p["name"], "prompt": p["prompt"]} for p in personas], indent=2)
    rule_block = json.dumps([{k: v for k, v in r.items() if k != "target_role"} for r in rules], indent=2)
    step_text = (
        "Step 1: For each persona entry, immediately call `create_persona` with the `name` and `prompt`, then record the returned ID under that persona's role.\n"
        "Step 2: After all personas exist, iterate the rule entries. For rules with `target_role`, replace tokens like `<builder_id>` with the ID assigned to that role.\n"
        "Step 3: Call `create_rule` with the finalized `name`, `condition`, and `instruction`.\n"
        "Step 4: Once every rule is created, reply with JSON listing every persona and rule name + id.\n"
    )
    return (
        "You are Zo. Execute the persona install manifest below.\n"
        "- Create personas first, mapping each role to the returned ID.\n"
        "- Use those IDs when composing rules that reference specialized personas.\n"
        "- Do not duplicate installs if the same names already exist.\n"
        "- Do not switch personas during install.\n\n"
        f"{step_text}\n"
        f"Personas:\n{persona_block}\n\n"
        f"Rules:\n{rule_block}\n"
        "Return JSON, for example: {\n  \"success\": true,\n  \"personas\": [{\"name\": \"Builder\", \"id\": \"abc\"}],\n  \"rules\": [{\"name\": \"persona: builder switch\", \"id\": \"rule-123\"}]\n}"
    )


def execute_install_manifest(personas: List[Dict[str, Any]], rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    prompt = build_install_prompt(personas, rules)
    response = send_zo_prompt(prompt)
    summary = extract_json_summary(response.get("output", ""))
    summary.setdefault("raw_output", response.get("output", ""))
    return summary


def write_install_receipt(summary: Dict[str, Any], mapping: Dict[str, str]) -> None:
    receipt = {
        "timestamp": datetime.now().isoformat(),
        "mapping": mapping,
        "summary": summary,
    }
    timestamped(f"Writing install receipt to {INSTALL_RECEIPT_PATH}")
    INSTALL_RECEIPT_PATH.write_text(json.dumps(receipt, indent=2), encoding="utf-8")


def apply_install(dry_run: bool = False) -> None:
    if not INSTALL_PROPOSAL_PATH.exists():
        raise RuntimeError("INSTALL_PROPOSAL.md not found. Run --scan first.")
    personalize = parse_personalize()
    if personalize.get("approve_install", "false").lower() != "true":
        raise RuntimeError("approve_install must be true in templates/personalize.md before applying.")
    candidates = find_candidates()
    mapping = propose_mapping(candidates)
    mapping.update({
        "documents_system_path": personalize.get("documents_system_path", mapping["documents_system_path"]),
        "learning_ledger_path": personalize.get("learning_ledger_path", mapping["learning_ledger_path"]),
    })
    # Treat empty learning_ledger_path as unset; fall back to proposed default
    if not mapping["learning_ledger_path"]:
        mapping["learning_ledger_path"] = propose_mapping(candidates)["learning_ledger_path"]
    persona_names = {
        "operator": personalize.get("operator_name", "Operator"),
        "builder": personalize.get("builder_name", "Builder"),
        "debugger": personalize.get("debugger_name", "Debugger"),
        "strategist": personalize.get("strategist_name", "Strategist"),
        "writer": personalize.get("writer_name", "Writer"),
        "researcher": personalize.get("researcher_name", "Researcher"),
        "teacher": personalize.get("teacher_name", "Teacher"),
        "architect": personalize.get("architect_name", "Architect"),
        "librarian": personalize.get("librarian_name", "Librarian"),
    }
    docs_system = Path(mapping["documents_system_path"])
    docs_system.mkdir(parents=True, exist_ok=True)
    routing = apply_placeholders(load_text(ROUTING_TEMPLATE_PATH), {
        "operator_name": persona_names["operator"],
        "builder_name": persona_names["builder"],
        "debugger_name": persona_names["debugger"],
        "strategist_name": persona_names["strategist"],
        "writer_name": persona_names["writer"],
        "researcher_name": persona_names["researcher"],
        "teacher_name": persona_names["teacher"],
        "architect_name": persona_names["architect"],
        "librarian_name": persona_names["librarian"],
    })
    (docs_system / "persona-routing-contract.md").write_text(routing, encoding="utf-8")
    ledger_path = Path(mapping["learning_ledger_path"])
    if not ledger_path.exists():
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(
            """---
created: 2026-02-10
last_edited: 2026-02-10
version: 1.0
provenance: bootloader-install
---

# Persona Learnings

- 
""",
            encoding="utf-8",
        )
    persona_manifest = build_persona_manifest(persona_names, str(ledger_path))
    rules = build_rule_manifest(personalize.get("rule_prefix", "persona"), persona_names, str(ledger_path))
    timestamped(f"Prepared {len(persona_manifest)} personas and {len(rules)} rules")
    if dry_run:
        timestamped("Dry run enabled; skipping /zo/ask call")
        print(json.dumps({"personas": persona_manifest, "rules": rules, "mapping": mapping}, indent=2))
        return
    summary = execute_install_manifest(persona_manifest, rules)
    if not summary.get("success"):
        raise RuntimeError(f"Install failed: {summary.get('error_message', summary)}")
    timestamped("Install manifest submitted. Review Zo's response for created IDs.")
    timestamped(json.dumps(summary, indent=2))
    write_install_receipt(summary, mapping)


def write_install_proposal(mapping: Dict[str, str], persona_names: Dict[str, str]) -> None:
    lines = [
        "---",
        "created: 2026-02-10",
        "last_edited: 2026-02-10",
        "version: 1.0",
        "provenance: bootloader-scan",
        "---",
        "",
        "# Install Proposal (Socratic Step)",
        "",
        "## Proposed Paths",
        f"- documents_system_path: {mapping['documents_system_path']}",
        f"- learning_ledger_path: {mapping['learning_ledger_path']}",
        "",
        "## Personas to Create",
    ]
    for role, name in persona_names.items():
        lines.append(f"- {role}: {name}")
    lines += [
        "",
        "## What Will Be Installed",
        "- Routing contract file",
        "- Learning ledger file (if not exists)",
        "- 9 persona prompts (in Zo settings)",
        "- 8 rules (5 hard-switch + 2 methodology + return-to-operator)",
        "",
        "## How ad-hoc changes are applied across the board",
        "- Persona names and rule prefixes are injected into templates before export",
        "- Routes and learning ledger paths are customizable via personalize.md",
        "",
        "## Socratic questions (answer in templates/personalize.md)",
        "1. Which personas are you installing, and why those?",
        "2. Where will the routing contract and learning ledger live?",
        "3. What rule prefix avoids collisions in your system?",
        "4. What would break if rules mis-route a request?",
        "5. How will you verify switching correctness?",
    ]
    INSTALL_PROPOSAL_PATH.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Zo Persona Optimization bootloader")
    parser.add_argument("--scan", action="store_true", help="Scan the workspace and write INSTALL_PROPOSAL.md")
    parser.add_argument("--apply", action="store_true", help="Apply the install manifest via Zo's /zo/ask endpoint")
    parser.add_argument("--dry-run", action="store_true", help="Simulate apply without calling /zo/ask")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.scan and not args.apply:
        print("Please specify --scan or --apply. Use --scan first, then update personalize.md, then --apply.")
        sys.exit(1)
    if args.scan:
        candidates = find_candidates()
        mapping = propose_mapping(candidates)
        personalize = parse_personalize()
        persona_names = {
            "operator": personalize.get("operator_name", "Operator"),
            "builder": personalize.get("builder_name", "Builder"),
            "debugger": personalize.get("debugger_name", "Debugger"),
            "strategist": personalize.get("strategist_name", "Strategist"),
            "writer": personalize.get("writer_name", "Writer"),
            "researcher": personalize.get("researcher_name", "Researcher"),
            "teacher": personalize.get("teacher_name", "Teacher"),
            "architect": personalize.get("architect_name", "Architect"),
            "librarian": personalize.get("librarian_name", "Librarian"),
        }
        write_install_proposal(mapping, persona_names)
        print(
            f"Wrote {INSTALL_PROPOSAL_PATH}. Review it, update templates/personalize.md, set approve_install: true, then run --apply."
        )
        return
    apply_install(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
