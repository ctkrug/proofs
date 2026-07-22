from __future__ import annotations

import unittest
from unittest import mock

from proof_factory import review_inbox


class FakeClient:
    def __init__(self, values: dict[str, object]) -> None:
        self.values = values

    def list_requests(self) -> list[str]:
        return [key for key in self.values if key.startswith(review_inbox.PREFIX)]

    def get_json(self, key: str) -> object:
        return self.values[key]

    def put_json(self, key: str, value: object) -> None:
        self.values[key] = value

    def delete(self, key: str) -> None:
        del self.values[key]


def request(attempt_id: str = "candidate-1") -> dict[str, object]:
    return {
        "schema_version": 1, "attempt_id": attempt_id, "decision": "accept",
        "note": "I reviewed the evidence.", "reviewer": "Charlie Krug",
        "release": False, "source": "site-ui",
    }


class ReviewInboxTests(unittest.TestCase):
    def test_validate_request_fails_closed(self) -> None:
        payload = request()
        payload["release"] = True
        with self.assertRaisesRegex(ValueError, "authority"):
            review_inbox.validate_request(payload)

    def test_process_uses_authoritative_review_and_clears_request(self) -> None:
        key = review_inbox.PREFIX + "candidate-1"
        client = FakeClient({key: request()})
        with mock.patch.object(review_inbox, "already_approved", return_value=False), mock.patch.object(review_inbox.cli, "_review") as approve:
            results = review_inbox.process(client)

        approve.assert_called_once_with("candidate-1", "accept", "I reviewed the evidence.", release=False, reviewer="Charlie Krug")
        self.assertNotIn(key, client.values)
        self.assertEqual(results[0]["status"], "approved")

    def test_process_is_idempotent_for_existing_approval(self) -> None:
        key = review_inbox.PREFIX + "candidate-1"
        client = FakeClient({key: request()})
        with mock.patch.object(review_inbox, "already_approved", return_value=True), mock.patch.object(review_inbox.cli, "_review") as approve:
            review_inbox.process(client)

        approve.assert_not_called()
        self.assertEqual(client.values[review_inbox.STATUS_PREFIX + "candidate-1"]["status"], "approved")


if __name__ == "__main__":
    unittest.main()
