#!/usr/bin/env bash
set -euo pipefail

PROOF_ROOT="${PROOF_FACTORY_ROOT:-/root/proof-factory}"
cd "$PROOF_ROOT"

# systemd resolves ReadWritePaths before Python can create these runtime directories.
install -d -m 0700 state state/locks
install -d -m 0755 site research data

python3 -m venv .venv
.venv/bin/pip install --disable-pip-version-check -r requirements.txt
npm ci --no-audit --no-fund
.venv/bin/python -m proof_factory render

install -m 0644 deploy/proof-factory-hard.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-hard.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-easy.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-easy.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-watchdog.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-watchdog.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-publish.service /etc/systemd/system/
systemctl daemon-reload

# Safe bring-up: render/watchdog may run; research timers are enabled only after a real canary.
systemctl enable --now proof-factory-watchdog.timer
