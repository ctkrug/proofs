from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proof_factory import research_state, store, tactics


class TacticsValueScoringTests(unittest.TestCase):
    def test_value_per_cost_beats_stale_continuation(self) -> None:
        problem = {"id": "p", "statement": "Find x.", "verifiability": "Exact witness"}
        state = research_state._initial(problem)
        state["baseline_review"]["status"] = "complete"
        state["next_session"] = {"recommended_strategy_id": "expensive"}
        state["strategies"] = [
            {
                "id": "expensive", "fingerprint": "a", "family": "SAT", "mechanism": "repeat labelled solve",
                "status": "active", "attempts": 2, "hypothesis": "might help", "discriminating_test": "rerun",
                "route_evaluation": {
                    "gate_proximity": 0.1, "contribution_value": 0.2, "decisiveness": 0.2,
                    "novelty_confidence": 0.1, "novelty_risk": 0.9, "model_cost": 8,
                    "cpu_cost": 8, "scope": 0.1, "reuse_value": 0.1,
                },
            },
            {
                "id": "decisive", "fingerprint": "b", "family": "classification", "mechanism": "block every known class",
                "status": "proposed", "attempts": 0, "hypothesis": "a class remains", "discriminating_test": "complete boundary solve",
                "route_evaluation": {
                    "gate_proximity": 0.8, "contribution_value": 0.9, "decisiveness": 1.0,
                    "novelty_confidence": 0.8, "novelty_risk": 0.1, "model_cost": 0.4,
                    "cpu_cost": 1.0, "scope": 0.9, "reuse_value": 0.8,
                },
            },
        ]
        with patch.object(research_state, "load", return_value=state):
            brief = tactics.build(problem)
        self.assertEqual(brief["incumbent"]["strategy_id"], "decisive")
        stale = next(row for row in brief["portfolio"] if row["strategy_id"] == "expensive")
        self.assertEqual(stale["score_components"]["continuation_priority"], 30)
        self.assertEqual(stale["score_components"]["continuation_effective"], 3)
        self.assertGreater(brief["incumbent"]["value_per_cost"], stale["value_per_cost"])

    def test_missing_and_nonfinite_metrics_use_visible_safe_defaults(self) -> None:
        row = {
            "id": "legacy", "family": "theory", "mechanism": "derive an inequality", "status": "proposed",
            "route_evaluation": {"contribution_value": "bad", "model_cost": float("inf")},
        }
        scored = tactics._score_strategy(row, {"strategies": [row], "open_leads": [], "next_session": {}})
        self.assertEqual(scored["route_evaluation"]["contribution_value"], 0.5)
        self.assertEqual(scored["route_evaluation"]["model_cost"], 1.0)
        self.assertIn("gate_proximity", scored["route_evaluation_defaulted_fields"])


class ResearchStateReconciliationTests(unittest.TestCase):
    def test_terminal_and_orphaned_leads_are_closed_in_view(self) -> None:
        state = {
            "strategies": [
                {"id": "dead", "family": "SAT", "mechanism": "old sweep", "status": "exhausted"},
                {"id": "live", "family": "theory", "mechanism": "new inequality", "status": "active"},
            ],
            "open_leads": [
                {"id": "ld", "strategy_id": "dead", "description": "repeat", "status": "open"},
                {"id": "lo", "strategy_id": "missing", "description": "orphan", "status": "open"},
                {"id": "lm", "description": "unattached", "status": "open"},
                {"id": "ll", "strategy_id": "live", "description": "continue", "status": "open"},
            ],
        }
        result = research_state.reconcile_value(state, reconciled_at="2026-07-21T00:00:00Z")
        leads = {row["id"]: row for row in result["state"]["open_leads"]}
        self.assertEqual(leads["ld"]["closure_reason"], "terminal_strategy")
        self.assertEqual(leads["lo"]["closure_reason"], "orphaned_strategy")
        self.assertEqual(leads["lm"]["closure_reason"], "missing_strategy_id")
        self.assertEqual(leads["ll"]["status"], "open")
        self.assertEqual(state["open_leads"][0]["status"], "open")

    def test_empty_or_error_strategy_is_ineligible(self) -> None:
        problem = {"id": "p", "statement": "Find x."}
        state = research_state._initial(problem)
        state["baseline_review"]["status"] = "complete"
        state["strategies"] = [
            {"id": "bad", "family": "unspecified", "mechanism": "error", "status": "active"},
            {"id": "good", "family": "SAT", "mechanism": "canonical block", "status": "proposed"},
        ]
        with patch.object(research_state, "load", return_value=state):
            brief = tactics.build(problem)
        self.assertEqual(brief["incumbent"]["strategy_id"], "good")
        bad = next(row for row in brief["closed_routes"] if row["strategy_id"] == "bad")
        self.assertEqual(bad["ineligible_reason"], "terminal_status")
        self.assertIn("bad", brief["state_reconciliation"]["invalid_strategy_ids"])

    def test_reconcile_api_is_dry_run_by_default_and_can_write(self) -> None:
        problem = {"id": "p", "statement": "Find x."}
        state = research_state._initial(problem)
        state["strategies"] = [{"id": "dead", "family": "SAT", "mechanism": "sweep", "status": "blocked"}]
        state["open_leads"] = [{"id": "l", "strategy_id": "dead", "description": "retry", "status": "open"}]
        with tempfile.TemporaryDirectory() as raw, patch.object(store, "DATA", Path(raw)):
            path = research_state.state_path("p")
            path.parent.mkdir(parents=True)
            store.write_json_atomic(path, state)
            dry = research_state.reconcile(problem)
            self.assertFalse(dry["report"]["written"])
            self.assertEqual(store.read_json(path, {})["open_leads"][0]["status"], "open")
            written = research_state.reconcile(problem, write=True)
            self.assertTrue(written["report"]["written"])
            self.assertEqual(store.read_json(path, {})["open_leads"][0]["status"], "closed")

    def test_close_named_leads_records_reason_and_evidence(self) -> None:
        problem = {"id": "p", "statement": "Find x."}
        state = research_state._initial(problem)
        state["open_leads"] = [
            {"id": "resolved", "description": "authenticate corpus", "status": "open"},
            {"id": "keep", "description": "run discriminator", "status": "open"},
        ]
        with tempfile.TemporaryDirectory() as raw, patch.object(store, "DATA", Path(raw)):
            path = research_state.state_path("p")
            path.parent.mkdir(parents=True)
            store.write_json_atomic(path, state)
            result = research_state.close_leads(
                problem, ["resolved"], reason="control completed", evidence="sha256 manifest", actor="test",
            )
            saved = store.read_json(path, {})
        self.assertEqual(result["closed_lead_ids"], ["resolved"])
        self.assertEqual(saved["open_leads"][0]["closure_evidence"], "sha256 manifest")
        self.assertEqual(saved["open_leads"][1]["status"], "open")
        self.assertEqual(saved["tactical_memory"]["decision_history"][-1]["actor"], "test")


if __name__ == "__main__":
    unittest.main()
