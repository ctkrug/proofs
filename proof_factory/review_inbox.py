from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from proof_factory import cli, config, store


PREFIX = "review-request:"
STATUS_PREFIX = "review-status:"


def validate_request(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("invalid review request schema")
    attempt_id = payload.get("attempt_id")
    if not isinstance(attempt_id, str) or not attempt_id or len(attempt_id) > 200 or not all(
        character.isalnum() or character in "._-" for character in attempt_id
    ):
        raise ValueError("invalid attempt id")
    note = payload.get("note")
    if not isinstance(note, str) or not note.strip() or len(note) > 1000:
        raise ValueError("invalid review note")
    if payload.get("decision") != "accept" or payload.get("reviewer") != "Charlie Krug":
        raise ValueError("unsupported review decision")
    if payload.get("release") is not False or payload.get("source") != "site-ui":
        raise ValueError("invalid review request authority")
    return {"attempt_id": attempt_id, "note": note.strip()}


def already_approved(attempt_id: str) -> bool:
    reviews = store.read_json(store.DATA / "reviews.json", [])
    return isinstance(reviews, list) and any(
        row.get("attempt_id") == attempt_id
        and row.get("decision") == "accept"
        and row.get("reviewer") == "Charlie Krug"
        for row in reviews if isinstance(row, dict)
    )


@dataclass
class KVClient:
    token: str
    account: str
    namespace: str

    @property
    def base(self) -> str:
        return f"https://api.cloudflare.com/client/v4/accounts/{self.account}/storage/kv/namespaces/{self.namespace}"

    def _request(self, path: str, *, method: str = "GET", data: bytes | None = None) -> bytes:
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Cloudflare KV request failed: {exc}") from exc

    def list_requests(self) -> list[str]:
        body = json.loads(self._request(f"/keys?prefix={urllib.parse.quote(PREFIX)}"))
        if not body.get("success"):
            raise RuntimeError("Cloudflare KV key listing failed")
        return [row["name"] for row in body.get("result", []) if isinstance(row, dict) and str(row.get("name", "")).startswith(PREFIX)]

    def get_json(self, key: str) -> Any:
        return json.loads(self._request(f"/values/{urllib.parse.quote(key, safe='')}"))

    def put_json(self, key: str, value: Any) -> None:
        self._request(
            f"/values/{urllib.parse.quote(key, safe='')}?expiration_ttl=604800",
            method="PUT",
            data=json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(),
        )

    def delete(self, key: str) -> None:
        self._request(f"/values/{urllib.parse.quote(key, safe='')}", method="DELETE")


def process(client: KVClient) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for key in client.list_requests():
        attempt_id = key.removeprefix(PREFIX)
        try:
            request = validate_request(client.get_json(key))
            if request["attempt_id"] != attempt_id:
                raise ValueError("request key does not match attempt id")
            if not already_approved(attempt_id):
                cli._review(attempt_id, "accept", request["note"], release=False, reviewer="Charlie Krug")
            status = {"status": "approved", "attempt_id": attempt_id, "reviewed_at": store.now_iso()}
        except ValueError as exc:
            status = {"status": "error", "attempt_id": attempt_id, "message": str(exc)}
        client.put_json(STATUS_PREFIX + attempt_id, status)
        client.delete(key)
        results.append(status)
    return results


def configured_client() -> KVClient:
    token = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID")
    namespace = config.get_text("PROOF_RUNTIME_KV_NAMESPACE_ID", "", allow_empty=True)
    if not token or not account or not namespace:
        raise RuntimeError("Cloudflare review inbox is not configured")
    return KVClient(token, account, namespace)
