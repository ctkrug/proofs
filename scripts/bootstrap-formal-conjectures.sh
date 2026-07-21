#!/usr/bin/env bash
# Provision a project-scoped Formal Conjectures checkout for local Lean verification.
# Nothing here modifies a shell profile or requires root access.
set -euo pipefail

if [[ $# -ne 0 ]]; then
  echo "usage: $0" >&2
  exit 64
fi

for required in awk curl git mkdir mktemp sha256sum; do
  command -v "$required" >/dev/null || {
    echo "missing required command: $required" >&2
    exit 69
  }
done

cache_root="${PROOF_FACTORY_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/proof-factory}"
elan_home="${ELAN_HOME:-$cache_root/lean/elan}"
checkout="$cache_root/formal-conjectures"
lock_dir="$cache_root/locks/formal-conjectures-bootstrap.lock"
revision="${PROOF_FACTORY_FORMAL_CONJECTURES_REVISION:-b8b5208aa5d01f5f91c49ca516bf09cae8d93693}"
manifest_sha256="${PROOF_FACTORY_FORMAL_CONJECTURES_MANIFEST_SHA256:-5b99b5f4f807cbba67bbcd22e5e486c17d6a8d970ea218de08d05830ab350c26}"
mkdir -p "$cache_root/locks"


# `mkdir` is atomic on macOS and Linux. Serializing avoids competing hydration/build
# processes corrupting the shared package checkout.
lock_acquired=false
for _ in $(seq 1 600); do
  if mkdir "$lock_dir" 2>/dev/null; then
    printf '%s\n' "$$" > "$lock_dir/pid"
    lock_acquired=true
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
if [[ "$lock_acquired" != true ]]; then
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
  # A first clone plus Mathlib hydrate can consume several GiB. Fail before
  # downloading if the cache filesystem cannot absorb it. An already-hydrated
  # checkout remains usable under the normal, much smaller reserve.
  min_free_kib="${PROOF_FACTORY_LEAN_BOOTSTRAP_MIN_FREE_KIB:-8388608}" # 8 GiB
  available_kib="$(df -Pk "$cache_root" | awk 'NR == 2 { print $4 }')"
  if [[ ! "$available_kib" =~ ^[0-9]+$ ]] || (( available_kib < min_free_kib )); then
    echo "formal-conjectures first hydrate needs $((${min_free_kib} / 1024 / 1024)) GiB free in $cache_root; only ${available_kib:-0} KiB available" >&2
    exit 75
  fi
  git clone --depth 1 https://github.com/google-deepmind/formal-conjectures.git "$checkout"
  git -C "$checkout" fetch --depth 1 origin "$revision"
  git -C "$checkout" checkout --detach "$revision"
fi

cd "$checkout"
if [[ "$(git rev-parse HEAD)" != "$revision" ]]; then
  echo "formal-conjectures checkout is not at the pinned revision $revision" >&2
  exit 65
fi
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "formal-conjectures checkout has tracked changes; refusing a non-reproducible build" >&2
  exit 65
fi
if [[ ! -f lake-manifest.json ]]; then
  echo "pinned formal-conjectures checkout is missing lake-manifest.json" >&2
  exit 66
fi
actual_manifest_sha256="$(sha256sum lake-manifest.json | awk '{print $1}')"
if [[ "$actual_manifest_sha256" != "$manifest_sha256" ]]; then
  echo "formal-conjectures manifest hash mismatch" >&2
  exit 66
fi
if [[ ! -d "$checkout/.lake/packages/mathlib/.lake/build" ]]; then
  min_free_kib="${PROOF_FACTORY_LEAN_BOOTSTRAP_MIN_FREE_KIB:-8388608}" # 8 GiB
  available_kib="$(df -Pk "$cache_root" | awk 'NR == 2 { print $4 }')"
  if [[ ! "$available_kib" =~ ^[0-9]+$ ]] || (( available_kib < min_free_kib )); then
    echo "formal-conjectures Mathlib build cache needs $((${min_free_kib} / 1024 / 1024)) GiB free in $cache_root; only ${available_kib:-0} KiB available" >&2
    exit 75
  fi
  ELAN_HOME="$elan_home" "$elan_home/bin/lake" exe cache get
fi
# Build the imported support library once. Candidate module builds then have all local imports.
LEAN_NUM_THREADS="${LEAN_NUM_THREADS:-1}" ELAN_HOME="$elan_home" \
  "$elan_home/bin/lake" build FormalConjecturesUtil

olean="$checkout/.lake/build/lib/lean/FormalConjecturesUtil.olean"
if [[ ! -s "$olean" ]]; then
  echo "FormalConjecturesUtil.olean was not produced" >&2
  exit 70
fi
if [[ "$(git rev-parse HEAD)" != "$revision" ]] || \
    [[ "$(sha256sum lake-manifest.json | awk '{print $1}')" != "$manifest_sha256" ]] || \
    [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "formal-conjectures immutable inputs changed during bootstrap" >&2
  exit 70
fi

printf '%s\n' "$checkout"
