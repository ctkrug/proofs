from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from typing import Any
from urllib.parse import urlparse

from . import intake, publication, render, research_state, scheduler, scout, store, strategy_lab


EXTERNAL_STATES = {
    "expert-confirmed", "repository-accepted", "venue-accepted", "peer-reviewed",
    "duplicate", "rejected", "corrected",
}


def _doctor() -> dict[str, Any]:
    problems = store.load_problems()
    attempts = store.load_attempts()
    codex_bin = os.environ.get("CODEX_BIN", "codex")
    checks: dict[str, Any] = {
        "problems": bool(problems),
        "attempt_log_valid": isinstance(attempts, list),
        "codex_binary": bool(shutil.which(codex_bin)),
    }
    if checks["codex_binary"]:
        proc = subprocess.run([codex_bin, "login", "status"], text=True, capture_output=True, timeout=30)
        checks["codex_login"] = proc.returncode == 0 and "logged in" in (proc.stdout + proc.stderr).lower()
    else:
        checks["codex_login"] = False
    checks["ok"] = all(bool(value) for key, value in checks.items() if key != "ok")
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
    return 2
