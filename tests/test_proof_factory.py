from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proof_factory import agent, cli, render, scheduler, store


class ProofFactoryTests(unittest.TestCase):
    def test_initial_lane_selection(self) -> None:
        problems = store.load_problems()
        self.assertEqual(scheduler.choose_problem("hard", problems)["id"], "erdos-242")
        self.assertEqual(scheduler.choose_problem("easy", problems)["id"], "erdos-647")

    def test_extract_structured_result(self) -> None:
        text = '''work\n```proof_result
{"outcome":"progress","approach":"one lemma","summary":"bounded result","rationale":"exact check","claims":[],"evidence":[],"next_steps":[],"citations":[],"techniques":[]}
```'''
        result = agent.extract_result(text)
        self.assertEqual(result["outcome"], "progress")

    def test_rejects_self_declared_solved_outcome(self) -> None:
        text = '''```proof_result
{"outcome":"solved","approach":"magic","summary":"done","rationale":"trust me","claims":[],"evidence":[],"next_steps":[],"citations":[],"techniques":[]}
```'''
        with self.assertRaises(ValueError):
            agent.extract_result(text)

    def test_human_gate_cannot_accept_non_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            state = root / "state"
            data.mkdir()
            (data / "problems.json").write_text(json.dumps([{"id": "p", "status": "attempted"}]))
            (data / "attempts.jsonl").write_text(json.dumps({
                "id": "a", "problem_id": "p", "outcome": "no_progress",
            }) + "\n")
            (data / "reviews.json").write_text("[]\n")
            with patch.multiple(
                store, ROOT=root, DATA=data, STATE=state, SITE=root / "site",
                PROBLEMS_FILE=data / "problems.json", ATTEMPTS_FILE=data / "attempts.jsonl",
            ):
                with self.assertRaises(ValueError):
                    cli._review("a", "accept", "reviewed")

    def test_record_attempt_is_append_only_and_updates_projection(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            problems_file = root / "data" / "problems.json"
            attempts_file = root / "data" / "attempts.jsonl"
            state_dir = root / "state"
            problems_file.parent.mkdir(parents=True)
            problems_file.write_text(json.dumps([{"id": "p", "status": "active", "attempt_count": 0}]))
            attempts_file.write_text("")
            attempt = {
                "id": "a1", "problem_id": "p", "started_at": "2026-01-01T00:00:00+00:00",
                "finished_at": "2026-01-01T00:01:00+00:00", "lane": "easy",
                "outcome": "failed", "summary": "route failed",
            }
            with patch.multiple(store, ROOT=root, DATA=root / "data", STATE=state_dir,
                                PROBLEMS_FILE=problems_file, ATTEMPTS_FILE=attempts_file):
                store.record_attempt(attempt)
                self.assertEqual(store.load_attempts()[0]["id"], "a1")
                problem = store.load_problems()[0]
                self.assertEqual(problem["attempt_count"], 1)
                self.assertEqual(problem["status"], "attempted")
                with self.assertRaises(ValueError):
                    store.record_attempt(attempt)

    def test_render_contains_statuses_sources_and_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            site = Path(raw) / "site"
            with patch.object(store, "SITE", site):
                render.build()
                index = (site / "index.html").read_text()
                self.assertIn("Every attempt", index)
                self.assertIn("Erdős–Straus conjecture", index)
                self.assertIn("Official source", index)
                self.assertTrue((site / "api" / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
