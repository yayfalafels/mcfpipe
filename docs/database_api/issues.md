# DB API: Issues

__Assessment__

Core structure matches the intended architecture (handler + core + domain + config).  
Addressing these issues will bring the implementation much closer to the design, while the additional unit/integration/E2E tests will harden behavior and prevent regressions.

The biggest gaps are

- schema/validator key mismatch
- opaque pagination token
- reload payload
- envelope & route consistency
- tests diverging from spec

__issues__

| id | status | type | issue | description |
| - | - | - | - | - |
| 01 | open | BUG | engine.reload payload | |
| 02 | open | BUG | opaque pagination token | |
| 17 | open | BUG | validator schema keys mismatch | |
| 03 | open | BUG | router garbled error code | |
| 04 | open | BUG | health version payload | |
| 05 | open | BUG | UTC time format | |
| 06 | open | BUG | variable name mismatch | |
| 07 | open | BUG | empty default schema JSON | |
| 08 | open | BUG | DynamoDB number types | |
| 09 | open | BUG | policies not enforced | |
| 10 | open | BUG | routing and op naming | |
| 11 | open | BUG | root version behavior | |
| 12 | open | BUG | item key naming | |
| 13 | open | BUG | write-delete request-response spec | |
| 14 | open | BUG | search query params | |
| 15 | open | BUG | settings keys mismatch | |
| 16 | open | BUG | tests error mapping | |
| 20 | closed | BUG | logging to CW log | lambda not resolve correct image digest from image tag |
| 17 | open | ENHANCEMENT | consolidated response build | |
| 18 | open | ENHANCEMENT | logging format | |
| 19 | open | ENHANCEMENT | auth placeholder | |

__Potential bugs and exceptions__

_01 (open) BUG engine.reload payload_

`engine.reload()` returns the wrong payload. It currently returns `{'reloaded_at': self.version}` instead of a timestamp. Spec calls for an epoch/instant (e.g., ISO or unix seconds). Fix to return a real time value.

Quick patch:

```python
import time
def reload(self) -> dict:
    ...
    self.log.info('engine_reloaded', tables=len(self._tables))
    return {'reloaded_at': int(time.time())}
```

_02 (open) BUG opaque pagination token_

Pagination token is not opaque/base64. `Table.search()` returns DynamoDB’s raw LastEvaluatedKey in next. Design requires an opaque base64 token; requests should also accept next and decode it into ExclusiveStartKey.

Pagination token (opaque):

```python
# in Table.search(...)
import json, base64
...
if 'LastEvaluatedKey' in resp:
    token_json = json.dumps(resp['LastEvaluatedKey'], separators=(',',':'))
    next_token = base64.urlsafe_b64encode(token_json.encode()).decode()
else:
    next_token = None
return {'items': items, 'next': next_token}
```

…and in Router, if query has next, base64-decode and set ExclusiveStartKey.

_17 (open) BUG validator schema keys mismatch_

Validator schema keys don’t match the spec.  
mismatch validator module `core/validators.py` with the schema in the design
This will skip required/type checks silently. Align keys or support both.

- as implemented: "column_name", "data_type", "nullable" 
- design:  "name", "type", "required" 

Validator key alignment:

```python
# build columns map tolerant to both styles
def _name(c): return c.get('name') or c.get('column_name')
def _type(c): return c.get('type') or c.get('data_type')
def _required(c): 
    return bool(c.get('required')) or not c.get('nullable', True)
self.columns = { _name(c): {'type': _type(c), 'required': _required(c)} for c in cols if _name(c) }
```

__Response envelope mismatches and typos__

_03 (open) BUG router garbled error code_

Router returns error code 'internal_err...cted_error' (string is garbled). Needs a stable "internal_error" with mapped error names per table.

_04 (open) BUG health version payloads_

Health/version payloads differ from spec—see §2 and §3 below.

Health route payload. Spec says health => `{"ok": true}` (detailed_design) or `{"success": true}` `design.md`. Your test asserts `status == 1`. Pick one and standardize test + code (recommend {"ok": true}).

Return {"ok": true} for health and unify tests to that.
Prefer routing / through Router (meta.version) returning {service, version, stage} as spec’d.

_05 (open) BUG UTC time format_

Handler time formatting. `_utcnow_iso()` builds an ISO string with +00:00 then appends 'Z', yielding ...+00:00Z. Either use `.strftime('%Y-%m-%dT%H:%M:%SZ')` or produce a clean UTC ISO8601.

_06 (open) BUG variable name mismatch design and implementation_

S3/env var names drift. `engine.py` 
Support both names or switch to the spec.

- separate config keys too
- `engine.py` looks for `S3_BUCKET` and `DB_SCHEMA_S3`
- design specifies  `SCHEMA_S3_BUCKET` and `SCHEMA_S3_KEY` 

_07 (open) BUG empty default schema JSON_

Empty bundled schema. `schemas/db_schema.json` has "tables": []. If S3 isn’t set/available, all CRUD routes will fail at runtime. Consider raising a clear startup error or ship a minimal example schema.

