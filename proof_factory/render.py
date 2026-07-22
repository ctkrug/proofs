from __future__ import annotations

import html
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import brain, live, research_state, store
from .html_templates import BRAIN_CARD, BRAIN_LINK, BRAIN_PAGE, LAYOUT, html_fragment, render as render_template


STATUS_ORDER = ["candidate", "active", "attempted", "internal_result", "failed", "queued", "parked", "verified", "published"]
STATUS_LABELS = {
    "queued": "Queued",
    "active": "Active / ongoing",
    "attempted": "Tried — still open",
    "parked": "On hold after campaign review",
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


def _program_label(lane: str | None) -> str:
    return "Hard research queue" if lane == "hard" else "Open-problem program"


def _problem_tag(problem: dict[str, Any]) -> str:
    return str(problem.get("contribution_type") or _program_label(str(problem.get("lane") or "easy")))


def _layout(title: str, body: str, *, description: str = "Ongoing and planned AI-assisted mathematics research.") -> str:
    return render_template(LAYOUT, title=title, description=description, body=html_fragment(body))


def _effective_outcome(attempt: dict[str, Any], reviews: list[dict[str, Any]]) -> str:
    latest = reviews[-1] if reviews else {}
    if attempt.get("outcome") == "candidate" and latest.get("display_status") == "internal_result":
        return "internal_result"
    return str(attempt.get("outcome") or "unknown")


def _attempt_row(attempt: dict[str, Any], problem: dict[str, Any], reviews: list[dict[str, Any]] | None = None) -> str:
    outcome = _effective_outcome(attempt, reviews or [])
    label = STATUS_LABELS.get(outcome, outcome.replace("_", " ").title())
    duration = attempt.get("duration_seconds")
    duration_text = f"{round(float(duration) / 60)} min" if isinstance(duration, (int, float)) else "Duration unavailable"
    next_steps = attempt.get("next_steps") or []
    next_action = next_steps[0] if next_steps else None
    if isinstance(next_action, dict):
        next_action = next_action.get("action") or next_action.get("description") or str(next_action)
    return f"""
<article class="attempt-row" data-outcome="{h(outcome)}" data-run-id="{h(attempt.get('id'))}">
  <div class="attempt-rail outcome-{h(outcome)}"></div>
  <div class="attempt-copy">
    <div class="eyebrow"><span>{h(_time(attempt.get('finished_at')))}</span><span>{h(_program_label(str(attempt.get('lane'))))} · {h(duration_text)}</span></div>
    <h3><a href="/attempts/{h(attempt['id'])}/">{h(problem['title'])}</a></h3>
    <p class="approach">{h(attempt.get('approach') or 'Research pass')}</p>
    <div class="accomplishment"><span>What this run accomplished</span><p>{h(attempt.get('summary') or 'No accomplishment summary was recorded.')}</p></div>
    {f'<p class="next-action"><strong>Next:</strong> {h(next_action)}</p>' if next_action else ''}
    <div class="row-end"><span class="badge badge-{h(outcome)}">{h(label)}</span><a class="arrow" href="/attempts/{h(attempt['id'])}/">Open full record →</a></div>
  </div>
</article>"""


def _lane_card(lane: str, payload: dict[str, Any]) -> str:
    running = payload.get("status") == "running"
    title = payload.get("running_problem_title") or ("Exact-problem queue" if lane == "hard" else "Discovery queue")
    status = "Running now" if running else "Between runs"
    detail = "Research pass in progress" if running else "Next dispatch scheduled"
    return f"""
<article class="operation-card operation-{h(lane)}" data-live-lane="{h(lane)}">
  <div class="operation-head"><span class="lane lane-{h(lane)}">{h(_program_label(lane))}</span><span class="operation-status{' is-live' if running else ''}" data-role="status">{h(status)}</span></div>
  <h3 data-role="title">{h(title)}</h3>
  <p class="operation-detail" data-role="detail">{h(detail)}</p>
  <dl>
    <div><dt>Current pass</dt><dd data-role="current-clock" data-started-at="{h(payload.get('started_at'))}">{'Calculating…' if running else 'Idle'}</dd></div>
    <div><dt>Next run</dt><dd data-role="next-clock" data-next-at="{h(payload.get('next_at'))}">Calculating…</dd></div>
    <div><dt>Last result</dt><dd data-role="last-result">{h(STATUS_LABELS.get(str(payload.get('last_outcome')), str(payload.get('last_outcome') or 'Not yet').replace('_', ' ').title()))}</dd></div>
  </dl>
</article>"""


def _problem_card(problem: dict[str, Any], attempts: list[dict[str, Any]], state: dict[str, Any]) -> str:
    last = attempts[-1] if attempts else None
    status = str(problem.get("status") or "queued")
    lane = str(problem.get("lane") or "easy")
    campaign_progress = ""
    if lane == "easy" and problem.get("campaign_state") == "active":
        minimum = max(store.DISCOVERY_CAMPAIGN_MIN_RUNS, int(problem.get("campaign_min_runs") or 0))
        campaign_progress = f" · campaign {store.discovery_campaign_run_count(problem)}/{minimum}+"
    return f"""
<article class="problem-card" data-status="{h(status)}" data-lane="{h(lane)}">
  <div class="card-top"><span class="lane lane-{h(lane)}">{h(_problem_tag(problem))}</span>{_badge(status)}</div>
  <h3><a href="/problems/{h(problem['id'])}/">{h(problem['title'])}</a></h3>
  <p>{h(problem.get('statement'))}</p>
  <div class="meter"><span style="width:{min(100, int(problem.get('difficulty') or 0) * 10)}%"></span></div>
  <div class="card-meta"><span>Difficulty {h(problem.get('difficulty'))}/10</span><span>{h(problem.get('attempt_count', 0))} attempts{h(campaign_progress)} · {h(research_state.summary_counts(state)['open_leads'])} open leads</span></div>
  <div class="last-note"><strong>Latest:</strong> {h((last or {}).get('summary') or 'No research pass yet.')}</div>
  <div class="card-actions"><a href="{h(problem.get('source_url'))}" rel="noopener">Official source ↗</a><a href="/problems/{h(problem['id'])}/">Full record →</a></div>
</article>"""


def _candidate_review_href(candidates: list[dict[str, Any]]) -> str:
    """Link one candidate to its dossier; send a queue to the live work section."""
    if len(candidates) == 1:
        return f"/problems/{h(candidates[0].get('id'))}/"
    return "#ongoing"


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
    operational_blockers = runtime.get("operational_blockers") or []
    health = runtime.get("health", "starting")
    health_issues = runtime.get("health_issues") or []
    usage_policy = runtime.get("usage_policy") or {}
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
        candidate_banner = f"""<section class="candidate-alert"><div><span class="pulse"></span><strong>{len(candidates)} candidate finding{'s' if len(candidates) != 1 else ''} need review.</strong><p>Candidate means unverified. It is not a solved claim.</p></div><a href="{_candidate_review_href(candidates)}">Review records →</a></section>"""
    blocker_banner = ""
    if operational_blockers:
        blocker = operational_blockers[0] if isinstance(operational_blockers[0], dict) else {"detail": str(operational_blockers[0])}
        blocker_banner = f"""<section class="candidate-alert operational-alert" data-operational-blockers><div><span class="pulse"></span><strong>Research infrastructure needs attention.</strong><p>{h(blocker.get('detail') or blocker.get('title') or 'A required research dependency is unavailable.')} {h(blocker.get('next_action') or '')}</p></div><a href="#runs">Open run history →</a></section>"""
    issues = "" if not health_issues else " · ".join(h(x) for x in health_issues)
    usage_note = h(usage_policy.get("reason") or "Usage policy awaiting its first check.")
    live_work = "No pass currently running" if not running_lanes else "Active now: " + " and ".join(
        _program_label(lane) for lane in running_lanes
    )
    live_snapshot = live.snapshot(problems, attempts, runtime, reviews)
    experiment_counts = live_snapshot["experiments"]["counts"]
    experiment_lifecycle = " · ".join(
        f"{h(name.replace('_', ' '))}: {int(experiment_counts.get(name, 0))}"
        for name in ("running", "checkpointed", "completed_awaiting_review", "validated", "stopped_with_reason")
    )
    body = f"""
<section class="hero">
  <div class="hero-kicker">AI-assisted mathematics research</div>
  <h1>Mathematical research<br>in progress.</h1>
  <p class="hero-copy">Proof Factory seeks to contribute useful mathematics, no matter how small or large. This site shows the work underway, what is planned next, and the attempts made so far.</p>
</section>
{candidate_banner}
{blocker_banner}
<section id="operations" class="operations section-block">
  <div class="section-heading"><div><span class="overline">RESEARCH OPERATIONS</span><h2>Current schedule</h2></div><span class="section-note" data-live-updated>Updated {_time(runtime.get('updated_at') or store.now_iso())}</span></div>
  <div class="healthline"><span class="health health-{h(health)}" data-live-health>System {h(health)}</span><span>{h(live_work)}</span><span data-usage-policy>{usage_note}</span><span>{issues}</span></div>
  <div class="operation-grid">{_lane_card('hard', live_snapshot['lanes']['hard'])}{_lane_card('easy', live_snapshot['lanes']['easy'])}</div>
  <div class="healthline" data-experiment-lifecycle><strong>Experiment lifecycle</strong> · {experiment_lifecycle}</div>
</section>
<section id="ongoing" class="section-block">
  <div class="section-heading"><div><span class="overline">WORK UNDERWAY</span><h2>Ongoing work</h2></div><span class="section-note">R(5,5) twice hourly · focused open-problem campaign 12× daily</span></div>
  <div class="problem-grid">{''.join(_problem_card(row, by_problem[row['id']], states[row['id']]) for row in ongoing) or '<p class="empty">No research pass is currently open.</p>'}</div>
</section>
<section id="planned" class="section-block planned-block">
  <div class="section-heading"><div><span class="overline">NEXT IN QUEUE</span><h2>Planned work</h2></div></div>
  <div class="problem-grid">{''.join(_problem_card(row, by_problem[row['id']], states[row['id']]) for row in planned) or '<p class="empty">No additional work is queued.</p>'}</div>
</section>
<section id="runs" class="section-block attempts-block">
  <div class="section-heading"><div><span class="overline">RUN HISTORY</span><h2>Completed research passes</h2></div><span class="section-note">Newest first · complete records retained</span></div>
  <div class="attempt-list" data-live-runs>{''.join(_attempt_row(row, next(p for p in problems if p['id'] == row['problem_id']), reviews_by_attempt[str(row.get('id'))]) for row in reversed(attempts[-25:])) or '<p>No attempts yet.</p>'}</div>
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
        candidate_attempt_id = h(problem.get("candidate_attempt_id") or "")
        candidate = f'''<section class="candidate-review" data-candidate-review data-attempt-id="{candidate_attempt_id}">
  <div class="candidate-review-copy"><span class="overline">Human review gate</span><h2>Unverified candidate finding</h2><p>Read the attempt and evidence below. Approval records your human review; it does not claim external acceptance or submit the result.</p><code>{candidate_attempt_id}</code></div>
  <form class="candidate-review-form" data-candidate-review-form>
    <label>Review note<textarea name="note" required>I reviewed the evidence packet and approve this candidate for the next external contribution step.</textarea></label>
    <label>Approval password<input name="password" type="password" required autocomplete="current-password"></label>
    <button type="submit">Approve candidate</button>
    <p class="candidate-review-status" data-candidate-review-status role="status" aria-live="polite"></p>
  </form>
</section>'''
    counts = research_state.summary_counts(state)
    strategies = list(reversed(state.get("strategies", [])[-12:]))
    ruled = list(reversed(state.get("ruled_out", [])[-10:]))
    leads = [row for row in state.get("open_leads", [])[-10:] if row.get("status", "open") == "open"]
    checkpoint = state.get("next_session", {})
    external_state = h(problem.get("external_validation_state") or "none")
    external_url = problem.get("external_validation_url")
    external_tracking = (
        f'<a href="{h(external_url)}" rel="noopener">{external_state} ↗</a>'
        if external_url else external_state
    )
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
  <div class="card-top"><span class="lane lane-{h(problem.get('lane'))}">{h(_problem_tag(problem))}</span>{_badge(str(problem.get('status')))}</div>
  <h1>{h(problem['title'])}</h1>
  <p class="statement">{h(problem.get('statement'))}</p>
  <div class="source-line"><a href="{h(problem.get('source_url'))}" rel="noopener">{h(problem.get('source_name'))} ↗</a>{f'<a href="{h(problem.get("formalization_url"))}" rel="noopener">Formal statement ↗</a>' if problem.get('formalization_url') else ''}</div>
</section>
{candidate}
<section class="dossier-grid">
  <article><span class="overline">Why this problem</span><p>{h(problem.get('rationale'))}</p></article>
  <article><span class="overline">Verification contract</span><p>{h(problem.get('verifiability'))}</p></article>
  <article><span class="overline">Tracking</span><dl><dt>Difficulty</dt><dd>{h(problem.get('difficulty'))}/10</dd><dt>Attempts</dt><dd>{h(problem.get('attempt_count',0))}</dd><dt>Last attempt</dt><dd>{h(_time(problem.get('last_attempt_at')))}</dd><dt>Source status</dt><dd>{h(problem.get('problem_state'))}</dd><dt>External validation</dt><dd>{external_tracking}</dd></dl></article>
</section>
<section class="techniques"><span class="overline">Techniques and harnesses</span><div>{technique_tags}</div></section>
{research_map}
<section class="section-block attempts-block"><div class="section-heading"><div><span class="overline">Complete history</span><h2>Attempts on this problem</h2></div></div><div class="attempt-list">{attempt_html}</div></section>
"""
    return _layout(problem["title"], body, description=str(problem.get("statement")))


def _about_page() -> str:
    body = """
<section class="method-head about-head">
  <span class="overline">SYSTEM MAP / ABOUT THE PROJECT</span>
  <h1>A proof engine<br><em>that remembers.</em></h1>
  <p>Proof Factory is an AI-assisted research system for making useful mathematical contributions, no matter how small or large, while pursuing hard finite problems without losing the evidence, failures, or context between passes.</p>
  <nav class="about-jump" aria-label="About page sections"><a href="#engine">Engine</a><a href="#passes">Research passes</a><a href="#memory">Memory</a><a href="#roles">Roles</a><a href="#gates">Publication gates</a></nav>
</section>

<section id="engine" class="about-section engine-section">
  <div class="about-section-head"><div><span class="overline">01 / END-TO-END ARCHITECTURE</span><h2>One evidence loop</h2></div><p>Every pass begins from current source material and durable state. It ends by changing that state only when the evidence survives its gates.</p></div>
  <div class="engine-inputs" aria-label="Engine inputs"><span>Primary sources</span><span>Problem registry</span><span>Prior-art register</span><span>Research memory</span><span>Lab events</span></div>
  <ol class="engine-flow" aria-label="Proof Factory process">
    <li><span class="step-no">01</span><span class="overline">Scout + intake</span><h3>Find a real opening</h3><p>Audit a current, recognized source; check comments, claims, active work, acceptance path, and whether a compact certificate is possible.</p><strong>Output · exact target</strong></li>
    <li><span class="step-no">02</span><span class="overline">Baseline</span><h3>Map what is known</h3><p>Read primary literature, capture established facts, datasets, live methods, exclusions, novelty risks, and verification tools.</p><strong>Output · sourced research map</strong></li>
    <li><span class="step-no">03</span><span class="overline">Strategy</span><h3>Choose a discriminator</h3><p>Compare witness, impossibility certificate, structural reduction, alternative formalism, and adjacent-field transfer by decision value per cost.</p><strong>Output · prediction + stop rule</strong></li>
    <li><span class="step-no">04</span><span class="overline">Research + lab</span><h3>Run the bounded test</h3><p>Reason in a research pass; move long deterministic work to a resource-capped lab with immutable inputs, checkpoints, manifests, and logs.</p><strong>Output · artifact + receipt</strong></li>
    <li><span class="step-no">05</span><span class="overline">Adversarial verification</span><h3>Try to break it</h3><p>Replay cleanly, check scope and quantifiers, use an independent implementation or formal kernel, and repeat the novelty search.</p><strong>Output · verified scope</strong></li>
    <li><span class="step-no">06</span><span class="overline">Decision</span><h3>Learn, redirect, or release</h3><p>Record the exact delta. Continue, hold, redirect, or close the route. Candidate work still waits for contribution, skeptic, and human gates.</p><strong>Output · next state</strong></li>
  </ol>
  <div class="engine-return"><span>↳</span><p><strong>Feedback, not amnesia.</strong> Facts, failures, route scores, artifacts, and the next first action return to the next epoch. A failed search narrows only its recorded scope.</p></div>
</section>

<section id="passes" class="about-section pass-section">
  <div class="about-section-head"><div><span class="overline">02 / RESEARCH ORCHESTRATION</span><h2>How a pass thinks</h2></div><p>Model agreement is never treated as validation. Reconnaissance diversifies the search; the principal chooses and audits one concrete test.</p></div>
  <div class="pass-map" aria-label="Research and laboratory pass architecture">
    <div class="pass-column pass-start"><span class="overline">Admitting evidence</span><h3>Canonical route brief</h3><p>Statement, source status, research map, tactical incumbent, challenger, roadmap, prior art, and any completed lab event.</p></div>
    <div class="pass-column pass-delegates"><span class="overline">Terra reconnaissance</span><div class="mini-role"><strong>Source discriminator</strong><span>Exact status, smallest executable test, outside acceptance path</span></div><div class="mini-role"><strong>Prior-art challenger</strong><span>Overlap, missing premise, genuinely different route</span></div><div class="mini-role"><strong>Experiment verifier</strong><span>Controls, failure modes, stop conditions, independent check</span></div><small>Roles are admitted only when their evidence can change the route.</small></div>
    <div class="pass-column pass-principal"><span class="overline">Sol principal</span><h3>Select one bounded discriminator</h3><ul><li>Audit delegate claims</li><li>Predeclare success and failure</li><li>Reject duplicated mechanisms</li><li>Update the five-route portfolio</li></ul><strong>Reasoning stays accountable to artifacts.</strong></div>
    <div class="pass-column pass-execution"><span class="overline">Execution split</span><div class="execution-route"><strong>≤ 2 minutes</strong><span>Run inside the research pass with hashes, seed, limits, logs, and measured output.</span></div><div class="execution-route"><strong>&gt; 2 minutes</strong><span>Submit a shell-free lab job with pilot, immutable inputs, checkpoints, resource caps, and durable completion events.</span></div></div>
    <div class="pass-column pass-review"><span class="overline">Review return</span><h3>Prediction → observation</h3><p>Record surprise, reusable assets, constraints learned, failure signature, bottleneck update, and the cheapest next discriminator.</p><div class="decision-tags"><span>Continue</span><span>Validate</span><span>Redirect</span><span>Promote</span></div></div>
  </div>
</section>

<section id="memory" class="about-section memory-section">
  <div class="about-section-head"><div><span class="overline">03 / KNOWLEDGE + STATE</span><h2>What the engine remembers</h2></div><p>Different stores answer different questions. Mutable projections make the next pass efficient; append-only records and hashed artifacts preserve what actually happened.</p></div>
  <div class="memory-stack">
    <article><span class="memory-index">L1</span><div><span class="overline">Selection state</span><h3>Problem registry + source audits</h3><p>Exact statements, lanes, priority, recognition, current status, verification contract, and external acceptance route.</p></div><strong>Chooses what may run</strong></article>
    <article><span class="memory-index">L2</span><div><span class="overline">Working memory</span><h3>Research map + tactical memory</h3><p>Established facts, scoped exclusions, open leads, strategies, route fingerprints, prediction/observation learning, and next-session checkpoint.</p></div><strong>Lets the next pass resume</strong></article>
    <article><span class="memory-index">L3</span><div><span class="overline">Anti-rediscovery layer</span><h3>Prior art + cross-problem brain</h3><p>Nearest historical mechanisms, required material delta, source URLs, shared concepts, reusable methods, and explicit transfer hypotheses.</p></div><strong>Stops renamed repetition</strong></article>
    <article><span class="memory-index">L4</span><div><span class="overline">Immutable evidence</span><h3>Attempts + experiment receipts</h3><p>Claims, citations, hashes, commands, seeds, limits, logs, manifests, certificates, checker results, failures, and human adjudications.</p></div><strong>Records what happened</strong></article>
    <article><span class="memory-index">L5</span><div><span class="overline">Provenance + projection</span><h3>Per-problem Git repos + public ledger</h3><p>Readable checkpoints, ordinary-sized artifacts, AI/tool disclosure, publication packets, limits, and the public distinction between attempt and accepted result.</p></div><strong>Makes the trail inspectable</strong></article>
  </div>
</section>

<section id="roles" class="about-section roles-section">
  <div class="about-section-head"><div><span class="overline">04 / PERSONAS</span><h2>Six roles, separate powers</h2></div><p>The names describe responsibilities, not claims of personhood. Separation keeps discovery, verification, and publication from collapsing into one optimistic voice.</p></div>
  <div class="role-grid">
    <article><span class="role-glyph">S</span><span class="overline">Scout</span><h3>Finds legitimate openings</h3><p>Checks live source status, upstream work, recognition, tractability, certificate shape, and a real external recipient.</p><strong>Cannot lower the intake bar</strong></article>
    <article><span class="role-glyph">R</span><span class="overline">Reconnaissance delegates</span><h3>Challenge before committing</h3><p>Source, prior-art, and experiment specialists produce compact memos with falsifiers and stop conditions.</p><strong>Memos are leads, not evidence</strong></article>
    <article><span class="role-glyph">P</span><span class="overline">Principal investigator</span><h3>Owns the research decision</h3><p>Selects one route, audits every inherited claim, executes bounded reasoning, and leaves structured state for the next epoch.</p><strong>Cannot self-promote a result</strong></article>
    <article><span class="role-glyph">L</span><span class="overline">Lab worker</span><h3>Runs deterministic compute</h3><p>Executes argv without a shell, under CPU, memory, time, workspace, checkpoint, and artifact-growth controls.</p><strong>Queueing compute is not evidence</strong></article>
    <article><span class="role-glyph">V</span><span class="overline">Skeptic + verifier</span><h3>Starts from the artifact</h3><p>Checks the statement, scope, certificate, independent replay, and novelty without inheriting the researcher's conclusion.</p><strong>Model agreement does not count</strong></article>
    <article><span class="role-glyph">H</span><span class="overline">Human steward</span><h3>Accepts responsibility</h3><p>Charlie reviews the bounded release packet and explicitly approves publication. Outside experts or maintainers determine external acceptance.</p><strong>Approval is not peer review</strong></article>
  </div>
</section>

<section id="gates" class="about-section gate-section">
  <div class="about-section-head"><div><span class="overline">05 / CLAIM CONTROL</span><h2>The publication firewall</h2></div><p>A correct computation can still be unoriginal, irrelevant, or too narrowly scoped. Each gate asks a different question and fails closed.</p></div>
  <ol class="gate-flow">
    <li><span>01</span><div><strong>Contribution gate</strong><p>Is there a meaningful delta, recognized contribution class, reproducible novelty search, independent validation, and real acceptance path?</p></div></li>
    <li><span>02</span><div><strong>Isolated skeptic</strong><p>Does the claim survive statement, scope, certificate, adversarial, and literature checks without relying on the research transcript?</p></div></li>
    <li><span>03</span><div><strong>Charlie approval</strong><p>Is the bounded packet honest, useful, appropriately disclosed, and ready to put his name behind?</p></div></li>
    <li><span>04</span><div><strong>Mechanical release</strong><p>Publish the artifacts, manifest, citations, limitations, AI disclosure, validation plan, and public classification.</p></div></li>
    <li><span>05</span><div><strong>External acceptance</strong><p>Repository merge, expert confirmation, venue review, or another sourced outside event. Self-publication alone scores zero.</p></div></li>
  </ol>
  <div class="status-legend" aria-label="Public result classifications"><span><i class="status-dot attempt"></i>Attempt</span><span><i class="status-dot candidate"></i>Candidate</span><span><i class="status-dot verified"></i>Computationally verified</span><span><i class="status-dot reviewed"></i>Independently reviewed</span><span><i class="status-dot published"></i>Published / accepted</span></div>
</section>

<section class="about-source"><span class="overline">OPEN RESEARCH RECORD</span><h2>Inspect the machinery.</h2><p>All engine code, public problem repositories, research records, limitations, and tool disclosures are inspectable. Commits establish provenance; certificates, checkers, and outside review establish mathematical confidence.</p><a href="https://github.com/ctkrug/proofs">View source and repositories →</a></section>
"""
    return _layout("How it works", body, description="Architecture, research process, roles, memory, verification, and publication gates inside Proof Factory.")


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
                    render_template(
                        BRAIN_LINK,
                        problem_id=target.get("problem_id"),
                        label=target.get("label"),
                        concepts=", ".join(edge.get("concepts") or []),
                    )
                )
            elif edge.get("relation") == "uses_concept":
                concepts.append(str(target.get("label") or ""))
        cards.append(
            render_template(
                BRAIN_CARD,
                problem_id=problem.get("problem_id"),
                baseline_status=problem.get("baseline_status"),
                lane=problem.get("lane"),
                url=problem.get("url"),
                label=problem.get("label"),
                summary=problem.get("summary"),
                concepts=", ".join(concepts[:12]) or "Awaiting baseline.",
                links=html_fragment("".join(links[:8]) or "<li>No shared concept edge yet.</li>"),
            )
        )
    counts = brain.summary(graph)
    body = render_template(
        BRAIN_PAGE,
        node_count=counts.get("nodes"),
        edge_count=counts.get("edges"),
        concept_count=counts.get("concept", 0),
        cards=html_fragment("".join(cards)),
    )
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


