from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from typing import Any

from . import intake, render, scheduler, store


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


def _review(attempt_id: str, decision: str, note: str) -> dict[str, Any]:
    if decision not in {"accept", "reject", "needs-work"}:
        raise ValueError("decision must be accept, reject, or needs-work")
    with store.lock("state") as acquired:
        if not acquired:
            raise RuntimeError("state lock unavailable")
        attempts = store.load_attempts()
        attempt = next((row for row in attempts if row.get("id") == attempt_id), None)
        if not attempt:
            raise ValueError(f"unknown attempt: {attempt_id}")
        if decision == "accept" and attempt.get("outcome") != "candidate":
            raise ValueError("only a candidate attempt can be accepted as a result")
        if decision == "accept" and not note.strip():
            raise ValueError("accepting a result requires a human review note")
        problems = store.load_problems()
        problem = next(row for row in problems if row["id"] == attempt["problem_id"])
        reviews = store.read_json(store.DATA / "reviews.json", [])
        record = {
            "attempt_id": attempt_id,
            "problem_id": problem["id"],
            "decision": decision,
            "note": note,
            "reviewed_at": store.now_iso(),
            "reviewer": "Charlie Krug",
        }
        reviews.append(record)
        store.write_json_atomic(store.DATA / "reviews.json", reviews)
        if decision == "accept":
            problem["status"] = "verified"
            problem["accepted_result"] = True
        elif decision == "reject":
            problem["status"] = "attempted"
            problem.pop("candidate_attempt_id", None)
        else:
            problem["status"] = "candidate"
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
    intake_parser = sub.add_parser("intake")
    intake_parser.add_argument("--target", type=int, default=12)
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
        print(json.dumps(_review(args.attempt, args.decision, args.note), indent=2))
        return 0
    if args.command == "intake":
        result = intake.replenish(target=args.target)
        if result["added"]:
            render.build()
        print(json.dumps(result, indent=2))
        return 0
    return 2
