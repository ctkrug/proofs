from __future__ import annotations

import unittest
from string import Template

from proof_factory import render
from proof_factory.html_templates import HTMLFragment, html_fragment, render as render_template


class HTMLTemplateTests(unittest.TestCase):
    def test_substitutions_escape_by_default_and_fragments_are_explicit(self) -> None:
        template = Template('<h1 title="$title">$title</h1><main>$body</main>')

        output = render_template(
            template,
            title='"><script>alert(1)</script>',
            body=html_fragment("<p>reviewed</p>"),
        )

        self.assertNotIn("<script>", output)
        self.assertIn("&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;", output)
        self.assertIn("<main><p>reviewed</p></main>", output)
        self.assertIsInstance(html_fragment("<b>x</b>"), HTMLFragment)

    def test_layout_escapes_metadata_but_preserves_rendered_body(self) -> None:
        output = render._layout(
            'Title <img src=x onerror="bad">',
            "<section>safe fragment</section>",
            description='description"><script>bad()</script>',
        )

        self.assertIn("<main id=\"content\"><section>safe fragment</section></main>", output)
        self.assertNotIn("<img src=x", output)
        self.assertNotIn("<script>bad()", output)
        self.assertIn("Title &lt;img src=x onerror=&quot;bad&quot;&gt;", output)
        self.assertIn("description&quot;&gt;&lt;script&gt;bad()&lt;/script&gt;", output)
        self.assertIn("inlineMath:[['$','$']", output)

    def test_brain_page_smoke_and_untrusted_graph_values_are_escaped(self) -> None:
        graph = {
            "nodes": [
                {
                    "id": "problem:unsafe",
                    "type": "problem",
                    "problem_id": 'unsafe\"><script>problem()</script>',
                    "baseline_status": "complete<script>status()</script>",
                    "lane": "easy",
                    "url": '/problems/unsafe/\" onmouseover=\"url()',
                    "label": "Unsafe <img src=x onerror=label()>",
                    "summary": "Summary <script>summary()</script>",
                },
                {
                    "id": "concept:unsafe",
                    "type": "concept",
                    "problem_id": 'target\"><script>target()</script>',
                    "label": "Target <script>label()</script>",
                },
            ],
            "edges": [
                {
                    "source": "problem:unsafe",
                    "target": "concept:unsafe",
                    "relation": "shares_concepts",
                    "concepts": ["graph<script>concept()</script>"],
                },
                {
                    "source": "problem:unsafe",
                    "target": "concept:unsafe",
                    "relation": "uses_concept",
                },
            ],
        }

        output = render._brain_page(graph)

        self.assertIn("Research brain · Proof Factory", output)
        self.assertIn("2 nodes · 2 edges · 1 concepts", output)
        self.assertIn("Unsafe &lt;img src=x onerror=label()&gt;", output)
        self.assertIn("Summary &lt;script&gt;summary()&lt;/script&gt;", output)
        self.assertIn("graph&lt;script&gt;concept()&lt;/script&gt;", output)
        self.assertNotIn("<script>summary()", output)
        self.assertNotIn("<script>concept()", output)

    def test_about_page_explains_the_engine_and_its_claim_gates(self) -> None:
        output = render._about_page()

        self.assertIn("One evidence loop", output)
        self.assertIn("How a pass thinks", output)
        self.assertIn("What the engine remembers", output)
        self.assertIn("Six roles, separate powers", output)
        self.assertIn("The publication firewall", output)
        self.assertIn('aria-label="Proof Factory process"', output)
        self.assertIn('id="memory"', output)
        self.assertIn("How it works · Proof Factory", output)

    def test_single_candidate_review_link_opens_its_record(self) -> None:
        href = render._candidate_review_href([{"id": "candidate-one"}])

        self.assertEqual(href, "/problems/candidate-one/")

    def test_multiple_candidate_review_link_targets_existing_section(self) -> None:
        href = render._candidate_review_href([{"id": "candidate-one"}, {"id": "candidate-two"}])

        self.assertEqual(href, "#ongoing")

    def test_problem_page_links_external_submission(self) -> None:
        output = render._problem_page(
            {
                "id": "candidate-one", "title": "Candidate", "status": "published",
                "external_validation_state": "submitted",
                "external_validation_url": "https://example.test/pull/18",
            },
            [],
            {"strategies": [], "ruled_out": [], "open_leads": []},
            [],
        )

        self.assertIn('href="https://example.test/pull/18"', output)
        self.assertIn("submitted ↗", output)

    def test_candidate_problem_has_password_gated_review_form(self) -> None:
        output = render._problem_page(
            {
                "id": "candidate-one", "title": "Candidate", "status": "candidate",
                "candidate_attempt_id": "attempt-safe-1",
            },
            [],
            {"strategies": [], "ruled_out": [], "open_leads": []},
            [],
        )

        self.assertIn('data-candidate-review', output)
        self.assertIn('data-attempt-id="attempt-safe-1"', output)
        self.assertIn('type="password"', output)
        self.assertIn("Approval records your human review", output)

    def test_verified_problem_has_no_review_form(self) -> None:
        output = render._problem_page(
            {"id": "verified-one", "title": "Verified", "status": "verified"},
            [], {"strategies": [], "ruled_out": [], "open_leads": []}, [],
        )

        self.assertNotIn('data-candidate-review', output)


if __name__ == "__main__":
    unittest.main()
