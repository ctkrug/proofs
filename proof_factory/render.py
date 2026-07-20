from __future__ import annotations

import html
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import brain, research_state, store


STATUS_ORDER = ["candidate", "active", "attempted", "internal_result", "failed", "queued", "parked", "verified", "published"]
STATUS_LABELS = {
    "queued": "Queued",
    "active": "Active / ongoing",
    "attempted": "Tried — still open",
    "parked": "Paused after 3 passes",
    "failed": "Failed route",
    "candidate": "Candidate — review needed",
    "internal_result": "Internal result — value unestablished",
    "verified": "Verified",
    "published": "Public research note",
}


def h(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def _time(value: str | None) -> str:
    dt = store.parse_iso(value)
    if not dt:
        return "Not yet"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _badge(status: str) -> str:
    label = STATUS_LABELS.get(status, status.replace("_", " ").title())
    return f'<span class="badge badge-{h(status)}">{h(label)}</span>'


def _layout(title: str, body: str, *, description: str = "Ongoing and planned AI-assisted mathematics research.") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#07100e">
  <title>{h(title)} · Proof Factory</title>
  <meta name="description" content="{h(description)}">
  <link rel="stylesheet" href="/assets/site-v3.css">
  <script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token":"153bb72472fb49d8863fb2f8f08f6b2b"}}'></script>
  <script>MathJax={{tex:{{inlineMath:[['$','$'],['\\(','\\)']]}}}};</script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
</head>
<body>
  <a class="skip-link" href="#content">Skip to content</a>
  <header class="topbar">
    <a class="brand" href="/"><span class="brand-mark">PF</span><span>Proof Factory</span><small>Research system / 01</small></a>
    <nav aria-label="Primary"><a href="/#ongoing">Ongoing</a><a href="/#planned">Planned</a><a href="/#attempts">Attempts</a><a href="/about/">About</a></nav>
  </header>
  <main id="content">{body}</main>
  <footer><span>Proof Factory / AI-assisted mathematics research</span><span>Seeking useful contributions, small or large</span><span>UTC · <a href="https://github.com/ctkrug/proofs">Source</a></span></footer>
</body>
</html>"""


def _effective_outcome(attempt: dict[str, Any], reviews: list[dict[str, Any]]) -> str:
    latest = reviews[-1] if reviews else {}
    if attempt.get("outcome") == "candidate" and latest.get("display_status") == "internal_result":
        return "internal_result"
    return str(attempt.get("outcome") or "unknown")


def _attempt_row(attempt: dict[str, Any], problem: dict[str, Any], reviews: list[dict[str, Any]] | None = None) -> str:
    outcome = _effective_outcome(attempt, reviews or [])
    label = STATUS_LABELS.get(outcome, outcome.replace("_", " ").title())
    return f"""
<article class="attempt-row" data-outcome="{h(outcome)}">
  <div class="attempt-rail outcome-{h(outcome)}"></div>
  <div class="attempt-copy">
    <div class="eyebrow"><span>{h(_time(attempt.get('finished_at')))}</span><span>{h(attempt.get('model'))} · {h(attempt.get('effort'))}</span></div>
    <h3><a href="/attempts/{h(attempt['id'])}/">{h(problem['title'])}</a></h3>
    <p class="approach">{h(attempt.get('approach'))}</p>
    <p>{h(attempt.get('summary'))}</p>
    <div class="row-end"><span class="badge badge-{h(outcome)}">{h(label)}</span><a class="arrow" href="/attempts/{h(attempt['id'])}/">Evidence →</a></div>
  </div>
</article>"""


def _problem_card(problem: dict[str, Any], attempts: list[dict[str, Any]], state: dict[str, Any]) -> str:
    last = attempts[-1] if attempts else None
    status = str(problem.get("status") or "queued")
    lane = str(problem.get("lane") or "easy")
    return f"""
<article class="problem-card" data-status="{h(status)}" data-lane="{h(lane)}">
  <div class="card-top"><span class="lane lane-{h(lane)}">{h(lane)}</span>{_badge(status)}</div>
  <h3><a href="/problems/{h(problem['id'])}/">{h(problem['title'])}</a></h3>
  <p>{h(problem.get('statement'))}</p>
  <div class="meter"><span style="width:{min(100, int(problem.get('difficulty') or 0) * 10)}%"></span></div>
  <div class="card-meta"><span>Difficulty {h(problem.get('difficulty'))}/10</span><span>{h(problem.get('attempt_count', 0))} attempts · {h(research_state.summary_counts(state)['open_leads'])} open leads</span></div>
  <div class="last-note"><strong>Latest:</strong> {h((last or {}).get('summary') or 'No research pass yet.')}</div>
  <div class="card-actions"><a href="{h(problem.get('source_url'))}" rel="noopener">Official source ↗</a><a href="/problems/{h(problem['id'])}/">Full record →</a></div>
</article>"""


def _index(
    problems: list[dict[str, Any]], attempts: list[dict[str, Any]], runtime: dict[str, Any], reviews: list[dict[str, Any]]
) -> str:
    states = research_state.load_all(problems)
    by_problem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        by_problem[str(attempt.get("problem_id"))].append(attempt)
    reviews_by_attempt: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for review in reviews:
        reviews_by_attempt[str(review.get("attempt_id"))].append(review)
    candidates = [row for row in problems if row.get("status") == "candidate"]
    health = runtime.get("health", "starting")
    health_issues = runtime.get("health_issues") or []
    running_lanes = [lane for lane in ("hard", "easy") if runtime.get(f"{lane}_running")]
    ordered = lambda rows: sorted(
        rows,
        key=lambda row: (
            STATUS_ORDER.index(row.get("status")) if row.get("status") in STATUS_ORDER else 99,
            0 if row.get("lane") == "hard" else 1,
            int(row.get("difficulty") or 10),
        ),
    )
    ongoing = ordered([row for row in problems if row.get("status") in {"active", "attempted", "candidate"}])
    planned = ordered([row for row in problems if row.get("status") == "queued"])
    candidate_banner = ""
    if candidates:
        candidate_banner = f"""<section class="candidate-alert"><div><span class="pulse"></span><strong>{len(candidates)} candidate finding{'s' if len(candidates) != 1 else ''} need review.</strong><p>Candidate means unverified. It is not a solved claim.</p></div><a href="#problems">Review records →</a></section>"""
    issues = "" if not health_issues else " · ".join(h(x) for x in health_issues)
    live_work = (
        "No pass currently running" if not running_lanes
        else f"Active now: {', '.join(running_lanes)} lane{'s' if len(running_lanes) != 1 else ''}"
    )
    body = f"""
<section class="hero">
  <div class="hero-kicker"><span class="live-dot"></span> AI-ASSISTED MATHEMATICS RESEARCH / LIVE</div>
  <h1>Current<br><em>research.</em></h1>
  <p class="hero-copy">Proof Factory seeks to contribute useful mathematics, no matter how small or large. This site shows the work underway, what is planned next, and the attempts made so far.</p>
</section>
{candidate_banner}
<section class="healthline"><span class="health health-{h(health)}">System {h(health)}</span><span>{h(live_work)}</span><span>Updated {_time(runtime.get('updated_at') or store.now_iso())}</span><span>{issues}</span></section>
<section id="ongoing" class="section-block">
  <div class="section-heading"><div><span class="overline">WORK UNDERWAY</span><h2>Ongoing work</h2></div><span class="section-note">R(5,5) hourly · discovery 12 times daily</span></div>
  <div class="problem-grid">{''.join(_problem_card(row, by_problem[row['id']], states[row['id']]) for row in ongoing) or '<p class="empty">No research pass is currently open.</p>'}</div>
</section>
<section id="planned" class="section-block planned-block">
  <div class="section-heading"><div><span class="overline">NEXT IN QUEUE</span><h2>Planned work</h2></div></div>
  <div class="problem-grid">{''.join(_problem_card(row, by_problem[row['id']], states[row['id']]) for row in planned) or '<p class="empty">No additional work is queued.</p>'}</div>
</section>
<section id="attempts" class="section-block attempts-block">
  <div class="section-heading"><div><span class="overline">RESEARCH RECORD</span><h2>Recent attempts</h2></div></div>
  <div class="attempt-list">{''.join(_attempt_row(row, next(p for p in problems if p['id'] == row['problem_id']), reviews_by_attempt[str(row.get('id'))]) for row in reversed(attempts[-25:])) or '<p>No attempts yet.</p>'}</div>
</section>
"""
    return _layout("Research work", body)


def _state_items(rows: list[dict[str, Any]], primary: str, secondary: str, *, empty: str) -> str:
    if not rows:
        return f"<li>{h(empty)}</li>"
    result = []
    for row in rows:
        reopen = f'<br><em>Reopen only if:</em> {h(row.get("reopen_condition"))}' if row.get("reopen_condition") else ""
        result.append(f'<li><strong>{h(row.get(primary))}</strong><br>{h(row.get(secondary))}{reopen}</li>')
    return "".join(result)


def _problem_page(
    problem: dict[str, Any], attempts: list[dict[str, Any]], state: dict[str, Any], reviews: list[dict[str, Any]]
) -> str:
    technique_tags = "".join(f"<span>{h(x)}</span>" for x in problem.get("techniques") or [])
    reviews_by_attempt: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for review in reviews:
        reviews_by_attempt[str(review.get("attempt_id"))].append(review)
    attempt_html = "".join(
        _attempt_row(row, problem, reviews_by_attempt[str(row.get("id"))]) for row in reversed(attempts)
    ) or '<div class="empty">No attempt has completed yet. The problem is queued transparently.</div>'
    candidate = ""
    if problem.get("status") == "candidate":
        candidate = '<div class="candidate-alert"><div><strong>Unverified candidate finding</strong><p>Read the attempt and evidence below. This is not an accepted solution.</p></div></div>'
    counts = research_state.summary_counts(state)
    strategies = list(reversed(state.get("strategies", [])[-12:]))
    ruled = list(reversed(state.get("ruled_out", [])[-10:]))
    leads = [row for row in state.get("open_leads", [])[-10:] if row.get("status", "open") == "open"]
    checkpoint = state.get("next_session", {})
    research_map = f"""
<section class="research-map">
  <div class="section-heading"><div><span class="overline">Resumable campaign memory</span><h2>Research map</h2></div><span>{h(state.get('epoch_count', 0))} epochs · {counts['promising']} promising · {counts['blocked']} blocked · {counts['ruled_out']} ruled out</span></div>
  <div class="research-grid">
    <article><span class="overline">Next session checkpoint</span><h3>{h(checkpoint.get('objective') or 'Select the cheapest new discriminator.')}</h3><p><strong>First action:</strong> {h(checkpoint.get('first_action') or 'Review the source and strategy registry.')}</p><p><strong>Stop or redirect when:</strong> {h(checkpoint.get('stop_condition') or 'The planned discriminator resolves the route.')}</p></article>
    <article><span class="overline">Open leads</span><ul>{_state_items(leads, 'description', 'next_experiment', empty='No open lead is checkpointed.')}</ul></article>
    <article><span class="overline">Strategy registry</span><ul>{_state_items(strategies, 'family', 'mechanism', empty='No strategy has completed an epoch yet.')}</ul></article>
    <article><span class="overline">Ruled out, with scope</span><ul>{_state_items(ruled, 'claim_or_route', 'reason', empty='Nothing has been rigorously ruled out yet.')}</ul></article>
  </div>
</section>"""
    body = f"""
<section class="dossier-head">
  <a class="back" href="/">← Live ledger</a>
  <div class="card-top"><span class="lane lane-{h(problem.get('lane'))}">{h(problem.get('lane'))}</span>{_badge(str(problem.get('status')))}</div>
  <h1>{h(problem['title'])}</h1>
  <p class="statement">{h(problem.get('statement'))}</p>
  <div class="source-line"><a href="{h(problem.get('source_url'))}" rel="noopener">{h(problem.get('source_name'))} ↗</a>{f'<a href="{h(problem.get("formalization_url"))}" rel="noopener">Formal statement ↗</a>' if problem.get('formalization_url') else ''}</div>
</section>
{candidate}
<section class="dossier-grid">
  <article><span class="overline">Why this problem</span><p>{h(problem.get('rationale'))}</p></article>
  <article><span class="overline">Verification contract</span><p>{h(problem.get('verifiability'))}</p></article>
  <article><span class="overline">Tracking</span><dl><dt>Difficulty</dt><dd>{h(problem.get('difficulty'))}/10</dd><dt>Attempts</dt><dd>{h(problem.get('attempt_count',0))}</dd><dt>Last attempt</dt><dd>{h(_time(problem.get('last_attempt_at')))}</dd><dt>Source status</dt><dd>{h(problem.get('problem_state'))}</dd><dt>External validation</dt><dd>{h(problem.get('external_validation_state') or 'none')}</dd></dl></article>
</section>
<section class="techniques"><span class="overline">Techniques and harnesses</span><div>{technique_tags}</div></section>
{research_map}
<section class="section-block attempts-block"><div class="section-heading"><div><span class="overline">Complete history</span><h2>Attempts on this problem</h2></div></div><div class="attempt-list">{attempt_html}</div></section>
"""
    return _layout(problem["title"], body, description=str(problem.get("statement")))


def _about_page() -> str:
    body = """
<section class="method-head about-head">
  <span class="overline">ABOUT THE PROJECT</span>
  <h1>Seeking useful<br><em>mathematics.</em></h1>
  <p>Proof Factory is an AI-assisted research project seeking to make real mathematical contributions, no matter how small or large.</p>
</section>
<section class="about-grid">
  <article><span class="overline">The aim</span><h2>Contribute something useful.</h2><p>A correction, verified computation, dataset, research tool, formalization, narrow lemma, improved bound, counterexample, or complete proof can all matter.</p></article>
  <article><span class="overline">The work</span><h2>Research in bounded steps.</h2><p>The system studies prior work, records what is known, runs reproducible experiments, and carries promising directions into the next research pass.</p></article>
  <article><span class="overline">The standard</span><h2>Be precise about the result.</h2><p>An attempt is not a discovery. Any claim must be scoped, reproducible, checked independently, and compared with existing literature before it is presented as a contribution.</p></article>
</section>
<section class="about-source"><p>All repositories and research records are public. Commits are attributed to Charlie Krug; AI and computational assistance are disclosed.</p><a href="https://github.com/ctkrug/proofs">View source and repositories →</a></section>
"""
    return _layout("About", body, description="About Proof Factory and its goal of contributing useful mathematics at any scale.")


def _attempt_page(attempt: dict[str, Any], problem: dict[str, Any], reviews: list[dict[str, Any]]) -> str:
    def items(name: str) -> str:
        rows = attempt.get(name) or []
        return "<ul>" + "".join(f"<li>{h(x)}</li>" for x in rows) + "</ul>" if rows else '<p class="muted">None recorded.</p>'
    def object_items(name: str, primary: str) -> str:
        rows = [row for row in attempt.get(name, []) if isinstance(row, dict)]
        if not rows:
            return '<p class="muted">None recorded.</p>'
        rendered = []
        for row in rows:
            details = " · ".join(str(value) for key, value in row.items() if key != primary and value)
            rendered.append(f'<li><strong>{h(row.get(primary))}</strong><br>{h(details)}</li>')
        return "<ul>" + "".join(rendered) + "</ul>"
    raw_outcome = str(attempt.get("outcome") or "unknown")
    outcome = _effective_outcome(attempt, reviews)
    warning = ""
    if outcome == "candidate":
        warning = '<div class="candidate-alert"><div><strong>Candidate for review — not a solution claim</strong><p>Independent statement checking, criticism, literature review, and verification remain required.</p></div></div>'
    elif outcome == "internal_result":
        warning = '<div class="internal-alert"><div><strong>Internal result — not a contribution candidate</strong><p>The computation remains in the transparent ledger, but it did not establish meaningful novelty or scholarly value and is not queued for Charlie review.</p></div></div>'
    if attempt.get("policy_flags"):
        warning += f'<div class="candidate-alert"><div><strong>Research-policy redirect</strong><p>{h(" · ".join(attempt.get("policy_flags") or []))}</p></div></div>'
    if problem.get("publication_attempt_id") == attempt.get("id"):
        warning += f'<div class="candidate-alert"><div><strong>{h(problem.get("publication_state"))}</strong><p>Human-approved research note; external acceptance and peer review are separate states.</p></div><a href="/publications/{h(attempt["id"])}/">Publication packet →</a></div>'
    review_html = "".join(
        f'<li><strong>{h(row.get("decision"))}</strong> · {h(row.get("reviewer"))} · {h(_time(row.get("reviewed_at")))}<br>{h(row.get("note") or "No note recorded.")}</li>'
        for row in reviews
    ) or '<p class="muted">No human review recorded.</p>'
    body = f"""
<section class="attempt-head"><a class="back" href="/problems/{h(problem['id'])}/">← {h(problem['title'])}</a><div class="eyebrow"><span>{h(_time(attempt.get('finished_at')))}</span><span>{h(attempt.get('model'))} · {h(attempt.get('effort'))}</span></div><h1>{h(attempt.get('approach'))}</h1>{_badge(outcome)}<p class="lead">{h(attempt.get('summary'))}</p></section>
{warning}
<section class="attempt-detail">
  <article><span class="overline">Strategy and discriminator</span><p><strong>{h((attempt.get('strategy') or {}).get('family') or 'Legacy attempt')}</strong></p><p>{h((attempt.get('strategy') or {}).get('mechanism') or attempt.get('approach'))}</p><p><strong>Hypothesis:</strong> {h(attempt.get('hypothesis') or 'Not recorded.')}</p><p><strong>Test:</strong> {h(attempt.get('discriminating_test') or 'Not recorded.')}</p></article>
  <article><span class="overline">Rationale</span><p>{h(attempt.get('rationale'))}</p></article>
  <article><span class="overline">Claims requiring scrutiny</span>{items('claims')}</article>
  <article><span class="overline">Evidence and scope</span>{items('evidence')}</article>
  <article><span class="overline">Computational experiments</span>{items('experiments')}</article>
  <article><span class="overline">Independent checker</span><p>{h(attempt.get('independent_checker') or 'Not provided.')}</p></article>
  <article><span class="overline">Contribution gate</span><p><strong>{h((attempt.get('contribution_gate') or {}).get('status') or ('retroactively adjudicated' if outcome == 'internal_result' else 'legacy attempt'))}</strong></p>{('<ul>' + ''.join(f'<li>{h(reason)}</li>' for reason in (attempt.get('contribution_gate') or {}).get('reasons', [])) + '</ul>') if (attempt.get('contribution_gate') or {}).get('reasons') else '<p class="muted">No structured gate reasons were recorded in this legacy attempt; see the adjudication ledger.</p>'}<dl><dt>Original model outcome</dt><dd>{h(raw_outcome)}</dd><dt>Public classification</dt><dd>{h(outcome)}</dd></dl></article>
  <article><span class="overline">Cross-domain transfers tested</span>{items('transfer_insights')}</article>
  <article><span class="overline">Established facts</span>{object_items('established_facts', 'claim')}</article>
  <article><span class="overline">Ruled out in this epoch</span>{object_items('ruled_out', 'claim_or_route')}</article>
  <article><span class="overline">Open leads</span>{object_items('open_leads', 'description')}</article>
  <article><span class="overline">Continuation checkpoint</span><p><strong>Objective:</strong> {h((attempt.get('continuation') or {}).get('objective'))}</p><p><strong>First action:</strong> {h((attempt.get('continuation') or {}).get('first_action'))}</p><p><strong>Stop condition:</strong> {h((attempt.get('continuation') or {}).get('stop_condition'))}</p></article>
  <article><span class="overline">Next moves</span>{items('next_steps')}</article>
  <article><span class="overline">Citations</span><ul>{''.join(f'<li><a href="{h(x)}" rel="noopener">{h(x)} ↗</a></li>' for x in attempt.get('citations') or [])}</ul></article>
  <article><span class="overline">Tool disclosure</span><p>{h(attempt.get('tool_disclosure'))}</p><dl><dt>Duration</dt><dd>{h(attempt.get('duration_seconds','—'))}s</dd><dt>Review state</dt><dd>{h(attempt.get('review_status'))}</dd><dt>Attempt ID</dt><dd><code>{h(attempt.get('id'))}</code></dd></dl></article>
  <article><span class="overline">Human review ledger</span>{f'<ul>{review_html}</ul>' if reviews else review_html}</article>
</section>
"""
    return _layout(f"Attempt · {problem['title']}", body)


def _publication_page(problem: dict[str, Any], attempt: dict[str, Any], reviews: list[dict[str, Any]], validations: list[dict[str, Any]]) -> str:
    review = next((row for row in reversed(reviews) if row.get("attempt_id") == attempt.get("id") and row.get("decision") == "accept"), {})
    claims = "".join(f"<li>{h(value)}</li>" for value in attempt.get("claims") or [])
    evidence = "".join(f"<li>{h(value)}</li>" for value in attempt.get("evidence") or [])
    packet = str(problem.get("publication_packet") or f"publications/{attempt['id']}")
    github = f"https://github.com/ctkrug/proofs/tree/main/{packet}"
    validation = next((row for row in reversed(validations) if row.get("attempt_id") == attempt.get("id")), {})
    external = (
        f'<a href="{h(validation.get("source_url"))}">{h(validation.get("state"))} ↗</a>'
        if validation.get("source_url") else h(validation.get("state") or "none")
    )
    body = f"""
<section class="method-head"><span class="overline">Charlie-approved public research note</span><h1>{h(problem['title'])}</h1><p>{h(attempt.get('summary'))}</p></section>
<div class="candidate-alert"><div><strong>Not peer-reviewed</strong><p>Release records provenance and invites external checking. It does not itself establish novelty or journal acceptance.</p></div><a href="{h(github)}">Packet and hashes ↗</a></div>
<section class="attempt-detail">
  <article><span class="overline">Precise contribution</span><ul>{claims}</ul></article>
  <article><span class="overline">Evidence</span><ul>{evidence}</ul></article>
  <article><span class="overline">Human approval</span><p>{h(review.get('note'))}</p><dl><dt>Reviewer</dt><dd>{h(review.get('reviewer'))}</dd><dt>Date</dt><dd>{h(_time(review.get('reviewed_at')))}</dd></dl></article>
  <article><span class="overline">Disclosure</span><p>{h(attempt.get('tool_disclosure'))}</p><p>{len(attempt.get('artifact_hashes') or {})} hashed artifacts are recorded in the packet manifest.</p><p>External validation: {external}</p></article>
</section>
"""
    return _layout(f"Publication · {problem['title']}", body)


def _method_page() -> str:
    body = """
<section class="method-head"><span class="overline">North star</span><h1>Find the low-hanging fruit.<br><em>Prove it is real.</em></h1><p>Maximize independently verifiable, net-new scholarly contribution value per unit of compute and human review. Fame is a tie-breaker, not the objective.</p></section>
<section class="method-grid">
  <article><strong>01</strong><h2>Source</h2><p>Every problem has a current status page, original-source trail, precise statement, and explicit verification contract.</p></article>
  <article><strong>02</strong><h2>Select</h2><p>Finite witnesses, exact optima, classifications, sequence contributions, formalizations, and narrow lemmas outrank famous narratives when they have a credible external acceptance path.</p></article>
  <article><strong>03</strong><h2>Portfolio</h2><p>Every problem keeps a durable registry of distinct mechanisms, live leads, theorem-strength blockers, scoped negative results, and explicit conditions for reopening a route.</p></article>
  <article><strong>04</strong><h2>Experiment</h2><p>Sol designs theories and discriminating tests. Deterministic scripts, Terra, exact solvers, and proof tools do repetition, parameter sweeps, and falsification with recorded seeds and hashes.</p></article>
  <article><strong>05</strong><h2>Resume</h2><p>The campaign can continue indefinitely through bounded safety-controlled epochs. Each epoch must leave an objective, first action, and stop condition for the next one.</p></article>
  <article><strong>06</strong><h2>Gate</h2><p>A model cannot promote its own work. Arbitrary cutoff extensions remain internal results; candidate eligibility requires meaningful delta, reproducible novelty searches, a named outside channel, sourced relevance, and validation beyond another local implementation.</p></article>
  <article><strong>07</strong><h2>Improve</h2><p>A separate strategy lab studies current primary research and may add or revise only concrete, testable methods with evaluators and named failure modes.</p></article>
  <article><strong>08</strong><h2>Release</h2><p>One human approval action creates and publishes a versioned packet with claims, artifacts, hashes, citations, limitations, and AI disclosure. External acceptance remains separate.</p></article>
</section>
<section class="principles"><h2>Research integrity</h2><p>This project follows the practical direction of the Leiden Declaration: disclose automated tools, preserve attribution, support independent verification, retain human responsibility, and do not substitute a website post for peer review.</p><div><a href="https://leidendeclaration.ai/">Leiden Declaration ↗</a><a href="https://github.com/teorth/erdosproblems/wiki/What-to-do-when-I-think-I-managed-to-get-AI-to-solve-an-Erd%C5%91s-problem%3F">Erdős AI review guidance ↗</a><a href="https://github.com/google-deepmind/formal-conjectures">Formal Conjectures ↗</a></div></section>
"""
    return _layout("Method", body)


def _strategies_page(library: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> str:
    cards = []
    for row in library:
        failures = "".join(f"<li>{h(value)}</li>" for value in row.get("failure_modes", [])) or "<li>Not recorded.</li>"
        sources = "".join(f'<a href="{h(url)}" rel="noopener">Source ↗</a>' for url in row.get("sources", []))
        cards.append(f"""
<article><span class="overline">Version {h(row.get('version') or 1)}</span><h2>{h(row.get('family'))}</h2>
<p><strong>Use when:</strong> {h(row.get('use_when'))}</p><p><strong>Mechanism:</strong> {h(row.get('mechanism'))}</p>
<p><strong>First discriminator:</strong> {h(row.get('first_discriminator'))}</p>
{f'<p><strong>Executable template:</strong> {h(row.get("experiment_template"))}</p>' if row.get('experiment_template') else ''}
<p><strong>Known failure modes:</strong></p><ul>{failures}</ul><div class="strategy-sources">{sources}</div></article>""")
    recent = "".join(
        f'<li><strong>{h(row.get("action"))}: {h(row.get("family"))}</strong> · {_time(row.get("recorded_at"))}<br>{h(row.get("change_rationale"))}</li>'
        for row in reversed(proposals[-20:])
    ) or '<li>No autonomous revisions have completed yet. The seeded library is active.</li>'
    body = f"""
<section class="method-head"><span class="overline">Self-improving method registry</span><h1>Strategies must earn<br><em>their compute.</em></h1><p>The daily strategy lab studies primary research and can add or revise a method only when it specifies an applicability condition, information-generating mechanism, cheap discriminator, executable experiment, sources, and failure modes.</p></section>
<section class="strategy-library">{''.join(cards)}</section>
<section class="principles"><h2>Revision ledger</h2><ul>{recent}</ul><p>No revision silently rewrites a past attempt. Immutable attempt records and problem-specific research maps remain available in the public data export.</p></section>
"""
    return _layout("Strategies", body)


def _brain_page(graph: dict[str, Any]) -> str:
    nodes = {row["id"]: row for row in graph.get("nodes", [])}
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in graph.get("edges", []):
        outgoing[str(edge.get("source"))].append(edge)
    problems = [row for row in graph.get("nodes", []) if row.get("type") == "problem"]
    cards = []
    for problem in problems:
        links = []
        concepts = []
        for edge in outgoing.get(problem["id"], []):
            target = nodes.get(str(edge.get("target")), {})
            if edge.get("relation") == "shares_concepts":
                links.append(
                    f'<li><a href="/problems/{h(target.get("problem_id"))}/">{h(target.get("label"))}</a><br>'
                    f'{h(", ".join(edge.get("concepts") or []))}</li>'
                )
            elif edge.get("relation") == "uses_concept":
                concepts.append(str(target.get("label") or ""))
        cards.append(f"""
<article id="problem-{h(problem.get('problem_id'))}"><span class="overline">{h(problem.get('baseline_status'))} baseline · {h(problem.get('lane'))}</span>
<h2><a href="{h(problem.get('url'))}">{h(problem.get('label'))}</a></h2><p>{h(problem.get('summary'))}</p>
<p><strong>Concepts:</strong> {h(', '.join(concepts[:12]) or 'Awaiting baseline.')}</p>
<p><strong>Linked problems:</strong></p><ul>{''.join(links[:8]) or '<li>No shared concept edge yet.</li>'}</ul></article>""")
    counts = brain.summary(graph)
    body = f"""
<section class="method-head"><span class="overline">Generated research wiki</span><h1>Problems remember.<br><em>Ideas connect.</em></h1>
<p>This graph is rebuilt from the canonical problem registry, per-problem research maps, append-only attempts, and strategy library. Links propose transfers; they never serve as mathematical evidence.</p>
<div class="source-line"><a href="/api/brain.json">Download graph JSON ↗</a><span>{h(counts.get('nodes'))} nodes · {h(counts.get('edges'))} edges · {h(counts.get('concept', 0))} concepts</span></div></section>
<section class="strategy-library">{''.join(cards)}</section>
"""
    return _layout("Research brain", body)


CSS = r"""
:root{--ink:#151716;--muted:#6b716d;--paper:#f4f1e8;--card:#fffdf7;--line:#d8d3c7;--red:#b64232;--amber:#c77b22;--green:#2b7254;--blue:#345f86;--black:#181a19}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.55}.topbar{height:72px;padding:0 clamp(20px,5vw,72px);display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);background:rgba(244,241,232,.94);backdrop-filter:blur(12px);position:sticky;top:0;z-index:20}.brand{display:flex;align-items:center;gap:11px;color:var(--ink);font-weight:760;text-decoration:none;letter-spacing:-.02em}.brand-mark{width:30px;height:30px;display:grid;place-items:center;background:var(--black);color:#fff;border-radius:50%;font-size:14px}.topbar nav{display:flex;gap:26px}.topbar nav a,footer a{color:var(--ink);text-decoration:none;font-size:14px}.topbar nav a:hover{text-decoration:underline}main{max-width:1440px;margin:auto}.hero{padding:clamp(74px,10vw,150px) clamp(20px,7vw,110px) 74px;border-bottom:1px solid var(--line);background:radial-gradient(circle at 82% 18%,rgba(198,123,34,.13),transparent 28%),linear-gradient(135deg,#f7f4eb 0,#eee9dc 100%)}.hero-kicker,.overline,.panel-label,.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.12em;font-weight:750;color:var(--muted)}.live-dot,.pulse{width:8px;height:8px;border-radius:50%;display:inline-block;background:var(--green);margin-right:8px;box-shadow:0 0 0 5px rgba(43,114,84,.12)}.hero h1,.dossier-head h1,.attempt-head h1,.method-head h1{font-family:Georgia,"Times New Roman",serif;font-size:clamp(48px,8vw,112px);line-height:.93;letter-spacing:-.055em;font-weight:400;margin:23px 0 30px;max-width:1060px}.hero h1 em,.method-head h1 em{color:var(--red);font-weight:400}.hero-copy{max-width:770px;font-size:clamp(18px,2vw,25px);color:#444943}.hero-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin-top:62px;max-width:900px}.hero-stats div{background:rgba(255,253,247,.74);padding:22px}.hero-stats strong{font-family:Georgia,serif;font-size:36px;font-weight:400;display:block}.hero-stats span{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.candidate-alert{margin:28px clamp(20px,7vw,110px);padding:20px 24px;background:#fff3dc;border:1px solid #dca85d;display:flex;justify-content:space-between;align-items:center;gap:20px}.candidate-alert p{margin:3px 0 0;color:#6b512f}.candidate-alert a{color:var(--ink);font-weight:700}.pulse{background:var(--amber);margin-right:12px}.lanes{padding:55px clamp(20px,7vw,110px);display:grid;grid-template-columns:1fr 1fr;gap:24px}.lane-panel{min-height:280px;padding:34px;border:1px solid var(--line);background:var(--card);display:flex;flex-direction:column}.hard-panel{border-top:5px solid var(--red)}.easy-panel{border-top:5px solid var(--blue)}.lane-panel h2{font-family:Georgia,serif;font-size:36px;line-height:1.1;font-weight:400;margin:26px 0 12px}.lane-panel p{color:#545a55;max-width:650px}.panel-foot{margin-top:auto;padding-top:24px;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:20px;font-size:13px}.panel-foot a{color:var(--ink);font-weight:700}.healthline{margin:0 clamp(20px,7vw,110px) 35px;padding:14px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);display:flex;gap:24px;flex-wrap:wrap;font-size:13px;color:var(--muted)}.health{color:var(--ink);font-weight:750}.health:before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--amber);margin-right:8px}.health-healthy:before{background:var(--green)}.health-degraded:before{background:var(--red)}.section-block{padding:72px clamp(20px,7vw,110px)}.section-heading{display:flex;align-items:end;justify-content:space-between;gap:30px;margin-bottom:30px}.section-heading h2{font-family:Georgia,serif;font-weight:400;font-size:clamp(35px,5vw,60px);line-height:1;margin:8px 0 0}.section-heading>a{color:var(--ink);font-weight:700}.filters{display:flex;gap:8px;flex-wrap:wrap}.filter{border:1px solid var(--line);background:transparent;padding:9px 14px;border-radius:100px;cursor:pointer}.filter.active{background:var(--black);color:#fff;border-color:var(--black)}.problem-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.problem-card{background:var(--card);border:1px solid var(--line);padding:25px;min-height:390px;display:flex;flex-direction:column}.problem-card.hidden{display:none}.card-top{display:flex;justify-content:space-between;gap:12px;align-items:center}.lane,.badge{display:inline-flex;align-items:center;border-radius:100px;padding:5px 10px;font-size:11px;text-transform:uppercase;letter-spacing:.07em;font-weight:800}.lane{background:#ece8dc}.lane-hard{color:var(--red);background:#f8e5df}.lane-easy{color:var(--blue);background:#e3edf5}.lane-calibration{color:#64548c;background:#ece7f5}.badge{border:1px solid var(--line);background:#fff}.badge-candidate{background:#fff0d2;border-color:#dea750;color:#7a4c0d}.badge-active,.badge-progress{background:#e3f1ea;border-color:#9bc4af;color:#1f6348}.badge-attempted,.badge-failed,.badge-no_progress,.badge-error{background:#f2e7e2;border-color:#d5ada1;color:#8b392d}.badge-verified,.badge-published{background:#e2eee7;border-color:#8bb89e;color:#235e45}.problem-card h3{font-family:Georgia,serif;font-size:28px;line-height:1.1;font-weight:400;margin:22px 0 14px}.problem-card h3 a,.attempt-row h3 a{color:var(--ink);text-decoration:none}.problem-card p{font-size:14px;color:#4f5551}.meter{height:4px;background:#e5e0d5;margin-top:auto}.meter span{display:block;height:100%;background:var(--red)}.card-meta,.card-actions{display:flex;justify-content:space-between;gap:12px;font-size:12px;color:var(--muted);margin-top:9px}.last-note{font-size:13px;padding:17px 0;margin-top:18px;border-top:1px solid var(--line);color:#555b57}.card-actions{margin-top:auto;padding-top:13px}.card-actions a{color:var(--ink);font-weight:700;text-decoration:none}.attempts-block{background:#ebe6da}.attempt-list{border-top:1px solid #c9c2b4}.attempt-row{display:grid;grid-template-columns:5px 1fr;border-bottom:1px solid #c9c2b4;background:rgba(255,253,247,.45)}.attempt-rail{background:var(--muted)}.outcome-candidate{background:var(--amber)}.outcome-progress,.outcome-verified,.outcome-published{background:var(--green)}.outcome-failed,.outcome-no_progress,.outcome-error{background:var(--red)}.attempt-copy{padding:24px 28px}.eyebrow{display:flex;gap:25px}.attempt-copy h3{font-family:Georgia,serif;font-size:26px;font-weight:400;margin:11px 0}.attempt-copy p{margin:6px 0;color:#515753}.attempt-copy .approach{color:var(--ink);font-weight:700}.row-end{display:flex;justify-content:space-between;align-items:center;margin-top:16px}.arrow{color:var(--ink);font-weight:700;text-decoration:none}.dossier-head,.attempt-head,.method-head{padding:70px clamp(20px,7vw,110px) 55px;border-bottom:1px solid var(--line)}.dossier-head h1,.attempt-head h1,.method-head h1{font-size:clamp(48px,7vw,90px);margin-top:30px}.back{color:var(--ink);text-decoration:none;font-size:14px}.statement,.lead{font-family:Georgia,serif;font-size:clamp(20px,2.2vw,30px);max-width:1000px}.source-line{display:flex;gap:22px;margin-top:28px;flex-wrap:wrap}.source-line a{color:var(--ink);font-weight:700}.dossier-grid,.attempt-detail,.method-grid{padding:44px clamp(20px,7vw,110px);display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.dossier-grid article,.attempt-detail article,.method-grid article{background:var(--card);border:1px solid var(--line);padding:26px}.dossier-grid p,.attempt-detail p{color:#4d534e}.dossier-grid dl,.attempt-detail dl{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:14px 0 0}.dossier-grid dt,.attempt-detail dt{color:var(--muted)}.dossier-grid dd,.attempt-detail dd{margin:0;text-align:right}.techniques{margin:0 clamp(20px,7vw,110px);padding:26px;border:1px solid var(--line);background:var(--card)}.techniques>div{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}.techniques>div span{background:#ebe7dc;padding:7px 11px;border-radius:4px;font-size:13px}.empty{padding:34px;background:var(--card)}.attempt-detail{grid-template-columns:repeat(2,1fr)}.attempt-detail ul{padding-left:20px}.attempt-detail li{margin:8px 0}.attempt-detail a{overflow-wrap:anywhere;color:var(--blue)}code{font-size:11px;overflow-wrap:anywhere}.muted{color:var(--muted)}.method-head p{font-size:22px;max-width:750px}.method-grid{grid-template-columns:repeat(3,1fr)}.method-grid article strong{font-family:Georgia,serif;font-size:32px;color:var(--red);font-weight:400}.method-grid h2{font-family:Georgia,serif;font-size:32px;font-weight:400;margin:20px 0 10px}.principles{margin:20px clamp(20px,7vw,110px) 80px;background:var(--black);color:#fff;padding:clamp(30px,5vw,65px)}.principles h2{font-family:Georgia,serif;font-size:45px;font-weight:400}.principles p{max-width:900px;color:#d5d7d5;font-size:18px}.principles div{display:flex;flex-wrap:wrap;gap:20px;margin-top:30px}.principles a{color:#fff}footer{min-height:100px;border-top:1px solid var(--line);padding:28px clamp(20px,5vw,72px);display:flex;align-items:center;justify-content:space-between;gap:20px;color:var(--muted);font-size:12px}@media(max-width:980px){.problem-grid,.method-grid{grid-template-columns:repeat(2,1fr)}.hero-stats{grid-template-columns:repeat(2,1fr)}.dossier-grid{grid-template-columns:1fr 1fr}}@media(max-width:720px){.topbar nav a:not(:first-child){display:none}.lanes,.problem-grid,.dossier-grid,.attempt-detail,.method-grid{grid-template-columns:1fr}.section-heading{align-items:start;flex-direction:column}.hero{padding-top:70px}.hero-stats{grid-template-columns:1fr 1fr}.panel-foot,.card-actions,footer{align-items:flex-start;flex-direction:column}.eyebrow{flex-direction:column;gap:3px}.candidate-alert{align-items:flex-start;flex-direction:column}}
"""


CSS += r"""
.research-map{padding:55px clamp(20px,7vw,110px)}.research-map>.section-heading>span{color:var(--muted);font-size:13px}.research-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}.research-grid article{background:var(--card);border:1px solid var(--line);padding:26px}.research-grid h3{font-family:Georgia,serif;font-size:28px;font-weight:400;line-height:1.15;margin:16px 0}.research-grid ul{padding-left:20px}.research-grid li{margin:11px 0}.research-grid em{color:var(--red)}
.strategy-library{padding:44px clamp(20px,7vw,110px);display:grid;grid-template-columns:repeat(2,1fr);gap:18px}.strategy-library article{background:var(--card);border:1px solid var(--line);padding:28px}.strategy-library h2{font-family:Georgia,serif;font-size:32px;font-weight:400;line-height:1.1}.strategy-sources{display:flex;gap:14px;flex-wrap:wrap}.strategy-sources a{color:var(--blue);font-weight:700}
.internal-alert{margin:28px clamp(20px,7vw,110px);padding:20px 24px;background:#f2e7e2;border:1px solid #d5ada1;color:#6f3126}.badge-internal_result{background:#f2e7e2;border-color:#d5ada1;color:#8b392d}.outcome-internal_result{background:var(--red)}
@media(max-width:720px){.research-grid,.strategy-library{grid-template-columns:1fr}}
"""


CSS += r"""
/* Scientific instrument interface / v2 */
:root{
  --ink:#e8f1ed;--muted:#8fa39b;--paper:#07100e;--card:#0c1714;--card-2:#101d19;
  --line:#243832;--line-bright:#3d5d53;--red:#ff746c;--amber:#f0c36a;--green:#65e1b8;
  --blue:#79bfff;--violet:#b8a4ff;--black:#030806;--mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
}
html{background:var(--black);scroll-padding-top:72px}
body{
  min-height:100vh;background:
    linear-gradient(rgba(101,225,184,.025) 1px,transparent 1px),
    linear-gradient(90deg,rgba(101,225,184,.025) 1px,transparent 1px),
    var(--paper);
  background-size:32px 32px;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  overflow-x:hidden;font-size:15px;line-height:1.55;
}
a{color:var(--green);text-underline-offset:3px}
a:focus-visible,button:focus-visible{outline:2px solid var(--green);outline-offset:3px}
.skip-link{position:fixed;left:16px;top:-60px;z-index:100;background:var(--green);color:var(--black);padding:9px 12px;font:700 12px var(--mono)}
.skip-link:focus{top:12px}
.topbar{
  height:62px;padding:0 clamp(18px,4vw,64px);border-bottom:1px solid var(--line);background:rgba(3,8,6,.92);
  backdrop-filter:blur(18px);box-shadow:0 10px 36px rgba(0,0,0,.18)
}
.brand{gap:10px;color:var(--ink);font-family:var(--mono);font-size:13px;font-weight:760;letter-spacing:.02em;text-transform:uppercase}
.brand-mark{width:30px;height:30px;border:1px solid var(--green);border-radius:2px;background:rgba(101,225,184,.08);color:var(--green);font-size:10px;letter-spacing:.05em}
.brand small{padding-left:10px;border-left:1px solid var(--line);color:var(--muted);font-size:9px;font-weight:500;letter-spacing:.12em}
.topbar nav{gap:clamp(12px,2vw,28px)}
.topbar nav a,footer a{color:var(--muted);font:600 10px var(--mono);letter-spacing:.1em;text-decoration:none;text-transform:uppercase}
.topbar nav a:hover,footer a:hover{color:var(--green);text-decoration:none}
main{max-width:1600px;margin:0 auto;border-left:1px solid rgba(36,56,50,.55);border-right:1px solid rgba(36,56,50,.55);background:rgba(7,16,14,.84)}
.hero{
  position:relative;overflow:hidden;padding:clamp(64px,8vw,116px) clamp(22px,6vw,92px) clamp(42px,5vw,72px);
  border-bottom:1px solid var(--line);background:
    radial-gradient(circle at 82% 25%,rgba(101,225,184,.09),transparent 22%),
    linear-gradient(140deg,rgba(12,28,23,.98),rgba(7,16,14,.96) 62%);
}
.hero:before{
  content:"R(5,5)   SAT / LEAN   Σ   GRAPH THEORY";position:absolute;right:-34px;top:76px;max-width:520px;
  color:rgba(101,225,184,.07);font:700 clamp(42px,6vw,90px)/.94 var(--mono);letter-spacing:-.08em;text-align:right;white-space:pre-wrap;transform:rotate(-2deg)
}
.hero>*{position:relative;z-index:1}
.hero-kicker,.overline,.panel-label,.eyebrow{color:var(--green);font:650 10px var(--mono);letter-spacing:.14em;text-transform:uppercase}
.live-dot,.pulse{width:7px;height:7px;background:var(--green);box-shadow:0 0 0 4px rgba(101,225,184,.1),0 0 18px rgba(101,225,184,.55)}
.hero h1,.dossier-head h1,.attempt-head h1,.method-head h1{
  max-width:980px;margin:20px 0 22px;color:var(--ink);font-family:var(--serif);font-size:clamp(48px,7vw,100px);font-weight:400;line-height:.92;letter-spacing:-.055em
}
.hero h1 em,.method-head h1 em{color:var(--green);font-weight:400}
.hero-copy{max-width:720px;color:#b7c8c1;font-size:clamp(16px,1.7vw,21px);line-height:1.55}
.hero-stats{max-width:920px;margin-top:44px;grid-template-columns:repeat(4,1fr);gap:0;background:transparent;border:1px solid var(--line)}
.hero-stats div{position:relative;padding:18px 20px;background:rgba(3,8,6,.42);border-right:1px solid var(--line)}
.hero-stats div:last-child{border-right:0}
.hero-stats strong{color:var(--ink);font:500 30px/1 var(--mono);font-variant-numeric:tabular-nums}
.hero-stats span{display:block;margin-top:9px;color:var(--muted);font:600 9px var(--mono);letter-spacing:.12em;text-transform:uppercase}
.candidate-alert,.internal-alert{margin:0;padding:17px clamp(22px,6vw,92px);border:0;border-bottom:1px solid var(--amber);background:rgba(240,195,106,.08);color:var(--ink)}
.candidate-alert p{color:#c8b98f}.candidate-alert a{color:var(--amber);font:700 10px var(--mono);letter-spacing:.1em;text-transform:uppercase}
.internal-alert{border-color:var(--red);background:rgba(255,116,108,.08);color:var(--ink)}
.lanes{padding:32px clamp(22px,6vw,92px);gap:14px;border-bottom:1px solid var(--line)}
.lane-panel{min-height:236px;padding:25px;border:1px solid var(--line);border-top:1px solid var(--line);background:linear-gradient(150deg,rgba(16,29,25,.98),rgba(8,18,15,.98));box-shadow:0 14px 40px rgba(0,0,0,.14)}
.lane-panel:before{content:"";display:block;width:42px;height:2px;margin-bottom:18px;background:var(--red)}
.easy-panel:before{background:var(--blue)}
.lane-panel h2{margin:14px 0 10px;color:var(--ink);font-family:var(--serif);font-size:clamp(27px,3vw,38px);font-weight:400;line-height:1.08}
.lane-panel p{margin:0;color:#9fb0aa;font-size:13px;line-height:1.55}
.panel-foot{padding-top:17px;border-color:var(--line);color:var(--muted);font:550 10px/1.5 var(--mono)}
.panel-foot a{color:var(--green);text-decoration:none}
.healthline{margin:0;padding:12px clamp(22px,6vw,92px);border:0;border-bottom:1px solid var(--line);background:rgba(3,8,6,.42);color:var(--muted);font:550 9px var(--mono);letter-spacing:.06em;text-transform:uppercase}
.health{color:var(--ink)}.health:before{background:var(--amber)}.health-healthy:before{background:var(--green)}.health-degraded:before{background:var(--red)}
.section-block{padding:clamp(46px,6vw,78px) clamp(22px,6vw,92px)}
.section-heading{margin-bottom:24px;padding-bottom:18px;border-bottom:1px solid var(--line)}
.section-heading h2{margin:6px 0 0;color:var(--ink);font-family:var(--serif);font-size:clamp(34px,4.5vw,58px);font-weight:400;line-height:1;letter-spacing:-.035em}
.section-heading>a{color:var(--green);font:650 10px var(--mono);letter-spacing:.08em;text-decoration:none;text-transform:uppercase}
.section-note{color:var(--muted);font:550 9px var(--mono);letter-spacing:.08em;text-transform:uppercase}
.planned-block{border-top:1px solid var(--line);background:rgba(8,19,16,.62)}
.filters{gap:6px}
.filter{padding:7px 11px;border:1px solid var(--line);border-radius:2px;background:transparent;color:var(--muted);font:650 9px var(--mono);letter-spacing:.08em;text-transform:uppercase}
.filter:hover{border-color:var(--line-bright);color:var(--ink)}
.filter.active{border-color:var(--green);background:rgba(101,225,184,.1);color:var(--green)}
.problem-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.problem-card{min-width:0;min-height:342px;padding:20px;border:1px solid var(--line);background:linear-gradient(155deg,rgba(16,29,25,.96),rgba(9,19,16,.98));box-shadow:none}
.problem-card:hover{border-color:var(--line-bright);transform:translateY(-1px);transition:border-color .15s ease,transform .15s ease}
.card-top{align-items:flex-start}.lane,.badge{border-radius:2px;padding:5px 7px;font:700 8px var(--mono);letter-spacing:.09em}
.lane{border:1px solid var(--line);background:transparent;color:var(--muted)}
.lane-hard{border-color:rgba(255,116,108,.45);background:rgba(255,116,108,.07);color:var(--red)}
.lane-easy{border-color:rgba(121,191,255,.4);background:rgba(121,191,255,.07);color:var(--blue)}
.lane-calibration{border-color:rgba(184,164,255,.4);background:rgba(184,164,255,.07);color:var(--violet)}
.badge{border-color:var(--line);background:rgba(255,255,255,.025);color:var(--muted)}
.badge-candidate{border-color:rgba(240,195,106,.52);background:rgba(240,195,106,.08);color:var(--amber)}
.badge-active,.badge-progress,.badge-verified,.badge-published{border-color:rgba(101,225,184,.42);background:rgba(101,225,184,.08);color:var(--green)}
.badge-attempted,.badge-failed,.badge-no_progress,.badge-error,.badge-internal_result{border-color:rgba(255,116,108,.4);background:rgba(255,116,108,.07);color:var(--red)}
.problem-card h3{margin:18px 0 10px;font-family:var(--serif);font-size:25px;font-weight:400;line-height:1.08;overflow-wrap:anywhere}
.problem-card h3 a,.attempt-row h3 a{display:block;max-width:100%;color:var(--ink);text-decoration:none;overflow-wrap:anywhere}
.problem-card mjx-container{display:inline-block!important;width:100%!important;max-width:100%;overflow-x:auto;overflow-y:hidden}
.problem-card mjx-container>mjx-math{max-width:100%}
.problem-card p{margin:0;color:#9fb0aa;font-size:12.5px;line-height:1.55}
.meter{height:2px;margin-top:auto;background:var(--line)}.meter span{background:var(--green)}
.card-meta,.card-actions{color:var(--muted);font:500 9px/1.4 var(--mono)}
.last-note{max-height:74px;overflow:hidden;margin-top:14px;padding:13px 0 0;border-color:var(--line);color:#aebdb7;font-size:11.5px;line-height:1.5}
.card-actions{padding-top:13px;border-top:1px solid var(--line)}.card-actions a{color:var(--green);text-decoration:none}
.attempts-block{background:rgba(3,8,6,.48)}
.attempt-list{border-color:var(--line)}
.attempt-row{max-width:100%;grid-template-columns:3px minmax(0,1fr);border-color:var(--line);background:rgba(12,23,20,.72)}
.attempt-row:hover{background:rgba(16,31,26,.88)}
.attempt-rail{background:var(--muted)}.outcome-candidate{background:var(--amber)}.outcome-progress,.outcome-verified,.outcome-published{background:var(--green)}.outcome-failed,.outcome-no_progress,.outcome-error,.outcome-internal_result{background:var(--red)}
.attempt-copy{min-width:0;padding:19px 22px;overflow-wrap:anywhere}.eyebrow{gap:18px;color:var(--muted)}
.attempt-copy h3{margin:8px 0 6px;font-family:var(--serif);font-size:23px;font-weight:400}
.attempt-copy p{margin:4px 0;color:#9fb0aa;font-size:12.5px}.attempt-copy .approach{color:var(--ink);font-weight:620}
.row-end{margin-top:12px}.arrow{color:var(--green);font:650 9px var(--mono);letter-spacing:.08em;text-decoration:none;text-transform:uppercase}
.dossier-head,.attempt-head,.method-head{padding:clamp(52px,7vw,92px) clamp(22px,6vw,92px) 44px;border-color:var(--line);background:linear-gradient(145deg,rgba(13,28,23,.98),rgba(7,16,14,.96))}
.dossier-head h1,.attempt-head h1,.method-head h1{margin:22px 0 18px;font-size:clamp(45px,6vw,78px)}
.back{color:var(--muted);font:600 9px var(--mono);letter-spacing:.08em;text-transform:uppercase}
.statement,.lead{max-width:960px;color:#c3d0cb;font-family:var(--serif);font-size:clamp(18px,2vw,25px);line-height:1.45}
.source-line{gap:18px;margin-top:22px}.source-line a{color:var(--green);font:650 9px var(--mono);letter-spacing:.07em;text-decoration:none;text-transform:uppercase}
.dossier-grid,.attempt-detail,.method-grid{padding:30px clamp(22px,6vw,92px);gap:10px}
.dossier-grid article,.attempt-detail article,.method-grid article,.research-grid article,.strategy-library article{border:1px solid var(--line);background:rgba(12,23,20,.88);padding:21px}
.dossier-grid p,.attempt-detail p{color:#aab9b3;font-size:12.5px}
.dossier-grid dl,.attempt-detail dl{font:500 10px/1.5 var(--mono)}
.dossier-grid dt,.attempt-detail dt{color:var(--muted)}.dossier-grid dd,.attempt-detail dd{color:var(--ink)}
.techniques{margin:0 clamp(22px,6vw,92px);padding:19px;border-color:var(--line);background:rgba(12,23,20,.78)}
.techniques>div span{border:1px solid var(--line);border-radius:2px;background:transparent;color:var(--muted);font:550 9px var(--mono)}
.research-map{padding:38px clamp(22px,6vw,92px)}
.research-grid{gap:10px}.research-grid h3{color:var(--ink);font-family:var(--serif);font-size:25px;font-weight:400}.research-grid li,.attempt-detail li{margin:8px 0;color:#aab9b3;font-size:12px}
.strategy-library{padding:30px clamp(22px,6vw,92px);gap:10px}.strategy-library h2{color:var(--ink);font-family:var(--serif);font-size:28px}.strategy-library p,.strategy-library li{color:#aab9b3;font-size:12.5px}.strategy-sources a{color:var(--green)}
.method-grid article strong{color:var(--green);font:500 22px var(--mono)}.method-grid h2{color:var(--ink);font-family:var(--serif);font-size:27px;font-weight:400}.method-grid p{color:#aab9b3;font-size:12.5px}
.principles{margin:20px clamp(22px,6vw,92px) 58px;padding:clamp(26px,4vw,46px);border:1px solid var(--line);background:linear-gradient(145deg,#0b1b16,#06100d);color:var(--ink)}
.principles h2{margin-top:0;color:var(--ink);font-family:var(--serif);font-size:38px;font-weight:400}.principles p,.principles li{color:#aab9b3;font-size:13px}.principles a{color:var(--green)}
.about-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding:30px clamp(22px,6vw,92px)}
.about-grid article{min-height:280px;padding:25px;border:1px solid var(--line);background:rgba(12,23,20,.88)}
.about-grid h2{margin:24px 0 12px;color:var(--ink);font-family:var(--serif);font-size:30px;font-weight:400;line-height:1.08}
.about-grid p,.about-source p{color:#aab9b3;font-size:13px;line-height:1.65}
.about-source{margin:0 clamp(22px,6vw,92px) 58px;padding:25px;border:1px solid var(--line);background:linear-gradient(145deg,#0b1b16,#06100d)}
.about-source p{max-width:820px}.about-source a{font:650 10px var(--mono);letter-spacing:.08em;text-decoration:none;text-transform:uppercase}
.empty{border:1px solid var(--line);background:var(--card);color:var(--muted)}
code{color:var(--green);font-family:var(--mono);font-size:10px}.muted{color:var(--muted)}
footer{min-height:78px;padding:22px clamp(22px,4vw,64px);border-color:var(--line);background:var(--black);color:var(--muted);font:500 9px var(--mono);letter-spacing:.06em;text-transform:uppercase}
@media(max-width:1080px){.problem-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.brand small{display:none}}
@media(max-width:760px){
  .topbar{height:56px}.topbar nav{gap:9px}.topbar nav a{display:inline!important;font-size:8px}.brand span:not(.brand-mark),.brand small{display:none}
  .hero{padding-top:58px}.hero:before{display:none}.hero-stats{grid-template-columns:repeat(2,1fr)}.hero-stats div:nth-child(2){border-right:0}.hero-stats div:nth-child(-n+2){border-bottom:1px solid var(--line)}
  .lanes,.problem-grid,.dossier-grid,.attempt-detail,.method-grid,.research-grid,.strategy-library,.about-grid{grid-template-columns:minmax(0,1fr)}
  .section-heading{align-items:flex-start}.section-heading h2{font-size:38px}.filters{margin-top:4px}
  .problem-card{min-height:315px}.card-meta,.card-actions{flex-wrap:wrap}footer{align-items:flex-start}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.problem-card:hover{transform:none}}
"""


def _build_unlocked() -> Path:
    problems = store.load_problems()
    attempts = store.load_attempts()
    runtime = store.runtime()
    reviews = store.read_json(store.DATA / "reviews.json", [])
    if not isinstance(reviews, list):
        reviews = []
    validations = store.read_json(store.DATA / "validations.json", [])
    if not isinstance(validations, list):
        validations = []
    research_states = research_state.load_all(problems)
    brain.refresh()
    if store.SITE.exists():
        # Keep the mount-point directory itself intact for systemd ReadWritePaths.
        for child in store.SITE.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
    (store.SITE / "assets").mkdir(parents=True, exist_ok=True)
    _write(store.SITE / "assets" / "site-v3.css", CSS)
    _write(store.SITE / "index.html", _index(problems, attempts, runtime, reviews))
    by_problem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        by_problem[str(attempt.get("problem_id"))].append(attempt)
    problem_by_id = {row["id"]: row for row in problems}
    for problem in problems:
        _write(
            store.SITE / "problems" / problem["id"] / "index.html",
            _problem_page(problem, by_problem[problem["id"]], research_states[problem["id"]], reviews),
        )
    for attempt in attempts:
        problem = problem_by_id.get(str(attempt.get("problem_id")))
        if problem:
            attempt_reviews = [row for row in reviews if row.get("attempt_id") == attempt.get("id")]
            _write(store.SITE / "attempts" / attempt["id"] / "index.html", _attempt_page(attempt, problem, attempt_reviews))
            if problem.get("publication_attempt_id") == attempt.get("id"):
                _write(store.SITE / "publications" / attempt["id"] / "index.html", _publication_page(problem, attempt, reviews, validations))
    _write(store.SITE / "about" / "index.html", _about_page())
    _write(store.SITE / "robots.txt", "User-agent: *\nAllow: /\nSitemap: https://proofs.charliekrug.com/sitemap.xml\n")
    _write(
        store.SITE / "_redirects",
        "/brain/* / 301\n/method/* /about/ 301\n/strategies/* /about/ 301\n/api/* / 301\n",
    )
    urls = ["/", "/about/"] + [f"/problems/{p['id']}/" for p in problems] + [f"/attempts/{a['id']}/" for a in attempts]
    urls += [f"/publications/{p['publication_attempt_id']}/" for p in problems if p.get("publication_attempt_id")]
    _write(store.SITE / "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>https://proofs.charliekrug.com{h(url)}</loc></url>\n" for url in urls) + "</urlset>\n")
    _write(store.SITE / "_headers", "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  Permissions-Policy: camera=(), microphone=(), geolocation=()\n  X-Frame-Options: DENY\n\n/assets/*\n  Cache-Control: public, max-age=3600\n")
    _write(store.SITE / "404.html", _layout("Not found", '<section class="method-head"><h1>That record does not exist.</h1><p><a href="/">Return to the research work →</a></p></section>'))
    return store.SITE


def build() -> Path:
    """Render the shared site under a cross-process lock.

    Hard, easy, watchdog, and publishing services can run concurrently.  They
    all rebuild the same directory, so cleanup and writes must be serialized.
    """
    with store.lock("render") as acquired:
        if not acquired:
            raise RuntimeError("render lock unavailable")
        return _build_unlocked()
