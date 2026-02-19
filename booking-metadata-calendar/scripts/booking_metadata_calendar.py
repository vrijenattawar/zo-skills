#!/usr/bin/env python3
"""Booking metadata parser + calendar wiring + persistence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VALID_MEETING_INTENTS = {
    "partnership",
    "sales",
    "investor",
    "hiring",
    "intro",
    "advisory",
    "support",
    "internal-planning",
    "check-in",
    "other",
}
VALID_STRATEGIC_IMPORTANCE = {"high", "medium", "low"}
VALID_RELATIONSHIP_GOALS = {
    "deepen-trust",
    "advance-deal",
    "qualify-fit",
    "request-support",
    "offer-support",
    "maintain-cadence",
    "explore-opportunity",
    "other",
}
VALID_PROMOTION_BIAS = {"promote-now", "promote-if-novel", "archive-only"}


@dataclass
class BookingInput:
    message: str
    title: str
    start: str
    end: str
    timezone_name: str
    attendees: list[str]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _slugify(value: str) -> str:
    value = value.lower()
    value = value.replace("&", "and").replace("@", "at").replace("+", "plus")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "meeting"


def _meeting_id(title: str, start_iso: str) -> str:
    parsed = datetime.fromisoformat(start_iso)
    return f"{parsed.date().isoformat()}_{_slugify(title)[:64]}"


def _extract_expected_outputs(message: str) -> list[str]:
    text = _normalize(message)
    clauses = re.split(r"[.;]", text)
    outputs: list[str] = []
    triggers = ("want to", "need to", "goal is", "walk away with", "outcome", "next step")
    for clause in clauses:
        chunk = clause.strip(" -")
        if not chunk:
            continue
        if any(trigger in chunk for trigger in triggers):
            outputs.append(chunk)

    if outputs:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in outputs:
            clean = item.strip()
            if clean and clean not in seen:
                seen.add(clean)
                deduped.append(clean)
        if deduped:
            return deduped[:5]

    fallback_outputs = []
    if "intro" in text:
        fallback_outputs.append("establish context and define follow-up")
    if "decision" in text or "decide" in text:
        fallback_outputs.append("reach a decision and assign owner")
    if "next step" in text or "follow up" in text:
        fallback_outputs.append("clarify next steps and timeline")
    if not fallback_outputs:
        fallback_outputs.append("clarity on next step")
    return fallback_outputs


def _classify_meeting_intent(text: str) -> str:
    if any(k in text for k in ("partnership", "collab", "pilot")):
        return "partnership"
    if any(k in text for k in ("customer", "prospect", "deal", "sales", "demo")):
        return "sales"
    if any(k in text for k in ("investor", "fundraise", "funding", "seed", "series a")):
        return "investor"
    if any(k in text for k in ("candidate", "hiring", "interview", "recruit")):
        return "hiring"
    if "intro" in text or "introduction" in text:
        return "intro"
    if any(k in text for k in ("advisor", "advisory", "mentor")):
        return "advisory"
    if any(k in text for k in ("support", "help request")):
        return "support"
    if any(k in text for k in ("planning", "roadmap", "strategy", "alignment")):
        return "internal-planning"
    if any(k in text for k in ("check in", "catch up", "sync")):
        return "check-in"
    return "other"


def _classify_importance(text: str) -> str:
    high_terms = ("urgent", "critical", "strategic", "high stakes", "key decision", "investor")
    low_terms = ("casual", "light touch", "quick catch up", "optional")
    if any(term in text for term in high_terms):
        return "high"
    if any(term in text for term in low_terms):
        return "low"
    return "medium"


def _classify_relationship_goal(text: str, intent: str) -> str:
    if any(k in text for k in ("trust", "relationship", "rapport")):
        return "deepen-trust"
    if intent == "sales":
        return "advance-deal"
    if intent in {"hiring", "intro"}:
        return "qualify-fit"
    if any(k in text for k in ("need help", "ask for support", "request")):
        return "request-support"
    if any(k in text for k in ("offer support", "help them", "introduce them")):
        return "offer-support"
    if any(k in text for k in ("weekly", "monthly", "cadence", "check in")):
        return "maintain-cadence"
    if intent in {"partnership", "investor", "advisory"}:
        return "explore-opportunity"
    return "other"


def _classify_promotion_bias(text: str, importance: str) -> str:
    if any(k in text for k in ("archive only", "for record only", "no follow-up")):
        return "archive-only"
    if importance == "high" or any(k in text for k in ("must capture", "promote", "priority")):
        return "promote-now"
    return "promote-if-novel"


def parse_metadata(booking: BookingInput) -> dict[str, Any]:
    validate_booking_input(booking)
    text = _normalize(booking.message)
    intent = _classify_meeting_intent(text)
    importance = _classify_importance(text)
    relationship_goal = _classify_relationship_goal(text, intent)
    promotion_bias = _classify_promotion_bias(text, importance)

    metadata = {
        "meeting_intent": intent,
        "strategic_importance": importance,
        "expected_outputs": _extract_expected_outputs(booking.message),
        "relationship_goal": relationship_goal,
        "promotion_bias": promotion_bias,
        "parser_version": "1.0.0",
        "raw_booking_message": booking.message.strip(),
        "parsed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    validate_metadata(metadata)
    return metadata


def validate_booking_input(booking: BookingInput) -> None:
    if not booking.message.strip():
        raise ValueError("Booking message cannot be empty")
    if not booking.title.strip():
        raise ValueError("Booking title cannot be empty")

    try:
        start_dt = datetime.fromisoformat(booking.start)
    except ValueError as exc:
        raise ValueError("Invalid start timestamp. Use ISO 8601 format.") from exc
    try:
        end_dt = datetime.fromisoformat(booking.end)
    except ValueError as exc:
        raise ValueError("Invalid end timestamp. Use ISO 8601 format.") from exc

    if end_dt <= start_dt:
        raise ValueError("End timestamp must be after start timestamp")

    try:
        ZoneInfo(booking.timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Invalid timezone: {booking.timezone_name}") from exc


def validate_metadata(metadata: dict[str, Any]) -> None:
    if metadata.get("meeting_intent") not in VALID_MEETING_INTENTS:
        raise ValueError("Invalid meeting_intent")
    if metadata.get("strategic_importance") not in VALID_STRATEGIC_IMPORTANCE:
        raise ValueError("Invalid strategic_importance")
    if metadata.get("relationship_goal") not in VALID_RELATIONSHIP_GOALS:
        raise ValueError("Invalid relationship_goal")
    if metadata.get("promotion_bias") not in VALID_PROMOTION_BIAS:
        raise ValueError("Invalid promotion_bias")
    expected_outputs = metadata.get("expected_outputs", [])
    if not isinstance(expected_outputs, list) or not expected_outputs:
        raise ValueError("expected_outputs must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in expected_outputs):
        raise ValueError("expected_outputs must contain non-empty strings")


def build_calendar_payload(
    booking: BookingInput,
    meeting_id: str,
    metadata: dict[str, Any],
    metadata_path: Path,
    calendar_event_id: str | None = None,
) -> dict[str, Any]:
    return {
        "calendar_event_id": calendar_event_id,
        "title": booking.title,
        "start": booking.start,
        "end": booking.end,
        "timezone": booking.timezone_name,
        "attendees": booking.attendees,
        "description": (
            "BOOKING_METADATA\n"
            f"meeting_id: {meeting_id}\n"
            f"intent: {metadata['meeting_intent']}\n"
            f"strategic_importance: {metadata['strategic_importance']}\n"
            f"promotion_bias: {metadata['promotion_bias']}\n"
            f"metadata_ref: {metadata_path}\n"
        ),
    }


def persist_record(
    root: Path,
    meeting_id: str,
    booking: BookingInput,
    metadata: dict[str, Any],
    calendar_payload: dict[str, Any],
) -> Path:
    by_meeting_dir = root / "by_meeting"
    by_meeting_dir.mkdir(parents=True, exist_ok=True)
    registry_path = root / "registry.jsonl"

    record = {
        "meeting_id": meeting_id,
        "title": booking.title,
        "start": booking.start,
        "end": booking.end,
        "timezone": booking.timezone_name,
        "attendees": booking.attendees,
        "metadata": metadata,
        "calendar": calendar_payload,
        "stored_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    target_path = by_meeting_dir / f"{meeting_id}.json"
    target_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    registry_entry = {
        "meeting_id": meeting_id,
        "path": str(target_path),
        "calendar_event_id": calendar_payload.get("calendar_event_id"),
        "meeting_intent": metadata["meeting_intent"],
        "strategic_importance": metadata["strategic_importance"],
        "promotion_bias": metadata["promotion_bias"],
        "stored_at_utc": record["stored_at_utc"],
    }
    duplicate_found = False
    if registry_path.exists():
        for line in registry_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                row.get("meeting_id") == registry_entry["meeting_id"]
                and row.get("calendar_event_id") == registry_entry["calendar_event_id"]
            ):
                duplicate_found = True
    if not duplicate_found:
        with registry_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(registry_entry) + "\n")
    return target_path


def _booking_from_args(args: argparse.Namespace) -> BookingInput:
    attendees = [a.strip() for a in (args.attendees or "").split(",") if a.strip()]
    return BookingInput(
        message=args.message,
        title=args.title,
        start=args.start,
        end=args.end,
        timezone_name=args.timezone,
        attendees=attendees,
    )


def cmd_parse(args: argparse.Namespace) -> int:
    booking = _booking_from_args(args)
    metadata = parse_metadata(booking)
    print(json.dumps(metadata, indent=2))
    return 0


def cmd_book(args: argparse.Namespace) -> int:
    booking = _booking_from_args(args)
    metadata = parse_metadata(booking)
    meeting_id = args.meeting_id or _meeting_id(booking.title, booking.start)
    storage_root = Path(args.storage_root).resolve()
    metadata_path = storage_root / "by_meeting" / f"{meeting_id}.json"

    calendar_payload = build_calendar_payload(
        booking=booking,
        meeting_id=meeting_id,
        metadata=metadata,
        metadata_path=metadata_path,
        calendar_event_id=args.calendar_event_id,
    )
    target_path = persist_record(storage_root, meeting_id, booking, metadata, calendar_payload)
    print(
        json.dumps(
            {
                "meeting_id": meeting_id,
                "record_path": str(target_path),
                "calendar_payload": calendar_payload,
            },
            indent=2,
        )
    )
    return 0


def cmd_validate_cases(args: argparse.Namespace) -> int:
    cases_path = Path(args.cases_file).resolve()
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    for case in cases:
        booking = BookingInput(
            message=case["message"],
            title=case["title"],
            start=case["start"],
            end=case["end"],
            timezone_name=case.get("timezone", "America/New_York"),
            attendees=case.get("attendees", []),
        )
        metadata = parse_metadata(booking)
        if metadata["meeting_intent"] != case["expected"]["meeting_intent"]:
            failures.append(
                f"{case['id']}: intent={metadata['meeting_intent']} expected={case['expected']['meeting_intent']}"
            )
        if metadata["promotion_bias"] != case["expected"]["promotion_bias"]:
            failures.append(
                f"{case['id']}: promotion_bias={metadata['promotion_bias']} expected={case['expected']['promotion_bias']}"
            )

    result = {"total_cases": len(cases), "failures": failures, "passed": len(failures) == 0}
    print(json.dumps(result, indent=2))
    return 0 if not failures else 1


def parser() -> argparse.ArgumentParser:
    default_storage = "./N5/data/booking_metadata"
    default_cases = "./Skills/booking-metadata-calendar/references/validation-cases.json"

    p = argparse.ArgumentParser(description="Booking metadata + calendar integration utility")
    sub = p.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse", help="Parse NL booking message into structured metadata")
    parse_cmd.add_argument("--message", required=True)
    parse_cmd.add_argument("--title", required=True)
    parse_cmd.add_argument("--start", required=True, help="ISO 8601 start timestamp")
    parse_cmd.add_argument("--end", required=True, help="ISO 8601 end timestamp")
    parse_cmd.add_argument("--timezone", default="America/New_York")
    parse_cmd.add_argument("--attendees", default="")
    parse_cmd.set_defaults(func=cmd_parse)

    book_cmd = sub.add_parser("book", help="Parse, wire calendar payload, and persist metadata")
    book_cmd.add_argument("--message", required=True)
    book_cmd.add_argument("--title", required=True)
    book_cmd.add_argument("--start", required=True, help="ISO 8601 start timestamp")
    book_cmd.add_argument("--end", required=True, help="ISO 8601 end timestamp")
    book_cmd.add_argument("--timezone", default="America/New_York")
    book_cmd.add_argument("--attendees", default="")
    book_cmd.add_argument("--meeting-id", default="")
    book_cmd.add_argument("--calendar-event-id", default=None)
    book_cmd.add_argument("--storage-root", default=default_storage)
    book_cmd.set_defaults(func=cmd_book)

    validate_cmd = sub.add_parser(
        "validate-cases", help="Run representative parsing validation cases (minimum 3 intents)"
    )
    validate_cmd.add_argument("--cases-file", default=default_cases)
    validate_cmd.set_defaults(func=cmd_validate_cases)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
