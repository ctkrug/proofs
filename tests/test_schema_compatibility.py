from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proof_factory import capacity, cli, contribution_gate, evidence, lab, research_state, schemas, store


class SchemaCompatibilityTests(unittest.TestCase):
    def test_shared_loader_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "duplicate.json"
            path.write_text('{"schema_version":1,"schema_version":1}\n')
            with self.assertRaisesRegex(schemas.SchemaError, "duplicate JSON key"):
                schemas.load_json_object(path, kind="fixture")

    def test_research_state_migrates_v1_through_v5_without_inventing_findings(self) -> None:
        problem = {"id": "p", "statement": "Find x.", "verifiability": "Exact witness"}
        legacy = {
            "schema_version": 1,
            "problem_id": "p",
            "epoch_count": 2,
            "established_facts": [{"claim": "legacy fact", "evidence": "legacy receipt"}],
            "strategies": [],
            "open_leads": [],
            "ruled_out": [],
            "unresolved_questions": [],
        }
        migrated = research_state.migrate_value(legacy, problem)
        self.assertEqual(migrated["schema_version"], research_state.SCHEMA_VERSION)
        self.assertEqual(migrated["established_facts"], legacy["established_facts"])
        self.assertEqual(migrated["tactical_memory"]["decision_history"], [])
        self.assertEqual(migrated["tactical_memory"]["prior_art_decisions"], [])
        self.assertEqual(legacy["schema_version"], 1)

    def test_research_state_rejects_unknown_or_mismatched_schema(self) -> None:
        problem = {"id": "p"}
        with self.assertRaisesRegex(schemas.SchemaError, "supported versions"):
            research_state.migrate_value({"schema_version": 0, "problem_id": "p"}, problem)
        with self.assertRaisesRegex(schemas.SchemaError, "does not match"):
            research_state.migrate_value({"schema_version": 1, "problem_id": "other"}, problem)

    def test_lab_v1_records_remain_viewable_but_cannot_execute_or_mutate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state_root = root / "state"
            jobs = state_root / "labs" / "jobs"
            jobs.mkdir(parents=True)
            legacy = {
                "schema_version": 1,
                "id": "legacy-job",
                "problem_id": "p",
                "status": "completed_awaiting_review",
            }
            (jobs / "legacy-job.json").write_text(json.dumps(legacy))
            with patch.multiple(store, STATE=state_root, RESEARCH=root / "research"):
                report = lab.status("p")
                self.assertEqual(report["jobs"][0]["schema_version"], 1)
                self.assertFalse(report["jobs"][0]["schema_compatible"])
                with self.assertRaisesRegex(schemas.SchemaError, "current schema_version is 2"):
                    lab._read_state("legacy-job")

    def test_lab_state_identifier_cannot_traverse_state_root(self) -> None:
        with self.assertRaisesRegex(schemas.SchemaError, "invalid lab job id"):
            lab._state_path("../outside")

    def test_lab_persisted_spec_rejects_v1_instead_of_defaulting_new_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "legacy.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "id": "legacy-job",
                "problem_id": "p",
                "command": ["python3", "run.py"],
            }))
            with self.assertRaisesRegex(schemas.SchemaError, "current schema_version is 2"):
                lab._load_persisted_spec(path)

    def test_lab_worker_quarantines_v1_spec_and_keeps_legacy_state_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            state_root = root / "state"
            research = root / "research"
            data.mkdir()
            (data / "problems.json").write_text(json.dumps([{"id": "p"}]))
            queue = research / "p" / "workspace" / "lab-queue"
            queue.mkdir(parents=True)
            legacy = {
                "schema_version": 1, "id": "legacy-job", "problem_id": "p",
                "status": "queued", "command": ["python3", "-c", "print(1)"],
            }
            (queue / "legacy-job.json").write_text(json.dumps(legacy))
            jobs = state_root / "labs" / "jobs"
            jobs.mkdir(parents=True)
            state_path = jobs / "legacy-job.json"
            state_path.write_text(json.dumps(legacy))
            with patch.multiple(
                store,
                ROOT=root,
                DATA=data,
                STATE=state_root,
                RESEARCH=research,
                PROBLEMS_FILE=data / "problems.json",
                ATTEMPTS_FILE=data / "attempts.jsonl",
            ), patch.object(capacity, "admission", return_value={"allowed": True}):
                result = lab.worker_once()
            self.assertEqual(result["status"], "stopped_with_reason")
            self.assertEqual(result["problem_id"], "p")
            self.assertIn("current schema_version is 2", result["error"])
            self.assertEqual(json.loads(state_path.read_text())["schema_version"], 1)
            self.assertTrue((research / "p" / "workspace" / "lab-rejected" / "legacy-job.running.json").exists())

    def test_lab_checkpoint_rollover_rehashes_next_spec_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            state_root = root / "state"
            research = root / "research"
            data.mkdir()
            (data / "problems.json").write_text(json.dumps([{"id": "p"}]))
            code = (
                "import json,pathlib; "
                "pathlib.Path('checkpoint.json').write_text(json.dumps({'done':1})); "
                "pathlib.Path('progress.json').write_text(json.dumps({"
                "'completed_units':1,'total_units':3,'complete':False,"
                "'correctness_checks_passed':True,'decision_value_active':True,'artifact_bytes':10}))"
            )
            efficiency = {
                "naive_cost": "three units",
                "opportunities_considered": ["symmetry", "memoization", "decomposition"],
                "chosen_reductions": "one resumable unit per segment",
                "expected_throughput_gain": "bounded recovery",
                "soundness_basis": "independent progress counter",
                "remains_uncompressed": "three units",
            }
            with patch.multiple(
                store,
                ROOT=root,
                DATA=data,
                STATE=state_root,
                RESEARCH=research,
                PROBLEMS_FILE=data / "problems.json",
                ATTEMPTS_FILE=data / "attempts.jsonl",
            ), patch.object(capacity, "admission", return_value={"allowed": True}):
                submitted = lab.submit({
                    "problem_id": "p",
                    "name": "hash-rollover",
                    "hypothesis": "checkpoint advances without corrupting its immutable envelope",
                    "expected_signal": "a current-schema second segment remains executable",
                    "decision_value": "protects resumable long-job execution",
                    "efficiency_design": efficiency,
                    "command": ["python3", "-c", code],
                    "segment_seconds": 60,
                    "memory_mb": 128,
                    "max_segments": 3,
                    "pilot_segments": 2,
                    "checkpoint_path": "checkpoint.json",
                    "progress_path": "progress.json",
                    "continuation_thresholds": {"require_correctness_checks": True},
                })
                first = lab.worker_once()
                self.assertEqual(first["status"], "checkpointed")
                queued = research / "p" / "workspace" / "lab-queue" / f"{submitted['id']}.json"
                next_spec = lab._load_persisted_spec(queued)
                state = lab._read_state(submitted["id"])
                self.assertEqual(next_spec["segment"], 2)
                self.assertEqual(state["segment"], 2)
                self.assertEqual(state["spec_sha256"], next_spec["spec_sha256"])

    def test_lab_segment_event_names_completed_segment_after_rollover(self) -> None:
        spec = {"id": "job", "problem_id": "p", "segment": 2}
        record = {"segment": 1, "progress": {"completed_units": 1}}
        with patch.object(lab.events, "enqueue", return_value={"id": "event"}) as enqueue:
            lab._emit_segment_event(spec, "checkpointed", record)
        self.assertIn("segment 1 entered checkpointed", enqueue.call_args.kwargs["evidence"])

    def test_lab_progress_rejects_coerced_booleans_and_nonfinite_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            progress_path = workspace / "progress.json"
            spec = {
                "progress_path": "progress.json",
                "continuation_thresholds": {
                    "min_throughput_per_second": 0,
                    "max_artifact_growth_bytes": 0,
                    "require_correctness_checks": True,
                },
            }
            progress_path.write_text(json.dumps({
                "completed_units": 1,
                "total_units": 2,
                "artifact_bytes": 1,
                "complete": "false",
                "correctness_checks_passed": "false",
                "decision_value_active": "false",
            }))
            progress, failures = lab._progress(workspace, spec, {}, 1.0)
            self.assertEqual(progress, {})
            self.assertIn("must be bool", failures[0])

            progress_path.write_text(
                '{"completed_units":NaN,"total_units":2,"artifact_bytes":1,'
                '"complete":false,"correctness_checks_passed":true,"decision_value_active":true}'
            )
            progress, failures = lab._progress(workspace, spec, {}, 1.0)
            self.assertEqual(progress, {})
            self.assertIn("non-finite JSON number", failures[0])

    def test_lab_progress_uses_independently_measured_artifact_growth(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            (workspace / "progress.json").write_text(json.dumps({
                "completed_units": 1,
                "total_units": 2,
                "artifact_bytes": 1,
                "complete": False,
                "correctness_checks_passed": True,
                "decision_value_active": True,
            }))
            spec = {
                "progress_path": "progress.json",
                "continuation_thresholds": {
                    "min_throughput_per_second": 0,
                    "max_artifact_growth_bytes": 100,
                    "require_correctness_checks": True,
                },
            }
            progress, failures = lab._progress(
                workspace, spec, {}, 1.0, measured_growth_bytes=1000,
            )
            self.assertEqual(progress["artifact_growth_bytes"], 1000)
            self.assertTrue(any("artifact growth exceeded" in reason for reason in failures))

    def test_lab_late_bookkeeping_failure_cannot_leave_next_segment_queued(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            state_root = root / "state"
            research = root / "research"
            data.mkdir()
            (data / "problems.json").write_text(json.dumps([{"id": "p"}]))
            code = (
                "import json,pathlib; "
                "pathlib.Path('checkpoint.json').write_text('{}'); "
                "pathlib.Path('progress.json').write_text(json.dumps({"
                "'completed_units':1,'total_units':3,'complete':False,"
                "'correctness_checks_passed':True,'decision_value_active':True,'artifact_bytes':2}))"
            )
            efficiency = {
                "naive_cost": "three units",
                "opportunities_considered": ["symmetry", "memoization", "decomposition"],
                "chosen_reductions": "one unit per segment",
                "expected_throughput_gain": "resumability",
                "soundness_basis": "fixture counter",
                "remains_uncompressed": "three units",
            }
            with patch.multiple(
                store,
                ROOT=root,
                DATA=data,
                STATE=state_root,
                RESEARCH=research,
                PROBLEMS_FILE=data / "problems.json",
                ATTEMPTS_FILE=data / "attempts.jsonl",
            ), patch.object(capacity, "admission", return_value={"allowed": True}):
                submitted = lab.submit({
                    "problem_id": "p", "name": "late-failure", "hypothesis": "fixture",
                    "expected_signal": "one checkpoint", "decision_value": "lifecycle safety",
                    "efficiency_design": efficiency, "command": ["python3", "-c", code],
                    "segment_seconds": 60, "memory_mb": 128, "max_segments": 3,
                    "pilot_segments": 2, "checkpoint_path": "checkpoint.json",
                    "progress_path": "progress.json",
                })
                with patch.object(lab.repositories, "record_lab", side_effect=RuntimeError("late failure")):
                    result = lab.worker_once()
                queue = research / "p" / "workspace" / "lab-queue" / f"{submitted['id']}.json"
                self.assertEqual(result["status"], "stopped_with_reason")
                self.assertFalse(queue.exists())
                self.assertEqual(lab._read_state(submitted["id"])["status"], "stopped_with_reason")

    def test_evidence_loaders_accept_generated_records_and_reject_legacy_schema(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "proof.txt").write_text("proof\n")
            manifest_path = evidence.create_attempt_manifest(
                workspace,
                "schema-test",
                evidence.capture_workspace_snapshot(workspace),
                claimed_evidence_paths=["proof.txt"],
                manifest_root=root / "evidence",
            )
            receipt_path = evidence.create_evidence_receipt(manifest_path)
            self.assertEqual(evidence.load_attempt_manifest(manifest_path)["attempt_id"], "schema-test")
            self.assertEqual(evidence.load_evidence_receipt(receipt_path)["status"], "valid")

            legacy = root / "legacy-receipt.json"
            receipt = json.loads(receipt_path.read_text())
            receipt["schema_version"] = 0
            legacy.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(schemas.SchemaError, "current schema_version is 1"):
                evidence.load_evidence_receipt(legacy)

    def test_acceptance_requires_present_valid_current_passed_gate(self) -> None:
        valid = {
            "schema_version": contribution_gate.SCHEMA_VERSION,
            "passed": True,
            "status": "candidate_eligible",
            "reasons": [],
            "contribution_class": "terminal_result",
            "meaningful_delta": "Settles the exact configured target.",
            "scholarly_question": "Does the exact target hold?",
            "external_recipient": "Registry maintainer",
            "independent_validation_types": ["formal_kernel"],
        }
        self.assertTrue(contribution_gate.validate(valid, require_passed=True)["passed"])
        malformed = dict(valid, schema_version=0)
        with self.assertRaisesRegex(schemas.SchemaError, "current schema_version is 1"):
            contribution_gate.validate(malformed, require_passed=True)

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = root / "data"
            data.mkdir()
            (data / "problems.json").write_text(json.dumps([{"id": "p", "status": "candidate"}]))
            (data / "attempts.jsonl").write_text(json.dumps({
                "id": "a", "problem_id": "p", "outcome": "candidate",
            }) + "\n")
            (data / "reviews.json").write_text("[]\n")
            with patch.multiple(
                store,
                ROOT=root,
                DATA=data,
                STATE=root / "state",
                PROBLEMS_FILE=data / "problems.json",
                ATTEMPTS_FILE=data / "attempts.jsonl",
            ):
                with self.assertRaisesRegex(ValueError, "present current-schema"):
                    cli._review("a", "accept", "reviewed")


if __name__ == "__main__":
    unittest.main()
