#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "install-lab-tools.sh must run as root" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
  build-essential cmake jq \
  z3 minisat cadical nauty \
  gap pari-gp singular coinor-cbc \
  python3-numpy python3-scipy python3-sympy python3-networkx python3-z3 python3-pulp

for tool in python3 gcc g++ make cmake jq z3 minisat cadical dreadnaut geng gap gp Singular cbc; do
  command -v "$tool" >/dev/null
done

echo "Proof Factory lab toolchain installed and verified."
