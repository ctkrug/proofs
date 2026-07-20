from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proof_factory import agent, cli, intake, render, scheduler, scout, store


class ProofFactoryTests(unittest.TestCase):
    def test_initial_lane_selection(self) -> None:
        problems = store.load_problems()
        self.assertEqual(scheduler.choose_problem("hard", problems)["id"], "erdos-242")
        frontier = [
            {"id": "easy-first", "lane": "easy", "status": "queued", "difficulty": 4, "research_attempt_count": 0},
            {"id": "easy-next", "lane": "easy", "status": "queued", "difficulty": 6, "research_attempt_count": 0},
        ]
        self.assertEqual(scheduler.choose_problem("easy", frontier)["id"], "easy-first")
        frontier[0]["research_attempt_count"] = 1
        self.assertEqual(scheduler.choose_problem("easy", frontier)["id"], "easy-next")

    def test_parse_official_statement(self) -> None:
        page = '<div id="content">Is there an $n&gt;2$?<br>Exactly.</div>'
        self.assertEqual(intake.parse_statement(page), "Is there an $n>2$? Exactly.")

    def test_scout_requires_sourced_scored_candidate(self) -> None:
        text = '''```contribution_candidate
{"title":"One missing case","statement":"Determine exact X(7).","source_url":"https://example.test/paper","source_name":"Paper","problem_state":"open","contribution_type":"exact optimum","verifiability":"Witness and UNSAT certificate","rationale":"Adjacent cases are known","external_channel":"Maintained table","external_url":"https://example.test/table","estimated_success_probability":0.2,"difficulty":4,"verification_score":5,"contribution_score":3,"review_cost":2,"novelty_risk":3,"techniques":["SAT"]}
```'''
        value = scout.extract_candidate(text)
        self.assertEqual(value["contribution_type"], "exact optimum")

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

    def test_prompt_injects_computational_researcher_contract(self) -> None:
        problem = store.load_problems()[1]
        prompt = agent.build_prompt(problem, "hard", Path("/tmp/research/workspace"))
        self.assertIn("Maximize independently verifiable, net-new contribution", prompt)
        self.assertIn("run_experiment.py", prompt)
        self.assertIn("research_mode", prompt)

    def test_experiment_runner_records_reproducible_result(self) -> None:
        runner = Path(__file__).parents[1] / "skills" / "computational-researcher" / "scripts" / "run_experiment.py"
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "experiments"
            proc = subprocess.run([
                sys.executable, str(runner),
                "--name", "arithmetic-control",
                "--hypothesis", "six times seven is forty-two",
                "--expected-signal", "stdout is 42",
                "--timeout", "30",
                "--output-root", str(output),
                "--", sys.executable, "-c", "print(6 * 7)",
            ], text=True, capture_output=True, timeout=40)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            record = json.loads(proc.stdout)
            self.assertEqual(record["returncode"], 0)
            experiment_dir = Path(record["experiment_dir"])
            self.assertEqual((experiment_dir / "stdout.txt").read_text().strip(), "42")
            self.assertTrue((experiment_dir / "experiment.json").exists())

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

    def test_accept_and_release_builds_publication_packet(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            state = root / "state"
            data.mkdir()
            problem = {"id": "p", "title": "Tiny result", "status": "candidate", "source_url": "https://example.test"}
            attempt = {
                "id": "a", "problem_id": "p", "outcome": "candidate", "summary": "bounded claim",
                "rationale": "exact check", "claims": ["claim"], "evidence": ["checker"],
                "citations": ["https://example.test"], "techniques": ["enumeration"],
                "tool_disclosure": "AI and Python", "artifact_hashes": {"proof.txt": "abc"},
                "independent_checker": "A separately written checker reproduced the result.",
            }
            (data / "problems.json").write_text(json.dumps([problem]))
            (data / "attempts.jsonl").write_text(json.dumps(attempt) + "\n")
            (data / "reviews.json").write_text("[]\n")
            with patch.multiple(
                store, ROOT=root, DATA=data, STATE=state, SITE=root / "site",
                PROBLEMS_FILE=data / "problems.json", ATTEMPTS_FILE=data / "attempts.jsonl",
            ), patch.object(render, "build"):
                cli._review("a", "accept", "I reproduced the checker.", release=True)
                updated = store.load_problems()[0]
                self.assertEqual(updated["status"], "published")
                self.assertFalse(updated["accepted_result"])
                self.assertTrue((root / "publications" / "a" / "README.md").exists())
                self.assertIn("abc", (root / "publications" / "a" / "MANIFEST.sha256").read_text())
                cli._external_validation(
                    "a", "expert-confirmed", "https://example.test/review", "The source expert confirmed it."
                )
                self.assertTrue(store.load_problems()[0]["accepted_result"])

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

    def test_low_hanging_score_learns_from_accepted_techniques(self) -> None:
        win = {"id": "win", "accepted_result": True, "difficulty": 4, "techniques": ["SAT"], "contribution_type": "finite witness"}
        similar = {"id": "similar", "difficulty": 4, "techniques": ["SAT"], "contribution_type": "finite witness"}
        unrelated = {"id": "other", "difficulty": 4, "techniques": ["calculus"], "contribution_type": "lemma"}
        problems = [win, similar, unrelated]
        self.assertGreater(scheduler.low_hanging_score(similar, problems), scheduler.low_hanging_score(unrelated, problems))

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
