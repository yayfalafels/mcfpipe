#!/usr/bin/env bash
set -euo pipefail

# =========================
# Inputs (env vars)
# =========================
: "${AWS_REGION:?set AWS_REGION}"
: "${REST_API_ID:?set REST_API_ID (e.g., 1vrt51wp19)}"
: "${DEV_ENV:?set DEV_ENV (e.g., prod)}"

STAGE_NAME=$DEV_ENV

# Optional for in-VPC probe (recommended)
CLUSTER="${CLUSTER:-}"                  # ECS cluster
TASK_DEF="${TASK_DEF:-}"                # task def family:rev or ARN
SUBNETS_CSV="${SUBNETS_CSV:-}"          # e.g. subnet-aaa,subnet-bbb
SECURITY_GROUPS_CSV="${SECURITY_GROUPS_CSV:-}"  # e.g. sg-111,sg-222
ASSIGN_PUBLIC_IP="${ASSIGN_PUBLIC_IP:-DISABLED}" # DISABLED|ENABLED
CONTAINER_NAME="${CONTAINER_NAME:-tester}"
LOG_GROUP="${LOG_GROUP:-}"               # optional awslogs group to tail

# Optional private-path extras
VPCE_ID="${VPCE_ID:-}"                   # e.g., vpce-xxxx (execute-api)
API_KEY="${API_KEY:-}"                   # optional, if your stage/methods require it

# Derived
DB_API_URL="${DB_API_URL:-https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

bold(){ printf "\e[1m%s\e[0m\n" "$*"; }
hr(){ printf '\n%s\n' '------------------------------------------------------------'; }
need(){ command -v "$1" >/dev/null || { echo "Missing tool: $1" >&2; exit 99; }; }

need aws
need jq

bold "API/Network Diagnostics for PRIVATE API Gateway via VPCE"
cat <<EOF
Region         : ${AWS_REGION}
REST API ID    : ${REST_API_ID}
Stage          : ${STAGE_NAME}
DB_API_URL     : ${DB_API_URL}
Cluster        : ${CLUSTER:-<not set>}
TaskDef        : ${TASK_DEF:-<not set>}
Subnets        : ${SUBNETS_CSV:-<not set>}
SecGroups      : ${SECURITY_GROUPS_CSV:-<not set>}
AssignPublicIp : ${ASSIGN_PUBLIC_IP}
VPCE_ID        : ${VPCE_ID:-<not set>}
Log group      : ${LOG_GROUP:-<not set>}
API_KEY set    : $( [[ -n "$API_KEY" ]] && echo yes || echo no )
EOF
hr

# =========================
# A) Control plane checks
# =========================
bold "A1) REST API endpoint type + policy"
API_INFO=$(aws apigateway get-rest-api --rest-api-id "$REST_API_ID")
echo "$API_INFO" | jq '{name:.name,id:.id,endpoint:.endpointConfiguration.types,policy:.policy}'

ENDPOINT_TYPES=$(echo "$API_INFO" | jq -r '.endpointConfiguration.types|join(",")')
if [[ "$ENDPOINT_TYPES" != *"PRIVATE"* ]]; then
  echo "❌ API is not PRIVATE (types=$ENDPOINT_TYPES)" >&2
else
  echo "✅ API is PRIVATE"
fi

bold "A2) Stages present"
aws apigateway get-stages --rest-api-id "$REST_API_ID" | jq '.item[].stageName'
if ! aws apigateway get-stages --rest-api-id "$REST_API_ID" \
      | jq -re --arg s "$STAGE_NAME" '.item[].stageName | select(.==$s)' >/dev/null; then
  echo "❌ Stage '$STAGE_NAME' does not exist on this API" >&2
fi

bold "A3) Stage/method key requirements (apiKeyRequired)"
METHOD_SETTINGS=$(aws apigateway get-stage --rest-api-id "$REST_API_ID" --stage-name "$STAGE_NAME" --query 'methodSettings' || echo '{}')
echo "$METHOD_SETTINGS" | jq .
ROOT_ID=$(aws apigateway get-resources --rest-api-id "$REST_API_ID" --query 'items[?path==`/`].id' --output text || true)
PROXY_ID=$(aws apigateway get-resources --rest-api-id "$REST_API_ID" --query 'items[?pathPart==`{proxy+}`].id' --output text || true)
if [[ -n "$ROOT_ID" ]]; then
  echo -n "root GET apiKeyRequired: "
  aws apigateway get-method --rest-api-id "$REST_API_ID" --resource-id "$ROOT_ID" --http-method GET --query 'apiKeyRequired' || echo "n/a"
