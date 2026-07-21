"""Small, dependency-free HTML templates with escaping enabled by default.

``string.Template`` deliberately has no HTML policy of its own.  Keeping the
escaping boundary here makes the safe behavior difficult to bypass by
accident: every ordinary substitution is escaped, while already-rendered
fragments must be marked explicitly with :func:`html_fragment`.
"""

from __future__ import annotations

import html
from string import Template
from typing import Any


class HTMLFragment(str):
    """HTML assembled by another escaping template or a constant."""


def html_fragment(value: str) -> HTMLFragment:
    """Mark a reviewed or previously escaped string as safe HTML."""

    return HTMLFragment(value)


def render(template: Template, /, **values: Any) -> str:
    """Render *template*, HTML-escaping every substitution by default."""

    escaped = {
        key: str(value) if isinstance(value, HTMLFragment) else html.escape(str(value if value is not None else ""), quote=True)
        for key, value in values.items()
    }
    return template.substitute(escaped)


LAYOUT = Template(r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#f4f1e8">
  <title>$title · Proof Factory</title>
  <meta name="description" content="$description">
  <link rel="stylesheet" href="/assets/site-v4.css">
  <script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{"token":"153bb72472fb49d8863fb2f8f08f6b2b"}'></script>
  <script>MathJax={tex:{inlineMath:[['$$','$$'],['\\(','\\)']]}};</script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
  <script defer src="/assets/site-v4.js"></script>
</head>
<body>
  <a class="skip-link" href="#content">Skip to content</a>
  <header class="topbar">
    <a class="brand" href="/"><span class="brand-mark">PF</span><span>Proof Factory</span><small>Open mathematics research</small></a>
    <nav aria-label="Primary"><a href="/#operations">Status</a><a href="/#ongoing">Work</a><a href="/#runs">Runs</a><a href="/about/">About</a></nav>
  </header>
  <main id="content">$body</main>
  <footer><span>Proof Factory / AI-assisted mathematics research</span><span>Seeking useful contributions, small or large</span><span>UTC · <a href="https://github.com/ctkrug/proofs">Source</a></span></footer>
</body>
</html>""")


BRAIN_PAGE = Template("""
<section class="method-head"><span class="overline">Generated research wiki</span><h1>Problems remember.<br><em>Ideas connect.</em></h1>
<p>This graph is rebuilt from the canonical problem registry, per-problem research maps, append-only attempts, and strategy library. Links propose transfers; they never serve as mathematical evidence.</p>
<div class="source-line"><a href="/api/brain.json">Download graph JSON ↗</a><span>$node_count nodes · $edge_count edges · $concept_count concepts</span></div></section>
<section class="strategy-library">$cards</section>
""")


BRAIN_CARD = Template("""
<article id="problem-$problem_id"><span class="overline">$baseline_status baseline · $lane</span>
<h2><a href="$url">$label</a></h2><p>$summary</p>
<p><strong>Concepts:</strong> $concepts</p>
<p><strong>Linked problems:</strong></p><ul>$links</ul></article>""")


BRAIN_LINK = Template("""<li><a href="/problems/$problem_id/">$label</a><br>$concepts</li>""")

