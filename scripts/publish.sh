#!/usr/bin/env bash
set -euo pipefail

PROOF_ROOT="${PROOF_FACTORY_ROOT:-/root/proof-factory}"
cd "$PROOF_ROOT"

# Charlie owns every commit. Automation assists and discloses itself in the
# research records, but never uses a synthetic Git author or committer identity.
git config user.name "ctkrug"
git config user.email "ctkrug4501@gmail.com"

export CLOUDFLARE_API_TOKEN="${CLOUDFLARE_API_TOKEN:-${CF_API_TOKEN:-}}"
export CLOUDFLARE_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-${CF_ACCOUNT_ID:-}}"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" || -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  echo "Cloudflare credentials are not configured" >&2
  exit 1
fi

# Laptop evolution lab (proof-lab-local) publishes into data/local_lab/ via git.
# Default-off: this box only pulls those results when the flag file exists.
if [[ -f "$PROOF_ROOT/state/local-lab-pull.enabled" ]]; then
  if git pull --rebase --autostash origin main; then
    .venv/bin/python -m proof_factory render || echo "Warning: post-pull render failed" >&2
  else
    echo "Warning: local-lab pull failed; publishing existing state" >&2
    git rebase --abort 2>/dev/null || true
  fi
fi

# Research services create local commits without credentials. Only this publisher
# may provision and push the public per-problem GitHub repositories.
if ! .venv/bin/python -m proof_factory repo-sync; then
  echo "Warning: one or more public problem repositories did not sync" >&2
fi

git add data publications
if ! git diff --cached --quiet; then
  git commit -m "Record automated research attempt"
  if ! git push origin main; then
    echo "Warning: public ledger deployed, but GitHub state sync failed" >&2
  fi
fi

./node_modules/.bin/wrangler pages deploy site --project-name=proofs --commit-dirty=true
