from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proof_factory import events, store


class ResearchEventTests(unittest.TestCase):
    def test_event_is_required_evidence_and_consumed_once(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            state = root / "state"
            data.mkdir()
            problems = data / "problems.json"
            problems.write_text(json.dumps([{"id": "ramsey-r55"}]))
            with patch.multiple(
                store, ROOT=root, DATA=data, STATE=state, PROBLEMS_FILE=problems,
            ):
                self.assertEqual(events.pending("ramsey-r55"), [])
                event = events.enqueue(
                    "ramsey-r55", "lab_completed", evidence="checked result hash abc", source="job-1",
                )
                self.assertEqual([row["id"] for row in events.pending("ramsey-r55")], [event["id"]])
                consumed = events.consume("ramsey-r55", "attempt-1")
                self.assertEqual(consumed[0]["attempt_id"], "attempt-1")
                self.assertEqual(events.pending("ramsey-r55"), [])
                archived = json.loads((state / "research-events" / "archive" / f"{event['id']}.json").read_text())
                self.assertEqual(archived["attempt_id"], "attempt-1")

    def test_invalid_event_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            problems = data / "problems.json"
            problems.write_text(json.dumps([{"id": "ramsey-r55"}]))
            with patch.multiple(store, ROOT=root, DATA=data, STATE=root / "state", PROBLEMS_FILE=problems):
                with self.assertRaises(ValueError):
                    events.enqueue("ramsey-r55", "timer_tick", evidence="clock", source="timer")
                with self.assertRaises(ValueError):
                    events.enqueue("ramsey-r55", "source_changed", evidence="", source="source")

    def test_selected_consumption_leaves_unreviewed_events_pending(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            problems = data / "problems.json"
            problems.write_text(json.dumps([{"id": "p"}]))
            with patch.multiple(store, ROOT=root, DATA=data, STATE=root / "state", PROBLEMS_FILE=problems):
                first = events.enqueue("p", "lab_completed", evidence="job one", source="job-1")
                second = events.enqueue("p", "lab_completed", evidence="job two", source="job-2")
                consumed = events.consume("p", "attempt-1", event_ids={first["id"]})
                self.assertEqual([row["id"] for row in consumed], [first["id"]])
                self.assertEqual([row["id"] for row in events.pending("p")], [second["id"]])


if __name__ == "__main__":
    unittest.main()
