#!/usr/bin/env python3
import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import List
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from N5.cognition.n5_memory_client import N5MemoryClient
    MEMORY_AVAILABLE = True
except Exception:
    MEMORY_AVAILABLE = False


@dataclass
class SourcePayload:
    source_label: str
    source_kind: str
    text: str
    notes: List[str]


@dataclass
class SemanticAnchor:
    score: float
    path: str
    source: str
    snippet: str
    quality_tag: str
    adjusted_score: float


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._chunks: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def text(self) -> str:
        return "\n".join(self._chunks)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_transcript_jsonl(path: Path) -> str:
    rows: List[str] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if isinstance(obj, dict):
                speaker = obj.get("speaker") or obj.get("speaker_name")
                text = (
                    obj.get("text")
                    or obj.get("content")
                    or obj.get("transcript")
                    or obj.get("utterance")
                    or ""
                )
                text = str(text).strip()
                if not text:
                    continue
                if speaker:
                    rows.append(f"{speaker}: {text}")
                else:
                    rows.append(text)
            else:
                rows.append(str(obj))
    return "\n".join(rows)


def _read_srt(path: Path) -> str:
    lines: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        if "-->" in line:
            continue
        lines.append(line)
    return "\n".join(lines)


def _fetch_url(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            )
        },
    )
    with urlopen(req, timeout=30) as r:
        body = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
        html = body.decode(charset, errors="replace")
    parser = _HTMLTextExtractor()
    parser.feed(html)
    text = _clean_web_text(parser.text())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _clean_web_text(text: str) -> str:
    if not text:
        return text
    noise_exact = {
        "about",
        "search",
        "menu",
        "home",
        "skip to content",
        "on this page",
        "all rights reserved",
    }
    cleaned: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        key = line.lower()
        if key in noise_exact:
            continue
        if re.match(r"^(privacy policy|terms of use|cookie policy)$", key):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _split_passages(text: str, max_chars: int) -> List[str]:
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: List[str] = []
    cur = ""
    for p in paragraphs:
        if not cur:
            cur = p
            continue
        candidate = f"{cur}\n\n{p}"
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            out.append(cur)
            cur = p
    if cur:
        out.append(cur)
    return out


def _derive_provenance(output_path: Path, explicit_provenance: str | None) -> str:
    if explicit_provenance:
        return explicit_provenance.strip()
    match = re.search(r"/workspaces/(con_[A-Za-z0-9]+)/", str(output_path))
    if match:
        return match.group(1)
    return "rapid-context-extractor"


def _truncate(text: str, max_chars: int = 280) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _infer_title_from_source(payload: SourcePayload) -> str:
    lines = [ln.strip() for ln in payload.text.splitlines() if ln.strip()]
    if not lines:
        return "source"
    first = lines[0]
    if len(first) > 120:
        return first[:120].strip()
    return first