fi
if [[ -n "$PROXY_ID" ]]; then
  echo -n "proxy ANY apiKeyRequired: "
  aws apigateway get-method --rest-api-id "$REST_API_ID" --resource-id "$PROXY_ID" --http-method ANY --query 'apiKeyRequired' || echo "n/a"
fi

hr
bold "A4) Test invoke (bypasses VPCE path)"
if [[ -n "$ROOT_ID" ]]; then
  set +e
  TI=$(aws apigateway test-invoke-method --rest-api-id "$REST_API_ID" --resource-id "$ROOT_ID" --http-method GET 2>&1)
  RC=$?
  set -e
  echo "$TI"
  [[ $RC -eq 0 ]] && echo "✅ test-invoke-method OK" || echo "❌ test-invoke-method failed"
else
  echo "⚠ Could not resolve RootResourceId; skipping test-invoke."
fi

# =========================
# B) VPCE checks (optional)
# =========================
hr
if [[ -n "$VPCE_ID" ]]; then
  bold "B1) VPCE details & policy"
  aws ec2 describe-vpc-endpoints --vpc-endpoint-ids "$VPCE_ID" \
    --query 'VpcEndpoints[0].{Service:ServiceName,PrivateDns:PrivateDnsEnabled,VpcId:VpcId,SubnetIds:SubnetIds,SgIds:Groups[].GroupId,Policy:PolicyDocument}' \
    --output json | jq .

  bold "B2) VPCE Security Group inbound rules"
  for SG in $(aws ec2 describe-vpc-endpoints --vpc-endpoint-ids "$VPCE_ID" --query 'VpcEndpoints[0].Groups[].GroupId' --output text); do
    echo "SG: $SG"
    aws ec2 describe-security-groups --group-ids "$SG" --query 'SecurityGroups[0].IpPermissions' --output json | jq .
  done

  bold "B3) VPCE hostnames"
  VPCE_HOST=$(aws ec2 describe-vpc-endpoints --vpc-endpoint-ids "$VPCE_ID" \
    --query 'VpcEndpoints[0].DnsEntries[0].DnsName' --output text 2>/dev/null || true)
  echo "VPCE_HOST: ${VPCE_HOST:-<none>}"
else
  echo "ℹ VPCE_ID not set; skipping VPCE checks."
fi

# =========================
# C) Inside-VPC ECS probe
# =========================
hr
run_ecs=false
if [[ -n "$CLUSTER" && -n "$TASK_DEF" && -n "$SUBNETS_CSV" && -n "$SECURITY_GROUPS_CSV" ]]; then
  run_ecs=true
fi

