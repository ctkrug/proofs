from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import call, patch

from proof_factory import capacity, render, repositories, resources, scheduler, store


def _completed(
    args: list[str] | tuple[str, ...],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


class RepositorySyncTests(unittest.TestCase):
    problem = {"id": "edge-case", "title": "Edge case"}
    remote_url = "https://github.com/ctkrug/proofs-edge-case"

    def test_existing_public_repository_pushes_to_matching_origin(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)

            def fake_git(_repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
                if args == ("remote", "get-url", "origin"):
                    return _completed(args, stdout=f"{self.remote_url}\n")
                if args == ("rev-parse", "HEAD"):
                    return _completed(args, stdout="a" * 40 + "\n")
                return _completed(args)

            with patch.object(repositories, "ensure", return_value={"path": str(repo)}), \
                    patch.object(repositories, "_gh", return_value=_completed(
                        ["gh"], stdout=json.dumps({"url": self.remote_url, "visibility": "PUBLIC"}),
                    )) as gh, patch.object(repositories, "_git", side_effect=fake_git) as git:
                result = repositories._sync_problem(self.problem)

        self.assertFalse(result["created"])
        self.assertEqual(result["commit"], "a" * 40)
        gh.assert_called_once_with(
            "repo", "view", "ctkrug/proofs-edge-case", "--json", "url,visibility", check=False,
        )
        self.assertIn(call(repo, "push", "--set-upstream", "origin", "main"), git.call_args_list)
        self.assertNotIn(call(repo, "remote", "add", "origin", self.remote_url), git.call_args_list)

    def test_dot_git_suffix_is_a_matching_origin(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)

            def fake_git(_repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
                if args == ("remote", "get-url", "origin"):
                    return _completed(args, stdout=f"{self.remote_url}.git\n")
                if args == ("rev-parse", "HEAD"):
                    return _completed(args, stdout="b" * 40 + "\n")
                return _completed(args)

            with patch.object(repositories, "ensure", return_value={"path": str(repo)}), \
                    patch.object(repositories, "_gh", return_value=_completed(
                        ["gh"], stdout=json.dumps({"url": self.remote_url, "visibility": "PUBLIC"}),
                    )), patch.object(repositories, "_git", side_effect=fake_git) as git:
                result = repositories._sync_problem(self.problem)

        self.assertEqual(result["commit"], "b" * 40)
        self.assertIn(call(repo, "push", "--set-upstream", "origin", "main"), git.call_args_list)
        self.assertNotIn(call(repo, "remote", "add", "origin", self.remote_url), git.call_args_list)

    def test_absent_repository_is_created_then_remote_added_and_pushed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            gh_results = [
                _completed(["gh"], returncode=1, stderr="not found"),
                _completed(["gh"]),
                _completed(["gh"], stdout=json.dumps({"url": self.remote_url, "visibility": "PUBLIC"})),
            ]

            def fake_git(_repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
                if args == ("remote", "get-url", "origin"):
                    return _completed(args, returncode=2, stderr="no such remote")
                if args == ("rev-parse", "HEAD"):
                    return _completed(args, stdout="b" * 40 + "\n")
                return _completed(args)

            with patch.object(repositories, "ensure", return_value={"path": str(repo)}), \
                    patch.object(repositories, "_gh", side_effect=gh_results) as gh, \
                    patch.object(repositories, "_git", side_effect=fake_git) as git:
                result = repositories._sync_problem(self.problem)

        self.assertTrue(result["created"])
        self.assertEqual(gh.call_args_list[1], call(
            "repo", "create", "ctkrug/proofs-edge-case", "--public",
            "--description", "Transparent Proof Factory research for Edge case",
        ))
        self.assertIn(call(repo, "remote", "add", "origin", self.remote_url), git.call_args_list)
        self.assertIn(call(repo, "push", "--set-upstream", "origin", "main"), git.call_args_list)

    def test_sync_all_writes_successful_repository_registry(self) -> None:
        problems = [{"id": "one"}, {"id": "two"}]
        synced = [
            {"problem_id": "one", "repository": "ctkrug/proofs-one", "url": "https://example/one",
             "visibility": "PUBLIC", "created": False, "commit": "1" * 40},
            {"problem_id": "two", "repository": "ctkrug/proofs-two", "url": "https://example/two",
             "visibility": "PUBLIC", "created": True, "commit": "2" * 40},
        ]
        with patch.object(store, "load_problems", return_value=problems), \
                patch.object(repositories, "_sync_problem", side_effect=synced), \
                patch.object(store, "write_json_atomic") as write:
            result = repositories.sync_all()

        self.assertEqual(result["synced"], 2)
        self.assertEqual(result["errors"], [])
        registry = write.call_args.args[1]
        self.assertEqual(write.call_args.args[0], store.DATA / "problem_repositories.json")
        self.assertNotIn("created", registry["repositories"][0])
        self.assertNotIn("created", registry["repositories"][1])

    def test_failed_lab_projection_is_durable_and_retried(self) -> None:
        with tempfile.TemporaryDirectory() as raw, patch.object(store, "STATE", Path(raw)):
            queued = repositories.queue_lab_projection(
                "p", "validated", {"id": "job"}, error="repository offline",
            )
            with patch.object(repositories, "record_lab", return_value={"commit": "a" * 40}) as record:
                result = repositories.retry_lab_projections()
            self.assertEqual(result["retried"], 1)
            self.assertEqual(result["remaining"], 0)
            record.assert_called_once_with("p", "validated", {"id": "job"})
            self.assertEqual(list((Path(raw) / "repository_projection_queue").glob("*.json")), [])
            self.assertEqual(len(queued["id"]), 64)

    def test_malformed_projection_receipt_is_retained_for_operator_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as raw, patch.object(store, "STATE", Path(raw)):
            queue = Path(raw) / "repository_projection_queue"
            queue.mkdir()
            malformed = queue / "truncated.json"
            malformed.write_text('{"schema_version":1')
            result = repositories.retry_lab_projections()
            self.assertEqual(result["retried"], 0)
            self.assertEqual(result["remaining"], 1)
            self.assertTrue(malformed.is_file())
            self.assertTrue(any("malformed projection retained" in error for error in result["errors"]))

    def test_legacy_projection_jsonl_is_atomically_imported_before_retry(self) -> None:
        with tempfile.TemporaryDirectory() as raw, patch.object(store, "STATE", Path(raw)):
            legacy = Path(raw) / "repository_projection_queue.jsonl"
            legacy.write_text(json.dumps({
                "schema_version": 1, "id": "a" * 64, "problem_id": "p",
                "event": "validated", "payload": {"id": "job"},
            }) + "\n")
            with patch.object(repositories, "record_lab", return_value={"commit": "b" * 40}) as record:
                result = repositories.retry_lab_projections()
            self.assertEqual(result["retried"], 1)
            self.assertEqual(result["remaining"], 0)
            self.assertFalse(legacy.exists())
            record.assert_called_once_with("p", "validated", {"id": "job"})

    def test_malformed_legacy_projection_jsonl_remains_byte_intact(self) -> None:
        with tempfile.TemporaryDirectory() as raw, patch.object(store, "STATE", Path(raw)):
            legacy = Path(raw) / "repository_projection_queue.jsonl"
            original = '{"schema_version":1\n'
            legacy.write_text(original)
            result = repositories.retry_lab_projections()
            self.assertEqual(result["remaining"], 1)
            self.assertEqual(legacy.read_text(), original)
            self.assertTrue(any("malformed legacy projection retained" in error for error in result["errors"]))

    def test_mismatched_existing_origin_fails_without_push(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)

            def fake_git(_repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
                if args == ("remote", "get-url", "origin"):
                    return _completed(args, stdout="https://github.com/someone/other\n")
                return _completed(args)

            with patch.object(repositories, "ensure", return_value={"path": str(repo)}), \
                    patch.object(repositories, "_gh", return_value=_completed(
                        ["gh"], stdout=json.dumps({"url": self.remote_url, "visibility": "PUBLIC"}),
                    )), patch.object(repositories, "_git", side_effect=fake_git) as git:
                with self.assertRaisesRegex(RuntimeError, "origin already points elsewhere"):
                    repositories._sync_problem(self.problem)

        self.assertFalse(any(args.args[1:2] == ("push",) for args in git.call_args_list))


class ResourceBootstrapTests(unittest.TestCase):
    body = b"record-one\nrecord-two\n"

    def spec(self, *, sha256: str | None = None, byte_count: int | None = None,
             record_count: int | None = 2) -> resources.SourceBootstrap:
        return resources.SourceBootstrap(
            problem_id="fixture", url="https://origin.test/data",
            destination="sources/data.txt",
            sha256=sha256 or hashlib.sha256(self.body).hexdigest(),
            byte_count=len(self.body) if byte_count is None else byte_count,
            record_count=record_count,
        )

    def test_unconfigured_problem_needs_no_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            self.assertIsNone(resources.prepare({"id": "unknown"}, Path(raw)))

    def test_valid_existing_source_uses_cache_without_curl(self) -> None:
        spec = self.spec()
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            target = workspace / spec.destination
            target.parent.mkdir(parents=True)
            target.write_bytes(self.body)
            Path(str(target) + ".provenance.json").write_text("{}\n")
            with patch.object(resources, "BOOTSTRAPS", {"fixture": spec}), \
                    patch.object(resources.shutil, "which") as which:
                result = resources.prepare({"id": "fixture"}, workspace)

        self.assertEqual(result, {"status": "cached", "path": str(target), "sha256": spec.sha256})
        which.assert_not_called()

    def test_retrieval_records_final_redirect_headers_and_authenticated_counts(self) -> None:
        spec = self.spec()

        def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            Path(command[command.index("--output") + 1]).write_bytes(self.body)
            Path(command[command.index("--dump-header") + 1]).write_text(
                "HTTP/1.1 301 Moved Permanently\r\nLocation: https://cdn.test/data\r\n\r\n"
                "HTTP/2 200\r\nContent-Type: application/x-graph6\r\nETag: final\r\n\r\n"
            )
            return _completed(command)

        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            with patch.object(resources, "BOOTSTRAPS", {"fixture": spec}), \
                    patch.object(resources.shutil, "which", return_value="/usr/bin/curl"), \
                    patch.object(resources.subprocess, "run", side_effect=fake_run):
                result = resources.prepare({"id": "fixture"}, workspace)
            provenance = json.loads(Path(str(workspace / spec.destination) + ".provenance.json").read_text())

        self.assertEqual(result["status"], "retrieved")
        self.assertEqual(provenance["sha256"], spec.sha256)
        self.assertEqual(provenance["byte_count"], len(self.body))
        self.assertEqual(provenance["record_count"], 2)
        self.assertEqual(provenance["content_type"], "application/x-graph6")
        self.assertEqual(provenance["response_headers"], {
            "content-type": "application/x-graph6", "etag": "final",
        })
        self.assertFalse(provenance["content_type_inferred"])

    def test_retrieval_rejects_wrong_hash_even_when_count_matches(self) -> None:
        spec = self.spec(sha256="0" * 64)

        def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            Path(command[command.index("--output") + 1]).write_bytes(self.body)
            Path(command[command.index("--dump-header") + 1]).write_text("HTTP/2 200\r\n\r\n")
            return _completed(command)

        with tempfile.TemporaryDirectory() as raw, \
                patch.object(resources, "BOOTSTRAPS", {"fixture": spec}), \
                patch.object(resources.shutil, "which", return_value="/usr/bin/curl"), \
                patch.object(resources.subprocess, "run", side_effect=fake_run):
            with self.assertRaisesRegex(resources.ResourceProvisionError, "failed frozen admission"):
                resources.prepare({"id": "fixture"}, Path(raw))

    def test_retrieval_rejects_wrong_record_count_even_when_hash_and_bytes_match(self) -> None:
        spec = self.spec(record_count=3)

        def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            Path(command[command.index("--output") + 1]).write_bytes(self.body)
            Path(command[command.index("--dump-header") + 1]).write_text("HTTP/2 200\r\n\r\n")
            return _completed(command)

        with tempfile.TemporaryDirectory() as raw, \
                patch.object(resources, "BOOTSTRAPS", {"fixture": spec}), \
                patch.object(resources.shutil, "which", return_value="/usr/bin/curl"), \
                patch.object(resources.subprocess, "run", side_effect=fake_run):
            with self.assertRaisesRegex(resources.ResourceProvisionError, "records=2"):
                resources.prepare({"id": "fixture"}, Path(raw))

    def test_missing_curl_fails_before_retrieval(self) -> None:
        spec = self.spec()
        with tempfile.TemporaryDirectory() as raw, \
                patch.object(resources, "BOOTSTRAPS", {"fixture": spec}), \
                patch.object(resources.shutil, "which", return_value=None):
            with self.assertRaisesRegex(resources.ResourceProvisionError, "curl is unavailable"):
                resources.prepare({"id": "fixture"}, Path(raw))

    def test_headers_use_only_final_response_and_handle_absence(self) -> None:
        self.assertEqual(resources._headers("not HTTP headers"), {})
        raw = (
            "HTTP/1.1 302 Found\r\nContent-Type: text/html\r\nLocation: /final\r\n\r\n"
            "HTTP/2 200\r\nETag: xyz\r\n\r\n"
        )
        self.assertEqual(resources._headers(raw), {"etag": "xyz"})


class WatchdogBoundaryTests(unittest.TestCase):
    fixed_now = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        fixed_now = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:
            return cls.fixed_now if tz is not None else cls.fixed_now.replace(tzinfo=None)

    def watchdog(
        self,
        *,
        attempts: list[dict[str, object]] | None = None,
        runtime: dict[str, object] | None = None,
        problems: list[dict[str, object]] | None = None,
        reviewable: list[dict[str, object]] | None = None,
        capacity_policy: dict[str, object] | None = None,
        easy_expected: str = "0",
    ) -> dict[str, object]:
        attempts = attempts or []
        runtime = runtime or {}
        problems = problems or []
        reviewable = reviewable or []
        capacity_policy = capacity_policy or {"allowed": True, "reasons": []}
        with tempfile.TemporaryDirectory() as raw, \
                patch.object(store, "SITE", Path(raw) / "site"), \
                patch.object(store, "load_attempts", return_value=attempts), \
                patch.object(store, "load_problems", return_value=problems), \
                patch.object(store, "runtime", return_value=runtime), \
                patch.object(store, "update_runtime", side_effect=lambda **fields: fields), \
                patch.object(store, "now_iso", return_value=self.fixed_now.isoformat()), \
                patch.object(scheduler, "datetime", self.FrozenDateTime), \
                patch.object(scheduler, "rendered_attempt_freshness", return_value={
                    "status": "fresh", "lag_seconds": 0, "latest_attempt_id": None,
                }), \
                patch.object(scheduler, "_reviewable_events", return_value=reviewable), \
                patch.object(capacity, "admission", return_value=capacity_policy), \
                patch.object(render, "build"), \
                patch.dict("os.environ", {"PROOF_EASY_EXPECTED": easy_expected}):
            return scheduler.watchdog()

    def test_capacity_rejection_degrades_watchdog(self) -> None:
        report = self.watchdog(capacity_policy={"allowed": False, "reasons": ["capacity reserve"]})
        self.assertEqual(report["health"], "degraded")
        self.assertIn("capacity reserve", report["health_issues"])

    def test_pending_hard_event_becomes_stale_only_after_six_hours(self) -> None:
        base = {"id": "hard", "lane": "hard", "problem_id": "ramsey", "outcome": "progress"}
        exact = self.watchdog(attempts=[{
            **base, "finished_at": (self.fixed_now - timedelta(hours=6)).isoformat(),
        }], reviewable=[{"id": "event"}])
        stale = self.watchdog(attempts=[{
            **base, "finished_at": (self.fixed_now - timedelta(hours=6, seconds=1)).isoformat(),
        }], reviewable=[{"id": "event"}])
        self.assertEqual(exact["health"], "healthy")
        self.assertIn("unconsumed evidence event", stale["health_issues"][0])

    def test_first_hard_review_ready_degrades_without_prior_hard_attempt(self) -> None:
        report = self.watchdog(
            problems=[{"id": "ramsey", "lane": "hard"}], reviewable=[{"id": "event"}],
        )
        self.assertTrue(any("has not completed its first review" in issue for issue in report["health_issues"]))

    def test_easy_attempt_becomes_stale_only_after_three_hours(self) -> None:
        base = {"id": "easy", "lane": "easy", "problem_id": "p", "outcome": "progress"}
        exact = self.watchdog(attempts=[{
            **base, "finished_at": (self.fixed_now - timedelta(hours=3)).isoformat(),
        }], easy_expected="1")
        stale = self.watchdog(attempts=[{
            **base, "finished_at": (self.fixed_now - timedelta(hours=3, seconds=1)).isoformat(),
        }], easy_expected="1")
        self.assertEqual(exact["health"], "healthy")
        self.assertTrue(any("more than 3 hours" in issue for issue in stale["health_issues"]))

    def test_missing_first_easy_attempt_degrades_after_03_utc(self) -> None:
        report = self.watchdog(easy_expected="1")
        self.assertTrue(any("has not completed its first attempt" in issue for issue in report["health_issues"]))

    def test_site_page_is_fresh_at_exactly_four_hours_then_stale(self) -> None:
        attempt = {"id": "page", "finished_at": (self.fixed_now - timedelta(hours=4)).isoformat()}
        with tempfile.TemporaryDirectory() as raw, patch.object(store, "SITE", Path(raw) / "site"):
            exact = scheduler.rendered_attempt_freshness([attempt], now=self.fixed_now)
            after = scheduler.rendered_attempt_freshness(
                [{**attempt, "finished_at": (self.fixed_now - timedelta(hours=4, seconds=1)).isoformat()}],
                now=self.fixed_now,
            )
        self.assertEqual(exact["status"], "fresh")
        self.assertEqual(exact["lag_seconds"], 4 * 3600)
        self.assertEqual(after["status"], "stale")


if __name__ == "__main__":
    unittest.main()
