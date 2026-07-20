#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 ATTEMPT_ID REVIEW_NOTE" >&2
  exit 2
fi

PROOF_ROOT="${PROOF_FACTORY_ROOT:-/root/proof-factory}"
cd "$PROOF_ROOT"

.venv/bin/python -m proof_factory review \
  --attempt "$1" \
  --decision accept \
  --note "$2" \
  --release

# The publisher owns deployment credentials; the research and review processes do not.
systemctl start proof-factory-publish.service
