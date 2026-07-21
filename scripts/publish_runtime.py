#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from proof_factory import config, live, store


def main() -> int:
    token = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID")
    namespace = config.get_text("PROOF_RUNTIME_KV_NAMESPACE_ID", "", allow_empty=True)
    if not token or not account or not namespace:
        print("Cloudflare runtime publishing is not configured", file=sys.stderr)
        return 1

    with store.lock("runtime-publish", nonblocking=True) as acquired:
        if not acquired:
            return 0
        reviews = store.read_json(store.DATA / "reviews.json", [])
        if not isinstance(reviews, list):
            reviews = []
        payload = json.dumps(
            live.snapshot(store.load_problems(), store.load_attempts(), store.runtime(), reviews),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        digest = hashlib.sha256(payload).hexdigest()
        marker = store.STATE / "runtime-publish.sha256"
        if marker.exists() and marker.read_text().strip() == digest:
            return 0

        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{account}/storage/kv/namespaces/{namespace}/values/runtime"
        )
        request = urllib.request.Request(
            url,
            data=payload,
            method="PUT",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"Cloudflare returned HTTP {response.status}")
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            print(f"Runtime snapshot publish failed: {exc}", file=sys.stderr)
            return 1
        marker.write_text(digest + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
