from __future__ import annotations

import html
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import store


STATUS_ORDER = ["candidate", "active", "attempted", "failed", "queued", "parked", "verified", "published"]
STATUS_LABELS = {
    "queued": "Queued",
    "active": "Active / ongoing",
    "attempted": "Tried — still open",
    "parked": "Paused after 3 passes",
    "failed": "Failed route",
    "candidate": "Candidate — review needed",
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


def _layout(title: str, body: str, *, description: str = "Live, transparent AI-assisted mathematics research ledger.") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{h(title)} · Proof Factory</title>
  <meta name="description" content="{h(description)}">
  <link rel="stylesheet" href="/assets/site.css">
  <script defer src="/assets/site.js"></script>
  <script>MathJax={{tex:{{inlineMath:[['$','$'],['\\(','\\)']]}}}};</script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/"><span class="brand-mark">∎</span><span>Proof Factory</span></a>
    <nav><a href="/#problems">Targets</a><a href="/#attempts">Attempts</a><a href="/method/">Method</a><a href="/api/state.json">Data</a></nav>
  </header>
  <main>{body}</main>
  <footer><span>AI-assisted research, disclosed per attempt.</span><span>Human responsibility: Charlie Krug.</span><span>UTC · <a href="https://github.com/ctkrug/proofs">Source</a></span></footer>
</body>
</html>"""


def _attempt_row(attempt: dict[str, Any], problem: dict[str, Any]) -> str:
    outcome = str(attempt.get("outcome") or "unknown")
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


def _problem_card(problem: dict[str, Any], attempts: list[dict[str, Any]]) -> str:
    last = attempts[-1] if attempts else None
    status = str(problem.get("status") or "queued")
    lane = str(problem.get("lane") or "easy")
    return f"""
<article class="problem-card" data-status="{h(status)}" data-lane="{h(lane)}">
  <div class="card-top"><span class="lane lane-{h(lane)}">{h(lane)}</span>{_badge(status)}</div>
  <h3><a href="/problems/{h(problem['id'])}/">{h(problem['title'])}</a></h3>
  <p>{h(problem.get('statement'))}</p>
  <div class="meter"><span style="width:{min(100, int(problem.get('difficulty') or 0) * 10)}%"></span></div>
  <div class="card-meta"><span>Difficulty {h(problem.get('difficulty'))}/10</span><span>{h(problem.get('attempt_count', 0))} attempts</span></div>
  <div class="last-note"><strong>Latest:</strong> {h((last or {}).get('summary') or 'No research pass yet.')}</div>
  <div class="card-actions"><a href="{h(problem.get('source_url'))}" rel="noopener">Official source ↗</a><a href="/problems/{h(problem['id'])}/">Full record →</a></div>
</article>"""


def _index(problems: list[dict[str, Any]], attempts: list[dict[str, Any]], runtime: dict[str, Any]) -> str:
    by_problem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        by_problem[str(attempt.get("problem_id"))].append(attempt)
    candidates = [row for row in problems if row.get("status") == "candidate"]
    hard = next((row for row in problems if row.get("lane") == "hard" and row.get("status") in {"active", "attempted", "candidate"}), None)
    easy = next(
        (row for row in problems if row.get("lane") == "easy" and row.get("status") in {"active", "attempted", "candidate"}),
        None,
    )
    accepted = sum(1 for row in problems if row.get("accepted_result") is True)
    health = runtime.get("health", "starting")
    health_issues = runtime.get("health_issues") or []
    running_lanes = [lane for lane in ("hard", "easy") if runtime.get(f"{lane}_running")]
    hard_run_text = (
        f"Running now · started {_time(runtime.get('hard_started_at'))}"
        if runtime.get("hard_running") else f"Last run: {_time((hard or {}).get('last_attempt_at'))}"
    )
    easy_run_text = (
        f"Running now · started {_time(runtime.get('easy_started_at'))}"
        if runtime.get("easy_running") else f"Last run: {_time((easy or {}).get('last_attempt_at'))}"
    )
    ordered = sorted(
        problems,
        key=lambda row: (
            STATUS_ORDER.index(row.get("status")) if row.get("status") in STATUS_ORDER else 99,
            0 if row.get("lane") == "hard" else 1,
            int(row.get("difficulty") or 10),
        ),
    )
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
  <div class="hero-kicker"><span class="live-dot"></span> Always-on research ledger</div>
  <h1>Every attempt.<br><em>Including the failures.</em></h1>
  <p class="hero-copy">A headless academic contribution system working one famous problem deeply while optimizing the discovery lane for the smallest legitimate, independently verifiable new result. Progress is public; claims are not trusted until independently checked.</p>
  <div class="hero-stats">
    <div><strong>{len(problems)}</strong><span>tracked problems</span></div>
    <div><strong>{len(attempts)}</strong><span>recorded attempts</span></div>
    <div><strong>{len(candidates)}</strong><span>candidates to review</span></div>
    <div><strong>{accepted}/2</strong><span>external wins before scaling</span></div>
  </div>
</section>
{candidate_banner}
<section class="lanes">
  <article class="lane-panel hard-panel">
    <div class="panel-label">Hard / famous lane · 2× daily · Sol xhigh</div>
    <h2>{h((hard or {}).get('title') or 'Selecting…')}</h2>
    <p>{h((hard or {}).get('rationale') or 'The hard lane is being initialized.')}</p>
    <div class="panel-foot"><span>{h(hard_run_text)}</span>{f'<a href="/problems/{h(hard["id"])}/">Open dossier →</a>' if hard else ''}</div>
  </article>
  <article class="lane-panel easy-panel">
    <div class="panel-label">Discovery lane · easier-first · 6× daily</div>
    <h2>{h((easy or {}).get('title') or 'Selecting…')}</h2>
    <p>{h((easy or {}).get('rationale') or 'The discovery lane is being initialized.')}</p>
    <div class="panel-foot"><span>{h(easy_run_text)}</span>{f'<a href="/problems/{h(easy["id"])}/">Open dossier →</a>' if easy else ''}</div>
  </article>
</section>
<section class="healthline"><span class="health health-{h(health)}">System {h(health)}</span><span>{h(live_work)}</span><span>Updated {_time(runtime.get('updated_at') or store.now_iso())}</span><span>{issues}</span></section>
<section id="problems" class="section-block">
  <div class="section-heading"><div><span class="overline">Contribution registry</span><h2>Active, tried, failed, and past work</h2></div><div class="filters"><button class="filter active" data-filter="all">All</button><button class="filter" data-filter="hard">Hard</button><button class="filter" data-filter="easy">Discovery</button><button class="filter" data-filter="candidate">Candidates</button></div></div>
  <div class="problem-grid">{''.join(_problem_card(row, by_problem[row['id']]) for row in ordered)}</div>
</section>
<section id="attempts" class="section-block attempts-block">
  <div class="section-heading"><div><span class="overline">Append-only history</span><h2>Recent research attempts</h2></div><a href="/api/state.json">Download JSON →</a></div>
  <div class="attempt-list">{''.join(_attempt_row(row, next(p for p in problems if p['id'] == row['problem_id'])) for row in reversed(attempts[-25:])) or '<p>No attempts yet.</p>'}</div>
</section>
"""
    return _layout("Live ledger", body)


def _problem_page(problem: dict[str, Any], attempts: list[dict[str, Any]]) -> str:
    technique_tags = "".join(f"<span>{h(x)}</span>" for x in problem.get("techniques") or [])
    attempt_html = "".join(_attempt_row(row, problem) for row in reversed(attempts)) or '<div class="empty">No attempt has completed yet. The problem is queued transparently.</div>'
    candidate = ""
    if problem.get("status") == "candidate":
        candidate = '<div class="candidate-alert"><div><strong>Unverified candidate finding</strong><p>Read the attempt and evidence below. This is not an accepted solution.</p></div></div>'
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
<section class="section-block attempts-block"><div class="section-heading"><div><span class="overline">Complete history</span><h2>Attempts on this problem</h2></div></div><div class="attempt-list">{attempt_html}</div></section>
"""
    return _layout(problem["title"], body, description=str(problem.get("statement")))


def _attempt_page(attempt: dict[str, Any], problem: dict[str, Any], reviews: list[dict[str, Any]]) -> str:
    def items(name: str) -> str:
        rows = attempt.get(name) or []
        return "<ul>" + "".join(f"<li>{h(x)}</li>" for x in rows) + "</ul>" if rows else '<p class="muted">None recorded.</p>'
    outcome = str(attempt.get("outcome") or "unknown")
    warning = ""
    if outcome == "candidate":
        warning = '<div class="candidate-alert"><div><strong>Candidate for review — not a solution claim</strong><p>Independent statement checking, criticism, literature review, and verification remain required.</p></div></div>'
    if problem.get("publication_attempt_id") == attempt.get("id"):
        warning += f'<div class="candidate-alert"><div><strong>{h(problem.get("publication_state"))}</strong><p>Human-approved research note; external acceptance and peer review are separate states.</p></div><a href="/publications/{h(attempt["id"])}/">Publication packet →</a></div>'
    review_html = "".join(
        f'<li><strong>{h(row.get("decision"))}</strong> · {h(_time(row.get("reviewed_at")))}<br>{h(row.get("note") or "No note recorded.")}</li>'
        for row in reviews
    ) or '<p class="muted">No human review recorded.</p>'
    body = f"""
<section class="attempt-head"><a class="back" href="/problems/{h(problem['id'])}/">← {h(problem['title'])}</a><div class="eyebrow"><span>{h(_time(attempt.get('finished_at')))}</span><span>{h(attempt.get('model'))} · {h(attempt.get('effort'))}</span></div><h1>{h(attempt.get('approach'))}</h1>{_badge(outcome)}<p class="lead">{h(attempt.get('summary'))}</p></section>
{warning}
<section class="attempt-detail">
  <article><span class="overline">Rationale</span><p>{h(attempt.get('rationale'))}</p></article>
  <article><span class="overline">Claims requiring scrutiny</span>{items('claims')}</article>
  <article><span class="overline">Evidence and scope</span>{items('evidence')}</article>
  <article><span class="overline">Computational experiments</span>{items('experiments')}</article>
  <article><span class="overline">Independent checker</span><p>{h(attempt.get('independent_checker') or 'Not provided.')}</p></article>
  <article><span class="overline">Cross-domain transfers tested</span>{items('transfer_insights')}</article>
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
  <article><strong>03</strong><h2>Experiment</h2><p>Sol designs theories and discriminating tests. Deterministic scripts, Terra, exact solvers, and proof tools do repetition, parameter sweeps, and falsification with recorded seeds and hashes.</p></article>
  <article><strong>04</strong><h2>Label</h2><p>Failed, no progress, progress, and candidate are distinct states. Candidate never means solved.</p></article>
  <article><strong>05</strong><h2>Review</h2><p>A candidate needs statement validation, isolated criticism, post-candidate literature search, reproducible evidence, and Charlie's approval.</p></article>
  <article><strong>06</strong><h2>Release</h2><p>One human approval action creates and publishes a versioned research packet with claims, artifacts, hashes, citations, limitations, and AI disclosure. Expert and peer-review states remain separate.</p></article>
</section>
<section class="principles"><h2>Research integrity</h2><p>This project follows the practical direction of the Leiden Declaration: disclose automated tools, preserve attribution, support independent verification, retain human responsibility, and do not substitute a website post for peer review.</p><div><a href="https://leidendeclaration.ai/">Leiden Declaration ↗</a><a href="https://github.com/teorth/erdosproblems/wiki/What-to-do-when-I-think-I-managed-to-get-AI-to-solve-an-Erd%C5%91s-problem%3F">Erdős AI review guidance ↗</a><a href="https://github.com/google-deepmind/formal-conjectures">Formal Conjectures ↗</a></div></section>
"""
    return _layout("Method", body)


CSS = r"""
:root{--ink:#151716;--muted:#6b716d;--paper:#f4f1e8;--card:#fffdf7;--line:#d8d3c7;--red:#b64232;--amber:#c77b22;--green:#2b7254;--blue:#345f86;--black:#181a19}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.55}.topbar{height:72px;padding:0 clamp(20px,5vw,72px);display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);background:rgba(244,241,232,.94);backdrop-filter:blur(12px);position:sticky;top:0;z-index:20}.brand{display:flex;align-items:center;gap:11px;color:var(--ink);font-weight:760;text-decoration:none;letter-spacing:-.02em}.brand-mark{width:30px;height:30px;display:grid;place-items:center;background:var(--black);color:#fff;border-radius:50%;font-size:14px}.topbar nav{display:flex;gap:26px}.topbar nav a,footer a{color:var(--ink);text-decoration:none;font-size:14px}.topbar nav a:hover{text-decoration:underline}main{max-width:1440px;margin:auto}.hero{padding:clamp(74px,10vw,150px) clamp(20px,7vw,110px) 74px;border-bottom:1px solid var(--line);background:radial-gradient(circle at 82% 18%,rgba(198,123,34,.13),transparent 28%),linear-gradient(135deg,#f7f4eb 0,#eee9dc 100%)}.hero-kicker,.overline,.panel-label,.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.12em;font-weight:750;color:var(--muted)}.live-dot,.pulse{width:8px;height:8px;border-radius:50%;display:inline-block;background:var(--green);margin-right:8px;box-shadow:0 0 0 5px rgba(43,114,84,.12)}.hero h1,.dossier-head h1,.attempt-head h1,.method-head h1{font-family:Georgia,"Times New Roman",serif;font-size:clamp(48px,8vw,112px);line-height:.93;letter-spacing:-.055em;font-weight:400;margin:23px 0 30px;max-width:1060px}.hero h1 em,.method-head h1 em{color:var(--red);font-weight:400}.hero-copy{max-width:770px;font-size:clamp(18px,2vw,25px);color:#444943}.hero-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin-top:62px;max-width:900px}.hero-stats div{background:rgba(255,253,247,.74);padding:22px}.hero-stats strong{font-family:Georgia,serif;font-size:36px;font-weight:400;display:block}.hero-stats span{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.candidate-alert{margin:28px clamp(20px,7vw,110px);padding:20px 24px;background:#fff3dc;border:1px solid #dca85d;display:flex;justify-content:space-between;align-items:center;gap:20px}.candidate-alert p{margin:3px 0 0;color:#6b512f}.candidate-alert a{color:var(--ink);font-weight:700}.pulse{background:var(--amber);margin-right:12px}.lanes{padding:55px clamp(20px,7vw,110px);display:grid;grid-template-columns:1fr 1fr;gap:24px}.lane-panel{min-height:280px;padding:34px;border:1px solid var(--line);background:var(--card);display:flex;flex-direction:column}.hard-panel{border-top:5px solid var(--red)}.easy-panel{border-top:5px solid var(--blue)}.lane-panel h2{font-family:Georgia,serif;font-size:36px;line-height:1.1;font-weight:400;margin:26px 0 12px}.lane-panel p{color:#545a55;max-width:650px}.panel-foot{margin-top:auto;padding-top:24px;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:20px;font-size:13px}.panel-foot a{color:var(--ink);font-weight:700}.healthline{margin:0 clamp(20px,7vw,110px) 35px;padding:14px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);display:flex;gap:24px;flex-wrap:wrap;font-size:13px;color:var(--muted)}.health{color:var(--ink);font-weight:750}.health:before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--amber);margin-right:8px}.health-healthy:before{background:var(--green)}.health-degraded:before{background:var(--red)}.section-block{padding:72px clamp(20px,7vw,110px)}.section-heading{display:flex;align-items:end;justify-content:space-between;gap:30px;margin-bottom:30px}.section-heading h2{font-family:Georgia,serif;font-weight:400;font-size:clamp(35px,5vw,60px);line-height:1;margin:8px 0 0}.section-heading>a{color:var(--ink);font-weight:700}.filters{display:flex;gap:8px;flex-wrap:wrap}.filter{border:1px solid var(--line);background:transparent;padding:9px 14px;border-radius:100px;cursor:pointer}.filter.active{background:var(--black);color:#fff;border-color:var(--black)}.problem-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.problem-card{background:var(--card);border:1px solid var(--line);padding:25px;min-height:390px;display:flex;flex-direction:column}.problem-card.hidden{display:none}.card-top{display:flex;justify-content:space-between;gap:12px;align-items:center}.lane,.badge{display:inline-flex;align-items:center;border-radius:100px;padding:5px 10px;font-size:11px;text-transform:uppercase;letter-spacing:.07em;font-weight:800}.lane{background:#ece8dc}.lane-hard{color:var(--red);background:#f8e5df}.lane-easy{color:var(--blue);background:#e3edf5}.lane-calibration{color:#64548c;background:#ece7f5}.badge{border:1px solid var(--line);background:#fff}.badge-candidate{background:#fff0d2;border-color:#dea750;color:#7a4c0d}.badge-active,.badge-progress{background:#e3f1ea;border-color:#9bc4af;color:#1f6348}.badge-attempted,.badge-failed,.badge-no_progress,.badge-error{background:#f2e7e2;border-color:#d5ada1;color:#8b392d}.badge-verified,.badge-published{background:#e2eee7;border-color:#8bb89e;color:#235e45}.problem-card h3{font-family:Georgia,serif;font-size:28px;line-height:1.1;font-weight:400;margin:22px 0 14px}.problem-card h3 a,.attempt-row h3 a{color:var(--ink);text-decoration:none}.problem-card p{font-size:14px;color:#4f5551}.meter{height:4px;background:#e5e0d5;margin-top:auto}.meter span{display:block;height:100%;background:var(--red)}.card-meta,.card-actions{display:flex;justify-content:space-between;gap:12px;font-size:12px;color:var(--muted);margin-top:9px}.last-note{font-size:13px;padding:17px 0;margin-top:18px;border-top:1px solid var(--line);color:#555b57}.card-actions{margin-top:auto;padding-top:13px}.card-actions a{color:var(--ink);font-weight:700;text-decoration:none}.attempts-block{background:#ebe6da}.attempt-list{border-top:1px solid #c9c2b4}.attempt-row{display:grid;grid-template-columns:5px 1fr;border-bottom:1px solid #c9c2b4;background:rgba(255,253,247,.45)}.attempt-rail{background:var(--muted)}.outcome-candidate{background:var(--amber)}.outcome-progress,.outcome-verified,.outcome-published{background:var(--green)}.outcome-failed,.outcome-no_progress,.outcome-error{background:var(--red)}.attempt-copy{padding:24px 28px}.eyebrow{display:flex;gap:25px}.attempt-copy h3{font-family:Georgia,serif;font-size:26px;font-weight:400;margin:11px 0}.attempt-copy p{margin:6px 0;color:#515753}.attempt-copy .approach{color:var(--ink);font-weight:700}.row-end{display:flex;justify-content:space-between;align-items:center;margin-top:16px}.arrow{color:var(--ink);font-weight:700;text-decoration:none}.dossier-head,.attempt-head,.method-head{padding:70px clamp(20px,7vw,110px) 55px;border-bottom:1px solid var(--line)}.dossier-head h1,.attempt-head h1,.method-head h1{font-size:clamp(48px,7vw,90px);margin-top:30px}.back{color:var(--ink);text-decoration:none;font-size:14px}.statement,.lead{font-family:Georgia,serif;font-size:clamp(20px,2.2vw,30px);max-width:1000px}.source-line{display:flex;gap:22px;margin-top:28px;flex-wrap:wrap}.source-line a{color:var(--ink);font-weight:700}.dossier-grid,.attempt-detail,.method-grid{padding:44px clamp(20px,7vw,110px);display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.dossier-grid article,.attempt-detail article,.method-grid article{background:var(--card);border:1px solid var(--line);padding:26px}.dossier-grid p,.attempt-detail p{color:#4d534e}.dossier-grid dl,.attempt-detail dl{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:14px 0 0}.dossier-grid dt,.attempt-detail dt{color:var(--muted)}.dossier-grid dd,.attempt-detail dd{margin:0;text-align:right}.techniques{margin:0 clamp(20px,7vw,110px);padding:26px;border:1px solid var(--line);background:var(--card)}.techniques>div{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}.techniques>div span{background:#ebe7dc;padding:7px 11px;border-radius:4px;font-size:13px}.empty{padding:34px;background:var(--card)}.attempt-detail{grid-template-columns:repeat(2,1fr)}.attempt-detail ul{padding-left:20px}.attempt-detail li{margin:8px 0}.attempt-detail a{overflow-wrap:anywhere;color:var(--blue)}code{font-size:11px;overflow-wrap:anywhere}.muted{color:var(--muted)}.method-head p{font-size:22px;max-width:750px}.method-grid{grid-template-columns:repeat(3,1fr)}.method-grid article strong{font-family:Georgia,serif;font-size:32px;color:var(--red);font-weight:400}.method-grid h2{font-family:Georgia,serif;font-size:32px;font-weight:400;margin:20px 0 10px}.principles{margin:20px clamp(20px,7vw,110px) 80px;background:var(--black);color:#fff;padding:clamp(30px,5vw,65px)}.principles h2{font-family:Georgia,serif;font-size:45px;font-weight:400}.principles p{max-width:900px;color:#d5d7d5;font-size:18px}.principles div{display:flex;flex-wrap:wrap;gap:20px;margin-top:30px}.principles a{color:#fff}footer{min-height:100px;border-top:1px solid var(--line);padding:28px clamp(20px,5vw,72px);display:flex;align-items:center;justify-content:space-between;gap:20px;color:var(--muted);font-size:12px}@media(max-width:980px){.problem-grid,.method-grid{grid-template-columns:repeat(2,1fr)}.hero-stats{grid-template-columns:repeat(2,1fr)}.dossier-grid{grid-template-columns:1fr 1fr}}@media(max-width:720px){.topbar nav a:not(:first-child){display:none}.lanes,.problem-grid,.dossier-grid,.attempt-detail,.method-grid{grid-template-columns:1fr}.section-heading{align-items:start;flex-direction:column}.hero{padding-top:70px}.hero-stats{grid-template-columns:1fr 1fr}.panel-foot,.card-actions,footer{align-items:flex-start;flex-direction:column}.eyebrow{flex-direction:column;gap:3px}.candidate-alert{align-items:flex-start;flex-direction:column}}
"""


JS = r"""
document.addEventListener('click',e=>{const b=e.target.closest('.filter');if(!b)return;document.querySelectorAll('.filter').forEach(x=>x.classList.remove('active'));b.classList.add('active');const f=b.dataset.filter;document.querySelectorAll('.problem-card').forEach(card=>{card.classList.toggle('hidden',!(f==='all'||card.dataset.lane===f||card.dataset.status===f));});});
"""


def build() -> Path:
    problems = store.load_problems()
    attempts = store.load_attempts()
    runtime = store.runtime()
    reviews = store.read_json(store.DATA / "reviews.json", [])
    if not isinstance(reviews, list):
        reviews = []
    validations = store.read_json(store.DATA / "validations.json", [])
    if not isinstance(validations, list):
        validations = []
    if store.SITE.exists():
        # Keep the mount-point directory itself intact for systemd ReadWritePaths.
        for child in store.SITE.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
    (store.SITE / "assets").mkdir(parents=True, exist_ok=True)
    _write(store.SITE / "assets" / "site.css", CSS)
    _write(store.SITE / "assets" / "site.js", JS)
    _write(store.SITE / "index.html", _index(problems, attempts, runtime))
    by_problem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        by_problem[str(attempt.get("problem_id"))].append(attempt)
    problem_by_id = {row["id"]: row for row in problems}
    for problem in problems:
        _write(store.SITE / "problems" / problem["id"] / "index.html", _problem_page(problem, by_problem[problem["id"]]))
    for attempt in attempts:
        problem = problem_by_id.get(str(attempt.get("problem_id")))
        if problem:
            attempt_reviews = [row for row in reviews if row.get("attempt_id") == attempt.get("id")]
            _write(store.SITE / "attempts" / attempt["id"] / "index.html", _attempt_page(attempt, problem, attempt_reviews))
            if problem.get("publication_attempt_id") == attempt.get("id"):
                _write(store.SITE / "publications" / attempt["id"] / "index.html", _publication_page(problem, attempt, reviews, validations))
    _write(store.SITE / "method" / "index.html", _method_page())
    public_state = {
        "generated_at": store.now_iso(),
        "runtime": runtime,
        "problems": problems,
        "attempts": attempts,
        "reviews": reviews,
        "validations": validations,
    }
    _write(store.SITE / "api" / "state.json", json.dumps(public_state, indent=2, ensure_ascii=False) + "\n")
    _write(store.SITE / "robots.txt", "User-agent: *\nAllow: /\nSitemap: https://proofs.charliekrug.com/sitemap.xml\n")
    urls = ["/", "/method/"] + [f"/problems/{p['id']}/" for p in problems] + [f"/attempts/{a['id']}/" for a in attempts]
    urls += [f"/publications/{p['publication_attempt_id']}/" for p in problems if p.get("publication_attempt_id")]
    _write(store.SITE / "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>https://proofs.charliekrug.com{h(url)}</loc></url>\n" for url in urls) + "</urlset>\n")
    _write(store.SITE / "_headers", "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  Permissions-Policy: camera=(), microphone=(), geolocation=()\n  X-Frame-Options: DENY\n\n/assets/*\n  Cache-Control: public, max-age=3600\n")
    _write(store.SITE / "404.html", _layout("Not found", '<section class="method-head"><h1>That record does not exist.</h1><p><a href="/">Return to the live ledger →</a></p></section>'))
    return store.SITE
