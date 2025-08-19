#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# Inputs (env vars)
# -----------------------------
: "${AWS_REGION:?set AWS_REGION}"
: "${REST_API_ID:?set REST_API_ID (e.g., 1vrt51wp19)}"
: "${DEV_ENV:?set DEV_ENV (e.g., prod)}"

STAGE_NAME=$DEV_ENV

# Optional, but recommended for “inside VPC” checks
CLUSTER="${CLUSTER:-}"                  # ECS cluster name/ARN
TASK_DEF="${TASK_DEF:-}"                # Task definition family:revision (or ARN)
SUBNETS_CSV="${SUBNETS_CSV:-}"          # e.g., subnet-aaa,subnet-bbb (no spaces)
SECURITY_GROUPS_CSV="${SECURITY_GROUPS_CSV:-}"  # e.g., sg-123,sg-456
ASSIGN_PUBLIC_IP="${ASSIGN_PUBLIC_IP:-DISABLED}" # DISABLED|ENABLED
CONTAINER_NAME="${CONTAINER_NAME:-tester}"
STREAM_PREFIX="${STREAM_PREFIX:-tester}" # must match awslogs-stream-prefix
LOG_GROUP="${LOG_GROUP:-}"               # optional; e.g., /mcfpipe/tester

# VPCE (for informational checks)
VPCE_ID="${VPCE_ID:-}"                   # e.g., vpce-xxxxxxxx (optional)

# Derived
DB_API_URL="${DB_API_URL:-https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

bold() { printf "\e[1m%s\e[0m\n" "$*"; }
hr()   { printf '\n%s\n' '------------------------------------------------------------'; }
jqok() { command -v jq >/dev/null; }

