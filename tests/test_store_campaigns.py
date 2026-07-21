from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proof_factory import store


def problem(*, total: int, baseline: int = 100) -> dict[str, object]:
    return {
        "id": "p",
        "lane": "easy",
        "status": "active",
        "attempt_count": total,
        "research_attempt_count": total,
        "campaign_state": "active",
        "campaign_min_runs": 25,
        "campaign_start_research_attempt_count": baseline,
    }


def attempt(outcome: str, *, decision: str = "hold", close_signal: str = "") -> dict[str, object]:
    return {
        "id": f"attempt-{outcome}",
        "problem_id": "p",
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T00:01:00+00:00",
        "lane": "easy",
        "outcome": outcome,
        "summary": "bounded result",
        "campaign_assessment": {
            "decision": decision,
            "close_signal": close_signal,
            "reason": "predeclared review",
        },
    }


class StoreCampaignTransitionTests(unittest.TestCase):
    def test_hold_cannot_fire_before_campaign_local_minimum(self) -> None:
        value = problem(total=123)
        store._project_problem_from_attempt(value, attempt("no_progress"), {})
        self.assertEqual(store.discovery_campaign_run_count(value), 24)
        self.assertEqual(value["campaign_state"], "active")
        self.assertEqual(value["status"], "attempted")

    def test_blank_close_signal_holds_at_minimum(self) -> None:
        value = problem(total=124)
        store._project_problem_from_attempt(value, attempt("no_progress"), {})
        self.assertEqual(store.discovery_campaign_run_count(value), 25)
        self.assertEqual(value["campaign_state"], "hold")
        self.assertEqual(value["status"], "parked")

    def test_concrete_close_signal_continues_at_minimum(self) -> None:
        value = problem(total=124)
        store._project_problem_from_attempt(
            value,
            attempt("no_progress", decision="continue", close_signal="One checked cube remains."),
            {},
        )
        self.assertEqual(value["campaign_state"], "active")
        self.assertEqual(value["status"], "active")

    def test_candidate_enters_review_before_minimum(self) -> None:
        value = problem(total=100)
        store._project_problem_from_attempt(value, attempt("candidate"), {})
        self.assertEqual(store.discovery_campaign_run_count(value), 1)
        self.assertEqual(value["campaign_state"], "review")
        self.assertEqual(value["status"], "candidate")

    def test_error_counts_attempt_but_not_campaign_run(self) -> None:
        value = problem(total=100)
        store._project_problem_from_attempt(value, attempt("error"), {})
        self.assertEqual(value["attempt_count"], 101)
        self.assertEqual(value["research_attempt_count"], 100)
        self.assertEqual(store.discovery_campaign_run_count(value), 0)
        self.assertEqual(value["campaign_state"], "active")

    def test_legacy_campaign_without_baseline_uses_zero(self) -> None:
        value = {"research_attempt_count": 7}
        self.assertEqual(store.discovery_campaign_run_count(value), 7)

    def test_unknown_problem_is_rejected_before_ledger_append(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            problems_file = data / "problems.json"
            attempts_file = data / "attempts.jsonl"
            problems_file.write_text("[]")
            attempts_file.write_text("")
            value = attempt("progress")
            with patch.multiple(
                store,
                ROOT=root,
                DATA=data,
                STATE=root / "state",
                PROBLEMS_FILE=problems_file,
                ATTEMPTS_FILE=attempts_file,
            ):
                with self.assertRaisesRegex(ValueError, "unknown problem"):
                    store.record_attempt(value)
            self.assertEqual(attempts_file.read_text(), "")

    def test_duplicate_attempt_does_not_change_projection(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            problems_file = data / "problems.json"
            attempts_file = data / "attempts.jsonl"
            original = problem(total=100)
            problems_file.write_text(json.dumps([original]))
            value = attempt("progress", decision="continue", close_signal="bounded next step")
            attempts_file.write_text(json.dumps(value) + "\n")
            with patch.multiple(
                store,
                ROOT=root,
                DATA=data,
                STATE=root / "state",
                PROBLEMS_FILE=problems_file,
                ATTEMPTS_FILE=attempts_file,
            ):
                with self.assertRaisesRegex(ValueError, "duplicate attempt"):
                    store.record_attempt(value)
            self.assertEqual(json.loads(problems_file.read_text()), [original])
            self.assertEqual(len(attempts_file.read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