def _extract_keywords(text: str, max_terms: int = 8) -> List[str]:
    stopwords = {
        "the", "and", "for", "that", "with", "this", "from", "have", "been", "are", "was",
        "were", "into", "their", "they", "your", "you", "but", "not", "all", "can", "will",
        "what", "when", "where", "which", "while", "more", "less", "than", "then", "also",
        "about", "could", "would", "should", "just", "them", "very", "much", "some", "many",
        "over", "under", "into", "onto", "like", "make", "made", "only", "most", "same",
    }
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", text.lower())
    counts: dict[str, int] = {}
    for t in tokens:
        if t in stopwords:
            continue
        counts[t] = counts.get(t, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [term for term, _ in ranked[:max_terms]]


def _build_auto_semantic_query(payload: SourcePayload, seed: str) -> str:
    title = _infer_title_from_source(payload)
    keywords = _extract_keywords(payload.text, max_terms=10)
    seed_hint = _truncate(seed, max_chars=120) if seed else ""
    parts = [
        "V documented beliefs, positions, and prior notes related to:",
        title,
        f"key terms: {', '.join(keywords)}" if keywords else "key terms: (none)",
        "focus on AI productivity, engineering quality, decision hygiene, and learning/growth",
    ]
    if seed_hint:
        parts.append(f"seed context hint: {seed_hint}")
    return " | ".join(parts)


def _anchor_quality(path: str) -> tuple[float, str]:
    normalized = path.lower()
    if "/personal/knowledge/" in normalized:
        return (0.10, "personal-knowledge")
    if "/knowledge/content-library/personal/" in normalized:
        return (0.09, "personal-library")
    if "/research/" in normalized:
        return (0.06, "research")
    if "/personal/meetings/" in normalized:
        return (0.04, "meetings")
    if "/n5/prefs/personas/" in normalized or "/n5/prefs/" in normalized:
        return (-0.20, "system-pref-penalty")
    if "/n5/" in normalized:
        return (-0.08, "system-penalty")
    return (0.0, "neutral")


def _load_semantic_anchors(query: str | None, limit: int) -> List[SemanticAnchor]:
    if not query or limit <= 0:
        return []
    if not MEMORY_AVAILABLE:
        return [
            SemanticAnchor(
                score=0.0,
                path="(none)",
                source="(semantic memory unavailable)",
                snippet="N5MemoryClient import failed",
                quality_tag="unavailable",
                adjusted_score=0.0,
            )
        ]
    try:
        client = N5MemoryClient()
        results = client.search(
            query,
            limit=max(limit * 5, 30),
            use_reranker=True,
            rerank_top_k=max(50, limit * 10),
        )
    except Exception as e:
        return [
            SemanticAnchor(
                score=0.0,
                path="(none)",
                source="(semantic memory error)",
                snippet=str(e),
                quality_tag="error",
                adjusted_score=0.0,
            )
        ]

    anchors: List[SemanticAnchor] = []
    for res in results or []:
        path = res.get("path", "unknown")
        lines = res.get("lines")
        if isinstance(lines, (list, tuple)) and len(lines) == 2:
            source = f"{path}:{lines[0]}-{lines[1]}"
        else:
            start = res.get("start_line")
            end = res.get("end_line")
            if start and end:
                source = f"{path}:{start}-{end}"
            else:
                source = path
        score = res.get("score", res.get("similarity", 0.0))
        try:
            score_f = float(score)
        except Exception:
            score_f = 0.0
        snippet = _truncate(res.get("content", ""))
        boost, quality_tag = _anchor_quality(path)
        anchors.append(
            SemanticAnchor(
                score=score_f,
                path=path,
                source=source,
                snippet=snippet,
                quality_tag=quality_tag,
                adjusted_score=score_f + boost,
            )
        )

    dedup: dict[str, SemanticAnchor] = {}
    for a in sorted(anchors, key=lambda x: x.adjusted_score, reverse=True):
        key = f"{a.source}|{a.snippet[:120]}"
        if key not in dedup:
            dedup[key] = a
    return list(dedup.values())[:limit]


def _build_integration_layer(anchors: List[SemanticAnchor]) -> List[str]:
    if not anchors:
        return [
            "- Aligns with prior concepts: (no semantic anchors found)",
            "- Extends your thinking: (add manually during analysis)",
            "- Conflicts or tension checks: (add manually during analysis)",
        ]

    ranked = sorted(anchors, key=lambda x: x.adjusted_score, reverse=True)
    aligns = ranked[:2]
    extends = ranked[2:4] if len(ranked) > 2 else []
    conflict_candidates = [
        a for a in ranked
        if any(k in a.snippet.lower() for k in ["risk", "tension", "contrad", "however", "but "])
    ][:2]

    lines: List[str] = []
    if aligns:
        lines.append("- Aligns with prior concepts:")
        for a in aligns:
            lines.append(f"  - `{a.source}` ({a.quality_tag})")
    else:
        lines.append("- Aligns with prior concepts: (none)")

    if extends:
        lines.append("- Extends your thinking:")
        for a in extends:
            lines.append(f"  - `{a.source}` ({a.quality_tag})")
    else:
        lines.append("- Extends your thinking: (none)")

    if conflict_candidates:
        lines.append("- Conflicts or tension checks:")
        for a in conflict_candidates:
            lines.append(f"  - `{a.source}` ({a.quality_tag})")
    else:
        lines.append("- Conflicts or tension checks: (none flagged automatically)")

    return lines


def _load_source(args) -> SourcePayload:
    notes: List[str] = []
    if args.source_text:
        return SourcePayload("inline-text", "text", args.source_text.strip(), notes)

    if args.source_file:
        p = Path(args.source_file)
        if not p.exists():
            raise FileNotFoundError(f"Source file not found: {p}")

        suffix = p.suffix.lower()
        if suffix == ".jsonl":
            text = _read_transcript_jsonl(p)
            return SourcePayload(str(p), "transcript-jsonl", text, notes)
        if suffix == ".srt":
            text = _read_srt(p)
            return SourcePayload(str(p), "subtitle", text, notes)
        if suffix in {".md", ".txt", ".log", ".csv", ".json", ".yaml", ".yml"}:
            text = _read_text(p)
            return SourcePayload(str(p), "file-text", text, notes)
        if suffix in {".mp3", ".wav", ".m4a", ".mp4", ".mov", ".mkv", ".webm"}:
            sidecar = p.with_suffix(p.suffix + ".transcript.jsonl")
            if sidecar.exists():
                text = _read_transcript_jsonl(sidecar)
                notes.append(f"Used sidecar transcript: {sidecar}")
                return SourcePayload(str(p), "media-with-sidecar", text, notes)
            raise ValueError(
                "Media file provided without transcript. Generate one first, e.g. via transcribe_audio/transcribe_video."
            )

        text = _read_text(p)
        notes.append("Unrecognized extension. Parsed as UTF-8 text.")
        return SourcePayload(str(p), "file-generic", text, notes)

    if args.source_url:
        text = _fetch_url(args.source_url)
        return SourcePayload(args.source_url, "url", text, notes)

    raise ValueError("No source input provided")


def _load_seed(args) -> str:
    if args.seed_text:
        return args.seed_text.strip()
    if args.seed_file:
        p = Path(args.seed_file)
        if not p.exists():
            raise FileNotFoundError(f"Seed file not found: {p}")
        return _read_text(p).strip()
    return ""


def _render_markdown(
    title: str,
    seed: str,
    payload: SourcePayload,
    image_notes: str,
    max_chars: int,
    provenance: str,
    semantic_query: str | None,
    semantic_anchors: List[SemanticAnchor],
) -> str:
    now = datetime.now(timezone.utc).date().isoformat()
    passages = _split_passages(payload.text, max_chars)
    source_word_count = len(payload.text.split())

    parts: List[str] = [
        "---",
        f"created: {now}",
        f"last_edited: {now}",
        "version: 1.0",
        f"provenance: {provenance}",
        "---",
        "",
        f"# {title}",
        "",
        "## Intake Metadata",
        f"- Source: `{payload.source_label}`",
        f"- Source kind: `{payload.source_kind}`",
        f"- Source words: {source_word_count}",
        f"- Passage chunks: {len(passages)}",
        f"- Seed context supplied: {'yes' if seed else 'no'}",
        f"- Semantic memory query supplied: {'yes' if semantic_query else 'no'}",
    ]

    if payload.notes:
        parts.append("- Notes:")
        for n in payload.notes:
            parts.append(f"  - {n}")

    parts.extend([
        "",
        "## Seed Context",
        seed if seed else "(none)",
        "",
        "## Source Text (Chronological Chunks)",
    ])

    if passages:
        for idx, chunk in enumerate(passages, start=1):
            parts.extend([
                f"### Chunk {idx}",
                chunk,
                "",
            ])
    else:
        parts.extend(["(no source text extracted)", ""])

    parts.extend([
        "## Image Notes",
        image_notes.strip() if image_notes else "(none)",
        "",
        "## Semantic Memory Anchors",
    ])

    if semantic_anchors:
        parts.append(f"Query: `{semantic_query}`")
        for idx, anchor in enumerate(semantic_anchors, start=1):
            parts.append(
                f"- {idx}. [{anchor.score:.2f}→{anchor.adjusted_score:.2f}] "
                f"{anchor.source} ({anchor.quality_tag}) — {anchor.snippet}"
            )
    else:
        parts.append("(none)")

    parts.extend([
        "",
        "## Integration Layer",
    ])
    parts.extend(_build_integration_layer(semantic_anchors))

    parts.extend([
        "",
        "## Analyst Execution Checklist",
        "- Absorb seed context first and state the active analytical frame in 1-2 lines.",
        "- Fill missing background via targeted research only where understanding gaps block analysis.",
        "- Distill the source into chronological bullet points in the exact order ideas appear.",
        "- Capture image-linked meaning if visuals are present.",
        "- Integrate source claims with the user's documented concepts, beliefs, or prior positions when semantic anchors are available.",
        "- Explicitly label: what aligns, what extends, and what conflicts/tensions with prior positions.",
        "- Explain concepts/terms likely unfamiliar to the reader.",
        "- Ask clarifying questions that move interpretation or action forward.",
        "- Invite active response: reactions, disagreements, and implications.",
        "- Ask whether to ingest final artifact to Content Library.",
        "",
        "## Response Capture Prompt",
        "Use this after presenting the analysis:",
        "- \"What is your immediate reaction in 1-3 lines?\"",
        "- \"Which single point do you agree with most, and which do you challenge?\"",
        "- \"Should I ingest this artifact to the Content Library now? (yes/no)\"",
        "",
    ])

    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a normalized analysis packet for the rapid-context-extractor skill"
    )
    parser.add_argument("--title", default="Rapid Context Extraction Packet")
    parser.add_argument("--seed-text")
    parser.add_argument("--seed-file")
    parser.add_argument("--source-text")
    parser.add_argument("--source-file")
    parser.add_argument("--source-url")
    parser.add_argument("--image-notes", default="")
    parser.add_argument("--max-chars", type=int, default=2400)
    parser.add_argument("--provenance")
    parser.add_argument("--semantic-query")
    parser.add_argument("--auto-semantic", action="store_true")
    parser.add_argument("--semantic-limit", type=int, default=5)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    source_count = sum(1 for v in [args.source_text, args.source_file, args.source_url] if v)
    if source_count != 1:
        raise ValueError("Provide exactly one source input: --source-text OR --source-file OR --source-url")

    seed_count = sum(1 for v in [args.seed_text, args.seed_file] if v)
    if seed_count > 1:
        raise ValueError("Provide at most one seed input: --seed-text OR --seed-file")

    seed = _load_seed(args)
    payload = _load_source(args)
    out = Path(args.output)
    provenance = _derive_provenance(out, args.provenance)
    semantic_query = args.semantic_query
    if args.auto_semantic and not semantic_query:
        semantic_query = _build_auto_semantic_query(payload, seed)
    semantic_anchors = _load_semantic_anchors(semantic_query, args.semantic_limit)
    packet = _render_markdown(
        title=args.title,
        seed=seed,
        payload=payload,
        image_notes=args.image_notes,
        max_chars=args.max_chars,
        provenance=provenance,
        semantic_query=semantic_query,
        semantic_anchors=semantic_anchors,
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(packet, encoding="utf-8")
    print(str(out.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
