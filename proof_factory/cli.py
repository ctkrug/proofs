from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import brain, capacity, events, intake, lab, prior_art, publication, render, repositories, research_state, roadmap, scheduler, scout, store, strategy_lab, tactics


EXTERNAL_STATES = {
    "expert-confirmed", "repository-accepted", "venue-accepted", "peer-reviewed",
    "duplicate", "rejected", "corrected",
}


def _doctor() -> dict[str, Any]:
    problems = store.load_problems()
    attempts = store.load_attempts()
    codex_bin = os.environ.get("CODEX_BIN", "codex")
    lab_python = store.ROOT / ".lab-venv" / "bin" / "python"
    repo_status = repositories.status()
    repo_registry = store.read_json(store.DATA / "problem_repositories.json", {})
    checks: dict[str, Any] = {
        "problems": bool(problems),
        "attempt_log_valid": isinstance(attempts, list),
        "codex_binary": bool(shutil.which(codex_bin)),
        "lab_runner": lab.RUNNER.is_file(),
        "research_brain": bool(brain.build().get("nodes")),
        "lab_python": lab_python.is_file(),
        "problem_repositories": repo_status["initialized"] == repo_status["problems"],
        "problem_repository_remotes": (
            repo_status["remotes"] == repo_status["problems"]
            and isinstance(repo_registry, dict) and not repo_registry.get("errors")
        ),
    }
    if checks["codex_binary"]:
        proc = subprocess.run([codex_bin, "login", "status"], text=True, capture_output=True, timeout=30)
        checks["codex_login"] = proc.returncode == 0 and "logged in" in (proc.stdout + proc.stderr).lower()
    else:
        checks["codex_login"] = False
    checks["simulation_tools"] = {
        name: shutil.which(name) for name in sorted(lab.ALLOWED_EXECUTABLES)
    }
    if checks["lab_python"]:
        proc = subprocess.run([
            str(lab_python), "-c",
            "import networkx,numpy,scipy,sympy,z3,pulp; assert numpy.__version__=='1.26.4'; assert scipy.__version__=='1.11.4'",
        ], text=True, capture_output=True, timeout=30)
        checks["lab_python_imports"] = proc.returncode == 0
    else:
        # Local development can use its own Python; production requires the pinned environment.
        checks["lab_python_imports"] = store.ROOT != Path("/root/proof-factory")
    checks["ok"] = all(bool(checks[key]) for key in (
        "problems", "attempt_log_valid", "codex_binary", "codex_login", "lab_runner", "research_brain",
        "lab_python_imports", "problem_repositories", "problem_repository_remotes",
    ))
    return checks


def _review(
    attempt_id: str, decision: str, note: str, *, release: bool = False, reviewer: str = "Charlie Krug"
) -> dict[str, Any]:
    if decision not in {"accept", "reject", "needs-work"}:
        raise ValueError("decision must be accept, reject, or needs-work")
    if not reviewer.strip():
        raise ValueError("reviewer is required")
    if decision == "accept" and reviewer != "Charlie Krug":
        raise ValueError("only Charlie Krug can accept a result")
    with store.lock("state") as acquired:
        if not acquired:
            raise RuntimeError("state lock unavailable")
        attempts = store.load_attempts()
        attempt = next((row for row in attempts if row.get("id") == attempt_id), None)
        if not attempt:
            raise ValueError(f"unknown attempt: {attempt_id}")
        reviews = store.read_json(store.DATA / "reviews.json", [])
        prior_reviews = [row for row in reviews if row.get("attempt_id") == attempt_id]
        if decision == "accept" and attempt.get("outcome") != "candidate":
            raise ValueError("only a candidate attempt can be accepted as a result")
        if decision == "accept" and prior_reviews and prior_reviews[-1].get("display_status") == "internal_result":
            raise ValueError("an internal result must pass a new contribution gate before it can be accepted")
        gate = attempt.get("contribution_gate") if isinstance(attempt.get("contribution_gate"), dict) else {}
        if decision == "accept" and gate and not gate.get("passed"):
            raise ValueError("the attempt did not pass the contribution gate")
        if decision == "accept" and not note.strip():
            raise ValueError("accepting a result requires a human review note")
        if release and decision != "accept":
            raise ValueError("only an accepted candidate can be released")
        problems = store.load_problems()
        problem = next(row for row in problems if row["id"] == attempt["problem_id"])
        record = {
            "attempt_id": attempt_id,
            "problem_id": problem["id"],
            "decision": decision,
            "note": note,
            "reviewed_at": store.now_iso(),
            "reviewer": reviewer,
            "display_status": "internal_result" if decision == "reject" else "candidate",
        }
        reviews.append(record)
        if decision == "accept":
            packet = publication.build_packet(problem, attempt, record)
            problem["status"] = "published" if release else "verified"
            problem["human_approved"] = True
            problem["accepted_result"] = False
            problem["approved_packet"] = str(packet.relative_to(store.ROOT))
            if release:
                problem["publication_attempt_id"] = attempt_id
                problem["publication_packet"] = str(packet.relative_to(store.ROOT))
                problem["publication_state"] = "public research note"
        elif decision == "reject":
            if problem.get("status") != "parked":
                problem["status"] = "attempted"
            problem.pop("candidate_attempt_id", None)
        else:
            problem["status"] = "candidate"
        store.write_json_atomic(store.DATA / "reviews.json", reviews)
        store.save_problems(problems)
    render.build()
    return record


