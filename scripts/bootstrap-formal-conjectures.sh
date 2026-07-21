#!/usr/bin/env bash
# Provision a project-scoped Formal Conjectures checkout for local Lean verification.
# Nothing here modifies a shell profile or requires root access.
set -euo pipefail

if [[ $# -ne 0 ]]; then
  echo "usage: $0" >&2
  exit 64
fi

for required in curl git mkdir mktemp; do
  command -v "$required" >/dev/null || {
    echo "missing required command: $required" >&2
    exit 69
  }
done

cache_root="${PROOF_FACTORY_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/proof-factory}"
elan_home="${ELAN_HOME:-$cache_root/lean/elan}"
checkout="$cache_root/formal-conjectures"
lock_dir="$cache_root/locks/formal-conjectures-bootstrap.lock"
mkdir -p "$cache_root/locks"

# A first Mathlib cache hydrate can consume several GiB.  Fail before any
# download if the cache filesystem cannot absorb it; the scheduler can keep
# normal research work running instead of letting this bootstrap fill a disk.
min_free_kib="${PROOF_FACTORY_LEAN_BOOTSTRAP_MIN_FREE_KIB:-8388608}" # 8 GiB
available_kib="$(df -Pk "$cache_root" | awk 'NR == 2 { print $4 }')"
if [[ ! "$available_kib" =~ ^[0-9]+$ ]] || (( available_kib < min_free_kib )); then
  echo "formal-conjectures bootstrap needs $((${min_free_kib} / 1024 / 1024)) GiB free in $cache_root; only ${available_kib:-0} KiB available" >&2
  exit 75
fi

# `mkdir` is atomic on macOS and Linux. Serializing avoids competing `lake update`
# processes corrupting a temporary package checkout.
for _ in $(seq 1 600); do
  if mkdir "$lock_dir" 2>/dev/null; then
    printf '%s\n' "$$" > "$lock_dir/pid"
    break
  fi
  if [[ -r "$lock_dir/pid" ]]; then
    read -r owner_pid < "$lock_dir/pid" || owner_pid=""
    if [[ "$owner_pid" =~ ^[0-9]+$ ]] && ! kill -0 "$owner_pid" 2>/dev/null; then
      rm -f "$lock_dir/pid"
      rmdir "$lock_dir" 2>/dev/null || true
      continue
    fi
  fi
  sleep 1
done
if [[ ! -d "$lock_dir" ]]; then
  echo "timed out waiting for Formal Conjectures bootstrap lock" >&2
  exit 75
fi
cleanup() {
  rm -f "$lock_dir/pid"
  rmdir "$lock_dir" 2>/dev/null || true
}
trap cleanup EXIT

if [[ ! -x "$elan_home/bin/lake" ]]; then
  installer="$(mktemp "$cache_root/elan-init.XXXXXX")"
  trap 'rm -f "$installer"; cleanup' EXIT
  curl --fail --location --silent --show-error \
    https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
    --output "$installer"
  ELAN_HOME="$elan_home" sh "$installer" -y --no-modify-path --default-toolchain none
  rm -f "$installer"
fi

if [[ ! -d "$checkout/.git" ]]; then
  git clone --depth 1 https://github.com/google-deepmind/formal-conjectures.git "$checkout"
fi

cd "$checkout"
ELAN_HOME="$elan_home" "$elan_home/bin/lake" update
ELAN_HOME="$elan_home" "$elan_home/bin/lake" exe cache get
# Build the imported support library once. Candidate module builds then have all local imports.
LEAN_NUM_THREADS="${LEAN_NUM_THREADS:-1}" ELAN_HOME="$elan_home" \
  "$elan_home/bin/lake" build FormalConjecturesUtil

printf '%s\n' "$checkout"