ACADEMIC_CSS = r"""
/* Academic journal interface / v4 */
:root{
  --ink:#1d2625;--muted:#66706e;--paper:#f4f1e8;--card:#fbfaf5;--card-2:#eeeae0;
  --line:#cec8ba;--line-bright:#969c97;--red:#7c2f36;--amber:#96691e;--green:#315c4f;
  --blue:#2f4e67;--violet:#554b70;--black:#17211f;
  --mono:"Avenir Next",Avenir,"Helvetica Neue",Arial,sans-serif;
  --serif:Charter,"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
}
html{background:var(--paper);scroll-padding-top:70px}
body{background:var(--paper);color:var(--ink);font-family:var(--serif);font-size:16px;line-height:1.58}
a{color:var(--blue)}a:focus-visible,button:focus-visible{outline-color:var(--red)}
.skip-link{background:var(--ink);color:#fff;font-family:var(--mono)}
.topbar{height:68px;padding:0 clamp(20px,4.5vw,76px);border-color:var(--line);background:rgba(244,241,232,.96);box-shadow:none}
.brand{color:var(--ink);font-family:var(--serif);font-size:17px;font-weight:650;letter-spacing:.005em;text-transform:none}
.brand-mark{width:32px;height:32px;border:1px solid var(--ink);border-radius:50%;background:transparent;color:var(--ink);font:700 10px var(--mono)}
.brand small{border-color:var(--line);color:var(--muted);font:600 9px var(--mono);letter-spacing:.12em;text-transform:uppercase}
.topbar nav{gap:clamp(13px,2.1vw,30px)}
.topbar nav a,footer a{color:var(--muted);font:650 10px var(--mono);letter-spacing:.09em;text-transform:uppercase}
.topbar nav a:hover,footer a:hover{color:var(--red)}
main{max-width:1480px;border-color:var(--line);background:var(--paper)}
.hero{padding:clamp(70px,8.5vw,126px) clamp(24px,7vw,108px) clamp(60px,7vw,94px);border-color:var(--line);background:linear-gradient(120deg,#f7f4ec,#eee9de)}
.hero:before{content:"R(5,5)  ·  GRAPH THEORY  ·  FORMAL METHODS";right:5.5vw;top:48px;color:rgba(47,78,103,.065);font:650 clamp(28px,4vw,58px)/1.05 var(--mono);letter-spacing:-.045em;transform:none}
.hero-kicker,.overline,.panel-label,.eyebrow{color:var(--red);font:650 10px var(--mono);letter-spacing:.14em;text-transform:uppercase}
.hero h1,.dossier-head h1,.attempt-head h1,.method-head h1{max-width:1100px;margin:24px 0 26px;color:var(--ink);font-family:var(--serif);font-size:clamp(48px,7vw,96px);font-weight:400;line-height:1.01;letter-spacing:-.045em}
.hero h1 em,.method-head h1 em{color:var(--red);font-style:normal}
.hero-copy{max-width:800px;color:#48514f;font-family:var(--serif);font-size:clamp(18px,1.8vw,24px);line-height:1.55}
.candidate-alert,.internal-alert{border-color:#c9aa74;background:#f6ecd7;color:var(--ink)}.candidate-alert p{color:#66573f}.pulse{background:var(--amber);box-shadow:none}
.candidate-review{margin:28px clamp(20px,7vw,110px);padding:clamp(24px,4vw,42px);border:1px solid #c9aa74;background:#f6ecd7;display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,.8fr);gap:clamp(28px,5vw,72px)}.candidate-review h2{margin:8px 0 12px;font:400 clamp(30px,4vw,48px)/1.05 var(--serif)}.candidate-review-copy p{max-width:680px;color:#66573f}.candidate-review-copy code{display:block;margin-top:18px}.candidate-review-form{display:grid;gap:15px}.candidate-review-form label{display:grid;gap:6px;color:var(--ink);font:700 10px var(--mono);letter-spacing:.08em;text-transform:uppercase}.candidate-review-form textarea,.candidate-review-form input{width:100%;border:1px solid #bca77f;background:#fffdf7;color:var(--ink);padding:12px;font:400 14px/1.45 var(--sans);text-transform:none;letter-spacing:0}.candidate-review-form textarea{min-height:96px;resize:vertical}.candidate-review-form button{justify-self:start;border:0;background:var(--ink);color:#fff;padding:12px 18px;font:700 10px var(--mono);letter-spacing:.08em;text-transform:uppercase;cursor:pointer}.candidate-review-form button:disabled{opacity:.55;cursor:wait}.candidate-review-status{min-height:1.4em;margin:0;color:#66573f;font-size:13px}.candidate-review-status.is-error{color:var(--red)}
.section-block{padding:clamp(48px,6vw,78px) clamp(24px,7vw,108px)}
.section-heading{margin-bottom:26px;padding-bottom:17px;border-color:var(--line)}
.section-heading h2{color:var(--ink);font-family:var(--serif);font-size:clamp(34px,4.3vw,56px);font-weight:400;letter-spacing:-.035em}
.section-note{color:var(--muted);font:600 9px var(--mono);letter-spacing:.09em}
.operations{border-bottom:1px solid var(--line);background:#f8f6f0}
.operations .section-heading{margin-bottom:0}.healthline{margin:0;padding:14px 0;border-top:0;border-color:var(--line);color:var(--muted);font:550 10px var(--mono);letter-spacing:.035em}
.health{color:var(--ink)}.health:before{background:var(--amber);box-shadow:none}.health-healthy:before{background:var(--green)}.health-degraded:before{background:var(--red)}
.operation-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:18px}
.operation-card{position:relative;min-width:0;padding:26px 28px 24px;border:1px solid var(--line);background:var(--card)}
.operation-card:before{content:"";position:absolute;left:-1px;top:-1px;bottom:-1px;width:4px;background:var(--blue)}.operation-hard:before{background:var(--red)}
.operation-head{display:flex;align-items:center;justify-content:space-between;gap:16px}.operation-status{color:var(--muted);font:650 10px var(--mono);letter-spacing:.07em;text-transform:uppercase}.operation-status.is-live{color:var(--green)}.operation-status.is-live:before{content:"";display:inline-block;width:7px;height:7px;margin-right:7px;border-radius:50%;background:var(--green)}
.operation-card h3{margin:24px 0 7px;color:var(--ink);font-size:clamp(24px,2.5vw,35px);font-weight:400;line-height:1.12}.operation-detail{margin:0;color:var(--muted);font-size:14px}
.operation-card dl{display:grid;grid-template-columns:.75fr 1.35fr 1fr;gap:0;margin:24px 0 0;border-top:1px solid var(--line)}.operation-card dl div{padding-top:14px}.operation-card dl div+div{padding-left:20px;border-left:1px solid var(--line)}.operation-card dt{color:var(--muted);font:650 9px var(--mono);letter-spacing:.1em;text-transform:uppercase}.operation-card dd{margin:4px 0 0;color:var(--ink);font:650 12px var(--mono)}
.problem-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.problem-card{min-height:350px;padding:24px;border-color:var(--line);background:var(--card)}.problem-card:hover{border-color:var(--line-bright)}
.lane,.badge{border-radius:0;font:700 8px var(--mono)}.lane{border-color:var(--line);background:transparent}.lane-hard{border-color:#b7898c;background:#f1e4e3;color:var(--red)}.lane-easy{border-color:#9eafbc;background:#e7edf0;color:var(--blue)}.lane-calibration{border-color:#aaa4b8;background:#ece9f0;color:var(--violet)}
.badge{border-color:var(--line);background:#f8f6f0;color:var(--muted)}.badge-candidate{border-color:#c9aa74;background:#f6ecd7;color:#76511a}.badge-active,.badge-progress,.badge-verified,.badge-published{border-color:#91aa9e;background:#e4ece7;color:var(--green)}.badge-attempted,.badge-failed,.badge-no_progress,.badge-error,.badge-internal_result{border-color:#bd9692;background:#f1e5e2;color:var(--red)}
.problem-card h3{font-size:26px}.problem-card p{color:#56605e;font-family:var(--serif);font-size:14px}.meter{background:#ddd7cb}.meter span{background:var(--red)}.card-meta,.card-actions{color:var(--muted);font:550 9px var(--mono)}.last-note{color:#525c59;font-family:var(--serif);font-size:13px}.card-actions{border-color:var(--line)}.card-actions a{color:var(--blue)}
.planned-block{border-color:var(--line);background:#eeeae0}.attempts-block{background:#e8e4da}.attempt-list{border-color:var(--line)}
.attempt-row{grid-template-columns:4px minmax(0,1fr);border-color:var(--line);background:rgba(251,250,245,.82)}.attempt-row:hover{background:var(--card)}.attempt-copy{padding:25px 28px}.eyebrow{color:var(--muted)}.attempt-copy h3{font-size:26px}.attempt-copy p{color:#56605e;font-family:var(--serif);font-size:14px}.attempt-copy .approach{color:var(--ink);font-weight:650}
.accomplishment{max-width:1020px;margin:15px 0 5px;padding:14px 17px;border-left:2px solid var(--blue);background:#f0eee7}.accomplishment>span{color:var(--blue);font:700 9px var(--mono);letter-spacing:.1em;text-transform:uppercase}.accomplishment p{margin:5px 0 0;color:#343d3b}.next-action{max-width:1020px}.arrow{color:var(--blue)}
.dossier-head,.attempt-head,.method-head{border-color:var(--line);background:linear-gradient(120deg,#f7f4ec,#eee9de)}.back{color:var(--muted)}.statement,.lead{color:#3f4947}.source-line a{color:var(--blue)}
.dossier-grid article,.attempt-detail article,.method-grid article,.research-grid article,.strategy-library article,.about-grid article{border-color:var(--line);background:var(--card)}.dossier-grid p,.attempt-detail p,.research-grid li,.attempt-detail li,.strategy-library p,.strategy-library li,.method-grid p,.about-grid p,.about-source p{color:#525c59;font-family:var(--serif);font-size:14px}.techniques{border-color:var(--line);background:var(--card)}.techniques>div span{border-color:var(--line);color:var(--muted)}
.research-grid h3,.strategy-library h2,.method-grid h2,.about-grid h2,.principles h2{color:var(--ink)}.strategy-sources a{color:var(--blue)}
.principles,.about-source{border-color:var(--line);background:var(--black);color:#f3f0e8}.principles h2,.about-source h2{color:#fff}.principles p,.principles li,.about-source p{color:#d3d7d2}.principles a,.about-source a{color:#e5d6b7}
.empty{border-color:var(--line);background:var(--card);color:var(--muted)}code{color:var(--red)}
footer{background:var(--black);color:#acb4b0;border-color:var(--black)}footer a{color:#d8ddd8}
@media(max-width:1080px){.problem-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){.hero:before{display:none}.operation-grid,.problem-grid{grid-template-columns:1fr}.operation-card dl{grid-template-columns:1fr}.operation-card dl div+div{margin-top:12px;padding-left:0;border-left:0}.topbar nav a{font-size:8px}.section-heading{align-items:flex-start}.attempt-copy{padding:20px}.accomplishment{padding:12px 14px}}
"""