if $run_ecs; then
  bold "C) Launching inside-VPC ECS diagnostics task"

  PY=$(cat <<'PY'
import os, json, socket, ssl, urllib.request, urllib.error, urllib.parse
def head(h): return {k.lower():v for k,v in h.items()} if hasattr(h,'items') else {}
base = os.environ.get("DB_API_URL","").rstrip("/") + "/"
host = urllib.parse.urlparse(base).hostname or ""
api_id = os.environ.get("REST_API_ID","").strip()
stage = os.environ.get("STAGE_NAME","").strip("/")
vpce_host = os.environ.get("VPCE_HOST","").strip()
api_key = os.environ.get("API_KEY","").strip()
hdrs = {"Accept":"application/json"}
if api_key: hdrs["x-api-key"] = api_key
res = {"base":base, "host":host}
# DNS
try:
  info = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
  res["dns"] = sorted({i[4][0] for i in info})
except Exception as e:
  res["dns_error"] = str(e)
# TLS
try:
  ctx = ssl.create_default_context()
  with socket.create_connection((host,443), timeout=5) as s:
    with ctx.wrap_socket(s, server_hostname=host) as ss:
      res["tls_ok"] = True
      res["tls_subject"] = ss.getpeercert().get("subject")
except Exception as e:
  res["tls_ok"] = False
  res["tls_error"] = type(e).__name__ + ": " + str(e)

def fetch(path, headers):
  url = urllib.parse.urljoin(base, path.strip("/"))
  try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
      return {"url":url,"status":r.status,"errorType":head(r.headers).get("x-amzn-errortype"),"body":r.read(512).decode("utf-8","ignore")}
  except urllib.error.HTTPError as e:
    bt = e.read(512).decode("utf-8","ignore") if hasattr(e,"read") else ""
    return {"url":url,"status":e.code,"error":"HTTPError","errorType":head(e.headers).get("x-amzn-errortype"),"body":bt}
  except Exception as e:
    return {"url":url,"error":type(e).__name__,"msg":str(e)}

res["get_root"] = fetch("", hdrs)
res["get_health"] = fetch("health", hdrs)

# VPCE hostname direct (if provided)
if vpce_host and api_id:
  u = f"https://{vpce_host}/{stage}/health" if stage else f"https://{vpce_host}/health"
  h2 = dict(hdrs); h2["x-amzn-apigateway-api-id"] = api_id
  try:
    req = urllib.request.Request(u, headers=h2)
    with urllib.request.urlopen(req, timeout=10) as r:
      res["vpce_health"] = {"url":u,"status":r.status,"errorType":head(r.headers).get("x-amzn-errortype"),"body":r.read(512).decode("utf-8","ignore")}
  except urllib.error.HTTPError as e:
    bt = e.read(512).decode("utf-8","ignore") if hasattr(e,"read") else ""
    res["vpce_health"] = {"url":u,"status":e.code,"error":"HTTPError","errorType":head(e.headers).get("x-amzn-errortype"),"body":bt}
  except Exception as e:
    res["vpce_health"] = {"url":u,"error":type(e).__name__,"msg":str(e)}

print(json.dumps(res, ensure_ascii=False))
code = 0
for k in ("get_root","get_health"):
  v = res.get(k, {})
  if not isinstance(v, dict) or v.get("status") not in (200,204):
    code = 2
raise SystemExit(code)
PY
)

  OVERRIDES=$(jq -n \
    --arg n "$CONTAINER_NAME" \
    --arg url "$DB_API_URL" \
    --arg id "$REST_API_ID" \
    --arg st "$STAGE_NAME" \
    --arg vh "${VPCE_HOST:-}" \
    --arg k "$API_KEY" \
    --arg py "$PY" \
    '{containerOverrides:[{name:$n,environment:[{name:"DB_API_URL",value:$url},{name:"REST_API_ID",value:$id},{name:"STAGE_NAME",value:$st},{name:"VPCE_HOST",value:$vh},{name:"API_KEY",value:$k}],command:["python","-c",$py]}]}')

  echo "ECS overrides:"
  echo "$OVERRIDES" | jq .

  RUN=$(aws ecs run-task \
    --cluster "$CLUSTER" \
    --launch-type FARGATE \
    --task-definition "$TASK_DEF" \
    --region "$AWS_REGION" \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS_CSV],securityGroups=[$SECURITY_GROUPS_CSV],assignPublicIp=$ASSIGN_PUBLIC_IP}" \
    --overrides "$OVERRIDES" \
    --enable-ecs-managed-tags \
    --tags "key=diag,value=apigw" "key=stage,value=${STAGE_NAME}")
  echo "$RUN" | jq .

  TASK_ARN=$(echo "$RUN" | jq -r '.tasks[0].taskArn')
  [[ -z "$TASK_ARN" || "$TASK_ARN" == "null" ]] && { echo "❌ failed to start ECS task" >&2; exit 50; }

  bold "Waiting for task STOPPED…"
  aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK_ARN"
  DESC=$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK_ARN")
  echo "$DESC" | jq '{taskArn:.tasks[0].taskArn,lastStatus:.tasks[0].lastStatus,exitCode:.tasks[0].containers[0].exitCode,reason:.tasks[0].stoppedReason}'

  if [[ -n "$LOG_GROUP" ]]; then
    bold "Tail recent logs ($LOG_GROUP)"
    aws logs tail "$LOG_GROUP" --region "$AWS_REGION" --since 10m --format short || true
  fi

  EXIT_CODE=$(echo "$DESC" | jq -r '.tasks[0].containers[0].exitCode // -1')
  [[ "$EXIT_CODE" -eq 0 ]] && echo "✅ Inside-VPC probe: / and /health OK" || echo "❌ Inside-VPC probe failed (exit $EXIT_CODE)"
else
  echo "ℹ ECS parameters incomplete; skipping inside-VPC probe."
fi

# =========================
# Summary
# =========================
hr
bold "Summary"
echo "API types     : $ENDPOINT_TYPES"
echo "Stage         : $STAGE_NAME"
echo "DB_API_URL    : $DB_API_URL"
if [[ -n "${EXIT_CODE:-}" ]]; then echo "ECS probe exit: $EXIT_CODE"; fi
