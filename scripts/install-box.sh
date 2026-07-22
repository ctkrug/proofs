#!/usr/bin/env bash
set -euo pipefail

PROOF_ROOT="${PROOF_FACTORY_ROOT:-/root/proof-factory}"
cd "$PROOF_ROOT"

# systemd resolves ReadWritePaths before Python can create these runtime directories.
install -d -m 0700 state state/locks
install -d -m 0755 site research data publications
install -d -m 0755 /etc/proof-factory
install -m 0644 deploy/proof-factory.env /etc/proof-factory/proof-factory.env

python3 -m venv .venv
.venv/bin/pip install --disable-pip-version-check -r requirements.txt
./scripts/install-lab-tools.sh
npm ci --no-audit --no-fund
.venv/bin/python -m proof_factory render
git config user.name "ctkrug"
git config user.email "ctkrug4501@gmail.com"

install -m 0644 deploy/proof-factory-hard.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-hard.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-easy.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-easy.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-watchdog.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-watchdog.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-capacity-guard.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-capacity-guard.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-publish.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-publish.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-publish.path /etc/systemd/system/
install -m 0644 deploy/proof-factory-lab.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-lab.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-intake.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-intake.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-scout.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-scout.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-strategy-lab.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-strategy-lab.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-runtime-sync.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-runtime-sync.timer /etc/systemd/system/
install -m 0644 deploy/proof-factory-review-inbox.service /etc/systemd/system/
install -m 0644 deploy/proof-factory-review-inbox.timer /etc/systemd/system/
systemctl daemon-reload

# The deployed portfolio has passed its canaries; enable the bounded production cadences.
systemctl enable --now proof-factory-watchdog.timer
systemctl enable --now proof-factory-capacity-guard.timer
systemctl enable --now proof-factory-easy.timer
systemctl enable --now proof-factory-hard.timer
systemctl enable --now proof-factory-intake.timer
systemctl enable --now proof-factory-scout.timer
systemctl enable --now proof-factory-publish.timer
systemctl enable --now proof-factory-publish.path
systemctl enable --now proof-factory-lab.timer
systemctl enable --now proof-factory-runtime-sync.timer
systemctl enable --now proof-factory-review-inbox.timer
