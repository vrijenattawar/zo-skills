---
name: rapid-context-extractor
description: Extract and teach key points from a source using seed context, then force active engagement. Use when analyzing articles, documents, transcripts, video/audio transcripts, or mixed media where output must preserve chronological idea flow, include concept explanation, and prompt user reflection.
---

# Rapid Context Extractor

Normalize source mechanics with the script, then do semantic analysis in chat.

## Quick Start

```bash
python3 Skills/rapid-context-extractor/scripts/prepare_payload.py \
  --seed-file "./Research/topic-frame.md" \
  --source-url "https://example.com/article" \
  --auto-semantic \
  --output "/home/.z/workspaces/con_tFxzWpGw5jorTDon/extraction_packet.md"
```

Use one source input per run:
- `--source-url` for web pages
- `--source-file` for local docs/transcripts/subtitles
- `--source-text` for pasted text

Optional seed context:
- `--seed-file` or `--seed-text`

Optional semantic memory anchoring:
- `--semantic-query` to retrieve relevant prior concepts from V's semantic memory
- `--auto-semantic` to generate semantic query from source title + extracted terms (recommended default)
- `--semantic-limit` (default 5) to control number of memory anchors
- `--provenance` to force frontmatter provenance (otherwise inferred from output path conversation ID)

## Workflow

1. Prepare packet
- Run `scripts/prepare_payload.py` to produce a markdown packet containing seed context + chronological source chunks.
- For media files, require transcript sidecar or transcribe first.

2. Adopt analyst frame
- Read seed context first.
- State the frame in 1-2 lines before distillation.
- If missing background blocks understanding, perform targeted research before summarizing.

3. Distill in chronological order
- Produce bullet points in the order ideas appear in source.
- Avoid regrouping by theme if it breaks chronology.
- Keep claims faithful to the source.

4. Include image meaning
- If visuals exist, summarize what each visual contributes to the argument.
- Note if visuals reinforce, contradict, or extend text claims.

5. Integrate for learning
- Explain key terms, concepts, and implications in plain language.
- Connect key claims to `Semantic Memory Anchors` where relevant (agreements, tensions, extensions).
- Explicitly classify each integration claim as `aligns`, `extends`, or `conflicts/tension`.
- Ask clarifying questions that advance interpretation or decisions.

6. Force active engagement
- Ask for immediate reaction (1-3 lines acceptable).
- Ask for one agreement and one challenge.
- Offer optional ingestion: only ingest if user explicitly says yes.

## Standard Output Shape

Use this structure in responses:

1. `Analytical Frame`
2. `Chronological Distillation`
3. `Visual Layer` (if applicable)
4. `Semantic Integration` (link to V-specific anchors)
: include explicit `aligns` / `extends` / `conflicts` labels
5. `Concept Decoder`
6. `Clarifying Questions`
7. `Your Reaction` (collect user response)
8. `Optional Next Step` (ingest yes/no)

## Content Library Ingestion

Only after explicit approval:

```bash
python3 N5/scripts/content_ingest.py "<artifact_path>" --move
```

Confirm with: `Ingested to Content Library as <type>`.

## Resources

- `scripts/prepare_payload.py`: deterministic intake/normalization for seed + source.
- `references/output-template.md`: copyable response template for consistent execution.
