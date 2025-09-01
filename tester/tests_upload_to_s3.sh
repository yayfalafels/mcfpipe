#!/usr/bin/env bash
# Upload tests to S3 (zips {app_name}/tests/ if present, else uploads {app_name}/test_.py)
# Emits useful outputs for both local usage and GitHub Actions.
# - tests_s3_dir (prefix ending with /)
# - tests_key     (tests.zip or tests.py)
#
# Usage (local):
#   tester/upload_tests_to_s3.sh \
#     --root {app_name} \
#     --bucket mcfpipe \
#     --prefix-base apps/tests/{app_name} \
#
# Usage (GitHub Actions step):
#   run: |
#     bash tester/upload_tests_to_s3.sh \
#     --root {app_name} \
#       --bucket "${S3_BUCKET}" \
#       --prefix-base "${TESTS_PREFIX_BASE}" \
#
set -euo pipefail

ROOT=""
BUCKET=""
PREFIX_BASE=""
QUIET=0

usage() {
  cat <<EOF
Upload tests to S3. If <ROOT>/tests/ exists, zips it to tests.zip; else uses <ROOT>/test.py.

Required:
  --root PATH             # repo-relative path holding tests (e.g., tester)
  --bucket NAME           # S3 bucket name (e.g., mcfpipe)
  --prefix-base PREFIX    # S3 prefix base w/o leading slash (e.g., apps/tests/jobdb)
  --quiet                 # suppress non-essential output
  -h | --help

Outputs:
  tests_s3_dir   -> s3 prefix (ends in /), versioned by short SHA
  tests_key      -> tests.zip or test_.py

If running in GitHub Actions, the script writes to \$GITHUB_OUTPUT automatically.
EOF
}

# ---------- parse args ----------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --bucket) BUCKET="$2"; shift 2 ;;
    --prefix-base) PREFIX_BASE="$2"; shift 2 ;;
    --quiet) QUIET=1; shift 1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

[[ -z "$ROOT" ]] || [[ -z "$BUCKET" ]] || [[ -z "$PREFIX_BASE" ]] && { usage; exit 2; }

# ---------- deps ----------
command -v aws >/dev/null || { echo "aws CLI not found" >&2; exit 127; }
command -v zip >/dev/null || { echo "zip not found (apt-get install -y zip)" >&2; exit 127; }

# ---------- normalize ----------
# no leading slash in prefix base; single trailing slash handled later
PREFIX_BASE="${PREFIX_BASE#/}"            # strip leading /
PREFIX_BASE="${PREFIX_BASE%/}"            # strip trailing /

ZIP_FILE_NAME=tests.zip
SINGLE_FILE_NAME=test_.py
TESTS_DIR="${ROOT%/}/tests"
SINGLE_FILE="${ROOT%/}/${SINGLE_FILE_NAME}"
STAGING_DIR="$(mktemp -d -t tests-upload.XXXXXX)"

# Final prefix: apps/jobdb/tests/
TESTS_S3_DIR="${PREFIX_BASE}/"

# ---------- package ----------
UPLOAD_SRC=""
TESTS_KEY=""
if [[ -d "$TESTS_DIR" ]]; then
  (( QUIET == 0 )) && echo "Found tests directory: ${TESTS_DIR} (zipping contents)"
  # zip the CONTENTS of tests/ so unzip lands files directly under /tests
  ( cd "${TESTS_DIR}" && zip -qr "${STAGING_DIR}/${ZIP_FILE_NAME}" . )
  UPLOAD_SRC="${STAGING_DIR}/${ZIP_FILE_NAME}"
  TESTS_KEY="${ZIP_FILE_NAME}"
  : "${CONTENT_TYPE:=application/zip}"
else
  # fallback single-file search
  for CAND in "tests.py" "test_.py"; do
    if [[ -f "${ROOT%/}/${CAND}" ]]; then
      (( QUIET == 0 )) && echo "Found single tests file: ${ROOT%/}/${CAND}"
      UPLOAD_SRC="${ROOT%/}/${CAND}"
      TESTS_KEY="${CAND}"
      : "${CONTENT_TYPE:=text/x-python}"
      break
    fi
  done
  if [[ -z "$UPLOAD_SRC" ]]; then
    echo "ERROR: No tests found in '${TESTS_DIR}' or '${ROOT%/}/tests.py|test_.py'." >&2
    exit 2
  fi
fi

# ---------- upload ----------
S3_URI="s3://${BUCKET}/${TESTS_S3_DIR}${TESTS_KEY}"
(( QUIET == 0 )) && echo "Uploading ${UPLOAD_SRC} -> ${S3_URI}"
aws s3 cp "${UPLOAD_SRC}" "${S3_URI}"

# ---------- outputs ----------
# 1) Print for humans
(( QUIET == 0 )) && cat <<OUT
Uploaded tests:
  tests_s3_dir: ${TESTS_S3_DIR}
  tests_key    : ${TESTS_KEY}
OUT

# 2) Export for shells (source-able)
echo "TESTS_S3_DIR=${TESTS_S3_DIR}"
echo "TESTS_KEY=${TESTS_KEY}"

# 3) GitHub Actions step outputs (if available)
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    echo "tests_s3_dir=${TESTS_S3_DIR}"
    echo "tests_key=${TESTS_KEY}"
  } >> "$GITHUB_OUTPUT"
fi

# 4) Clean up
rm -rf "$STAGING_DIR"
