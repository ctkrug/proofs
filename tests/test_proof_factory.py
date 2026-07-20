from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from proof_factory import agent, brain, cli, contribution_gate, intake, lab, live, render, repositories, research_state, scheduler, scout, store, strategy_lab


class ProofFactoryTests(unittest.TestCase):
    def test_initial_lane_selection(self) -> None:
        problems = store.load_problems()
        self.assertEqual(scheduler.choose_problem("hard", problems)["id"], "ramsey-r55")
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
{"outcome":"candidate","title":"One missing case","statement":"Determine exact X(7).","source_url":"https://example.test/paper","source_name":"Paper","problem_state":"open","contribution_type":"exact optimum","verifiability":"Witness and UNSAT certificate","rationale":"Adjacent cases are known","external_channel":"Maintained table","external_url":"https://example.test/table","estimated_success_probability":0.2,"difficulty":4,"verification_score":5,"contribution_score":3,"review_cost":2,"novelty_risk":3,"techniques":["SAT"]}
```'''
        value = scout.extract_candidate(text)
        self.assertEqual(value["contribution_type"], "exact optimum")
        self.assertEqual(scout.extract_candidate('{"outcome":"no_candidate","reason":"No current source survived."}')["outcome"], "no_candidate")

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

    def test_contribution_gate_rejects_arbitrary_range_extension(self) -> None:
        result = {
            "candidate_profile": {
                "contribution_class": "bounded_extension",
                "scholarly_question": "Which restricted examples occur below B?",
                "meaningful_delta": "Raised B from 30,000 to 1,000,000.",
                "acceptance_test": "Reproduce the list.",
                "closest_prior_work": [{"url": "https://example.test/paper", "difference": "larger B"}],
                "novelty_searches": [
                    {"source": "arXiv", "query": "restricted examples", "url": "https://example.test/a", "finding": "none"},
                    {"source": "repository", "query": "example list", "url": "https://example.test/b", "finding": "none"},
                ],
                "external_channel": {"recipient": "Maintainer", "url": "https://example.test/channel", "acceptance_path": "email"},
                "independent_validations": [{"type": "formal_kernel", "validator": "Lean", "result": "accepted", "artifact": "proof.lean"}],
                "relevance": {"evidence_url": "https://example.test/paper"},
                "arbitrary_cutoff_extension": True,
            }
        }
        gate = contribution_gate.assess(result)
        self.assertFalse(gate["passed"])
        self.assertEqual(gate["status"], "internal_result")
        self.assertTrue(any("cutoff" in reason for reason in gate["reasons"]))

    def test_contribution_gate_accepts_exact_recognized_target(self) -> None:
        result = {
            "candidate_profile": {
                "contribution_class": "terminal_result",
                "scholarly_question": "Does the exact open target have a witness?",
                "meaningful_delta": "Supplies the first exact witness.",
                "acceptance_test": "Independent checker accepts the witness.",
                "closest_prior_work": [{"url": "https://example.test/problem", "difference": "open; no witness"}],
                "novelty_searches": [
                    {"source": "maintained registry", "query": "target", "url": "https://example.test/problem", "finding": "open"},
                    {"source": "arXiv", "query": "exact target", "url": "https://example.test/search", "finding": "no result"},
                ],
                "external_channel": {"recipient": "Registry maintainer", "url": "https://example.test/problem", "acceptance_path": "submit certificate"},
                "independent_validations": [{"type": "repository_ci", "validator": "maintained checker", "result": "accepted", "evidence_url": "https://example.test/ci"}],
                "relevance": {"settles_exact_open_target": True, "evidence_url": "https://example.test/problem"},
                "arbitrary_cutoff_extension": False,
            }
        }
        self.assertTrue(contribution_gate.assess(result)["passed"])

    def test_rejected_candidate_displays_as_internal_result(self) -> None:
        attempt = {"id": "a", "outcome": "candidate"}
        reviews = [{"decision": "reject", "display_status": "internal_result"}]
        self.assertEqual(render._effective_outcome(attempt, reviews), "internal_result")

    def test_internal_result_cannot_be_human_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            (data / "problems.json").write_text(json.dumps([{"id": "p", "status": "attempted"}]))
            (data / "attempts.jsonl").write_text(json.dumps({"id": "a", "problem_id": "p", "outcome": "candidate"}) + "\n")
            (data / "reviews.json").write_text(json.dumps([{"attempt_id": "a", "display_status": "internal_result"}]))
            with patch.multiple(
                store, ROOT=root, DATA=data, STATE=root / "state", SITE=root / "site",
                PROBLEMS_FILE=data / "problems.json", ATTEMPTS_FILE=data / "attempts.jsonl",
            ):
                with self.assertRaisesRegex(ValueError, "internal result"):
                    cli._review("a", "accept", "looks good")

    def test_prompt_injects_computational_researcher_contract(self) -> None:
        problem = store.load_problems()[1]
        prompt = agent.build_prompt(problem, "hard", Path("/tmp/research/workspace"), [{
            "role": "experiment-verification", "model": "gpt-5.6-terra",
            "status": "completed", "memo": "Use an exact checker before scaling.",
        }])
        self.assertIn("Maximize independently verifiable, net-new contribution", prompt)
        self.assertIn("run_experiment.py", prompt)
        self.assertIn("research_mode", prompt)
        self.assertIn("DURABLE RESEARCH STATE", prompt)
        self.assertIn("STRATEGY PORTFOLIO RULES", prompt)
        self.assertIn("indefinitely continuing", prompt)
        self.assertIn("reopen_condition", prompt)
        self.assertIn("SOL-TERRA ORCHESTRATION", prompt)
        self.assertIn("Use an exact checker before scaling.", prompt)
        self.assertIn("CROSS-PROBLEM RESEARCH BRAIN", prompt)
        self.assertIn("submit_lab.py", prompt)
        delegate = agent.build_delegate_prompt(problem, "hard", Path("/tmp/research/workspace"), "experiment-verification")
        self.assertIn("GPT-5.6 Terra delegate", delegate)
        self.assertIn("cheapest decisive experiment", delegate)
        self.assertIn("may not promote a result", delegate)
        baseline = agent.build_prompt(problem, "hard", Path("/tmp/research/workspace"), phase="baseline")
        self.assertIn("MANDATORY BASELINE PHASE", baseline)
        self.assertIn("Do not try to solve the problem", baseline)

    def test_hard_run_uses_terra_delegates_then_sol_principal(self) -> None:
        problem = {
            "id": "delegation-test", "title": "Finite test", "statement": "Find an exact witness.",
            "source_url": "https://example.test/problem", "problem_state": "open",
            "rationale": "Compact certificate", "verifiability": "Exact checker", "techniques": [],
        }
        principal = '''```proof_result
{"outcome":"progress","approach":"checked route","summary":"bounded result","rationale":"exact control","claims":[],"evidence":[],"next_steps":[],"citations":[],"techniques":[]}
```'''
        calls = []

        def fake_run(prompt, *, model, effort, workspace, timeout):
            calls.append((model, effort, workspace.name))
            if model == agent.TERRA_MODEL:
                return "Delegate memo with one falsifiable test.", {"output_tokens": 10}
            return principal, {"output_tokens": 20}

        with tempfile.TemporaryDirectory() as raw, patch.object(store, "RESEARCH", Path(raw)), \
                patch.object(agent, "_run_codex", side_effect=fake_run):
            attempt = agent.run(problem, "hard")

        self.assertEqual([row[0] for row in calls], [agent.TERRA_MODEL, agent.TERRA_MODEL, agent.SOL_MODEL])
        self.assertEqual(calls[-1][1], "high")
        self.assertEqual(attempt["orchestration"]["architecture"], "sol-principal-terra-delegates")
        self.assertEqual(attempt["orchestration"]["delegate_statuses"], {
            "literature-strategy": "completed", "experiment-verification": "completed",
        })
        self.assertEqual(attempt["model"], agent.SOL_MODEL)
        self.assertTrue(all(row["memo_sha256"] for row in attempt["delegates"]))

    def test_research_state_is_resumable_and_deduplicates_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            problem = {"id": "p", "statement": "Find x.", "verifiability": "Exact witness"}
            attempt = {
                "id": "a1", "finished_at": "2026-01-01T00:01:00+00:00", "outcome": "progress",
                "approach": "Exact residue search", "summary": "Three classes remain.",
                "strategy": {"family": "congruences", "mechanism": "partition residue classes"},
                "strategy_status": "promising", "established_facts": [{"claim": "Covers class 0", "scope": "mod 6", "evidence": "identity"}],
                "ruled_out": [{"claim_or_route": "linear family", "scope": "degree one", "reason": "coefficient contradiction", "reopen_condition": "allow degree two"}],
                "open_leads": [{"description": "try mod 12", "next_experiment": "enumerate exact residues", "status": "open"}],
                "continuation": {"objective": "cover the remainder", "first_action": "run residues.py", "stop_condition": "all classes covered or witness fails"},
            }
            with patch.multiple(store, ROOT=root, DATA=data):
                first = research_state.update_from_attempt(problem, attempt)
                attempt["id"] = "a2"
                second = research_state.update_from_attempt(problem, attempt)
                self.assertEqual(second["epoch_count"], 2)
                self.assertEqual(len(second["strategies"]), 1)
                self.assertEqual(second["strategies"][0]["attempts"], 2)
                self.assertEqual(second["next_session"]["first_action"], "run residues.py")
                prompt_state = research_state.compact_for_prompt(problem)
                self.assertIn("allow degree two", prompt_state)
                self.assertEqual(first["problem_id"], "p")

    def test_baseline_review_is_required_then_completed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            problem = {"id": "p", "statement": "Find x.", "verifiability": "Exact witness", "problem_state": "open"}
            attempt = {
                "id": "baseline-1", "finished_at": "2026-01-01T00:01:00+00:00", "outcome": "progress",
                "phase": "baseline", "approach": "source audit", "summary": "status and literature mapped",
                "established_facts": [{"claim": "Target is open", "evidence": "primary source"}],
                "ruled_out": [{"claim_or_route": "known route", "scope": "published case", "reason": "exhausted"}],
                "open_leads": [{"description": "test a finite case", "status": "open"}],
            }
            with patch.multiple(store, ROOT=root, DATA=data):
                self.assertTrue(research_state.needs_baseline(problem))
                state = research_state.update_from_attempt(problem, attempt)
                self.assertEqual(state["baseline_review"]["status"], "complete")
                self.assertFalse(research_state.needs_baseline(problem))

    def test_brain_links_problems_through_shared_concepts(self) -> None:
        problems = [
            {"id": "a", "title": "A", "techniques": ["SAT"], "lane": "easy", "status": "queued"},
            {"id": "b", "title": "B", "techniques": ["SAT", "graphs"], "lane": "hard", "status": "active"},
        ]
        with patch.object(research_state, "load_all", return_value={
            "a": research_state._initial({"id": "a"}), "b": research_state._initial({"id": "b"}),
        }):
            graph = brain.build(problems, [])
        links = [row for row in graph["edges"] if row["relation"] == "shares_concepts"]
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]["concepts"], ["SAT"])

    def test_simulation_lab_runs_shell_free_bounded_job(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            research = root / "research"
            state = root / "state"
            data.mkdir()
            (data / "problems.json").write_text(json.dumps([{"id": "p"}]))
            with patch.multiple(
                store, ROOT=root, DATA=data, RESEARCH=research, STATE=state,
                PROBLEMS_FILE=data / "problems.json", ATTEMPTS_FILE=data / "attempts.jsonl",
            ):
                submitted = lab.submit({
                    "problem_id": "p", "name": "control", "hypothesis": "six times seven is 42",
                    "expected_signal": "stdout contains 42", "command": ["python3", "-c", "print(6*7)"],
                    "segment_seconds": 60, "memory_mb": 128,
                })
                self.assertEqual(submitted["status"], "queued")
                result = lab.worker_once()
                self.assertEqual(result["status"], "completed", result)
                self.assertEqual(result["returncode"], 0)
                self.assertTrue((state / "labs" / "jobs.jsonl").is_file())

    def test_strategy_lab_requires_executable_sourced_proposal(self) -> None:
        text = '''```strategy_proposal
{"outcome":"proposal","action":"add","target_id":"","family":"finite model finding","use_when":"a bounded structure decides a lemma","mechanism":"enumerate canonical models and emit certificates","first_discriminator":"reproduce one known model","experiment_template":"p -> H -> SAT -> model -> first UNSAT","failure_modes":["bad encoding","shared checker"],"sources":["https://example.test/paper"],"change_rationale":"new exact evaluator"}
```'''
        self.assertEqual(strategy_lab.extract_proposal(text)["action"], "add")

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
            workspace = root / "research" / "p" / "workspace"
            workspace.mkdir(parents=True)
            (workspace / "proof.txt").write_text("certificate\n")
            artifact_hash = hashlib.sha256((workspace / "proof.txt").read_bytes()).hexdigest()
            attempt = {
                "id": "a", "problem_id": "p", "outcome": "candidate", "summary": "bounded claim",
                "rationale": "exact check", "claims": ["claim"], "evidence": ["checker"],
                "citations": ["https://example.test"], "techniques": ["enumeration"],
                "tool_disclosure": "AI and Python", "artifact_hashes": {"proof.txt": artifact_hash},
                "independent_checker": "A separately written checker reproduced the result.",
            }
            (data / "problems.json").write_text(json.dumps([problem]))
            (data / "attempts.jsonl").write_text(json.dumps(attempt) + "\n")
            (data / "reviews.json").write_text("[]\n")
            with patch.multiple(
                store, ROOT=root, DATA=data, STATE=state, SITE=root / "site", RESEARCH=root / "research",
                PROBLEMS_FILE=data / "problems.json", ATTEMPTS_FILE=data / "attempts.jsonl",
            ), patch.object(render, "build"):
                cli._review("a", "accept", "I reproduced the checker.", release=True)
                updated = store.load_problems()[0]
                self.assertEqual(updated["status"], "published")
                self.assertFalse(updated["accepted_result"])
                self.assertTrue((root / "publications" / "a" / "README.md").exists())
                self.assertIn(artifact_hash, (root / "publications" / "a" / "MANIFEST.sha256").read_text())
                self.assertEqual((root / "publications" / "a" / "artifacts" / "proof.txt").read_text(), "certificate\n")
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
                self.assertIn("Current", index)
                self.assertIn("Ongoing work", index)
                self.assertIn("Planned work", index)
                self.assertIn("Current schedule", index)
                self.assertIn("Next run", index)
                self.assertIn("Completed research passes", index)
                self.assertIn("What this run accomplished", index)
                self.assertIn("Ramsey campaign", index)
                self.assertIn("Open-problem program", index)
                self.assertNotIn(">hard</span>", index)
                self.assertNotIn(">easy</span>", index)
                self.assertNotIn("hard lane ·", index)
                self.assertNotIn("easy lane ·", index)
                self.assertIn("/assets/site-v4.css", index)
                self.assertIn("/assets/site-v4.js", index)
                self.assertIn("Ramsey number R(5,5)", index)
                self.assertIn("Official source", index)
                self.assertNotIn("Every attempt", index)
                self.assertNotIn("External wins", index)
                self.assertNotIn("/brain/", index)
                self.assertNotIn("/method/", index)
                self.assertNotIn("/api/", index)
                self.assertFalse((site / "api").exists())
                self.assertFalse((site / "brain").exists())
                self.assertTrue((site / "_worker.js").is_file())
                redirects = (site / "_redirects").read_text()
                self.assertIn("/brain/* / 301", redirects)
                self.assertIn("/api/* / 301", redirects)
                about = (site / "about" / "index.html").read_text()
                self.assertIn("no matter how small or large", about)

    def test_live_schedule_and_snapshot(self) -> None:
        now = datetime(2026, 7, 20, 20, 40, tzinfo=timezone.utc)
        self.assertEqual(live.next_hard_after(now).isoformat(), "2026-07-20T21:00:00+00:00")
        self.assertEqual(
            live.next_hard_after(datetime(2026, 7, 20, 20, 10, tzinfo=timezone.utc)).isoformat(),
            "2026-07-20T20:30:00+00:00",
        )
        self.assertEqual(live.next_easy_after(now).isoformat(), "2026-07-20T22:30:00+00:00")
        exact = datetime(2026, 7, 20, 22, 30, tzinfo=timezone.utc)
        self.assertEqual(live.next_easy_after(exact).isoformat(), "2026-07-21T00:30:00+00:00")

        problems = [{"id": "p", "title": "Test problem", "lane": "hard"}]
        attempts = [{
            "id": "a", "problem_id": "p", "lane": "hard", "outcome": "progress",
            "started_at": "2026-07-20T20:00:00+00:00", "finished_at": "2026-07-20T20:10:00+00:00",
            "duration_seconds": 600, "approach": "Exact search", "summary": "Eliminated two cases.",
            "next_steps": ["Check the remaining case."], "experiments": [{"name": "checker"}],
        }]
        runtime = {
            "hard_running": "p", "hard_started_at": "2026-07-20T20:35:00+00:00",
            "hard_last_attempt_at": "2026-07-20T20:10:00+00:00", "hard_last_outcome": "progress",
            "health": "healthy", "updated_at": "2026-07-20T20:40:00+00:00",
        }
        value = live.snapshot(problems, attempts, runtime, now=now)
        self.assertEqual(value["lanes"]["hard"]["status"], "running")
        self.assertEqual(value["lanes"]["hard"]["running_problem_title"], "Test problem")
        self.assertEqual(value["recent_runs"][0]["accomplishment"], "Eliminated two cases.")
        self.assertEqual(value["recent_runs"][0]["next_action"], "Check the remaining case.")

    def test_render_uses_shared_process_lock(self) -> None:
        events: list[str] = []

        class Lock:
            def __enter__(self) -> bool:
                events.append("enter")
                return True

            def __exit__(self, *args: object) -> None:
                events.append("exit")

        with patch.object(store, "lock", return_value=Lock()) as lock, \
             patch.object(render, "_build_unlocked", return_value=Path("/tmp/site")):
            self.assertEqual(render.build(), Path("/tmp/site"))

        lock.assert_called_once_with("render")
        self.assertEqual(events, ["enter", "exit"])

    def test_problem_repository_checkpoints_attempt_and_large_artifact_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            research = root / "research"
            state = root / "state"
            data.mkdir()
            (data / "research_states").mkdir()
            problem = {
                "id": "test-problem", "title": "Test problem", "statement": "Find x.",
                "source_url": "https://example.test/problem", "lane": "easy", "status": "active",
            }
            problems_file = data / "problems.json"
            attempts_file = data / "attempts.jsonl"
            problems_file.write_text(json.dumps([problem]))
            attempts_file.write_text("")
            store.write_json_atomic(data / "research_states" / "test-problem.json", {
                "schema_version": 1, "problem_id": "test-problem", "epoch_count": 1,
            })
            dossier = research / "test-problem" / "DOSSIER.md"
            dossier.parent.mkdir(parents=True)
            dossier.write_text("# Prior work\n")
            attempt = {
                "id": "test-problem-20260720-000000-abc123", "problem_id": "test-problem",
                "started_at": "2026-07-20T00:00:00+00:00", "finished_at": "2026-07-20T00:01:00+00:00",
                "lane": "easy", "phase": "baseline", "outcome": "progress", "approach": "Exact check",
                "summary": "Recorded one bounded fact.", "claims": ["x=1 in the checked case"],
                "evidence": ["checker.py"], "citations": ["https://example.test/problem"],
                "tool_disclosure": "Python", "orchestration": {"architecture": "sol-principal-terra-delegates"},
            }
            with patch.multiple(
                store, ROOT=root, DATA=data, RESEARCH=research, STATE=state,
                PROBLEMS_FILE=problems_file, ATTEMPTS_FILE=attempts_file,
            ), patch.object(repositories, "MAX_TRACKED_FILE_BYTES", 10_000):
                info = repositories.ensure(problem)
                repo = Path(info["path"])
                (repo / "checker.py").write_text("print(1)\n")
                (repo / "raw.bin").write_bytes(b"x" * 20_000)
                result = repositories.record_attempt(problem, attempt)
                self.assertEqual(len(result["commit"]), 40)
                self.assertTrue((repo / "records" / "attempts" / f"{attempt['id']}.json").is_file())
                self.assertTrue((repo / "records" / "attempts" / f"{attempt['id']}.md").is_file())
                self.assertEqual((repo / "docs" / "DOSSIER.md").read_text(), "# Prior work\n")
                self.assertEqual(
                    subprocess.run(
                        ["git", "-C", str(repo), "config", "user.name"],
                        text=True, capture_output=True, check=True,
                    ).stdout.strip(),
                    "ctkrug",
                )
                metadata = json.loads((repo / ".proof-repository" / "metadata.json").read_text())
                self.assertEqual(metadata["visibility_policy"], "public-research-history")
                manifest = json.loads((repo / ".proof-repository" / "LARGE_ARTIFACTS.json").read_text())
                self.assertEqual(manifest["files"][0]["path"], "raw.bin")
                self.assertEqual(
                    subprocess.run(
                        ["git", "-C", str(repo), "rev-list", "--count", "HEAD"],
                        text=True, capture_output=True, check=True,
                    ).stdout.strip(),
                    "2",
                )
                tracked = subprocess.run(
                    ["git", "-C", str(repo), "ls-files"], text=True, capture_output=True, check=True,
                ).stdout.splitlines()
                self.assertIn("checker.py", tracked)
                self.assertNotIn("raw.bin", tracked)


if __name__ == "__main__":
    unittest.main()