ABOUT_CSS = r"""
/* Proof engine architecture / about */
.about-head{position:relative;overflow:hidden;padding-bottom:52px}
.about-head:after{content:"SOURCE → STATE → TEST → EVIDENCE → REVIEW";position:absolute;right:5vw;bottom:28px;color:rgba(124,47,54,.09);font:700 clamp(18px,2.8vw,42px) var(--mono);letter-spacing:-.03em;white-space:nowrap}
.about-head>p{max-width:900px;color:#46514e;font-size:clamp(18px,2vw,25px)}
.about-jump{position:relative;z-index:1;display:flex;flex-wrap:wrap;gap:8px;margin-top:34px}
.about-jump a{padding:8px 11px;border:1px solid var(--line);background:rgba(251,250,245,.7);color:var(--ink);font:650 9px var(--mono);letter-spacing:.1em;text-decoration:none;text-transform:uppercase}
.about-jump a:hover{border-color:var(--red);color:var(--red)}
.about-section{padding:clamp(54px,7vw,92px) clamp(24px,7vw,108px);border-bottom:1px solid var(--line)}
.about-section:nth-of-type(odd){background:#eeeae0}
.about-section-head{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(260px,.7fr);align-items:end;gap:50px;margin-bottom:36px}
.about-section-head h2{margin:8px 0 0;color:var(--ink);font:400 clamp(38px,5vw,64px)/.98 var(--serif);letter-spacing:-.04em}
.about-section-head>p{max-width:520px;margin:0;color:#525c59;font-size:15px}
.engine-inputs{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border:1px solid var(--line);border-bottom:0;background:#e5e0d5}
.engine-inputs span{padding:10px 12px;border-right:1px solid var(--line);color:var(--muted);font:650 9px var(--mono);letter-spacing:.09em;text-align:center;text-transform:uppercase}
.engine-inputs span:last-child{border-right:0}
.engine-flow{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));margin:0;padding:0;border:1px solid var(--line);list-style:none;background:var(--card)}
.engine-flow li{position:relative;min-width:0;min-height:330px;padding:22px 18px 18px;border-right:1px solid var(--line)}
.engine-flow li:last-child{border-right:0}
.engine-flow li:not(:last-child):after{content:"→";position:absolute;z-index:2;right:-13px;top:52px;width:24px;height:24px;border:1px solid var(--line);background:var(--paper);color:var(--red);font:700 15px/22px var(--mono);text-align:center}
.step-no{display:block;margin-bottom:25px;color:var(--red);font:500 30px/1 var(--mono)}
.engine-flow h3{min-height:60px;margin:10px 0 12px;color:var(--ink);font:400 22px/1.08 var(--serif)}
.engine-flow p{margin:0;color:#56605e;font-size:13px;line-height:1.55}
.engine-flow strong{position:absolute;right:18px;bottom:18px;left:18px;padding-top:11px;border-top:1px solid var(--line);color:var(--blue);font:650 8px var(--mono);letter-spacing:.07em;text-transform:uppercase}
.engine-return{display:grid;grid-template-columns:auto 1fr;align-items:center;gap:16px;padding:15px 20px;border:1px solid var(--line);border-top:0;background:var(--black);color:#f3f0e8}
.engine-return>span{color:#d8c49e;font:400 32px var(--mono)}.engine-return p{margin:0;color:#d3d7d2;font-size:13px}.engine-return strong{color:#fff}
.pass-section{background:#f4f1e8!important}
.pass-map{display:grid;grid-template-columns:1fr 1.12fr 1.12fr 1fr 1fr;gap:0;border:1px solid var(--line);background:var(--card)}
.pass-column{position:relative;min-width:0;min-height:390px;padding:22px;border-right:1px solid var(--line)}.pass-column:last-child{border-right:0}
.pass-column:not(:last-child):after{content:"";position:absolute;z-index:2;right:-5px;top:49px;width:9px;height:9px;border-top:2px solid var(--red);border-right:2px solid var(--red);background:var(--card);transform:rotate(45deg)}
.pass-column h3{margin:24px 0 12px;color:var(--ink);font:400 26px/1.08 var(--serif)}.pass-column p,.pass-column li{color:#56605e;font-size:13px}.pass-column ul{padding-left:18px}
.pass-column>strong{display:block;margin-top:22px;color:var(--red);font:650 9px/1.5 var(--mono);letter-spacing:.07em;text-transform:uppercase}
.pass-start{background:#f0eee7}.pass-principal{background:#e8ece7}.pass-review{background:#f1e8e4}
.mini-role,.execution-route{margin-top:14px;padding:12px;border-left:2px solid var(--blue);background:#f0eee7}.mini-role strong,.mini-role span,.execution-route strong,.execution-route span{display:block}.mini-role strong,.execution-route strong{color:var(--ink);font-size:13px}.mini-role span,.execution-route span{margin-top:3px;color:#5c6663;font-size:11.5px;line-height:1.45}
.pass-delegates small{display:block;margin-top:15px;color:var(--muted);font:600 8px/1.5 var(--mono);letter-spacing:.06em;text-transform:uppercase}
.execution-route{border-color:var(--green)}.execution-route+ .execution-route{border-color:var(--red)}
.decision-tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:22px}.decision-tags span{padding:5px 7px;border:1px solid #bd9692;color:var(--red);font:650 8px var(--mono);letter-spacing:.07em;text-transform:uppercase}
.memory-section{background:#e8e4da!important}
.memory-stack{max-width:1120px;margin:0 auto}.memory-stack article{display:grid;grid-template-columns:62px minmax(0,1fr) minmax(150px,.28fr);align-items:center;gap:24px;min-height:128px;padding:20px 24px;border:1px solid var(--line);border-bottom:0;background:var(--card)}.memory-stack article:last-child{border-bottom:1px solid var(--line)}
.memory-stack article:nth-child(2){margin:0 18px}.memory-stack article:nth-child(3){margin:0 36px}.memory-stack article:nth-child(4){margin:0 54px}.memory-stack article:nth-child(5){margin:0 72px}
.memory-index{display:grid;width:50px;height:50px;place-items:center;border:1px solid var(--red);border-radius:50%;color:var(--red);font:650 12px var(--mono)}
.memory-stack h3{margin:6px 0 4px;color:var(--ink);font:400 23px var(--serif)}.memory-stack p{margin:0;color:#56605e;font-size:13px}.memory-stack article>strong{color:var(--blue);font:650 8px/1.5 var(--mono);letter-spacing:.07em;text-align:right;text-transform:uppercase}
.roles-section{background:#f4f1e8!important}.role-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.role-grid article{position:relative;min-height:290px;padding:25px;border:1px solid var(--line);background:var(--card)}
.role-glyph{display:grid;width:42px;height:42px;margin-bottom:27px;place-items:center;border:1px solid var(--ink);border-radius:50%;color:var(--ink);font:650 11px var(--mono)}
.role-grid h3{margin:9px 0 11px;color:var(--ink);font:400 27px/1.08 var(--serif)}.role-grid p{color:#56605e;font-size:13px}.role-grid strong{position:absolute;right:25px;bottom:22px;left:25px;padding-top:11px;border-top:1px solid var(--line);color:var(--red);font:650 8px var(--mono);letter-spacing:.07em;text-transform:uppercase}
.gate-section{background:#eeeae0!important}.gate-flow{margin:0;padding:0;border-top:1px solid var(--line);list-style:none}.gate-flow li{display:grid;grid-template-columns:70px minmax(0,1fr);gap:22px;padding:22px 0;border-bottom:1px solid var(--line)}.gate-flow li>span{color:var(--red);font:500 24px var(--mono)}.gate-flow strong{color:var(--ink);font:400 24px var(--serif)}.gate-flow p{max-width:890px;margin:4px 0 0;color:#56605e;font-size:13px}
.status-legend{display:flex;flex-wrap:wrap;gap:18px;margin-top:24px;color:var(--muted);font:650 8px var(--mono);letter-spacing:.07em;text-transform:uppercase}.status-legend span{display:flex;align-items:center;gap:7px}.status-dot{width:8px;height:8px;border-radius:50%;background:var(--muted)}.status-dot.candidate{background:var(--amber)}.status-dot.verified{background:var(--blue)}.status-dot.reviewed{background:var(--violet)}.status-dot.published{background:var(--green)}
.about-source{margin:0;padding:clamp(48px,6vw,78px) clamp(24px,7vw,108px);border:0;background:var(--black)}.about-source h2{margin:10px 0 12px;font:400 clamp(36px,4vw,54px) var(--serif)}.about-source p{max-width:900px}.about-source a{display:inline-block;margin-top:12px;color:#e5d6b7}
@media(max-width:1180px){.engine-flow{grid-template-columns:repeat(3,minmax(0,1fr))}.engine-flow li{border-bottom:1px solid var(--line)}.engine-flow li:nth-child(3){border-right:0}.engine-flow li:nth-child(3):after{display:none}.engine-flow li:nth-child(n+4){border-bottom:0}.pass-map{grid-template-columns:repeat(2,minmax(0,1fr))}.pass-column{min-height:0;border-bottom:1px solid var(--line)}.pass-column:nth-child(2),.pass-column:nth-child(4){border-right:0}.pass-column:nth-child(2):after,.pass-column:nth-child(4):after{display:none}.pass-column:last-child{grid-column:1/-1;border-bottom:0}}
@media(max-width:820px){.about-section-head{grid-template-columns:1fr;gap:16px}.engine-inputs{grid-template-columns:1fr 1fr}.engine-inputs span{border-bottom:1px solid var(--line)}.engine-inputs span:last-child{grid-column:1/-1}.role-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.memory-stack article,.memory-stack article:nth-child(n){grid-template-columns:50px minmax(0,1fr);margin:0}.memory-stack article>strong{grid-column:2;text-align:left}}
@media(max-width:820px){.candidate-review{grid-template-columns:1fr}}
@media(max-width:620px){.topbar nav a:not(:last-child){display:none!important}.about-head:after{display:none}.about-head,.about-section,.about-source{max-width:100%;overflow:hidden}.about-head>*,.about-section *{min-width:0}.about-head p,.about-section p{overflow-wrap:anywhere}.about-section{padding-right:20px;padding-left:20px}.engine-inputs{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.engine-flow,.pass-map,.role-grid{grid-template-columns:minmax(0,1fr)}.engine-flow li{min-height:290px;border-right:0;border-bottom:1px solid var(--line)!important}.engine-flow li:last-child{border-bottom:0!important}.engine-flow li:not(:last-child):after,.pass-column:not(:last-child):after{content:"↓";right:auto;top:auto;bottom:-13px;left:24px;width:24px;height:24px;border:1px solid var(--line);background:var(--paper);transform:none;text-align:center}.pass-column,.pass-column:nth-child(n){grid-column:auto;border-right:0;border-bottom:1px solid var(--line)}.pass-column:last-child{border-bottom:0}.role-grid article{min-height:270px}.memory-stack article{grid-template-columns:42px minmax(0,1fr);gap:14px;padding:18px 14px}.memory-index{width:38px;height:38px}.gate-flow li{grid-template-columns:42px minmax(0,1fr);gap:10px}.status-legend{display:grid;grid-template-columns:1fr 1fr}}
"""