def _external_validation(attempt_id: str, state: str, source_url: str, note: str) -> dict[str, Any]:
    if state not in EXTERNAL_STATES:
        raise ValueError(f"invalid external validation state: {state}")
    positive = {"expert-confirmed", "repository-accepted", "venue-accepted", "peer-reviewed"}
    if state in positive and not source_url.strip():
        raise ValueError("positive external validation requires a public source URL")
    if source_url and urlparse(source_url).scheme not in {"http", "https"}:
        raise ValueError("external validation URL must use http or https")
    if not note.strip():
        raise ValueError("external validation requires a note")
    with store.lock("state") as acquired:
        if not acquired:
            raise RuntimeError("state lock unavailable")
        attempt = next((row for row in store.load_attempts() if row.get("id") == attempt_id), None)
        if not attempt:
            raise ValueError(f"unknown attempt: {attempt_id}")
        problems = store.load_problems()
        problem = next(row for row in problems if row["id"] == attempt["problem_id"])
        record = {
            "attempt_id": attempt_id,
            "problem_id": problem["id"],
            "state": state,
            "source_url": source_url,
            "note": note,
            "recorded_at": store.now_iso(),
            "recorded_by": "Charlie Krug",
        }
        validations = store.read_json(store.DATA / "validations.json", [])
        validations.append(record)
        store.write_json_atomic(store.DATA / "validations.json", validations)
        problem["external_validation_state"] = state
        problem["external_validation_url"] = source_url
        problem["accepted_result"] = state in positive
        store.save_problems(problems)
    render.build()
    return record


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="proof-factory")
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("render")
    sub.add_parser("status")
    sub.add_parser("doctor")
    watch = sub.add_parser("watchdog")
    watch.add_argument("--publish", action="store_true")
    guard = sub.add_parser("capacity-guard")
    guard.add_argument("--lane", choices=("easy", "hard"), default="easy")
    tick = sub.add_parser("tick")
    tick.add_argument("--lane", choices=("easy", "hard"), required=True)
    tick.add_argument("--publish", action="store_true")
    review = sub.add_parser("review")
    review.add_argument("--attempt", required=True)
    review.add_argument("--decision", choices=("accept", "reject", "needs-work"), required=True)
    review.add_argument("--note", default="")
    review.add_argument("--reviewer", default="Charlie Krug")
    review.add_argument("--release", action="store_true", help="publish the approved research-note packet")
    validate = sub.add_parser("validate")
    validate.add_argument("--attempt", required=True)
    validate.add_argument("--state", choices=sorted(EXTERNAL_STATES), required=True)
    validate.add_argument("--source-url", default="")
    validate.add_argument("--note", required=True)
    intake_parser = sub.add_parser("intake")
    intake_parser.add_argument("--target", type=int, default=12)
    sub.add_parser("scout")
    sub.add_parser("strategy-lab")
    sub.add_parser("backfill-state")
    sub.add_parser("brain-build")
    tactical = sub.add_parser("tactics-show")
    tactical.add_argument("--problem", required=True)
    roadmap_parser = sub.add_parser("roadmap-show")
    roadmap_parser.add_argument("--problem", required=True)
    prior_art_parser = sub.add_parser("prior-art-show")
    prior_art_parser.add_argument("--problem", required=True)
    reconcile_parser = sub.add_parser("state-reconcile")
    reconcile_parser.add_argument("--problem", required=True)
    reconcile_parser.add_argument("--write", action="store_true")
    event_parser = sub.add_parser("research-event")
    event_parser.add_argument("--problem", required=True)
    event_parser.add_argument("--kind", choices=sorted(events.ALLOWED_KINDS), required=True)
    event_parser.add_argument("--evidence", required=True)
    event_parser.add_argument("--source", required=True)
    repo_init = sub.add_parser("repo-init")
    repo_init.add_argument("--problem")
    repo_init.add_argument("--all", action="store_true")
    sub.add_parser("repo-backfill")
    sub.add_parser("repo-status")
    sub.add_parser("repo-sync")
    lab_status = sub.add_parser("lab-status")
    lab_status.add_argument("--problem")
    lab_worker = sub.add_parser("lab-worker")
    lab_worker.add_argument("--drain", action="store_true", help="run bounded segments continuously until review is due")
    lab_review = sub.add_parser("lab-review")
    lab_review.add_argument("--job", required=True)
    lab_review.add_argument("--decision", choices=sorted(lab.REVIEW_DECISIONS), required=True)
    lab_review.add_argument("--reason", required=True)
    lab_review.add_argument("--reviewer", default="operator")
    lab_submit = sub.add_parser("lab-submit")
    lab_submit.add_argument("--problem", required=True)
    lab_submit.add_argument("--name", required=True)
    lab_submit.add_argument("--hypothesis", required=True)
    lab_submit.add_argument("--expected-signal", required=True)
    lab_submit.add_argument("--decision-value", required=True)
    lab_submit.add_argument("--efficiency-design", required=True, help="JSON efficiency-design report")
    lab_submit.add_argument("--source-url", action="append", default=[])
    lab_submit.add_argument("--segment-seconds", type=int, default=3600)
    lab_submit.add_argument("--max-segments", type=int, default=1)
    lab_submit.add_argument("--memory-mb", type=int, default=512)
    lab_submit.add_argument("--seed", type=int, default=0)
    lab_submit.add_argument("--checkpoint-path", default="")
    lab_submit.add_argument("--progress-path", default="")
    lab_submit.add_argument("--pilot-segments", type=int, default=1)
    lab_submit.add_argument("--review-every-segments", type=int, default=1)
    lab_submit.add_argument("--min-throughput", type=float, default=0.0)
    lab_submit.add_argument("--max-artifact-growth-bytes", type=int, default=0)
    lab_submit.add_argument("--no-correctness-gate", action="store_true")
    lab_submit.add_argument("argv", nargs=argparse.REMAINDER)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "render":
        print(render.build())
        return 0
    if args.command == "status":
        print(json.dumps(scheduler.status(), indent=2))
        return 0
    if args.command == "doctor":
        result = _doctor()
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    if args.command == "watchdog":
        print(json.dumps(scheduler.watchdog(publish=args.publish), indent=2))
        return 0
    if args.command == "capacity-guard":
        result = capacity.admission(args.lane)
        print(json.dumps(result, indent=2))
        # Capacity pressure is an expected protected state; scheduler admission
        # records the deferment, so the maintenance timer itself stays healthy.
        return 0
    if args.command == "tick":
        print(json.dumps(scheduler.tick(args.lane, publish=args.publish), indent=2))
        return 0
    if args.command == "review":
        print(json.dumps(_review(
            args.attempt, args.decision, args.note, release=args.release, reviewer=args.reviewer
        ), indent=2))
        return 0
    if args.command == "validate":
        print(json.dumps(_external_validation(args.attempt, args.state, args.source_url, args.note), indent=2))
        return 0
    if args.command == "intake":
        result = intake.replenish(target=args.target)
        if result["added"]:
            render.build()
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "scout":
        result = scout.run()
        if result.get("added"):
            render.build()
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "strategy-lab":
        result = strategy_lab.run()
        render.build()
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "backfill-state":
        result = research_state.backfill()
        render.build()
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "brain-build":
        graph = brain.refresh()
        render.build()
        print(json.dumps(brain.summary(graph), indent=2))
        return 0
    if args.command == "tactics-show":
        problem = next((row for row in store.load_problems() if row["id"] == args.problem), None)
        if not problem:
            raise ValueError(f"unknown problem: {args.problem}")
        print(json.dumps(tactics.build(problem), indent=2))
        return 0
    if args.command == "roadmap-show":
        problem = next((row for row in store.load_problems() if row["id"] == args.problem), None)
        if not problem:
            raise ValueError(f"unknown problem: {args.problem}")
        print(json.dumps(roadmap.current(problem), indent=2))
        return 0
    if args.command == "prior-art-show":
        problem = next((row for row in store.load_problems() if row["id"] == args.problem), None)
        if not problem:
            raise ValueError(f"unknown problem: {args.problem}")
        print(json.dumps(prior_art.load(problem), indent=2))
        return 0
    if args.command == "state-reconcile":
        problem = next((row for row in store.load_problems() if row["id"] == args.problem), None)
        if not problem:
            raise ValueError(f"unknown problem: {args.problem}")
        print(json.dumps(research_state.reconcile(problem, write=args.write), indent=2))
        return 0
    if args.command == "research-event":
        print(json.dumps(events.enqueue(
            args.problem, args.kind, evidence=args.evidence, source=args.source,
        ), indent=2))
        return 0
    if args.command == "repo-init":
        if args.all == bool(args.problem):
            raise ValueError("repo-init requires exactly one of --all or --problem")
        result = repositories.initialize_all() if args.all else repositories.ensure(
            next(row for row in store.load_problems() if row["id"] == args.problem)
        )
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "repo-status":
        print(json.dumps(repositories.status(), indent=2))
        return 0
    if args.command == "repo-backfill":
        print(json.dumps(repositories.backfill(), indent=2))
        return 0
    if args.command == "repo-sync":
        result = repositories.sync_all()
        print(json.dumps(result, indent=2))
        return 1 if result["errors"] else 0
    if args.command == "lab-status":
        print(json.dumps(lab.status(args.problem), indent=2))
        return 0
    if args.command == "lab-worker":
        print(json.dumps(lab.worker_tranche() if args.drain else lab.worker_once(), indent=2))
        return 0
    if args.command == "lab-review":
        print(json.dumps(lab.apply_review(args.job, args.decision, reason=args.reason, reviewer=args.reviewer), indent=2))
        return 0
    if args.command == "lab-submit":
        command = list(args.argv)
        if command[:1] == ["--"]:
            command = command[1:]
        efficiency = json.loads(Path(args.efficiency_design).read_text())
        result = lab.submit({
            "problem_id": args.problem, "name": args.name, "hypothesis": args.hypothesis,
            "expected_signal": args.expected_signal, "decision_value": args.decision_value,
            "efficiency_design": efficiency, "source_urls": args.source_url,
            "segment_seconds": args.segment_seconds, "max_segments": args.max_segments,
            "memory_mb": args.memory_mb, "seed": args.seed,
            "checkpoint_path": args.checkpoint_path, "progress_path": args.progress_path,
            "pilot_segments": args.pilot_segments, "review_every_segments": args.review_every_segments,
            "continuation_thresholds": {
                "min_throughput_per_second": args.min_throughput,
                "max_artifact_growth_bytes": args.max_artifact_growth_bytes,
                "require_correctness_checks": not args.no_correctness_gate,
            }, "command": command,
        })
        print(json.dumps(result, indent=2))
        return 0
    return 2
