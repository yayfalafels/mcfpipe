#!/usr/bin/env bash
# Print concise CloudFormation failure/rollback info for a stack.
# Usage: cfn_stack_diagnostics.sh <STACK_NAME> [REGION] [--nested]
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <STACK_NAME> [REGION] [--nested]"
  exit 2
fi

STACK="$1"
REGION="${2:-${AWS_REGION:-}}"
SHOW_NESTED="${3:-}"

AWS=(aws)
[[ -n "$REGION" ]] && AWS+=(--region "$REGION")

# Don’t crash the job if the stack isn’t found or calls fail
set +e

echo "== Stack status =="
"${AWS[@]}" cloudformation describe-stacks --stack-name "$STACK" \
  --query 'Stacks[0].[StackStatus,StackStatusReason]' \
  --output table

echo "== Recent failed/rollback events =="
"${AWS[@]}" cloudformation describe-stack-events --stack-name "$STACK" \
  --query 'reverse(sort_by(StackEvents,&Timestamp))[?contains(ResourceStatus, `FAILED`) || contains(ResourceStatus, `ROLLBACK`)].[
    Timestamp, ResourceType, LogicalResourceId, ResourceStatus, ResourceStatusReason
  ]' \
  --output table | head -n 50

if [[ "$SHOW_NESTED" == "--nested" ]]; then
  IDS=$("${AWS[@]}" cloudformation describe-stack-resources --stack-name "$STACK" \
    --query 'StackResources[?ResourceType==`AWS::CloudFormation::Stack`].PhysicalResourceId' --output text)
  for N in $IDS; do
    echo "== Nested stack $N failures =="
    "${AWS[@]}" cloudformation describe-stack-events --stack-name "$N" \
      --query 'reverse(sort_by(StackEvents,&Timestamp))[?contains(ResourceStatus, `FAILED`) || contains(ResourceStatus, `ROLLBACK`)].[
        Timestamp, ResourceType, LogicalResourceId, ResourceStatus, ResourceStatusReason
      ]' \
      --output table | head -n 50
  done
fi

# Always succeed so this script doesn't mask the real failing step
exit 0
