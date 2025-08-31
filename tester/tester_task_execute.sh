#!/usr/bin/env bash
# tester_task_execute.sh
# Run the ECS tester task, inject DB_API_URL + importer/env vars, and on failure print CloudWatch Logs.

set -euo pipefail

### --- CONFIG (override via env or flags) -------------------------------------
AWS_REGION="${AWS_REGION:-ap-southeast-1}"
CLUSTER="${CLUSTER:-mcfpipe}"
TASK_DEF="${TASK_DEF:-mcfpipe-tester}"
SUBNETS_CSV="${SUBNETS_CSV:-subnet-abc123,subnet-*}"     # comma-separated
SECURITY_GROUPS_CSV="${SECURITY_GROUPS_CSV:-sg-*}"       # comma-separated
ASSIGN_PUBLIC_IP="${ASSIGN_PUBLIC_IP:-DISABLED}"         # ENABLED|DISABLED
VPCE_ID="${VPCE_ID:-}"                                   # API GW VPC endpoint id (if private)
DB_API_ID="${DB_API_ID:-}"                               # API GW id (rest api id)
DEV_ENV="${DEV_ENV:-dev}"                                # stage name
STAGE_NAME="$DEV_ENV"
REGION="$AWS_REGION"                                     # for consistency below

# CloudWatch Logs (should match your task def log config)
LOG_GROUP="${LOG_GROUP:-/mcfpipe/tester}"
STREAM_PREFIX="${STREAM_PREFIX:-ecs}"            # must match awslogs-stream-prefix in task def
CONTAINER_NAME="${CONTAINER_NAME:-tester}"       # containerDefinitions[].name
TAG_ROLE="${TAG_ROLE:-Bridges}"                  # tag: role
TAG_PROJECT_NAME="${TAG_PROJECT_NAME:-mcfpipe}"  # tag: project

# ---- App/Test env injected into container -----------------------------------
# DB endpoint (allow explicit --db-url to override)
DB_API_URL_DEFAULT="https://${DB_API_ID}-${VPCE_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}"
DB_API_URL="${DB_API_URL:-$DB_API_URL_DEFAULT}"

# Importer/env for import.py -> tests/
S3_BUCKET="${S3_BUCKET:-mcfpipe}"
TESTS_S3_DIR="${TESTS_S3_DIR:-apps/tests}"            # e.g., apps/jobdb/tests/$GITHUB_SHA
IMPORT_LOG_FILE="${IMPORT_LOG_FILE:-/var/log/import_tests.log}"
LOGGING_LEVEL="${LOGGING_LEVEL:-INFO}"

# Pytest verbosity / selection (container uses: pytest ${PYTEST_ARGS} ${TESTS_LOCAL_DIR})
PYTEST_ARGS="${PYTEST_ARGS:--q}"

# Optional: override container command (JSON array), e.g.:
# CMD_OVERRIDE_JSON='["sh","-lc","/app/import_run_tests.sh"]'
CMD_OVERRIDE_JSON="${CMD_OVERRIDE_JSON:-}"

### --- USAGE ------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $(basename "$0") [--db-url URL]

Env overrides (commonly set by GHA):
  AWS_REGION, CLUSTER, TASK_DEF, SUBNETS_CSV, SECURITY_GROUPS_CSV, ASSIGN_PUBLIC_IP
  VPCE_ID, DB_API_ID, DEV_ENV
  LOG_GROUP, STREAM_PREFIX, CONTAINER_NAME
  S3_BUCKET, TESTS_S3_DIR, LOGGING_LEVEL, PYTEST_ARGS
  CMD_OVERRIDE_JSON  (optional JSON array to override container command)

Examples:
  GITHUB_SHA=\$(git rev-parse --short HEAD)
  TESTS_S3_DIR="apps/jobdb/tests/\$GITHUB_SHA" \\
  DB_API_URL="https://abc123-vpce-xyz.execute-api.${REGION}.amazonaws.com/prod" \\
  SUBNETS_CSV="subnet-1,subnet-2" SECURITY_GROUPS_CSV="sg-1" \\
  $(basename "$0")
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db-url) DB_API_URL="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

[[ -z "$DB_API_URL" ]] && { echo "ERROR: DB_API_URL is required (env or --db-url)."; exit 2; }

# deps
command -v aws >/dev/null 2>&1 || { echo "aws CLI not found"; exit 127; }
command -v jq  >/dev/null 2>&1 || { echo "jq not found"; exit 127; }

