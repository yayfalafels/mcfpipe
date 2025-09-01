#!/usr/bin/env bash
# Compute a safe git diff range for GitHub Actions and emit:
#   base=<sha>
#   ref=<sha>
# to $GITHUB_OUTPUT so downstream steps (e.g., paths-filter) can consume them.
#
# Works for: pull_request, push, workflow_dispatch, re-runs, new branches.
# Assumes you've already done "actions/checkout@v4" (ideally with fetch-depth: 0).

set -euo pipefail

# Inputs expected via env (provide from workflow using ${{ github.* }})
EVENT_NAME="${EVENT_NAME:-}"
PR_BASE_SHA="${PR_BASE_SHA:-}"
PR_HEAD_SHA="${PR_HEAD_SHA:-}"
PUSH_BEFORE_SHA="${PUSH_BEFORE_SHA:-}"
GITHUB_SHA_IN="${GITHUB_SHA_IN:-}"
REF_NAME="${REF_NAME:-}"

# Helper: write output (both for logs and GHA)
emit_output() {
  local k="$1" v="$2"
  echo "${k}=${v}"
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "${k}=${v}" >> "$GITHUB_OUTPUT"
  fi
}

echo "[compute_diff_range] event=${EVENT_NAME} ref_name=${REF_NAME:-?} sha=${GITHUB_SHA_IN}"

# Ensure we have enough history locally for HEAD~1 detection on dispatch/others
# (safe even if already fetched deeply)
git fetch --prune --no-tags origin +refs/heads/*:refs/remotes/origin/* >/dev/null 2>&1 || true

case "$EVENT_NAME" in
  pull_request)
    # Full PR delta: base -> head
    if [[ -z "$PR_BASE_SHA" || -z "$PR_HEAD_SHA" ]]; then
      echo "[compute_diff_range] ERROR: PR_BASE_SHA/PR_HEAD_SHA not provided" >&2
      exit 2
    fi
    BASE="$PR_BASE_SHA"
    REF="$PR_HEAD_SHA"
    ;;

  push)
    # GitHub provides previous commit in PUSH_BEFORE_SHA
    if [[ -z "$GITHUB_SHA_IN" ]]; then
      echo "[compute_diff_range] ERROR: GITHUB_SHA_IN missing" >&2
      exit 2
    fi
    if [[ "${PUSH_BEFORE_SHA:-}" != "0000000000000000000000000000000000000000" && -n "${PUSH_BEFORE_SHA:-}" ]]; then
      BASE="$PUSH_BEFORE_SHA"
    else
      # New branch (no before): compare against the empty tree so all files count as added
      BASE="$(git hash-object -t tree /dev/null)"
    fi
    REF="$GITHUB_SHA_IN"
    ;;

  *)
    # workflow_dispatch / schedule / re-run / other events:
    # Try previous local commit; if none, fall back to HEAD (no-op unless you change it)
    if git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
      BASE="$(git rev-parse HEAD~1)"
    else
      BASE="$GITHUB_SHA_IN"
    fi
    REF="$GITHUB_SHA_IN"
    ;;
esac

echo "[compute_diff_range] base=${BASE}"
echo "[compute_diff_range] ref =${REF}"

emit_output base "$BASE"
emit_output ref  "$REF"
