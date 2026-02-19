#!/usr/bin/env python3
"""Tests for booking metadata + calendar flow."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from booking_metadata_calendar import (
    BookingInput,
    build_calendar_payload,
    parse_metadata,
    persist_record,
)


class BookingMetadataCalendarTests(unittest.TestCase):
    def test_parse_required_fields(self) -> None:
        booking = BookingInput(
            message="Strategic partnership call to align on pilot and next steps.",
            title="Partnership Call",
            start="2026-02-18T15:00:00-05:00",
            end="2026-02-18T15:45:00-05:00",
            timezone_name="America/New_York",
            attendees=["a@acme.com"],
        )
        metadata = parse_metadata(booking)
        self.assertEqual(metadata["meeting_intent"], "partnership")
        self.assertIn("strategic_importance", metadata)
        self.assertTrue(metadata["expected_outputs"])
        self.assertIn("relationship_goal", metadata)
        self.assertIn("promotion_bias", metadata)

    def test_end_to_end_persistence(self) -> None:
        booking = BookingInput(
            message="Investor update and key decision sync.",
            title="Investor Update",
            start="2026-02-19T10:00:00-05:00",
            end="2026-02-19T10:30:00-05:00",
            timezone_name="America/New_York",
            attendees=["partner@fund.com"],
        )
        metadata = parse_metadata(booking)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            meeting_id = "2026-02-19_investor-update"
            target = root / "by_meeting" / f"{meeting_id}.json"
            calendar = build_calendar_payload(
                booking=booking,
                meeting_id=meeting_id,
                metadata=metadata,
                metadata_path=target,
                calendar_event_id="cal_evt_123",
            )
            written = persist_record(root, meeting_id, booking, metadata, calendar)
            self.assertTrue(written.exists())
            record = json.loads(written.read_text(encoding="utf-8"))
            self.assertEqual(record["meeting_id"], meeting_id)
            self.assertEqual(record["calendar"]["calendar_event_id"], "cal_evt_123")
            self.assertIn("metadata_ref", record["calendar"]["description"])

    def test_validation_rejects_bad_time_range(self) -> None:
        booking = BookingInput(
            message="Quick sync",
            title="Bad Time",
            start="2026-02-19T10:30:00-05:00",
            end="2026-02-19T10:00:00-05:00",
            timezone_name="America/New_York",
            attendees=[],
        )
        with self.assertRaises(ValueError):
            parse_metadata(booking)

    def test_validation_rejects_blank_title(self) -> None:
        booking = BookingInput(
            message="Quick sync",
            title="   ",
            start="2026-02-19T10:00:00-05:00",
            end="2026-02-19T10:30:00-05:00",
            timezone_name="America/New_York",
            attendees=[],
        )
        with self.assertRaises(ValueError):
            parse_metadata(booking)

    def test_registry_deduplicates_same_meeting_and_event(self) -> None:
        booking = BookingInput(
            message="Investor update and key decision sync.",
            title="Investor Update",
            start="2026-02-19T10:00:00-05:00",
            end="2026-02-19T10:30:00-05:00",
            timezone_name="America/New_York",
            attendees=["partner@fund.com"],
        )
        metadata = parse_metadata(booking)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            meeting_id = "2026-02-19_investor-update"
            target = root / "by_meeting" / f"{meeting_id}.json"
            calendar = build_calendar_payload(
                booking=booking,
                meeting_id=meeting_id,
                metadata=metadata,
                metadata_path=target,
                calendar_event_id="cal_evt_123",
            )
            persist_record(root, meeting_id, booking, metadata, calendar)
            persist_record(root, meeting_id, booking, metadata, calendar)
            rows = [r for r in (root / "registry.jsonl").read_text(encoding="utf-8").splitlines() if r.strip()]
            self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
