from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from proof_factory import agent, brain, briefing, capacity, cli, contribution_gate, intake, lab, live, prior_art, render, repositories, research_state, roadmap, scheduler, scout, store, strategy_lab, tactics, usage


class ProofFactoryTests(unittest.TestCase):
    def test_result_json_rejects_duplicate_keys(self) -> None:
        text = '''```proof_result
{"outcome":"progress","outcome":"failed","approach":"a","summary":"s","rationale":"r"}
```'''
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            agent.extract_result(text)

    def test_agent_prompt_routes_lab_evidence_to_immutable_records(self) -> None:
        source = (store.ROOT / "proof_factory" / "agent.py").read_text()
        self.assertIn("`lab-archive/**`", source)
        self.assertIn("immutable `records/labs/**` record", source)

    def test_formal_conjectures_bootstrap_is_hash_locked(self) -> None:
        script = (store.ROOT / "scripts" / "bootstrap-formal-conjectures.sh").read_text()
        self.assertIn("b8b5208aa5d01f5f91c49ca516bf09cae8d93693", script)
        self.assertIn("5b99b5f4f807cbba67bbcd22e5e486c17d6a8d970ea218de08d05830ab350c26", script)
        self.assertNotIn('"$elan_home/bin/lake" update', script)
        self.assertIn('if [[ "$lock_acquired" != true ]]', script)
        self.assertIn("FormalConjecturesUtil.olean was not produced", script)

    def test_ramsey_brief_is_bounded_valid_json_and_selects_seeded_route(self) -> None:
        problem = next(row for row in store.load_problems() if row["id"] == "ramsey-r55")
        packet = briefing.compact_for_prompt(problem)
        decoded = json.loads(packet)
        self.assertLessEqual(len(packet), 24000)
        self.assertEqual(decoded["tactics"]["incumbent"]["fingerprint"], "r55knownclassembeddingblock2026")
        prompt = agent.build_prompt(problem, "hard", store.RESEARCH / problem["id"] / "workspace", phase="research")
        self.assertLessEqual(len(prompt), 50000)
        self.assertIn("deliberately invalidates the", prompt)
        self.assertIn("records/research-state.json", prompt)

    def test_ramsey_brief_emergency_compaction_handles_event_accumulation(self) -> None:
        problem = next(row for row in store.load_problems() if row["id"] == "ramsey-r55")
        payload = briefing.build(problem)
        payload["research_events"] = [
            {"id": f"event-{index}", "kind": "lab_completed", "created_at": store.now_iso(),
             "evidence": "e" * 4000, "source": "state/labs/jobs/job.json"}
            for index in range(10)
        ]
        with patch.object(briefing, "build", return_value=payload):
            compact = briefing.compact_for_prompt(problem, max_chars=18000)
        self.assertLessEqual(len(compact), 18000)
        self.assertEqual(len(json.loads(compact)["research_events"]), 3)

    def test_initial_lane_selection(self) -> None:
        problems = store.load_problems()
        self.assertEqual(scheduler.choose_problem("hard", problems)["id"], "ramsey-r55")
        frontier = [
            {"id": "easy-first", "lane": "easy", "status": "queued", "difficulty": 4, "research_attempt_count": 0},
            {"id": "easy-next", "lane": "easy", "status": "queued", "difficulty": 6, "research_attempt_count": 0},
        ]
        self.assertEqual(scheduler.choose_problem("easy", frontier)["id"], "easy-first")
        frontier[0]["research_attempt_count"] = 1
        self.assertEqual(scheduler.choose_problem("easy", frontier)["id"], "easy-first")
        frontier[1]["campaign_state"] = "active"
        frontier[1]["campaign_started_at"] = "2026-07-21T00:00:00+00:00"
        self.assertEqual(scheduler.choose_problem("easy", frontier)["id"], "easy-next")

    def test_parse_official_statement(self) -> None:
        page = '<div id="content">Is there an $n&gt;2$?<br>Exactly.</div>'
        self.assertEqual(intake.parse_statement(page), "Is there an $n>2$? Exactly.")

    def test_scout_requires_sourced_scored_candidate(self) -> None:
        text = '''```contribution_candidate
{"outcome":"candidate","title":"One missing case","statement":"Determine exact X(7).","source_url":"https://example.test/paper","source_name":"Paper","problem_state":"open","contribution_type":"exact optimum","verifiability":"Witness and UNSAT certificate","rationale":"Adjacent cases are known","external_channel":"Maintained table","external_url":"https://example.test/table","upstream_work_check":{"active_prs":0,"checked_url":"https://example.test/issues/7","checked_at":"2026-07-21","evidence":"no linked PR"},"estimated_success_probability":0.2,"difficulty":4,"verification_score":5,"contribution_score":3,"review_cost":2,"novelty_risk":3,"techniques":["SAT"]}
```'''
        value = scout.extract_candidate(text)
        self.assertEqual(value["contribution_type"], "exact optimum")
        self.assertEqual(scout.extract_candidate('{"outcome":"no_candidate","reason":"No current source survived."}')["outcome"], "no_candidate")

    def test_extract_structured_result(self) -> None:
        text = '''work\n```proof_result
{"outcome":"progress","approach":"one lemma","summary":"bounded result","rationale":"exact check","search_efficiency":{"naive_space":"proof-only; no candidate sweep","reductions_considered":["symbolic simplification"],"chosen_mechanism":"direct lemma","estimated_or_measured_savings":"not applicable","soundness_guard":"ordinary proof checking"},"space_reduction":{"ambient_space":"proof states","represented_space_before":"one goal","eliminated_or_quotiented":"one lemma discharged","represented_space_after":"next goal","reduction_factor":"not applicable","measurement_status":"not_applicable","unit":"proof states","coverage_scope":"single lemma","soundness_basis":"ordinary proof checking","remaining_unknown":"remaining theorem","next_bulk_elimination":"derive next lemma"},"tactical_learning":{"prediction":"lemma holds","observation":"lemma holds","surprise":"none","failure_signature":"none","bottleneck_update":"next lemma","reusable_assets":[],"constraints_learned":[],"route_decision":"continue","next_discriminator":"test next lemma"},"prior_art_check":{"nearest_method_ids":["none-found"],"classification":"genuinely_different","exact_delta":"direct lemma beyond baseline","duplicate_risk":"may restate a known lemma","comparison_test":"compare exact theorem statements","decision":"proceed","source_urls":["https://example.test/source"]},"field_progress_assessment":{"status":"not_met","gate_id":"none","contribution_class":"internal lemma","closest_prior_result":"baseline","measurable_improvement":"none","independent_validation":"proof check","external_audience":"none","remains_unproved":"target","route_recommendation":"continue bounded route"},"claims":[],"evidence":[],"next_steps":[],"citations":[],"techniques":[]}
```'''
        result = agent.extract_result(text)
        self.assertEqual(result["outcome"], "progress")

    def test_structured_result_requires_search_efficiency_audit(self) -> None:
        text = '''```proof_result
{"outcome":"progress","approach":"one lemma","summary":"bounded result","rationale":"exact check","claims":[],"evidence":[],"next_steps":[],"citations":[],"techniques":[]}
```'''
        with self.assertRaisesRegex(ValueError, "search_efficiency"):
            agent.extract_result(text)

    def test_structured_result_requires_tactical_learning(self) -> None:
        text = '''```proof_result
{"outcome":"progress","approach":"one lemma","summary":"bounded result","rationale":"exact check","search_efficiency":{"naive_space":"proof-only","reductions_considered":["symbolic"],"chosen_mechanism":"direct","estimated_or_measured_savings":"n/a","soundness_guard":"proof check"},"space_reduction":{"ambient_space":"proof states","represented_space_before":"one goal","eliminated_or_quotiented":"none","represented_space_after":"one goal","reduction_factor":"none","measurement_status":"not_applicable","unit":"proof states","coverage_scope":"one goal","soundness_basis":"none","remaining_unknown":"goal","next_bulk_elimination":"prove lemma"},"claims":[],"evidence":[],"next_steps":[],"citations":[],"techniques":[]}
```'''
        with self.assertRaisesRegex(ValueError, "tactical_learning"):
            agent.extract_result(text)

    def test_structured_result_requires_space_reduction_ledger(self) -> None:
        text = '''```proof_result
{"outcome":"progress","approach":"one lemma","summary":"bounded result","rationale":"exact check","search_efficiency":{"naive_space":"proof-only","reductions_considered":["symbolic"],"chosen_mechanism":"direct","estimated_or_measured_savings":"n/a","soundness_guard":"proof check"},"claims":[],"evidence":[],"next_steps":[],"citations":[],"techniques":[]}
```'''
        with self.assertRaisesRegex(ValueError, "space_reduction"):
            agent.extract_result(text)

    def test_rejects_self_declared_solved_outcome(self) -> None:
        text = '''```proof_result
{"outcome":"solved","approach":"magic","summary":"done","rationale":"trust me","claims":[],"evidence":[],"next_steps":[],"citations":[],"techniques":[]}
```'''
        with self.assertRaises(ValueError):
            agent.extract_result(text)

    def test_result_schema_drives_error_stub_projection_and_synthesis_persistence(self) -> None:
        problem = {
            "id": "schema-sync", "title": "Finite test", "statement": "Check one case.",
            "source_url": "https://example.test/problem", "problem_state": "open",
            "rationale": "Exact", "verifiability": "Exact checker", "techniques": [],
        }
        result = agent._error_result(problem, agent.SOL_MODEL, RuntimeError("fixture"))
        candidates = [{
            "family": f"composite-{index}",
            "mechanism": "combine two exact filters",
            "parent_strategy_ids": ["strategy-a", "strategy-b"],
            "source_inputs": ["filter a", "filter b"],
            "transfer_hypothesis": "the filters eliminate complementary cases",
            "discriminating_test": "compare one bounded fixture",
            "falsification_signal": "no matched reduction",
            "rationale": "mechanism-level composition",
        } for index in range(35)]
        result.update({
            "outcome": "no_progress",
            "approach": "x" * 4100,
            "summary": "bounded schema control",
            "rationale": "exact serialization check",
            "synthesis_candidates": candidates,
        })
        encoded = f"```proof_result\n{json.dumps(result)}\n```"
        validated = agent.extract_result(encoded)
        projection = agent._project_result(validated)
        self.assertEqual(len(projection["approach"]), 4000)
        self.assertEqual(len(projection["synthesis_candidates"]), 30)
        self.assertEqual(projection["synthesis_candidates"][-1]["family"], "composite-29")
        self.assertEqual(projection["lab_review"], {"decision": "none"})

        def fake_run(prompt, *, model, effort, workspace, timeout, telemetry_meta=None):
            if model == agent.TERRA_MODEL:
                return "bounded source-discriminator memo", {}
            return encoded, {}

        with tempfile.TemporaryDirectory() as raw, patch.object(store, "RESEARCH", Path(raw)), \
                patch.object(agent, "_run_codex", side_effect=fake_run):
            attempt = agent.run(problem, "easy")
        self.assertEqual(attempt["synthesis_candidates"], candidates[:30])

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

    def test_contribution_gate_rejects_hostless_urls_and_string_booleans(self) -> None:
        result = {
            "candidate_profile": {
                "contribution_class": "terminal_result",
                "scholarly_question": "Does the target hold?",
                "meaningful_delta": "Claims to settle it.",
                "acceptance_test": "Replay the proof.",
                "closest_prior_work": [{"url": "https:", "difference": "claimed delta"}],
                "novelty_searches": [
                    {"source": "a", "query": "q", "url": "https:", "finding": "none"},
                    {"source": "b", "query": "q", "url": "https:", "finding": "none"},
                ],
                "external_channel": {
                    "recipient": "Maintainer", "url": "https:", "acceptance_path": "submit",
                },
                "independent_validations": [{
                    "type": "formal_kernel", "validator": "checker", "result": "accepted",
                    "artifact": "proof",
                }],
                "relevance": {"settles_exact_open_target": "false", "evidence_url": "https:"},
                "arbitrary_cutoff_extension": "false",
            }
        }
        gate = contribution_gate.assess(result)
        self.assertFalse(gate["passed"])
        self.assertTrue(any("booleans" in reason for reason in gate["reasons"]))

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
        self.assertIn("SEARCH-EFFICIENCY PASS", prompt)
        self.assertIn("search_efficiency", prompt)
        self.assertIn("space_reduction", prompt)
        self.assertIn("bulk class/cube/profile elimination", prompt)
        self.assertIn("DETERMINISTIC TACTICAL BRIEF", prompt)
        self.assertIn("AUTOMATED CAMPAIGN ROADMAP", prompt)
        self.assertIn("PRIOR-ART ANTI-REDISCOVERY REGISTER", prompt)
        self.assertIn("prior_art_check", prompt)
        self.assertIn("tactical_learning", prompt)
        self.assertLess(prompt.index("OPERATING SKILL"), prompt.index("CURRENT TASK STATEMENT"))
        self.assertLess(prompt.index("ACCEPTABLE CONTRIBUTIONS"), prompt.index("CURRENT TASK STATEMENT"))
        self.assertLess(prompt.index("11. End with exactly one fenced JSON block"), prompt.index("CURRENT TASK STATEMENT"))
        self.assertLess(prompt.index("SOL-TERRA ORCHESTRATION"), prompt.index("CURRENT TASK STATEMENT"))
        delegate = agent.build_delegate_prompt(problem, "hard", Path("/tmp/research/workspace"), "experiment-verification")
        self.assertIn("GPT-5.6 Terra delegate", delegate)
        self.assertIn("cheapest decisive experiment", delegate)
        self.assertIn("may not promote a result", delegate)
        self.assertIn("search-efficiency pass", delegate)
        self.assertIn("PRIOR-ART ANTI-REDISCOVERY REGISTER", delegate)
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
{"outcome":"progress","approach":"checked route","summary":"bounded result","rationale":"exact control","search_efficiency":{"naive_space":"finite test space","reductions_considered":["bitsets"],"chosen_mechanism":"batched exact checker","estimated_or_measured_savings":"2x expected","soundness_guard":"independent scalar replay"},"space_reduction":{"ambient_space":"finite test space","represented_space_before":"100 cases","eliminated_or_quotiented":"50 exact failures","represented_space_after":"50 cases","reduction_factor":"2x","measurement_status":"exact","unit":"labelled assignments","coverage_scope":"bounded fixture","soundness_basis":"independent scalar replay","remaining_unknown":"50 cases","next_bulk_elimination":"canonicalize classes"},"tactical_learning":{"prediction":"find signal","observation":"bounded result","surprise":"none","failure_signature":"none","bottleneck_update":"larger exact test","reusable_assets":[],"constraints_learned":[],"route_decision":"continue","next_discriminator":"larger pilot"},"prior_art_check":{"nearest_method_ids":["none-found"],"classification":"material_modification","exact_delta":"batched checker compared with scalar baseline","duplicate_risk":"speedup may be implementation-only","comparison_test":"matched scalar replay","decision":"proceed","source_urls":["https://example.test/source"]},"field_progress_assessment":{"status":"not_met","gate_id":"none","contribution_class":"verified internal experiment","closest_prior_result":"baseline","measurable_improvement":"none","independent_validation":"scalar replay","external_audience":"none","remains_unproved":"target","route_recommendation":"continue bounded route"},"claims":[],"evidence":[],"next_steps":[],"citations":[],"techniques":[]}
```'''
        calls = []

        def fake_run(prompt, *, model, effort, workspace, timeout, telemetry_meta=None):
            calls.append((model, effort, workspace.name))
            if model == agent.TERRA_MODEL:
                return "Delegate memo with one falsifiable test.", {"output_tokens": 10}
            if effort == "high":
                return ('{"outcome":"progress","classification":"material_modification",'
                        '"field_progress_assessment":{"status":"not_met"}'), {"output_tokens": 5}
            return principal, {"output_tokens": 20}

        with tempfile.TemporaryDirectory() as raw, patch.object(store, "RESEARCH", Path(raw)), \
                patch.object(agent, "_run_codex", side_effect=fake_run), \
                patch.object(briefing, "build", wraps=briefing.build) as briefing_build:
            attempt = agent.run(problem, "hard")

            self.assertEqual([row[0] for row in calls].count(agent.TERRA_MODEL), 2)
            self.assertEqual([row[:2] for row in calls[-2:]], [
                (agent.SOL_MODEL, "high"), (agent.SOL_MODEL, "low"),
            ])
            self.assertEqual(briefing_build.call_count, 1)
        self.assertEqual(attempt["orchestration"]["architecture"], "sol-principal-terra-delegates")
        self.assertEqual(attempt["orchestration"]["delegate_statuses"], {
                "challenger-prior-art": "completed", "experiment-verification": "completed",
        })
        self.assertEqual(attempt["model"], agent.SOL_MODEL)
        self.assertTrue(attempt["json_repair"]["attempted"])
        self.assertTrue(attempt["json_repair"]["used"])
        self.assertTrue(all(row["memo_sha256"] for row in attempt["delegates"]))

    def test_delegate_count_adapts_to_admitting_event(self) -> None:
        self.assertEqual(agent.delegate_roles("hard", [{"kind": "lab_segment_completed"}]), ())
        self.assertEqual(
            agent.delegate_roles("hard", [{"kind": "lab_completed"}]),
            ("experiment-verification",),
        )
        self.assertEqual(
            agent.delegate_roles("hard", [{"kind": "source_changed"}]),
            ("challenger-prior-art", "experiment-verification"),
        )
        self.assertEqual(agent.delegate_roles("easy", []), ("source-discriminator",))

    def test_json_repair_fails_closed_and_cannot_upgrade(self) -> None:
        repaired = {
            "outcome": "candidate",
            "prior_art_check": {"classification": "genuinely_different"},
            "field_progress_assessment": {"status": "met"},
        }
        original = ('{"outcome":"no_progress","classification":"replication_control",'
                    '"field_progress_assessment":{"status":"not_met"}}')
        with self.assertRaisesRegex(ValueError, "protected field outcome"):
            agent._enforce_repair_guard(original, repaired)

        problem = {
            "id": "repair-failure", "title": "Finite test", "statement": "Check one case.",
            "source_url": "https://example.test/problem", "problem_state": "open",
            "rationale": "Exact", "verifiability": "Exact checker", "techniques": [],
        }
        calls = []

        def never_repairs(prompt, *, model, effort, workspace, timeout, telemetry_meta=None):
            calls.append((model, effort))
            if model == agent.TERRA_MODEL:
                return "memo", {}
            return ('{"outcome":"no_progress","classification":"replication_control",'
                    '"field_progress_assessment":{"status":"not_met"}'), {}

        with tempfile.TemporaryDirectory() as raw, patch.object(store, "RESEARCH", Path(raw)), \
                patch.object(agent, "_run_codex", side_effect=never_repairs):
            attempt = agent.run(problem, "hard")
        self.assertEqual(attempt["outcome"], "error")
        self.assertTrue(attempt["json_repair"]["attempted"])
        self.assertFalse(attempt["json_repair"]["used"])
        self.assertEqual(calls[-1], (agent.SOL_MODEL, "low"))

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
                "synthesis_candidates": [{
                    "family": "constraint-guided residue SAT",
                    "mechanism": "feed residue exclusions into a canonical SAT cube generator",
                    "parent_strategy_ids": ["strategy-existing-residues", "strategy-existing-cubes"],
                    "source_inputs": ["this problem's residue checker", "Ramsey canonical cube method"],
                    "transfer_hypothesis": "residue constraints reduce the canonical cube branching factor",
                    "discriminating_test": "compare 100 constrained and unconstrained cubes",
                    "falsification_signal": "no reduction in solved cube count under matched calls",
                    "rationale": "combines two mechanisms rather than renaming either one",
                }],
                "continuation": {"objective": "cover the remainder", "first_action": "run residues.py", "stop_condition": "all classes covered or witness fails"},
                "tactical_learning": {
                    "prediction": "new residue classes", "observation": "same obstruction", "surprise": "no new classes",
                    "failure_signature": "residue partition stalls on class 5", "bottleneck_update": "class 5",
                    "reusable_assets": [{"name": "residue checker", "use": "exact replay", "evidence": "checker.py"}],
                    "constraints_learned": [{"constraint": "class 5 remains", "scope": "mod 6", "evidence": "checker.py"}],
                    "route_decision": "redirect", "next_discriminator": "test mod 12",
                },
                "space_reduction": {
                    "ambient_space": "all residue classes", "represented_space_before": "6 classes",
                    "eliminated_or_quotiented": "5 classes", "represented_space_after": "1 class",
                    "reduction_factor": "6x upper bound", "measurement_status": "exact", "unit": "profiles",
                    "coverage_scope": "mod 6", "soundness_basis": "exact identity",
                    "remaining_unknown": "class 5", "next_bulk_elimination": "refine to mod 12",
                },
            }
            with patch.multiple(store, ROOT=root, DATA=data):
                first = research_state.update_from_attempt(problem, attempt)
                attempt["id"] = "a2"
                second = research_state.update_from_attempt(problem, attempt)
                self.assertEqual(second["epoch_count"], 2)
                self.assertEqual(len(second["strategies"]), 2)
                self.assertEqual(next(row for row in second["strategies"] if row["family"] == "congruences")["attempts"], 2)
                synthesis = next(row for row in second["strategies"] if row["family"] == "constraint-guided residue SAT")
                self.assertEqual(synthesis["origin"], "cross_problem_or_cross_field_synthesis")
                self.assertEqual(synthesis["parent_ids"], ["strategy-existing-residues", "strategy-existing-cubes"])
                self.assertEqual(second["next_session"]["first_action"], "run residues.py")
                self.assertEqual(second["tactical_memory"]["failure_signatures"][0]["count"], 2)
                self.assertEqual(second["tactical_memory"]["reusable_assets"][0]["name"], "residue checker")
                self.assertEqual(second["tactical_memory"]["reduction_ledger"][0]["represented_space_after"], "1 class")
                self.assertIn("allow degree two", json.dumps(second))
                self.assertEqual(first["problem_id"], "p")

    def test_tactical_brief_blocks_closed_routes_and_prefers_challenger(self) -> None:
        problem = {"id": "p", "statement": "Find x.", "verifiability": "Exact witness"}
        state = research_state._initial(problem)
        state["baseline_review"]["status"] = "complete"
        state["strategies"] = [
            {"id": "dead", "fingerprint": "dead", "family": "circulant", "mechanism": "same sweep", "status": "exhausted", "attempts": 8, "reopen_condition": "new theorem"},
            {"id": "live", "fingerprint": "live", "family": "SAT decomposition", "mechanism": "canonical cubes", "status": "proposed", "attempts": 0, "hypothesis": "cubes shrink", "discriminating_test": "pilot 100 cubes"},
        ]
        with patch.object(research_state, "load", return_value=state):
            brief = tactics.build(problem)
        self.assertEqual(brief["incumbent"]["strategy_id"], "live")
        self.assertFalse(next(row for row in brief["portfolio"] if row["strategy_id"] == "dead")["eligible"])
        self.assertEqual(brief["closed_routes"][0]["reopen_condition"], "new theorem")

    def test_tactical_brief_honors_child_of_recommended_closed_route(self) -> None:
        problem = {"id": "p", "statement": "Find x.", "verifiability": "Exact witness"}
        state = research_state._initial(problem)
        state["baseline_review"]["status"] = "complete"
        state["next_session"] = {"recommended_strategy_id": "closed"}
        state["strategies"] = [
            {"id": "closed", "fingerprint": "closed", "family": "old", "mechanism": "labelled blocks", "status": "blocked", "attempts": 1, "reopen_evidence": "evidence consumed by the failed retry"},
            {"id": "child", "fingerprint": "child", "family": "canonical", "mechanism": "class quotient", "status": "proposed", "attempts": 0, "parent_ids": ["closed"], "hypothesis": "quotient helps", "discriminating_test": "small orbit gate"},
            {"id": "stale", "fingerprint": "stale", "family": "other", "mechanism": "untried idea", "status": "proposed", "attempts": 0, "hypothesis": "maybe", "discriminating_test": "pilot"},
        ]
        with patch.object(research_state, "load", return_value=state):
            brief = tactics.build(problem)
        self.assertEqual(brief["incumbent"]["strategy_id"], "child")
        self.assertEqual(brief["incumbent"]["score_components"]["continuation_priority"], 30)
        self.assertFalse(next(row for row in brief["portfolio"] if row["strategy_id"] == "closed")["eligible"])

    def test_strategy_similarity_separates_paraphrase_from_distinct_mechanism(self) -> None:
        paraphrase = research_state.mechanism_similarity(
            "deletion-minimize raw K5 clauses and canonicalize signed incidence cores",
            "strip auxiliaries, minimize raw K5 clauses, and canonicalize signed-incidence cores",
        )
        distinct = research_state.mechanism_similarity(
            "freeze an order-30 core and solve its boundary edges",
            "encode every order-42 constraint with degree 20 or 21",
        )
        self.assertGreaterEqual(paraphrase, 0.25)
        self.assertLess(distinct, 0.25)

    def test_roadmap_selects_phase_from_tactical_incumbent(self) -> None:
        problem = {"id": "p"}
        value = {
            "schema_version": 2, "problem_id": "p", "default_phase": "first",
            "phases": [
                {"id": "first", "strategy_fingerprints": ["a"]},
                {"id": "second", "strategy_fingerprints": ["b"]},
            ],
        }
        with tempfile.TemporaryDirectory() as raw, patch.object(store, "DATA", Path(raw)), \
                patch.object(roadmap.tactics, "build", return_value={"incumbent": {"fingerprint": "b"}}):
            folder = Path(raw) / "campaign_roadmaps"
            folder.mkdir()
            (folder / "p.json").write_text(json.dumps(value))
            selected = roadmap.current(problem)
        self.assertEqual(selected["incumbent_fingerprint"], "b")
        self.assertEqual(selected["active_phase"]["id"], "second")

    def test_prior_art_registry_is_machine_readable(self) -> None:
        problem = {"id": "p"}
        value = {"schema_version": 1, "problem_id": "p", "methods": [{"id": "known-route"}]}
        with tempfile.TemporaryDirectory() as raw, patch.object(store, "DATA", Path(raw)):
            folder = Path(raw) / "prior_art"
            folder.mkdir()
            (folder / "p.json").write_text(json.dumps(value))
            loaded = prior_art.load(problem)
        self.assertTrue(loaded["configured"])
        self.assertEqual(loaded["methods"][0]["id"], "known-route")

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
            ), patch.object(capacity, "admission", return_value={"allowed": True}):
                submitted = lab.submit({
                    "problem_id": "p", "name": "control", "hypothesis": "six times seven is 42",
                    "expected_signal": "stdout contains 42", "command": ["python3", "-c", "print(6*7)"],
                    "segment_seconds": 60, "memory_mb": 128,
                })
                self.assertEqual(submitted["status"], "queued")
                result = lab.worker_once()
                self.assertEqual(result["status"], "completed_awaiting_review", result)
                self.assertEqual(result["returncode"], 0)
                self.assertTrue((state / "labs" / "jobs.jsonl").is_file())

    def test_lab_allows_lean_virtual_address_space_but_keeps_a_hard_cap(self) -> None:
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
                accepted = lab._validate({
                    "problem_id": "p", "name": "lean", "hypothesis": "module elaborates",
                    "expected_signal": "zero exit", "command": ["lean", "Target.lean"],
                    "segment_seconds": 60, "memory_mb": 16384,
                })
                self.assertEqual(accepted["memory_mb"], 16384)
                with self.assertRaisesRegex(ValueError, "memory_mb"):
                    lab._validate({
                        "problem_id": "p", "name": "too-large", "hypothesis": "no",
                        "expected_signal": "no", "command": ["lean", "Target.lean"],
                        "segment_seconds": 60, "memory_mb": 16385,
                    })

    def test_lab_checkpoint_review_continue_validate_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); data = root / "data"; research = root / "research"; state = root / "state"
            data.mkdir(); (data / "problems.json").write_text(json.dumps([{"id": "p"}]))
            code = (
                "import json,pathlib; c=pathlib.Path('checkpoint.json'); "
                "n=(json.loads(c.read_text())['n'] if c.exists() else 0)+1; "
                "c.write_text(json.dumps({'n':n})); "
                "pathlib.Path('progress.json').write_text(json.dumps({'completed_units':n,'total_units':2,"
                "'complete':n>=2,'correctness_checks_passed':True,'decision_value_active':True,'artifact_bytes':c.stat().st_size}))"
            )
            efficiency = {
                "naive_cost": "two full units", "opportunities_considered": ["symmetry", "memoization", "decomposition"],
                "chosen_reductions": "checkpoint one unit per segment", "expected_throughput_gain": "resumability",
                "soundness_basis": "unit counter checked independently", "remains_uncompressed": "two units",
            }
            with patch.multiple(store, ROOT=root, DATA=data, RESEARCH=research, STATE=state,
                                PROBLEMS_FILE=data / "problems.json", ATTEMPTS_FILE=data / "attempts.jsonl"), \
                    patch.object(capacity, "admission", return_value={"allowed": True}):
                submitted = lab.submit({
                    "problem_id": "p", "name": "lifecycle", "hypothesis": "two segments complete",
                    "expected_signal": "counter reaches two", "decision_value": "decides lifecycle correctness",
                    "efficiency_design": efficiency, "command": ["python3", "-c", code],
                    "segment_seconds": 60, "memory_mb": 128, "max_segments": 2,
                    "checkpoint_path": "checkpoint.json", "progress_path": "progress.json",
                    "continuation_thresholds": {"require_correctness_checks": True},
                })
                first = lab.worker_once()
                self.assertEqual(first["status"], "completed_awaiting_review")
                retuned = lab.retune_review_interval(
                    submitted["id"], 8, reason="pilot throughput supports a longer tranche", actor="test",
                )
                self.assertEqual(retuned["configuration_change"]["old"], 1)
                self.assertEqual(retuned["configuration_change"]["new"], 8)
                self.assertEqual(lab.apply_review(submitted["id"], "continue", reason="pilot passed")["status"], "queued")
                queued_spec = json.loads(
                    (research / "p" / "workspace" / "lab-queue" / f"{submitted['id']}.json").read_text()
                )
                self.assertEqual(queued_spec["review_every_segments"], 8)
                second = lab.worker_once()
                self.assertEqual(second["status"], "completed_awaiting_review")
                with self.assertRaisesRegex(ValueError, "validation receipt"):
                    lab.apply_review(submitted["id"], "validate", reason="unbound model assertion")
                workspace = research / "p" / "workspace"
                checker = workspace / "independent-checker.py"
                checker.write_text("# independent fixture checker\n")
                artifact = workspace / "checkpoint.json"
                final_state = lab._read_state(submitted["id"])
                receipt_path = workspace / "validation-receipt.json"
                receipt_path.write_text(json.dumps({
                    "schema_version": lab.VALIDATION_RECEIPT_SCHEMA_VERSION,
                    "job_id": submitted["id"],
                    "segment": final_state["segment"],
                    "progress_sha256": final_state["latest_progress"]["sha256"],
                    "result": "passed",
                    "validator": "independent fixture checker",
                    "checker_path": "independent-checker.py",
                    "checker_sha256": hashlib.sha256(checker.read_bytes()).hexdigest(),
                    "checked_artifacts": {
                        "checkpoint.json": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    },
                    "independence_basis": "separate checker code reads only the final artifact",
                    "created_at": store.now_iso(),
                }))
                self.assertEqual(lab.apply_review(
                    submitted["id"], "validate", reason="complete and checked",
                    validation_receipt="validation-receipt.json",
                )["status"], "validated")
                self.assertEqual(lab.status("p")["counts"]["validated"], 1)

    def test_strategy_lab_requires_executable_sourced_proposal(self) -> None:
        text = '''```strategy_proposal
{"outcome":"proposal","action":"add","target_id":"","family":"finite model finding","use_when":"a bounded structure decides a lemma","mechanism":"enumerate canonical models and emit certificates","first_discriminator":"reproduce one known model","efficiency_plan":"quotient isomorphisms, batch bitsets, then independently replay canonical coverage","experiment_template":"p -> H -> SAT -> model -> first UNSAT","failure_modes":["bad encoding","shared checker"],"sources":["https://example.test/paper"],"change_rationale":"new exact evaluator"}
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
                "contribution_gate": {
                    "schema_version": contribution_gate.SCHEMA_VERSION,
                    "passed": True,
                    "status": "candidate_eligible",
                    "reasons": [],
                    "contribution_class": "research_artifact",
                    "meaningful_delta": "First checked artifact for the configured target.",
                    "scholarly_question": "Can the configured target be checked independently?",
                    "external_recipient": "Maintainer",
                    "independent_validation_types": ["independent_third_party"],
                },
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

    def test_discovery_campaign_cannot_hold_before_25_runs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            problems_file = data / "problems.json"
            attempts_file = data / "attempts.jsonl"
            problems_file.parent.mkdir(parents=True)
            problems_file.write_text(json.dumps([{
                "id": "p", "lane": "easy", "status": "attempted", "attempt_count": 23,
                "research_attempt_count": 23, "campaign_state": "active", "campaign_min_runs": 25,
            }]))
            attempts_file.write_text("")

            def attempt(attempt_id: str) -> dict[str, object]:
                return {
                    "id": attempt_id, "problem_id": "p", "started_at": "2026-01-01T00:00:00+00:00",
                    "finished_at": "2026-01-01T00:01:00+00:00", "lane": "easy",
                    "outcome": "no_progress", "summary": "bounded route failed",
                    "campaign_assessment": {"decision": "hold", "close_signal": "", "reason": "route exhausted"},
                }

            with patch.multiple(
                store, ROOT=root, DATA=data, STATE=root / "state", RESEARCH=root / "research",
                PROBLEMS_FILE=problems_file, ATTEMPTS_FILE=attempts_file,
            ):
                store.record_attempt(attempt("a24"))
                problem = store.load_problems()[0]
                self.assertEqual(problem["research_attempt_count"], 24)
                self.assertNotEqual(problem["status"], "parked")
                self.assertEqual(problem["campaign_state"], "active")

                store.record_attempt(attempt("a25"))
                problem = store.load_problems()[0]
                self.assertEqual(problem["research_attempt_count"], 25)
                self.assertEqual(problem["status"], "parked")
                self.assertEqual(problem["campaign_state"], "hold")

    def test_discovery_campaign_continues_after_25_with_close_signal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            problems_file = data / "problems.json"
            attempts_file = data / "attempts.jsonl"
            problems_file.parent.mkdir(parents=True)
            problems_file.write_text(json.dumps([{
                "id": "p", "lane": "easy", "status": "attempted", "attempt_count": 24,
                "research_attempt_count": 24, "campaign_state": "active", "campaign_min_runs": 25,
            }]))
            attempts_file.write_text("")
            attempt = {
                "id": "a25", "problem_id": "p", "started_at": "2026-01-01T00:00:00+00:00",
                "finished_at": "2026-01-01T00:01:00+00:00", "lane": "easy",
                "outcome": "no_progress", "summary": "one route failed but a certificate is nearly complete",
                "campaign_assessment": {
                    "decision": "continue", "close_signal": "The checker passes 99 of 100 exhaustive cubes.",
                    "reason": "The final cube is bounded and uses the same verified encoding.",
                },
            }
            with patch.multiple(
                store, ROOT=root, DATA=data, STATE=root / "state", RESEARCH=root / "research",
                PROBLEMS_FILE=problems_file, ATTEMPTS_FILE=attempts_file,
            ):
                store.record_attempt(attempt)
                problem = store.load_problems()[0]
                self.assertEqual(problem["research_attempt_count"], 25)
                self.assertEqual(problem["status"], "active")
                self.assertEqual(problem["campaign_state"], "active")

    def test_discovery_campaign_minimum_counts_only_runs_since_start(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            problems_file = data / "problems.json"
            attempts_file = data / "attempts.jsonl"
            problems_file.parent.mkdir(parents=True)
            problems_file.write_text(json.dumps([{
                "id": "p", "lane": "easy", "status": "active", "attempt_count": 123,
                "research_attempt_count": 123, "campaign_state": "active", "campaign_min_runs": 25,
                "campaign_start_research_attempt_count": 100,
            }]))
            attempts_file.write_text("")

            def attempt(attempt_id: str) -> dict[str, object]:
                return {
                    "id": attempt_id, "problem_id": "p", "started_at": "2026-01-01T00:00:00+00:00",
                    "finished_at": "2026-01-01T00:01:00+00:00", "lane": "easy",
                    "outcome": "no_progress", "summary": "bounded route failed",
                    "campaign_assessment": {"decision": "hold", "close_signal": "", "reason": "route exhausted"},
                }

            with patch.multiple(
                store, ROOT=root, DATA=data, STATE=root / "state", RESEARCH=root / "research",
                PROBLEMS_FILE=problems_file, ATTEMPTS_FILE=attempts_file,
            ):
                store.record_attempt(attempt("campaign-24"))
                problem = store.load_problems()[0]
                self.assertEqual(problem["research_attempt_count"], 124)
                self.assertEqual(store.discovery_campaign_run_count(problem), 24)
                self.assertEqual(problem["campaign_state"], "active")

                store.record_attempt(attempt("campaign-25"))
                problem = store.load_problems()[0]
                self.assertEqual(store.discovery_campaign_run_count(problem), 25)
                self.assertEqual(problem["campaign_state"], "hold")

    def test_low_hanging_score_learns_from_accepted_techniques(self) -> None:
        win = {"id": "win", "accepted_result": True, "difficulty": 4, "techniques": ["SAT"], "contribution_type": "finite witness"}
        similar = {"id": "similar", "difficulty": 4, "techniques": ["SAT"], "contribution_type": "finite witness"}
        unrelated = {"id": "other", "difficulty": 4, "techniques": ["calculus"], "contribution_type": "lemma"}
        problems = [win, similar, unrelated]
        self.assertGreater(scheduler.low_hanging_score(similar, problems), scheduler.low_hanging_score(unrelated, problems))

    def test_watchdog_accepts_paused_open_problem_program(self) -> None:
        attempts = [
            {"lane": "hard", "finished_at": store.now_iso()},
            {"lane": "easy", "finished_at": "2026-01-01T00:00:00+00:00"},
        ]
        with patch.object(store, "load_attempts", return_value=attempts), \
                patch.object(store, "runtime", return_value={}), \
                patch.object(store, "update_runtime", side_effect=lambda **fields: fields), \
                patch.object(render, "build"), \
                patch.object(capacity, "admission", return_value={"allowed": True}), \
                patch.dict("os.environ", {"PROOF_EASY_EXPECTED": "0"}):
            report = scheduler.watchdog()
        self.assertEqual(report["health"], "healthy")
        self.assertEqual(report["health_issues"], [])

    def test_watchdog_flags_attempt_page_missing_for_four_hours(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            site = Path(raw) / "site"
            old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
            attempts = [{"id": "missing-page", "lane": "hard", "problem_id": "p", "finished_at": old}]
            with patch.object(store, "SITE", site), \
                    patch.object(store, "load_attempts", return_value=attempts), \
                    patch.object(store, "load_problems", return_value=[]), \
                    patch.object(store, "runtime", return_value={}), \
                    patch.object(store, "update_runtime", side_effect=lambda **fields: fields), \
                    patch.object(render, "build"), \
                    patch.object(capacity, "admission", return_value={"allowed": True}), \
                    patch.dict("os.environ", {"PROOF_EASY_EXPECTED": "0"}):
                report = scheduler.watchdog()
            self.assertEqual(report["site_freshness"]["status"], "stale")
            self.assertIn("no rendered page", report["health_issues"][0])

    def test_capacity_admission_defers_when_memory_reserve_is_low(self) -> None:
        with patch.object(capacity, "cleanup", return_value={}), \
                patch.object(capacity, "_free_bytes", return_value=20 * 1024**3), \
                patch.object(capacity, "_available_memory_bytes", return_value=100 * 1024**2):
            report = capacity.admission("easy")
        self.assertFalse(report["allowed"])
        self.assertIn("available memory", report["reasons"][0])

    def test_workspace_lab_can_ignore_unrelated_full_build_cache(self) -> None:
        gib = 1024**3
        with patch.object(capacity, "cleanup", return_value={}), \
                patch.object(capacity, "_free_bytes", side_effect=[20 * gib, 0]), \
                patch.object(capacity, "_available_memory_bytes", return_value=4 * gib):
            report = capacity.admission("hard", require_cache=False)
        self.assertTrue(report["allowed"])
        self.assertFalse(report["cache_required"])
        self.assertEqual(report["cache_free_bytes"], 0)
        self.assertTrue(lab._requires_build_cache({"command": ["checks/run_lean_build.sh"]}))
        self.assertFalse(lab._requires_build_cache({"command": ["python3", "enumerate.py"]}))

    def test_easy_lane_yields_to_priority_lab_compute(self) -> None:
        gib = 1024**3
        with patch.object(capacity, "cleanup", return_value={}), \
                patch.object(capacity, "_free_bytes", return_value=20 * gib), \
                patch.object(capacity, "_available_memory_bytes", return_value=4 * gib), \
                patch.object(capacity, "_lab_compute_active", return_value=True):
            easy = capacity.admission("easy")
            hard = capacity.admission("hard")
        self.assertFalse(easy["allowed"])
        self.assertTrue(easy["lab_compute_active"])
        self.assertIn("priority checkpointed lab compute", easy["reasons"][0])
        self.assertTrue(hard["allowed"])
        self.assertFalse(hard["lab_compute_active"])

    def test_lab_tranche_drains_checkpoints_until_review(self) -> None:
        with patch.object(lab, "worker_once", side_effect=[
            {"status": "checkpointed", "segment": 2},
            {"status": "checkpointed", "segment": 3},
            {"status": "completed_awaiting_review", "segment": 4},
        ]):
            report = lab.worker_tranche()
        self.assertEqual(report["status"], "completed_awaiting_review")
        self.assertEqual(report["segments_run"], 3)

    def test_lab_tranche_has_no_hidden_activation_cap_before_review(self) -> None:
        segments = [
            {"status": "checkpointed", "segment": index}
            for index in range(1, 102)
        ] + [{"status": "completed_awaiting_review", "segment": 102}]
        with patch.object(lab, "worker_once", side_effect=segments) as worker:
            report = lab.worker_tranche()
        self.assertEqual(report["status"], "completed_awaiting_review")
        self.assertEqual(report["segments_run"], 102)
        self.assertEqual(worker.call_count, 102)

    def test_lab_tranche_explicit_operator_cap_remains_available(self) -> None:
        with patch.object(lab, "worker_once", return_value={"status": "checkpointed", "segment": 1}) as worker:
            report = lab.worker_tranche(max_segments=2)
        self.assertEqual(report["status"], "checkpointed")
        self.assertEqual(report["segments_run"], 2)
        self.assertEqual(worker.call_count, 2)

    def test_capacity_cleanup_candidates_exclude_fresh_and_system_tmp(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            old = tmp / "old"
            old.write_text("remove")
            fresh = tmp / "fresh"
            fresh.write_text("keep")
            system = tmp / "systemd-private-safe"
            system.write_text("keep")
            import os
            os.utime(old, (1, 1))
            os.utime(fresh, (999, 999))
            with patch.object(capacity, "TMP_MAX_AGE_SECONDS", 10):
                candidates = capacity._cleanup_candidates(tmp, 1_000.0)
        self.assertEqual(candidates, [old])

    def test_lab_worker_leaves_job_queued_when_capacity_is_reserved(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            state = root / "state"
            research = root / "research"
            data.mkdir()
            state.mkdir()
            research.mkdir()
            problems = data / "problems.json"
            attempts = data / "attempts.jsonl"
            problems.write_text(json.dumps([{"id": "p", "lane": "hard", "status": "active"}]))
            attempts.write_text("")
            queued = research / "p" / "workspace" / "lab-queue"
            queued.mkdir(parents=True)
            queued_file = queued / "job.json"
            queued_file.write_text(json.dumps({"problem_id": "p"}))
            with patch.multiple(store, ROOT=root, DATA=data, STATE=state, RESEARCH=research,
                                PROBLEMS_FILE=problems, ATTEMPTS_FILE=attempts), \
                    patch.object(capacity, "admission", return_value={"allowed": False, "reasons": ["reserve"]}):
                result = lab.worker_once()
            self.assertEqual(result["status"], "deferred")
            self.assertTrue(queued_file.exists())

    def test_usage_policy_enforces_elapsed_week_and_baseline(self) -> None:
        now = datetime(2026, 7, 20, 2, 0, tzinfo=timezone.utc)
        clock = now.timestamp()
        fresh = {"ok": True, "checked_at": clock, "week": {"used_pct": 20.0, "resets_at": clock + 5.25 * 86400, "window_seconds": 7 * 86400}}
        with tempfile.TemporaryDirectory() as raw:
            cache = Path(raw) / "usage.json"
            cache.write_text(json.dumps(fresh))
            with patch.dict("os.environ", {"PROOF_USAGE_CACHE_PATH": str(cache)}):
                within = usage.admission("hard", now=now, monotonic_now=clock)
                self.assertEqual(within["mode"], "primary")
                self.assertTrue(within["allowed"])
                fresh["week"]["used_pct"] = 40.0
                cache.write_text(json.dumps(fresh))
                baseline = usage.admission("hard", now=now.replace(hour=3), monotonic_now=clock)
                self.assertEqual(baseline["mode"], "baseline")
                self.assertFalse(baseline["allowed"])
                easy = usage.admission("easy", now=now.replace(hour=3), monotonic_now=clock)
                self.assertTrue(easy["allowed"])

    def test_operator_run_is_one_shot_and_cannot_bypass_provider_stop(self) -> None:
        now = datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)
        payload = {
            "ok": True, "checked_at": 1000.0,
            "week": {"used_pct": 90.0, "resets_at": 704800.0, "window_seconds": 604800.0},
        }
        with tempfile.TemporaryDirectory() as raw:
            cache = Path(raw) / "usage.json"
            cache.write_text(json.dumps(payload))
            with patch.dict("os.environ", {
                "PROOF_USAGE_CACHE_PATH": str(cache), "PROOF_OPERATOR_RUN": "1",
            }):
                allowed = usage.admission("hard", now=now, monotonic_now=1000.0)
                self.assertTrue(allowed["allowed"])
                self.assertEqual(allowed["mode"], "operator")
                payload["rate_limit_reached_type"] = "weekly"
                cache.write_text(json.dumps(payload))
                stopped = usage.admission("hard", now=now, monotonic_now=1000.0)
                self.assertFalse(stopped["allowed"])
                self.assertEqual(stopped["mode"], "paused")

    def test_removed_hard_priority_cannot_bypass_pacing_or_provider_stop(self) -> None:
        payload = {
            "ok": True, "checked_at": 1000.0,
            "week": {"used_pct": 90.0, "resets_at": 604800.0, "window_seconds": 604800.0},
        }
        with tempfile.TemporaryDirectory() as raw:
            cache = Path(raw) / "usage.json"; cache.write_text(json.dumps(payload))
            with patch.dict("os.environ", {"PROOF_USAGE_CACHE_PATH": str(cache), "PROOF_HARD_PRIORITY": "true"}):
                now = datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)
                allowed = usage.admission("hard", now=now, monotonic_now=1000.0)
                self.assertFalse(allowed["allowed"]); self.assertEqual(allowed["mode"], "baseline")
                self.assertNotIn("priority_authorized", allowed)
                payload["spend_control_reached"] = True; cache.write_text(json.dumps(payload))
                self.assertEqual(usage.admission("hard", now=now, monotonic_now=1000.0)["mode"], "paused")

    def test_usage_tie_break_prefers_discovery_without_preemption(self) -> None:
        decisions = {"hard": {"allowed": True}, "easy": {"allowed": True}}
        self.assertEqual(usage.preferred_lane(decisions), "easy")
        self.assertEqual(usage.preferred_lane({"hard": {"allowed": True}}), "hard")
        self.assertIsNone(usage.preferred_lane({"hard": {"allowed": False}, "easy": {"allowed": False}}))

        payload = {
            "ok": True, "checked_at": 302400.0,
            "week": {"used_pct": 10.0, "resets_at": 604800.0, "window_seconds": 604800.0},
        }
        with tempfile.TemporaryDirectory() as raw:
            cache = Path(raw) / "usage.json"; cache.write_text(json.dumps(payload))
            with patch.dict("os.environ", {"PROOF_USAGE_CACHE_PATH": str(cache)}), \
                    patch.object(store, "runtime", return_value={"easy_running": "erdos-530"}):
                hard = usage.admission("hard", monotonic_now=302400.0)
                easy = usage.admission("easy", monotonic_now=302400.0)
        self.assertFalse(hard["allowed"])
        self.assertEqual(hard["mode"], "portfolio")
        self.assertTrue(easy["allowed"])

    def test_scout_is_limited_to_one_completed_call_per_day(self) -> None:
        now = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as raw, patch.object(store, "STATE", Path(raw)), \
                patch.object(subprocess, "run") as run:
            store.write_json_atomic(Path(raw) / "scout-last.json", {
                "finished_at": (now - timedelta(hours=1)).isoformat(), "returncode": 0,
            })
            result = scout.run(now=now)
        self.assertFalse(result["added"])
        self.assertEqual(result["reason"], "daily scout already completed")
        run.assert_not_called()

    def test_recent_hard_pass_satisfies_next_baseline_slot(self) -> None:
        recent = datetime.now(timezone.utc).isoformat()
        with patch.object(capacity, "admission", return_value={"allowed": True}), \
                patch.object(usage, "admission", return_value={"allowed": True, "mode": "baseline"}), \
                patch.object(store, "runtime", return_value={"hard_last_attempt_at": recent}), \
                patch.object(store, "update_runtime"), patch.object(render, "build"):
            result = scheduler.tick("hard")
        self.assertEqual(result["status"], "deferred")
        self.assertIn("already satisfied", result["usage_policy"]["reason"])

    def test_lab_review_applies_on_easy_lane_and_events_consume_selectively(self) -> None:
        attempt = {
            "id": "easy-attempt", "lane": "easy",
            "evidence_validation": {"status": "valid"},
            "lab_review": {"job_id": "job-reviewed", "decision": "continue", "reason": "hashes pass"},
        }
        with patch.object(lab, "apply_review", return_value={"status": "queued"}) as apply_review:
            reviewed_job = scheduler._apply_lab_review(attempt)
        self.assertEqual(reviewed_job, "job-reviewed")
        self.assertEqual(attempt["lab_review_applied"]["status"], "queued")
        apply_review.assert_called_once_with(
            "job-reviewed", "continue", reason="hashes pass", reviewer="proof-factory:easy-attempt",
        )
        research_events = [
            {"id": "old-job", "kind": "lab_completed", "source": "state/labs/jobs/job-old.json"},
            {"id": "reviewed-job", "kind": "lab_completed", "source": "state/labs/jobs/job-reviewed.json"},
            {"id": "source", "kind": "source_changed", "source": "source"},
        ]
        pending_events = [
            *research_events,
            {"id": "segment", "kind": "lab_segment_completed", "source": "state/labs/jobs/job-reviewed.json"},
            {"id": "prefix", "kind": "lab_segment_completed", "source": "state/labs/jobs/job-reviewed-10.json"},
        ]
        selected = scheduler._consumable_event_ids(
            research_events, pending_events, reviewed_job=reviewed_job, evidence_valid=True,
        )
        self.assertEqual(selected, {"reviewed-job", "source", "segment"})
        self.assertEqual(
            scheduler._consumable_event_ids(
                research_events, pending_events, reviewed_job=reviewed_job, evidence_valid=False,
            ),
            set(),
        )

    def test_automated_lab_review_cannot_validate_without_operator_receipt(self) -> None:
        attempt = {
            "id": "model-review", "evidence_validation": {"status": "valid"},
            "lab_review": {"job_id": "job", "decision": "validate", "reason": "looks complete"},
        }
        with patch.object(lab, "apply_review") as apply_review:
            self.assertEqual(scheduler._apply_lab_review(attempt), "")
        apply_review.assert_not_called()
        self.assertTrue(any("only an operator" in flag for flag in attempt["policy_flags"]))

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
        self.assertEqual(live.next_hard_after(now).isoformat(), "2026-07-21T00:00:00+00:00")
        self.assertEqual(
            live.next_hard_after(datetime(2026, 7, 20, 20, 10, tzinfo=timezone.utc)).isoformat(),
            "2026-07-21T00:00:00+00:00",
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
            ), patch.object(repositories, "_max_tracked_file_bytes", return_value=10_000):
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
