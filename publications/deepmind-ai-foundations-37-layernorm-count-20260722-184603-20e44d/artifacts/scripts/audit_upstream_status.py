#!/usr/bin/env python3
"""Fail-closed live-status audit for DeepMind ai-foundations issue #37."""

import hashlib
import json
import subprocess
import sys
import urllib.parse
import urllib.request


REPOSITORY = "google-deepmind/ai-foundations"
REMOTE = f"https://github.com/{REPOSITORY}.git"
ISSUE_URL = f"https://api.github.com/repos/{REPOSITORY}/issues/37"
SEARCH_QUERIES = (
    f"repo:{REPOSITORY} is:pr 37 in:title,body",
    f"repo:{REPOSITORY} is:pr parameter_count_layer_norm",
)


def fetch_json(url: str) -> tuple[dict, str]:
  request = urllib.request.Request(
      url,
      headers={
          "Accept": "application/vnd.github+json",
          "User-Agent": "proof-factory-issue-37-status-audit",
          "X-GitHub-Api-Version": "2022-11-28",
      },
  )
  with urllib.request.urlopen(request, timeout=30) as response:
    body = response.read()
  return json.loads(body), hashlib.sha256(body).hexdigest()


def main() -> int:
  remote = subprocess.run(
      ["git", "ls-remote", REMOTE, "refs/heads/main"],
      check=True,
      capture_output=True,
      text=True,
  ).stdout.strip()
  fields = remote.split()
  if len(fields) != 2 or fields[1] != "refs/heads/main":
    raise AssertionError(f"unexpected ls-remote output: {remote!r}")

  issue, issue_sha256 = fetch_json(ISSUE_URL)
  searches = []
  for query in SEARCH_QUERIES:
    url = "https://api.github.com/search/issues?" + urllib.parse.urlencode({"q": query})
    result, response_sha256 = fetch_json(url)
    searches.append(
        {
            "query": query,
            "url": url,
            "total_count": result["total_count"],
            "response_sha256": response_sha256,
            "matches": [
                {"number": item["number"], "state": item["state"], "url": item["html_url"]}
                for item in result["items"]
            ],
        }
    )

  report = {
      "repository": f"https://github.com/{REPOSITORY}",
      "main_commit": fields[0],
      "issue": {
          "url": issue["html_url"],
          "state": issue["state"],
          "title": issue["title"],
          "comments": issue["comments"],
          "updated_at": issue["updated_at"],
          "response_sha256": issue_sha256,
      },
      "pull_request_searches": searches,
  }
  print(json.dumps(report, indent=2, sort_keys=True))

  if issue["state"] != "open":
    print("STOP: issue #37 is no longer open", file=sys.stderr)
    return 1
  if any(search["total_count"] != 0 for search in searches):
    print("STOP: a potentially matching pull request exists", file=sys.stderr)
    return 1
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