_08 (open) BUG DynamoDB number types_

DynamoDB number types. Writes may send floats; DynamoDB prefers Decimal. Consider coercing numeric types (or document the expectation) to avoid precision/type issues.

Type safety and numbers. Consider Decimal for numeric attributes to play nicely with DynamoDB. Add mypy type hints where feasible.

_09 (open) BUG policies not enforced_

Idempotency & limits not enforced. Spec mentions idempotency and rate/size caps; code paths for those aren’t present (policies file is a stub).

__implementation consistency vs design__

_10 (open) BUG routing and op naming_

Routes & op naming: Your `config/routes.json` uses simple ops: "get", "create", "search", etc. Spec shows namespaced ops like "table.get", "engine.reload", "meta.health" plus a query_to_search mapping. You can either: (a) update Router to normalize both styles, or (b) adopt the namespaced ops and mapping from the spec.

Router op names & mapping. Consider adopting the namespaced ops from spec (table.get, engine.reload, meta.health) and a query_to_search map to decouple URL/params from Table.search.

_11 (open) BUG root version behavior_

Root/version behavior. The handler short-circuits / and returns version inline; spec models this as a route via router (minor but worth aligning for consistency/config-driven behavior).

_12 (open) BUG item key naming_

Single-item response body keys: One spec table shows { "id": ... }, another shows { "pk": ... } for create/put/delete responses—your Table.create/put/delete return {<actual_pk_name>: value}. Choose one convention and lock it: (a) standardize on { "id": ... } for UX simplicity, or (b) echo actual PK (e.g., job_id). Update docs & tests accordingly.

_13 (open) BUG batch write-delete request-response_

Batch write/delete shapes: Spec alternates between {"items":[...]} vs raw [...] for batch write and requires {"keys":[{pk,sk?},...]} for batch delete. Your tests appear to POST a raw list of ids to /{table}/delete. Align both code and tests to one documented request shape.

Batch-delete request. Your cleanup uses a plain list of ids; spec requires {"keys":[{pk,sk?},...]}. Update test to post {"keys":[{"job_id": "..."}]} or update the API to tolerate both.

Create/Put/Delete response shape. Tests should assert the same response envelope the spec declares (see §2 above), not "status": 1.

Batch-delete request shape tolerance:
Accept either {"keys":[...]} or [...] (ids) to ease migration, but document the canonical shape (recommend {"keys":[...]}).

_14 (open) BUG search query params_

Search query params. Spec defines index, limit, next, pk, sk, eq[field], begins[field]. Ensure the router feeds these into expression builders and uses base64 next.

Search behavior. Tests don’t appear to cover: index, limit, next (base64), eq[...], begins[...], or GSI flows. Add these per the spec.

_15 (open) BUG settings keys mismatch_

Settings keys. Your `config/settings.json` uses payload_max_bytes; spec shows max_body_kb, max_batch, etc. Align naming and enforcement.

_16 (open) BUG tests error mapping_

Error mapping. Add tests that assert 400/401/403/404/409/413/429/500 mappings with the standardized error envelope.

_20 (closed) BUG logging to CW log_

unable to find CW logs for event handling

**diagnostics**

observations

- cannot see any logging or `print()` from lambda runtime
- can see lambda invoke START / STOP

X (ruled out) possible cause 01: API deployment version mismatch with Lambda

validation failed --> did not resolve the logging issue

resolution

add `${RestApi}` to the SourceArn in the CF logical resource `DbLambdaInvokeFromApiGw`

```
SourceArn: !Sub arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${RestApi}/*/*/*
```

location: `aws/cloudformation/db_api_stack.yaml`

```yaml
  # Let API Gateway invoke the Lambda for any stage/method/path
  DbLambdaInvokeFromApiGw:
    Type: AWS::Lambda::Permission
    Properties:
      Action: lambda:InvokeFunction
      FunctionName: !Ref DbLambda
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${RestApi}/*/*/*

```

root cause (closed) possible cause 02: Lambda pointing to wrong image

from the ECR list, for latest image "6286dfd" last pull date shows blank

from the Lambda console, it shows

image URI `339953771490.dkr.ecr.ap-southeast-1.amazonaws.com/mcfpipe-dbapi:6286dfd` 

Resolved Image URI `339953771490.dkr.ecr.ap-southeast-1.amazonaws.com/mcfpipe-dbapi@sha256:8828308fb75011ce096f2a344fd3ee5dcf1f66bcc28a1a9071e62bc0c5b83e98`

The latest published image is 

URI `339953771490.dkr.ecr.ap-southeast-1.amazonaws.com/mcfpipe-dbapi:6286dfd`
digest `sha256:e999332cefd3b9e92b1b5e0aa9d9e40558d2e61d0de3b614cd978c70785bc22f`
tag `6286dfd`

resolution:

pass `DIGEST_URI` with the full `@sha...` digest reference to CF stack deploy instead of `IMAGE_URI` which uses the tag