SITE_JS = r"""
(() => {
  const labels = {
    progress: "Progress", no_progress: "No progress", failed: "Failed route", error: "Error",
    candidate: "Candidate — review needed", internal_result: "Internal result", verified: "Verified", published: "Public research note"
  };
  const programLabels = {hard: "Hard research queue", easy: "Open-problem program"};
  const renderBlockers = blockers => {
    const existing = document.querySelector("[data-operational-blockers]");
    if (!blockers?.length) { existing?.remove(); return; }
    const blocker = typeof blockers[0] === "object" ? blockers[0] : {detail: String(blockers[0])};
    const detail = blocker.detail || blocker.title || "A required research dependency is unavailable.";
    if (existing) { const copy = existing.querySelector("p"); if (copy) copy.textContent = `${detail} ${blocker.next_action || ""}`.trim(); return; }
    const alert = document.createElement("section"); alert.className = "candidate-alert operational-alert"; alert.dataset.operationalBlockers = "";
    alert.innerHTML = `<div><span class="pulse"></span><strong>Research infrastructure needs attention.</strong><p></p></div><a href="#runs">Open run history →</a>`;
    alert.querySelector("p").textContent = `${detail} ${blocker.next_action || ""}`.trim();
    document.querySelector(".hero")?.insertAdjacentElement("afterend", alert);
  };
  const renderUsagePolicy = policy => {
    const item = document.querySelector("[data-usage-policy]");
    if (item) item.textContent = policy?.reason || "Usage policy awaiting its first check.";
  };
  const dateText = value => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Not yet";
    return new Intl.DateTimeFormat("en-GB", {year:"numeric",month:"short",day:"2-digit",hour:"2-digit",minute:"2-digit",timeZone:"UTC",timeZoneName:"short"}).format(date);
  };
  const intervalText = seconds => {
    seconds = Math.max(0, Math.round(seconds));
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return hours ? `${hours}h ${minutes}m ${secs}s` : `${minutes}m ${secs}s`;
  };
  const updateClock = card => {
    const current = card.querySelector('[data-role="current-clock"]');
    const next = card.querySelector('[data-role="next-clock"]');
    if (!current || !next) return;
    const status = card.querySelector('[data-role="status"]')?.textContent;
    const started = new Date(current.dataset.startedAt || "");
    current.textContent = status === "Running now" && !Number.isNaN(started.getTime()) ? intervalText((Date.now() - started.getTime()) / 1000) : "Idle";
    const nextDate = new Date(next.dataset.nextAt || "");
    next.textContent = Number.isNaN(nextDate.getTime()) ? "Not scheduled" : `${dateText(next.dataset.nextAt)} · in ${intervalText((nextDate.getTime() - Date.now()) / 1000)}`;
  };
  const renderLane = (lane, payload) => {
    const card = document.querySelector(`[data-live-lane="${lane}"]`);
    if (!card || !payload) return;
    const running = payload.status === "running";
    const status = card.querySelector('[data-role="status"]');
    status.textContent = running ? "Running now" : "Between runs";
    status.classList.toggle("is-live", running);
    card.querySelector('[data-role="title"]').textContent = payload.running_problem_title || (lane === "hard" ? "Exact-problem queue" : "Discovery queue");
    card.querySelector('[data-role="detail"]').textContent = running ? "Research pass in progress" : "Next dispatch scheduled";
    card.querySelector('[data-role="current-clock"]').dataset.startedAt = payload.started_at || "";
    card.querySelector('[data-role="next-clock"]').dataset.nextAt = payload.next_at || "";
    card.querySelector('[data-role="last-result"]').textContent = labels[payload.last_outcome] || (payload.last_outcome || "Not yet").replaceAll("_", " ");
    updateClock(card);
  };
  const el = (name, className, text) => {
    const node = document.createElement(name);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  };
  const renderRuns = runs => {
    const list = document.querySelector("[data-live-runs]");
    if (!list || !Array.isArray(runs) || !runs.length) return;
    list.replaceChildren(...runs.map(run => {
      const article = el("article", "attempt-row"); article.dataset.outcome = run.outcome || "unknown"; article.dataset.runId = run.id || "";
      article.append(el("div", `attempt-rail outcome-${run.outcome || "unknown"}`));
      const copy = el("div", "attempt-copy");
      const eyebrow = el("div", "eyebrow"); eyebrow.append(el("span", "", dateText(run.finished_at)), el("span", "", `${programLabels[run.lane] || "Research program"} · ${run.duration_seconds ? Math.round(run.duration_seconds / 60) + " min" : "duration unavailable"}`));
      const h3 = el("h3"); const title = el("a", "", run.problem_title || run.problem_id); title.href = run.href; h3.append(title);
      const approach = el("p", "approach", run.approach || "Research pass");
      const accomplishment = el("div", "accomplishment"); accomplishment.append(el("span", "", "What this run accomplished"), el("p", "", run.accomplishment || "No accomplishment summary was recorded."));
      copy.append(eyebrow, h3, approach, accomplishment);
      if (run.next_action) { const next = el("p", "next-action"); next.append(el("strong", "", "Next: "), document.createTextNode(run.next_action)); copy.append(next); }
      const end = el("div", "row-end"); end.append(el("span", `badge badge-${run.outcome || "unknown"}`, labels[run.outcome] || (run.outcome || "unknown").replaceAll("_", " ")));
      const link = el("a", "arrow", "Open full record →"); link.href = run.href; end.append(link); copy.append(end); article.append(copy); return article;
    }));
  };
  const refresh = async () => {
    try {
      const response = await fetch("/api/live", {cache:"no-store", headers:{accept:"application/json"}});
      if (!response.ok) return;
      const data = await response.json(); if (!data.available) return;
      renderLane("hard", data.lanes?.hard); renderLane("easy", data.lanes?.easy); renderRuns(data.recent_runs); renderBlockers(data.operational_blockers); renderUsagePolicy(data.usage_policy);
      const updated = document.querySelector("[data-live-updated]"); if (updated) updated.textContent = `Live data · ${dateText(data.generated_at)}`;
      const health = document.querySelector("[data-live-health]"); if (health) { health.textContent = `System ${data.health || "starting"}`; health.className = `health health-${data.health || "starting"}`; health.dataset.liveHealth = ""; }
    } catch (_) { /* Static render remains the honest fallback. */ }
  };
  document.querySelectorAll("[data-live-lane]").forEach(updateClock);
  setInterval(() => document.querySelectorAll("[data-live-lane]").forEach(updateClock), 1000);
  refresh(); setInterval(refresh, 30000);

  document.querySelectorAll("[data-candidate-review]").forEach(panel => {
    const form = panel.querySelector("[data-candidate-review-form]");
    const status = panel.querySelector("[data-candidate-review-status]");
    const button = form?.querySelector('button[type="submit"]');
    const attemptId = panel.dataset.attemptId;
    const setStatus = (message, error = false) => { status.textContent = message; status.classList.toggle("is-error", error); };
    const poll = async () => {
      for (let count = 0; count < 30; count += 1) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const response = await fetch(`/api/reviews/status?attempt_id=${encodeURIComponent(attemptId)}`, {cache:"no-store"});
        if (!response.ok) continue;
        const data = await response.json();
        if (data.status === "approved") { setStatus("Approved. Refreshing the signed ledger…"); window.location.reload(); return; }
        if (data.status === "error") { setStatus(data.message || "Approval could not be recorded.", true); button.disabled = false; return; }
      }
      setStatus("Approval is queued. The public ledger will update shortly."); button.disabled = false;
    };
    form?.addEventListener("submit", async event => {
      event.preventDefault(); button.disabled = true; setStatus("Checking approval…");
      const fields = new FormData(form);
      try {
        const response = await fetch("/api/reviews", {method:"POST",headers:{"content-type":"application/json","accept":"application/json"},body:JSON.stringify({attempt_id:attemptId,note:fields.get("note"),password:fields.get("password")})});
        const data = await response.json().catch(() => ({}));
        if (!response.ok) { setStatus(data.error || "Approval could not be queued.", true); button.disabled = false; return; }
        form.querySelector('[name="password"]').value = ""; setStatus("Approval queued. Waiting for the signed review ledger…"); poll();
      } catch (_) { setStatus("Network error. Please try again.", true); button.disabled = false; }
    });
  });
})();
"""


