#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./setup/export_stack_outputs.sh <STACK_NAME> <AWS_REGION> <S3_BUCKET> [s3_key_prefix]
# Example:
#   ./setup/export_stack_outputs.sh mcfpipe-network ap-southeast-1 mcfpipe aws/network/network_config.json

STACK_NAME="${1:?Missing STACK_NAME}"
AWS_REGION="${2:?Missing AWS_REGION}"
S3_BUCKET="${3:?Missing S3_BUCKET}"
S3_KEY="${4:-aws/network/network_config.json}"   # Matches your documented S3 layout

# deps check
command -v aws >/dev/null 2>&1 || { echo "aws CLI not found" >&2; exit 1; }
command -v jq  >/dev/null 2>&1 || { echo "jq not found" >&2; exit 1; }

TMP_JSON="$(mktemp)"
trap 'rm -f "$TMP_JSON"' EXIT

echo "Fetching CloudFormation outputs for stack: $STACK_NAME ($AWS_REGION)..."

# Grab the Outputs as an array of objects and reduce to {OutputKey, OutputValue}
aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' \
  --output json \
| jq '[ .[] | {OutputKey: .OutputKey, OutputValue: .OutputValue} ]' > "$TMP_JSON"

# sanity check
if [[ "$(jq 'length' "$TMP_JSON")" -eq 0 ]]; then
  echo "No Outputs found on stack '$STACK_NAME' or stack not found." >&2
  exit 2
fi

echo "Wrote $(jq 'length' "$TMP_JSON") outputs to $TMP_JSON"

# Upload to S3 in the documented location
aws s3 cp "$TMP_JSON" "s3://${S3_BUCKET}/${S3_KEY}" \
  --region "$AWS_REGION" \
  --content-type application/json \
  --sse AES256

echo "Uploaded to s3://${S3_BUCKET}/${S3_KEY}"