require_tools() {
  local missing=()
  for t in aws jq; do command -v "$t" >/dev/null || missing+=("$t"); done
  if ((${#missing[@]})); then
    echo "Missing tools: ${missing[*]}. Ensure GitHub runner has them." >&2
    exit 99
  fi
}
require_tools

bold "API/Network Diagnostics for PRIVATE API Gateway via VPCE"
echo "Region         : ${AWS_REGION}"
echo "REST API ID    : ${REST_API_ID}"
echo "Stage          : ${STAGE_NAME}"
echo "DB_API_URL     : ${DB_API_URL}"
echo "Cluster        : ${CLUSTER:-<not set>}"
echo "TaskDef        : ${TASK_DEF:-<not set>}"
echo "Subnets        : ${SUBNETS_CSV:-<not set>}"
echo "SecGroups      : ${SECURITY_GROUPS_CSV:-<not set>}"
echo "AssignPublicIp : ${ASSIGN_PUBLIC_IP}"
echo "VPCE_ID        : ${VPCE_ID:-<not set>}"
echo "Log group      : ${LOG_GROUP:-<not set>}"
hr

# -----------------------------
# A) Control-plane checks
# -----------------------------
bold "A1) REST API endpoint type + policy"
API_INFO_JSON=$(aws apigateway get-rest-api --rest-api-id "$REST_API_ID")
echo "$API_INFO_JSON" | jq '{name:.name, id:.id, endpoint:.endpointConfiguration.types, policy: .policy}'

if [[ "$(echo "$API_INFO_JSON" | jq -r '.endpointConfiguration.types|join(",")')" != *"PRIVATE"* ]]; then
  echo "❌ API is not PRIVATE. Current endpoint types: $(echo "$API_INFO_JSON" | jq -r '.endpointConfiguration.types|join(",")')" >&2
else
  echo "✅ API is PRIVATE"
fi

bold "A2) Stages"
aws apigateway get-stages --rest-api-id "$REST_API_ID" | jq '.item[].stageName'
if ! aws apigateway get-stages --rest-api-id "$REST_API_ID" | jq -re --arg s "$STAGE_NAME" '.item[].stageName | select(.==$s)' >/dev/null; then
  echo "❌ Stage '$STAGE_NAME' not found on API $REST_API_ID" >&2
fi

bold "A3) Lambda integration + invoke permission scope (root GET)"
ROOT_ID=$(aws apigateway get-resources --rest-api-id "$REST_API_ID" --query 'items[?path==`/`].id' --output text || true)
if [[ -n "$ROOT_ID" ]]; then
  INTEGRATION_URI=$(aws apigateway get-integration --rest-api-id "$REST_API_ID" --resource-id "$ROOT_ID" --http-method GET --query 'uri' --output text 2>/dev/null || true)
  echo "Integration URI (GET /): ${INTEGRATION_URI:-<none>}"
fi
# (policy check shown later via test-invoke)

hr

# -----------------------------
# B) VPCE checks (optional)
# -----------------------------
if [[ -n "$VPCE_ID" ]]; then
  bold "B1) Describe VPCE $VPCE_ID"
  aws ec2 describe-vpc-endpoints --vpc-endpoint-ids "$VPCE_ID" \
    --query 'VpcEndpoints[0].{Service:ServiceName,PrivateDns:PrivateDnsEnabled,VpcId:VpcId,SubnetIds:SubnetIds,SgIds:Groups[].GroupId,Policy:PolicyDocument}' \
    --output json | jq .

  bold "B2) VPCE SG rules (inbound 443 should allow from tester SGs)"
  for SG in $(aws ec2 describe-vpc-endpoints --vpc-endpoint-ids "$VPCE_ID" --query 'VpcEndpoints[0].Groups[].GroupId' --output text); do
    echo "Security Group: $SG"
    aws ec2 describe-security-groups --group-ids "$SG" --query 'SecurityGroups[0].IpPermissions' --output json | jq .
    echo
  done
else
  echo "ℹ VPCE_ID not provided; skipping VPCE policy/SG inspection"
fi

hr

# -----------------------------
# C) Public-plane sanity: test-invoke (bypasses VPCE path)
# -----------------------------
bold "C) API Gateway test-invoke-method (bypasses VPC/VPCE)"
if [[ -n "$ROOT_ID" ]]; then
  set +e
  TEST_INV=$(aws apigateway test-invoke-method --rest-api-id "$REST_API_ID" --resource-id "$ROOT_ID" --http-method GET 2>&1)
  RC=$?
  set -e
  echo "$TEST_INV"
  if ((RC==0)); then echo "✅ test-invoke-method OK"; else echo "❌ test-invoke-method failed (integration/permission issue)"; fi
else
  echo "⚠ Could not resolve RootResourceId; skipping test-invoke"
fi

hr

# -----------------------------
# D) Inside-VPC runtime probe (ECS task)
# -----------------------------
run_ecs_diag=false
if [[ -n "${CLUSTER}" && -n "${TASK_DEF}" && -n "${SUBNETS_CSV}" && -n "${SECURITY_GROUPS_CSV}" ]]; then
  run_ecs_diag=true
fi

if $run_ecs_diag; then
  bold "D) Launching ECS diagnostic task inside VPC"
  PYCODE=$(cat <<'PY'
import os, socket, ssl, sys, json, urllib.request, urllib.error, urllib.parse
base = os.environ.get("DB_API_URL","").rstrip("/") + "/"
host = urllib.parse.urlparse(base).hostname or ""
res = {"base": base, "host": host}

# DNS
try:
    infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    res["dns"] = sorted({i[4][0] for i in infos})
except Exception as e:
    res["dns_error"] = str(e)

# TLS
try:
    ctx = ssl.create_default_context()
    with socket.create_connection((host,443), timeout=5) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
            res["tls_ok"] = True
            res["tls_subject"] = cert.get("subject")
except Exception as e:
    res["tls_ok"] = False
    res["tls_error"] = str(e)

def fetch(path):
    url = urllib.parse.urljoin(base, path.strip("/"))
    try:
        req = urllib.request.Request(url, headers={"Accept":"application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read(512).decode("utf-8","ignore")
            return {"url": url, "status": r.status, "headers": dict(r.getheaders()), "body": body}
    except urllib.error.HTTPError as e:
        body = e.read(512).decode("utf-8","ignore") if hasattr(e, "read") else ""
        return {"url": url, "status": e.code, "error": "HTTPError", "body": body}
    except Exception as e:
        return {"url": url, "error": type(e).__name__, "msg": str(e)}

res["get_root"] = fetch("")
res["get_health"] = fetch("health")
print(json.dumps(res))
code = 0
for k in ("get_root","get_health"):
    v = res.get(k, {})
    if not isinstance(v, dict) or v.get("status") not in (200,204):
        code = 2
sys.exit(code)
PY
)
  CODE_JSON=$(jq -Rn --arg code "$PYCODE" '$code')
  OVERRIDES_JSON=$(jq -n \
    --arg name "$CONTAINER_NAME" \
    --arg url "$DB_API_URL" \
    --arg code "$PYCODE" \
    '{containerOverrides:[{name:$name,environment:[{name:"DB_API_URL",value:$url}],command:["python","-c",$code]}]}')

  echo "Running task with overrides:"
  echo "$OVERRIDES_JSON" | jq .

  RUN_OUT=$(aws ecs run-task \
    --cluster "$CLUSTER" \
    --launch-type FARGATE \
    --task-definition "$TASK_DEF" \
    --region "$AWS_REGION" \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS_CSV],securityGroups=[$SECURITY_GROUPS_CSV],assignPublicIp=$ASSIGN_PUBLIC_IP}" \
    --overrides "$OVERRIDES_JSON" \
    --enable-ecs-managed-tags \
    --tags "key=diag,value=apigw" "key=project,value=${PROJECT_NAME:-mcfpipe}")
  echo "$RUN_OUT" | jq .

  TASK_ARN=$(echo "$RUN_OUT" | jq -r '.tasks[0].taskArn')
  if [[ "$TASK_ARN" == "null" || -z "$TASK_ARN" ]]; then
    echo "❌ Failed to start ECS task" >&2
    exit 50
  fi
  echo "Task ARN: $TASK_ARN"

  bold "Waiting for task to STOP..."
  aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK_ARN"
  DESC=$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK_ARN")
  echo "$DESC" | jq '{taskArn:.tasks[0].taskArn, lastStatus:.tasks[0].lastStatus, stopCode:.tasks[0].stopCode, stoppedReason:.tasks[0].stoppedReason, exitCode:.tasks[0].containers[0].exitCode}'

  EXIT_CODE=$(echo "$DESC" | jq -r '.tasks[0].containers[0].exitCode // -1')
  if [[ -n "$LOG_GROUP" ]]; then
    bold "Tail (recent) CloudWatch Logs: $LOG_GROUP"
    # best-effort tail across streams
    aws logs tail "$LOG_GROUP" --region "$AWS_REGION" --since 10m --format short || true
  fi

  if (( EXIT_CODE == 0 )); then
    echo "✅ Inside-VPC probe: GET / and /health returned 200/204"
  else
    echo "❌ Inside-VPC probe failed (exit $EXIT_CODE). See logs above for JSON diagnostics from container."
  fi
else
  echo "ℹ ECS parameters not fully set; skipping inside-VPC probe (set CLUSTER, TASK_DEF, SUBNETS_CSV, SECURITY_GROUPS_CSV)."
fi

hr
bold "Summary"
echo "API type  : $(echo "$API_INFO_JSON" | jq -r '.endpointConfiguration.types|join(",")')"
echo "Stage     : $STAGE_NAME"
echo "DB_API_URL: $DB_API_URL"
if $run_ecs_diag; then
  echo "ECS probe : exit ${EXIT_CODE:-<skipped>}"
fi
