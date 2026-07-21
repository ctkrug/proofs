from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from proof_factory import evidence


class EvidenceTests(unittest.TestCase):
    def test_manifest_hashes_every_claim_without_cap_and_labels_projections(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "status.json").write_text("{}\n")
            before = evidence.capture_workspace_snapshot(workspace)
            claimed = []
            for index in range(275):
                relative = f"proofs/leaf-{index:03}.lrat"
                path = workspace / relative
                path.parent.mkdir(exist_ok=True)
                path.write_text(f"certificate {index}\n")
                claimed.append(relative)
            (workspace / "status.json").write_text('{"attempt": 1}\n')

            manifest_path = evidence.create_attempt_manifest(
                workspace,
                "attempt-001",
                before,
                claimed_evidence_paths=claimed,
                mutable_projection_patterns=["status.json"],
                manifest_root=root / "manifests",
                created_at="2026-07-21T00:00:00+00:00",
            )
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["artifact_count"], 276)
            self.assertEqual(len(manifest["claimed_evidence_paths"]), 275)
            self.assertEqual(
                next(row for row in manifest["artifacts"] if row["path"] == "status.json")["role"],
                "mutable_projection",
            )
            receipt = evidence.validate_attempt_manifest(
                manifest_path, checked_at="2026-07-21T00:01:00+00:00"
            )
            self.assertEqual(receipt["status"], "valid")
            self.assertEqual(receipt["claimed_evidence_count"], 275)
            self.assertEqual(receipt["mutable_projection_count"], 1)

    def test_validation_fails_closed_for_hash_or_scope_but_allows_projection_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "proof.txt").write_text("proof v1\n")
            (workspace / "dashboard.json").write_text("old\n")
            before = evidence.capture_workspace_snapshot(workspace)
            (workspace / "proof.txt").write_text("proof v2\n")
            (workspace / "dashboard.json").write_text("attempt projection\n")
            manifest = evidence.create_attempt_manifest(
                workspace,
                "attempt-002",
                before,
                claimed_evidence_paths=["proof.txt"],
                mutable_projection_patterns=["dashboard.json"],
                manifest_root=root / "manifests",
            )

            (workspace / "dashboard.json").write_text("later projection\n")
            self.assertEqual(evidence.validate_attempt_manifest(manifest)["status"], "valid")
            (workspace / "proof.txt").write_text("tampered\n")
            receipt = evidence.validate_attempt_manifest(manifest)
            self.assertEqual(receipt["status"], "invalid")
            self.assertTrue(any("hash mismatch" in error for error in receipt["errors"]))

            with self.assertRaisesRegex(ValueError, "normalized relative path"):
                evidence.create_attempt_manifest(
                    workspace,
                    "attempt-003",
                    evidence.capture_workspace_snapshot(workspace),
                    claimed_evidence_paths=["../outside.txt"],
                    manifest_root=root / "manifests",
                )

    def test_manifest_and_receipt_are_exclusive_and_mutable_claims_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "proof.txt").write_text("proof\n")
            before = evidence.capture_workspace_snapshot(workspace)
            manifest = evidence.create_attempt_manifest(
                workspace,
                "attempt-004",
                before,
                claimed_evidence_paths=["proof.txt"],
                manifest_root=root / "manifests",
            )
            with self.assertRaises(FileExistsError):
                evidence.create_attempt_manifest(
                    workspace,
                    "attempt-004",
                    before,
                    claimed_evidence_paths=["proof.txt"],
                    manifest_root=root / "manifests",
                )
            receipt = evidence.create_evidence_receipt(
                manifest, checked_at="2026-07-21T00:02:00+00:00"
            )
            self.assertEqual(json.loads(receipt.read_text())["status"], "valid")
            with self.assertRaises(FileExistsError):
                evidence.create_evidence_receipt(manifest)
            with self.assertRaisesRegex(ValueError, "mutable projection"):
                evidence.create_attempt_manifest(
                    workspace,
                    "attempt-005",
                    before,
                    claimed_evidence_paths=["proof.txt"],
                    mutable_projection_patterns=["*.txt"],
                    manifest_root=root / "manifests",
                )


if __name__ == "__main__":
    unittest.main()