WORKER_JS = r"""
const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}
});
const safeAttempt = value => typeof value === "string" && /^[A-Za-z0-9._-]{1,200}$/.test(value);
const sameOrigin = request => {
  const origin = request.headers.get("origin");
  return origin && origin === new URL(request.url).origin;
};
const equalSecret = async (left, right) => {
  if (typeof left !== "string" || typeof right !== "string") return false;
  const encode = value => crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  const [a, b] = await Promise.all([encode(left), encode(right)]);
  const aa = new Uint8Array(a), bb = new Uint8Array(b);
  let diff = aa.length ^ bb.length;
  for (let i = 0; i < Math.max(aa.length, bb.length); i += 1) diff |= (aa[i] || 0) ^ (bb[i] || 0);
  return diff === 0;
};
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/live") {
      const value = env.PROOF_RUNTIME ? await env.PROOF_RUNTIME.get("runtime") : null;
      return new Response(value || JSON.stringify({available:false}), {
        status: value ? 200 : 503,
        headers: {"content-type":"application/json; charset=utf-8","cache-control":"no-store"}
      });
    }
    if (url.pathname === "/api/reviews/status" && request.method === "GET") {
      const attemptId = url.searchParams.get("attempt_id");
      if (!safeAttempt(attemptId)) return json({error:"Invalid attempt."}, 400);
      const value = env.PROOF_RUNTIME ? await env.PROOF_RUNTIME.get(`review-status:${attemptId}`) : null;
      return value ? new Response(value, {headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}}) : json({status:"pending"});
    }
    if (url.pathname === "/api/reviews" && request.method === "POST") {
      if (!sameOrigin(request)) return json({error:"Approval must come from this site."}, 403);
      if (!env.PROOF_RUNTIME || !env.PROOF_REVIEW_PASSWORD) return json({error:"Approval service is unavailable."}, 503);
      const length = Number(request.headers.get("content-length") || 0);
      if (length > 4096) return json({error:"Request is too large."}, 413);
      let body;
      try {
        const raw = await request.text();
        if (new TextEncoder().encode(raw).length > 4096) return json({error:"Request is too large."}, 413);
        body = JSON.parse(raw);
      } catch (_) { return json({error:"Invalid request."}, 400); }
      if (!safeAttempt(body.attempt_id) || typeof body.note !== "string" || !body.note.trim() || body.note.length > 1000) return json({error:"Attempt and review note are required."}, 400);
      if (!await equalSecret(body.password, env.PROOF_REVIEW_PASSWORD)) return json({error:"Password incorrect."}, 401);
      const key = `review-request:${body.attempt_id}`;
      const existing = await env.PROOF_RUNTIME.get(key);
      if (!existing) await env.PROOF_RUNTIME.put(key, JSON.stringify({schema_version:1,attempt_id:body.attempt_id,decision:"accept",note:body.note.trim(),reviewer:"Charlie Krug",release:false,requested_at:new Date().toISOString(),source:"site-ui"}), {expirationTtl:604800});
      await env.PROOF_RUNTIME.put(`review-status:${body.attempt_id}`, JSON.stringify({status:"queued",attempt_id:body.attempt_id}), {expirationTtl:604800});
      return json({status:"queued",attempt_id:body.attempt_id}, 202);
    }
    return env.ASSETS.fetch(request);
  }
};
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
    _write(store.SITE / "assets" / "site-v5.css", CSS + ACADEMIC_CSS + ABOUT_CSS)
    _write(store.SITE / "assets" / "site-v4.js", SITE_JS)
    _write(store.SITE / "_worker.js", WORKER_JS)
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