```yaml
- name: Push image to ECR
id: docker_image_ecr
if: steps.app_dir_change.outputs.app == 'true' || inputs.force_rebuild == true
run: |
    docker push "$IMAGE_URI"
    DIGEST=$(aws ecr describe-images \
    --repository-name "$REPO_NAME" \
    --image-ids imageTag="$IMAGE_TAG" \
    --query 'imageDetails[0].imageDigest' --output text)
    DIGEST_URI="${IMAGE_REPO}@${DIGEST}"
    echo "DIGEST_URI=$DIGEST_URI" >> $GITHUB_ENV
```

and for the case of no change detected

```yaml
      - name: Set image tags and ECR URI
        id: image_tag_name
        env:
          REBUILD: ${{ steps.decide.outputs.rebuild }}
        run: |
          set -euo pipefail
          SHORT_SHA="${GITHUB_SHA::7}"
          REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
          IMAGE_REPO="${REGISTRY}/${REPO_NAME}"

          if [[ "${REBUILD}" == "true" ]]; then
            IMAGE_TAG="sha-${SHORT_SHA}"
            IMAGE_URI="${IMAGE_REPO}:sha-${SHORT_SHA}"            
          else
            # Pull the most recently pushed TAGGED image (any tag)
            # If you only want sha-* tags, add a jq filter: select(.imageTags[]|test("^sha-"))
            IMAGE_TAG="$(aws ecr describe-images \
              --repository-name "${REPO_NAME}" \
              --filter tagStatus=TAGGED \
              --query 'reverse(sort_by(imageDetails,&imagePushedAt))[0].imageTags[0]' \
              --output text)"
            if [[ -z "${IMAGE_TAG}" || "${IMAGE_TAG}" == "None" ]]; then
              echo "No tagged images found in ECR for ${REPO_NAME}" >&2
              exit 1
            fi
            IMAGE_URI="${IMAGE_REPO}:${IMAGE_TAG}"
            DIGEST=$(aws ecr describe-images \
              --repository-name "$REPO_NAME" \
              --image-ids imageTag="$IMAGE_TAG" \
              --query 'imageDetails[0].imageDigest' --output text)
            DIGEST_URI="${IMAGE_REPO}@${DIGEST}"
            echo "DIGEST_URI=$DIGEST_URI" >> $GITHUB_ENV
            fi

          echo "IMAGE_URI=${IMAGE_URI}" | tee -a "$GITHUB_OUTPUT"
          {
            echo "IMAGE_REPO=${IMAGE_REPO}"
            echo "IMAGE_TAG=${IMAGE_TAG}"
            echo "IMAGE_URI=${IMAGE_URI}"
           } >> "$GITHUB_ENV" 

```

CF stack deploy

```bash
aws cloudformation deploy \
--template-file $CF_TEMPLATE_DIR/$STACK_TEMPLATE_FILE \
--stack-name $STACK_NAME \
--capabilities CAPABILITY_NAMED_IAM \
--no-fail-on-empty-changeset \
--parameter-overrides \
    VpcId=$VPC_ID \
    PrivateSubnetIds=$PRIVATE_SUBNET \
    DBLambdaSG=$SG_PRIVATE \
    S3Bucket=$S3_BUCKET \
    LambdaImageUri=$DIGEST_URI \
```

__Coding style, parameterization and design patterns__

_17 (open) ENHANCEMENT consolidated response build_

Consistent envelopes. Centralize response building in `core/responses.py` so all success/error shapes are uniform and tested (health, version, CRUD results).

_18 (open) ENHANCEMENT logging format_

Logging correlation. Extend core/logging.Log emissions to always include request_id, method, path, route, table, op, status, duration_ms, stage, version as per spec. (Router can supply context.)

_18 (open) ENHANCEMENT auth placeholder_

Auth/Policies. Even if default is VPC-only, keep the pluggable strategy (none, key, jwt) ready and wire policy denies (DELETE, batch-delete) in prod.

__Test coverage__
tests cases to add

| id | status | type | test | description |
| - | - | - | - | - |
| 01 | open | core/engine | S3 load success/fallback | reload() rebuilds tables; env var matrix (new+legacy names). |
| 02 | open | core/table | happy-path CRUD | conditional write conflict → 409, batch partial-failure list, search expression building (pk/sk + filters). |
| 03 | open | core/router | route matching: method-path | malformed JSON → 400; policy deny in prod (DELETE & batch-delete). |
| 04 | open | core/router | Integration local handler | Use synthetic APIGW events to verify headers, envelopes, pagination token round-trip. |
| 05 | open | core/router | End to end within VPC | Full CRUD, GSI search, pagination across >1 page, rate-limit behavior (429), and policy differences between envs. |
| 06 | open | edge | Empty/unknown attributes | Empty/unknown attributes (strip or allow?), max body/array sizes, missing PK, wrong types, unknown table, forbidden in prod, bad next token, Content-Type not application/json. |