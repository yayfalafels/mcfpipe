#!/usr/bin/env bash
# tester_task_execute.sh
# Run the ECS tester task, inject DB_API_URL, and on failure print its CloudWatch Logs.
# Intended for GitHub Actions but works locally if AWS creds/region are set.

set -euo pipefail

### --- CONFIG (override via env or flags) -------------------------------------
CLUSTER="${CLUSTER:-mcfpipe}"
TASK_DEF="${TASK_DEF:-mcfpipe-tester}"
SUBNETS_CSV="${SUBNETS_CSV:-subnet-abc123,subnet-def456}"             # comma-separated
SECURITY_GROUPS_CSV="${SECURITY_GROUPS_CSV:-sg-0123456789abcdef0}"    # comma-separated
ASSIGN_PUBLIC_IP="${ASSIGN_PUBLIC_IP:-DISABLED}"                      # ENABLED|DISABLED

# CloudWatch Logs
LOG_GROUP="${LOG_GROUP:-/mcfpipe/tester}"
STREAM_PREFIX="${STREAM_PREFIX:-ecs}"       # should match awslogs-stream-prefix in task def
CONTAINER_NAME="${CONTAINER_NAME:-tester}"  # containerDefinitions[].name

# App env
DB_API_URL="${DB_API_URL:-}"                # REQUIRED (or pass --db-url)
# Optional: override command at run-time (e.g., '["sh","-lc","pytest -q tests.py 2>&1 | tee /var/log/tests.log"]')
CMD_OVERRIDE_JSON="${CMD_OVERRIDE_JSON:-}"  # leave empty to use the task def CMD

REGION="${AWS_REGION:-ap-southeast-1}"

### --- USAGE ------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $(basename "$0") [--db-url URL]

Env overrides:
  CLUSTER, TASK_DEF, SUBNETS_CSV, SECURITY_GROUPS_CSV, ASSIGN_PUBLIC_IP
  LOG_GROUP, STREAM_PREFIX, CONTAINER_NAME, AWS_REGION
  CMD_OVERRIDE_JSON  (optional JSON array for "command" override)
Examples:
  DB_API_URL="https://abc.execute-api.${REGION}.amazonaws.com/prod" \\
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

if [[ -z "${DB_API_URL}" ]]; then
  echo "ERROR: DB_API_URL is required (env or --db-url)." >&2
  exit 2
fi

# deps
command -v aws >/dev/null 2>&1 || { echo "aws CLI not found"; exit 127; }
command -v jq  >/dev/null 2>&1 || { echo "jq not found"; exit 127; }

echo "Cluster: $CLUSTER"
echo "TaskDef: $TASK_DEF"
echo "Region : $REGION"
echo "DB_API_URL: $DB_API_URL"

### --- Build overrides JSON ---------------------------------------------------
# containerOverrides: env var injection; optional command override
OVERRIDES="$(jq -nc --arg name "$CONTAINER_NAME" --arg url "$DB_API_URL" \
  --arg cmd "$CMD_OVERRIDE_JSON" '
  {
    containerOverrides: [
      {
        name: $name,
        environment: [{name:"DB_API_URL", value:$url}]
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
  --overrides "$OVERRIDES")

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
  # small delay to allow final log flush
  sleep 3 || true
  if ! aws logs get-log-events \
        --region "$REGION" \
        --log-group-name "$LOG_GROUP" \
        --log-stream-name "$STREAM" \
        --query 'events[].message' \
        --output text ; then
    echo "(could not fetch exact stream, falling back to recent tail)"
    aws logs tail "$LOG_GROUP" --region "$REGION" --since 1h --format short || true
  fi
  echo "::endgroup::"
fi

exit "$EXIT_CODE"
