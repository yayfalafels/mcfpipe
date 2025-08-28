#!/usr/bin/env bash
# import_run_tests.sh — runtime: import tests from S3, then run pytest on tests/

set -euo pipefail

# ---- Defaults (can be overridden via env) -----------------------------------
AWS_REGION="${AWS_REGION:-ap-southeast-1}"
S3_BUCKET="${S3_BUCKET:-mcfpipe}"
TESTS_S3_DIR="${TESTS_S3_DIR:-apps/tests}"   # e.g. apps/jobdb/tests/$GITHUB_SHA or any prefix
TESTS_LOCAL_DIR="${TESTS_LOCAL_DIR:-/app/tests}"
TMP_TESTS_DIR="${TMP_TESTS_DIR:-/tmp/tests}"
IMPORT_LOG_FILE="${IMPORT_LOG_FILE:-/var/log/import_tests.log}"
LOGGING_LEVEL="${LOGGING_LEVEL:-INFO}"

# pytest args (optional)
PYTEST_ARGS="${PYTEST_ARGS:--q}"

# ---- Import tests -----------------------------------------------------------
echo "[import_run_tests] importing tests from s3://${S3_BUCKET}/${TESTS_S3_DIR} -> ${TESTS_LOCAL_DIR}"
python /app/import.py \
  --region "${AWS_REGION}" \
  --bucket "${S3_BUCKET}" \
  --s3-dir "${TESTS_S3_DIR}" \
  --tests-dir "${TESTS_LOCAL_DIR}" \
  --tmp-dir "${TMP_TESTS_DIR}" \
  --log-file "${IMPORT_LOG_FILE}" \
  --clean-tmp

# ---- Run tests --------------------------------------------------------------
echo "[import_run_tests] running: pytest ${PYTEST_ARGS} ${TESTS_LOCAL_DIR}"

# keep the old log piping behavior
set -o pipefail
pytest ${PYTEST_ARGS} "${TESTS_LOCAL_DIR}" 2>&1 | tee /var/log/tests.log