echo "Cluster         : $CLUSTER"
echo "TaskDef         : $TASK_DEF"
echo "Region          : $REGION"
echo "DB_API_URL      : $DB_API_URL"
echo "S3_BUCKET       : $S3_BUCKET"
echo "TESTS_S3_DIR    : $TESTS_S3_DIR"
echo "LOGGING_LEVEL   : $LOGGING_LEVEL"
echo "PYTEST_ARGS     : $PYTEST_ARGS"
[[ -n "$CMD_OVERRIDE_JSON" ]] && echo "CMD override    : $CMD_OVERRIDE_JSON"

### --- Build overrides JSON ---------------------------------------------------
# Build environment array dynamically so we don't inject empties.
OVERRIDES_ENV_JSON="$(jq -nc \
  --arg DB_API_URL   "$DB_API_URL" \
  --arg AWS_REGION   "$AWS_REGION" \
  --arg S3_BUCKET    "$S3_BUCKET" \
  --arg TESTS_S3_DIR "$TESTS_S3_DIR" \
  --arg LOGGING_LEVEL   "$LOGGING_LEVEL" \
  --arg PYTEST_ARGS     "$PYTEST_ARGS" '
  [
    {name:"DB_API_URL", value:$DB_API_URL},
    {name:"AWS_REGION", value:$AWS_REGION},
    {name:"S3_BUCKET", value:$S3_BUCKET},
    {name:"TESTS_S3_DIR", value:$TESTS_S3_DIR},
    {name:"LOGGING_LEVEL", value:$LOGGING_LEVEL},
    {name:"PYTEST_ARGS", value:$PYTEST_ARGS}
  ] | map(select(.value != null and .value != ""))')"

OVERRIDES="$(jq -nc \
  --arg name "$CONTAINER_NAME" \
  --argjson env "$OVERRIDES_ENV_JSON" \
  --arg cmd "$CMD_OVERRIDE_JSON" '
  {
    containerOverrides: [
      {
        name: $name,
        environment: $env
      }
    ]
  } as $base
  |
  if ($cmd | length) > 0 then
     ($base.containerOverrides[0].command = ( $cmd | fromjson )) | $base
  else
     $base
  end
')"

### --- Run task ---------------------------------------------------------------
RUN_OUT=$(aws ecs run-task \
  --cluster "$CLUSTER" \
  --launch-type FARGATE \
  --task-definition "$TASK_DEF" \
  --region "$REGION" \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS_CSV],securityGroups=[$SECURITY_GROUPS_CSV],assignPublicIp=$ASSIGN_PUBLIC_IP}" \
  --overrides "$OVERRIDES" \
  --tags key=project,value="${TAG_PROJECT_NAME}" key=role,value="${TAG_ROLE}"
)

FAILURES=$(echo "$RUN_OUT" | jq -r '.failures | length')
if [[ "$FAILURES" != "0" ]]; then
  echo "ECS run-task returned failures:"
  echo "$RUN_OUT" | jq -r '.failures[]'
  exit 1
fi

TASK_ARN=$(echo "$RUN_OUT" | jq -r '.tasks[0].taskArn')
TASK_ID="${TASK_ARN##*/}"
echo "TASK_ARN=$TASK_ARN"
echo "TASK_ID=$TASK_ID"

### --- Wait for stop ----------------------------------------------------------
aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK_ARN" --region "$REGION"

DESC=$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK_ARN" --region "$REGION")
EXIT_CODE=$(echo "$DESC" | jq -r '.tasks[0].containers[] | select(.name=="'"$CONTAINER_NAME"'") | .exitCode // -1')
STOPPED_REASON=$(echo "$DESC" | jq -r '.tasks[0].stoppedReason // ""')

echo "Container exit code: $EXIT_CODE"
echo "Stopped reason: $STOPPED_REASON"

### --- On failure: print CW logs to runner output ----------------------------
if [[ "$EXIT_CODE" != "0" ]]; then
  echo "::group::CloudWatch Logs for failed task"
  STREAM="${STREAM_PREFIX}/${CONTAINER_NAME}/${TASK_ID}"
  # tiny delay for final log flush
  sleep 3 || true
  if ! aws logs get-log-events \
        --region "$REGION" \
        --log-group-name "$LOG_GROUP" \
        --log-stream-name "$STREAM" \
        --query 'events[].message' \
        --output text ; then
    echo "(could not fetch exact stream, tailing recent logs)"
    aws logs tail "$LOG_GROUP" --region "$REGION" --since 1h --format short || true
  fi
  echo "::endgroup::"
fi

exit "$EXIT_CODE"
