"""Best-effort Phoenix tracing for Proof Factory research epochs.

The proof engine invokes Codex through a subprocess, so SDK auto-instrumentation
cannot observe its LLM calls.  This module reconstructs compact OpenInference LLM
spans from the CLI JSONL envelope instead.  It is deliberately optional: a missing
dependency, credential, or collector must never alter research scheduling or an
attempt's outcome.
"""
from __future__ import annotations

import atexit
import json
import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator

from . import config


log = logging.getLogger("proof_factory.telemetry")
_tracer = None
_state = "off"


def _enabled() -> bool:
    return config.get_bool("PHOENIX_ENABLED", False)


def _text(value: str) -> str:
    if not config.get_bool("PHOENIX_CAPTURE_TEXT", True):
        return ""
    limit = config.get_int("PHOENIX_TEXT_LIMIT", 6000, minimum=0, maximum=1_000_000)
    value = value or ""
    return value if len(value) <= limit else value[:limit] + f"\n…[truncated {len(value) - limit} chars]"


def init():
    """Return an OTel tracer, or ``None`` when telemetry is intentionally unavailable."""
    global _tracer, _state
    if _tracer is not None or _state == "failed" or not _enabled():
        return _tracer
    endpoint = config.get_https_url("PHOENIX_ENDPOINT", "", allow_empty=True)
    if not endpoint:
        _state = "failed"
        log.warning("PHOENIX_ENABLED is set but PHOENIX_ENDPOINT is absent; continuing uninstrumented")
        return None
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        headers = {}
        if api_key := os.environ.get("PHOENIX_API_KEY"):
            headers["authorization"] = f"Bearer {api_key}"
        provider = TracerProvider(resource=Resource.create({
            "service.name": "proof-factory",
            "openinference.project.name": config.get_text("PHOENIX_PROJECT", "proof-factory"),
        }))
        provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(
            endpoint=f"{endpoint}/v1/traces", headers=headers,
        )))
        _tracer = provider.get_tracer("proof_factory")
        atexit.register(lambda: provider.force_flush(timeout_millis=5000))
        _state = "on"
    except Exception as exc:  # optional observability never breaks the engine
        _state = "failed"
        log.warning("Phoenix telemetry unavailable (%s); continuing uninstrumented", type(exc).__name__)
    return _tracer


def _set(handle: Any, attrs: dict[str, Any]) -> None:
    for key, value in attrs.items():
        if value is None:
            continue
        if not isinstance(value, (str, bool, int, float)):
            value = json.dumps(value, default=str)[:2000]
        handle.set_attribute(key, value)


@contextmanager
def span(name: str, kind: str, attrs: dict[str, Any] | None = None) -> Iterator[None]:
    tracer = init()
    if tracer is None:
        yield
        return
    try:
        with tracer.start_as_current_span(name) as current:
            _set(current, {"openinference.span.kind": kind, **(attrs or {})})
            yield
    except Exception as exc:
        # Export/network errors are swallowed by the exporter. This only catches an
        # instrumentation failure, never an exception raised by the research itself.
        log.debug("Phoenix span failed: %s", exc)
        raise


def codex_call(*, prompt: str, output: str, usage: dict[str, Any], model: str,
               effort: str, role: str, lane: str, problem_id: str, phase: str,
               duration_seconds: float, outcome: str) -> None:
    token_fields = {
        "input_tokens": "llm.token_count.prompt",
        "output_tokens": "llm.token_count.completion",
        "total_tokens": "llm.token_count.total",
        "cached_input_tokens": "proof.tokens.cached_input",
        "reasoning_output_tokens": "proof.tokens.reasoning_output",
    }
    attrs: dict[str, Any] = {
        "llm.model_name": model,
        "llm.provider": "openai",
        "llm.invocation_parameters": json.dumps({"effort": effort, "runtime": "codex-cli", "output_format": "jsonl"}),
        "input.value": _text(prompt), "output.value": _text(output),
        "proof.role": role, "proof.lane": lane, "proof.problem_id": problem_id,
        "proof.phase": phase, "proof.duration_seconds": round(duration_seconds, 1),
        "proof.outcome": outcome,
    }
    for source, target in token_fields.items():
        if usage.get(source) is not None:
            attrs[target] = int(usage[source])
    if attrs.get("llm.token_count.total") is None:
        attrs["llm.token_count.total"] = int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0)
    with span("proof.codex", "LLM", attrs):
        pass


def epoch_summary(attempt: dict[str, Any]) -> None:
    """Emit the monitor-friendly progress and prompt-contract record for an epoch."""
    gate = attempt.get("contribution_gate") or {}
    flags = attempt.get("policy_flags") or []
    checker = str(attempt.get("independent_checker") or "").strip().lower()
    citations = {str(row) for row in attempt.get("citations") or [] if str(row).startswith(("http://", "https://"))}
    valid_contract = attempt.get("outcome") != "error"
    # A deterministic prompt-quality proxy: it rates the observable instruction-following
    # contract, not mathematical truth. Truth remains gated by independent verification.
    quality = sum((
        valid_contract,
        bool(attempt.get("evidence")),
        checker not in {"", "not provided", "not applicable"},
        len(citations) >= 1,
        not flags,
    ))
    attrs = {
        "proof.attempt_id": attempt.get("id"), "proof.problem_id": attempt.get("problem_id"),
        "proof.lane": attempt.get("lane"), "proof.phase": attempt.get("phase"),
        "proof.outcome": attempt.get("outcome"), "proof.duration_seconds": attempt.get("duration_seconds"),
        "proof.prompt_contract_valid": valid_contract, "proof.prompt_quality_score": quality,
        "proof.prompt_quality_scale": "0-5 deterministic instruction-following proxy",
        "proof.evidence_count": len(attempt.get("evidence") or []),
        "proof.citation_count": len(citations), "proof.policy_flag_count": len(flags),
        "proof.contribution_gate_passed": bool(gate.get("passed")),
        "proof.contribution_gate_status": gate.get("status", "not_requested"),
        "proof.research_mode": attempt.get("research_mode"),
        "proof.strategy_status": attempt.get("strategy_status"),
    }
    with span("proof.epoch", "CHAIN", attrs):
        pass
